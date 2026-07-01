# routes/form_filler.py — Form Auto-Filler endpoint
#
# Extracts the data needed to fill a specific legal form (TR1, etc.)
# from a set of case documents. Returns a structured JSON object with one
# key per panel of the form, ready to be displayed in the Form Filler UI.
#
# To add a new form type: add a new key to FORM_PROMPTS with the matching prompt.

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from embeddings import case_collection
from auth_utils import require_auth

router = APIRouter()


# ── Prompt templates per supported form type ───────────────────────────────────
# Each prompt instructs Gemini to return a JSON object with panel keys.
# Keep prompts specific and structured — Gemini must return valid JSON only.

FORM_PROMPTS = {
    "TR1": """You are a highly experienced UK conveyancing solicitor.
You are reading a set of case documents in order to complete a TR1 (Transfer of Whole of Registered Title) form.

Extract ONLY the information that can be found in the provided documents. For any panel where the information is not present, return exactly: "[Not found in documents]"

Return your answer as a valid JSON object with exactly these keys. Do not add any text outside the JSON block:

{
  "panel_1": "The title number(s) of the property (e.g. ABS12345)",
  "panel_2": "The full property description/address as it appears on the title register",
  "panel_3": "The completion/transfer date (leave blank if not yet agreed)",
  "panel_4": "Full legal name(s) of the transferor (seller). Include company number if a company.",
  "panel_5": "Full legal name(s) of the transferee (buyer). Include address as stated in the contract.",
  "panel_6": "The transferee's intended address for service of notices (usually their solicitor's address or the property address after completion)",
  "panel_7": "Title guarantee — state whether 'full title guarantee' or 'limited title guarantee' and any relevant context",
  "panel_8": "The consideration (purchase price) — exact amount in £",
  "panel_9": "Capacity in which transferor transfers — e.g. 'as beneficial owner', 'as personal representative', 'as trustee'",
  "panel_10": "Any additional provisions, covenants, easements, or declarations that should be included (copy relevant clauses from the contract if present)",
  "panel_11": "Declaration of trust — state whether buyers will hold as 'joint tenants' or 'tenants in common' and in what shares if applicable",
  "panel_12": "Execution details — names/capacities of those who will sign (e.g. individual, company, attorney)"
}

DOCUMENTS:
"""
}


class FormExtractRequest(BaseModel):
    title_number: str        # e.g. "EX332661"
    filenames:    List[str]  # list of filenames to read across
    form_type:    str        # e.g. "TR1"


@router.post("/form-extract")
async def form_extract_route(req: FormExtractRequest, _user=Depends(require_auth)):
    """
    Extracts information needed to complete a specific legal form (e.g. TR1)
    from the selected case documents. Returns a structured JSON object with
    one key per panel of the requested form.
    """
    try:
        from title_report import gemini_model
        import json as json_lib

        form_type = req.form_type.upper()
        if form_type not in FORM_PROMPTS:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Form type '{form_type}' is not supported yet."}
            )

        tn = req.title_number.upper()

        # Gather text from ALL selected files
        all_text_parts = []
        for filename in req.filenames:
            results = case_collection.get(
                where={
                    "$and": [
                        {"title_number": {"$eq": tn}},
                        {"source":       {"$eq": filename}}
                    ]
                }
            )
            if not results["ids"]:
                all_text_parts.append(f"[[ {filename} — no content found in database ]]")
                continue

            chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
            chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
            doc_text = "\n\n".join([chunk for chunk, _ in chunks_with_meta])
            all_text_parts.append(f"=== DOCUMENT: {filename} ===\n\n{doc_text}")

        if not all_text_parts:
            return JSONResponse(
                status_code=404,
                content={"detail": "No content found for any of the selected documents."}
            )

        full_text = "\n\n" + ("\n\n" + "─" * 60 + "\n\n").join(all_text_parts)
        prompt    = FORM_PROMPTS[form_type] + full_text

        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON in ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        panels = json_lib.loads(raw)

        return {
            "form_type": form_type,
            "panels":    panels
        }

    except Exception as e:
        print(f"[/form-extract] Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Form extraction failed: {str(e)}"}
        )