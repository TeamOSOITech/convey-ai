# Convey-AI — Technical Documentation
## Chapter 4: AI Services

---

## 4.1 Overview

The AI services are the core intelligence of Convey-AI. There are three separate AI service modules, each handling a distinct task:

| Module | File | Task |
|---|---|---|
| **Title Report** | `title_report.py` | Reads selected legal documents and extracts structured legal fields (Rights Granted, Rights Reserved, Covenants, Provisions) plus document dates |
| **Title Check** | `title_check.py` | Visually reads form documents (TA6, TA10, TA13) against a checklist of 70+ rules and generates formal enquiry drafts |
| **Chatbot / RAG** | `chatbot.py` | Answers solicitor questions about case documents using Retrieval-Augmented Generation (RAG), with a 3-model fallback chain |

Each module uses different AI strategies suited to its specific problem.

---

## 4.2 Title Report — `title_report.py`

### Purpose
A solicitor selects one or more documents (Transfer deed, Lease, Contract etc.) and the system reads them and extracts the key legal fields a client's Title Report needs. The output is rendered as a structured, section-by-section report in the frontend.

### AI Model Used
**Gemini Flash Lite** — via `google-generativeai`. The model is initialised at module load time:

```python
# Dynamically select the Gemini Flash Lite model available on the account
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
flash_model_name = next((m for m in available_models if '3.1-flash-lite' in m), 'gemini-3.1-flash-lite')
gemini_model = genai.GenerativeModel(flash_model_name)
```

> **Why dynamic model discovery?** Gemini model names change frequently as new versions are released. Listing available models at startup and selecting the best match ensures the code continues to work even as new Lite models are released without any code changes.

### The Title Report Pipeline

For each selected document:

```
1. Fetch ALL ChromaDB chunks for this document
   (uses .get() not .query() — retrieves everything, not top-N)

2. Sort chunks by chunk_index to restore reading order

3. Concatenate all chunks into one full_text string
   (Gemini's 1M token window means we can send the ENTIRE document)

4. Date Extraction
   - OCE (Title Register) → looks for "This official copy shows the entries
     on the register of title on [DATE] at [TIME]"
   - All other documents → looks for execution/signing date
   - Only reads first 3000 characters (dates always appear near the top)

5. Legal Field Extraction (non-OCE documents only)
   - Sends full_text to Gemini with a structured prompt
   - Gemini returns text under four exact headings:
       RIGHTS GRANTED:   PAGE: [N]  [content]
       RIGHTS RESERVED:  PAGE: [N]  [content]
       COVENANTS:        PAGE: [N]  [content]
       PROVISIONS:       PAGE: [N]  [content]
   - The backend parses the headings into separate dict keys
   - PAGE lines are stripped and stored separately as *_page keys
     (used by the frontend to generate PDF deep-link URLs)
```

### The Four Extracted Legal Fields

| Field | What it Contains |
|---|---|
| **Rights Granted** | Rights given TO the buyer — e.g. right of way over the seller's land, rights to use shared drainage |
| **Rights Reserved** | Rights KEPT by the seller — e.g. right to lay pipes over the sold land in future |
| **Covenants** | Binding obligations on the land — e.g. not to build extensions, not to use for business |
| **Provisions** | All other operative clauses — e.g. conditions, declarations, indemnities |

### OCE vs Non-OCE Distinction

An OCE (Official Copy of the Register of Title from HM Land Registry) is treated differently:
- The date extracted is the **search date** (when the copy was issued), not an execution date
- The four legal field extraction is **skipped entirely** — the Title Register does not contain Rights Granted, Covenants etc. in the same way as a Transfer or Lease
- The `is_oce` flag is returned to the frontend so it knows to render the OCE card differently

### The Page Number System

For each extracted legal field, Gemini is also asked to identify the **page number** where that content begins. This is stored as e.g. `rights_granted_page: "7"`. The frontend uses this to construct a PDF deep-link (`/view-pdf/{filename}#page=7`) that opens the PDF viewer directly on the relevant page — the solicitor can instantly verify what the AI extracted.

