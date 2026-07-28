# Convey-AI — Technical Documentation
## Chapter 3: Document Processing Pipeline

---

## 3.1 Overview

When a solicitor uploads a document (PDF or ZIP), it passes through several stages before the AI can read it. Each stage is handled by a dedicated module:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROCESSING PIPELINE                              │
│                                                                                │
│  [Extract]──►[OCR + Extract]──►[Chunk]──►[Embed & Store]──►[Upload]          │
│                                                                                │
│  zip_processor.py    ocr.py       chunker.py    embeddings.py    storage.py  │
└──────────────────────────────────────────────────────────────────────────────┘
```

This pipeline runs synchronously per document during the upload request. The frontend waits for the full pipeline to complete before showing the success state.

---

## 3.2 Stage 1 — ZIP Extraction (`zip_processor.py`)

This stage only runs when the user uploads a **ZIP file** (i.e. a full contract pack). Single PDF uploads skip this stage.

### What it does
`extract_zip(zip_bytes: bytes) → list` takes the raw bytes of a ZIP file and extracts every PDF inside it. For each PDF found, it identifies the document type from the filename.

### The full process
```
1. Write ZIP bytes to a temporary file on disk
2. Open and extract the ZIP to a temp directory
3. Walk every file in the extracted directory tree
4. For each file ending in .pdf (case-insensitive):
   a. Read its bytes
   b. Call identify_doc_type(filename) to guess the doc type
   c. Append {filename, pdf_bytes, doc_type} to results list
5. Delete the temp directory (runs in finally block — always happens)
6. Return the list of extracted documents
```

> **Important:** The temp directory is always cleaned up in a `finally` block, even if an error occurs mid-way through. This is local, transient disk use inside the Railway container during a single request — it's unrelated to document *storage*, which lives entirely in Supabase (see Stage 5).

### Document Type Detection — `identify_doc_type(filename)`

The function performs a case-insensitive keyword scan of the filename. It checks the filename against a dictionary of keywords for each document type:

| Doc Type | Keywords that trigger it |
|---|---|
| `TA6` | `ta6`, `property information`, `pif`, `seller` |
| `TA7` | `ta7`, `leasehold`, `fittings`, `contents`, `fcf` |
| `TA10` | `ta10`, `fittings and contents` |
| `TR1` | `tr1`, `transfer` |
| `OCE` | `official copy`, `oce`, `title register`, `hmlr` |
| `LEASE` | `lease`, `underlease`, `tenancy` |
| `EPC` | `epc`, `energy performance` |
| `CONTRACT` | `contract`, `draft contract` |
| `SEARCHES` | `search`, `drainage`, `environmental`, `local authority` |
| `MORTGAGE` | `mortgage`, `charge`, `lender` |
| `OTHER` | Default — used when no keyword matches |

**Example detections:**
- `"Title_Register_EX123.pdf"` → `OCE` (matches `title register`)
- `"TA6_Form_Seller.pdf"` → `TA6` (matches `ta6`)
- `"Draft_Contract_v2.pdf"` → `CONTRACT` (matches `draft contract`)
- `"Survey_Report.pdf"` → `OTHER` (no keyword matches)

> **To add new keywords:** Edit the `DOC_TYPE_KEYWORDS` dictionary in `zip_processor.py`. This is frequently updated as the firm's document naming conventions become clearer.

---

## 3.3 Stage 2 — OCR & Text Extraction (`ocr.py`)

This stage actually OCRs the PDF (via `ocrmypdf`/Tesseract) before extracting word-level text with bounding boxes (used later for PDF highlighting/citations). It has to: many real-world uploads — e.g. HM Land Registry "official copies" — are scanned images with no native text layer at all. Reading those with PyMuPDF alone returns nothing but the odd digitally-stamped footer, not the actual document content.

### The full process — `process_pdf(pdf_bytes, filename)`

```
1. Write pdf_bytes to a temp file — ocrmypdf needs a real file path, not bytes
2. Run ocrmypdf.ocr(input_path, output_path, force_ocr=True, language="eng",
   optimize=0, oversample=300, jobs=1)
   → force_ocr=True re-OCRs EVERY page, even ones that already have a text
     layer, so a partially-OCR'd PDF can't slip through
   → this embeds a real, correctly-positioned text layer over the scanned
     image, using Tesseract's word-level bounding boxes
