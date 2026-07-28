# Convey-AI — Technical Documentation
## Chapter 2: Backend Core Infrastructure

---

## 2.1 Overview

The backend is a single **FastAPI** application written in Python 3.11. It acts as the brain of Convey-AI — it receives requests from the Next.js frontend, orchestrates document processing, queries the vector database, calls external AI APIs, and reads/writes the Supabase PostgreSQL database.

**File:** `backend/main.py`  
**Entry point:** `uvicorn main:app --host 0.0.0.0 --port 8080`

All business logic is split across purpose-built modules. `main.py` purely defines the HTTP routes (endpoints) and calls into those modules. It does **not** contain AI logic, chunking logic, or database queries directly — those live in their own files.

---

## 2.2 Application Startup Sequence

When `uvicorn main:app` is called, Python executes `main.py` from top to bottom. The startup sequence is:

```
1. Imports — all modules are loaded (embeddings.py loads the SentenceTransformer
   model into RAM; storage.py connects to Supabase and ensures the Storage
   bucket exists)
2. FastAPI app object created
3. CORS middleware applied — restricts which origins can call the API
4. DEV_MODE flag read — gates debug endpoints
5. Route functions defined
6. Route modules imported and registered via app.include_router()
```

> **Critical:** The `embeddings.py` module is imported at startup, which loads the `all-MiniLM-L6-v2` embedding model into RAM. This is the only local/in-memory state the backend holds — documents, metadata, and vectors all live in Supabase, so there's no local disk to initialise.

---

## 2.3 Module Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | HTTP routes (endpoints), startup, CORS |
| `auth_utils.py` | JWT token validation dependency (`require_auth`) |
| `database.py` | All Supabase Postgres read/write operations |
| `storage.py` | Supabase Storage operations — upload/download/delete/signed-URL for processed PDFs |
| `embeddings.py` | Embedding model, pgvector storage & similarity search (Postgres) |
| `chunker.py` | Splits long text into overlapping chunks for storage |
| `ocr.py` | PDF → searchable text via OCRmyPDF + PyMuPDF |
| `zip_processor.py` | Extracts PDFs from a ZIP archive and detects document types |
| `chatbot.py` | RAG chatbot (ask_question) and enquiry generation (raise_enquiry) |
| `title_report.py` | Title Report generation using Gemini |
| `title_check.py` | TA6/TA10 form analysis, enquiry matching, draft generation |
| `ingest_formats.py` | One-time script to populate the format_library table |
| `routes/formats.py` | `GET /formats/{code}` — fetch an enquiry template by code |
| `routes/smart_extract.py` | `POST /smart-extract` — free-form AI extraction from a document |
| `routes/form_filler.py` | `POST /form-extract` — AI fill a legal form (TR1 etc.) from case docs |

---

## 2.4 Authentication — `auth_utils.py`

Every protected endpoint uses FastAPI's dependency injection with `Depends(require_auth)`. This means FastAPI automatically calls `require_auth()` before executing the actual endpoint function. If it raises an exception, the endpoint never runs.

```python
# How a protected route looks:
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), _user=Depends(require_auth)):
    ...
```

### How `require_auth` works step by step

```python
async def require_auth(authorization: str = Header(default=None)):
    # 1. Check the Authorization header exists and starts with "Bearer "
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    # 2. Strip the "Bearer " prefix to get the raw JWT
    token = authorization[len("Bearer "):].strip()

    # 3. Call Supabase to validate the token (run in a thread to not block async event loop)
    user_response = await asyncio.to_thread(_supabase_auth.auth.get_user, token)

    # 4. If Supabase says user is valid, return the user object
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_response.user
```

> **Why `asyncio.to_thread`?** FastAPI's event loop is async. The Supabase Python client's `auth.get_user()` is a **synchronous blocking call**. Calling it directly would freeze the event loop, preventing any other request from being processed. Wrapping it in `asyncio.to_thread()` runs it in a thread pool, keeping the server responsive.

