# title_check.py — AI-assisted Title Check & Enquiry Generation Tool
#
# Architecture (Global Rule Pool + Gemini Vision):
#   All rules from the firm's Title Check Checklist are stored as a single flat list
#   in GLOBAL_RULE_POOL below. There are NO form-specific silos (TA6/TA10/TA13).
#
# Pipeline (per document):
#   1. resolve_pdf_path()              → find the processed PDF file on disk
#   2. pdf_to_images()                 → render each PDF page to a PIL Image via PyMuPDF
#   3. classify_document()             → identify form type for context labelling only
#   4. evaluate_document_vision()      → send page IMAGES + GLOBAL_RULE_POOL to Gemini
#                                        Gemini visually reads ticked checkboxes like a human
#                                        Returns a JSON list of triggered rules + reasons
#   5. fetch_enquiry_template()        → fetch draft template from ChromaDB by exact code ID
#   6. personalise_draft()             → Gemini fills placeholders with seller-specific details
#   7. run_title_check()               → orchestrates the pipeline, returns findings for the UI
#
# Why Vision instead of OCR text?
#   Standard OCR (ocrmypdf) cannot reliably represent ticked checkboxes as text.
#   A ticked box may appear as a garbled character, a filled square, or nothing at all.
#   Sending the raw page images to Gemini lets it SEE the checkboxes visually,
#   the same way a human solicitor would — eliminating the OCR checkbox problem entirely.

import os
import re
import io
import json
import fitz                          # PyMuPDF — converts PDF pages to images
from PIL import Image
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError
from dotenv import load_dotenv
from embeddings import case_collection, format_collection

load_dotenv()

# ── Gemini Setup & Fallback Mechanism ─────────────────────────────────────────
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY missing from environment.")

genai.configure(api_key=api_key.strip())

# The fallback order requested by the user
FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash" # Safe ultimate fallback just in case the 3.x models are not yet available in the SDK
]

def generate_with_fallback(contents) -> str:
    """
    Attempts to generate content using the preferred model. If a rate limit or 
    quota error occurs, it falls back to the next model in the list.
    """
    last_error = None
    for model_name in FALLBACK_MODELS:
        try:
            print(f"[TitleCheck] Attempting generation with {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(contents)
            print(f"[TitleCheck] Success with {model_name}.")
            return response.text
        except ResourceExhausted as e:
            print(f"[TitleCheck] Rate limit/quota exceeded for {model_name}. Falling back...")
            last_error = e
        except GoogleAPIError as e:
            print(f"[TitleCheck] API error with {model_name}: {e}. Falling back...")
            last_error = e
        except Exception as e:
            # Catch all other errors (like invalid model name if 3.5 doesn't exist yet)
            print(f"[TitleCheck] Unexpected error with {model_name}: {e}. Falling back...")
            last_error = e
            
    # If we get here, all models failed
    print(f"[TitleCheck] CRITICAL: All models in fallback list failed. Last error: {last_error}")
    raise Exception(f"All fallback models failed. Last error: {last_error}")


# ── File Path Resolution ──────────────────────────────────────────────────────
# Processed PDFs are stored at {DATA_DIR}/processed_pdfs/{filename}
# DATA_DIR defaults to "./data" locally and is set to "/app/data" on Railway
DATA_DIR = os.getenv("DATA_DIR", "./data")

def resolve_pdf_path(filename: str) -> str:
    """
    Returns the absolute path to the processed PDF file on disk.
    Converts the original filename to the cleaned '_ocr.pdf' format used by the backend.
    Returns None if the file does not exist (triggers text fallback).
    """
    # Replicate the make_clean_filename logic from main.py to avoid circular imports
    cleaned = filename.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "")
    if cleaned.endswith(".PDF"):
        cleaned = cleaned[:-4] + "_ocr.pdf"
    elif cleaned.endswith(".pdf"):
        cleaned = cleaned[:-4] + "_ocr.pdf"

    path = os.path.join(DATA_DIR, "processed_pdfs", cleaned)
    return path if os.path.exists(path) else None


# ── PDF to Images ─────────────────────────────────────────────────────────────

