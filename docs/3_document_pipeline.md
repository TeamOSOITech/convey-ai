# Convey-AI — Technical Documentation
## Chapter 3: Document Processing Pipeline

---

## 3.1 Overview

When a solicitor uploads a document (PDF or ZIP), it passes through a 5-stage pipeline before the AI can read it. Each stage is handled by a dedicated module:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROCESSING PIPELINE                      │
│                                                                      │
│  [Upload]──►[Extract]──►[OCR]──►[Chunk]──►[Embed & Store]          │
│                                                                      │
│  zip_processor.py   ocr.py    chunker.py    embeddings.py           │
└──────────────────────────────────────────────────────────────────────┘
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

> **Important:** The temp directory is always cleaned up in a `finally` block, even if an error occurs mid-way through. This prevents temporary files from accumulating on the Railway disk.

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

## 3.3 Stage 2 — OCR Processing (`ocr.py`)

This is the most computationally intensive stage. Its job is to take a PDF (which may be a scanned image with no selectable text) and produce:
1. A **text-searchable OCR'd PDF** saved permanently to disk
2. The **extracted plain text** for chunking and embedding

### Why OCR is necessary
Solicitors frequently receive PDFs that are scanned photocopies — essentially images stored inside a PDF container. These contain zero machine-readable text. Without OCR, the AI would have nothing to read. OCRmyPDF uses Tesseract (an open-source OCR engine) to read the images and add a proper text layer.

### The full process — `process_pdf(input_pdf_bytes, filename)`

```
Step 1: Write the uploaded PDF bytes to a temp file (needed by ocrmypdf which requires a file path)

Step 2: Build the output path
        - Clean the filename (spaces → underscores, remove brackets/commas)
        - Remove any existing extension
        - Append _ocr.pdf
        - Example: "Lease Document (Copy).PDF" → "Lease_Document_Copy_ocr.pdf"
        - Full path: DATA_DIR/processed_pdfs/Lease_Document_Copy_ocr.pdf

Step 3: Run ocrmypdf.ocr(input_path, output_path, ...)
        - force_ocr=True    → processes EVERY page, even those that already have text
                              (prevents partially-OCR'd PDFs from slipping through)
        - language="eng"    → English language model for Tesseract
        - optimize=0        → skip PDF compression (faster, less CPU)
        - oversample=300    → 300 DPI upsampling for accuracy on small/blurry text
        - jobs=1            → single-threaded (Railway free tier has limited CPU)

Step 4: Open the saved OCR'd PDF with PyMuPDF (fitz)
        - Iterate over every page
        - Call page.get_text() to extract the text layer
        - Concatenate all pages into one big string

Step 5: Return {success, text, pages, saved_pdf}

Step 6 (finally): Delete the temp INPUT file
                  The OUTPUT file is kept permanently on disk
```

### OCR settings explained

| Setting | Value | Reason |
|---|---|---|
| `force_ocr` | `True` | Ensures every page is re-OCR'd. Without this, pages that already have a text layer (even a bad one) would be skipped. |
| `language` | `"eng"` | English language pack for Tesseract. Legal documents are always English. |
| `optimize` | `0` | Disables PDF compression post-OCR. Keeps output fast at the cost of slightly larger file size. |
| `oversample` | `300` | Upsamples images to 300 DPI before OCR. Dramatically improves accuracy on small or blurry scans. |
| `jobs` | `1` | Limits to a single CPU thread. Railway's free tier has limited CPU; multi-threading causes out-of-memory crashes. |

### Output

- **OCR'd PDF saved to disk:** `DATA_DIR/processed_pdfs/{clean_filename}_ocr.pdf`
  - This file is served to the frontend via `/view-pdf/{filename}` for the in-browser PDF viewer
- **Extracted text:** returned as a single Python string, passed to the chunker

### Error handling
If `ocrmypdf.ocr()` throws any exception (corrupt PDF, unsupported format, memory issue), the function catches it and returns `{"success": False, "error": "..."}`. The pipeline in `main.py` checks this and records the failure in the upload results without crashing the whole batch.

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
        "chunk_index": 7,                  # position in document (0-indexed)
        "total_chunks": 42                 # total number of chunks in this document
    }
}
```

> **Critical — the `source` key:** The `source` metadata field is the single most important piece of metadata in the entire system. Every ChromaDB query that filters by document uses `where: {"source": {"$eq": filename}}`. If this key were missing or named differently, document-specific search would fail entirely. It is set here in the chunker and relied upon by the chatbot, title check, smart extract, and form filler.

### Example
A 10-page lease document with 30,000 characters would produce approximately **60–70 chunks** with overlap.

---

## 3.5 Stage 4 — Embedding & Storage (`embeddings.py`)

The final stage converts each chunk's text into a **768-dimensional vector** (a list of 768 floating-point numbers) and stores it in ChromaDB alongside its metadata.

### The embedding model
```python
model = SentenceTransformer(
    "BAAI/bge-large-en-v1.5",
    cache_folder="./models"     # downloaded once, cached here permanently
)
```

**Why `BAAI/bge-large-en-v1.5`?**
- Specifically designed for **retrieval tasks** (finding relevant documents given a query)
- Produces 768-dimensional vectors — higher dimensional than most free models, meaning more semantic nuance is preserved
- Strong performance on legal and professional English text
- The `bge` name stands for **Beijing General Embeddings** — it is one of the top-ranked models on the MTEB (Massive Text Embedding Benchmark) leaderboard

### The `store_case_chunks()` function

```python
def store_case_chunks(chunks: list, title_number: str):

    # 1. Extract just the text strings from all chunks
    texts = [chunk["text"] for chunk in chunks]

    # 2. Convert all texts to vectors in one batch operation
    embeddings = model.encode(texts).tolist()

    # 3. Build unique IDs for each chunk
    #    Format: {TITLE_NUMBER}_{safe_source_filename}_chunk_{N}
    #    Example: EX332661_Title_Register.pdf_chunk_0
    #    Note: safe_source replaces spaces with underscores to keep IDs clean
    ids = [f"{title_number}_{chunk['metadata']['source'].replace(' ', '_')}_chunk_{i}"
           for i, chunk in enumerate(chunks)]

    # 4. Build metadata list (spread existing metadata + add title_number)
    metadatas = [
        {**chunk["metadata"], "title_number": title_number}
        for chunk in chunks
    ]

    # 5. Store everything in ChromaDB in one batch call
    case_collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )
