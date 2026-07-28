# Convey-AI — Technical Documentation
## Chapter 1: System Architecture & Setup

---

## 1.1 What Is Convey-AI?

Convey-AI is an internal legal technology platform built for UK conveyancing solicitors. It uses Artificial Intelligence to automate the most time-consuming parts of property transaction work, including:

- Reading and understanding large volumes of uploaded legal documents
- Running AI-powered title checks against standard UK conveyancing checklists
- Generating formal Title Reports for clients
- Drafting legal enquiries (pre-contract questions) to the seller's solicitors
- Answering solicitor questions about case documents in plain English via a chatbot
- Extracting specific information from documents on demand
- Auto-filling legal forms (e.g. TR1 Transfer forms) from case documents

The system is designed for a team of solicitors who each handle multiple property cases simultaneously. Every case is identified by its **Land Registry Title Number** (e.g. `EX332661`).

---

## 1.2 High-Level Architecture

The system is split into two completely separate applications that communicate via HTTP:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                              │
│                                                                     │
│   Next.js 16 Frontend (React 19)                                    │
│   Hosted on: Vercel (convey-ai-mauve.vercel.app)                   │
│                                                                     │
│   ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│   │  Dashboard/Cases │  │  AI Tools UI     │  │  Auth Pages     │  │
│   └──────────────────┘  └──────────────────┘  └─────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTPS API calls
                              │ (Authorization: Bearer <JWT>)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND SERVER                              │
│                                                                     │
│   FastAPI (Python 3.11)                                             │
│   Hosted on: Railway (convey-ai-production-be43.up.railway.app)    │
│   Port: 8080                                                        │
│                                                                     │
│   ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│   │  main.py (API)   │  │  AI Services     │  │  Route Modules  │  │
│   └──────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                     │
│   SentenceTransformer embedding model runs in-process here —       │
│   the only local/in-memory state the backend holds.                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                              SUPABASE                                │
│                                                                       │
│  Postgres tables          Storage bucket           pgvector tables   │
│  - cases                  - case-documents          - document_chunks│
│  - case_documents           (processed PDFs,         - format_library│
│                              private, signed URLs)                   │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
                  ┌──────────────────────────────────────────────┐
                  │ External AI APIs                              │
                  │                                               │
                  │ - Google Gemini API (title reports, extract)  │
                  │ - Groq API (chatbot fallback: gpt-oss-120b)   │
                  └──────────────────────────────────────────────┘