---

## 2.5 Database Layer — `database.py`

This module is the only place in the entire backend that directly talks to **Supabase PostgreSQL**. All other modules call these functions instead of touching Supabase directly.

### Functions

#### `create_case(title_number: str)`
Creates a new case in the `cases` table. If the case already exists (same title number), it returns the existing case without throwing an error. This is called defensively at upload time so uploads always succeed even if the case was already created.

```python
# Behaviour:
# - Case does NOT exist → INSERT → returns {success: True, case: {...}, created: True}
# - Case DOES exist     → returns {success: True, case: {...}, created: False}
```

#### `add_document(title_number, doc_type, filename, file_url)`
Registers a processed document in the `case_documents` table. Called after OCR + embedding is complete. Despite the name, `file_url` stores the **Supabase Storage path** (e.g. `EX332661/Lease_ocr.pdf`), not a URL — see `get_case()` below for why.

**`doc_type` values:**
| Code | Meaning |
|---|---|
| `OCE` | Official Copy of the Title Register (Land Registry) |
| `LEASE` | Lease document |
| `TR1` | Transfer of Whole form |
| `CONTRACT` | Sale/Purchase contract |
| `TA6` | Property Information Form |
| `TA10` | Fittings & Contents form |
| `EPC` | Energy Performance Certificate |
| `OTHER` | Any document that doesn't match the above |

#### `get_case(title_number: str)`
Fetches a case and ALL of its documents. This is the main query the frontend uses to populate the case page. For each document, it swaps the stored Storage *path* for a freshly-minted 1-hour **signed URL** (via `storage.get_signed_url()`) before returning — the frontend never sees a raw path, and the bucket stays private. If signing fails for a row (e.g. a stale/legacy path), `file_url` comes back `null` rather than breaking the whole response. Returns:
```json
{
  "success": true,
  "case": { "id": "...", "title_number": "EX332661", "status": "active" },
  "documents": [
    { "id": "...", "doc_type": "OCE", "filename": "Title_Register.pdf", "file_url": "https://...supabase.co/storage/v1/object/sign/..." },
    ...
  ]
}
```

#### `get_all_cases()`
Returns all cases ordered by `created_at` descending. Used by the dashboard to list every active case.

#### `delete_document(document_id, title_number)`
Looks up the document by ID, records its filename, then deletes the Supabase record. Returns the filename to the caller (`main.py`) so it can also delete the object from Supabase Storage and remove the document's chunks from `document_chunks`.

---

## 2.6 Complete API Endpoint Reference

All endpoints listed below. Protected endpoints require `Authorization: Bearer <token>` header.

### System Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | ❌ | Health check — returns `{"message": "Convey AI backend is running"}` |
| `GET` | `/health` | ❌ | Returns `{"status": "ok"}` — used by Railway health checks |

### Document Management Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/upload-pdf` | ✅ | Upload a single PDF. Full pipeline: OCR → chunk → embed → Storage upload → Supabase register |
| `POST` | `/upload-zip` | ✅ | Upload a ZIP of PDFs. Extracts, OCRs, chunks, and ingests all files in one call |

### Case Management Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/cases` | ✅ | Create a new case by title number |
| `GET` | `/cases` | ✅ | Get all cases (dashboard) |
| `GET` | `/cases/{title_number}` | ✅ | Get a specific case + all its documents |
| `DELETE` | `/cases/{title_number}/documents/{document_id}` | ✅ | Delete a document from Supabase (row, Storage object, and vector chunks) |

