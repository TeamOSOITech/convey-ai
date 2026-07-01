# routes/formats.py — Enquiry format lookup endpoint
# Serves enquiry templates from ChromaDB by code (e.g. A1, F3a).
# Used by the Title Check review board "Add Enquiry" feature.

from fastapi import APIRouter, HTTPException, Depends
from embeddings import format_collection
from auth_utils import require_auth

router = APIRouter()


@router.get("/formats/{code}")
async def get_format(code: str, _=Depends(require_auth)):
    """Fetch an enquiry format by its code (e.g. A1, E7) for manual addition."""
    results = format_collection.get(where={"code": code.upper()})
    if not results["ids"]:
        results = format_collection.get(where={"code": code})
        if not results["ids"]:
            raise HTTPException(status_code=404, detail=f"Enquiry code '{code}' not found")

    return {
        "code":  results["metadatas"][0]["code"],
        "topic": results["metadatas"][0]["topic"],
        "draft": results["documents"][0]
    }