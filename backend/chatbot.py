# # chatbot.py — handles all AI chat functionality

# import os
# from groq import Groq
# from dotenv import load_dotenv
# from embeddings import search_case, search_formats

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# #Comment
# def ask_question(question: str, title_number: str, history: list = []) -> dict:
#     """
#     General Q&A with conversation memory
#     history is the full list of previous messages
#     """

#     # # Search case documents for relevant chunks
#     # search_results = search_case(
#     #     query=question,
#     #     title_number=title_number,
#     #     n_results=15
#     # )
#     # relevant_chunks = search_results["documents"][0]
#     # context = "\n\n".join(relevant_chunks)

#     current_doc_context = ""
#     other_docs_context = ""

#     if current_document:
#         # 1. Search ONLY in the currently opened document
#         current_results = case_collection.query(
#             query_texts=[question],
#             n_results=3,
#             where={"$and": [
#                 {"title_number": title_number}, 
#                 {"filename": current_document}
#             ]}
#         )
#         if current_results["documents"]:
#             current_doc_context = "\n\n".join(current_results["documents"][0])

#         # 2. Search in the REST of the case documents
#         other_results = case_collection.query(
#             query_texts=[question],
#             n_results=3,
#             where={"$and": [
#                 {"title_number": title_number}, 
#                 {"filename": {"$ne": current_document}} # $ne means Not Equal
#             ]}
#         )
#         if other_results["documents"]:
#             other_docs_context = "\n\n".join(other_results["documents"][0])

#     else:
#         # Fallback: If no document is open, just search everything normally
#         results = case_collection.query(
#             query_texts=[question],
#             n_results=5,
#             where={"title_number": title_number}
#         )
#         if results["documents"]:
#             other_docs_context = "\n\n".join(results["documents"][0])

# #     system_prompt = f"""You are a UK conveyancing legal assistant.
# # You help solicitors and legal employees understand property documents.
# # Answer questions based ONLY on the context provided below.
# # If the answer is not in the context, say "I cannot find that information in this document."
# # Be precise, professional and detailed in your answers.
# # Always provide complete information — do not give short answers.
# # Use UK legal terminology.

# # DOCUMENT CONTEXT:
# # {context}"""

#     system_prompt = f"""You are an expert UK conveyancing legal assistant AI.
#     Your role is to answer questions based strictly on the extracted case documents.

#     PRIORITY RULES:
#     1. FIRST, attempt to answer the question using ONLY the facts in the [CURRENTLY OPEN DOCUMENT CONTEXT].
#     2. If (and only if) the answer is completely missing from the open document, fallback to the [OTHER CASE DOCUMENTS CONTEXT].
#     3. If the answer is found, state it directly. Never use phrases like "Based on the documents...".
#     4. If the answer is in neither context, reply: "I cannot find this information in the case documents."

#     [CURRENTLY OPEN DOCUMENT CONTEXT]
#     {current_doc_context if current_doc_context else "None available."}

#     [OTHER CASE DOCUMENTS CONTEXT]
#     {other_docs_context if other_docs_context else "None available."}
#     """



#     # Build messages array with full history
#     # This gives Groq memory of the whole conversation
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     # Add previous messages from history (excluding the current question)
#     for msg in history[:-1]:  # exclude last message as we add it separately
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     # Add current question
#     groq_messages.append({"role": "user", "content": question})

#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "question",
#         "answer": response.choices[0].message.content,
#         "title_number": title_number,
#         "chunks_used": len(relevant_chunks)
#     }


# def raise_enquiry(issue: str, title_number: str, history: list = []) -> dict:
#     """
#     Generates case-specific enquiry text with conversation memory
#     """

# #     # Search format library for matching enquiry template
# #     format_results = search_formats(query=issue, n_results=2)
# #     format_chunks = format_results["documents"][0]
# #     format_metadata = format_results["metadatas"][0]

# #     # Search case documents for relevant facts
# #     case_results = search_case(
# #         query=issue,
# #         title_number=title_number,
# #         n_results=5
# #     )
# #     case_chunks = case_results["documents"][0]

