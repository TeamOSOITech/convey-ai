# database.py — handles all Supabase database operations

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


def create_case(title_number: str) -> dict:
    # Check if case already exists
    existing = supabase.table("cases")\
        .select("*")\
        .eq("title_number", title_number)\
        .execute()

    if existing.data:
        return {"success": True, "case": existing.data[0], "created": False}

    result = supabase.table("cases").insert({
        "title_number": title_number,
        "status": "active"
    }).execute()

    return {"success": True, "case": result.data[0], "created": True}


def get_case_id(title_number: str) -> str:
    """
    Looks up a case's UUID by title_number. Used by callers that only have
    title_number in scope (routes, chatbot, etc.) but need case_id to filter
    document_chunks — case_id is the real relational key, title_number is
    just the public-facing lookup. Returns None if the case doesn't exist.
    """
    result = supabase.table("cases").select("id").eq("title_number", title_number).execute()
    return result.data[0]["id"] if result.data else None


def add_document(title_number: str, doc_type: str, filename: str, file_url: str = None) -> dict:
    """
    Adds a document record to a case
    doc_type is TA6, TA7, OCE, TR1, EPC etc.
    """
    # First get the case id
    case = supabase.table("cases")\
        .select("id")\
        .eq("title_number", title_number)\
        .execute()

    if not case.data:
        return {"success": False, "error": "Case not found"}

    case_id = case.data[0]["id"]

    # Insert document record
    result = supabase.table("case_documents").insert({
        "case_id": case_id,
        "title_number": title_number,
        "doc_type": doc_type,
        "filename": filename,
        "file_url": file_url,
        "processed": True
    }).execute()

    return {"success": True, "document": result.data[0]}


def get_case(title_number: str) -> dict:
    """
    Gets a case and all its documents by title number.
    case_documents.file_url holds a Supabase Storage *path*, not a URL —
    each document's file_url is swapped here for a freshly-minted signed URL.
    """
    # Local import to avoid a circular import — storage.py imports `supabase` from this module.
    from storage import get_signed_url

    # Get case
    case = supabase.table("cases")\
        .select("*")\
        .eq("title_number", title_number)\
        .execute()

    if not case.data:
        return {"success": False, "error": "Case not found"}

    # Get all documents for this case — joined by case_id (the real FK),
    # not title_number
    documents = supabase.table("case_documents")\
        .select("*")\
        .eq("case_id", case.data[0]["id"])\
        .execute()

    docs = documents.data
    for doc in docs:
        if doc.get("file_url"):
            doc["file_url"] = get_signed_url(doc["file_url"])

    return {
        "success": True,
        "case": case.data[0],
        "documents": docs
    }


def get_all_cases() -> dict:
    """
    Gets all cases — for the case dashboard
    """
    result = supabase.table("cases")\
        .select("*")\
        .order("created_at", desc=True)\
        .execute()

    return {"success": True, "cases": result.data}

def delete_document(document_id: str, title_number: str) -> dict:
    """
    Deletes a document record from Supabase
    Returns the deleted document's filename so we can clean up files too
    """
    # First get the document details before deleting
    doc = supabase.table("case_documents")\
        .select("*")\
        .eq("id", document_id)\
        .execute()

    if not doc.data:
        return {"success": False, "error": "Document not found"}

    filename = doc.data[0]["filename"]

    # Delete from Supabase
    supabase.table("case_documents")\
        .delete()\
        .eq("id", document_id)\
        .execute()

    return {"success": True, "filename": filename}