```

### Why the ID includes the source filename
Early versions used IDs like `EX332661_chunk_0`. This caused a **silent overwrite bug**: if two documents in the same case both had a chunk 0, the second document's chunk 0 would silently overwrite the first document's chunk 0 in ChromaDB (IDs must be unique). By including the source filename in the ID, each document's chunks are guaranteed to have globally unique IDs.

### ChromaDB collections

The system uses three collections:

#### `case_documents`
- **Contents:** All text chunks from all uploaded case documents, across all cases
- **Key metadata fields:** `title_number`, `source` (filename), `chunk_index`, `total_chunks`
- **How it's queried:** Always filtered by `title_number` first. Then optionally filtered by `source` to narrow to a specific document.

#### `format_library`
- **Contents:** Standard UK conveyancing enquiry templates
- **Key metadata fields:** `code` (e.g. `A1`, `F3a`), `topic` (e.g. `"Boundaries"`)
- **How it's queried:** Semantically — given a description of an issue, find the most relevant template
- **Populated by:** `ingest_formats.py` (one-time seeding script)

#### `checklists`
- **Contents:** Freehold and Leasehold title check item descriptions
- **Key metadata fields:** `checklist_type` (`freehold`/`leasehold`), `item_id`
- **How it's queried:** By `checklist_type` to get all items for the relevant property type
- **Populated by:** `ingest_formats.py` (same script, different section)

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
Query vector: [0.023, -0.891, 0.445, ... ] (768 numbers)
         │
         ▼
ChromaDB: compare query vector against ALL stored chunk vectors
         using cosine similarity (measures angle between vectors)
         │
         ▼
Returns the N chunks whose vectors are most similar to the query vector
(i.e. chunks about rent, ground rent, annual payments, lease obligations)
```

Chunks that are **semantically similar** to the query — even if they don't share the exact same words — will score high and be returned. For example, a chunk mentioning "yearly payment to the freeholder" would rank highly for "annual ground rent" even without those exact words.

---

## 3.7 The `ingest_formats.py` Script

This is a **one-time setup script** that populates the `format_library` and `checklists` ChromaDB collections. It does not run during normal operation — it is only run when:
1. Setting up the server for the first time
2. Adding new enquiry templates to the library
3. Rebuilding after the ChromaDB data is wiped

### How to run it
```bash
cd backend
python ingest_formats.py
# Or via the API endpoint:
# POST /reingest-formats
```

### What it contains
The script contains the entire library of standard UK conveyancing enquiries hardcoded as Python strings. Each enquiry has:
- A **code** (e.g. `A1`, `B2`, `F3a`) — standard SCPC/Law Society enquiry reference
- A **topic** (e.g. `"Boundaries"`, `"Title Guarantee"`)
- A **draft** (the full text of the standard enquiry letter wording)

These are embedded using the same `BAAI/bge-large-en-v1.5` model and stored in `format_library` so the AI can find the most relevant template for any issue a solicitor describes.

> **Maintenance note:** When new enquiry formats are added to `ingest_formats.py`, hit `POST /reingest-formats` on the live Railway server to rebuild the collection. This wipes the existing collection first to avoid duplicate entries.

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
│     Runs tesseract OCR on all 40 pages
│     Saves: /app/data/processed_pdfs/Lease_ocr.pdf  ← stays on disk permanently
│     Returns: 40,000 characters of text
│
├─► chunker.py
│     Splits 40,000 chars into ~75 chunks (600 chars each, 200 overlap)
│     Each chunk: {text: "...", metadata: {source: "Lease.pdf", chunk_index: N}}
│
├─► embeddings.py
│     Encodes 75 texts into 75 × 768-d vectors
│     Stores in ChromaDB case_documents collection
│     IDs: "EX332661_Lease.pdf_chunk_0" through "EX332661_Lease.pdf_chunk_74"
│
├─► database.py
│     Inserts into Supabase case_documents:
│     {title_number: "EX332661", doc_type: "LEASE", filename: "Lease.pdf",
│      file_url: "https://railway.../view-pdf/Lease_ocr.pdf"}
│
└─► Response to frontend: {success: true, pages: 40, total_chunks: 75}
```

From this point, every AI feature in the system can find and read this lease by querying ChromaDB with `{"title_number": "EX332661", "source": "Lease.pdf"}`.

---

*Next: Chapter 4 — AI Services*