# #     format_context = "\n\n".join(format_chunks)
# #     case_context = "\n\n".join(case_chunks)

# #     best_match = format_metadata[0] if format_metadata else {}
# #     enquiry_code = best_match.get("code", "Unknown")
# #     enquiry_topic = best_match.get("topic", "Unknown")

# #     system_prompt = f"""You are a UK conveyancing legal assistant at a solicitors firm.
# # Your job is to generate formal legal enquiry text to be sent to the seller's solicitors.
# # Use professional UK conveyancing language throughout.
# # Generate ONLY the enquiry text — no explanations, no preamble, no sign-off.
# # Replace placeholders like (year), (insert date), (insert name) with actual values from the case facts.
# # If you cannot find a specific value, keep the placeholder but flag it with [PLEASE COMPLETE].

# # ENQUIRY TEMPLATE:
# # {format_context}

# # CASE FACTS:
# # {case_context}"""


#     format_results = format_collection.query(
#         query_texts=[issue],
#         n_results=1  # We only need the top matching format template
#     )
#     format_library_context = ""
#     if format_results["documents"] and len(format_results["documents"][0]) > 0:
#         format_library_context = format_results["documents"][0][0]

#     # 2. Fetch the specific case facts (Context-Weighted)
#     current_doc_context = ""
#     other_docs_context = ""

#     if current_document:
#         # Search ONLY in the currently opened document
#         current_results = case_collection.query(
#             query_texts=[issue],
#             n_results=3,
#             where={"$and": [
#                 {"title_number": title_number}, 
#                 {"filename": current_document}
#             ]}
#         )
#         if current_results["documents"]:
#             current_doc_context = "\n\n".join(current_results["documents"][0])

#         # Search in the REST of the case documents
#         other_results = case_collection.query(
#             query_texts=[issue],
#             n_results=3,
#             where={"$and": [
#                 {"title_number": title_number}, 
#                 {"filename": {"$ne": current_document}} # Exclude current doc
#             ]}
#         )
#         if other_results["documents"]:
#             other_docs_context = "\n\n".join(other_results["documents"][0])

#     else:
#         # Fallback: If no document is open, search everything
#         results = case_collection.query(
#             query_texts=[issue],
#             n_results=5,
#             where={"title_number": title_number}
#         )
#         if results["documents"]:
#             other_docs_context = "\n\n".join(results["documents"][0])


#     # 3. The newly structured priority prompt for Enquiries
#     enquiry_system_prompt = f"""You are a senior UK conveyancing solicitor drafting formal legal enquiries to the seller's solicitors.

# TASK:
# Draft a formal enquiry combining the standard wording from the FORMAT LIBRARY with the specific facts from the CASE CONTEXT.

# PRIORITY RULES:
# 1. When filling in dates, names, or values, look FIRST in the [CASE FACTS - CURRENTLY OPEN DOCUMENT].
# 2. If the missing facts are not there, look in the [CASE FACTS - OTHER DOCUMENTS].
# 3. Tone must be highly formal, polite, but firm. Draft ONLY the text of the enquiry itself.
# 4. If the case context completely lacks the necessary facts to complete the standard format, state: "INCOMPLETE FACTS: Cannot draft enquiry. Missing [State what is missing]."

# FORMAT LIBRARY REFERENCE:
# {format_library_context if format_library_context else "No standard format found. Draft manually based on facts."}

# [CASE FACTS - CURRENTLY OPEN DOCUMENT]
# {current_doc_context if current_doc_context else "None available."}

# [CASE FACTS - OTHER DOCUMENTS]
# {other_docs_context if other_docs_context else "None available."}
# """



#     # Build messages with history for memory
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     # Add conversation history
#     for msg in history[:-1]:
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     # Add current request
#     groq_messages.append({
#         "role": "user",
#         "content": f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
#     })

#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "enquiry",
#         "enquiry_code": enquiry_code,
#         "enquiry_topic": enquiry_topic,
#         "generated_text": response.choices[0].message.content,
#         "title_number": title_number
#     }


# chatbot.py — handles all AI chat functionality
# KEY FIX: ChromaDB metadata stores the document name under "source" (set in chunker.py),
# NOT "filename". All where-filters must use "source" to match correctly.