```

Documents, structured metadata, and vector search all live in Supabase — the Railway app process holds no persistent state of its own. The one exception is the SentenceTransformer embedding model, which runs in-process to turn chunk text into vectors before they're written to Postgres.

---

## 1.3 Technology Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Backend runtime |
| FastAPI | latest | REST API framework |
| Uvicorn | latest | ASGI server (runs FastAPI) |
| SentenceTransformers | latest | Local text embedding model (`all-MiniLM-L6-v2`) |
| google-generativeai | 0.8.3 | Gemini AI models for all generation tasks |
| groq | latest | Groq API client (chatbot fallback) |
| supabase | latest | Supabase client — Postgres, Storage, and Auth |
| ocrmypdf | latest | PDF OCR processing |
| pymupdf | latest | PDF reading and page extraction |
| langchain-text-splitters | latest | Intelligent text chunking |
| python-dotenv | latest | Environment variable loading |
| python-multipart | latest | File upload support in FastAPI |
| aiofiles | latest | Async file I/O |
| Pillow | latest | Image processing for OCR |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.2.6 | React framework with App Router |
| React | 19.2.4 | UI library |
| @supabase/ssr | 0.10.3 | Supabase client for server-side rendering |
| @supabase/supabase-js | 2.106.1 | Supabase client for browser |
| react-markdown | 10.1.0 | Rendering AI responses as formatted markdown |
| remark-gfm | 4.0.1 | GitHub Flavored Markdown (tables, strikethrough) |
| TailwindCSS | 4 | Utility-first CSS framework |

### Infrastructure
| Service | Purpose |
|---|---|
| **Vercel** | Hosts the Next.js frontend. Auto-deploys from the `main` branch of GitHub. |
| **Railway** | Hosts the FastAPI backend inside a Docker container. Stateless — holds no persistent disk data. |
| **Supabase** | Postgres database, file Storage, vector search (pgvector), and user authentication — all in one place. |

---

## 1.4 Project Folder Structure

```
convey-ai/
│
├── backend/                    ← FastAPI Python backend
│   ├── main.py                 ← Main API server, all HTTP endpoints
│   ├── auth_utils.py           ← JWT authentication dependency
│   ├── database.py             ← Supabase Postgres operations
│   ├── storage.py              ← Supabase Storage operations (processed PDFs)
│   ├── embeddings.py           ← Embedding model + pgvector read/write operations
│   ├── chunker.py              ← Splits document text into chunks
│   ├── ocr.py                  ← OCR processing for uploaded PDFs
│   ├── zip_processor.py        ← Handles ZIP file extraction
│   ├── chatbot.py              ← AI chatbot & enquiry generation (RAG)
│   ├── title_report.py         ← Title Report AI generation logic
│   ├── title_check.py          ← Title Check & Enquiry AI logic
│   ├── ingest_formats.py       ← Populates the format_library table
│   ├── sql/
│   │   └── pgvector_schema.sql ← One-time Supabase SQL setup (tables + RPCs)
│   ├── routes/                 ← Modular API route files
│   │   ├── __init__.py
│   │   ├── formats.py          ← GET /formats/{code} endpoint
│   │   ├── smart_extract.py    ← POST /smart-extract endpoint
│   │   └── form_filler.py      ← POST /form-extract endpoint
│   ├── requirements.txt        ← Python package dependencies
│   ├── Dockerfile              ← Docker build instructions for Railway
│   └── .env                    ← Secret environment variables (NOT in git)
│
└── frontend/                   ← Next.js React frontend
    ├── app/                    ← Next.js App Router pages
    │   ├── layout.js           ← Root layout (applies to all pages)
    │   ├── page.js             ← Dashboard (lists all cases)
    │   ├── globals.css         ← Global CSS
    │   ├── login/              ← Login page
    │   └── case/
    │       └── [titleNumber]/  ← Dynamic case pages (URL: /case/EX332661)
    │           ├── page.js     ← Case overview & tool selector
    │           ├── upload/     ← Document upload tool
    │           ├── chatbot/    ← AI chatbot tool
    │           ├── title-report/ ← Title Report tool
    │           ├── title-check/  ← Title Check & Enquiries tool
    │           ├── extract/    ← Smart Extract tool
    │           └── form-filler/ ← Form Auto-Filler tool
    ├── lib/                    ← Shared utility files
    │   ├── supabase.js         ← Supabase browser client
    │   ├── auth.js             ← useAuth() React hook
    │   └── api.js              ← apiFetch() helper (adds JWT to requests)
    ├── middleware.js            ← Route protection (redirects unauthenticated users)
    ├── next.config.mjs         ← Next.js config + security headers
    ├── package.json            ← Node.js dependencies
    └── .env.local              ← Frontend secret variables (NOT in git)
```

---

## 1.5 Environment Variables

These are the secret keys that connect the application to external services. They are **never committed to git**.

### Backend — `backend/.env`

| Variable | Example Value | Purpose |
|---|---|---|
| `SUPABASE_URL` | `https://xxxx.supabase.co` | URL of the Supabase project |
| `SUPABASE_KEY` | `eyJ...` | Supabase **service role** key (bypasses Row Level Security — keep secret!) |
| `SUPABASE_STORAGE_BUCKET` | `case-documents` | Storage bucket name for processed PDFs. Optional — defaults to `case-documents` if unset. Auto-created on backend startup. |
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API key for AI generation |
| `GROQ_API_KEY` | `gsk_...` | Groq API key for chatbot fallback |
| `DEV_MODE` | `false` | Set to `true` locally only to enable debug endpoints like `/debug-sources` |

