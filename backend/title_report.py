# # # title_report.py — generates structured Title Reports from selected case documents
# # #
# # # How it works:
# # #   1. Employee selects documents (OCE, Transfer, Lease etc.) in the UI
# # #   2. For each selected document, we fetch ALL its chunks from ChromaDB
# # #   3. OCE (Title Register) → specific search date extraction only
# # #   4. All other docs → date + Rights Granted, Rights Reserved, Covenants, Provisions
# # #   5. LLM returns markdown-formatted text for structured rendering in the frontend

# # import os
# # from groq import Groq
# # from dotenv import load_dotenv
# # from embeddings import case_collection, model

# # load_dotenv()

# # # Initialise Groq LLM client using API key from environment
# # client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# # # Keywords used to identify Title Register (OCE) documents by filename
# # OCE_KEYWORDS = ["oce", "official copy", "title register", "official copies", "hmlr"]


# # def is_oce_document(filename: str) -> bool:
# #     """
# #     Returns True if the filename suggests this is a Title Register (OCE) document.
# #     Uses keyword matching on the lowercase filename.
# #     """
# #     return any(keyword in filename.lower() for keyword in OCE_KEYWORDS)


# # def extract_date(chunks: list, filename: str, is_oce: bool = False) -> str:
# #     """
# #     Extracts the date from the document chunks.

# #     For OCE documents: specifically targets the search date in the format
# #     "This official copy shows the entries on the register of title on [DATE] at [TIME]"
# #     e.g. "29 Sep 2016 at 10:08:02"

# #     For all other documents: looks for the main execution/signing date of the deed.

# #     Returns the date string or [NOT FOUND] if unavailable.
# #     max_tokens is low — we only need a short date string back.
# #     """
# #     context = "\n\n".join(chunks)

# #     if is_oce:
# #         # OCE-specific prompt — targets the exact search date shown on the official copy
# #         # This is the "entries shown as at" date, NOT the edition date
# #         prompt = f"""You are reading an Official Copy of Register of Title from HM Land Registry.

# # TASK: Find and return the search date of this official copy.

# # Look specifically for text like:
# # - "This official copy shows the entries on the register of title on [DATE] at [TIME]"
# # - "Issued on [DATE]"

# # Return the date AND time exactly as shown. Example: "29 Sep 2016 at 10:08:02"

# # Do NOT return the "Edition date" — that is a different field and not what we want.

# # RULES:
# # - Return ONLY the date/time string, nothing else
# # - If not found, return exactly: [NOT FOUND]

# # DOCUMENT TEXT:
# # {context}"""

# #     else:
# #         # Standard date extraction for transfer, lease, conveyance, deed etc.
# #         # These documents typically have "This deed is made on [date]" or "dated [date]"
# #         prompt = f"""You are reading a UK legal conveyancing document: {filename}

# # TASK: Find and return the date this document was executed (signed/completed).

# # Look for phrases like:
# # - "dated [date]"
# # - "this deed is made on [date]"
# # - "made the [day] day of [month] [year]"
# # - "THIS TRANSFER is made on [date]"

# # RULES:
# # - Return ONLY the date string. Example: "25 March 1999" or "15th June 2005"
# # - If multiple dates exist, return the main execution date
# # - If not found, return exactly: [NOT FOUND]

# # DOCUMENT TEXT:
# # {context}"""

# #     response = client.chat.completions.create(
# #         model="groq/compound",
# #         messages=[{"role": "user", "content": prompt}],
# #         max_tokens=50  # Date is never more than a few words
# #     )

# #     return response.choices[0].message.content.strip()


# # def extract_legal_fields(chunks: list, filename: str) -> dict:
# #     """
# #     Extracts the four standard legal fields from a conveyancing document.
# #     Requests markdown-formatted output so the frontend can render it with
# #     proper structure — headers, bold text, numbered lists etc.

# #     Returns a dict with keys: rights_granted, rights_reserved, covenants, provisions
# #     """
# #     context = "\n\n".join(chunks)

# #     prompt = f"""You are a UK conveyancing legal assistant reading OCR-extracted text from: {filename}

# # TASK: Extract the following four categories. Format each section using markdown:
# # - Use **bold** for key terms and clause references
# # - Use numbered lists (1. 2. 3.) for multiple items
# # - Use > blockquote for verbatim legal text
# # - Keep headings clean — do not add extra headers beyond what is specified below

