# Convey-AI — Technical Documentation
## Chapter 8: Deployment — Spinning Up a New Environment

---

## 8.1 What This Covers

Convey-AI's only persistent state lives in Supabase (Postgres tables, pgvector tables, and a Storage bucket) — the backend (Railway) and frontend (Vercel) are both stateless and can be redeployed freely. That means standing up a **complete new environment** — a separate client tenant, a staging environment, disaster recovery, whatever the reason — is just: new Supabase project → run two SQL scripts → deploy backend → deploy frontend → point them at each other.

This chapter is a repeatable checklist for exactly that. Nothing here is automated end-to-end (there's no single "deploy" script) — each step is a dashboard action or a command, in order.

---

## 8.2 Prerequisites

- A Supabase account (supabase.com) — can be a new organization/project under an existing account, doesn't need to be a separate Supabase account
- A Railway account, with access to this GitHub repo
- A Vercel account, with access to this GitHub repo
- API keys for Google Gemini and Groq (can reuse existing keys across environments, or use separate ones — your call)

---

## 8.3 Step 1 — Create the Supabase Project

1. supabase.com/dashboard → **New Project**.
2. Pick an organization, name, database password (save it — you likely won't need it directly since the app uses the API keys, not a direct Postgres connection string, but keep it somewhere safe), and region.
3. Wait for provisioning to finish (~2 minutes).

---

## 8.4 Step 2 — Run the SQL Scripts

In the new project: **SQL Editor → New query**.

Run these two scripts from this repo, in either order (they don't depend on each other):

1. [`backend/sql/core_schema.sql`](../backend/sql/core_schema.sql) — creates `cases` and `case_documents`.
2. [`backend/sql/pgvector_schema.sql`](../backend/sql/pgvector_schema.sql) — enables the `pgvector` extension, creates `document_chunks` and `format_library`, and the `match_document_chunks`/`match_format_library` similarity-search functions.

Copy-paste each file's full contents into a query and hit **Run**. Both are idempotent (`if not exists` / `or replace` throughout) — safe to re-run.

> No Row Level Security policies are created by either script. The backend always uses the `service_role` key (which bypasses RLS) and the frontend never queries these tables directly — this matches current production behavior exactly. If you want RLS as defense-in-depth, that's tracked separately in `docs/todo_and_security.md` (item F12) and is a deliberate future decision, not something these scripts assume.

---

## 8.5 Step 3 — Storage Bucket (no action needed)

The `case-documents` Storage bucket is created automatically the first time the backend boots against this project — see `_ensure_bucket()` in `backend/storage.py`. Nothing to do here manually; it'll appear under **Storage** in the dashboard after the first successful backend deploy (Step 7).

---

## 8.6 Step 4 — Create a Login User

The frontend only has a **login** page, no sign-up flow (`app/login/page.js` calls `supabase.auth.signInWithPassword` directly). Without at least one user, nobody can log in.

**Authentication → Users → Add user** in the Supabase dashboard. Create one with an email/password, or invite by email. Repeat for every solicitor who needs access.

---

## 8.7 Step 5 — Collect Supabase Credentials

**Project Settings → API** in the new project. You'll need three values:

| Value | Where | Used by |
|---|---|---|
| Project URL | "Project URL" | Both backend `SUPABASE_URL` and frontend `NEXT_PUBLIC_SUPABASE_URL` |
| `service_role` key | "Project API keys" → `service_role` (click reveal) | Backend `SUPABASE_KEY` only — **never** put this in the frontend |
| `anon` key | "Project API keys" → `anon` `public` | Frontend `NEXT_PUBLIC_SUPABASE_ANON_KEY` only |

---

## 8.8 Step 6 — Deploy the Backend (Railway)

1. Railway → **New Project** → **Deploy from GitHub repo** → select this repo.
2. In the service's **Settings**, set the **Root Directory** to `backend` (the `Dockerfile` and `Procfile` live there, not at the repo root).
3. Railway builds from `backend/Dockerfile` automatically (Python 3.11-slim + `tesseract-ocr`, `ghostscript`, `libgl1` + `pip install -r requirements.txt`) and starts with `uvicorn main:app --host 0.0.0.0 --port $PORT` per the `Procfile`.
4. Set environment variables under **Variables**:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Project URL from Step 5 |
| `SUPABASE_KEY` | `service_role` key from Step 5 |
| `SUPABASE_STORAGE_BUCKET` | Optional — defaults to `case-documents` if unset |
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `GOOGLE_API_KEY` | Same value as `GEMINI_API_KEY` — `title_check.py` reads this specific name |
| `GROQ_API_KEY` | Your Groq API key |
| `DEV_MODE` | `false` — **do not** set `true` in a real deployment; it enables endpoints that expose raw document text (`/debug-chunks`, `/debug-query`, `/debug-sources`) |

5. Deploy. Note the generated Railway URL (e.g. `https://your-service.up.railway.app`) — the frontend needs it next.

---

## 8.9 Step 7 — Deploy the Frontend (Vercel)

1. Vercel → **Add New Project** → import this repo.
2. In **Root Directory**, select `frontend` (same reasoning as Railway — it's a subfolder, not the repo root).
3. Set environment variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL from Step 5 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `anon` key from Step 5 |
| `NEXT_PUBLIC_API_URL` | The Railway URL from Step 6 |

4. Deploy.

### CORS — no backend code change needed
The backend's CORS config in `main.py` already allows `allow_origin_regex = r"https://.*\.vercel\.app"` — **any** `*.vercel.app` domain is accepted automatically, including a brand-new Vercel project's default domain. You only need to touch `main.py`'s `allow_origins` list if you later attach a **custom domain** (not a `*.vercel.app` one) to the frontend.

---

## 8.10 Step 8 — Seed the Format Library

`format_library` starts empty — the Title Check and Raise Enquiry features need it populated before they're useful. Two ways to run it:

**Locally, pointed at the new project** (create a throwaway `backend/.env` with the new project's credentials, or temporarily edit your existing one):
```bash
cd backend
python ingest_formats.py
```

**Or remotely**, once the backend is deployed:
```bash
curl -X POST https://your-service.up.railway.app/reingest-formats
```

Either way this is a full wipe-and-rebuild of `format_library` — safe to re-run whenever `ingest_formats.py`'s enquiry list changes.

---

## 8.11 Step 9 — Smoke Test

In order, on the deployed frontend URL:
1. Log in with the user created in Step 4.
2. Create a case (a title number, e.g. `TESTCASE`).
3. Upload a single PDF via `/case/TESTCASE/upload` — confirm it succeeds (check Railway logs if not; the most likely failure mode is a missing/wrong env var).
4. Open the case, confirm the PDF renders in the viewer (proves Supabase Storage + signed URLs work).
5. Ask the chatbot a question about the document (proves `document_chunks` + the `match_document_chunks` RPC work).
6. Run Title Check on a TA6/TA10 if you have one, or hit `GET /formats/A1` directly — confirm it returns a template (proves `format_library` was seeded).
7. Delete the test document, confirm it disappears from the case (proves the Storage object + `document_chunks` rows were cleaned up too).

---

## 8.12 Full Environment Variable Reference

| Service | Variable | Source |
|---|---|---|
| Backend (Railway) | `SUPABASE_URL` | Supabase → Project Settings → API |
| Backend (Railway) | `SUPABASE_KEY` | Supabase → Project Settings → API → `service_role` |
| Backend (Railway) | `SUPABASE_STORAGE_BUCKET` | Optional, defaults to `case-documents` |
| Backend (Railway) | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google AI Studio |
| Backend (Railway) | `GROQ_API_KEY` | console.groq.com |
| Backend (Railway) | `DEV_MODE` | `false` in production, `true` only for local dev |
| Frontend (Vercel) | `NEXT_PUBLIC_SUPABASE_URL` | Same as backend's `SUPABASE_URL` |
| Frontend (Vercel) | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → `anon` `public` |
| Frontend (Vercel) | `NEXT_PUBLIC_API_URL` | The Railway backend's public URL |

See `docs/1_architecture_setup.md` §1.5 for the same table framed for local development instead of a fresh cloud environment.