# import os
# from groq import Groq
# from dotenv import load_dotenv
# # Import the shared embedding model + both ChromaDB collections
# from embeddings import case_collection, format_collection, model

# load_dotenv()

# # Initialise the Groq LLM client using the API key from environment variables
# client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# def ask_question(question: str, title_number: str, history: list = [], current_document: str = None) -> dict:
#     """
#     General Q&A with conversation memory and Context-Weighted RAG.
#     If a document is currently open in the viewer, we prioritise chunks from that doc.
#     Falls back to all case docs if no specific doc is open.
#     """
#     title_number = title_number.upper()
#     current_doc_context = ""
#     other_docs_context = ""

#     # Encode the question into a vector using our BAAI/bge model.
#     # We MUST do this manually here — passing query_texts would use ChromaDB's
#     # default embedding model (384d) which mismatches our stored vectors (768d → crash).
#     query_embedding = model.encode([question]).tolist()

#     if current_document:
#         # ── STEP 1: Search ONLY the currently open document ──────────────────
#         # FIX: metadata key is "source" (set in chunker.py), NOT "filename"
#         current_document = current_document.strip()
#         current_results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=8,
#             where={"$and": [
#                 {"title_number": title_number},
#                 {"source": current_document}   # ← was "filename", now "source"
#             ]}
#         )
#         # Flatten the nested list ChromaDB returns and join into one block of text
#         if current_results["documents"] and len(current_results["documents"][0]) > 0:
#             current_doc_context = "\n\n".join(current_results["documents"][0])

#         # ── STEP 2: Search all OTHER documents in the same case ───────────────
#         # $ne = "not equal" — excludes the currently open doc
#         other_results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=12,
#             where={"$and": [
#                 {"title_number": title_number},
#                 {"source": {"$ne": current_document}}  # ← was "filename", now "source"
#             ]}
#         )
#         if other_results["documents"] and len(other_results["documents"][0]) > 0:
#             other_docs_context = "\n\n".join(other_results["documents"][0])

#     else:
#         # ── FALLBACK: No document open — search everything in the case ────────
#         results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=20,
#             where={"title_number": title_number}
#         )
#         if results["documents"] and len(results["documents"][0]) > 0:
#             other_docs_context = "\n\n".join(results["documents"][0])

#     # Build the system prompt with two clearly labelled context sections.
#     # The LLM is instructed to prefer the open document before falling back.
#     system_prompt = f"""You are an expert UK conveyancing legal assistant. You are reading OCR-extracted text from scanned legal documents — the text may contain garbled characters, broken formatting, and OCR noise. Your job is to intelligently interpret this imperfect text and extract the correct information.
 
# RULES:
# 1. Always attempt to answer using the [CURRENTLY OPEN DOCUMENT] first.
# 2. Only use [OTHER DOCUMENTS] if the answer is completely absent from the open document.
# 3. OCR text is often noisy — if you can reasonably interpret a value (address, name, date, number) from the context despite formatting issues, do so. Do not refuse just because the text looks messy.
# 4. Give direct, concise answers. No preamble. No "based on the documents". Just the answer.
# 5. If a value is partially legible, give your best interpretation and flag it: e.g. "115 Deepwell Avenue, Sheffield [OCR — verify against original]"
# 6. Only say "I cannot find this information" if the information is genuinely absent from both contexts — not just hard to read.
# 7. Use UK legal terminology.
 
# [CURRENTLY OPEN DOCUMENT]
# {current_doc_context if current_doc_context else "None available."}
 
# [OTHER DOCUMENTS]
# {other_docs_context if other_docs_context else "None available."}
# """

#     # Build the full message list for Groq, including conversation history for memory
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     # Add all previous turns EXCEPT the last user message (we add that separately below)
#     for msg in history[:-1]:
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     # Add the current user question as the final turn
#     groq_messages.append({"role": "user", "content": question})

#     response = client.chat.completions.create(
#         model="openai/gpt-oss-120b",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "question",
#         "answer": response.choices[0].message.content,
#         "title_number": title_number,
#         "chunks_used": 8
#     }