def pdf_to_images(pdf_path: str, dpi: int = 120, max_pages: int = 40) -> list:
    """
    Renders each page of a PDF as a PIL Image using PyMuPDF.

    dpi=120 is sufficient for Gemini to read checkbox states and handwriting
    without generating unnecessarily large image payloads.

    max_pages=40 is a safety cap — TA6/TA10/TA13 forms are typically 5–16 pages.
    Returns a list of PIL Image objects, one per page.
    """
    doc = fitz.open(pdf_path)
    images = []
    scale = dpi / 72.0          # PyMuPDF default is 72 DPI
    mat = fitz.Matrix(scale, scale)

    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        images.append(img)

    doc.close()
    print(f"[TitleCheck] Rendered {len(images)} page image(s) from PDF")
    return images


# ── Global Rule Pool ──────────────────────────────────────────────────────────
# This is the single source of truth for ALL checklist rules.
# It is a flat list — NOT split by form type. The LLM evaluates the uploaded
# document against this entire pool simultaneously.
#
# Each rule follows the format:
#   CODE | TRIGGER CONDITION (when to raise this enquiry)
#
# To add a new rule: simply append a new line to this string. No code changes needed.
# To edit a rule: update the description here. Nothing else needs to change.
#
# Source: Your firm's "TITLE CHECK CHECKLIST — FREEHOLD PROPERTY" PDF.