### Frontend — `frontend/.env.local`

| Variable | Example Value | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` | Same Supabase URL — safe to expose (starts with `NEXT_PUBLIC_`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` | Supabase **anon** key — safe for browser use (limited permissions) |
| `NEXT_PUBLIC_API_URL` | `https://convey-ai-production-be43.up.railway.app` | The Railway backend URL the frontend calls |

> **Important distinction:** The backend uses the **service role** key (full database access). The frontend uses the **anon** key (limited to public-facing operations like auth). Never swap these.

---

## 1.6 Supabase Database Schema

Supabase provides a managed Postgres database. There are two plain relational tables plus two pgvector tables (see §1.7).

### Table: `cases`
Stores one record per property case.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated unique identifier |
| `title_number` | TEXT | Land Registry title number (e.g. `EX332661`). Unique per case. |
| `status` | TEXT | Case status — always `"active"` currently |
| `created_at` | TIMESTAMP | When the case was created. Used for ordering the dashboard. |

### Table: `case_documents`
Stores metadata about every uploaded document. The actual PDF bytes live in Supabase Storage; this table tracks what's been processed and where to find it.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated unique identifier |
| `case_id` | UUID (FK) | References `cases.id` |
| `title_number` | TEXT | Duplicated for easy filtering without joins |
| `doc_type` | TEXT | Document category code: `OCE`, `LEASE`, `TR1`, `CONTRACT`, `TA6`, `TA10`, `EPC`, `OTHER` |
| `filename` | TEXT | Original filename (e.g. `Title_Register.pdf`) |
| `file_url` | TEXT | **Supabase Storage path** (e.g. `EX332661/Title_Register_ocr.pdf`), not a URL. The bucket is private — a fresh signed URL is minted from this path every time `database.get_case()` returns documents to the frontend, so a stored value never goes stale or leaks a permanent public link. |
| `processed` | BOOLEAN | Always `true` — set when OCR + embedding is complete |

---

## 1.7 pgvector — Vector Search

Vector search runs inside the same Supabase Postgres database via the `pgvector` extension — there's no separate vector database process. Two tables hold embeddings (384-dimensional, from the `all-MiniLM-L6-v2` SentenceTransformer model that runs in-process in the backend):

| Table | Contents |
|---|---|
| `document_chunks` | Text chunks from all uploaded case documents. Columns include `title_number`, `source` (filename), `page`, `chunk_index`, `bbox`, `content`, `embedding`. |
| `format_library` | Standard UK legal enquiry templates and their codes (e.g. `A1`, `F3a`). Populated by running `ingest_formats.py`. |

Similarity search (cosine distance) is exposed as two Postgres functions — `match_document_chunks` and `match_format_library` — called via `supabase.rpc(...)` from `embeddings.py`, since the Supabase Python client can't do vector math client-side. Both tables and functions are set up once via `backend/sql/pgvector_schema.sql`, run manually in the Supabase SQL Editor (see §1.12).

> **Why `all-MiniLM-L6-v2`?** It's a small, fast model (384-dim output) chosen to keep the backend's memory footprint low. An earlier version of this project used the larger `BAAI/bge-large-en-v1.5` (1024-dim) — if you see that name anywhere else, it's stale; the running code has used MiniLM for some time.

---

## 1.8 Authentication Architecture

The app uses **Supabase Auth** with **JWT tokens**. Here is the complete flow from login to an authenticated API call:

