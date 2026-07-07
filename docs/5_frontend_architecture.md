# Convey-AI — Technical Documentation
## Chapter 5: Frontend Architecture & Auth

---

## 5.1 Overview

The frontend is a **Next.js 14** (App Router) application deployed on **Vercel**. It is a pure client-side rendered application — all pages use `'use client'` and fetch data from the Railway backend at runtime. There is no server-side rendering (SSR) or React Server Components involved.

**Framework:** Next.js 14 (App Router)  
**Styling:** Tailwind CSS  
**Auth:** Supabase Auth (email/password)  
**Fonts:** Geist Sans + Geist Mono (Next.js native fonts)

---

## 5.2 Project Directory Structure

```
frontend/
├── app/                          ← Next.js App Router pages
│   ├── layout.js                 ← Root layout (fonts, global styles)
│   ├── globals.css               ← Global Tailwind base styles
│   ├── page.js                   ← Dashboard (/) — create & list cases
│   ├── login/
│   │   └── page.js               ← Login page (/login)
│   └── case/
│       └── [titleNumber]/        ← Dynamic route — one page per case
│           ├── page.js           ← Case Dashboard — tool selection grid
│           ├── chatbot/
│           │   └── page.js       ← AI Chatbot tool
│           ├── title-report/
│           │   └── page.js       ← Title Report generator
│           ├── title-check/
│           │   └── page.js       ← Title Check + Enquiry Review Board
│           ├── extract/
│           │   └── page.js       ← Smart Extract tool
│           ├── form-filler/
│           │   └── page.js       ← Form Auto-Filler (TR1 etc.)
│           └── upload/
│               └── page.js       ← Document upload page
├── lib/
│   ├── supabase.js               ← Supabase browser client (singleton)
│   ├── auth.js                   ← useAuth() hook + getToken() helper
│   └── api.js                    ← apiFetch() authenticated fetch wrapper
├── middleware.js                  ← Route protection (server-side)
├── next.config.mjs               ← Security headers, image config, CSP
└── .env.local                    ← Environment variables (NOT committed)
```

---

## 5.3 Environment Variables

The frontend uses three environment variables, all prefixed `NEXT_PUBLIC_` — meaning they are available in the browser (included in the JavaScript bundle). This is intentional and safe for these specific values:

| Variable | Value | Why NEXT_PUBLIC_ is safe |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | The Supabase project URL | This is a public URL, not a secret |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | The Supabase anon (public) key | This key is designed to be public — all permissions are governed by RLS (Row Level Security) policies in Supabase, not the key itself |
| `NEXT_PUBLIC_BACKEND_URL` | The Railway backend URL | This is the public URL of the API |

> **Critical:** The Supabase `service_role` key (which bypasses RLS) is **never** used in the frontend. It only lives in the backend's `.env` on Railway. The anon key used in the frontend cannot access any data that RLS doesn't permit.

---

## 5.4 Auth Architecture — Two Layers of Protection

The application has **two independent layers of auth protection**, each catching a different attack vector:

### Layer 1 — Server-Side Middleware (`middleware.js`)

This runs on the **Vercel Edge** — before any page is even rendered. It checks if the user has a valid Supabase session stored in their cookies:

```javascript
// middleware.js — simplified logic
import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'

export async function middleware(req) {
    const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        cookies: { ... }  // reads cookies from the Request object
    })

    const { data: { session } } = await supabase.auth.getSession()

    // If no session and trying to access a protected route → redirect to login
    if (!session && !req.nextUrl.pathname.startsWith('/login')) {
        return NextResponse.redirect(new URL('/login', req.url))
    }

    return NextResponse.next()
}
```

**What this protects against:** A user trying to type `/case/EX332661` directly in the URL bar without being logged in. The middleware intercepts the request at the Edge (before any code runs), checks the Supabase session cookie, and immediately redirects to `/login` if there's no valid session.

**Why this matters:** Without middleware, Next.js would serve the page HTML/JS bundle to anyone — even unauthenticated users — and only the client-side check would catch them. With middleware, the page never even renders.

### Layer 2 — Client-Side Hook (`useAuth()` in `lib/auth.js`)

Every protected page calls `const { user, loading } = useAuth()`. This hook:

1. Calls `supabase.auth.getSession()` on mount to check the current session
2. If no session → calls `router.push('/login')` immediately
3. Subscribes to `supabase.auth.onAuthStateChange()` — if the user logs out in another tab, this fires and triggers a redirect automatically
4. Returns `user` (the Supabase user object) and `loading` (boolean — true while the session check is in progress)

**Why both layers?** Middleware covers the case where no page JS has run yet. The `useAuth()` hook covers the case where the session expires mid-session, or where the middleware check had a momentary failure.

```
Request → /case/EX332661
     │
     ▼
middleware.js (Edge, server-side)
     ├── Session cookie valid? → continue
     └── No session? → redirect /login (page never renders)
     │
     ▼
page.js renders, useAuth() fires
     ├── Session valid? → fetch case data, show page
     └── No session? → router.push('/login') (second-line defence)
```