3. Read the OCR'd output back into memory (ocr_pdf_bytes) — this is the
   searchable copy that gets uploaded to Supabase Storage (Stage 5), not
   the raw original upload
4. Open the OCR'd PDF with PyMuPDF, and for every page:
   a. Read page width/height
   b. Extract words with bounding boxes via page.get_text("words") —
      now populated with Tesseract's OCR output, not just pre-existing text
   c. Group words into line-ish blocks (splits every ~100 chars or on a newline)
5. Return {success, pages: [{page, blocks, width, height}, ...], filename, ocr_pdf_bytes}
6. Delete both temp files (finally block) — nothing is kept on local disk;
   the durable copy is whatever the caller uploads to Storage
```

### OCR settings explained

| Setting | Value | Reason |
|---|---|---|
| `force_ocr` | `True` | Ensures every page is re-OCR'd, even ones with an existing (possibly bad) text layer. |
| `language` | `"eng"` | English language pack for Tesseract — legal documents are always English. |
| `optimize` | `0` | Disables PDF compression post-OCR — faster, avoids errors. |
| `oversample` | `300` | Upsamples images to 300 DPI before OCR — dramatically improves accuracy on small/blurry scans, at a real memory cost. |
| `jobs` | `1` | Single-threaded — Railway's tier has limited CPU/memory; this setting has previously been the lever pulled to fix OOM crashes if `oversample` proves too expensive in practice. |

### Error handling
If OCR or extraction throws any exception (corrupt PDF, unsupported format, OOM), the function catches it and returns `{"success": False, "error": "..."}`. The pipeline in `main.py` checks this and records the failure in the upload results without crashing the whole batch.

---

## 3.4 Stage 3 — Text Chunking (`chunker.py`)

An AI model cannot be given an entire 50-page legal document as one block of text — it is far too large. The chunker splits the extracted text into smaller, overlapping pieces called **chunks** that can be individually embedded and searched.

### The splitter configuration

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,      # maximum characters per chunk
    chunk_overlap=200,   # how many characters are shared between adjacent chunks
    separators=["\n\n", "\n", ".", " "]  # preference order for where to split
)
```

### Chunk size reasoning
- **600 characters** ≈ roughly one paragraph of dense legal text
- This is small enough for precise semantic search (a too-large chunk buries the relevant sentence)
- This is large enough to retain context within a single answer (a too-small chunk gives isolated fragments)

### Chunk overlap reasoning
- **200 characters** of overlap means the last 200 characters of chunk N are also the first 200 characters of chunk N+1
- **Why this matters:** If a critical sentence sits at the boundary between two chunks, without overlap one half would be in chunk N and the other half in chunk N+1 — neither chunk would be complete enough to answer a question about that sentence. Overlap ensures every sentence is fully contained within at least one chunk.

### Separator hierarchy
LangChain's `RecursiveCharacterTextSplitter` tries separators in order, preferring to split at natural language boundaries:
1. `\n\n` — double newline (paragraph break) — most preferred
2. `\n` — single newline (line break)
3. `.` — end of sentence
4. ` ` — word boundary — last resort

This means chunks always end at a natural language boundary wherever possible, rather than cutting words in half.

### The chunk format
Each chunk is returned as a dictionary:

```python
{
    "text": "...the actual text of this chunk...",
    "metadata": {
        "source": "Title_Register.pdf",   # original filename — used for filtering
        "title_number": "EX332661",
        "page": 3,
        "bbox": [0.12, 0.30, 0.88, 0.34], # normalised 0-1 coordinates, or None
        "chunk_index": 7,                  # position in document (0-indexed)
        "total_chunks": 42                 # total number of chunks in this document
    }
}
```