GLOBAL_RULE_POOL = """
A1  | Trigger if the freehold title absolute is not confirmed in the title register.
A2a | Trigger if the property description in the title register does not match the contract plan.
A2b | Trigger if the title plan is unclear, indecipherable, or missing from the official copies.
A2c | Trigger if there is no filed plan and the description is only by verbal description.
A2d | Trigger if the title plan does not include areas referred to in the register (e.g. garage, parking).
A2e | Trigger if there is a discrepancy between the contract plan and the title plan boundaries.
A2f | Trigger if the property address differs between the contract and the title register.
A3  | Trigger if the title register contains any adverse entries that have not been explained.
A4  | Trigger if any entries on the title register are not referred to in the contract.
A5  | Trigger if there are overriding interests that have not been disclosed.
A6a | Trigger if the register refers to a document and a copy has not been supplied.
A6b | Trigger if the documents supplied appear to be incomplete or illegible.
A7  | Trigger if the title register shows a restriction that will not be complied with on completion.
A8  | Trigger if there are any cautions, inhibitions or notices on the title that have not been explained.
A9  | Trigger if the seller is not the registered proprietor and no explanation has been given.
B1  | Trigger if any search results disclose matters that require further enquiry or explanation.
B2  | Trigger if any required searches (local, drainage, environmental) have not been provided.
B3  | Trigger if search results have expired or are approaching expiry.
C1  | Trigger if the TA13 Completion Information Form has not been included in the contract pack.
C2a | Trigger if the seller refuses to adopt the Code for Completion by Post (paragraph 3.2 of TA13).
C2b | Trigger if the seller has agreed to adopt the Code for Completion by Post but not in full.
C2c | Trigger if the charges listed in paragraph 5.1 of the TA13 do not correspond with the Charges Register.
C2d | Trigger if the seller's undertaking to redeem charges is limited in scope rather than unequivocal.
C2e | Trigger if there are financial entries against the property that will not be removed by DS1 on completion.
D1  | Trigger if the contract has not been signed by the seller or their authorised representative.
D2  | Trigger if the contract is undated or the date appears to be incorrect.
D3  | Trigger if the purchase price in the contract does not match the agreed price.
D4  | Trigger if the deposit amount in the contract is incorrect or missing.
D5  | Trigger if the completion date is missing from the contract or has already passed.
D6a | Trigger if the property description in the contract does not accurately describe the property being purchased.
D6b | Trigger if the title number in the contract does not match the official copies.
D6c | Trigger if the seller's name in the contract does not match the registered proprietor.
D7  | Trigger if the contract conditions differ materially from the Standard Conditions of Sale and no explanation is given.
D8  | Trigger if there are special conditions in the contract that are unusual, onerous, or have not been explained to the client.
D9  | Trigger if the chattels or fixtures and fittings included in the sale are not clearly defined in the contract.
D10 | Trigger if the title guarantee given in the contract is less than full title guarantee without explanation.
D11 | Trigger if the contract does not address how VAT will be treated on the purchase price.
E1  | Trigger if the Property Information Form (TA6) has not been included in the contract pack at all.
E2  | Trigger if the seller has left one or more sections of the Property Information Form incomplete.
E3  | Trigger if pages appear to be missing from the copy Property Information Form supplied.
E4  | Trigger if the seller has not confirmed whether the form is based on original documents.
E5  | Trigger if the seller refers to documents within the PIF but copies of those documents have not been supplied.
E6  | Trigger if the seller has indicated a parking scheme operates but has not provided the permit details.
E7  | Trigger if no EPC has been supplied and none is available via the online EPC register.
E8  | Trigger if the EPC supplied has expired (EPCs are valid for 10 years).
E9  | Trigger if there are occupiers at the property aged 17 or over who are not a party to the transaction and have not provided consent.
E10 | Trigger if the property is tenanted and notice to vacate has not been confirmed or a copy tenancy agreement has not been provided.
E11 | Trigger if the Property Information Form has not been correctly signed and dated by the seller.
E12 | Trigger if the Property Information Form was completed more than 6 months ago.
F1  | Trigger if building works have been carried out at the property and the seller has not provided planning permission and building regulations completion certificate.
F2a | Trigger if alterations have been made that required listed building consent and it has not been provided.
F2b | Trigger if alterations have been made in a conservation area without the required consent.
F3  | Trigger if replacement windows or doors have been installed and no FENSA certificate or building regulations completion certificate has been provided.
F3b | Trigger if a new boiler or central heating system has been installed and no Gas Safe certificate has been provided.
F3c | Trigger if electrical works have been carried out and no Competent Persons Scheme certificate or building regulations completion certificate has been provided.
F4  | Trigger if the property has cavity wall insulation and no guarantee or warranty has been provided, or if there are known structural or damp issues related to it.
G1  | Trigger if the Fittings and Contents Form (TA10) has not been correctly signed and dated by the seller.
G2  | Trigger if the Fittings and Contents Form was completed more than 6 months ago.
G3a | Trigger if the seller has not completed all sections of the Fittings and Contents Form.
G3b | Trigger if the seller has not completed all columns in Section 2 of the Fittings and Contents Form relating to the kitchen.
G4  | Trigger if the seller has offered any items for sale separately and the price or details have not been agreed with the client.
H1  | Trigger if the mortgage or charge listed on the title register has not been addressed in the contract pack or TA13.
H2  | Trigger if a Help to Buy equity loan or other government scheme charge is registered and no redemption details have been provided.
H3  | Trigger if the seller has indicated there is a second charge and no details or redemption figure have been supplied.
J1  | Trigger if the property is leasehold and the freehold title has not been investigated.
J2  | Trigger if there are chancel repair liability risks that have not been addressed by insurance or indemnity.
J3  | Trigger if there is a flying freehold or other unusual structural arrangement that has not been disclosed or explained.
K1  | Trigger if new build warranties (e.g. NHBC Buildmark) have not been provided for a new build or recently converted property.
K2  | Trigger if the property was built within the last 10 years and no new build warranty or architect's certificate has been provided.
K3  | Trigger if there are covenants in the title that are not addressed by restrictive covenant indemnity insurance.
K4  | Trigger if there are outstanding disputes or complaints about the property that have not been fully resolved and documented.
K5  | Trigger if there are any planning notices, enforcement notices, or local authority matters that have not been explained.
"""


# ── Document Classification ───────────────────────────────────────────────────
# Provides context to Gemini about what kind of document it is reading.
# Classification does NOT restrict which rules are checked — all rules are always evaluated.
FORM_KEYWORDS = {
    "TA6":  ["property information form", "ta6", "seller's property information"],
    "TA10": ["fittings and contents", "ta10", "fixtures and fittings"],
    "TA13": ["completion information", "ta13", "code for completion", "undertaking"],
    "CONTRACT": ["contract for sale", "standard conditions of sale", "the seller", "the buyer"],
    "OCE": ["official copy", "title register", "hm land registry", "registered proprietor"],
}