### Why Gemini Replaced the Old Groq Map-Reduce Approach

The original architecture used Groq (Llama 3) and a complex **Map-Reduce** strategy:
- Split the document into 8,000-character batches
- Send each batch to Groq (MAP step) — extract partial findings
- Send all partial findings to Groq again (REDUCE step) — consolidate into one output

This was necessary because Groq's context window was too small to fit a whole document. The approach required many sequential API calls and was prone to Groq's strict rate limits causing `HTTP 413` errors on large documents.

With Gemini's **1,000,000 token** context window, the entire document — regardless of length — is sent in a single API call. This is faster, simpler, more accurate (no risk of a clause being missed between batches), and eliminates the rate limit problem entirely.

---

## 4.3 Title Check — `title_check.py`

### Purpose
The most sophisticated AI feature. A solicitor selects a TA6, TA10, or TA13 form and the system checks it against a library of 70+ standard UK conveyancing rules. For each triggered rule, it generates a formal enquiry draft personalised to the specific case.

### Why Vision Instead of Text

Standard OCR cannot reliably represent ticked checkboxes. A ticked box (✓) may appear in the OCR output as:
- A garbled character (`â€˜`)
- A filled square (`■`)
- A blank (nothing at all)

The only reliable way to read checkbox states is to look at the **visual image of the page** — exactly how a human solicitor does it. Sending the PDF as images to Gemini Vision bypasses the OCR checkbox problem completely.

### AI Models — Vision Fallback Chain

`title_check.py` has its own separate fallback chain for vision tasks (different from the chatbot fallback):

```python
FALLBACK_MODELS = [
    "gemini-3.5-flash",   # primary — latest vision-capable model
    "gemini-3.0-flash",   # secondary
    "gemini-2.5-flash",   # tertiary
    "gemini-1.5-flash"    # ultimate fallback — always available
]
```

The `generate_with_fallback(contents)` function tries each model in order, catching `ResourceExhausted` (rate limit), `GoogleAPIError`, and any other exception before moving to the next.

### The Global Rule Pool

All 70+ checklist rules are stored as a single flat Python string called `GLOBAL_RULE_POOL`. Each rule follows this format:

```
CODE | TRIGGER CONDITION (when to raise this enquiry)
```

**Example rules:**
```
E11 | Trigger if the Property Information Form has not been correctly signed and dated by the seller.
E12 | Trigger if the Property Information Form was completed more than 6 months ago.
F3b | Trigger if a new boiler or central heating system has been installed and no Gas Safe certificate has been provided.
```

**Rule categories:**
| Prefix | Area |
|---|---|
| A | Title Register / Official Copies |
| B | Search Results |
| C | Completion Information (TA13) |
| D | Contract |
| E | Property Information Form (TA6) |
| F | Building Works / Certificates |
| G | Fittings & Contents (TA10) |
| H | Mortgages / Charges |
| J | Leasehold / Special Title Issues |
| K | New Build / Covenants / Disputes |

> **Maintenance:** To add a new rule, append a new line to `GLOBAL_RULE_POOL`. No other code changes needed. The rule becomes active immediately on the next request.

### The Title Check Pipeline — step by step

