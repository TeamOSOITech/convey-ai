# title_check.py — AI-assisted Title Check & Enquiry Generation Tool
#
# Architecture (Global Rule Pool):
#   All rules from the firm's Title Check Checklist are stored as a single flat list
#   in GLOBAL_RULE_POOL below. There are NO form-specific silos (TA6/TA10/TA13).
#
# Pipeline (per document):
#   1. get_all_chunks_text()          → reconstruct full document text from ChromaDB chunks
#   2. classify_document()            → identify form type for context only (not for rule selection)
#   3. evaluate_document_against_rules() → Gemini reads the document + ALL rules simultaneously
#                                          Returns a JSON list of which rules are triggered and why
#   4. fetch_enquiry_template()       → for each triggered code, fetch template from ChromaDB
#   5. personalise_draft()            → Gemini fills any placeholders using seller's specific details
#   6. run_title_check()              → orchestrates the pipeline and returns findings for the UI

import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv
from embeddings import case_collection, format_collection

load_dotenv()

# ── Gemini Setup ──────────────────────────────────────────────────────────────
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY missing from environment.")

genai.configure(api_key=api_key.strip())

try:
    available_models = [
        m.name for m in genai.list_models()
        if 'generateContent' in m.supported_generation_methods
    ]
    # Use Flash-Lite — sufficient for form analysis; keeps cost low
    model_name = next(
        (m for m in available_models if '3.1-flash-lite' in m),
        'gemini-3.1-flash-lite'
    )
    print(f"[TitleCheck] Using model: {model_name}")
except Exception as e:
    print(f"[TitleCheck] Model list failed, falling back. Error: {e}")
    model_name = 'gemini-3.1-flash-lite'

gemini_model = genai.GenerativeModel(model_name)


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

def evaluate_document_against_rules(full_text: str, form_type: str, filename: str) -> list:
    """
    Sends the full document text AND the entire GLOBAL_RULE_POOL to Gemini in a
    single prompt. Gemini evaluates the document holistically and identifies which
    rules from the pool are triggered by what it finds in the document.

    No rules are pre-filtered by form type — Gemini sees ALL rules and picks the
    ones that apply. This means if a TA6 also has contract information, the
    CONTRACT rules will be evaluated too.

    Returns a list of triggered findings:
    [
      {
        "enquiry_code": "E11",
        "reason": "The Property Information Form has not been signed — the signature box on page 3 is blank.",
        "evidence": "Signature box on page 3 is empty."
      },
      ...
    ]
    """

    prompt = f"""You are a UK conveyancing solicitor conducting a formal title check on an OCR-scanned document.

IMPORTANT — OCR LIMITATIONS:
This document was scanned and processed through OCR software. As a result:
- Ticked checkboxes may appear as: ✓, ✗, X, ■, □, [X], [✓], filled characters, or completely garbled text
- Unticked checkboxes may appear as empty boxes, blank spaces, or missing entirely
- Handwritten signatures or dates may appear as garbled characters, smudged text, or blank areas
- Some sections may be partially illegible or show OCR artefacts
You must use CONTEXTUAL REASONING — look at surrounding text, form structure, and what is ABSENT
rather than relying on clean tick mark symbols. For example, if a signature line shows no legible name
or date, treat it as unsigned.

You have been given:
1. A scanned legal document (OCR text): {filename} — classified as: {form_type}
2. A complete list of rules from the firm's Title Check Checklist

Your task:
- Read through the document carefully, accounting for OCR limitations.
- For each rule in the checklist, determine whether the document triggers that rule.
- A rule is triggered when the document shows a problem, missing item, or condition that matches the rule description.
- Do NOT trigger a rule if the document clearly shows the condition is satisfied.
- Do NOT trigger rules that are clearly irrelevant to this type of document.
- When uncertain due to poor OCR quality, lean towards triggering the rule (the solicitor will verify).

IMPORTANT: Return ONLY a valid JSON array (no markdown, no explanation).
Each triggered rule must be an object with exactly these three keys:
- "enquiry_code": the code string from the rule (e.g. "E11")
- "reason": a single sentence explaining why this specific rule was triggered, referencing what you saw (or didn't see) in the document
- "evidence": a short quote or specific detail from the document that supports the trigger — if the trigger is based on an ABSENCE (e.g. blank signature field), describe what is missing

If NO rules are triggered, return an empty array: []

=== CHECKLIST RULES ===
{GLOBAL_RULE_POOL}

=== DOCUMENT TEXT ===
{full_text}"""

    try:
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps output in them
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        triggered = json.loads(raw)

        # Validate structure — ensure we have a list of dicts with required keys
        validated = []
        for item in triggered:
            if isinstance(item, dict) and "enquiry_code" in item:
                validated.append({
                    "enquiry_code": str(item.get("enquiry_code", "")).strip(),
                    "reason":       str(item.get("reason", "")).strip(),
                    "evidence":     str(item.get("evidence", "")).strip()
                })

        print(f"[TitleCheck] Gemini triggered {len(validated)} rules from global pool")
        return validated

    except json.JSONDecodeError as e:
        print(f"[TitleCheck] JSON parse error: {e}")
        print(f"[TitleCheck] Raw Gemini output (first 500 chars): {raw[:500]}")
        return []
    except Exception as e:
        print(f"[TitleCheck] evaluate_document_against_rules failed: {e}")
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
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[TitleCheck] Personalisation failed: {e}")
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
      1. Reconstruct full document text from ChromaDB chunks
      2. Classify document type (context only — does not restrict rules evaluated)
      3. Send full text + GLOBAL_RULE_POOL to Gemini — Gemini identifies triggered rules
      4. For each triggered rule: fetch template from ChromaDB + personalise with Gemini
      5. Return structured findings for the frontend Review Board

    Returns:
    {
      "form_type": "TA6",
      "filename": "ta6.pdf",
      "findings": [
        {
          "enquiry_code": "E11",
          "topic": "Property Information Form — not signed and dated",
          "reason": "The form has not been signed — the signature box is blank.",
          "evidence": "Signature box on page 3 is empty.",
          "draft": "We note that the Property Information Form has not been...",
          "status": "pending"
        },
        ...
      ]
    }
    """
    print(f"[TitleCheck] Starting check for '{filename}' in case {title_number}")

    # Step 1: Reconstruct full text from ChromaDB chunks
    full_text = get_all_chunks_text(title_number, filename)
    if not full_text:
        return {
            "error": (
                f"No text found in ChromaDB for '{filename}'. "
                f"Please ensure the document has been uploaded and processed correctly."
            )
        }

    # Step 2: Classify for context labelling only
    form_type = classify_document(full_text, filename)
    print(f"[TitleCheck] Document classified as: {form_type}")

    # Step 3: Gemini evaluates document against the full GLOBAL_RULE_POOL
    triggered = evaluate_document_against_rules(full_text, form_type, filename)

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
            "evidence":     evidence,   # shown in the Review Board as the "Why triggered" detail
            "draft":        draft,
            "status":       "pending"   # frontend sets to "approved" / "edited" / "discarded"
        })

    print(f"[TitleCheck] Pipeline complete. {len(findings)} findings returned.")

    return {
        "form_type": form_type,
        "filename":  filename,
        "findings":  findings
    }