# # For each category:
# # - Extract the actual legal wording as accurately as possible
# # - If genuinely not present in this document, write: *Not present in this document*

# # Respond using EXACTLY these four headings in this order:

# # RIGHTS GRANTED:
# # [markdown formatted extracted text]

# # RIGHTS RESERVED:
# # [markdown formatted extracted text]

# # COVENANTS:
# # [markdown formatted extracted text]

# # PROVISIONS:
# # [markdown formatted extracted text]

# # DOCUMENT TEXT:
# # {context}"""

# #     response = client.chat.completions.create(
# #         model="groq/compound",
# #         messages=[{"role": "user", "content": prompt}],
# #         max_tokens=2048
# #     )

# #     raw = response.choices[0].message.content.strip()

# #     # Parse the structured response into individual fields
# #     fields = {
# #         "rights_granted": "[NOT FOUND]",
# #         "rights_reserved": "[NOT FOUND]",
# #         "covenants": "[NOT FOUND]",
# #         "provisions": "[NOT FOUND]"
# #     }

# #     # Map each heading to its dict key for parsing
# #     heading_map = {
# #         "RIGHTS GRANTED:": "rights_granted",
# #         "RIGHTS RESERVED:": "rights_reserved",
# #         "COVENANTS:": "covenants",
# #         "PROVISIONS:": "provisions"
# #     }

# #     headings = list(heading_map.keys())

# #     for i, heading in enumerate(headings):
# #         if heading not in raw:
# #             continue

# #         # Content starts right after the heading
# #         start = raw.index(heading) + len(heading)

# #         # Content ends at the next heading or end of string
# #         end = len(raw)
# #         for next_heading in headings[i + 1:]:
# #             if next_heading in raw:
# #                 candidate = raw.index(next_heading)
# #                 if candidate > start:
# #                     end = candidate
# #                     break

# #         fields[heading_map[heading]] = raw[start:end].strip()

# #     return fields


# # def generate_title_report(title_number: str, selected_filenames: list) -> dict:
# #     """
# #     Main entry point — generates the full Title Report for a set of selected documents.

# #     For each selected filename:
# #       - Fetches all ChromaDB chunks for that document
# #       - Sorts chunks by chunk_index to preserve reading order
# #       - Runs date extraction (all documents, OCE uses specific prompt)
# #       - Runs 4-field extraction (all documents EXCEPT OCE/Title Register)

# #     Returns a structured dict the frontend renders as the Title Report.
# #     """
# #     title_number = title_number.upper()
# #     report_documents = []

# #     for filename in selected_filenames:
# #         filename = filename.strip()

# #         # Fetch ALL chunks for this specific document from ChromaDB
# #         # .get() returns everything — not top-N like .query()
# #         results = case_collection.get(
# #             where={
# #                 "$and": [
# #                     {"title_number": {"$eq": title_number}},
# #                     {"source": {"$eq": filename}}
# #                 ]
# #             },
# #             include=["documents", "metadatas"]
# #         )

# #         # If no chunks found, document hasn't been ingested — skip gracefully
# #         if not results["ids"]:
# #             report_documents.append({
# #                 "filename": filename,
# #                 "is_oce": is_oce_document(filename),
# #                 "date": "[DOCUMENT NOT FOUND IN SYSTEM]",
# #                 "rights_granted": None,
# #                 "rights_reserved": None,
# #                 "covenants": None,
# #                 "provisions": None,
# #                 "error": "No chunks found — document may not have been uploaded"
# #             })
# #             continue

# #         # Sort chunks by chunk_index to read the document in correct order
# #         chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
# #         chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
# #         all_chunks = [chunk for chunk, _ in chunks_with_meta]

# #         is_oce = is_oce_document(filename)

# #         # For date extraction:
# #         # OCE → first 3 chunks only (search date is always on page 1)
# #         # Other docs → first 5 chunks (execution date usually near the top)
# #         date_chunks = all_chunks[:3] if is_oce else all_chunks[:5]
# #         date = extract_date(date_chunks, filename, is_oce=is_oce)

# #         # Build the result entry for this document
# #         doc_result = {
# #             "filename": filename,
# #             "is_oce": is_oce,
# #             "date": date,
# #             "rights_granted": None,  # None = not applicable for OCE
# #             "rights_reserved": None,
# #             "covenants": None,
# #             "provisions": None
# #         }