# def raise_enquiry(issue: str, title_number: str, history: list = [], current_document: str = None) -> dict:
#     """
#     Generates a formal UK legal enquiry by combining:
#     - The best matching template from the format library (ChromaDB)
#     - Case-specific facts, prioritising the currently open document
#     """
#     title_number = title_number.upper()
#     # Encode the issue description into a vector for similarity search
#     query_embedding = model.encode([issue]).tolist()

#     # ── STEP 1: Find the best matching enquiry template from the format library ──
#     format_results = format_collection.query(
#         query_embeddings=query_embedding,
#         n_results=1  # Only need the single best match
#     )
#     format_context = ""
#     enquiry_code = "Unknown"
#     enquiry_topic = "Unknown"

#     if format_results["documents"] and len(format_results["documents"][0]) > 0:
#         format_context = format_results["documents"][0][0]  # The template text
#         if format_results["metadatas"] and len(format_results["metadatas"][0]) > 0:
#             best_match = format_results["metadatas"][0][0]
#             enquiry_code = best_match.get("code", "Unknown")
#             enquiry_topic = best_match.get("topic", "Unknown")

#     # ── STEP 2: Gather case facts, prioritising the open document ─────────────
#     current_doc_context = ""
#     other_docs_context = ""

#     if current_document:
#         # FIX: metadata key is "source" (set in chunker.py), NOT "filename"
#         current_document = current_document.strip()
#         current_results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=3,
#             where={"$and": [
#                 {"title_number": title_number},
#                 {"source": current_document}   # ← was "filename", now "source"
#             ]}
#         )
#         if current_results["documents"] and len(current_results["documents"][0]) > 0:
#             current_doc_context = "\n\n".join(current_results["documents"][0])

#         # Search remaining case documents excluding the open one
#         other_results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=5,
#             where={"$and": [
#                 {"title_number": title_number},
#                 {"source": {"$ne": current_document}}  # ← was "filename", now "source"
#             ]}
#         )
#         if other_results["documents"] and len(other_results["documents"][0]) > 0:
#             other_docs_context = "\n\n".join(other_results["documents"][0])

#     else:
#         # Fallback: no open document — search the whole case
#         results = case_collection.query(
#             query_embeddings=query_embedding,
#             n_results=8,
#             where={"title_number": title_number}
#         )
#         if results["documents"] and len(results["documents"][0]) > 0:
#             other_docs_context = "\n\n".join(results["documents"][0])

#     # Build the enquiry generation prompt
#     system_prompt = f"""You are a senior UK conveyancing solicitor drafting formal legal enquiries to the seller's solicitors. You are reading OCR-extracted text from scanned legal documents — the text may be garbled or imperfectly formatted. Interpret it intelligently.
 
# TASK:
# Using the FORMAT LIBRARY template as your base, draft a formal legal enquiry populated with real facts from the case documents.
 
# RULES:
# 1. Use the FORMAT LIBRARY as the structural template and legal wording base.
# 2. Fill in all dates, names, addresses and values using facts from [CURRENTLY OPEN DOCUMENT] first, then [OTHER DOCUMENTS].
# 3. OCR text is noisy — interpret values intelligently even if formatting is broken.
# 4. Output ONLY the enquiry text itself. No covering note, no "Dear Sirs", no sign-off, no explanation.
# 5. For any value you cannot find, insert [PLEASE COMPLETE] inline.
# 6. Never refuse to draft — always produce the best possible enquiry from available facts.
# 7. Use formal UK conveyancing language throughout.
 
# FORMAT LIBRARY:
# {format_context if format_context else "No matching template found — draft the enquiry from scratch based on the issue and case facts."}
 
# [CURRENTLY OPEN DOCUMENT]
# {current_doc_context if current_doc_context else "None available."}
 
# [OTHER DOCUMENTS]
# {other_docs_context if other_docs_context else "None available."}
# """

#     # Build Groq message list with full conversation history for memory
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     # Add all previous turns except the last (added separately below)
#     for msg in history[:-1]:
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     # The current request, including the matched enquiry code and topic for context
#     groq_messages.append({
#         "role": "user",
#         "content": f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
#     })

