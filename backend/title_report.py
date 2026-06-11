# title_report.py — generates structured Title Reports from selected case documents
#
# How it works:
#   1. Employee selects documents (OCE, Transfer, Lease etc.) in the UI
#   2. For each selected document, we fetch ALL its chunks from ChromaDB
#   3. OCE (Title Register) → specific search date extraction only
#   4. All other docs → date + Rights Granted, Rights Reserved, Covenants, Provisions
#   5. LLM returns markdown-formatted text for structured rendering in the frontend

import os
from groq import Groq
from dotenv import load_dotenv
from embeddings import case_collection, model

load_dotenv()

# Initialise Groq LLM client using API key from environment
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Keywords used to identify Title Register (OCE) documents by filename
OCE_KEYWORDS = ["oce", "official copy", "title register", "official copies", "hmlr"]


def is_oce_document(filename: str) -> bool:
    """
    Returns True if the filename suggests this is a Title Register (OCE) document.
    Uses keyword matching on the lowercase filename.
    """
    return any(keyword in filename.lower() for keyword in OCE_KEYWORDS)


def extract_date(chunks: list, filename: str, is_oce: bool = False) -> str:
    """
    Extracts the date from the document chunks.

    For OCE documents: specifically targets the search date in the format
    "This official copy shows the entries on the register of title on [DATE] at [TIME]"
    e.g. "29 Sep 2016 at 10:08:02"

    For all other documents: looks for the main execution/signing date of the deed.

    Returns the date string or [NOT FOUND] if unavailable.
    max_tokens is low — we only need a short date string back.
    """
    context = "\n\n".join(chunks)

    if is_oce:
        # OCE-specific prompt — targets the exact search date shown on the official copy
        # This is the "entries shown as at" date, NOT the edition date
        prompt = f"""You are reading an Official Copy of Register of Title from HM Land Registry.

TASK: Find and return the search date of this official copy.

Look specifically for text like:
- "This official copy shows the entries on the register of title on [DATE] at [TIME]"
- "Issued on [DATE]"

Return the date AND time exactly as shown. Example: "29 Sep 2016 at 10:08:02"

Do NOT return the "Edition date" — that is a different field and not what we want.

RULES:
- Return ONLY the date/time string, nothing else
- If not found, return exactly: [NOT FOUND]

DOCUMENT TEXT:
{context}"""

    else:
        # Standard date extraction for transfer, lease, conveyance, deed etc.
        # These documents typically have "This deed is made on [date]" or "dated [date]"
        prompt = f"""You are reading a UK legal conveyancing document: {filename}

TASK: Find and return the date this document was executed (signed/completed).

Look for phrases like:
- "dated [date]"
- "this deed is made on [date]"
- "made the [day] day of [month] [year]"
- "THIS TRANSFER is made on [date]"

RULES:
- Return ONLY the date string. Example: "25 March 1999" or "15th June 2005"
- If multiple dates exist, return the main execution date
- If not found, return exactly: [NOT FOUND]

DOCUMENT TEXT:
{context}"""

    response = client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50  # Date is never more than a few words
    )

    return response.choices[0].message.content.strip()


def extract_legal_fields(chunks: list, filename: str) -> dict:
    """
    Extracts the four standard legal fields from a conveyancing document.
    Requests markdown-formatted output so the frontend can render it with
    proper structure — headers, bold text, numbered lists etc.

    Returns a dict with keys: rights_granted, rights_reserved, covenants, provisions
    """
    context = "\n\n".join(chunks)

    prompt = f"""You are a UK conveyancing legal assistant reading OCR-extracted text from: {filename}

TASK: Extract the following four categories. Format each section using markdown:
- Use **bold** for key terms and clause references
- Use numbered lists (1. 2. 3.) for multiple items
- Use > blockquote for verbatim legal text
- Keep headings clean — do not add extra headers beyond what is specified below

For each category:
- Extract the actual legal wording as accurately as possible
- If genuinely not present in this document, write: *Not present in this document*

Respond using EXACTLY these four headings in this order:

RIGHTS GRANTED:
[markdown formatted extracted text]

RIGHTS RESERVED:
[markdown formatted extracted text]

COVENANTS:
[markdown formatted extracted text]

PROVISIONS:
[markdown formatted extracted text]

DOCUMENT TEXT:
{context}"""

    response = client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048
    )

    raw = response.choices[0].message.content.strip()

    # Parse the structured response into individual fields
    fields = {
        "rights_granted": "[NOT FOUND]",
        "rights_reserved": "[NOT FOUND]",
        "covenants": "[NOT FOUND]",
        "provisions": "[NOT FOUND]"
    }

    # Map each heading to its dict key for parsing
    heading_map = {
        "RIGHTS GRANTED:": "rights_granted",
        "RIGHTS RESERVED:": "rights_reserved",
        "COVENANTS:": "covenants",
        "PROVISIONS:": "provisions"
    }

    headings = list(heading_map.keys())

    for i, heading in enumerate(headings):
        if heading not in raw:
            continue

        # Content starts right after the heading
        start = raw.index(heading) + len(heading)

        # Content ends at the next heading or end of string
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
      - Fetches all ChromaDB chunks for that document
      - Sorts chunks by chunk_index to preserve reading order
      - Runs date extraction (all documents, OCE uses specific prompt)
      - Runs 4-field extraction (all documents EXCEPT OCE/Title Register)

    Returns a structured dict the frontend renders as the Title Report.
    """
    title_number = title_number.upper()
    report_documents = []

    for filename in selected_filenames:
        filename = filename.strip()

        # Fetch ALL chunks for this specific document from ChromaDB
        # .get() returns everything — not top-N like .query()
        results = case_collection.get(
            where={
                "$and": [
                    {"title_number": {"$eq": title_number}},
                    {"source": {"$eq": filename}}
                ]
            },
            include=["documents", "metadatas"]
        )

        # If no chunks found, document hasn't been ingested — skip gracefully
        if not results["ids"]:
            report_documents.append({
                "filename": filename,
                "is_oce": is_oce_document(filename),
                "date": "[DOCUMENT NOT FOUND IN SYSTEM]",
                "rights_granted": None,
                "rights_reserved": None,
                "covenants": None,
                "provisions": None,
                "error": "No chunks found — document may not have been uploaded"
            })
            continue

        # Sort chunks by chunk_index to read the document in correct order
        chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
        chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
        all_chunks = [chunk for chunk, _ in chunks_with_meta]

        is_oce = is_oce_document(filename)

        # For date extraction:
        # OCE → first 3 chunks only (search date is always on page 1)
        # Other docs → first 5 chunks (execution date usually near the top)
        date_chunks = all_chunks[:3] if is_oce else all_chunks[:5]
        date = extract_date(date_chunks, filename, is_oce=is_oce)

        # Build the result entry for this document
        doc_result = {
            "filename": filename,
            "is_oce": is_oce,
            "date": date,
            "rights_granted": None,  # None = not applicable for OCE
            "rights_reserved": None,
            "covenants": None,
            "provisions": None
        }

        # Extract the four legal fields for non-OCE documents only
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