### AI Tool Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/chat` | ✅ | Chatbot Q&A. Body: `{question, history, current_document}` |
| `POST` | `/raise-enquiry` | ✅ | Generate a legal enquiry draft. Body: `{issue, history, current_document}` |
| `POST` | `/generate-title-report` | ✅ | Generate a full title report from selected documents |
| `POST` | `/title-check` | ✅ | Run Title Check pipeline on a TA6/TA10 file |
| `GET` | `/formats/{code}` | ✅ | Fetch an enquiry template by code (e.g. `A1`, `F3a`) |
| `GET` | `/search-formats` | ❌ | Search format library by topic (test/dev utility) |
| `POST` | `/smart-extract` | ✅ | Free-form AI extraction from a single document |
| `POST` | `/form-extract` | ✅ | Extract TR1 (or other form) panel data from selected documents |

### Utility / Maintenance Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/ingest-formats` | ❌ | Seed the format_library table (run once after deploy) |
| `POST` | `/reingest-formats` | ❌ | Wipe and rebuild the format_library collection |
| `GET` | `/find-page` | ❌ | Estimate which PDF page a search phrase is on (used by chatbot InPage Ref pills) |

### Debug Endpoints (DEV_MODE=true only)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/debug-chunks/{title_number}` | ❌ | Show 5 raw document_chunks rows for a case |
| `GET` | `/debug-query/{title_number}` | ❌ | Show what chunks the chatbot would retrieve for a given query |
| `GET` | `/debug-sources/{title_number}` | ❌ | List all unique source filenames stored for a case |

> **Note:** Debug endpoints return `HTTP 403` in production (`DEV_MODE=false`). Set `DEV_MODE=true` in your local `.env` to enable them.

---

## 2.7 The Upload Pipeline — Step by Step

This is the most critical flow in the backend. When a user uploads a document, this is what happens:

```
User uploads PDF (or ZIP)
         │
         ▼
POST /upload-pdf (or /upload-zip)
         │
         ├── 1. READ — file bytes loaded from HTTP request into memory
         │
         ├── 2. EXTRACT (ZIP only) — zip_processor.py extracts individual PDFs
         │         and auto-detects doc_type from filename keywords
         │
         ├── 3. OCR/EXTRACT — ocr.py reads text + bounding boxes from every page
         │         via PyMuPDF (no separate OCR'd file is produced or saved)
         │
         ├── 4. CHUNK — chunker.py splits the extracted text
         │         → Uses LangChain RecursiveCharacterTextSplitter
         │         → chunk_size=600, chunk_overlap=200
         │         → Each chunk carries metadata: {source: filename, chunk_index: N}
         │
         ├── 5. EMBED — embeddings.py converts each chunk to a 384-d vector
         │         → Model: all-MiniLM-L6-v2 (runs locally on Railway)
         │         → Stored in the document_chunks Postgres table (pgvector)
         │         → Each row ID: {title_number}_{safe_source}_p{page}_c{chunk_index}_{uuid}
         │
         ├── 6. UPLOAD — storage.py uploads the PDF bytes to Supabase Storage
         │         at {title_number}/{clean_name}_ocr.pdf (private bucket)
         │
         ├── 7. REGISTER — database.py writes to Supabase case_documents table
         │         → Records: title_number, doc_type, filename, file_url (Storage path)
         │
         └── 8. RESPOND — returns JSON with success status, page count, chunk count,
                   and a freshly-signed download_url for the uploaded PDF
```

### Filename Cleaning

All filenames are cleaned before being used as a Supabase Storage key, to avoid URL and object-key issues:

```python
def make_clean_filename(filename: str) -> str:
    cleaned = filename
        .replace(" ", "_")    # spaces → underscores
        .replace(",", "")     # remove commas
        .replace("(", "")     # remove parentheses
        .replace(")", "")
    # Append _ocr suffix and normalise extension
    if cleaned.endswith(".PDF") or cleaned.endswith(".pdf"):
        cleaned = cleaned[:-4] + "_ocr.pdf"
    return cleaned

# Example: "Title Register (Copy).PDF" → "Title_Register_Copy_ocr.pdf"
# Storage key: {title_number}/Title_Register_Copy_ocr.pdf
```

