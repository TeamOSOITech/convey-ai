# Convey-AI — Outstanding Work & Security Backlog

> Last updated: 2026-07-07

---

## Important Tech Changes

| # | Item | Notes |
|---|---|---|
| 1 | LLM  | Add Claude ZDR or Gemini ZDR |
| 2 | Groq to Gemini | Try to use both groq and gemini for flexibility |
| 3 | BETTER OCR | AWS Textract or Other paid ocr service, but for pdf on display use ocrmypdf only (currently using) |

---

## Part 1 — Security Issues Still Open

The original security audit ran on 2026-06-23. The table below shows every issue, its current status, and what still needs to be done.

### ✅ Issues Already Fixed

| ID | Issue | How it was fixed |
|---|---|---|
| **F2** | Upload page had no auth guard | `useAuth()` + auth redirect added to `upload/page.js` (line 13) |
| **F3** | No JWT sent to backend in API calls | `lib/api.js` (`apiFetch`) created — automatically attaches `Authorization: Bearer <token>` to every request |
| **F6** | `fetchCases()` fired before auth resolved | `useEffect([user])` dependency added in `app/page.js` |
| **F9** | No security headers | `next.config.mjs` now includes `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`, and `Content-Security-Policy-Report-Only` |
| **B3** | Path traversal on `/view-pdf/{filename}` | `pathlib.Path.resolve()` + prefix check added in `main.py` — `..` and absolute paths are blocked |

---

### Critical Issues — Still Open

These are the highest-priority items. They put live client legal data at risk right now.

---

#### B1 / F1 — API Keys May Still Be in Git History

**Risk:** `GROQ_API_KEY`, `SUPABASE_KEY` (service_role — bypasses ALL Row Level Security), and `GOOGLE_API_KEY` were stored in `.env`. `NEXT_PUBLIC_SUPABASE_ANON_KEY` and the Railway URL were in `.env.local`. Even if these files are now in `.gitignore`, if they were ever committed, the credentials are permanently in git history and readable by anyone with repo access.

**What to do:**
1. Run these commands to check:
   ```bash
   git log --all --full-history -- backend/.env
   git log --all --full-history -- frontend/.env.local
   ```
2. If any results appear — use **BFG Repo Cleaner** to purge them from all history
3. **Rotate all keys immediately** regardless — assume they are compromised:
   - Groq: console.groq.com — API Keys
   - Google AI Studio: aistudio.google.com — API Keys
   - Supabase: Project Settings — API — Rotate `service_role` key
4. Ensure `.env` and `.env.local` are in `.gitignore` and inject all secrets via Railway / Vercel environment variable panels only

---

#### B2 / B10 — Unauthenticated Admin Endpoints Still Live

**File:** `backend/main.py`

These endpoints are open to anyone on the internet:
```
POST /ingest-formats   → rebuilds ChromaDB format library
POST /reingest-formats → WIPES all enquiry templates
POST /ingest-letters   → wipes letter template library
GET  /debug-chunks/{title_number}  → returns ChromaDB chunks (client document text)
GET  /debug-query/{title_number}   → returns actual text from client legal documents
GET  /debug-sources/{title_number} → returns all filenames for any case
```

Any person who guesses a UK title number (format: 2 letters + 6 digits, predictable) can read the full text contents of any client's uploaded legal documents via `/debug-query`.

**What to do:**
- **Delete** `/debug-chunks`, `/debug-query`, `/debug-sources` from `main.py` entirely — they have no business purpose in production
- **Protect** `/ingest-formats` and `/reingest-formats` with a secret admin token:
  ```python
  @app.post("/reingest-formats")
  async def reingest_formats_route(x_admin_token: str = Header(...)):
      if x_admin_token != os.getenv("ADMIN_SECRET"):
          raise HTTPException(status_code=403)
  ```

---

#### B4 — Path Traversal in `title_check.py`

**File:** `backend/title_check.py` — `resolve_pdf_path()` (lines 86-100)

The fix applied to `/view-pdf/` in `main.py` was NOT applied here. The `filename` from the `/title-check` POST body flows directly into `os.path.join()` without canonicalisation. A filename of `../../.env` passes through the cleanup and PyMuPDF attempts to open it.