def classify_document(full_text: str, filename: str) -> str:
    """
    Identifies the form type for context labelling only.
    Does NOT control which rules are applied — all rules are always evaluated.
    Returns e.g. "TA6", "TA10", "CONTRACT", "OCE", or "UNKNOWN".
    """
    fname_lower = filename.lower()
    for form_type, keywords in FORM_KEYWORDS.items():
        if any(kw in fname_lower for kw in keywords):
            return form_type

    header_text = full_text[:1500].lower()
    for form_type, keywords in FORM_KEYWORDS.items():
        if any(kw in header_text for kw in keywords):
            return form_type

    return "UNKNOWN"


# ── Core Evaluation Function ──────────────────────────────────────────────────

def _parse_gemini_json(raw: str, source_label: str) -> list:
    """
    Shared helper: strips markdown fences from Gemini output, parses JSON,
    validates structure, and returns a clean list of findings.
    Called by both the vision and text evaluation functions.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        triggered = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[TitleCheck:{source_label}] JSON parse error: {e}")
        print(f"[TitleCheck:{source_label}] Raw output (first 500 chars): {raw[:500]}")
        return []

    validated = []
    for item in triggered:
        if isinstance(item, dict) and "enquiry_code" in item:
            validated.append({
                "enquiry_code": str(item.get("enquiry_code", "")).strip(),
                "reason":       str(item.get("reason", "")).strip(),
                "evidence":     str(item.get("evidence", "")).strip()
            })

    print(f"[TitleCheck:{source_label}] {len(validated)} rules triggered")
    return validated


def _build_evaluation_prompt(form_type: str, filename: str, extra_instruction: str = "") -> str:
    """
    Returns the common evaluation prompt used by both the vision and text paths.
    extra_instruction is appended before the rules to give mode-specific guidance.
    """
    return f"""You are a UK conveyancing solicitor conducting a formal title check.

Document: {filename} — Form type: {form_type}
{extra_instruction}
Your task:
- Evaluate the document against every rule in the checklist below.
- Trigger a rule only when the document shows a problem, missing item, or condition that matches the rule.
- Do NOT trigger a rule if the document clearly shows the condition is satisfied.
- Do NOT trigger rules that are clearly irrelevant to this type of document.
- If uncertain, lean towards triggering the rule — the solicitor will verify using the PDF viewer.

Return ONLY a valid JSON array (no markdown, no explanation).
Each triggered rule must have exactly these three keys:
- "enquiry_code": the code string (e.g. "E11")
- "reason": one sentence explaining why the rule was triggered, referencing what you observed
- "evidence": a specific detail — a quote, a page reference, or a description of what is absent

If NO rules are triggered, return: []

=== CHECKLIST RULES ===
{GLOBAL_RULE_POOL}
"""


def evaluate_document_vision(page_images: list, form_type: str, filename: str) -> list:
    """
    PRIMARY evaluation path — sends actual PDF page images to Gemini.

    Gemini can visually see ticked checkboxes, handwritten dates, signatures,
    and blank fields exactly as a human solicitor would.
    This completely bypasses the OCR checkbox representation problem.

    page_images: list of PIL Image objects (one per page)
    Returns a list of triggered findings: [{enquiry_code, reason, evidence}, ...]
    """
    vision_instruction = """You are looking at scanned images of a legal form. Each image is one page.
You can see the actual checkboxes, tick marks, handwriting, and signatures visually.
Look carefully at each page for:
- Ticked boxes (may appear as ✓, ✗, X, a filled square, or a handwritten mark inside a box)
- Unticked or empty boxes (blank squares with no mark inside)
- Signature fields (look for a handwritten name or whether the line is blank)
- Date fields (look for a written date or whether the field is empty)
- "Give details" text boxes (check whether they contain written text or are blank)