# #         # Extract the four legal fields for non-OCE documents only
# #         if not is_oce:
# #             fields = extract_legal_fields(all_chunks, filename)
# #             doc_result["rights_granted"] = fields["rights_granted"]
# #             doc_result["rights_reserved"] = fields["rights_reserved"]
# #             doc_result["covenants"] = fields["covenants"]
# #             doc_result["provisions"] = fields["provisions"]

# #         report_documents.append(doc_result)

# #     return {
# #         "title_number": title_number,
# #         "total_documents": len(report_documents),
# #         "documents": report_documents
# #     }

# #
# # title_report.py — generates structured Title Reports from selected case documents
# #
# # Uses a MAP-REDUCE approach for legal field extraction:
# #   MAP:    Split full document into 8000-char batches, scan each for fields
# #   REDUCE: Consolidate all batch findings into one clean markdown output
# #
# # This ensures the entire document is scanned regardless of length,
# # while keeping each individual Groq request well within size limits.
# # With Groq compound at 70k req/min, multiple small calls is no problem.

# import os
# from groq import Groq
# from dotenv import load_dotenv
# from embeddings import case_collection, model

# load_dotenv()

# # Initialise Groq LLM client using API key from environment
# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# # Keywords used to identify Title Register (OCE) documents by filename
# OCE_KEYWORDS = ["oce", "official copy", "title register", "official copies", "hmlr"]

# # Batch size for the map step — 8000 chars keeps each request small
# # enough to never hit Groq's 413 limit, even on large documents
# BATCH_SIZE = 8000

# # Overlap between batches so content spanning a batch boundary isn't missed
# # e.g. a covenant that starts at the end of batch 1 and continues into batch 2
# BATCH_OVERLAP = 300

# # Date extraction only needs the first page — dates are always near the top
# MAX_CHARS_DATE = 3000


# def is_oce_document(filename: str) -> bool:
#     """
#     Returns True if the filename suggests this is a Title Register (OCE) document.
#     """
#     return any(keyword in filename.lower() for keyword in OCE_KEYWORDS)


# def split_into_batches(text: str) -> list:
#     """
#     Splits a long document text into overlapping batches of BATCH_SIZE chars.
#     The overlap ensures content at batch boundaries is captured by both batches.
#     Returns a list of text strings.
#     """
#     batches = []
#     start = 0
#     text_length = len(text)

#     while start < text_length:
#         end = start + BATCH_SIZE
#         batches.append(text[start:end])
#         # Move forward by BATCH_SIZE minus the overlap
#         # so the next batch starts BATCH_OVERLAP chars before where this one ended
#         start += BATCH_SIZE - BATCH_OVERLAP

#     return batches


# def extract_date(chunks: list, filename: str, is_oce: bool = False) -> str:
#     """
#     Extracts the date from the first part of the document.
#     Dates are always near the top so we only need the first 3000 chars.

#     OCE: targets "This official copy shows entries on register of title on [DATE] at [TIME]"
#     Other docs: targets the main execution/signing date of the deed.
#     """
#     # Dates are on the first page — no need to scan the whole document
#     context = "\n\n".join(chunks)[:MAX_CHARS_DATE]

#     if is_oce:
#         # Specific prompt for Official Copy — targets the search date, not the edition date
#         prompt = f"""You are reading an Official Copy of Register of Title from HM Land Registry.

# TASK: Find and return the search date of this official copy.

# Look specifically for:
# "This official copy shows the entries on the register of title on [DATE] at [TIME]"

# Return the date AND time exactly as shown. Example: "29 Sep 2016 at 10:08:02"

# Do NOT return the "Edition date" — that is a different field.

# RULES:
# - Return ONLY the date/time string, nothing else
# - If not found, return exactly: [NOT FOUND]

# DOCUMENT TEXT:
# {context}"""

#     else:
#         # Standard execution date extraction for transfers, leases, deeds etc.
#         prompt = f"""You are reading a UK legal conveyancing document: {filename}

# TASK: Find and return the date this document was executed (signed/completed).

# Look for:
# - "dated [date]"
# - "this deed is made on [date]"
# - "made the [day] day of [month] [year]"
# - "THIS TRANSFER is made on [date]"

