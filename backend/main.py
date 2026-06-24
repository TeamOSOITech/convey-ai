# main.py — main backend server file

from fastapi import FastAPI, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from ocr import process_pdf
from chunker import chunk_text
from embeddings import store_case_chunks, search_formats, case_collection
from chatbot import ask_question, raise_enquiry
from database import create_case, add_document, get_case, get_all_cases, delete_document
import os
from pydantic import BaseModel
from typing import List, Optional
from zip_processor import extract_zip
from chatbot import ask_question, raise_enquiry
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from title_report import generate_title_report
from title_check import run_title_check


# Create required folders if they don't exist
# Railway starts with a clean filesystem so we need to create these

"""In embeddings.py:
pythonDATA_DIR = os.getenv("DATA_DIR", "./data")
client = chromadb.PersistentClient(path=f"{DATA_DIR}/chroma_db")
In ocr.py:
pythonDATA_DIR = os.getenv("DATA_DIR", "./data")
PROCESSED_FOLDER = f"{DATA_DIR}/processed_pdfs"
In main.py:
pythonDATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(f"{DATA_DIR}/processed_pdfs", exist_ok=True)
os.makedirs(f"{DATA_DIR}/chroma_db", exist_ok=True)
Then in Railway Variables add:
DATA_DIR=/app/data
Locally it uses ./data, on Railway it uses /app/data. Clean and portable."""

# Set data directory — uses /app/data on Railway, ./data locally
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Create required folders
os.makedirs(f"{DATA_DIR}/processed_pdfs", exist_ok=True)
os.makedirs(f"{DATA_DIR}/chroma_db", exist_ok=True)

# Create FastAPI app BEFORE mounting anything
app = FastAPI()

