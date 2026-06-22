# title_check.py — AI-assisted Title Check & Enquiry Generation Tool
#
# Pipeline (per document):
#   1. classify_document()   → identify form type from text (TA6, TA10, TA13, etc.)
#   2. extract_form_fields() → Gemini reads the OCR text and returns a structured JSON
#                              of checkbox states and free-text notes from the form
#   3. apply_rules_engine()  → hardcoded IF/THEN rules based on your Title Check Checklist
#                              Each rule maps a checkbox state → enquiry code to trigger
#   4. draft_enquiries()     → fetch template text from ChromaDB format_library, weave in
#                              the seller's specific details extracted by Gemini
#   5. run_title_check()     → orchestrates the whole pipeline for one document

import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv
from embeddings import case_collection, format_collection

load_dotenv()

# ── Gemini Setup ──────────────────────────────────────────────────────────────
# Reuse the same Gemini model already configured in title_report.py
# We need the 1M token context window for reading full forms
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY missing from environment.")

genai.configure(api_key=api_key.strip())

try:
    available_models = [
        m.name for m in genai.list_models()
        if 'generateContent' in m.supported_generation_methods
    ]
    # Use the Flash-Lite model — sufficient for form extraction and cheap
    model_name = next(
        (m for m in available_models if '3.1-flash-lite' in m),
        'gemini-3.1-flash-lite'
    )
    print(f"[TitleCheck] Using model: {model_name}")
except Exception as e:
    print(f"[TitleCheck] Model list failed, falling back. Error: {e}")
    model_name = 'gemini-3.1-flash-lite'

gemini_model = genai.GenerativeModel(model_name)


# ── Document Type Keywords ────────────────────────────────────────────────────
# Used by classify_document() to identify which type of form was uploaded
FORM_KEYWORDS = {
    "TA6":  ["property information form", "ta6", "seller's property information"],
    "TA10": ["fittings and contents", "ta10", "fixtures and fittings"],
    "TA13": ["completion information", "ta13", "code for completion", "undertaking"],
}


def classify_document(full_text: str, filename: str) -> str:
    """
    Identifies the form type from the OCR text and filename.
    Returns one of: "TA6", "TA10", "TA13", or "UNKNOWN".
    Checks filename first (fastest), then first 1000 chars of text.
    """
    # Check filename first — most reliable signal
    fname_lower = filename.lower()
    for form_type, keywords in FORM_KEYWORDS.items():
        if any(kw in fname_lower for kw in keywords):
            return form_type

    # Fall back to scanning the top of the document text
    header_text = full_text[:1000].lower()
    for form_type, keywords in FORM_KEYWORDS.items():
        if any(kw in header_text for kw in keywords):
            return form_type

    return "UNKNOWN"


def extract_form_fields(full_text: str, form_type: str) -> dict:
    """
    Sends the OCR text of a form to Gemini and asks it to return a structured
    JSON object containing:
      - The state of every checkbox question relevant to our Rules Engine
      - Any free-text detail notes the seller has written in answer boxes

    The prompt is form-specific so Gemini knows exactly what to look for.
    Returns a dict of field_key → value. Example:
      {
        "signed_and_dated": true,
        "form_date": "12 March 2024",
        "all_sections_completed": true,
        "building_works_carried_out": true,
        "building_works_details": "Extension built in 2019, no planning permission obtained.",
        "windows_replaced": false,
        "epc_supplied": true,
        "epc_expiry_date": "2026",
        ...
      }
    If extraction fails, returns an empty dict and we fallback gracefully.
    """

    # Build a form-specific extraction prompt
    if form_type == "TA6":
        prompt = f"""You are reading an OCR-scanned TA6 Property Information Form.
Your job is to extract FACTS ONLY from the form text. Do NOT guess or infer.
Look for ticked checkboxes (Yes/No), dates, and any text written in "give details" boxes.

Return ONLY a valid JSON object (no markdown, no explanation) with these exact keys:
{{
  "signed_and_dated": true/false,
  "form_date": "date string or null",
  "all_sections_completed": true/false,
  "missing_sections": "list any incomplete sections or null",
  "all_pages_present": true/false,
  "documents_referred_to_missing": true/false,
  "missing_documents_details": "details or null",
  "epc_supplied": true/false,
  "epc_expired": true/false,
  "epc_expiry_date": "date or null",
  "occupiers_present": true/false,
  "occupiers_names": "names or null",
  "tenants_present": true/false,
  "parking_permit_required": true/false,
  "building_works_carried_out": true/false,
  "building_works_details": "details including dates or null",
  "windows_replaced": true/false,
  "windows_year": "year or null",
  "boiler_replaced": true/false,
  "boiler_year": "year or null",
  "electrical_works_done": true/false,
  "electrical_works_year": "year or null",
  "cavity_wall_insulation": true/false,
  "alterations_requiring_consent": true/false,
  "alterations_details": "details or null"
}}

FORM TEXT:
{full_text}"""

    elif form_type == "TA10":
        prompt = f"""You are reading an OCR-scanned TA10 Fittings and Contents Form.
Your job is to extract FACTS ONLY. Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "signed_and_dated": true/false,
  "form_date": "date string or null",
  "all_sections_completed": true/false,
  "kitchen_section_complete": true/false,
  "items_offered_for_sale": true/false,
  "items_for_sale_details": "details or null"
}}

FORM TEXT:
{full_text}"""

    elif form_type == "TA13":
        prompt = f"""You are reading an OCR-scanned TA13 Completion Information and Undertakings form.
Your job is to extract FACTS ONLY. Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "code_for_completion_by_post_adopted": true/false,
  "code_adopted_in_full": true/false,
  "charges_details_provided": true/false,
  "charges_match_register": true/false,
  "charges_details": "details of charges listed or null",
  "undertaking_unequivocal": true/false,
  "financial_entries_present": true/false,
  "financial_entries_details": "details or null"
}}

FORM TEXT:
{full_text}"""

    else:
        # For unknown form types, return empty — nothing to check
        return {}

    try:
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps output in them
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        fields = json.loads(raw)
        return fields

    except json.JSONDecodeError as e:
        print(f"[TitleCheck] JSON parse error from Gemini: {e}")
        print(f"[TitleCheck] Raw response was: {raw[:300]}")
        return {}
    except Exception as e:
        print(f"[TitleCheck] Gemini extraction failed: {e}")
        return {}