```
Step 1 — Login
  User enters email + password on /login page
  → Frontend calls supabase.auth.signInWithPassword()
  → Supabase validates credentials and returns a JWT access token
  → Token is stored in an httpOnly cookie (managed by @supabase/ssr)

Step 2 — Page Load Protection (Middleware)
  User navigates to any page (e.g. /case/EX332661)
  → middleware.js runs BEFORE the page renders (Next.js edge middleware)
  → It calls supabase.auth.getSession() using the cookie
  → If session is valid → allow page to render
  → If session is invalid/missing → redirect to /login

Step 3 — Authenticated API Call
  Frontend React component calls apiFetch('/some-endpoint', ...)
  → lib/api.js retrieves the current JWT: supabase.auth.getSession()
  → Attaches it as: Authorization: Bearer <token>
  → Sends HTTPS request to Railway backend

Step 4 — Backend Token Validation
  FastAPI endpoint has Depends(require_auth) in its signature
  → auth_utils.py extracts the Bearer token from the header
  → Calls supabase.auth.get_user(token) to validate against Supabase
  → If valid → returns the user object, endpoint proceeds
  → If invalid → raises HTTP 401 Unauthorized immediately
```

This means **no API endpoint can be called without a valid Supabase session**. The token is validated server-side against Supabase on every single request.

---

## 1.9 CORS Policy

The backend only accepts requests from trusted origins, preventing any other website from calling the API:

```python
# Allowed origins (in main.py)
allow_origin_regex = r"https://.*\.vercel\.app"   # any Vercel preview deployment
allow_origins = [
    "http://localhost:3000",                         # local development
    "https://convey-ai-mauve.vercel.app",           # production frontend
]
```

---

## 1.10 Security Headers (Frontend)

All pages served by the frontend include these HTTP security headers, configured in `next.config.mjs`:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing attacks |
| `X-Frame-Options` | `DENY` | Prevents clickjacking via iframes |
| `Strict-Transport-Security` | `max-age=63072000` | Forces HTTPS for 2 years |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer info sent to third parties |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disables device access |
| `Content-Security-Policy-Report-Only` | (see next.config.mjs) | CSP in report-only mode (monitoring) |

---

## 1.11 Deployment

### Backend — Railway
- The backend runs as a Docker container on Railway.
- The `Dockerfile` uses Python 3.11 slim as the base image.
- It installs system dependencies: `tesseract-ocr` (OCR engine), `ghostscript` (PDF processing), `libgl1` (image library).
- Then installs all Python packages from `requirements.txt`.
- The server starts with: `uvicorn main:app --host 0.0.0.0 --port 8080`
- The backend is stateless — all persistent data (documents, metadata, vectors) lives in Supabase, not on Railway's disk. No persistent volume is needed.
- Environment variables are set in the Railway dashboard under the project's "Variables" tab.

### Frontend — Vercel
- The Next.js frontend is deployed automatically by Vercel whenever code is pushed to the `main` branch on GitHub.
- Environment variables are set in the Vercel dashboard under "Settings → Environment Variables".
- Vercel automatically handles SSL, CDN, and edge deployments.

---

## 1.12 Local Development Setup

Follow these steps to run the project locally on a new machine:

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Step 1 — Clone the repository
```bash
git clone https://github.com/TeamOSOITech/convey-ai.git
cd convey-ai
```

### Step 2 — Supabase setup (one-time, per project)
In the Supabase dashboard, open **SQL Editor → New query**, paste the contents of `backend/sql/pgvector_schema.sql`, and run it. This enables the `pgvector` extension and creates the `document_chunks`/`format_library` tables plus their similarity-search functions. Only needs to be done once per Supabase project.

### Step 3 — Backend setup
```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate
# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create `backend/.env` with the following content (get real values from a team member):
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
DEV_MODE=true
```

Start the backend:
```bash
uvicorn main:app --reload --port 8000
```
The API is now running at `http://localhost:8000`.

### Step 4 — Frontend setup
```bash
cd frontend
npm install
```

Create `frontend/.env.local` with:
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:
```bash
npm run dev
```
The app is now running at `http://localhost:3000`.

### Step 5 — Populate the format library (first time only)
The `format_library` table needs to be seeded with enquiry templates. This only needs to be done once:
```bash
cd backend
python ingest_formats.py
```

---

*Next: Chapter 2 — Backend Core Infrastructure*
