-- core_schema.sql — one-time setup for Convey AI's core Postgres tables
--
-- Run this once in the Supabase SQL Editor (Project → SQL Editor → New query),
-- on any fresh Supabase project you want to run Convey AI against — a new
-- client tenant, a staging environment, disaster recovery, etc.
--
-- This covers the two plain relational tables (cases, case_documents).
-- For the vector-search tables (document_chunks, format_library) run
-- pgvector_schema.sql as well — the two scripts are independent and can
-- run in either order.
--
-- No Row Level Security policies are defined here. The backend always
-- talks to Postgres with the service_role key (which bypasses RLS), and
-- the frontend never queries these tables directly — this matches current
-- production behavior. RLS hardening is tracked separately in
-- docs/todo_and_security.md (F12) if you want to add it later.

create extension if not exists pgcrypto;  -- provides gen_random_uuid(); on by default on Supabase

create table if not exists cases (
    id           uuid primary key default gen_random_uuid(),
    title_number text not null unique,
    status       text not null default 'active',
    created_at   timestamptz not null default now()
);

create table if not exists case_documents (
    id           uuid primary key default gen_random_uuid(),
    case_id      uuid not null references cases(id) on delete cascade,
    title_number text not null,     -- denormalised copy of cases.title_number, for filtering without a join
    doc_type     text not null default 'OTHER',   -- OCE, LEASE, TR1, CONTRACT, TA6, TA10, EPC, OTHER, ...
    filename     text not null,     -- original uploaded filename
    file_url     text,              -- Supabase Storage PATH (e.g. "EX332661/Lease_ocr.pdf"), not a URL —
                                     -- signed on read by database.get_case(), see storage.py
    processed    boolean not null default true,
    created_at   timestamptz not null default now()
);

create index if not exists case_documents_title_number_idx on case_documents (title_number);
create index if not exists case_documents_case_id_idx on case_documents (case_id);
