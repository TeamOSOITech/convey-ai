# Convey-AI — Technical Documentation
## Chapter 6: Frontend Tool Pages (UI)

---

## 6.1 Overview

Each tool in Convey-AI lives in its own dedicated page under `/case/[titleNumber]/`. Every tool page follows the same structural pattern:

1. `useAuth()` — gate the page
2. `useParams()` — extract `titleNumber` from the URL
3. `fetchCase()` — load the case and its documents from the backend
4. Tool-specific state and logic
5. Phase-based UI rendering (setup → running → results)

All pages use `ReactMarkdown` with `remarkGfm` to render AI-generated markdown content — headers, bold text, blockquotes, and numbered lists display properly instead of as raw symbols.

---

## 6.2 Chatbot Tool — `/case/[titleNumber]/chatbot`

**File:** [chatbot/page.js](file:///c:/Users/User/OneDrive/Desktop/NP/convey-ai/frontend/app/case/[titleNumber]/chatbot/page.js)

### Layout — Three-Panel Design

```
┌──────────────────────────────────────────────────────────────────┐
│  LEFT PANEL (w-64)  │   MIDDLE PANEL (flex-1)   │  RIGHT (w-96) │
│  Document list      │   Inline PDF viewer        │  AI Chatbot   │
│  + Upload button    │   (iframe)                 │  + Input area │
└──────────────────────────────────────────────────────────────────┘
```

### State

| State variable | Type | Purpose |
|---|---|---|
| `caseData` | object | Case + documents fetched from backend |
| `selectedDoc` | object | The document currently shown in the PDF viewer |
| `pdfPage` | number \| null | The `#page=N` fragment for the PDF iframe |
| `messages` | array | Full conversation history rendered in the right panel |
| `input` | string | Current text in the textarea |
| `loading` | boolean | True while waiting for the AI to respond |

### The PDF iframe and Deep-Linking

The middle panel renders the processed OCR'd PDF inside a native browser `<iframe>`. Chrome's built-in PDF viewer supports the `#page=N` URL fragment to jump to a specific page:

```jsx
<iframe
  key={selectedDoc.file_url + (pdfPage ?? '')}  // ← CRITICAL: key forces re-mount
  src={pdfPage
    ? `${selectedDoc.file_url}#page=${pdfPage}`
    : selectedDoc.file_url
  }
/>
```

> **Why the `key` prop is critical:** React reuses iframe DOM nodes for performance. If you just change `src`, the browser may ignore the change — especially if the base URL is the same and only the fragment changes. By including `pdfPage` in the `key`, React unmounts and remounts a fresh iframe every time the page changes, guaranteeing the browser loads the new fragment.

### Source Document Pills (Blue)

When the AI answers a question, the response includes a `sources` array of filenames that were actually retrieved from ChromaDB. Each filename renders as a blue pill button below the answer. Clicking a pill calls `openSourceDocument(filename)`, which:
- Finds the matching document object in `caseData.documents`
- Sets it as `selectedDoc` (swaps the PDF in the middle panel)
- Sets `pdfPage` to null (opens from page 1)

### InPage Ref Pills (Purple)

The AI may also return a `citations` array of `{source, ref}` objects. Each renders as a purple pill. Clicking one calls `openCitation(filename, ref)`, which:
1. Immediately swaps the PDF viewer to the source document
2. Calls `GET /find-page?title_number=...&filename=...&query=...`
3. Backend fuzzy-searches ChromaDB chunks for the phrase and returns an estimated page number
4. Sets `pdfPage` to that number — the iframe remounts with `#page=N`

### Message Types

| `msg.type` | Background | Contents |
|---|---|---|
| `question` (user) | Blue bubble | Plain text |
| `answer` | Gray bubble | ReactMarkdown + Source Pills + InPage Ref Pills + Copy button |
| `enquiry` | Green bubble | Green code badge + topic label + ReactMarkdown text + Copy button |
| `error` | Red bubble | Plain error message |

### Input Area