> **§2.8 used to document `/view-pdf/{filename}`**, a route that served processed PDFs directly off local disk with manual path-traversal checks. That route and the local-disk pipeline behind it have been removed — processed PDFs now live in a private Supabase Storage bucket (see `storage.py`), and the frontend loads them via a signed URL returned from `database.get_case()`. No proxy route or manual path sanitisation is needed since the frontend never sends a raw filename to the backend to fetch a PDF.

---

## 2.9 Route Modules — `routes/`

To keep `main.py` clean and maintainable, newer tool endpoints are placed in separate files under `routes/` using FastAPI's `APIRouter`. This is the pattern all new tools should follow.

### How to add a new tool endpoint

1. Create `routes/your_tool.py`
2. Define `router = APIRouter()` at the top
3. Define your endpoint with `@router.post("/your-endpoint")`
4. At the bottom of `main.py`, add:
```python
from routes.your_tool import router as your_tool_router
app.include_router(your_tool_router)
```

### `routes/formats.py` — `GET /formats/{code}`
Fetches a single enquiry template from the `format_library` table by its code. Used when a solicitor manually adds an enquiry on the Title Check review board. Tries uppercase match first, then falls back to case-sensitive match.

### `routes/smart_extract.py` — `POST /smart-extract`
Takes a `title_number`, `filename`, and free-form `instructions` string. Fetches all chunks for that file (already in reading order via `embeddings.get_document_chunks`), concatenates the full document text, then sends it to Gemini with the user's instructions. Returns markdown-formatted extraction results.

> **Design note:** The frontend calls this endpoint **once per file** in a sequential loop (not all files in one call). This avoids Vercel's 100-second function timeout — each individual file extraction is well under the limit.

### `routes/form_filler.py` — `POST /form-extract`
Similar to smart_extract but structured for form completion. Takes a `form_type` (e.g. `TR1`), a list of `filenames`, and looks up the matching prompt from the `FORM_PROMPTS` dictionary. Sends all selected documents concatenated to Gemini, which returns a strict JSON object with one key per form panel (e.g. `panel_1`, `panel_2`... `panel_12`). Strips markdown code fences from the response before JSON parsing.

**To add a new form type:** Add a new key to `FORM_PROMPTS` in `routes/form_filler.py`. No other code changes needed.

---

## 2.10 The `/find-page` Endpoint

This is a clever utility endpoint used by the chatbot's **InPage Ref pills** — the clickable references that jump to a specific page in the PDF viewer.

**The problem:** Chrome's PDF viewer supports `#page=N` in the URL but does NOT support `#search=text`. So when the AI says "see [InPage Ref.: Restrictive Covenants]", the frontend needs to convert that text phrase into a page number.

**The solution:**
```
1. Fetch all chunks for the document (embeddings.get_document_chunks — already
   sorted in reading order by chunk_index)
2. Try exact substring match for the search phrase → if found, record chunk position
3. If no exact match → fuzzy match using difflib.SequenceMatcher
4. Estimate page = floor(chunk_position / CHUNKS_PER_PAGE) + 1
   (CHUNKS_PER_PAGE = 5, based on ~600 chars/chunk and ~3000 chars/A4 page)
```

Returns `{"page": 3, "match_score": 0.85, "found": true}`. The frontend appends `#page=3` to the PDF URL.

---

## 2.11 Error Handling Philosophy

All AI endpoints follow this pattern: **always return JSON, never let FastAPI return an HTML 500 page.**

```python
@app.post("/generate-title-report")
async def generate_title_report_route(...):
    try:
        result = generate_title_report(...)
        return result
    except Exception as e:
        print(f"[TitleReport Error] {title_number}: {str(e)}")  # Logged to Railway
        return JSONResponse(
            status_code=500,
            content={"detail": f"Report generation failed: {str(e)}"}
        )
```

This ensures the frontend's `if (!res.ok)` check always gets a parseable JSON body with a `detail` key, and can display a clean error message to the user instead of crashing.

---

*Next: Chapter 3 — Document Processing Pipeline*
