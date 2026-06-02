# main.py — main backend server file

from fastapi import FastAPI, UploadFile, File
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
    allow_origin_regex=r"https://.*\.vercel\.app",  # regex — matches ALL *.vercel.app URLs
    allow_origins=[
        "http://localhost:3000",           # local development
        "https://convey-ai-mauve.vercel.app",    # production Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # Use DATA_DIR so it works both locally and on Railway volume
    # No title_number here — removed the erroneous .upper() call
    file_path = f"{DATA_DIR}/processed_pdfs/{filename}"
    if not os.path.exists(file_path):
        return {"error": "File not found", "looked_for": file_path}
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=" + filename,
            "Content-Type": "application/pdf",
            "X-Frame-Options": "ALLOWALL",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/")
def home():
    return {"message": "Convey AI backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-zip")
async def upload_zip(file: UploadFile = File(...), title_number: str = "UNKNOWN"):
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
async def upload_pdf(file: UploadFile = File(...), title_number: str = "UNKNOWN", doc_type: str = "OTHER"):
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

@app.post("/chat")
async def chat(title_number: str, request: ChatRequest):
    """General Q&A prioritizing the current document"""
    # Normalise title number to uppercase so ChromaDB where-filter matches stored metadata
    result = ask_question(
        request.question,
        title_number.upper(),  # inline .upper() avoids Python UnboundLocalError
        request.history,
        #request.current_document
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
async def raise_enquiry_route(title_number: str, request: EnquiryRequest):
    """Raises enquiry with conversation memory, prioritizing current document"""
    # Normalise title number to uppercase so ChromaDB where-filter matches stored metadata
    result = raise_enquiry(
        request.issue,
        title_number.upper(),  # inline .upper() avoids Python UnboundLocalError
        request.history,
        #request.current_document
    )
    return result

@app.post("/cases")
async def create_case_route(title_number: str):
    """Creates a new case in Supabase"""
    # Normalise title number to uppercase for consistency across all storage layers
    result = create_case(title_number.upper())
    return result

@app.get("/cases")
async def get_all_cases_route():
    """Returns all cases for the dashboard"""
    result = get_all_cases()
    return result

@app.get("/cases/{title_number}")
async def get_case_route(title_number: str):
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

@app.delete("/cases/{title_number}/documents/{document_id}")
async def delete_document_route(title_number: str, document_id: str):
    """
    Deletes a document completely:
    1. Removes record from Supabase (returns the original filename)
    2. Deletes OCR'd PDF from disk using DATA_DIR
    3. Removes ONLY this document's chunks from ChromaDB (filter by "source" key)
    """
    # Normalise title number to uppercase for consistent ChromaDB and Supabase lookups
    tn = title_number.upper()

    # Step 1: Delete from Supabase — returns the original filename so we know what to clean up
    result = delete_document(document_id, tn)
    if not result["success"]:
        return result

    original_filename = result["filename"]  # e.g. "Contract Pack.pdf"

    # Step 2: Delete the OCR'd PDF from disk
    # FIX: use DATA_DIR so this works on Railway volume, not just locally
    cleaned = make_clean_filename(original_filename)
    file_path = f"{DATA_DIR}/processed_pdfs/{cleaned}"
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted file: {file_path}")
    else:
        print(f"File not found on disk (already deleted?): {file_path}")

    # Step 3: Delete ONLY this document's chunks from ChromaDB
    # FIX: filter by BOTH title_number AND "source" (the filename key set in chunker.py)
    # Previously this only filtered by title_number — wiping ALL docs in the case!
    try:
        doc_chunks = case_collection.get(
            where={"$and": [
                {"title_number": tn},
                {"source": original_filename}  # "source" is set in chunker.py metadata
            ]}
        )
        if doc_chunks["ids"]:
            case_collection.delete(ids=doc_chunks["ids"])
            print(f"Deleted {len(doc_chunks['ids'])} chunks from ChromaDB for: {original_filename}")
        else:
            print(f"No ChromaDB chunks found for: {original_filename}")
    except Exception as e:
        print(f"ChromaDB cleanup error: {e}")

    return {"success": True, "message": f"Document '{original_filename}' deleted completely"}

@app.get("/debug-chunks/{title_number}")
async def debug_chunks(title_number: str):
    """
    Temporary debug route — shows what metadata keys/values are
    stored in ChromaDB for a given case. Delete after debugging.
    """
    # Fetch up to 5 chunks for this case to inspect their metadata
    results = case_collection.get(
        where={"title_number": title_number.upper()},
        limit=5
    )
    return {
        "ids": results["ids"],
        "metadatas": results["metadatas"]  # this shows all stored keys + values
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
    Temporary debug — shows exactly what chunks the chatbot would retrieve
    for a given question and open document
    """
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
    """Shows all unique document source names stored in ChromaDB for this case"""
    results = case_collection.get(
        where={"title_number": title_number.upper()}
    )
    # Extract unique source values from all metadata
    sources = list(set(m["source"] for m in results["metadatas"]))
    return {"title_number": title_number.upper(), "sources": sources}