#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "enquiry",
#         "enquiry_code": enquiry_code,
#         "enquiry_topic": enquiry_topic,
#         "generated_text": response.choices[0].message.content,
#         "title_number": title_number
#     }


# # chatbot.py — handles all AI chat functionality

# import os
# from groq import Groq
# from dotenv import load_dotenv
# from embeddings import search_case, search_formats

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# def ask_question(question: str, title_number: str, history: list = [], current_document: str = None) -> dict:
#     """
#     General Q&A with conversation memory
#     history is the full list of previous messages
#     """

#     # Search case documents for relevant chunks
#     search_results = search_case(
#         query=question,
#         title_number=title_number.upper(),
#         n_results=15
#     )
    
#     relevant_chunks = search_results["documents"][0] if search_results["documents"] else []
#     context = "\n\n".join(relevant_chunks)

#     system_prompt = f"""You are a UK conveyancing legal assistant.
# You help solicitors and legal employees understand property documents.
# Answer questions based ONLY on the context provided below.
# If the answer is not in the context, say "I cannot find that information in this document."
# Be precise, professional and detailed in your answers.
# Always provide complete information — do not give short answers.
# Use UK legal terminology.

# DOCUMENT CONTEXT:
# {context}"""

#     # Build messages array with full history
#     # This gives Groq memory of the whole conversation
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     # Add previous messages from history (excluding the current question)
#     for msg in history[:-1]:  # exclude last message as we add it separately
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     # Add current question
#     groq_messages.append({"role": "user", "content": question})

#     response = client.chat.completions.create(
#         model="openai/gpt-oss-120b",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "question",
#         "answer": response.choices[0].message.content,
#         "title_number": title_number,
#         "chunks_used": len(relevant_chunks)
#     }


# def raise_enquiry(issue: str, title_number: str, history: list = [], current_document: str = None) -> dict:
#     """
#     Generates case-specific enquiry text with conversation memory
#     """

#     # Search format library for matching enquiry template
#     format_results = search_formats(query=issue, n_results=2)
#     format_chunks = format_results["documents"][0] if format_results["documents"] else []
#     format_metadata = format_results["metadatas"][0] if format_results["metadatas"] else []

#     # Search case documents for relevant facts
#     case_results = search_case(
#         query=issue,
#         title_number=title_number.upper(),
#         n_results=5
#     )
#     case_chunks = case_results["documents"][0] if case_results["documents"] else []

#     format_context = "\n\n".join(format_chunks)
#     case_context = "\n\n".join(case_chunks)

#     best_match = format_metadata[0] if format_metadata else {}
#     enquiry_code = best_match.get("code", "Unknown")
#     enquiry_topic = best_match.get("topic", "Unknown")

#     system_prompt = f"""You are a UK conveyancing legal assistant at a solicitors firm.
# Your job is to generate formal legal enquiry text to be sent to the seller's solicitors.
# Use professional UK conveyancing language throughout.
# Generate ONLY the enquiry text — no explanations, no preamble, no sign-off.
# Replace placeholders like (year), (insert date), (insert name) with actual values from the case facts.
# If you cannot find a specific value, keep the placeholder but flag it with [PLEASE COMPLETE].

# ENQUIRY TEMPLATE:
# {format_context}

# CASE FACTS:
# {case_context}"""

#     # Build messages with history for memory
#     groq_messages = [{"role": "system", "content": system_prompt}]

#     for msg in history[:-1]:
#         groq_messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })

#     groq_messages.append({
#         "role": "user",
#         "content": f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
#     })

#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=groq_messages,
#         max_tokens=2048
#     )

#     return {
#         "type": "enquiry",
#         "enquiry_code": enquiry_code,
#         "enquiry_topic": enquiry_topic,
#         "generated_text": response.choices[0].message.content,
#         "title_number": title_number
#     }

# chatbot.py — handles all AI chat functionality

