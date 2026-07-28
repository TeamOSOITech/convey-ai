# storage.py — Supabase Storage wrapper for processed case documents
#
# Replaces local-disk persistence (backend/data/processed_pdfs/) with a
# private Supabase Storage bucket, namespaced per case. Callers never see
# a raw URL for a document — only a storage path — and must go through
# get_signed_url() to get something fetchable. This is the seam to swap
# for S3 later: every call site outside this file only knows about
# upload_document / get_signed_url / fetch_document_bytes / delete_document.

import os
from database import supabase

BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "case-documents")
SIGNED_URL_TTL = 3600  # seconds


def _ensure_bucket():
    """Idempotent bucket bootstrap — mirrors the os.makedirs(exist_ok=True)
    pattern main.py already uses for local folders."""
    try:
        supabase.storage.create_bucket(BUCKET_NAME, options={"public": False})
    except Exception:
        pass  # already exists


_ensure_bucket()


def upload_document(title_number: str, cleaned_filename: str, pdf_bytes: bytes) -> str:
    """Uploads bytes to {title_number}/{cleaned_filename}. Returns the storage path."""
    path = f"{title_number}/{cleaned_filename}"
    supabase.storage.from_(BUCKET_NAME).upload(
        path,
        pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def get_signed_url(storage_path: str, expires_in: int = SIGNED_URL_TTL) -> str | None:
    """Mints a time-limited URL for a stored document. Returns None on failure
    (missing object, bad legacy path) so callers can degrade gracefully."""
    try:
        result = supabase.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expires_in)
        return result.get("signedURL") or result.get("signedUrl")
    except Exception as e:
        print(f"[Storage] Failed to sign URL for {storage_path}: {e}")
        return None


def fetch_document_bytes(storage_path: str) -> bytes | None:
    """Downloads a document's raw bytes for server-side processing
    (e.g. rendering PDF pages to images for the Title Check vision pipeline)."""
    try:
        return supabase.storage.from_(BUCKET_NAME).download(storage_path)
    except Exception:
        return None


def delete_document(storage_path: str) -> None:
    try:
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])
    except Exception as e:
        print(f"[Storage] Failed to delete {storage_path}: {e}")