# Mount static files AFTER app is created
app.mount("/processed", StaticFiles(directory=f"{DATA_DIR}/processed_pdfs"), name="processed")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_origins=[
        "http://localhost:3000",
        "https://convey-ai-mauve.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── JWT Authentication ────────────────────────────────────────────────────────
# Verifies the Supabase JWT attached by the frontend on every request.
# The frontend sends: Authorization: Bearer <supabase_access_token>
# We pass that token to Supabase's auth.get_user() which validates it server-side.
# This ensures only logged-in users can access any data endpoints.

from supabase import create_client as _create_supabase_client
_supabase_auth = _create_supabase_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

async def require_auth(authorization: str = Header(default=None)):
    """
    FastAPI dependency — call as Depends(require_auth) on any protected route.
    Extracts the Bearer token from the Authorization header and validates it
    against Supabase. Raises 401 if missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>"
        )
    token = authorization[len("Bearer "):].strip()
    try:
        user_response = _supabase_auth.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Set to True locally for debug endpoints. Railway should NOT set this.
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

def make_clean_filename(filename: str) -> str:
    """
    Cleans filename to be URL and filesystem safe
    Handles both .pdf and .PDF extensions
    """
    # Remove special characters first
    cleaned = filename\
        .replace(" ", "_")\
        .replace(",", "")\
        .replace("(", "")\
        .replace(")", "")
    
    # Replace extension with _ocr.pdf — handle both cases
    if cleaned.endswith(".PDF"):
        cleaned = cleaned[:-4] + "_ocr.pdf"
    elif cleaned.endswith(".pdf"):
        cleaned = cleaned[:-4] + "_ocr.pdf"
    
    return cleaned

@app.post("/ingest-formats")
async def ingest_formats_route():
    """One-time route to populate format library in ChromaDB — delete after use"""
    # No title_number here — removed the erroneous .upper() call
    from ingest_formats import ingest_all_enquiries
    ingest_all_enquiries()
    return {"success": True, "message": "Format library ingested"}

@app.get("/view-pdf/{filename}")
async def view_pdf(filename: str):
    """
    Serves a processed PDF file for inline viewing in the browser.

    Security: Uses pathlib to resolve the canonical absolute path and verifies
    it stays within the intended 'processed_pdfs' directory, preventing path
    traversal attacks (e.g. ../../.env).
    """
    import pathlib

    # Reject obvious traversal attempts fast — before touching the filesystem
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Build the allowed base directory and resolve both to absolute canonical paths
    base_dir = pathlib.Path(DATA_DIR).resolve() / "processed_pdfs"
    requested_path = (base_dir / filename).resolve()

    # Verify the resolved path is still inside the allowed base directory.
    # This catches encoded traversal like %2e%2e/ that slips past the string check above.
    if not str(requested_path).startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not requested_path.exists():
        # Do NOT reveal the server-side path in the error response
        raise HTTPException(status_code=404, detail="File not found")

    # Safely encode the filename for the Content-Disposition header to prevent
    # header injection via newline characters in filenames
    import urllib.parse
    safe_filename = urllib.parse.quote(filename)

    return FileResponse(
        path=str(requested_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Content-Type": "application/pdf",
            # Allow our Vercel frontend (all subdomains, including preview URLs)
            # and localhost on any port to embed this PDF in an iframe.
            # *.vercel.app covers production + all branch/preview deployments.
            "Content-Security-Policy": (
                "frame-ancestors 'self' "
                "https://*.vercel.app "
                "http://localhost:* "
                "https://localhost:*"
            ),
        }
    )

@app.get("/")
def home():
    return {"message": "Convey AI backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-zip")
async def upload_zip(file: UploadFile = File(...), title_number: str = "UNKNOWN", _user=Depends(require_auth)):
    """
    Receives a contract pack ZIP
    Extracts all PDFs, OCRs each one, stores everything under the title number
    """
    # Normalise title number to uppercase so it matches ChromaDB and Supabase consistently
    title_number = title_number.upper()

    # Step 1: Read ZIP bytes
    zip_bytes = await file.read()

    # Step 2: Extract all PDFs from ZIP
    extracted_files = extract_zip(zip_bytes)

    if not extracted_files:
        return {"success": False, "error": "No PDF files found in ZIP"}

    # Step 3: Make sure case exists in Supabase
    create_case(title_number)

    # Step 4: Process each PDF
    results = []
    for doc in extracted_files:
        try:
            # OCR the PDF
            ocr_result = process_pdf(doc["pdf_bytes"], doc["filename"])

            if not ocr_result["success"]:
                results.append({
                    "filename": doc["filename"],
                    "doc_type": doc["doc_type"],
                    "success": False,
                    "error": ocr_result.get("error")
                })
                continue

            # Chunk the text
            chunks = chunk_text(ocr_result["text"], doc["filename"])

            # Store in ChromaDB
            store_case_chunks(chunks, title_number)

            # Build URL
            cleaned = make_clean_filename(doc["filename"])
            file_url = f"{os.getenv('BACKEND_URL', 'https://convey-ai-production-be43.up.railway.app')}/view-pdf/{cleaned}"

            # Register in Supabase
            add_document(
                title_number=title_number,
                doc_type=doc["doc_type"],
                filename=doc["filename"],
                file_url=file_url
            )

            results.append({
                "filename": doc["filename"],
                "doc_type": doc["doc_type"],
                "success": True,
                "pages": ocr_result["pages"],
                "chunks": len(chunks)
            })

        except Exception as e:
            results.append({
                "filename": doc["filename"],
                "doc_type": doc["doc_type"],
                "success": False,
                "error": str(e)
            })

    # Count successes
    successful = [r for r in results if r["success"]]

    return {
        "success": True,
        "title_number": title_number,
        "total_files": len(extracted_files),
        "processed": len(successful),
        "results": results
    }

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), title_number: str = "UNKNOWN", doc_type: str = "OTHER", _user=Depends(require_auth)):
    """
    Full pipeline: PDF → OCR → chunk → embed → store in ChromaDB + Supabase
    """
    # Normalise title number to uppercase so it matches ChromaDB and Supabase consistently
    title_number = title_number.upper()

    # Step 1: Read uploaded file bytes
    pdf_bytes = await file.read()

    # Step 2: Run OCR to extract text from scanned PDF
    ocr_result = process_pdf(pdf_bytes, file.filename)
    if not ocr_result["success"]:
        return ocr_result

    # Step 3: Split extracted text into chunks
    chunks = chunk_text(ocr_result["text"], file.filename)

    # Step 4: Store chunks as vectors in ChromaDB
    store_case_chunks(chunks, title_number)

    # Step 5: Build the URL using the consistent clean filename function
    cleaned = make_clean_filename(file.filename)
    download_url = f"{os.getenv('BACKEND_URL', 'https://convey-ai-production-be43.up.railway.app')}/view-pdf/{cleaned}"

    # Step 6: Make sure case exists in Supabase
    create_case(title_number)

    # Step 7: Register this document in Supabase with its URL
    add_document(
        title_number=title_number,
        doc_type=doc_type,
        filename=file.filename,
        file_url=download_url
    )

    return {
        "success": True,
        "pages": ocr_result["pages"],
        "total_chunks": len(chunks),
        "title_number": title_number,
        "doc_type": doc_type,
        "download_url": download_url
    }

# Model for chat request body
class ChatRequest(BaseModel):
    question: str
    history: Optional[List[dict]] = []  # conversation history
    current_document: Optional[str] = None  # Add this new field!

class EnquiryRequest(BaseModel):
    issue: str
    history: Optional[List[dict]] = []  # conversation history
    current_document: Optional[str] = None  # Add this new field!

class TitleReportRequest(BaseModel):
    selected_filenames: List[str]

@app.post("/chat")
async def chat(title_number: str, request: ChatRequest, _user=Depends(require_auth)):
    """General Q&A prioritizing the current document"""
    # Normalise title number to uppercase so ChromaDB where-filter matches stored metadata
    result = ask_question(
        request.question,
        title_number.upper(),  # inline .upper() avoids Python UnboundLocalError
        request.history,
        request.current_document
    )
    return result

@app.get("/search-formats")
async def search_formats_route(query: str):
    """Test route — searches format library by topic or issue description"""
    # No title_number param on this route — removed the erroneous .upper() call
    results = search_formats(query, n_results=3)
    return {
        "query": query,
        "matches": [
            {
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "relevance_rank": i + 1
            }
            for i in range(len(results["documents"][0]))
        ]
    }

@app.post("/raise-enquiry")
async def raise_enquiry_route(title_number: str, request: EnquiryRequest, _user=Depends(require_auth)):
    """Raises enquiry with conversation memory, prioritizing current document"""
    # Normalise title number to uppercase so ChromaDB where-filter matches stored metadata
    result = raise_enquiry(
        request.issue,
        title_number.upper(),  # inline .upper() avoids Python UnboundLocalError
        request.history,
        request.current_document
    )
    return result

@app.post("/cases")
async def create_case_route(title_number: str, _user=Depends(require_auth)):
    """Creates a new case in Supabase"""
    # Normalise title number to uppercase for consistency across all storage layers
    result = create_case(title_number.upper())
    return result

@app.get("/cases")
async def get_all_cases_route(_user=Depends(require_auth)):
    """Returns all cases for the dashboard"""
    result = get_all_cases()
    return result

@app.get("/cases/{title_number}")
async def get_case_route(title_number: str, _user=Depends(require_auth)):
    """Returns a specific case and all its documents"""
    # Normalise title number to uppercase so Supabase query matches stored data
    result = get_case(title_number.upper())
    return result

# @app.delete("/cases/{title_number}/documents/{document_id}")
# async def delete_document_route(title_number: str, document_id: str):
#     """
#     Deletes a document completely:
#     1. Removes record from Supabase
#     2. Deletes OCR'd PDF from disk
#     3. Removes chunks from ChromaDB
#     """
#     # Step 1: Delete from Supabase and get the filename back
#     result = delete_document(document_id, title_number)
#     if not result["success"]:
#         return result

#     # Step 2: Delete the OCR'd PDF file from disk
#     cleaned = make_clean_filename(result["filename"])
#     file_path = f"processed_pdfs/{cleaned}"
#     if os.path.exists(file_path):
#         os.remove(file_path)
#         print(f"Deleted file: {file_path}")

#     # Step 3: Delete all ChromaDB chunks for this case document
#     try:
#         all_chunks = case_collection.get(where={"title_number": title_number})
#         if all_chunks["ids"]:
#             case_collection.delete(ids=all_chunks["ids"])
#             print(f"Deleted {len(all_chunks['ids'])} chunks from ChromaDB")
#     except Exception as e:
#         print(f"ChromaDB cleanup error: {e}")

#     return {"success": True, "message": "Document deleted completely"}

# @app.delete("/cases/{title_number}/documents/{document_id}")
# async def delete_document_route(title_number: str, document_id: str):
#     """
#     Deletes a document completely:
#     1. Removes record from Supabase (returns the original filename)
#     2. Deletes OCR'd PDF from disk using DATA_DIR
#     3. Removes ONLY this document's chunks from ChromaDB (filter by "source" key)
#     """
#     # Normalise title number to uppercase for consistent ChromaDB and Supabase lookups
#     tn = title_number.upper()

#     # Step 1: Delete from Supabase — returns the original filename so we know what to clean up
#     result = delete_document(document_id, tn)
#     if not result["success"]:
#         return result

#     original_filename = result["filename"]  # e.g. "Contract Pack.pdf"

#     # Step 2: Delete the OCR'd PDF from disk
#     # FIX: use DATA_DIR so this works on Railway volume, not just locally
#     cleaned = make_clean_filename(original_filename)
#     file_path = f"{DATA_DIR}/processed_pdfs/{cleaned}"
#     if os.path.exists(file_path):
#         os.remove(file_path)
#         print(f"Deleted file: {file_path}")
#     else:
#         print(f"File not found on disk (already deleted?): {file_path}")

#     # Step 3: Delete ONLY this document's chunks from ChromaDB
#     # FIX: filter by BOTH title_number AND "source" (the filename key set in chunker.py)
#     # Previously this only filtered by title_number — wiping ALL docs in the case!
#     try:
#         doc_chunks = case_collection.get(
#             where={"$and": [
#                 {"title_number": tn},
#                 {"source": original_filename}  # "source" is set in chunker.py metadata
#             ]}
#         )
#         if doc_chunks["ids"]:
#             case_collection.delete(ids=doc_chunks["ids"])
#             print(f"Deleted {len(doc_chunks['ids'])} chunks from ChromaDB for: {original_filename}")
#         else:
#             print(f"No ChromaDB chunks found for: {original_filename}")
#     except Exception as e:
#         print(f"ChromaDB cleanup error: {e}")

#     return {"success": True, "message": f"Document '{original_filename}' deleted completely"}
@app.delete("/cases/{title_number}/documents/{document_id}")
async def delete_document_route(title_number: str, document_id: str, _user=Depends(require_auth)):
    """
    Deletes a document completely from Supabase, Disk, and ChromaDB.
    """
    tn = title_number.upper()

    # Step 1: Delete from Supabase — returns the original filename
    result = delete_document(document_id, tn)
    if not result["success"]:
        return result

    original_filename = result["filename"]

    # Step 2: Delete the OCR'd PDF from disk
    cleaned = make_clean_filename(original_filename)
    file_path = f"{DATA_DIR}/processed_pdfs/{cleaned}"
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted file: {file_path}")

    # Step 3: Delete ONLY this document's chunks from ChromaDB
    try:
        # Pass the strict $eq syntax directly to the delete command
        case_collection.delete(
            where={
                "$and": [
                    {"title_number": {"$eq": tn}},
                    {"source": {"$eq": original_filename}} 
                ]
            }
        )
        print(f"Successfully deleted ChromaDB chunks for: {original_filename}")
    except Exception as e:
        print(f"ChromaDB cleanup error: {e}")

    return {"success": True, "message": f"Document '{original_filename}' deleted completely"}

@app.get("/debug-chunks/{title_number}")
async def debug_chunks(title_number: str):
    """
    Debug route — gated behind DEV_MODE env var.
    Set DEV_MODE=true locally in .env. Never set this on Railway.
    """
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Debug endpoints are disabled in production")
    results = case_collection.get(
        where={"title_number": title_number.upper()},
        limit=5
    )
    return {
        "ids": results["ids"],
        "metadatas": results["metadatas"]
    }

# @app.get("/debug-query/{title_number}")
# async def debug_query(title_number: str, question: str, current_document: str = None):
#     """
#     Temporary debug — shows exactly what chunks the chatbot would retrieve
#     for a given question and open document
#     """
#     from embeddings import model
    
#     query_embedding = model.encode([question]).tolist()
#     tn = title_number.upper()
    
#     # What it finds in the current doc
#     current_results = {"documents": [[]], "metadatas": [[]]}
#     if current_document:
#         current_results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=3,
#             where={"$and": [
#                 {"title_number": tn},
#                 {"source": current_document}
#             ]}
#         )
    
#     # What it finds in other docs
#     other_results = case_collection.query(
#         query_embeddings=query_embedding,
#         n_results=3,
#         where={"title_number": tn}
#     )
    
#     return {
#         "title_number_queried": tn,
#         "current_document_filter": current_document,
#         "current_doc_chunks": current_results["documents"][0],
#         "other_chunks": other_results["documents"][0]
#     }
@app.get("/debug-query/{title_number}")
async def debug_query(title_number: str, question: str, current_document: str = None):
    """
    Debug route — gated behind DEV_MODE env var.
    Set DEV_MODE=true locally in .env. Never set this on Railway.
    """
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Debug endpoints are disabled in production")
    from embeddings import model
    
    query_embedding = model.encode([question]).tolist()
    tn = title_number.upper()
    
    # What it finds in the current doc
    current_results = {"documents": [[]], "metadatas": [[]]}
    if current_document:
        current_document = current_document.strip()
        current_results = case_collection.query(
            query_embeddings=query_embedding,
            n_results=3,
            where={
                "$and": [
                    {"title_number": {"$eq": tn}},
                    {"source": {"$eq": current_document}}
                ]
            }
        )
    
    # FIX: Explicitly exclude the current document from the fallback query
    if current_document:
        other_where = {
            "$and": [
                {"title_number": {"$eq": tn}},
                {"source": {"$ne": current_document}} # Excludes the active doc
            ]
        }
    else:
        other_where = {"title_number": tn}
        
    other_results = case_collection.query(
        query_embeddings=query_embedding,
        n_results=3,
        where=other_where
    )
    
    # Safely extract documents and metadatas
    c_docs = current_results["documents"][0] if current_results.get("documents") else []
    c_meta = current_results["metadatas"][0] if current_results.get("metadatas") else []
    o_docs = other_results["documents"][0] if other_results.get("documents") else []
    o_meta = other_results["metadatas"][0] if other_results.get("metadatas") else []
    
    return {
        "title_number_queried": tn,
        "current_document_filter": current_document,
        "current_doc_chunks": c_docs,
        "current_doc_metadatas": c_meta, # Look here to verify your keys!
        "other_chunks": o_docs,
        "other_metadatas": o_meta
    }
@app.get("/debug-sources/{title_number}")
async def debug_sources(title_number: str):
    """Debug route — gated behind DEV_MODE env var. Set DEV_MODE=true locally."""
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Debug endpoints are disabled in production")
    results = case_collection.get(
        where={"title_number": title_number.upper()}
    )
    sources = list(set(m["source"] for m in results["metadatas"]))
    return {"title_number": title_number.upper(), "sources": sources}


@app.get("/find-page")
async def find_page(title_number: str, filename: str, query: str):
    """
    Finds the estimated PDF page number for a given search phrase within a document.

    Used by the InPage Ref pills in the chatbot — Chrome's native PDF viewer
    supports #page=N but NOT #search=text, so we convert the phrase to a page.

    Strategy:
      1. Fetch all chunks for this document from ChromaDB, sorted by chunk_index
      2. Try exact substring match first (fast, works when OCR is clean)
      3. Fall back to difflib fuzzy ratio if no exact match found
      4. Estimate page = floor(best_chunk_index / CHUNKS_PER_PAGE) + 1
         Legal A4 docs: ~600 chars/chunk, ~3000 chars/page → ~5 chunks/page
    """
    from difflib import SequenceMatcher

    # Number of 600-char chunks that typically fit on one A4 legal page
    # Adjust if your docs are unusually dense or sparse
    CHUNKS_PER_PAGE = 5

    tn = title_number.upper()

    # Fetch every chunk for this specific document
    results = case_collection.get(
        where={
            "$and": [
                {"title_number": {"$eq": tn}},
                {"source":       {"$eq": filename}}
            ]
        },
        include=["documents", "metadatas"]
    )

    # If nothing found, default to page 1 gracefully
    if not results["ids"]:
        return {"page": 1, "found": False, "reason": "no chunks found for document"}

    # Sort chunks into document reading order
    chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
    chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))

    query_lower = query.lower()
    best_score  = 0.0
    best_index  = 0   # positional index in the sorted list (not stored chunk_index)

    for i, (chunk_text, _) in enumerate(chunks_with_meta):
        chunk_lower = chunk_text.lower()

        # Exact substring match — if found, stop immediately
        if query_lower in chunk_lower:
            best_index = i
            best_score = 1.0
            break

        # Fuzzy ratio against the whole chunk text
        score = SequenceMatcher(None, query_lower, chunk_lower).ratio()
        if score > best_score:
            best_score = score
            best_index = i

    # Convert chunk position to an estimated 1-based page number
    estimated_page = (best_index // CHUNKS_PER_PAGE) + 1

    return {
        "page":        estimated_page,
        "chunk_index": best_index,
        "match_score": round(best_score, 3),
        "found":       best_score > 0.05   # very low threshold — almost always true
    }


# The previous version had no try/except — if title_report.py threw any error
# (e.g. Groq 413), FastAPI returned an HTML 500 page instead of JSON.
# Frontend's res.json() then threw, landing in the catch block as "Something went wrong."
# This version catches all errors and always returns valid JSON so the frontend
# can display a proper error message instead.
 
@app.post("/generate-title-report")
async def generate_title_report_route(title_number: str, request: TitleReportRequest, _user=Depends(require_auth)):
    """
    Generates a structured Title Report for the selected documents.
    Always returns JSON — even on failure — so the frontend can show a real error.
    """
    try:
        result = generate_title_report(
            title_number.upper(),  # inline .upper() — never reassign FastAPI path params
            request.selected_filenames
        )
        return result
 
    except Exception as e:
        # Log the full error server-side for Railway logs
        print(f"[TitleReport Error] {title_number}: {str(e)}")
 
        # Return structured JSON error so frontend's !res.ok branch catches it
        # and displays data.detail rather than throwing and hitting the catch block
        return JSONResponse(
            status_code=500,
            content={"detail": f"Report generation failed: {str(e)}"}
        )


@app.post("/ingest-letters")
async def ingest_letters_route():
    """One-time route to ingest letter templates into ChromaDB"""
    from ingest_letters import ingest_all_letters
    ingest_all_letters()
    return {"success": True, "message": "Letter templates ingested"}


# ── Title Check endpoint ──────────────────────────────────────────────────────
# Runs the AI-assisted Title Check pipeline on a single uploaded TA6/TA10/TA13.
# Steps performed (see title_check.py for detail):
#   1. Reconstructs full document text from ChromaDB chunks
#   2. Classifies form type (TA6 / TA10 / TA13)
#   3. Gemini extracts checkbox states and seller notes as structured JSON
#   4. Hardcoded Rules Engine maps states → enquiry codes (no LLM here)
#   5. Fetches enquiry templates from format_library ChromaDB collection
#   6. Gemini personalises drafts where templates have placeholders
# Returns findings list for the human Review Board in the frontend.
class TitleCheckRequest(BaseModel):
    title_number: str   # e.g. "EX332661"
    filename:     str   # exact filename as stored in ChromaDB

@app.post("/title-check")
async def title_check_route(req: TitleCheckRequest, _user=Depends(require_auth)):
    """
    Runs the Title Check pipeline on a single TA6/TA10/TA13 document.
    Returns a findings list that the frontend displays as the Review Board.
    Each finding includes: enquiry_code, topic, reason, draft, status='pending'
    """
    try:
        result = run_title_check(
            filename=req.filename,
            title_number=req.title_number
        )
        # run_title_check returns {"error": "..."} if something went wrong upstream
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        print(f"[/title-check] Unhandled error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Title check failed: {str(e)}"}
        )


# ── Re-ingest formats endpoint ────────────────────────────────────────────────
# Use this to rebuild the format_library ChromaDB collection on Railway
# after adding new enquiry formats to ingest_formats.py.
# Hit: POST /reingest-formats  (no body needed)
@app.post("/reingest-formats")
async def reingest_formats_route():
    """
    Wipes and rebuilds the format_library ChromaDB collection from ingest_formats.py.
    Call this after deploying new enquiry formats to Railway so templates are available
    for the Title Check and chatbot raise-enquiry features.
    """
    try:
        from ingest_formats import ingest_all_enquiries
        ingest_all_enquiries()
        from embeddings import format_collection
        count = format_collection.count()
        return {"success": True, "message": f"Format library rebuilt. {count} enquiries now stored."}
    except Exception as e:
        print(f"[/reingest-formats] Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Re-ingestion failed: {str(e)}"}
        )