import os
from groq import Groq
from dotenv import load_dotenv
from embeddings import case_collection, format_collection, model

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_current_document_context(query_embedding: list, title_number: str, current_document: str, max_chunks: int = 5) -> list:
    """Fetches chunks STRICTLY from the currently open document."""
    current_document = current_document.strip()
    
    results = case_collection.query(
        query_embeddings=query_embedding,
        n_results=max_chunks,
        where={
            "$and": [
                {"title_number": {"$eq": title_number.upper()}}, # <-- ADDED $eq HERE
                {"source": {"$eq": current_document}}
            ]
        },
        include=["documents"]
    )
    
    if results["documents"] and len(results["documents"][0]) > 0:
        return [f"[Source: {current_document}]\n{doc}" for doc in results["documents"][0]]
    return []


def get_diverse_context(query_embedding: list, title_number: str, max_per_doc: int = 4, total_max: int = 15, exclude_document: str = None) -> list:
    """Fetches chunks from MULTIPLE documents, optionally excluding the open document."""
    where_clause = {"title_number": {"$eq": title_number.upper()}}
    
    # If a document is open, we exclude it from this fallback search
    if exclude_document:
        where_clause = {
            "$and": [
                {"title_number": {"$eq": title_number.upper()}}, # <-- ADDED $eq HERE
                {"source": {"$ne": exclude_document.strip()}}
            ]
        }

    # Cast a wide net (50 chunks)
    results = case_collection.query(
        query_embeddings=query_embedding,
        n_results=50,
        where=where_clause,
        include=["documents", "metadatas"]
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    diverse_chunks = {}

    # Group by document to prevent starvation
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "Unknown_Document")
        if source not in diverse_chunks:
            diverse_chunks[source] = []
            
        if len(diverse_chunks[source]) < max_per_doc:
            diverse_chunks[source].append(f"[Source: {source}]\n{doc}")

    final_chunks = []
    for source_chunks in diverse_chunks.values():
        final_chunks.extend(source_chunks)

    # Cap to save Groq API tokens
    return final_chunks[:total_max]


def ask_question(question: str, title_number: str, history: list = [], current_document: str = None) -> dict:
    """
    General Q&A with Context-Weighted RAG.
    Returns the answer text plus a deduplicated list of source filenames
    so the frontend can render them as clickable document buttons.
    """
    query_embedding = model.encode([question]).tolist()
    
    current_doc_chunks = []
    other_doc_chunks = []

    if current_document:
        # 1. Look in the open document FIRST
        current_doc_chunks = get_current_document_context(query_embedding, title_number, current_document, max_chunks=5)
        # 2. Look in diverse OTHER documents
        other_doc_chunks = get_diverse_context(query_embedding, title_number, max_per_doc=3, total_max=10, exclude_document=current_document)
    else:
        # Fallback: Just look everywhere diversely
        other_doc_chunks = get_diverse_context(query_embedding, title_number, max_per_doc=4, total_max=15)

    current_context = "\n\n".join(current_doc_chunks)
    other_context = "\n\n".join(other_doc_chunks)

    # ── Build a set of valid source names from retrieved chunks ─────────────
    # Used after the LLM responds to validate any filenames it mentions,
    # ensuring we never surface a hallucinated filename as a clickable button.
    valid_sources = set()
    for chunk in (current_doc_chunks + other_doc_chunks):
        if chunk.startswith("[Source: "):
            end = chunk.index("]")
            valid_sources.add(chunk[9:end])  # strip "[Source: " prefix

    system_prompt = f"""You are a UK conveyancing legal assistant. You are reviewing OCR-extracted legal property documents.
Answer questions based ONLY on the context provided below.

PRIORITY RULES:
1. FIRST, attempt to answer the question using ONLY the facts in the [CURRENTLY OPEN DOCUMENT CONTEXT].
2. If the answer is completely missing from the open document, fallback to the [OTHER CASE DOCUMENTS CONTEXT].
3. Give direct, precise answers using UK legal terminology. Do not say "Based on the documents...".
4. ALWAYS cite the [Source: filename] and [InPage Ref.: Heading Under the text is present] where you found the answer strictly in the format mentioned.
5. If the answer is in neither context, reply: "I cannot find this information in the case documents."

[CURRENTLY OPEN DOCUMENT CONTEXT]
{current_context if current_context else "None available."}

[OTHER CASE DOCUMENTS CONTEXT]
{other_context if other_context else "None available."}"""

    groq_messages = [{"role": "system", "content": system_prompt}]
    for msg in history[:-1]:  
        groq_messages.append({"role": msg["role"], "content": msg["content"]})
    groq_messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=groq_messages,
        max_tokens=2048
    )

    answer_text = response.choices[0].message.content

    # ── Extract only sources the LLM actually cited in its answer ────────────
    # The system prompt instructs the LLM to write [Source: filename] inline.
    # We regex-scan the answer for those tags, deduplicate in order of first
    # mention, then cross-check against valid_sources so hallucinated filenames
    # never appear as clickable buttons.
    import re
    mentioned_sources = []
    seen_mentioned = set()
    for match in re.finditer(r'\[Source:\s*([^\]]+)\]', answer_text):
        filename = match.group(1).strip()
        # Only surface filenames that were actually in the retrieved chunks
        if filename in valid_sources and filename not in seen_mentioned:
            seen_mentioned.add(filename)
            mentioned_sources.append(filename)

    return {
        "type": "question",
        "answer": answer_text,
        "sources": mentioned_sources,  # only filenames the LLM actually cited
        "title_number": title_number,
        "chunks_used": len(current_doc_chunks) + len(other_doc_chunks)
    }