> **Critical — the `source` key:** The `source` metadata field is the single most important piece of metadata in the entire system. Every vector-store query that filters by document uses `title_number` + `source` (filename). If this key were missing or named differently, document-specific search would fail entirely. It is set here in the chunker and relied upon by the chatbot, title check, smart extract, and form filler.

### Example
A 10-page lease document with 30,000 characters would produce approximately **60–70 chunks** with overlap.

---

## 3.5 Stage 4 — Embedding & Storage (`embeddings.py`)

Each chunk's text is converted into a **384-dimensional vector** and stored in Supabase Postgres (via the `pgvector` extension) alongside its metadata — see `backend/sql/pgvector_schema.sql` for the table definitions.

### The embedding model
```python
model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    cache_folder="./models"     # downloaded once, cached here permanently
)
```

**Why `all-MiniLM-L6-v2`?**
- Small and fast (384-dim output) — chosen specifically to keep the backend's memory footprint low enough for Railway's free/hobby tier
- Runs entirely in-process; no external embedding API call, no per-request cost
- Good general-purpose semantic search quality for a model this size

> If you see references elsewhere to `BAAI/bge-large-en-v1.5` (1024-dim, "Beijing General Embeddings") — that was an earlier, larger model this project used before the switch to MiniLM. It's no longer in the code. Because the vector column is now a fixed `vector(384)` in Postgres, a future model swap to a different dimensionality would need a schema migration, not just a code change — Postgres rejects a mismatched-dimension insert outright rather than silently corrupting data.

### The `store_case_chunks()` function

```python
def store_case_chunks(chunks: list, title_number: str):

    # 1. Extract just the text strings from all chunks
    texts = [chunk["text"] for chunk in chunks]

    # 2. Convert all texts to vectors in one batch operation
    vectors = model.encode(texts).tolist()

    # 3. Build one row per chunk, with a globally-unique ID
    #    Format: {TITLE_NUMBER}_{safe_source}_p{page}_c{chunk_index}_{uuid8}
    #    Example: EX332661_Title_Register.pdf_p3_c7_a1b2c3d4
    rows = [...]  # id, title_number, source, page, chunk_index, total_chunks,
                  # bbox, content, embedding

    # 4. Insert everything into Postgres in one batch call
    supabase.table("document_chunks").insert(rows).execute()
```

### Why the ID includes the source filename
Early versions used IDs like `EX332661_chunk_0`. This caused a **silent overwrite bug**: if two documents in the same case both had a chunk 0, the second document's chunk 0 would silently overwrite the first document's chunk 0 (IDs must be unique). By including the source filename (and now the page number) in the ID, each document's chunks are guaranteed to have globally unique IDs.

### The two pgvector tables

#### `document_chunks`
- **Contents:** All text chunks from all uploaded case documents, across all cases
- **Key columns:** `title_number`, `source` (filename), `page`, `chunk_index`, `total_chunks`, `bbox`, `content`, `embedding`
- **How it's queried:** Always filtered by `title_number` first (via the `match_document_chunks` Postgres function for similarity search, or a plain filtered `select` for "give me every chunk of this document"). Optionally filtered by `source` to narrow to a specific document.

#### `format_library`
- **Contents:** Standard UK conveyancing enquiry templates
- **Key columns:** `code` (e.g. `A1`, `F3a`), `topic` (e.g. `"Boundaries"`), `content`
- **How it's queried:** Semantically via the `match_format_library` function — given a description of an issue, find the most relevant template. Also supports a deterministic lookup by `id` (`"enquiry_A1"`) or `code`.
- **Populated by:** `ingest_formats.py` (one-time seeding script)

> A third collection, `checklists`, existed in an earlier ChromaDB-based version of this system but was never actually written to or queried by any code path. It was dropped during the move to pgvector rather than carried forward as dead schema.

