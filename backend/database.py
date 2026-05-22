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
    Gets a case and all its documents by title number
    """
    # Get case
    case = supabase.table("cases")\
        .select("*")\
        .eq("title_number", title_number)\
        .execute()

    if not case.data:
        return {"success": False, "error": "Case not found"}

    # Get all documents for this case
    documents = supabase.table("case_documents")\
        .select("*")\
        .eq("title_number", title_number)\
        .execute()

    return {
        "success": True,
        "case": case.data[0],
        "documents": documents.data
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