---

## 5.5 Auth Helper Library — `lib/`

### `lib/supabase.js`

A singleton Supabase browser client. The `createBrowserClient` function (from `@supabase/ssr`) creates a client that stores the session in **cookies** rather than localStorage. Cookies are necessary so that the server-side `middleware.js` can read the session (server code cannot access localStorage — that's browser-only).

```javascript
import { createBrowserClient } from '@supabase/ssr'

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)
```

This single `supabase` object is imported by `auth.js`, the login page, and the sign-out handler.

### `lib/auth.js`

Two exports:

**`useAuth()` hook:** Already described above. Every protected page begins with:
```javascript
const { user, loading } = useAuth()
if (authLoading) return <LoadingSpinner />
```

**`getToken()` async function:** Returns the current JWT access token string. Called by `apiFetch()` before every backend request.

```javascript
export async function getToken() {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}
```

### `lib/api.js`

The single authenticated fetch wrapper used by every page for every backend call:

```javascript
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL

export async function apiFetch(path, options = {}) {
  const token = await getToken()

  const defaultHeaders = {
    'ngrok-skip-browser-warning': 'true',       // ignored in production, needed for local ngrok tunnels
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  }

  const mergedHeaders = {
    ...defaultHeaders,
    ...(options.headers || {}),      // caller headers take precedence (e.g. Content-Type: application/json)
  }

  return fetch(`${BACKEND}${path}`, {
    ...options,
    headers: mergedHeaders,
  })
}
```

**Why not set `Content-Type: application/json` by default?** When uploading files, the body is a `FormData` object. If `Content-Type` is set manually for FormData, the `boundary` parameter (which the browser appends automatically) is missing, causing the server to reject the request. So `apiFetch` never sets `Content-Type` — the caller adds it only for JSON requests.

**Usage patterns throughout the codebase:**

```javascript
// GET with no body
const res = await apiFetch('/cases')

// POST with JSON body
const res = await apiFetch('/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question, history, current_document })
})

// POST with file upload (FormData — no Content-Type needed)
const formData = new FormData()
formData.append('file', pdfFile)
const res = await apiFetch(`/upload-pdf?title_number=${titleNumber}`, {
  method: 'POST',
  body: formData
})

// DELETE
const res = await apiFetch(`/cases/${titleNumber}/documents/${docId}`, {
  method: 'DELETE'
})
```

---

## 5.6 Routing — App Router Structure

Next.js App Router maps folder names directly to URL routes:

| URL | File | Page |
|---|---|---|
| `/` | `app/page.js` | Dashboard — lists all cases |
| `/login` | `app/login/page.js` | Email/password login form |
| `/case/EX332661` | `app/case/[titleNumber]/page.js` | Case Dashboard for case EX332661 |
| `/case/EX332661/chatbot` | `app/case/[titleNumber]/chatbot/page.js` | AI Chatbot |
| `/case/EX332661/title-report` | `app/case/[titleNumber]/title-report/page.js` | Title Report |
| `/case/EX332661/title-check` | `app/case/[titleNumber]/title-check/page.js` | Title Check |
| `/case/EX332661/extract` | `app/case/[titleNumber]/extract/page.js` | Smart Extract |
| `/case/EX332661/form-filler` | `app/case/[titleNumber]/form-filler/page.js` | Form Auto-Filler |
| `/case/EX332661/upload` | `app/case/[titleNumber]/upload/page.js` | Upload Document |

The `[titleNumber]` folder uses square brackets — Next.js dynamic routing. Any case title number in the URL is captured and accessible in the component via:
```javascript
const { titleNumber } = useParams()
```

---

## 5.7 Security Headers — `next.config.mjs`

The `next.config.mjs` file applies HTTP security headers to every page response. These are enforced at the Vercel CDN level:

| Header | Value | Purpose |
|---|---|---|
| `Content-Security-Policy` | Restricts which origins can load scripts, frames, and resources | Prevents XSS and clickjacking |
| `X-Frame-Options` | `SAMEORIGIN` | Prevents the app from being embedded in iframes on other sites |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing attacks |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer information sent to other domains |
| `Permissions-Policy` | Restricts camera, microphone, geolocation | Limits browser feature access |

**The CSP includes the Railway backend URL** in `connect-src` so that `apiFetch()` calls are permitted. It also includes `frame-src` for the Railway PDF serving endpoint, so the `<iframe>` PDF viewer can load documents.

---

## 5.8 The Login Page — `app/login/page.js`

The simplest page in the application. No auth check needed (obviously — it's the login page).

**Flow:**
1. User types email + password
2. Clicks Sign In (or presses Enter)
3. `supabase.auth.signInWithPassword({ email, password })` is called
4. If successful → Supabase sets a session cookie → `router.push('/')` redirects to dashboard
5. If failed → Supabase returns an error → displayed as a red message

The session is stored in a cookie (not localStorage) by `createBrowserClient`. This means:
- The cookie is automatically sent with every subsequent request
- The server-side middleware can read it on every page load
- It persists across browser tabs and sessions (until logout or expiry)

---

## 5.9 The Dashboard — `app/page.js`

The root page `/`. Shows all existing cases and lets the user create new ones.

**Auth gate:** Uses `useAuth()`. The `fetchCases()` call is gated behind `useEffect(..., [user])` — it only fires after auth resolves, preventing unauthenticated API calls on page load.

### Create Case — Two Paths

**Path 1 — ZIP upload:** The user provides a title number AND uploads a `.zip` file (a full contract pack). The frontend sends the ZIP to `POST /upload-zip` with the title number as a query parameter. The backend extracts all PDFs, OCRs them, and creates the case — all in one call. The UI shows "Processing Case..." while waiting.

**Path 2 — Empty case:** The user provides only a title number, no ZIP. The frontend calls `POST /cases` to create an empty case. Documents can be uploaded later via the Upload tool.

Both paths use `apiFetch()` so the request is always authenticated.

### Cases List

After creation (or on initial load), the cases list is fetched from `GET /cases`. Each case row shows:
- Title number (bold)
- Created date (formatted for UK locale `en-GB`)
- Click anywhere on the row → `router.push(/case/${titleNumber})`

---

## 5.10 The Case Dashboard — `app/case/[titleNumber]/page.js`

The landing page for every individual case. Instead of combining all tools on one page (the original v1 design, now commented out at the top of the file), the current design shows a **tool selection grid** — each tool navigates to its own dedicated page.

### Tool Cards

The 8 tool cards are defined as a data array `tools[]`. Each entry has:
- `id` — unique string key
- `title` — display name
- `description` — one-line explanation shown on the card
- `icon` — emoji
- `path` — the URL to navigate to
- `available` — boolean (false shows a "Coming soon" badge and disables click)
- `color` — one of 8 colour keys

**Currently available tools:**

| Tool | Color | Status |
|---|---|---|
| AI Assistant (Chatbot) | Blue | ✅ Live |
| Title Report | Indigo | ✅ Live |
| Title Check | Orange | ✅ Live |
| Smart Extract | Purple | ✅ Live |
| Form Auto-Filler | Teal | ✅ Live |
| Letter Generator | Green | ⏳ Coming Soon |
| Key Dates | Amber | ⏳ Coming Soon |
| Completion Statement | Emerald | ⏳ Coming Soon |

### Adding a New Tool

To add a new tool to the grid:
1. Add an entry to the `tools[]` array in `app/case/[titleNumber]/page.js`
2. Set `available: false` initially (shows "Coming soon")
3. Create the page at `app/case/[titleNumber]/your-tool/page.js`
4. Set `available: true` when ready

No other code changes needed — the grid renders from the array dynamically.

> **Important Tailwind note:** The `colorMap` object maps colour names to full Tailwind class strings. Tailwind classes **must be written in full** in the source code — you cannot construct them dynamically (e.g. `bg-${color}-50` won't work because Tailwind's build step won't include the class unless it finds the literal string). The `colorMap` guarantees all classes are present as literals.

### Document List Section

Below the tool grid, the page shows all documents currently in the case. Each row has:
- Document type badge (e.g. `OCE`, `LEASE`)
- Filename (truncated)
- Upload date
- Delete button (appears on hover via `group-hover:opacity-100`)

Clicking Delete calls `handleDeleteDocument(docId)` → `DELETE /cases/{titleNumber}/documents/{docId}` → optimistic UI update removes the document from state without re-fetching.

---

## 5.11 The Upload Page — `app/case/[titleNumber]/upload/page.js`

Lets the solicitor add individual documents to an existing case.

**Supported upload:** Single PDF files. The file is validated client-side (extension + MIME type check) before submission.

**Form:** `FormData` with `file` key + `title_number` as query parameter.

**Response:** The backend returns `{pages, total_chunks}` which the frontend shows as a success message: "Processed 32 pages, 58 chunks indexed."

After a successful upload, the page does **not** auto-navigate away — the solicitor may want to upload multiple files sequentially.

---

## 5.12 State Management Philosophy

There is **no global state management** (no Redux, no Zustand, no Context). Each page manages its own state locally with `useState` and `useEffect`. Data is fetched fresh when each page mounts.

**Why this works:**
- Cases rarely change during a session (documents are uploaded, not edited)
- Each tool page only needs the data relevant to that tool
- Simple `useState` is sufficient at this scale
- Adding global state was consciously avoided to keep the codebase approachable for new developers

**Data flow pattern on every tool page:**
```
1. useAuth() → gate on user
2. useParams() → get titleNumber from URL
3. useEffect([user]) → fetch case data once auth resolves
4. Local state for tool-specific data (e.g. AI results, selected docs)
5. Event handlers call apiFetch() and update local state
```

---

*Next: Chapter 6 — Frontend Tool Pages (UI)*