---

## 3.6 How Semantic Search Works

When the chatbot or any AI feature searches for relevant context, this is what happens mathematically:

```
User question: "What is the annual ground rent?"
         │
         ▼
model.encode(["What is the annual ground rent?"])
         │
         ▼
Query vector: [0.023, -0.891, 0.445, ... ] (384 numbers)
         │
         ▼
Postgres (pgvector): compare query vector against stored chunk vectors
         for this title_number using cosine distance (the <=> operator),
         via the match_document_chunks() SQL function
         │
         ▼
Returns the N chunks whose vectors are most similar to the query vector
(i.e. chunks about rent, ground rent, annual payments, lease obligations)
```

Chunks that are **semantically similar** to the query — even if they don't share the exact same words — will score high and be returned. For example, a chunk mentioning "yearly payment to the freeholder" would rank highly for "annual ground rent" even without those exact words.

---

## 3.7 The `ingest_formats.py` Script

This is a **one-time setup script** that populates the `format_library` table. It does not run during normal operation — it is only run when:
1. Setting up a new Supabase project for the first time
2. Adding new enquiry templates to the library
3. Rebuilding after the table is wiped

### How to run it
```bash
cd backend
python ingest_formats.py
# Or via the API endpoint:
# POST /reingest-formats
```

### What it contains
The script contains the entire library of standard UK conveyancing enquiries hardcoded as Python dicts. Each enquiry has:
- A **code** (e.g. `A1`, `B2`, `F3a`) — standard SCPC/Law Society enquiry reference
- A **topic** (e.g. `"Boundaries"`, `"Title Guarantee"`)
- A **text** (the full draft wording of the standard enquiry letter)

These are embedded using the same `all-MiniLM-L6-v2` model, via `embeddings.store_format_entries()`, which does a genuine wipe-and-rebuild (delete all rows, then insert fresh) so re-running the script or hitting `/reingest-formats` is always safe and idempotent.

> **Maintenance note:** When new enquiry formats are added to `ingest_formats.py`, hit `POST /reingest-formats` on the live Railway server to rebuild the table.

---

## 3.8 Data Flow Summary

The complete journey from upload to AI-readable:

```
solicitor uploads "Lease.pdf" for case "EX332661"
│
├─► zip_processor.py   (only if ZIP)
│     Extracts Lease.pdf, identifies doc_type = "LEASE"
│
├─► ocr.py
│     Runs ocrmypdf/Tesseract on all 40 pages (temp file in, temp file out)
│     Reads text + bounding boxes from the OCR'd result via PyMuPDF
│     Returns: pages with word blocks + ocr_pdf_bytes (temp files deleted after)
│
├─► chunker.py
│     Splits the page text into ~75 chunks (600 chars each, 200 overlap)
│     Each chunk: {text: "...", metadata: {source: "Lease.pdf", page: N, chunk_index: N}}
│
├─► embeddings.py
│     Encodes 75 texts into 75 × 384-d vectors
│     Inserts into Postgres document_chunks table
│     IDs: "EX332661_Lease.pdf_p1_c0_a1b2c3d4" ... one per chunk
│
├─► storage.py
│     Uploads ocr_pdf_bytes (the searchable, OCR'd copy — not the raw upload)
│     to Supabase Storage. Path: EX332661/Lease_ocr.pdf (private bucket)
│
├─► database.py
│     Inserts into Supabase case_documents:
│     {title_number: "EX332661", doc_type: "LEASE", filename: "Lease.pdf",
│      file_url: "EX332661/Lease_ocr.pdf"}   ← a Storage path, not a URL
│
└─► Response to frontend: {success: true, pages: 40, total_chunks: 75, download_url: <signed URL>}
```

From this point, every AI feature in the system can find and read this lease by querying `document_chunks` with `title_number = "EX332661" AND source = "Lease.pdf"`, and can fetch the PDF itself from Supabase Storage.

---

*Next: Chapter 4 — AI Services*