```
run_title_check(filename, title_number)
         │
         ├── Step 1: resolve_pdf_path()
         │         Build the cleaned OCR filename (e.g. "TA6_Form_ocr.pdf")
         │         Check if it exists on Railway disk at DATA_DIR/processed_pdfs/
         │
         ├── Step 2: classify_document()
         │         Check filename keywords first (e.g. "ta6" → TA6)
         │         Fall back to first 1500 chars of text content
         │         Returns: "TA6" | "TA10" | "TA13" | "CONTRACT" | "OCE" | "UNKNOWN"
         │         Used for context only — does NOT restrict which rules are checked
         │
         ├── Step 3a (PRIMARY — PDF found): evaluate_document_vision()
         │         pdf_to_images() → render each page at 120 DPI using PyMuPDF
         │         Cap at 40 pages (TA forms are typically 5-16 pages)
         │         Send [prompt_text, image1, image2, ...] to Gemini Vision
         │         Gemini reads checkboxes, signatures, dates VISUALLY
         │         Returns JSON list of triggered rules
         │
         ├── Step 3b (FALLBACK — PDF not on disk):
         │         Use OCR text from ChromaDB instead
         │         evaluate_document_text() warns Gemini about OCR checkbox limitations
         │         Less accurate for checkboxes but always available
         │
         ├── Step 4: For each triggered rule:
         │         fetch_enquiry_template(code)
         │           → Get draft from ChromaDB format_library by exact ID: "enquiry_{CODE}"
         │           → If not found, return "[Template not found. Draft manually]"
         │
         └── Step 5: personalise_draft(template, reason, evidence)
                   → Check if template has placeholders: (insert), [PLEASE COMPLETE], XXX, etc.
                   → If NO placeholders → return template as-is (saves API call)
                   → If YES placeholders → call Gemini to fill them using the
                     specific reason and evidence observed in the document
```

### The Evaluation Prompt Structure

The same prompt skeleton is used for both vision and text paths. The `_build_evaluation_prompt()` function assembles:

1. Role: "You are a UK conveyancing solicitor conducting a formal title check"
2. Document name and classified form type
3. Mode-specific instructions (vision: "look for ticks visually" / text: "account for OCR limitations")
4. Exact instructions on what to return and format
5. The full `GLOBAL_RULE_POOL` with all 70+ rules

Gemini must return **only** a JSON array. Each item in the array has exactly three keys:
```json
[
  {
    "enquiry_code": "E11",
    "reason": "The signature field on page 16 is blank.",
    "evidence": "Page 16 signature box contains no handwritten name or date."
  }
]
```

### What the Frontend Receives

Each finding in the `findings` array is a complete, ready-to-use unit:

```json
{
  "enquiry_code": "E11",
  "topic": "Property Information Form — Signature",
  "reason": "The signature field on page 16 is blank.",
  "evidence": "Page 16 signature box contains no handwritten name or date.",
  "draft": "We note that the Property Information Form has not been signed and dated...",
  "status": "pending"
}
```

The frontend displays each finding as a card in the **Review Board**. The solicitor can:
- **Approve** the enquiry (status → `"approved"`)
- **Edit** the draft text (status → `"edited"`)
- **Discard** the finding if it's not applicable (status → `"discarded"`)

---

## 4.4 Chatbot & RAG — `chatbot.py`

### Purpose
A legal-grade question-and-answer assistant that answers solicitor questions about their case documents. It uses **Retrieval-Augmented Generation (RAG)** — instead of relying on the AI's general training knowledge, it fetches the most relevant chunks from the actual uploaded documents and grounds every answer in those facts.

### The 3-Model Fallback Chain

The chatbot uses three models across two providers. If any model fails (rate limit, quota, timeout, context too long), the next one automatically takes over:

```
Slot 1: gemini-2.5-flash-lite-preview-06-17  [Gemini API]  ← try first
Slot 2: gemini-2.0-flash-lite                [Gemini API]  ← if slot 1 fails
Slot 3: openai/gpt-oss-120b                  [Groq API]    ← if slot 2 fails
```

All three slots are configured in the `_MODELS` list. The `call_llm()` function loops through them:

```python
def call_llm(system_prompt, conversation, user_message):
    errors = {}
    for provider, model_name in _MODELS:
        try:
            if provider == "gemini":
                return _call_gemini(model_name, system_prompt, conversation, user_message)
            else:
                return _call_groq(model_name, system_prompt, conversation, user_message)
        except Exception as err:
            errors[model_name] = str(err)
            print(f"[chatbot] '{model_name}' failed: {err} — trying next...")
    raise RuntimeError(f"All 3 LLM models failed. Errors — {errors}")
```