# ── Rules Engine ──────────────────────────────────────────────────────────────
# This is a hardcoded IF/THEN engine based on your firm's Title Check Checklist.
# The LLM never makes a decision here — only the extracted field values matter.
# Each rule is: (condition_function, enquiry_code, reason_string)
# The reason_string is shown to the solicitor in the Review Board UI.

TA6_RULES = [
    # E11 — PIF not signed and dated
    (
        lambda f: f.get("signed_and_dated") is False,
        "E11",
        "The Property Information Form has not been correctly signed and dated."
    ),
    # E12 — PIF over 6 months old (Gemini extracts the date; we check it here)
    # Note: date comparison is handled by a helper, rule just triggers if flag set
    (
        lambda f: f.get("form_over_6_months") is True,
        "E12",
        "The Property Information Form was completed over 6 months ago."
    ),
    # E2 — Incomplete sections
    (
        lambda f: f.get("all_sections_completed") is False,
        "E2",
        lambda f: f"The seller has not completed the following sections: {f.get('missing_sections', 'unknown sections')}."
    ),
    # E3 — Missing pages
    (
        lambda f: f.get("all_pages_present") is False,
        "E3",
        "Pages appear to be missing from the copy Property Information Form supplied."
    ),
    # E5 — Documents referred to but not supplied
    (
        lambda f: f.get("documents_referred_to_missing") is True,
        "E5",
        lambda f: f"The seller refers to documents in the PIF that were not included. Details: {f.get('missing_documents_details', 'see form')}."
    ),
    # E7 — EPC not supplied
    (
        lambda f: f.get("epc_supplied") is False,
        "E7",
        "No EPC has been supplied and none is available via the online register."
    ),
    # E8 — EPC expired
    (
        lambda f: f.get("epc_supplied") is True and f.get("epc_expired") is True,
        "E8",
        lambda f: f"The EPC supplied has expired (expiry: {f.get('epc_expiry_date', 'unknown')})."
    ),
    # E6 — Parking permit required but no details given
    (
        lambda f: f.get("parking_permit_required") is True,
        "E6",
        "The seller has indicated a parking permit is required but not provided details."
    ),
    # E9 — Occupiers present who need to consent
    (
        lambda f: f.get("occupiers_present") is True,
        "E9",
        lambda f: f"There are occupiers at the property ({f.get('occupiers_names', 'names not specified')}) who will need to confirm vacant possession."
    ),
    # E10 — Tenants who need notice to vacate
    (
        lambda f: f.get("tenants_present") is True,
        "E10",
        "The property appears to be tenanted. Notice to vacate must be confirmed before exchange."
    ),
    # F1 — Building works carried out
    (
        lambda f: f.get("building_works_carried_out") is True,
        "F1",
        lambda f: f"Building works have been carried out: {f.get('building_works_details', 'see form')}. Planning permission and building regulations must be provided."
    ),
    # F3 — Windows replaced, no FENSA certificate
    (
        lambda f: f.get("windows_replaced") is True,
        "F3",
        lambda f: f"Replacement windows/doors installed in {f.get('windows_year', 'unknown year')}. FENSA certificate required."
    ),
    # F3b — Boiler replaced, no Gas Safe certificate
    (
        lambda f: f.get("boiler_replaced") is True,
        "F3b",
        lambda f: f"New boiler/central heating installed in {f.get('boiler_year', 'unknown year')}. Gas Safe certificate required."
    ),
    # F3c — Electrical works done, no certificate
    (
        lambda f: f.get("electrical_works_done") is True,
        "F3c",
        lambda f: f"Electrical works carried out in {f.get('electrical_works_year', 'unknown year')}. Competent Persons Scheme certificate required."
    ),
    # F4 — Cavity wall insulation
    (
        lambda f: f.get("cavity_wall_insulation") is True,
        "F4",
        "Property has cavity wall insulation. Must confirm no structural/damp issues and no ongoing claim."
    ),
]

