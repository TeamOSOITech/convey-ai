# routes/formats.py — Enquiry format lookup endpoint
# Serves enquiry templates from the format_library table by code (e.g. A1, F3a).
# Used by the Title Check review board "Add Enquiry" feature.

from fastapi import APIRouter, HTTPException, Depends
from embeddings import get_format_by_code
from auth_utils import require_auth

router = APIRouter()


@router.get("/formats/{code}")
async def get_format(code: str, _=Depends(require_auth)):
    """Fetch an enquiry format by its code (e.g. A1, E7) for manual addition."""
    row = get_format_by_code(code)
    if not row:
        raise HTTPException(status_code=404, detail=f"Enquiry code '{code}' not found")

    return {
        "code":  row["code"],
        "topic": row["topic"],
        "draft": row["content"]
    }