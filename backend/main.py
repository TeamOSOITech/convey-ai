# main.py — main backend server file

from fastapi import FastAPI, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from ocr import process_pdf
from chunker import chunk_page
from embeddings import (
    store_case_chunks, search_formats, get_document_chunks,
    delete_case_chunks, query_case_chunks
)
from chatbot import ask_question, raise_enquiry
from database import create_case, add_document, get_case, get_all_cases, delete_document, supabase
import storage
import os
from pydantic import BaseModel
from typing import List, Optional
from zip_processor import extract_zip
from chatbot import ask_question, raise_enquiry
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from title_report import generate_title_report
from title_check import run_title_check
from auth_utils import require_auth

app = FastAPI()

# Update CORS middleware to be more permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://convey-ai-mauve.vercel.app",
        "https://*.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# require_auth is defined in auth_utils.py and imported at the top of this file.
# It validates the Supabase JWT on every protected route via Depends(require_auth).

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
    """One-time route to populate the format_library table — delete after use"""
    # No title_number here — removed the erroneous .upper() call
    from ingest_formats import ingest_all_enquiries
    ingest_all_enquiries()
    return {"success": True, "message": "Format library ingested"}

# /view-pdf/{filename} used to proxy local-disk PDFs for inline viewing.
# Documents now live in Supabase Storage — case_documents.file_url holds a
# signed URL (minted in database.get_case()) that the frontend loads directly,
# so this proxy route is no longer needed.

@app.get("/")
def home():
    return {"message": "Convey AI backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    title_number: str = "UNKNOWN",
    _user=Depends(require_auth)
):
    """
    Receives a contract pack ZIP,
    OCRs every PDF,
    chunks every page,
    embeds and stores every chunk in the vector store.
    """

    title_number = title_number.upper()

    # Step 1: Read ZIP
    zip_bytes = await file.read()

    # Step 2: Extract PDFs
    extracted_files = extract_zip(zip_bytes)

    if not extracted_files:
        return {
            "success": False,
            "error": "No PDF files found in ZIP"
        }

    # Step 3: Ensure case exists
    create_case(title_number)

    results = []

    for doc in extracted_files:

        try:

            # OCR
            ocr_result = process_pdf(
                doc["pdf_bytes"],
                doc["filename"]
            )

            if not ocr_result["success"]:
                results.append({
                    "filename": doc["filename"],
                    "doc_type": doc["doc_type"],
                    "success": False,
                    "error": ocr_result["error"]
                })
                continue

            # Chunk every page
            all_chunks = []

            for page in ocr_result["pages"]:

                page_chunks = chunk_page(
                    blocks=page["blocks"],
                    source_filename=doc["filename"],
                    title_number=title_number,
                    page=page["page"]
                )

                all_chunks.extend(page_chunks)

            # Store vectors
            store_case_chunks(all_chunks, title_number)

            # Upload processed PDF to Supabase Storage, register the storage
            # path (not a URL — signed URLs are minted on read, see database.get_case)
            cleaned = make_clean_filename(doc["filename"])
            storage_path = storage.upload_document(title_number, cleaned, doc["pdf_bytes"])

            add_document(
                title_number=title_number,
                doc_type=doc["doc_type"],
                filename=doc["filename"],
                file_url=storage_path
            )

            results.append({
                "filename": doc["filename"],
                "doc_type": doc["doc_type"],
                "success": True,
                "pages": len(ocr_result["pages"]),
                "chunks": len(all_chunks)
            })

        except Exception as e:

            results.append({
                "filename": doc["filename"],
                "doc_type": doc["doc_type"],
                "success": False,
                "error": str(e)
            })

    successful = [r for r in results if r["success"]]

    return {
        "success": True,
        "title_number": title_number,
        "total_files": len(extracted_files),
        "processed": len(successful),
        "results": results
    }


# main.py - Update the upload endpoints