# RULES:
# - Return ONLY the date string. Example: "25 March 1999"
# - Return the main execution date if multiple dates exist
# - If not found, return exactly: [NOT FOUND]

# DOCUMENT TEXT:
# {context}"""

#     response = client.chat.completions.create(
#         model="groq/compound",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=50  # Date is never more than a few words
#     )

#     return response.choices[0].message.content.strip()


# def scan_batch_for_fields(batch_text: str, filename: str, batch_num: int) -> str:
#     """
#     MAP STEP — scans a single batch of document text for any of the four legal fields.
#     Returns the raw findings as text, or an empty string if nothing relevant found.

#     Each batch is kept small (BATCH_SIZE chars) to avoid Groq 413 errors.
#     """
#     prompt = f"""You are scanning a section of a UK legal conveyancing document: {filename}
# This is section {batch_num} of the document.

# From THIS SECTION ONLY, extract any of the following if present:
# - Rights Granted (rights given to the buyer/owner)
# - Rights Reserved (rights kept by the seller/transferor)
# - Covenants (obligations or restrictions binding on the land)
# - Provisions (other operative clauses, conditions, or terms)

# Respond in this EXACT format:
# RIGHTS GRANTED: [extracted text or NONE]
# RIGHTS RESERVED: [extracted text or NONE]
# COVENANTS: [extracted text or NONE]
# PROVISIONS: [extracted text or NONE]

# Rules:
# - Write NONE if a category is not present in this section
# - Extract the actual text — do not summarise or paraphrase
# - OCR text may be noisy — interpret it intelligently

# SECTION TEXT:
# {batch_text}"""

#     response = client.chat.completions.create(
#         model="groq/compound",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=800  # Enough for partial findings from one batch
#     )

#     return response.choices[0].message.content.strip()


# def has_content(batch_result: str) -> bool:
#     """
#     Returns True if a batch scan found anything beyond NONE placeholders.
#     Used to filter out empty batches before the consolidation step.
#     """
#     # Replace all NONE lines and check if anything meaningful remains
#     cleaned = batch_result
#     for line in ["RIGHTS GRANTED: NONE", "RIGHTS RESERVED: NONE",
#                  "COVENANTS: NONE", "PROVISIONS: NONE"]:
#         cleaned = cleaned.replace(line, "")

#     return bool(cleaned.strip())


# def consolidate_findings(partial_results: list, filename: str) -> dict:
#     """
#     REDUCE STEP — takes all batch findings and consolidates into final output.

#     Sends all non-empty batch results to the LLM in one consolidation call.
#     The LLM deduplicates, merges fragments, and formats as clean markdown.
#     """
#     # Filter to only batches that found something
#     meaningful = [r for r in partial_results if has_content(r)]

#     # If nothing was found across the whole document, return not-present messages
#     if not meaningful:
#         return {
#             "rights_granted": "*Not present in this document*",
#             "rights_reserved": "*Not present in this document*",
#             "covenants": "*Not present in this document*",
#             "provisions": "*Not present in this document*"
#         }

#     # Combine all batch findings into one block for the consolidation prompt
#     combined = "\n\n--- NEXT SECTION ---\n\n".join(meaningful)

#     prompt = f"""You are consolidating legal field extractions from multiple sections of: {filename}

# The text below contains extractions from different parts of the document.
# Your job is to consolidate them into one clean, structured response per field.

# Rules:
# - Remove exact duplicates
# - Merge fragments of the same clause that were split across sections
# - Use markdown formatting:
#   * **bold** for key legal terms and clause references
#   * Numbered lists (1. 2. 3.) for multiple items
#   * > blockquote for verbatim legal text
# - If a field was NONE in ALL sections, write: *Not present in this document*

# Respond using EXACTLY these headings:

# RIGHTS GRANTED:
# [consolidated markdown]

# RIGHTS RESERVED:
# [consolidated markdown]

# COVENANTS:
# [consolidated markdown]

# PROVISIONS:
# [consolidated markdown]

# EXTRACTIONS FROM ALL SECTIONS:
# {combined}"""

#     response = client.chat.completions.create(
#         model="groq/compound",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=2500
#     )

#     return parse_field_response(response.choices[0].message.content.strip())


