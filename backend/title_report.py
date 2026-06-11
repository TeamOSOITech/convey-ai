# title_report.py — generates structured Title Reports from selected case documents
#
# How it works:
#   1. Employee selects documents (OCE, Transfer, Lease etc.) in the UI
#   2. For each selected document, we fetch ALL its chunks from ChromaDB
#   3. We send those chunks to the LLM with targeted extraction prompts
#   4. OCE (Title Register) → date only
#   5. All other docs → date + Rights Granted, Rights Reserved, Covenants, Provisions
#   6. Returns a structured dict the frontend renders as the Title Report

import os
from groq import Groq
from dotenv import load_dotenv
from embeddings import case_collection, model

load_dotenv()

# Initialise Groq LLM client using API key from environment
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Keywords used to identify Title Register (OCE) documents by filename
# OCE docs only get date extraction — the 4 legal fields don't apply to them
OCE_KEYWORDS = ["oce", "official copy", "title register", "official copies", "hmlr"]


def is_oce_document(filename: str) -> bool:
    """
    Returns True if the filename suggests this is a Title Register (OCE) document.
    Uses keyword matching on the lowercase filename.
    """
    filename_lower = filename.lower()
    return any(keyword in filename_lower for keyword in OCE_KEYWORDS)


def extract_date(chunks: list, filename: str) -> str:
    """
    Asks the LLM to find the date of the document from the provided text chunks.
    Returns a date string like "15 March 2024" or "[NOT FOUND]".
    
    We only send the first few chunks since dates appear on the first page.
    max_tokens is very low — we only need a short date string back.
    """
    # Join chunks into a single context block for the LLM
    context = "\n\n".join(chunks)

    prompt = f"""You are a UK conveyancing legal assistant reading OCR-extracted text from a scanned legal document.
Document: {filename}

TASK: Find and return the date of this document.
Look for phrases like "dated [date]", "this deed is made on [date]", "made the [date] day of", or a date on the first page.

RULES:
- Return ONLY the date string. Example: "15 March 2024" or "25th June 2005"
- If multiple dates exist, return the main execution date of the document
- If no date found, return exactly: [NOT FOUND]
- No explanation, no preamble — just the date

DOCUMENT TEXT:
{context}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50  # A date is never more than a few words
    )

    return response.choices[0].message.content.strip()


def extract_legal_fields(chunks: list, filename: str) -> dict:
    """
    Asks the LLM to extract the four standard legal fields from the document:
      - Rights Granted
      - Rights Reserved
      - Covenants
      - Provisions

    Returns a dict with these four keys.
    The LLM is instructed to use exact headings so we can parse the response reliably.
    """
    # Join all chunks — for legal field extraction we need the full document
    context = "\n\n".join(chunks)

    prompt = f"""You are a UK conveyancing legal assistant reading OCR-extracted text from a scanned legal document.
Document: {filename}

TASK: Extract the following four categories of information from this document.
OCR text may be noisy — interpret it intelligently even if formatting is broken.

For each category:
- Extract the actual legal wording as accurately as possible
- Do NOT summarise — use the verbatim text where possible
- If a category is genuinely not present in this document, write: [NOT PRESENT IN THIS DOCUMENT]

You MUST respond using EXACTLY these four headings in this order:

RIGHTS GRANTED:
[extracted text]

RIGHTS RESERVED:
[extracted text]

COVENANTS:
[extracted text]

PROVISIONS:
[extracted text]

DOCUMENT TEXT:
{context}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048  # Legal field text can be long
    )

    raw = response.choices[0].message.content.strip()

    # Parse the LLM response by splitting on the known headings
    # Default to [NOT FOUND] if a heading is missing from the response
    fields = {
        "rights_granted": "[NOT FOUND]",
        "rights_reserved": "[NOT FOUND]",
        "covenants": "[NOT FOUND]",
        "provisions": "[NOT FOUND]"
    }

    # Map each heading string to its dict key
    heading_map = {
        "RIGHTS GRANTED:": "rights_granted",
        "RIGHTS RESERVED:": "rights_reserved",
        "COVENANTS:": "covenants",
        "PROVISIONS:": "provisions"
    }

    headings = list(heading_map.keys())

    for i, heading in enumerate(headings):
        if heading not in raw:
            continue  # Heading missing — keep default [NOT FOUND]

        # Content starts after the heading
        start = raw.index(heading) + len(heading)

        # Content ends at the next heading (or end of string)
        end = len(raw)
        for next_heading in headings[i + 1:]:
            if next_heading in raw:
                candidate = raw.index(next_heading)
                if candidate > start:
                    end = candidate
                    break

        fields[heading_map[heading]] = raw[start:end].strip()

    return fields


def generate_title_report(title_number: str, selected_filenames: list) -> dict:
    """
    Main entry point — generates the full Title Report for a set of selected documents.

    For each selected filename:
      - Fetches all ChromaDB chunks for that document (filtered by title_number + source)
      - Sorts chunks by chunk_index to preserve document reading order
      - Runs date extraction (all documents)
      - Runs 4-field extraction (all documents EXCEPT OCE/Title Register)

    Returns a dict with per-document results that the frontend renders.
    """
    title_number = title_number.upper()
    report_documents = []

    for filename in selected_filenames:
        filename = filename.strip()

        # Fetch ALL chunks for this specific document from ChromaDB
        # We use .get() not .query() because we want every chunk, not top-N similar ones
        results = case_collection.get(
            where={
                "$and": [
                    {"title_number": {"$eq": title_number}},
                    {"source": {"$eq": filename}}
                ]
            },
            include=["documents", "metadatas"]
        )

        # If no chunks found, this document hasn't been ingested — skip gracefully
        if not results["ids"]:
            report_documents.append({
                "filename": filename,
                "is_oce": is_oce_document(filename),
                "date": "[DOCUMENT NOT FOUND IN SYSTEM]",
                "rights_granted": None,
                "rights_reserved": None,
                "covenants": None,
                "provisions": None,
                "error": "No chunks found — document may not have been uploaded or processed"
            })
            continue

        # Sort chunks by chunk_index so we read the document in order
        # chunk_index is set in chunker.py when the document is first processed
        chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
        chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
        all_chunks = [chunk for chunk, _ in chunks_with_meta]

        # Determine if this is a Title Register (OCE) document
        is_oce = is_oce_document(filename)

        # For date extraction: OCE → first 3 chunks (date is on page 1)
        # Other docs → first 5 chunks (date usually near the top)
        date_chunks = all_chunks[:3] if is_oce else all_chunks[:5]
        date = extract_date(date_chunks, filename)

        # Build the result entry for this document
        doc_result = {
            "filename": filename,
            "is_oce": is_oce,
            "date": date,
            "rights_granted": None,  # None = not applicable (OCE)
            "rights_reserved": None,
            "covenants": None,
            "provisions": None
        }

        # Extract the four legal fields for non-OCE documents only
        # OCE (Title Register) does not contain these sections
        if not is_oce:
            fields = extract_legal_fields(all_chunks, filename)
            doc_result["rights_granted"] = fields["rights_granted"]
            doc_result["rights_reserved"] = fields["rights_reserved"]
            doc_result["covenants"] = fields["covenants"]
            doc_result["provisions"] = fields["provisions"]

        report_documents.append(doc_result)

    return {
        "title_number": title_number,
        "total_documents": len(report_documents),
        "documents": report_documents
    }