TA10_RULES = [
    # G1 — FCF not signed and dated
    (
        lambda f: f.get("signed_and_dated") is False,
        "G1",
        "The Fittings and Contents Form has not been correctly signed and dated."
    ),
    # G2 — FCF over 6 months old
    (
        lambda f: f.get("form_over_6_months") is True,
        "G2",
        "The Fittings and Contents Form was completed over 6 months ago."
    ),
    # G3a — Incomplete sections
    (
        lambda f: f.get("all_sections_completed") is False,
        "G3a",
        "The seller has not completed all sections of the Fittings and Contents Form."
    ),
    # G3b — Kitchen section columns incomplete
    (
        lambda f: f.get("kitchen_section_complete") is False,
        "G3b",
        "The seller has not completed all columns in Section 2 of the FCF relating to the kitchen."
    ),
    # G4 — Items offered for sale
    (
        lambda f: f.get("items_offered_for_sale") is True,
        "G4",
        lambda f: f"The seller has offered items for sale: {f.get('items_for_sale_details', 'see form')}. Client instructions required."
    ),
]

TA13_RULES = [
    # C2a — Not prepared to adopt Code for Completion by Post
    (
        lambda f: f.get("code_for_completion_by_post_adopted") is False,
        "C2a",
        "The seller is not prepared to adopt the Code for Completion by Post."
    ),
    # C2b — Not adopted in full
    (
        lambda f: f.get("code_for_completion_by_post_adopted") is True and f.get("code_adopted_in_full") is False,
        "C2b",
        "The seller has not agreed to adopt the Code for Completion by Post in full."
    ),
    # C2c — Charges mismatch
    (
        lambda f: f.get("charges_details_provided") is True and f.get("charges_match_register") is False,
        "C2c",
        lambda f: f"The charge(s) listed in TA13 paragraph 5.1 do not correspond with the Charges Register. Details: {f.get('charges_details', 'see form')}."
    ),
    # C2d — Undertaking not unequivocal
    (
        lambda f: f.get("undertaking_unequivocal") is False,
        "C2d",
        "The undertaking to redeem charges is limited in scope. An unequivocal undertaking is required."
    ),
    # C2e — Financial entries without DS1
    (
        lambda f: f.get("financial_entries_present") is True,
        "C2e",
        lambda f: f"Financial entries noted against the property that will not be removed by DS1: {f.get('financial_entries_details', 'see form')}."
    ),
]

# Map each form type to its rule set
RULES_MAP = {
    "TA6":  TA6_RULES,
    "TA10": TA10_RULES,
    "TA13": TA13_RULES,
}


def apply_rules_engine(fields: dict, form_type: str) -> list:
    """
    Runs the hardcoded Rules Engine against the extracted form fields.
    Returns a list of triggered findings, each containing:
      - enquiry_code: the code from the Format Library (e.g. "E11")
      - reason: a human-readable explanation of why the rule fired
    No LLM involved — pure Python IF/THEN logic.
    """
    rules = RULES_MAP.get(form_type, [])
    triggered = []

    for condition, code, reason in rules:
        try:
            if condition(fields):
                # reason can be a string or a callable (lambda f: ...) for dynamic messages
                resolved_reason = reason(fields) if callable(reason) else reason
                triggered.append({
                    "enquiry_code": code,
                    "reason": resolved_reason
                })
        except Exception as e:
            # Never crash on a bad rule — just skip and log
            print(f"[TitleCheck] Rule for {code} threw: {e}")

    return triggered