> **Groq vs Gemini API format:** The two providers have different API interfaces. `_call_gemini()` uses the `google-generativeai` SDK with `start_chat(history=...)`. `_call_groq()` uses the OpenAI-compatible Groq client and formats messages as a flat list with `role: system/user/assistant`. The `call_llm()` dispatcher handles this transparently.

### Context-Weighted RAG

The chatbot uses a tiered document retrieval strategy based on which document the solicitor currently has open in their PDF viewer.

#### Tier 1 — Currently Open Document (Priority)
```python
get_current_document_context(query_embedding, title_number, current_document, max_chunks=5)
```
Searches only within the document the solicitor is currently viewing. Uses a strict `$and` filter with both `title_number` and `source` (filename). Returns up to 5 most semantically relevant chunks, each prefixed with `[Source: filename]`.

#### Tier 2 — All Other Documents (Fallback)
```python
get_diverse_context(query_embedding, title_number, max_per_doc=3, total_max=10, exclude_document=current_document)
```
Searches all other documents in the case. Uses `$ne` (not equal) to exclude the currently open document. To prevent a single large document from dominating all the results, it caps each document at `max_per_doc=3` chunks — this is the **anti-starvation** mechanism. Returns at most 10 chunks total.

#### Why this prioritisation?
A solicitor asking "What is the ground rent?" while looking at a lease should get the answer from the lease first, not from a search result that happened to mention rent.

### The System Prompt

The AI receives a carefully structured system prompt that:
1. Defines the role: "UK conveyancing legal assistant"
2. States the priority rules (open doc first, then fallback)
3. Instructs citation format: `[Source: filename]` and `[InPage Ref.: Heading]`
4. Injects the retrieved context under labelled sections

```
[CURRENTLY OPEN DOCUMENT CONTEXT]
[Source: Lease.pdf]
The annual ground rent shall be ONE HUNDRED POUNDS (£100)...

[OTHER CASE DOCUMENTS CONTEXT]
[Source: Title_Register.pdf]
Registered on 15 March 2001...
```

### Citation Parsing (Source Pills & InPage Ref Pills)

After the AI generates its answer, the backend parses the response text to extract two types of citation:

#### Source Pills
Found via regex: `\[Source:\s*([^\]]+)\]`
- Extracted filenames are cross-checked against `valid_sources` (the set of filenames that actually appeared in the retrieved chunks)
- This **prevents hallucinated filenames** from appearing as clickable buttons — the AI cannot invent a document that wasn't retrieved
- Deduplicated into a list: `["Lease.pdf", "Title_Register.pdf"]`

#### InPage Ref Pills
Found via regex: `\[InPage Ref\.:\s*([^\]]+)\]`
- Each ref is paired with the nearest `[Source:]` citation that appeared **before** it in the text
- This pairing is position-based: the code finds the last `[Source:]` whose character position is less than the `[InPage Ref.:]` position
- The result is a list: `[{"source": "Lease.pdf", "ref": "Restrictive Covenants"}]`
- The frontend uses these to call the `/find-page` endpoint, which converts the phrase to a PDF page number for deep-linking

### Conversation History

Every chatbot request includes the full `history` array of previous turns. The history is passed to `call_llm()` as the `conversation` parameter. For Gemini, this is converted to the `role: user/model` format. For Groq, it uses `role: user/assistant`.

The **last item** in history is always the current question — so `history[:-1]` (all items except the last) is passed as the prior conversation context.

### Enquiry Generation — `raise_enquiry()`

A separate function used by the "Raise Enquiry" button in the chatbot UI. The flow is:

```
1. Encode the issue description as a vector

2. Search format_library for the most semantically similar enquiry template
   (gets the template code, topic, and draft text)

3. Fetch case-specific context using the same Context-Weighted RAG
   (open document first, other documents second)

4. Build a system prompt with:
   - FORMAT LIBRARY TEMPLATE: the standard wording
   - CASE FACTS from open document
   - CASE FACTS from other documents

5. call_llm() generates the personalised enquiry text

6. Return: {type, enquiry_code, topic, enquiry_text, heading, content}
```