@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    title_number: str = "UNKNOWN",
    doc_type: str = "OTHER",
    _user=Depends(require_auth)
):
    """Full pipeline: PDF → OCR → Chunk → Embed → Store"""
    title_number = title_number.upper()
    pdf_bytes = await file.read()
    
    # Step 2: OCR
    ocr_result = process_pdf(pdf_bytes, file.filename)
    if not ocr_result["success"]:
        return ocr_result
    
    # Step 3: Chunk every page with page dimensions
    all_chunks = []
    for page_data in ocr_result["pages"]:
        page_chunks = chunk_page(
            blocks=page_data["blocks"],
            source_filename=file.filename,
            title_number=title_number,
            page=page_data["page"],
            page_width=page_data.get("width", 1.0),
            page_height=page_data.get("height", 1.0)
        )
        all_chunks.extend(page_chunks)

    # Step 4: Store vectors
    store_case_chunks(all_chunks, title_number)

    # Step 5: Upload processed PDF to Supabase Storage
    cleaned = make_clean_filename(file.filename)
    storage_path = storage.upload_document(title_number, cleaned, pdf_bytes)
    download_url = storage.get_signed_url(storage_path)

    # Step 6: Ensure case exists
    create_case(title_number)

    # Step 7: Register document — stores the storage path, not the signed URL,
    # since signed URLs expire. Fresh ones are minted on read (database.get_case).
    add_document(
        title_number=title_number,
        doc_type=doc_type,
        filename=file.filename,
        file_url=storage_path
    )

    return {
        "success": True,
        "pages": len(ocr_result["pages"]),
        "total_chunks": len(all_chunks),
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
    # Normalise title number to uppercase so the vector-store filter matches stored metadata
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
                "text": row["content"],
                "metadata": {
                    "code": row["code"],
                    "section": row["section"],
                    "topic": row["topic"],
                    "trigger": row["trigger_text"]
                },
                "relevance_rank": i + 1
            }
            for i, row in enumerate(results)
        ]
    }

@app.post("/raise-enquiry")
async def raise_enquiry_route(title_number: str, request: EnquiryRequest, _user=Depends(require_auth)):
    """Raises enquiry with conversation memory, prioritizing current document"""
    # Normalise title number to uppercase so the vector-store filter matches stored metadata
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

@app.delete("/cases/{title_number}/documents/{document_id}")
async def delete_document_route(title_number: str, document_id: str, _user=Depends(require_auth)):
    """
    Deletes a document completely from Supabase (row, Storage object, and vector chunks).
    """
    tn = title_number.upper()

    # Step 1: Delete from Supabase — returns the original filename
    result = delete_document(document_id, tn)
    if not result["success"]:
        return result

    original_filename = result["filename"]

    # Step 2: Delete the processed PDF from Supabase Storage
    cleaned = make_clean_filename(original_filename)
    storage.delete_document(f"{tn}/{cleaned}")

    # Step 3: Delete ONLY this document's chunks from the vector store
    try:
        delete_case_chunks(tn, original_filename)
        print(f"Successfully deleted vector chunks for: {original_filename}")
    except Exception as e:
        print(f"Vector store cleanup error: {e}")

    return {"success": True, "message": f"Document '{original_filename}' deleted completely"}

@app.get("/debug-chunks/{title_number}")
async def debug_chunks(title_number: str):
    """
    Debug route — gated behind DEV_MODE env var.
    Set DEV_MODE=true locally in .env. Never set this on Railway.
    """
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Debug endpoints are disabled in production")
    result = supabase.table("document_chunks")\
        .select("id, title_number, source, page, chunk_index")\
        .eq("title_number", title_number.upper())\
        .limit(5)\
        .execute()
    return {
        "ids": [row["id"] for row in result.data],
        "metadatas": result.data
    }

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
    current_chunks = []
    if current_document:
        current_document = current_document.strip()
        current_chunks = query_case_chunks(query_embedding, tn, source=current_document, n_results=3)

    # What it finds in other docs — explicitly excludes the active doc
    other_chunks = query_case_chunks(
        query_embedding, tn,
        exclude_source=current_document.strip() if current_document else None,
        n_results=3
    )

    return {
        "title_number_queried": tn,
        "current_document_filter": current_document,
        "current_doc_chunks": [c["text"] for c in current_chunks],
        "current_doc_metadatas": [c["metadata"] for c in current_chunks],
        "other_chunks": [c["text"] for c in other_chunks],
        "other_metadatas": [c["metadata"] for c in other_chunks]
    }

