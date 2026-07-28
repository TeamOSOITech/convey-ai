-- case_id_migration.sql — adds case_id to the already-live document_chunks
-- table and backfills existing rows, then swaps match_document_chunks to
-- filter by case_id instead of title_number.
--
-- Run this ONCE against a Supabase project that already ran the original
-- pgvector_schema.sql (i.e. already has data in document_chunks). For a
-- brand-new project, just run pgvector_schema.sql — it already has this
-- schema baked in, this file is not needed there.

alter table document_chunks
    add column if not exists case_id uuid references cases(id) on delete cascade;

create index if not exists document_chunks_case_id_idx on document_chunks (case_id);

-- Backfill existing rows by joining on the title_number they already share with cases
update document_chunks dc
set case_id = c.id
from cases c
where c.title_number = dc.title_number
  and dc.case_id is null;

-- Replace the similarity-search RPC to filter by case_id instead of title_number
create or replace function match_document_chunks(
    query_embedding vector(384),
    match_case_id uuid,
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
    where case_id = match_case_id
      and (match_source is null or source = match_source)
      and (exclude_source is null or source <> exclude_source)
    order by embedding <=> query_embedding
    limit match_count;
$$;