# def parse_field_response(raw: str) -> dict:
#     """
#     Parses the LLM's structured response into a dict with four field keys.
#     Splits on the known headings to extract each section's content.
#     """
#     fields = {
#         "rights_granted": "*Not present in this document*",
#         "rights_reserved": "*Not present in this document*",
#         "covenants": "*Not present in this document*",
#         "provisions": "*Not present in this document*"
#     }

#     heading_map = {
#         "RIGHTS GRANTED:": "rights_granted",
#         "RIGHTS RESERVED:": "rights_reserved",
#         "COVENANTS:": "covenants",
#         "PROVISIONS:": "provisions"
#     }

#     headings = list(heading_map.keys())

#     for i, heading in enumerate(headings):
#         if heading not in raw:
#             continue

#         start = raw.index(heading) + len(heading)

#         # Content ends at the next heading or end of string
#         end = len(raw)
#         for next_heading in headings[i + 1:]:
#             if next_heading in raw:
#                 candidate = raw.index(next_heading)
#                 if candidate > start:
#                     end = candidate
#                     break

#         extracted = raw[start:end].strip()
#         if extracted:
#             fields[heading_map[heading]] = extracted

#     return fields


# def extract_legal_fields(all_chunks: list, filename: str) -> dict:
#     """
#     Full map-reduce pipeline for extracting the four legal fields from a document.

#     MAP:    Joins all chunks into full document text, splits into BATCH_SIZE batches,
#             scans each batch independently with a small targeted LLM call.

#     REDUCE: Sends all non-empty batch findings to a consolidation LLM call
#             that merges, deduplicates and formats as markdown.

#     This scans the entire document regardless of length while keeping
#     every individual Groq request well within the 413 size limit.
#     """
#     # Join all chunks into the full document text first
#     full_text = "\n\n".join(all_chunks)

#     # Split into overlapping batches
#     batches = split_into_batches(full_text)
#     print(f"[Title Report] Scanning {filename} in {len(batches)} batches...")

#     # MAP: scan each batch for relevant legal content
#     partial_results = []
#     for i, batch in enumerate(batches):
#         result = scan_batch_for_fields(batch, filename, batch_num=i + 1)
#         partial_results.append(result)

#     # REDUCE: consolidate all batch findings into final structured output
#     return consolidate_findings(partial_results, filename)


# def generate_title_report(title_number: str, selected_filenames: list) -> dict:
#     """
#     Main entry point — generates the full Title Report for a set of selected documents.

#     For each selected filename:
#       - Fetches ALL ChromaDB chunks for that document
#       - Sorts chunks by chunk_index to preserve document reading order
#       - Runs date extraction (all documents)
#       - Runs map-reduce field extraction (all documents except OCE)

#     Returns a structured dict the frontend renders as the Title Report.
#     """
#     title_number = title_number.upper()
#     report_documents = []

#     for filename in selected_filenames:
#         filename = filename.strip()

#         # Fetch ALL chunks for this document from ChromaDB
#         # .get() returns every chunk, not top-N like .query()
#         results = case_collection.get(
#             where={
#                 "$and": [
#                     {"title_number": {"$eq": title_number}},
#                     {"source": {"$eq": filename}}
#                 ]
#             },
#             include=["documents", "metadatas"]
#         )

#         # If no chunks found, document hasn't been ingested — skip gracefully
#         if not results["ids"]:
#             report_documents.append({
#                 "filename": filename,
#                 "is_oce": is_oce_document(filename),
#                 "date": "[DOCUMENT NOT FOUND IN SYSTEM]",
#                 "rights_granted": None,
#                 "rights_reserved": None,
#                 "covenants": None,
#                 "provisions": None,
#                 "error": "No chunks found — document may not have been uploaded"
#             })
#             continue

#         # Sort chunks by chunk_index to read the document in correct order
#         chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
#         chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
#         all_chunks = [chunk for chunk, _ in chunks_with_meta]

#         is_oce = is_oce_document(filename)

#         # Date: OCE → first 3 chunks, others → first 5 chunks
#         # Dates are always near the top so we don't need the full document
#         date_chunks = all_chunks[:3] if is_oce else all_chunks[:5]
#         date = extract_date(date_chunks, filename, is_oce=is_oce)

#         doc_result = {
#             "filename": filename,
#             "is_oce": is_oce,
#             "date": date,
#             "rights_granted": None,  # None = not applicable for OCE
#             "rights_reserved": None,
#             "covenants": None,
#             "provisions": None
#         }