"""
    prompt_text = _build_evaluation_prompt(form_type, filename, vision_instruction)

    try:
        # Pass text prompt + all page images as a single content list
        content_parts = [prompt_text] + page_images
        response_text = generate_with_fallback(content_parts)
        return _parse_gemini_json(response_text, "vision")
    except Exception as e:
        print(f"[TitleCheck:vision] Evaluation failed after fallbacks: {e}")
        return []


def evaluate_document_text(full_text: str, form_type: str, filename: str) -> list:
    """
    FALLBACK evaluation path — used when the PDF file is not found on disk.
    Sends the OCR text to Gemini with instructions to handle garbled checkbox output.
    Less accurate for checkboxes but always available as a safety net.
    """
    text_instruction = """IMPORTANT — OCR LIMITATIONS:
This text was extracted by OCR software from a scanned form. As a result:
- Ticked checkboxes may appear as garbled characters, filled squares, or nothing at all
- Blank signature/date fields may appear as blank lines or be absent from the text
Use contextual reasoning — consider form structure and what is ABSENT, not just what is present.

"""
    prompt = _build_evaluation_prompt(form_type, filename, text_instruction) + f"=== DOCUMENT TEXT ===\n{full_text}"

    try:
        response_text = generate_with_fallback(prompt)
        return _parse_gemini_json(response_text, "text-fallback")
    except Exception as e:
        print(f"[TitleCheck:text-fallback] Evaluation failed after fallbacks: {e}")
        return []


# ── Template Fetching ─────────────────────────────────────────────────────────

def fetch_enquiry_template(code: str) -> dict:
    """
    Fetches the enquiry draft text for a given code directly from ChromaDB.
    Uses get() with the known ID (e.g. "enquiry_E11") — deterministic, no vector search.
    Returns {"code", "topic", "text"} or a safe fallback if the code is not in the library.
    """
    try:
        result = format_collection.get(
            ids=[f"enquiry_{code}"],
            include=["documents", "metadatas"]
        )
        if result["ids"]:
            meta = result["metadatas"][0]
            text = result["documents"][0]
            return {
                "code":  meta.get("code", code),
                "topic": meta.get("topic", f"Enquiry {code}"),
                "text":  text
            }
    except Exception as e:
        print(f"[TitleCheck] ChromaDB fetch failed for {code}: {e}")

    # Fallback — shown to solicitor with a manual drafting prompt
    return {
        "code":  code,
        "topic": f"Enquiry {code}",
        "text":  f"[Template for {code} not found in format library. Please draft this enquiry manually.]"
    }


# ── Draft Personalisation ─────────────────────────────────────────────────────

def personalise_draft(template_text: str, reason: str, evidence: str) -> str:
    """
    Uses Gemini to fill any bracketed placeholders in the enquiry template
    using the specific details observed in the document.

    Only calls Gemini if the template actually has placeholders — skips the
    API call entirely for self-contained templates, saving cost and latency.

    Returns the completed enquiry text ready for the solicitor to review.
    """
    has_placeholders = any(
        marker in template_text
        for marker in ["(insert", "[PLEASE COMPLETE", "XXX", "??", "(name", "(date", "(details"]
    )

    if not has_placeholders:
        # Template is self-contained — no personalisation needed
        return template_text

    prompt = f"""You are a UK conveyancing solicitor completing a formal enquiry letter.

Standard enquiry template:
---
{template_text}
---

Why this enquiry is being raised:
{reason}

Specific evidence from the document:
{evidence}