**What to do:** Apply the same `pathlib` canonicalisation:
```python
def resolve_pdf_path(filename: str) -> str:
    cleaned = filename.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "")
    base_dir = pathlib.Path(DATA_DIR).resolve() / "processed_pdfs"
    requested = (base_dir / cleaned).resolve()
    if not str(requested).startswith(str(base_dir)):
        return None
    return str(requested) if requested.exists() else None
```

---

#### B5 — Backend Has NO Authentication on Most Endpoints

**File:** `backend/main.py`

While `apiFetch()` on the frontend now sends the `Authorization: Bearer` header, the **backend never validates it on most routes**. The `require_auth` dependency exists in `auth_utils.py` but is only added to some endpoints. Routes like `/chat`, `/title-check`, `/generate-title-report` still have no `Depends(require_auth)`.

This means anyone who finds the Railway URL can use the API exactly like a logged-in solicitor — uploading documents, reading case data, running AI tools on other clients' cases.

**What to do:** Add `_user=Depends(require_auth)` to every endpoint that handles case data or AI operations:
```python
@app.post("/chat")
async def chat_route(..., _user=Depends(require_auth)):
    ...
```

---

### High Issues — Still Open

---

#### B7 — No File Upload Size Limit

**File:** `backend/main.py`, `zip_processor.py`

There is no size cap on uploaded PDFs or ZIPs. A 10GB upload will consume all Railway memory and crash the server. The ZIP extractor also has no **Zip Slip** protection — a malicious ZIP with `../` paths could write files outside the temp directory.

**What to do:**
```python
MAX_SIZE = 50 * 1024 * 1024  # 50MB

contents = await file.read()
if len(contents) > MAX_SIZE:
    raise HTTPException(status_code=413, detail="File too large. Maximum 50MB.")

# In zip_processor.py before extractall():
for member in zip_ref.namelist():
    if ".." in member or member.startswith("/") or member.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid ZIP contents")
```

---

#### B8 — Wildcard CORS on `/view-pdf/` Endpoint

**File:** `backend/main.py`

The `/view-pdf/` endpoint returns a hardcoded `Access-Control-Allow-Origin: *` header. Client legal document PDFs can be fetched from ANY website cross-origin.

**What to do:** Remove the manual `Access-Control-Allow-Origin: *` header and let the existing `CORSMiddleware` (which has a restricted origin list) handle it.

---

#### B9 — No Rate Limiting on Any Endpoint

An attacker can flood `/chat` or `/title-check` to exhaust Gemini API quota (costs real money), or flood `/upload-pdf` to fill Railway disk.

**What to do:** Add `slowapi`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat")
@limiter.limit("30/minute")
async def chat_route(request: Request, ...):
    ...
