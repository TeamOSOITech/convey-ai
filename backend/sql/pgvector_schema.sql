-- pgvector_schema.sql — one-time setup for Convey AI's vector store
--
-- Run this once in the Supabase SQL Editor (Project → SQL Editor → New query).
-- Replaces the ChromaDB collections that used to live on the Railway volume:
--   case_collection   -> document_chunks
--   format_collection -> format_library
-- (checklist_collection is dropped — it was created but never written to or
-- queried anywhere in the codebase.)
--
-- Embeddings are 384-dimensional because the backend uses the
-- all-MiniLM-L6-v2 SentenceTransformer model (see backend/embeddings.py).
-- If that model ever changes, the vector(384) columns below must change too.

create extension if not exists vector;

-- ── document_chunks — chunked, embedded text from every uploaded case document ──

create table if not exists document_chunks (
    id            text primary key,
    title_number  text not null,
    source        text not null,      -- original filename
    page          integer,
    chunk_index   integer,
    total_chunks  integer,
    bbox          jsonb,              -- [x0, y0, x1, y1] normalised 0-1, or null
    content       text not null,
    embedding     vector(384) not null,
    created_at    timestamptz not null default now()
);

create index if not exists document_chunks_embedding_idx
    on document_chunks using hnsw (embedding vector_cosine_ops);

create index if not exists document_chunks_title_source_idx
    on document_chunks (title_number, source);

-- ── format_library — standard UK conveyancing enquiry templates ──

create table if not exists format_library (
    id            text primary key,   -- e.g. "enquiry_A1" — deterministic, used for direct lookup
    code          text not null,      -- e.g. "A1"
    section       text,
    topic         text,
    trigger_text  text,
    content       text not null,      -- the draft enquiry wording
    embedding     vector(384) not null,
    created_at    timestamptz not null default now()
);

create unique index if not exists format_library_code_idx on format_library (code);

create index if not exists format_library_embedding_idx
    on format_library using hnsw (embedding vector_cosine_ops);

-- ── Similarity search RPCs ──
-- supabase-py can't do vector math client-side, so cosine search is exposed
-- as Postgres functions called via supabase.rpc(...).

create or replace function match_document_chunks(
    query_embedding vector(384),
    match_title_number text,
    match_source text default null,
    exclude_source text default null,
    match_count int default 10
)
returns table (
    id text, title_number text, source text, page int,
    chunk_index int, total_chunks int, bbox jsonb, content text, similarity float
)
language sql stable
as $$
    select id, title_number, source, page, chunk_index, total_chunks, bbox, content,
           1 - (embedding <=> query_embedding) as similarity
    from document_chunks
    where title_number = match_title_number
      and (match_source is null or source = match_source)
      and (exclude_source is null or source <> exclude_source)
    order by embedding <=> query_embedding
    limit match_count;
$$;

create or replace function match_format_library(
    query_embedding vector(384),
    match_count int default 3
)
returns table (
    id text, code text, section text, topic text, trigger_text text, content text, similarity float
)
language sql stable
as $$
    select id, code, section, topic, trigger_text, content,
           1 - (embedding <=> query_embedding) as similarity
    from format_library
    order by embedding <=> query_embedding
    limit match_count;
$$;