#         # Run map-reduce field extraction for non-OCE documents only
#         # OCE (Title Register) does not contain these sections
#         if not is_oce:
#             fields = extract_legal_fields(all_chunks, filename)
#             doc_result["rights_granted"] = fields["rights_granted"]
#             doc_result["rights_reserved"] = fields["rights_reserved"]
#             doc_result["covenants"] = fields["covenants"]
#             doc_result["provisions"] = fields["provisions"]

#         report_documents.append(doc_result)

#     return {
#         "title_number": title_number,
#         "total_documents": len(report_documents),
#         "documents": report_documents
#     }


# title_report.py — generates structured Title Reports from selected case documents

# title_report.py — Title Report generation using MAP-REDUCE over full case documents
#
# WHY MAP-REDUCE:
#   Legal documents can be very long. Sending the full text to Groq in one request
#   causes 413 (Request Too Large) errors. Instead we:
#     MAP:    Split full text into small batches, scan each independently
#     REDUCE: Consolidate all non-empty findings into one clean markdown output
#
#   This scans the ENTIRE document while keeping every individual request small.
#   With groq/compound at 70k req/min, many small calls is fine.

import os
import re
import time
from groq import Groq
from dotenv import load_dotenv
from embeddings import case_collection

load_dotenv()

# Groq client — API key loaded from environment variable
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Filename substrings that identify a Title Register (Official Copy of Entries) document
OCE_KEYWORDS = ["oce", "official copy", "title register", "official copies", "hmlr"]

# MAP step: each batch sent to Groq is at most BATCH_SIZE characters
# This keeps every request well under Groq's 413 size threshold
BATCH_SIZE = 6000

# Overlap between consecutive batches so content at a boundary isn't missed
# e.g. a covenant clause that straddles two batch boundaries
BATCH_OVERLAP = 300

# Date extraction only needs the first page — dates are always near the top
MAX_CHARS_DATE = 1500

# REDUCE step: cap the combined batch results before sending to consolidation
# Prevents the reduce call from becoming too large if there are many batches
MAX_CHARS_CONSOLIDATION = 10000


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def is_oce_document(filename: str) -> bool:
    """Returns True if the filename indicates this is a Title Register (OCE)."""
    return any(kw in filename.lower() for kw in OCE_KEYWORDS)


def split_into_batches(text: str) -> list:
    """
    Splits the full document text into overlapping BATCH_SIZE-char segments.
    Overlap of BATCH_OVERLAP chars ensures content at boundaries is captured.
    """
    batches = []
    start = 0
    while start < len(text):
        batches.append(text[start: start + BATCH_SIZE])
        # Advance by BATCH_SIZE minus overlap so next batch re-reads the tail
        start += BATCH_SIZE - BATCH_OVERLAP
    return batches