```

Recommended limits: `/chat` 30/min, `/title-check` 10/min, `/upload-pdf` 20/min, `/upload-zip` 5/min.

---

#### F5 — IDOR: Any User Can Access Any Case

Any authenticated solicitor who knows another client's title number can navigate to `/case/EX123456` and see all their documents, run AI tools on them, and delete them. There is no ownership check.

**What to do:**
1. Add a `user_id` column to the `cases` table in Supabase
2. On `POST /cases` — store the JWT `sub` as `user_id`
3. On all `GET /cases/{title_number}` requests — verify `user_id == JWT sub`
4. Enable Row Level Security (RLS) in Supabase on both `cases` and `case_documents` tables

---

#### F8 — No Rate Limiting / Lockout on Login

The login page calls `supabase.auth.signInWithPassword()` with no attempt counter, no lockout, and no CAPTCHA. An attacker can script unlimited login attempts.

**What to do:**
1. Enable Supabase Auth built-in rate limiting: Project — Auth — Rate Limits
2. Add client-side attempt counter with exponential backoff in `login/page.js`
3. Optionally add Cloudflare Turnstile CAPTCHA after 3 failures

---

### Medium Issues — Still Open

| ID | Issue | What to do |
|---|---|---|
| **B6** | Prompt injection via user-controlled input to LLM | Sanitise all user input before interpolating into prompts. Never inject `filename` (user-controlled) directly into system prompts |
| **B11** | Chat history role injection | Validate `role` is only `"user"` or `"assistant"` before passing to LLM |
| **B12** | No `title_number` format validation | Add regex check `^[A-Z]{2}[0-9]{1,8}$` before using in any DB/ChromaDB query |
| **B13** | Raw Python exception details sent to client | Log full error server-side, return `{"detail": "An error occurred"}` to client |
| **B14** | Unpinned Python dependencies | Run `pip freeze > requirements.txt` to lock all versions |
| **B15** | CORS regex matches ALL `*.vercel.app` subdomains | Replace regex with explicit list `allow_origins=["https://convey-ai.vercel.app"]` |
| **B16** | Mutable default argument `history=[]` in chatbot.py | Change to `history=None` then `if history is None: history = []` |
| **B17** | `Content-Disposition` header not URL-encoded | Wrap filename with `urllib.parse.quote(filename)` |
| **F11** | ReactMarkdown renders AI content without XSS sanitisation | Add `rehype-sanitize` plugin to all `<ReactMarkdown>` instances |
| **F12** | Supabase RLS not confirmed enabled on tables | In Supabase dashboard — Table Editor — each table — Enable RLS + add policies |
| **F13** | Document delete has no server-side ownership check | Backend `DELETE /cases/{title_number}/documents/{doc_id}` must verify JWT sub owns the document |
| **F14** | PDF iframes have no `sandbox` attribute | Add `sandbox="allow-scripts allow-same-origin"` to all `<iframe>` tags serving PDFs |
| **F15** | `ngrok-skip-browser-warning` header in production code | Remove from `lib/api.js` |
| **F16** | `console.error()` leaks internal details | Replace with a proper error reporting service (e.g. Sentry) in production |

---

### Low Issues — Still Open

| ID | Issue | What to do |
|---|---|---|
| **B18** | Docker container runs as root | Add `RUN adduser --disabled-password appuser` + `USER appuser` to Dockerfile |
| **B19** | FastAPI `/docs` and `/redoc` are public | `FastAPI(docs_url=None, redoc_url=None)` in production |
| **B20** | OCR output path in `ocr.py` not canonicalised | Apply same `pathlib.resolve()` + prefix check to output path in `ocr.py` |
| **F17** | Default scaffold metadata in `layout.js` | Update `title` and `description` in the `metadata` export |
| **F18** | Login page doesn't redirect authenticated users | Check session on mount in `login/page.js`, redirect to `/` if active |
| **F19** | File type validation is client-side only | Backend should validate magic bytes (first 4 bytes of PDF: `%PDF`) |
| **F20** | `alert()` used for security-sensitive feedback | Replace with a toast notification component (e.g. `react-hot-toast`) |

---

## Part 2 — Features Left to Build

These are planned product features not yet implemented, in priority order.

---

### High Priority

#### 1. Letter Generator Tool
**Status:** Card exists on Case Dashboard (marked "Coming Soon")  
**Path:** `/case/[titleNumber]/letters`  
**What it is:** Generate standard UK conveyancing letters — Report on Title, Completion Letter, Client Care Letter, Exchange of Contracts confirmation, etc.

**What's needed:**
- `backend/routes/letter_generator.py` — define letter types and their prompts
- Seed letter templates into ChromaDB (`ingest_letters.py` already partially exists)
- Frontend: `app/case/[titleNumber]/letters/page.js` — letter type selector + generated output
- Same pattern as Smart Extract but with fixed letter structures

---

#### 2. Case Ownership — Multi-User Isolation
**Status:** Not started  
**What it is:** Currently all cases are visible to all logged-in users. Each case should belong to the user (or firm) that created it.

**What's needed:**
- Add `user_id` column to `cases` table in Supabase
- Update `POST /cases` to store `user.id` from JWT
- Update `GET /cases` to filter by `user_id`
- Update all case-level endpoints to verify ownership
- Enable Supabase RLS policies

---

#### 3. Rate Limiting
**Status:** Not started (security issue B9)  
**What's needed:** `pip install slowapi` + rate limit decorator on all AI endpoints — see B9 fix above.

---

#### 4. Key Dates Tracker
**Status:** Card exists on Case Dashboard (marked "Coming Soon")  
**Path:** `/case/[titleNumber]/key-dates`  
**What it is:** Track critical deadlines — completion date, exchange date, search expiry, mortgage offer expiry.

**What's needed:**
- Smart Extract can already pull dates — this tool would store and display them with countdown logic
- A `key_dates` table in Supabase per case
- Frontend calendar/timeline view

---

#### 5. Completion Statement Generator
**Status:** Card exists on Case Dashboard (marked "Coming Soon")  
**Path:** `/case/[titleNumber]/completion-statement`  
**What it is:** Generate buyer and seller financial breakdowns — purchase price, deposit, mortgage redemption, SDLT, solicitor fees, estate agency fees.

**What's needed:**
- Extraction prompt targeting all financial figures from Contract, TA13, mortgage docs
- Structured output rendered as a financial table
- Export to clipboard or PDF

---

### Medium Priority

#### 6. Form Auto-Filler — Additional Form Types
**Status:** Only TR1 supported  
**What's needed:** Add entries to `FORM_PROMPTS` in `routes/form_filler.py` for:
- **AP1** — Application to register (HMLR)
- **DS1** — Discharge of mortgage
- **TA13** — Completion Information Form
- Each new form type only requires a new key in `FORM_PROMPTS` — no structural code changes

---

#### 7. Document Re-upload / Replace
**Status:** Not implemented  
**What it is:** Currently if a solicitor uploads a wrong document, they must delete and re-upload separately. No "replace" flow exists.

**What's needed:**
- A "Replace" button per document on the case dashboard
- Backend: delete old ChromaDB chunks + Supabase record + disk file, then process new file
- Wraps the existing delete + upload pipeline

---

#### 8. Bulk Download / Export
**Status:** Not implemented  
**What it is:** Download all OCR'd PDFs for a case as a ZIP, or export the title report as a formatted PDF.

**What's needed:**
- Backend: `GET /cases/{title_number}/export` — zip all `processed_pdfs` for the case
- Frontend: Download button on the Case Dashboard
- Optional: `reportlab` or `weasyprint` for PDF export of the title report

---

#### 9. Title Check — Additional Form Rules
**Status:** Supports TA6, TA10, TA13  
**What's needed:**
- Add new form keywords to `FORM_KEYWORDS` in `title_check.py`
- Add new rules to `GLOBAL_RULE_POOL` for the new forms
- No structural code changes needed — the rule pool is flat and evaluated as a whole

---

#### 10. User Management / Firm Admin Panel
**Status:** Not started  
**What it is:** A firm admin should be able to invite solicitors, deactivate accounts, and see all cases across the firm.

**What's needed:**
- Supabase team management / magic link invites
- A `/admin` route protected by a role check
- Firm-level ownership for case sharing within the same firm

---

### Low Priority / Polish

| # | Item | Notes |
|---|---|---|
| 11 | ReactMarkdown `rehypeSanitize` | Add `rehype-sanitize` to all `<ReactMarkdown>` instances (security F11) |
| 12 | Toast notifications | Replace all `alert()` with `react-hot-toast` or `sonner` |
| 13 | Custom error pages | Add `app/not-found.js` and `app/error.js` |
| 14 | Loading skeleton states | Replace `<p>Loading...</p>` with skeleton cards across all pages |
| 15 | Mobile responsiveness | Chatbot 3-panel and title report 2-column don't work on mobile |
| 16 | `layout.js` metadata | Update title/description from default scaffold text (security F17) |
| 17 | Disable FastAPI `/docs` in production | Gate with `ENVIRONMENT` env var (security B19) |

---

## Recommended Sprint Order

```
This week — Stop immediate security risks
├── Rotate ALL API keys (assume compromised)
├── Purge .env from git history (BFG Repo Cleaner)
├── Delete debug endpoints (B2/B10) from main.py
├── Fix path traversal in title_check.py (B4)
└── Add file upload size limit + Zip Slip check (B7)

Next sprint — Authentication completeness
├── Add Depends(require_auth) to ALL backend endpoints (B5)
├── Add user_id ownership to cases + Supabase RLS policies (F5)
├── Add rate limiting via slowapi (B9)
└── Fix CORS wildcard on /view-pdf/ (B8)

Following sprint — Product features
├── Letter Generator tool
├── Key Dates tracker
├── Additional form types for Form Filler
└── Document replace flow

Polish
├── rehypeSanitize on ReactMarkdown (F11)
├── Toast notifications replacing alert()
├── Custom 404/500 error pages
└── layout.js metadata update
```