The AI is instructed to fill in any placeholders (e.g. `(insert year)`, `(insert name)`) with actual values from the case facts, and flag any it cannot find with `[PLEASE COMPLETE]`.

---

## 4.5 Smart Extract — `routes/smart_extract.py`

### Purpose
A general-purpose extraction tool. The solicitor selects any documents and writes free-form extraction instructions. The AI reads each document and returns structured markdown results.

### How it Works
1. Fetch all ChromaDB chunks for the specified file, sort by `chunk_index`
2. Concatenate into `full_text`
3. Build a prompt: Gemini role + extraction instructions + rules + document text
4. Return the markdown-formatted extraction result

The frontend calls this endpoint **once per file** sequentially (not all files at once). This avoids Vercel's 100-second serverless function timeout — each individual file extraction takes well under 100 seconds.

**Key prompt rules given to Gemini:**
- Format output as markdown (bold headings, bullet points, tables where appropriate)
- If a requested piece of information is not present, write: `*[Not found in this document]*`
- No commentary or waffle — give only what was asked for
- Be precise, quote exact text where useful

---

## 4.6 Form Filler — `routes/form_filler.py`

### Purpose
Extracts the information needed to complete a specific legal form (e.g. TR1 Transfer of Whole) from selected case documents. Returns a structured JSON object with one key per panel of the form.

### FORM_PROMPTS Dictionary

Each supported form type has a detailed prompt stored in the `FORM_PROMPTS` dictionary. For TR1, the prompt instructs Gemini to return exactly 12 keys:

| Panel | Extracts |
|---|---|
| `panel_1` | Title number(s) |
| `panel_2` | Property description/address |
| `panel_3` | Completion/transfer date |
| `panel_4` | Transferor (seller) full legal name |
| `panel_5` | Transferee (buyer) full legal name and address |
| `panel_6` | Transferee's address for service of notices |
| `panel_7` | Title guarantee (full or limited) |
| `panel_8` | Consideration (purchase price in £) |
| `panel_9` | Capacity of transferor |
| `panel_10` | Additional provisions, covenants, easements |
| `panel_11` | Declaration of trust (joint tenants / tenants in common) |
| `panel_12` | Execution details (who will sign) |

If a panel value cannot be found in the documents, Gemini returns: `"[Not found in documents]"`.

### Adding New Form Types

To support a new form type (e.g. AP1, DS1):
1. Add a new key to `FORM_PROMPTS` in `routes/form_filler.py` with a prompt describing what to extract and what JSON keys to return
2. No other code changes needed — the endpoint automatically handles any form type in `FORM_PROMPTS`

### JSON Fence Stripping

Gemini sometimes wraps its JSON response in markdown code fences:
````
```json
{ "panel_1": "..." }
```
````

The code explicitly strips these before calling `json.loads()`:
```python
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
    raw = raw.strip()
panels = json_lib.loads(raw)
```

---

## 4.7 AI Model Summary

| Feature | Module | Primary Model | Fallback(s) | Context Strategy |
|---|---|---|---|---|
| Title Report | `title_report.py` | Gemini Flash Lite (dynamic) | None — single call | Full document in one prompt (1M context) |
| Title Check | `title_check.py` | gemini-3.5-flash (vision) | 3.0-flash → 2.5-flash → 1.5-flash | PDF images sent directly to vision model |
| Chatbot Q&A | `chatbot.py` | gemini-2.5-flash-lite | gemini-2.0-flash-lite → groq/gpt-oss-120b | Context-Weighted RAG (5 open doc + 10 other) |
| Enquiry Generation | `chatbot.py` | (same as chatbot) | (same as chatbot) | Format library template + case RAG |
| Smart Extract | `routes/smart_extract.py` | Gemini Flash Lite (shared) | None | Full document text in one prompt |
| Form Filler | `routes/form_filler.py` | Gemini Flash Lite (shared) | None | All selected docs concatenated |

---

*Next: Chapter 5 — Frontend Architecture & Auth*
