# embeddings.py — converts text chunks to vectors and stores/searches them
# in Supabase Postgres via pgvector (see backend/sql/pgvector_schema.sql).
#
# Embedding *computation* still happens in-process (SentenceTransformer runs
# locally); only the *index/storage* lives in Postgres now — ChromaDB and its
# Railway-volume-backed persistence have been removed entirely.

from sentence_transformers import SentenceTransformer
from database import supabase
import uuid

# This runs locally — text never leaves the machine for embedding purposes.
# First run downloads the model (~90MB) into ./models and caches it there.
model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    cache_folder="./models"
)


# ── Case document chunks (table: document_chunks) ────────────────────────────

def store_case_chunks(chunks: list, title_number: str):
    """
    Converts document chunks to embeddings and stores them in Postgres.

    Each chunk already contains:
        - source
        - title_number
        - page
        - bbox
        - chunk_index
        - total_chunks
    """
    texts = [chunk["text"] for chunk in chunks]
    vectors = model.encode(texts).tolist()

    rows = []
    for chunk, vector in zip(chunks, vectors):
        metadata = chunk["metadata"]

        safe_source = (
            metadata["source"]
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

        row_id = (
            f"{title_number}_{safe_source}_p{metadata['page']}_"
            f"c{metadata['chunk_index']}_{uuid.uuid4().hex[:8]}"
        )

        rows.append({
            "id": row_id,
            "title_number": title_number,
            "source": metadata["source"],
            "page": metadata.get("page"),
            "chunk_index": metadata.get("chunk_index"),
            "total_chunks": metadata.get("total_chunks"),
            "bbox": metadata.get("bbox"),
            "content": chunk["text"],
            "embedding": vector,
        })

    supabase.table("document_chunks").insert(rows).execute()

    return {
        "stored": len(rows),
        "title_number": title_number,
        "collection": "document_chunks"
    }


def _row_to_chunk(row: dict) -> dict:
    """Shapes a document_chunks row into the {text, metadata} form callers expect."""
    return {
        "text": row["content"],
        "metadata": {
            "source": row["source"],
            "title_number": row["title_number"],
            "page": row["page"],
            "bbox": row["bbox"],
            "chunk_index": row["chunk_index"],
            "total_chunks": row["total_chunks"],
        }
    }


def query_case_chunks(
    query_embedding: list,
    title_number: str,
    source: str = None,
    exclude_source: str = None,
    n_results: int = 10
) -> list:
    """
    Vector similarity search over a case's chunks via the match_document_chunks
    RPC. Optionally scoped to one document (source) or excluding one
    (exclude_source) — used for the chatbot's current-doc-first retrieval.
    """
    result = supabase.rpc("match_document_chunks", {
        "query_embedding": query_embedding,
        "match_title_number": title_number.upper(),
        "match_source": source,
        "exclude_source": exclude_source,
        "match_count": n_results,
    }).execute()

    return [_row_to_chunk(row) for row in result.data]


def get_document_chunks(title_number: str, source: str) -> list:
    """
    Fetches every chunk for one document, already in reading order.
    Replaces the old "get() everything then sort by chunk_index" pattern.
    """
    result = supabase.table("document_chunks")\
        .select("*")\
        .eq("title_number", title_number.upper())\
        .eq("source", source)\
        .order("chunk_index")\
        .execute()

    return [_row_to_chunk(row) for row in result.data]


def delete_case_chunks(title_number: str, source: str):
    """Deletes every chunk belonging to one document."""
    supabase.table("document_chunks")\
        .delete()\
        .eq("title_number", title_number.upper())\
        .eq("source", source)\
        .execute()


# ── Format library (table: format_library) ───────────────────────────────────

def store_format_entries(entries: list):
    """
    Wipes and rebuilds the format_library table from a list of
    {code, section, topic, trigger, text} dicts — see ingest_formats.py.
    """
    texts_to_embed = [
        f"Code: {e['code']}. Section: {e['section']}. Topic: {e['topic']}. "
        f"When to use: {e['trigger']}. Enquiry text: {e['text']}"
        for e in entries
    ]
    vectors = model.encode(texts_to_embed).tolist()

    rows = [
        {
            "id": f"enquiry_{e['code']}",
            "code": e["code"],
            "section": e["section"],
            "topic": e["topic"],
            "trigger_text": e["trigger"],
            "content": e["text"],
            "embedding": vector,
        }
        for e, vector in zip(entries, vectors)
    ]

    # True wipe-and-rebuild — /reingest-formats has always claimed this happens.
    supabase.table("format_library").delete().neq("id", "").execute()
    supabase.table("format_library").insert(rows).execute()

    return len(rows)


def search_formats(query: str, n_results: int = 3) -> list:
    """Semantic search over the format library — returns raw rows with a similarity score."""
    query_embedding = model.encode([query]).tolist()[0]
    result = supabase.rpc("match_format_library", {
        "query_embedding": query_embedding,
        "match_count": n_results,
    }).execute()
    return result.data


def get_enquiry_template(code: str) -> dict:
    """Deterministic lookup by enquiry code — no vector search."""
    result = supabase.table("format_library").select("*").eq("id", f"enquiry_{code}").execute()
    if not result.data:
        return None
    return result.data[0]


def get_format_by_code(code: str) -> dict:
    """Case-insensitive lookup by code, tries uppercase first then exact match."""
    result = supabase.table("format_library").select("*").eq("code", code.upper()).execute()
    if not result.data:
        result = supabase.table("format_library").select("*").eq("code", code).execute()
    if not result.data:
        return None
    return result.data[0]