def fetch_enquiry_template(code: str) -> dict:
    """
    Fetches the enquiry text and metadata for a given code directly from ChromaDB.
    Uses get() with a known ID rather than a vector search — we know exactly which
    document we want, so this is deterministic and instantaneous.
    Returns {"code", "topic", "text"} or a fallback if not found.
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
                "code": meta.get("code", code),
                "topic": meta.get("topic", ""),
                "text": text
            }
    except Exception as e:
        print(f"[TitleCheck] ChromaDB fetch failed for {code}: {e}")

    # Fallback if template is not found in ChromaDB
    return {
        "code": code,
        "topic": f"Enquiry {code}",
        "text": f"[Template for {code} not found in format library. Please draft manually.]"
    }


def personalise_draft(template_text: str, reason: str, fields: dict, form_type: str) -> str:
    """
    Uses Gemini to weave seller-specific details (from the extracted fields and reason)
    into the generic enquiry template text.
    This is the ONLY place the LLM is used for drafting — the decision to raise the
    enquiry has already been made by the rules engine.
    Returns the personalised draft string.
    """
    # Only use Gemini if the template has placeholders that need filling
    has_placeholders = any(
        marker in template_text
        for marker in ["(insert", "[PLEASE COMPLETE", "XXX", "??", "(name", "(date"]
    )

    if not has_placeholders:
        # Template is already self-contained — no Gemini call needed
        return template_text

    prompt = f"""You are a UK conveyancing solicitor drafting a formal enquiry.
Here is the standard enquiry template:
---
{template_text}
---
Here is the context about why this enquiry is being raised:
{reason}

Here are additional facts extracted from the form:
{json.dumps(fields, indent=2)}

TASK: Fill in any bracketed placeholders like (insert name), (year), (details) etc.
using ONLY the facts provided above. 
If a specific detail is not available in the facts above, write [PLEASE COMPLETE] in its place.
Return ONLY the completed enquiry text. Do not add any preamble or explanation.
Keep the formal legal tone exactly as written in the template."""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[TitleCheck] Personalisation failed: {e}")
        return template_text  # Return raw template if Gemini fails


def get_all_chunks_text(title_number: str, filename: str) -> str:
    """
    Fetches all stored ChromaDB chunks for a specific document and joins them
    into one full-text string. Used to reconstruct the full document text for
    Gemini to read (since we chunk on ingest but need full text for form extraction).
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

    # Sort chunks back into reading order before joining
    paired = list(zip(results["documents"], results["metadatas"]))
    paired.sort(key=lambda x: x[1].get("chunk_index", 0))
    return "\n\n".join(doc for doc, _ in paired)


def run_title_check(filename: str, title_number: str) -> dict:
    """
    Main entry point — orchestrates the full pipeline for one document:
      1. Reconstruct full text from ChromaDB chunks
      2. Classify the document type
      3. Extract form fields using Gemini
      4. Run the hardcoded Rules Engine
      5. Fetch enquiry templates from ChromaDB format_library
      6. Personalise each draft using Gemini where needed
      7. Return structured findings for the frontend Review Board

    Returns:
    {
      "form_type": "TA6",
      "filename": "ta6.pdf",
      "fields": { ...extracted checkbox states... },
      "findings": [
        {
          "enquiry_code": "E11",
          "topic": "Property Information Form not signed and dated",
          "reason": "The Property Information Form has not been...",
          "draft": "We note that the Property Information Form has...",
          "status": "pending"   ← frontend sets this to "approved"/"edited"/"discarded"
        },
        ...
      ]
    }
    """
    print(f"[TitleCheck] Starting check for {filename} in case {title_number}")

    # Step 1: Reconstruct full document text from chunks
    full_text = get_all_chunks_text(title_number, filename)
    if not full_text:
        return {
            "error": f"No text found in ChromaDB for '{filename}'. "
                     f"Please ensure the document has been uploaded and processed."
        }

    # Step 2: Classify document type
    form_type = classify_document(full_text, filename)
    print(f"[TitleCheck] Classified as: {form_type}")

    if form_type == "UNKNOWN":
        return {
            "error": f"Could not identify document type for '{filename}'. "
                     f"Currently supported: TA6, TA10, TA13."
        }

    # Step 3: Extract form fields using Gemini
    fields = extract_form_fields(full_text, form_type)
    print(f"[TitleCheck] Extracted {len(fields)} fields from Gemini")

    # Step 4: Run the Rules Engine — no LLM here, pure IF/THEN
    triggered = apply_rules_engine(fields, form_type)
    print(f"[TitleCheck] Rules engine triggered {len(triggered)} findings")

    # Step 5 + 6: Fetch templates and personalise each draft
    findings = []
    for item in triggered:
        code   = item["enquiry_code"]
        reason = item["reason"]

        # Fetch raw template from ChromaDB
        template = fetch_enquiry_template(code)

        # Personalise the draft with Gemini where placeholders exist
        draft = personalise_draft(template["text"], reason, fields, form_type)

        findings.append({
            "enquiry_code": code,
            "topic":        template["topic"],
            "reason":       reason,
            "draft":        draft,
            "status":       "pending"  # frontend changes this to "approved"/"edited"/"discarded"
        })

    return {
        "form_type":  form_type,
        "filename":   filename,
        "fields":     fields,     # returned so frontend can show evidence tooltips
        "findings":   findings
    }
