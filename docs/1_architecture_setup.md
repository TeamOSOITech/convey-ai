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
└──────────┬──────────────────────┬───────────────────────────────────┘
           │                      │
           ▼                      ▼
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ Supabase        │    │ ChromaDB (Vector Store)                       │
│ (PostgreSQL)    │    │ Persisted on Railway disk at /app/data        │
│                 │    │                                               │
│ Tables:         │    │ Collections:                                  │
│ - cases         │    │ - case_documents (all uploaded doc text)      │
│ - case_documents│    │ - format_library (enquiry templates)          │
└─────────────────┘    │ - checklists (freehold/leasehold checks)      │
                       └──────────────────────────────────────────────┘
                                         │
                                         ▼
                       ┌──────────────────────────────────────────────┐
                       │ External AI APIs                              │
                       │                                               │
                       │ - Google Gemini API (title reports, extract)  │
                       │ - Groq API (chatbot fallback: gpt-oss-120b)  │
                       └──────────────────────────────────────────────┘
```

---

## 1.3 Technology Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Backend runtime |
| FastAPI | latest | REST API framework |
| Uvicorn | latest | ASGI server (runs FastAPI) |
| ChromaDB | latest | Vector database for semantic search |
| SentenceTransformers | latest | Local text embedding model (`BAAI/bge-large-en-v1.5`) |
| google-generativeai | 0.8.3 | Gemini AI models for all generation tasks |
| groq | latest | Groq API client (chatbot fallback) |
| supabase | latest | PostgreSQL database client |
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
| **Railway** | Hosts the FastAPI backend inside a Docker container. Provides persistent disk storage for ChromaDB. |
| **Supabase** | Managed PostgreSQL database AND user authentication service. |

---

## 1.4 Project Folder Structure

```
convey-ai/
│
├── backend/                    ← FastAPI Python backend
│   ├── main.py                 ← Main API server, all HTTP endpoints
│   ├── auth_utils.py           ← JWT authentication dependency
│   ├── database.py             ← Supabase database operations
│   ├── embeddings.py           ← ChromaDB setup & vector operations
│   ├── chunker.py              ← Splits document text into chunks
│   ├── ocr.py                  ← OCR processing for uploaded PDFs
│   ├── zip_processor.py        ← Handles ZIP file extraction
│   ├── chatbot.py              ← AI chatbot & enquiry generation (RAG)
│   ├── title_report.py         ← Title Report AI generation logic
│   ├── title_check.py          ← Title Check & Enquiry AI logic
│   ├── ingest_formats.py       ← Populates the format library in ChromaDB
│   ├── routes/                 ← Modular API route files
│   │   ├── __init__.py
│   │   ├── formats.py          ← GET /formats/{code} endpoint
│   │   ├── smart_extract.py    ← POST /smart-extract endpoint
│   │   └── form_filler.py      ← POST /form-extract endpoint
│   ├── requirements.txt        ← Python package dependencies
│   ├── Dockerfile              ← Docker build instructions for Railway
│   ├── .env                    ← Secret environment variables (NOT in git)
│   └── data/                   ← Runtime data (Railway persistent disk)
│       ├── chroma_db/          ← ChromaDB vector store files
│       └── processed_pdfs/     ← Processed PDF files served statically
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
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API key for AI generation |
| `GROQ_API_KEY` | `gsk_...` | Groq API key for chatbot fallback |
| `DATA_DIR` | `/app/data` | Path for persistent data storage. Set to `/app/data` on Railway, left as `./data` locally. |
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

Supabase provides a managed PostgreSQL database. The schema has two tables:

### Table: `cases`
Stores one record per property case.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated unique identifier |
| `title_number` | TEXT | Land Registry title number (e.g. `EX332661`). Unique per case. |
| `status` | TEXT | Case status — always `"active"` currently |
| `created_at` | TIMESTAMP | When the case was created. Used for ordering the dashboard. |

### Table: `case_documents`
Stores metadata about every uploaded document. The actual file content lives in ChromaDB; this table just tracks what files have been processed.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated unique identifier |
| `case_id` | UUID (FK) | References `cases.id` |
| `title_number` | TEXT | Duplicated for easy filtering without joins |
| `doc_type` | TEXT | Document category code: `OCE`, `LEASE`, `TR1`, `CONTRACT`, `TA6`, `TA10`, `EPC`, `OTHER` |
| `filename` | TEXT | Original filename (e.g. `Title_Register.pdf`) |
| `file_url` | TEXT | URL to the processed PDF on Railway (served via `/processed/` static route) |
| `processed` | BOOLEAN | Always `true` — set when OCR + embedding is complete |

---

## 1.7 ChromaDB — Vector Database

ChromaDB is an in-process vector database that stores document text as mathematical vectors (embeddings) so that AI semantic search can work.

It lives at `DATA_DIR/chroma_db/` on the Railway disk. It has three separate **collections** (think of them as tables):

| Collection Name | Embedding Model | Contents |
|---|---|---|
| `case_documents` | `BAAI/bge-large-en-v1.5` (768 dimensions) | Text chunks from all uploaded case documents. Each chunk has metadata: `title_number`, `source` (filename), `chunk_index`. |
| `format_library` | `BAAI/bge-large-en-v1.5` (768 dimensions) | Standard UK legal enquiry templates and their codes (e.g. `A1`, `F3a`). Populated by running `ingest_formats.py`. |
| `checklists` | `BAAI/bge-large-en-v1.5` (768 dimensions) | Freehold and Leasehold title check item descriptions. Used by the Title Check feature to match issues to enquiry codes. |

> **Why use a separate embedding model?** ChromaDB has a built-in default embedder, but it only produces 384-dimensional vectors. Our model (`BAAI/bge-large-en-v1.5`) produces 768-dimensional vectors for significantly better semantic accuracy on legal text. This means **all vector operations must use our custom model** — passing raw text to ChromaDB's built-in search would cause a dimension mismatch crash.

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
- Railway provides a **persistent volume** mounted at `/app/data` — this is where ChromaDB and processed PDFs are stored permanently (they survive container restarts and redeploys).
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

### Step 2 — Backend setup
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

### Step 3 — Frontend setup
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

### Step 4 — Populate the format library (first time only)
The ChromaDB `format_library` and `checklists` collections need to be seeded with enquiry templates. This only needs to be done once:
```bash
cd backend
python ingest_formats.py
```

---

*Next: Chapter 2 — Backend Core Infrastructure*