Two buttons share the textarea input — both call `sendMessage(type)` with different `type` arguments:
- **Ask Question** → `type = 'question'` → calls `POST /chat`
- **Raise Enquiry** → `type = 'enquiry'` → calls `POST /raise-enquiry`

Both are disabled while `loading` is true or `input` is empty. The full `history` array of all messages is always sent with each request so the AI retains context.

---

## 6.3 Title Report Tool — `/case/[titleNumber]/title-report`

**File:** [title-report/page.js](file:///c:/Users/User/OneDrive/Desktop/NP/convey-ai/frontend/app/case/[titleNumber]/title-report/page.js)

### Layout — Two-Column

```
┌──────────────────────────────────────────────────────────────────┐
│  LEFT (w-72)            │   RIGHT (flex-1)                       │
│  Document selection     │   Generated report cards               │
│  ☑ Select all / Clear   │   One card per document                │
│  ☑ Lease.pdf            │   Date + 4 Legal Fields + Copy buttons │
│  ☑ Transfer.pdf         │                                        │
│  [Generate Report]      │                                        │
└──────────────────────────────────────────────────────────────────┘
```

### Sequential Processing — Anti-Timeout Design

Instead of sending all selected filenames in one API call, the frontend loops and calls `POST /generate-title-report` **once per document**:

```javascript
for (let i = 0; i < selectedFilenames.length; i++) {
  const filename = selectedFilenames[i]
  const res = await apiFetch('/generate-title-report', {
    body: JSON.stringify({ selected_filenames: [filename] })  // ← one file at a time
  })
  liveReport.documents.push(data.documents[0])
  setReport({ ...liveReport })  // ← updates UI live as each document completes
}
```

**Why sequential?** Vercel serverless functions have a **100-second timeout**. A large lease or transfer document can take 30-60 seconds for Gemini to read and extract all four fields. Sending 5 documents in one request would likely timeout. Sequential calls ensure each request completes well within the limit, and the UI updates progressively as each document finishes.

### Live Report Building

The `liveReport` object is updated after each document completes. `setReport({ ...liveReport })` re-renders the right panel with the newly added document card while the others are still processing. The solicitor can read finished documents while waiting for the next.

### Report Card Rendering

Each document produces a card with:
- **Header:** OCE vs Title Document badge, filename, and the extracted date
- **OCE cards:** Show a note ("Rights and covenants are in the title deeds")
- **Non-OCE cards:** Four sections — Rights Granted, Rights Reserved, Covenants, Provisions

Each section includes:
- A **Page badge** (e.g. `Page 7`) if Gemini identified the page number — clicking-ready for manual PDF navigation
- AI-generated content rendered via `ReactMarkdown`
- An individual **Copy** button with 2-second visual `✓ Copied` feedback
- A **Copy Full Report** button at the top assembles all text into one formatted plain-text block

### DOC_TYPE_LABELS

A constant object maps `doc_type` codes to human-readable labels displayed in the selection panel:
```javascript
const DOC_TYPE_LABELS = { OCE: 'Title Register', LEASE: 'Lease', TR1: 'Transfer', ... }
```

---

## 6.4 Title Check Tool — `/case/[titleNumber]/title-check`

**File:** [title-check/page.js](file:///c:/Users/User/OneDrive/Desktop/NP/convey-ai/frontend/app/case/[titleNumber]/title-check/page.js)

### Four-Phase UX State Machine

The entire page is governed by a `phase` state variable with four values:

```
'select'  →  'running'  →  'review'  →  'generate'
```

| Phase | What's shown | What happens |
|---|---|---|
| `select` | Document list, "Run Title Check" button | User picks a TA6/TA10/TA13 |
| `running` | Full-screen spinner with explanation text | Backend pipeline runs |
| `review` | Review Board — one card per finding | User approves, edits, or discards each |
| `generate` | Final compiled report text | Copy to clipboard for use |

### Running Phase

When the user clicks "Run Title Check":
1. `phase` → `'running'`
2. Calls `POST /title-check` with `{title_number, filename}`
3. Backend runs the full pipeline (up to ~60s for large forms with many pages)
4. Returns `{form_type, filename, evaluation_mode, findings}`
5. `phase` → `'review'`, findings loaded into state

The `evaluation_mode` field (`'vision'` or `'text-fallback'`) is displayed as a badge on the Review Board header so the solicitor knows whether Gemini could see the actual images or had to rely on OCR text.

### Review Board

Each finding card shows:
- **Code badge** (e.g. `E11`) + **Topic** (e.g. `Property Info Form — Signature`)
- **Reason** — why the rule was triggered (one sentence from Gemini)
- **Evidence** — specific detail (page, quote, or absent item)
- **Draft** — the personalised enquiry text (editable textarea)
- **Three action buttons:** Approve / Edit / Discard

**Status tracking:**
```javascript
// setFindingStatus changes the status of one finding without touching the others
const setFindingStatus = (index, status) => {
  setFindings(prev => prev.map((f, i) => i === index ? { ...f, status } : f))
}

// updateEditedDraft stores the modified text and auto-marks as 'edited'
const updateEditedDraft = (index, text) => {
  setEditedDrafts(prev => ({ ...prev, [index]: text }))
  setFindingStatus(index, 'edited')
}
```

**Visual status indicators:**
- `pending` → gray border
- `approved` → green left border + green badge
- `edited` → blue left border + blue badge
- `discarded` → gray, faded (content still visible for reference)

### Manual Enquiry Addition

On the Review Board, there is an "Add Enquiry" box where a solicitor can type any enquiry code (e.g. `A1`, `F3b`) and click Add. This calls `GET /formats/{code}` which fetches the standard template from ChromaDB. A new finding card is appended to the board with `status: 'pending'` and `reason: "Manually added by user."` — the solicitor can then edit the draft before approving.

### Generate Phase

Clicking "Generate Final Report" filters `findings` to `status !== 'discarded'` and compiles them into formatted plain text:

```
TITLE CHECK REPORT — EX332661
Document: TA6_Form.pdf | Form Type: TA6

────────────────────────────────────

ENQUIRY E11 — Property Information Form — Signature

Reason: Signature field on page 16 is blank.

ENQUIRY TEXT:
We note that the Property Information Form has not been signed...

────────────────────────────────────

ENQUIRY G1 — Fittings and Contents Form — Signature
...
```

---

## 6.5 Smart Extract Tool — `/case/[titleNumber]/extract`

**File:** [extract/page.js](file:///c:/Users/User/OneDrive/Desktop/NP/convey-ai/frontend/app/case/[titleNumber]/extract/page.js)

### Three-Phase UX

```
'setup'  →  'running'  →  'results'
```

### Layout — Two-Column

```
┌──────────────────────────────────────────────────────────────────┐
│  LEFT (w-72)            │   RIGHT (flex-1)                       │
│  Document selection     │   Quick Templates row                  │
│  ☑ Lease.pdf            │   [Instructions textarea]              │
│  ☑ Title Register.pdf   │   ─────────────────────────────────── │
│  [Run Extraction]       │   Result card per document             │
└──────────────────────────────────────────────────────────────────┘
```

### Quick Templates

Five built-in extraction templates appear as pill buttons above the instructions textarea. Clicking one populates the textarea with a detailed, professionally-worded extraction prompt. The active template is highlighted purple. Clicking "✏️ Custom" clears the textarea for free-form input.

| Template | What it extracts |
|---|---|
| 📅 Key Dates | All dates with context (completion, exchange, offer expiry etc.) |
| 👥 Parties & Roles | All named parties, roles, addresses, reference numbers |
| £ Financial Summary | All monetary amounts with context |
| ⚖️ Restrictions & Obligations | All covenants, easements, restrictions with type and who is bound |
| 🏠 Property Details | Address, title number, tenure, description, boundaries |

### Live Progress Indicator

During extraction, a spinner card shows the **current filename being processed** and `X of Y documents done`. This gives the solicitor real-time feedback since each document takes 10-30 seconds:

```jsx
<p>Extracting from <span className="text-purple-700 font-semibold">{currentFile}</span></p>
<p className="text-xs text-gray-400">{results.length} of {selectedFilenames.length} documents done</p>
```

Result cards appear immediately as each document finishes — the solicitor can read completed results while the next document is still processing.

### Results

Each result card has:
- Green `✓ Extracted` badge (or red `⚠ Error` if the extraction failed)
- Filename header
- Copy button with 2s feedback
- Full ReactMarkdown rendered content (tables, bold, lists, blockquotes)

A **Copy All** button assembles all results into a single formatted text block.

The **← New Extraction** button resets `phase` to `'setup'` and clears results, allowing a new query on the same or different documents without refreshing the page.

---

## 6.6 Form Auto-Filler Tool — `/case/[titleNumber]/form-filler`

**File:** [form-filler/page.js](file:///c:/Users/User/OneDrive/Desktop/NP/convey-ai/frontend/app/case/[titleNumber]/form-filler/page.js)

### Layout — Three-Panel

```
┌──────────────────────────────────────────────────────────────────┐
│  LEFT (source docs) │   MIDDLE (blank form PDF)   │ RIGHT (data) │
│  ☑ Lease.pdf        │   Drop your TR1 PDF here   │  Panel 1:... │
│  ☑ Transfer.pdf     │   ─────────────────────    │  Panel 2:... │
│                     │   [iframe: form PDF]        │  Panel 12:.. │
│  [Fill Form]        │                             │  [Copy]      │
└──────────────────────────────────────────────────────────────────┘
```

### Three Distinct Roles for Each Panel

**Left panel — Source Documents:** The solicitor checks which case documents to use as source material (the Lease, Transfer, OCE etc.). These are the documents ChromaDB will search to fill in the form.

**Middle panel — Blank Form Viewer:** The solicitor drags and drops (or clicks to select) their blank TR1 form PDF from their local PC. This loads into an iframe using a `blob:` URL — the form never leaves the browser, it's only used so the solicitor can visually reference the panel numbers while reading the extracted data.

**Right panel — Extracted Data:** After clicking Fill Form, the AI returns one text block per form panel. Each panel is editable (the solicitor can correct any AI errors) and individually copyable.

### Blob URL Management

The blank form PDF is loaded from the user's local filesystem using the File API:
```javascript
const handleFormFile = (file) => {
  if (formPdfUrl) URL.revokeObjectURL(formPdfUrl)  // ← release old blob to prevent memory leak
  const url = URL.createObjectURL(file)             // ← create blob: URL
  setFormPdfUrl(url)
}

// On unmount: release the blob URL
useEffect(() => {
  return () => { if (formPdfUrl) URL.revokeObjectURL(formPdfUrl) }
}, [formPdfUrl])
```

**Why blob URLs?** The form PDF is on the user's local machine, not on any server. A `blob:` URL allows the browser to display it in the `<iframe>` without any upload. The blob URL is tied to the browser session and automatically invalidated when the page closes — the `URL.revokeObjectURL()` call releases it earlier to free memory when a new file is loaded.

### Drag-and-Drop Upload

The middle panel implements a full drag-and-drop zone:
```javascript
const onDrop = useCallback((e) => {
  e.preventDefault()
  setDragging(false)
  const file = e.dataTransfer.files?.[0]
  if (file) handleFormFile(file)
}, [formPdfUrl])

const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
const onDragLeave = () => setDragging(false)
```

The `dragging` state adds a visual highlight to the drop zone while a file is being dragged over it.

### Form Type Detection

```javascript
function detectFormType(filename) {
  const lower = filename.toLowerCase()
  if (lower.includes('tr1')) return 'TR1'
  return 'TR1'  // default — extend as more forms are supported
}
```

The detected `formType` is sent to `POST /form-extract` so the backend knows which prompt to use from `FORM_PROMPTS`.

### Extraction Call

`POST /form-extract` is called with:
```json
{
  "title_number": "EX332661",
  "form_type": "TR1",
  "filenames": ["Lease.pdf", "Transfer.pdf"]
}
```

The backend returns a JSON object with one key per panel (`panel_1` through `panel_12` for TR1). The right panel renders each one as an editable textarea.

### Panel Navigation

The right panel has a miniature navigation sidebar listing all panel numbers. Clicking a panel number scrolls smoothly to that section using `panelRefs` and `scrollIntoView({ behavior: 'smooth' })`. The `activePanel` state highlights the currently visible panel in the navigation.

### SUPPORTED_FORMS

Form metadata is imported from a separate `forms.js` file in the same directory:
```javascript
import { SUPPORTED_FORMS } from './forms'
```

This keeps the form definitions separate from UI logic. Each entry in `SUPPORTED_FORMS` describes a form type, its panels, and their human-readable labels — making it easy to add new form types without touching the main component.

---

## 6.7 UI Patterns Used Across All Tools

### Breadcrumb Navigation

Every tool page has a consistent breadcrumb:
```
← All Cases / EX332661 / Tool Name
```
Each segment is a clickable link. The last segment is bold and non-clickable (current page).

### ReactMarkdown Rendering

AI-generated content is never shown as raw text. It's always rendered through:
```jsx
<div className="prose prose-sm max-w-none prose-indigo text-gray-800">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
</div>
```

`prose` (Tailwind Typography) adds proper typographic styles to the markdown output — readable heading sizes, spacing between paragraphs, blockquote styling, code blocks, etc. `remarkGfm` enables GitHub Flavoured Markdown — tables, strikethrough, task lists.

### Copy with 2-Second Feedback

All copy buttons use the same pattern:
```javascript
const [copiedField, setCopiedField] = useState(null)

const copyToClipboard = (text, fieldId) => {
  navigator.clipboard.writeText(text)
  setCopiedField(fieldId)
  setTimeout(() => setCopiedField(null), 2000)
}

// In JSX:
{copiedField === fieldId ? '✓ Copied' : 'Copy'}
```

`fieldId` is a unique string per button (e.g. `"0-rights_granted"`, `"doc-2"`) so multiple copy buttons can independently show their confirmation state.

### Sequential API Loop Pattern

All tools that process multiple documents use the same sequential loop:
```javascript
for (const filename of selectedFilenames) {
  setCurrentFile(filename)
  const res = await apiFetch('/endpoint', { body: JSON.stringify({ filename }) })
  const data = await res.json()
  liveResults.push(data)
  setResults([...liveResults])  // ← updates UI with each new result
}
```

This avoids Vercel's timeout, shows live progress, and isolates errors per-document (one failure doesn't abort the whole batch).

### Loading States

All tools show auth/page loading before rendering:
```jsx
if (authLoading || pageLoading) {
  return <div className="flex items-center justify-center min-h-screen bg-gray-50">
    <p className="text-gray-400 text-sm">Loading...</p>
  </div>
}
```

Inline AI operation loading is handled per-tool with spinners, "Thinking..." text, or animated emoji (⚙️ with `animate-pulse`).

---

## 6.8 Tool Feature Comparison

| Feature | Chatbot | Title Report | Title Check | Smart Extract | Form Filler |
|---|---|---|---|---|---|
| Document selection | Single (viewer) | Multi-checkbox | Single | Multi-checkbox | Multi-checkbox |
| Instructions | Textarea (question) | None | None | Custom textarea | None |
| API calls | Per message | Per document | One batch | Per document | One batch |
| Output format | Markdown chat | Structured cards | Review board | Markdown cards | Editable panels |
| Copy support | Per message | Per field + full | Per finding + full | Per doc + all | Per panel |
| Phase system | Messages list | Setup → Live build | 4-phase state machine | Setup → Running → Results | Setup → Results |
| PDF viewer | ✅ Yes (center panel) | ❌ No | ✅ Yes (evidence links) | ❌ No | ✅ Yes (blank form) |

---

*This completes the full six-chapter technical documentation for Convey-AI.*