def raise_enquiry(issue: str, title_number: str, history: list = [], current_document: str = None) -> dict:
    """Generates case-specific enquiry text with Context-Weighted RAG."""
    query_embedding = model.encode([issue]).tolist()

    # 1. Fetch standard format wording
    format_results = format_collection.query(
        query_embeddings=query_embedding,
        n_results=1
    )
    format_context = ""
    enquiry_code, enquiry_topic = "Unknown", "Unknown"
    
    if format_results["documents"] and len(format_results["documents"][0]) > 0:
        format_context = format_results["documents"][0][0]
        if format_results["metadatas"] and len(format_results["metadatas"][0]) > 0:
            best_match = format_results["metadatas"][0][0]
            enquiry_code = best_match.get("code", "Unknown")
            enquiry_topic = best_match.get("topic", "Unknown")

    # 2. Fetch Facts
    current_doc_chunks = []
    other_doc_chunks = []

    if current_document:
        current_doc_chunks = get_current_document_context(query_embedding, title_number, current_document, max_chunks=4)
        other_doc_chunks = get_diverse_context(query_embedding, title_number, max_per_doc=2, total_max=6, exclude_document=current_document)
    else:
        other_doc_chunks = get_diverse_context(query_embedding, title_number, max_per_doc=3, total_max=8)

    current_context = "\n\n".join(current_doc_chunks)
    other_context = "\n\n".join(other_doc_chunks)

    system_prompt = f"""You are a UK conveyancing legal assistant at a solicitors firm.
# Your job is to generate formal legal enquiry text to be sent to the seller's solicitors.
# Use professional UK conveyancing language throughout.
# Generate ONLY the enquiry text — no explanations, no preamble, no sign-off.
# Replace placeholders like (year), (insert date), (insert name) with actual values from the case facts.
# If you cannot find a specific value, keep the placeholder but flag it with [PLEASE COMPLETE].

FORMAT LIBRARY TEMPLATE:
{format_context if format_context else "No template found. Draft manually based on facts."}

[CASE FACTS - CURRENTLY OPEN DOCUMENT]
{current_context if current_context else "None available."}

[CASE FACTS - OTHER DOCUMENTS]
{other_context if other_context else "None available."}"""

    groq_messages = [{"role": "system", "content": system_prompt}]
    for msg in history[:-1]:
        groq_messages.append({"role": msg["role"], "content": msg["content"]})
    groq_messages.append({
        "role": "user",
        "content": f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
    })

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=groq_messages,
        max_tokens=2048
    )

    return {
        "type": "enquiry",
        "enquiry_code": enquiry_code,
        "enquiry_topic": enquiry_topic,
        "generated_text": response.choices[0].message.content,
        "title_number": title_number
    }