TASK: Fill in any bracketed placeholders such as (insert name), (date), (details), etc.
Use ONLY the reason and evidence provided above.
If a specific detail is not available, write [PLEASE COMPLETE] in its place.
Return ONLY the completed enquiry text. No preamble, no explanation.
Maintain the formal legal tone of the template exactly."""

    try:
        return generate_with_fallback(prompt).strip()
    except Exception as e:
        print(f"[TitleCheck] Personalisation failed after fallbacks: {e}")
        return template_text  # Return raw template as safe fallback


# ── Text Reconstruction ───────────────────────────────────────────────────────

def get_all_chunks_text(title_number: str, filename: str) -> str:
    """
    Fetches all ChromaDB chunks for a specific document and reconstructs the
    full document text in reading order. We chunk on ingest but need full text
    for the Gemini evaluation step.
    """
    results = case_collection.get(
        where={
            "$and": [
                {"title_number": {"$eq": title_number.upper()}},
                {"source":       {"$eq": filename}}
            ]
        },
        include=["documents", "metadatas"]
    )

    if not results["ids"]:
        return ""

    # Sort by chunk_index to restore reading order before joining
    paired = list(zip(results["documents"], results["metadatas"]))
    paired.sort(key=lambda x: x[1].get("chunk_index", 0))
    return "\n\n".join(doc for doc, _ in paired)


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_title_check(filename: str, title_number: str) -> dict:
    """
    Orchestrates the full Title Check pipeline for one document.

    Steps:
      1. Resolve PDF file path on disk
      2. Classify document type (context only — does not restrict rules evaluated)
      3a. PRIMARY:  Convert PDF pages to images → send to Gemini Vision
      3b. FALLBACK: If PDF not on disk, send OCR text from ChromaDB to Gemini
      4. For each triggered rule: fetch template from ChromaDB + personalise with Gemini
      5. Return structured findings for the frontend Review Board

    Returns:
    {
      "form_type": "TA6",
      "filename": "ta6.pdf",
      "evaluation_mode": "vision" | "text-fallback",
      "findings": [
        {
          "enquiry_code": "E11",
          "topic": "Property Information Form — not signed and dated",
          "reason": "The signature field on page 16 is blank.",
          "evidence": "Page 16 signature box contains no handwritten name or date.",
          "draft": "We note that the Property Information Form has not been...",
          "status": "pending"
        },
        ...
      ]
    }
    """
    print(f"[TitleCheck] Starting check for '{filename}' in case {title_number}")

    # Step 1: Try to find the processed PDF on disk for Vision evaluation
    pdf_path = resolve_pdf_path(filename)

    # Step 2: Classify document type — for context labelling, not rule filtering
    # We still need some text for classification if pdf_path not found
    # so always fetch chunks (used as fallback text anyway)
    full_text = get_all_chunks_text(title_number, filename)
    form_type = classify_document(full_text or "", filename)
    print(f"[TitleCheck] Document classified as: {form_type}")

    # Step 3: Evaluate — Vision primary, text fallback
    if pdf_path:
        print(f"[TitleCheck] PDF found at {pdf_path} — using Gemini Vision")
        page_images = pdf_to_images(pdf_path)
        if page_images:
            triggered = evaluate_document_vision(page_images, form_type, filename)
            evaluation_mode = "vision"
        else:
            # PDF found but rendering failed — fall back to text
            print("[TitleCheck] Image rendering failed — falling back to text")
            triggered = evaluate_document_text(full_text, form_type, filename)
            evaluation_mode = "text-fallback"
    else:
        # PDF not on disk (e.g. Railway restarted and wiped ephemeral storage)
        # Fall back to OCR text from ChromaDB
        if not full_text:
            return {
                "error": (
                    f"Could not find '{filename}' on disk or in ChromaDB. "
                    f"Please re-upload and process the document."
                )
            }
        print("[TitleCheck] PDF not on disk — falling back to OCR text")
        triggered = evaluate_document_text(full_text, form_type, filename)
        evaluation_mode = "text-fallback"

    # Step 4 + 5: Fetch templates and personalise each draft
    findings = []
    for item in triggered:
        code     = item["enquiry_code"]
        reason   = item["reason"]
        evidence = item["evidence"]

        # Fetch enquiry template from ChromaDB format_library by exact ID
        template = fetch_enquiry_template(code)

        # Personalise with Gemini only if template has placeholders
        draft = personalise_draft(template["text"], reason, evidence)

        findings.append({
            "enquiry_code": code,
            "topic":        template["topic"],
            "reason":       reason,
            "evidence":     evidence,
            "draft":        draft,
            "status":       "pending"   # frontend changes to "approved" / "edited" / "discarded"
        })

    print(f"[TitleCheck] Pipeline complete ({evaluation_mode}). {len(findings)} findings returned.")

    return {
        "form_type":        form_type,
        "filename":         filename,
        "evaluation_mode":  evaluation_mode,   # shown in UI so solicitor knows which path ran
        "findings":         findings
    }