def safe_groq_call(prompt: str, max_tokens: int) -> str:
    """
    Wraps every Groq API call with retry logic for rate limit (429) errors
    and graceful skip for size limit (413) errors.

    429 — extracts the suggested wait time from the error message and sleeps
    413 — logs and returns empty string so the caller can skip this batch
    """
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="groq/compound",  # Always groq/compound — do not change
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e)

            if "429" in error_str:
                # Groq tells us how long to wait — parse it and add a safety buffer
                wait_time = 5.0
                match_s = re.search(r"try again in ([0-9.]+)s", error_str)
                match_ms = re.search(r"try again in ([0-9.]+)ms", error_str)
                if match_s:
                    wait_time = float(match_s.group(1)) + 3.0
                elif match_ms:
                    wait_time = (float(match_ms.group(1)) / 1000.0) + 3.0
                print(f"[Rate Limit] Waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            elif "413" in error_str:
                # Batch is still too large — skip it rather than retrying
                print(f"[Size Limit] Prompt too large, skipping batch (attempt {attempt + 1})")
                return ""

            else:
                # Unknown error — short pause then retry
                print(f"[Groq Error] {error_str}")
                time.sleep(2)

    # All retries exhausted — return empty so caller handles gracefully
    return ""


# ---------------------------------------------------------------------------
# DATE EXTRACTION
# ---------------------------------------------------------------------------

def extract_date(chunks: list, filename: str, is_oce: bool = False) -> str:
    """
    Extracts the document date using only the first MAX_CHARS_DATE characters.
    Dates always appear near the top of a document so no need to scan further.

    OCE: looks for "entries on register of title on [DATE] at [TIME]"
    Other docs: looks for the main execution / signing date of the deed
    """
    # Truncate to first 1500 chars — keeps this request very small
    context = "\n\n".join(chunks)[:MAX_CHARS_DATE]

    if is_oce:
        # OCE-specific prompt — targets search date, NOT edition date
        prompt = (
            "You are reading an Official Copy of Register of Title (HM Land Registry).\n\n"
            "Find and return the search date. Look for:\n"
            '"This official copy shows the entries on the register of title on [DATE] at [TIME]"\n\n'
            "Return ONLY the date+time string, e.g. '29 Sep 2016 at 10:08:02'.\n"
            "Do NOT return the Edition date — that is a different field.\n"
            "If not found, return exactly: [NOT FOUND]\n\n"
            f"DOCUMENT:\n{context}"
        )
    else:
        prompt = (
            f"You are reading a UK legal conveyancing document: {filename}\n\n"
            "Find and return the date this document was executed (signed/completed).\n"
            "Look for: 'dated', 'this deed is made on', 'made the Xth day of [month] [year]'.\n\n"
            "Return ONLY the date string, e.g. '25 March 1999'.\n"
            "If not found, return exactly: [NOT FOUND]\n\n"
            f"DOCUMENT:\n{context}"
        )

    result = safe_groq_call(prompt, max_tokens=50)
    return result if result else "[NOT FOUND]"


# ---------------------------------------------------------------------------
# MAP STEP — scan individual batches
# ---------------------------------------------------------------------------

def scan_batch_for_fields(batch_text: str, filename: str, batch_num: int) -> str:
    """
    MAP STEP — sends one BATCH_SIZE-char section to Groq and asks it to extract
    any of the four legal field categories present in that section only.

    Returns the raw text response, or empty string if the batch is skipped.
    Each call is small enough to never hit Groq's 413 limit.
    """
    prompt = (
        f"You are scanning section {batch_num} of a UK legal document: {filename}\n\n"
        "From THIS SECTION ONLY, extract any of these if present:\n"
        "- Rights Granted (rights given to the buyer/owner)\n"
        "- Rights Reserved (rights kept by the seller/transferor)\n"
        "- Covenants (obligations or restrictions binding on the land)\n"
        "- Provisions (other operative clauses, conditions, or terms)\n\n"
        "Respond in EXACTLY this format (NONE if absent from this section):\n"
        "RIGHTS GRANTED: [text or NONE]\n"
        "RIGHTS RESERVED: [text or NONE]\n"
        "COVENANTS: [text or NONE]\n"
        "PROVISIONS: [text or NONE]\n\n"
        "Extract actual text — do not summarise. OCR may be noisy; interpret intelligently.\n\n"
        f"SECTION:\n{batch_text}"
    )
    return safe_groq_call(prompt, max_tokens=400)


def has_content(result: str) -> bool:
    """
    Returns True if a batch scan found anything beyond NONE placeholders.
    Used to filter empty batches before sending to the consolidation step.
    """
    cleaned = (result
               .replace("RIGHTS GRANTED: NONE", "")
               .replace("RIGHTS RESERVED: NONE", "")
               .replace("COVENANTS: NONE", "")
               .replace("PROVISIONS: NONE", ""))
    return bool(cleaned.strip())


# ---------------------------------------------------------------------------
# REDUCE STEP — consolidate all batch findings
# ---------------------------------------------------------------------------

def consolidate_findings(partial_results: list, filename: str) -> dict:
    """
    REDUCE STEP — takes all non-empty batch results and asks Groq to merge them
    into one clean, deduplicated, markdown-formatted output per field.

    The combined text is capped at MAX_CHARS_CONSOLIDATION to prevent this
    single consolidation call from triggering a 413 error.
    """
    # Keep only batches that found something meaningful
    meaningful = [r for r in partial_results if has_content(r)]

    # Nothing found anywhere — return not-present defaults for all fields
    if not meaningful:
        return {k: "*Not present in this document*"
                for k in ["rights_granted", "rights_reserved", "covenants", "provisions"]}

    # Join all findings, then cap total size before sending to Groq
    # This prevents the consolidation prompt itself from being too large
    combined = "\n\n--- NEXT SECTION ---\n\n".join(meaningful)
    combined = combined[:MAX_CHARS_CONSOLIDATION]

    prompt = (
        f"Consolidate these legal field extractions from different sections of: {filename}\n\n"
        "Rules:\n"
        "- Remove exact duplicates\n"
        "- Merge fragments of the same clause that were split across sections\n"
        "- Use markdown: **bold** for key terms, numbered lists, > blockquote for verbatim text\n"
        "- Write *Not present in this document* if NONE across all sections\n\n"
        "Respond with EXACTLY these headings:\n\n"
        "RIGHTS GRANTED:\n[text]\n\n"
        "RIGHTS RESERVED:\n[text]\n\n"
        "COVENANTS:\n[text]\n\n"
        "PROVISIONS:\n[text]\n\n"
        f"EXTRACTIONS:\n{combined}"
    )

    raw = safe_groq_call(prompt, max_tokens=2000)
    return parse_field_response(raw)


def parse_field_response(raw: str) -> dict:
    """
    Splits the LLM's structured REDUCE response into a dict by heading.
    Extracts content between each heading and the next.
    """
    # Default values if parsing fails or a field is missing
    fields = {
        "rights_granted": "*Not present in this document*",
        "rights_reserved": "*Not present in this document*",
        "covenants": "*Not present in this document*",
        "provisions": "*Not present in this document*"
    }

    if not raw:
        return fields

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
        start = raw.index(heading) + len(heading)
        end = len(raw)
        # Content ends where the next heading starts
        for next_h in headings[i + 1:]:
            if next_h in raw:
                candidate = raw.index(next_h)
                if candidate > start:
                    end = candidate
                    break
        extracted = raw[start:end].strip()
        if extracted:
            fields[heading_map[heading]] = extracted

    return fields


# ---------------------------------------------------------------------------
# ORCHESTRATION
# ---------------------------------------------------------------------------

def extract_legal_fields(all_chunks: list, filename: str) -> dict:
    """
    Full MAP-REDUCE pipeline for the four legal fields.

    1. Join all ChromaDB chunks into the full document text
    2. MAP:    Split into BATCH_SIZE batches, call Groq on each
    3. REDUCE: Consolidate non-empty results into final markdown output
    """
    full_text = "\n\n".join(all_chunks)
    batches = split_into_batches(full_text)
    print(f"[TitleReport] {filename}: scanning {len(batches)} batches")

    # MAP — one Groq call per batch
    partial_results = []
    for i, batch in enumerate(batches):
        result = scan_batch_for_fields(batch, filename, batch_num=i + 1)
        partial_results.append(result)

    # REDUCE — one Groq call to consolidate all findings
    return consolidate_findings(partial_results, filename)


def generate_title_report(title_number: str, selected_filenames: list) -> dict:
    """
    Main entry point — generates the Title Report for a set of selected documents.

    For each document:
      - Fetches ALL ChromaDB chunks, sorted by chunk_index (document reading order)
      - Extracts the date (first page only)
      - Runs map-reduce field extraction for non-OCE documents
    """
    # Uppercase inline — never reassign a FastAPI path param variable
    title_number = title_number.upper()
    report_documents = []

    for filename in selected_filenames:
        filename = filename.strip()

        # Fetch every stored chunk for this document from ChromaDB
        # Using .get() not .query() — we want all chunks, not just top-N by similarity
        results = case_collection.get(
            where={
                "$and": [
                    {"title_number": {"$eq": title_number}},
                    {"source": {"$eq": filename}}   # metadata key is "source" not "filename"
                ]
            },
            include=["documents", "metadatas"]
        )

        # Document not ingested or missing — record the error and move on
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

        # Sort chunks by chunk_index so the document is read in the correct order
        chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
        chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
        all_chunks = [chunk for chunk, _ in chunks_with_meta]

        is_oce = is_oce_document(filename)

        # Use only the first few chunks for date extraction (dates are always on page 1)
        date_chunks = all_chunks[:3] if is_oce else all_chunks[:5]
        date = extract_date(date_chunks, filename, is_oce=is_oce)

        doc_result = {
            "filename": filename,
            "is_oce": is_oce,
            "date": date,
            "rights_granted": None,  # None = not applicable for OCE docs
            "rights_reserved": None,
            "covenants": None,
            "provisions": None
        }

        # OCE (Title Register) doesn't contain rights/covenants — skip field extraction
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