@app.get("/debug-sources/{title_number}")
async def debug_sources(title_number: str):
    """Debug route — gated behind DEV_MODE env var. Set DEV_MODE=true locally."""
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Debug endpoints are disabled in production")
    result = supabase.table("document_chunks")\
        .select("source")\
        .eq("title_number", title_number.upper())\
        .execute()
    sources = list(set(row["source"] for row in result.data))
    return {"title_number": title_number.upper(), "sources": sources}


# /formats/{code}, /smart-extract, /form-extract live in routes/
# and are registered via include_router below.


@app.get("/find-page")
async def find_page(title_number: str, filename: str, query: str):
    """
    Finds the estimated PDF page number for a given search phrase within a document.

    Used by the InPage Ref pills in the chatbot — Chrome's native PDF viewer
    supports #page=N but NOT #search=text, so we convert the phrase to a page.

    Strategy:
      1. Fetch all chunks for this document, already sorted by chunk_index
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

    # Fetch every chunk for this specific document, already in reading order
    chunks_with_meta = [
        (c["text"], c["metadata"]) for c in get_document_chunks(tn, filename)
    ]

    # If nothing found, default to page 1 gracefully
    if not chunks_with_meta:
        return {"page": 1, "found": False, "reason": "no chunks found for document"}

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
    """One-time route to ingest letter templates into the vector store"""
    from ingest_letters import ingest_all_letters
    ingest_all_letters()
    return {"success": True, "message": "Letter templates ingested"}


# ── Title Check endpoint ──────────────────────────────────────────────────────
# Runs the AI-assisted Title Check pipeline on a single uploaded TA6/TA10/TA13.
# Steps performed (see title_check.py for detail):
#   1. Reconstructs full document text from the vector store's chunks
#   2. Classifies form type (TA6 / TA10 / TA13)
#   3. Gemini extracts checkbox states and seller notes as structured JSON
#   4. Hardcoded Rules Engine maps states → enquiry codes (no LLM here)
#   5. Fetches enquiry templates from the format_library table
#   6. Gemini personalises drafts where templates have placeholders
# Returns findings list for the human Review Board in the frontend.
class TitleCheckRequest(BaseModel):
    title_number: str   # e.g. "EX332661"
    filename:     str   # exact filename as stored in the vector store

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
# Use this to rebuild the format_library table on Railway
# after adding new enquiry formats to ingest_formats.py.
# Hit: POST /reingest-formats  (no body needed)
@app.post("/reingest-formats")
async def reingest_formats_route():
    """
    Wipes and rebuilds the format_library table from ingest_formats.py.
    Call this after deploying new enquiry formats to Railway so templates are available
    for the Title Check and chatbot raise-enquiry features.
    """
    try:
        from ingest_formats import ingest_all_enquiries
        count = ingest_all_enquiries()
        return {"success": True, "message": f"Format library rebuilt. {count} enquiries now stored."}
    except Exception as e:
        print(f"[/reingest-formats] Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Re-ingestion failed: {str(e)}"}
        )

# ── Route modules ──────────────────────────────────────────────────────────────
# Each tool's endpoint logic lives in its own file under routes/.
# Add new tools here by creating routes/<name>.py and registering below.
from routes.formats      import router as formats_router
from routes.smart_extract import router as smart_extract_router
from routes.form_filler   import router as form_filler_router

app.include_router(formats_router)
app.include_router(smart_extract_router)
app.include_router(form_filler_router)
