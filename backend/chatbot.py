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


import os
from groq import Groq
from dotenv import load_dotenv
# Added 'model' to the import list
from embeddings import case_collection, format_collection, model

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def ask_question(question: str, title_number: str, history: list = [], current_document: str = None) -> dict:
    """
    General Q&A with conversation memory and Context-Weighted RAG
    """
    current_doc_context = ""
    other_docs_context = ""

    # CRITICAL FIX: Encode the text using YOUR specific model before searching
    query_embedding = model.encode([question]).tolist()

    if current_document:
        # 1. Search ONLY in the currently opened document
        current_results = case_collection.query(
            query_embeddings=query_embedding,  # Changed from query_texts
            n_results=5,
            where={"$and": [
                {"title_number": title_number}, 
                {"filename": current_document}
            ]}
        )
        if current_results["documents"] and len(current_results["documents"][0]) > 0:
            current_doc_context = "\n\n".join(current_results["documents"][0])

        # 2. Search in the REST of the case documents
        other_results = case_collection.query(
            query_embeddings=query_embedding, # Changed from query_texts
            n_results=8,
            where={"$and": [
                {"title_number": title_number}, 
                {"filename": {"$ne": current_document}}
            ]}
        )
        if other_results["documents"] and len(other_results["documents"][0]) > 0:
            other_docs_context = "\n\n".join(other_results["documents"][0])
    else:
        # Fallback: Search all documents if none is open
        results = case_collection.query(
            query_embeddings=query_embedding, # Changed from query_texts
            n_results=15,
            where={"title_number": title_number}
        )
        if results["documents"] and len(results["documents"][0]) > 0:
            other_docs_context = "\n\n".join(results["documents"][0])

    system_prompt = f"""You are an expert UK conveyancing legal assistant AI.
Your role is to answer questions based strictly on the extracted case documents. You help solicitors and legal employees understand property documents.

PRIORITY RULES:
1. FIRST, attempt to answer the question using ONLY the facts in the [CURRENTLY OPEN DOCUMENT CONTEXT].
2. If (and only if) the answer is completely missing from the open document, fallback to the [OTHER CASE DOCUMENTS CONTEXT].
3. If the answer is found, state it directly. Never use phrases like "Based on the documents...".
4. If the answer is in neither context, reply: "I cannot find this information in the case documents."
5. Use UK legal terminology.

[CURRENTLY OPEN DOCUMENT CONTEXT]
{current_doc_context if current_doc_context else "None available."}

[OTHER CASE DOCUMENTS CONTEXT]
{other_docs_context if other_docs_context else "None available."}
"""

    groq_messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history[:-1]:
        groq_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
        
    groq_messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=groq_messages,
        max_tokens=2048
    )

    return {
        "type": "question",
        "answer": response.choices[0].message.content,
        "title_number": title_number,
        "chunks_used": 8
    }


def raise_enquiry(issue: str, title_number: str, history: list = [], current_document: str = None) -> dict:
    """
    Generates case-specific enquiry text with conversation memory and Context-Weighted RAG
    """
    # CRITICAL FIX: Encode the text using YOUR specific model before searching
    query_embedding = model.encode([issue]).tolist()

    # 1. Fetch format template
    format_results = format_collection.query(
        query_embeddings=query_embedding, # Changed from query_texts
        n_results=1
    )
    format_context = ""
    enquiry_code = "Unknown"
    enquiry_topic = "Unknown"
    
    if format_results["documents"] and len(format_results["documents"][0]) > 0:
        format_context = format_results["documents"][0][0]
        if format_results["metadatas"] and len(format_results["metadatas"][0]) > 0:
            best_match = format_results["metadatas"][0][0]
            enquiry_code = best_match.get("code", "Unknown")
            enquiry_topic = best_match.get("topic", "Unknown")

    # 2. Fetch context facts
    current_doc_context = ""
    other_docs_context = ""

    if current_document:
        current_results = case_collection.query(
            query_embeddings=query_embedding, # Changed from query_texts
            n_results=3,
            where={"$and": [
                {"title_number": title_number}, 
                {"filename": current_document}
            ]}
        )
        if current_results["documents"] and len(current_results["documents"][0]) > 0:
            current_doc_context = "\n\n".join(current_results["documents"][0])

        other_results = case_collection.query(
            query_embeddings=query_embedding, # Changed from query_texts
            n_results=5,
            where={"$and": [
                {"title_number": title_number}, 
                {"filename": {"$ne": current_document}}
            ]}
        )
        if other_results["documents"] and len(other_results["documents"][0]) > 0:
            other_docs_context = "\n\n".join(other_results["documents"][0])
    else:
        results = case_collection.query(
            query_embeddings=query_embedding, # Changed from query_texts
            n_results=8,
            where={"title_number": title_number}
        )
        if results["documents"] and len(results["documents"][0]) > 0:
            other_docs_context = "\n\n".join(results["documents"][0])

    system_prompt = f"""You are a senior UK conveyancing solicitor drafting formal legal enquiries to the seller's solicitors.

TASK:
Draft a formal enquiry combining the standard wording from the FORMAT LIBRARY with the specific facts from the CASE CONTEXT. You help solicitors and legal employees understand property documents.

PRIORITY RULES:
1. When filling in dates, names, or values, look FIRST in the [CASE FACTS - CURRENTLY OPEN DOCUMENT].
2. If the missing facts are not there, look in the [CASE FACTS - OTHER DOCUMENTS].
3. If you cannot find a specific value, keep the placeholder but flag it with [PLEASE COMPLETE].
4. Tone must be highly formal, polite, but firm. Draft ONLY the text of the enquiry itself.
5. If the case context completely lacks the necessary facts to complete the standard format, state: "INCOMPLETE FACTS: Cannot draft enquiry. Missing [State what is missing]."
6. Use UK legal terminology.

FORMAT LIBRARY REFERENCE:
{format_context if format_context else "No standard format found. Draft manually based on facts."}

[CASE FACTS - CURRENTLY OPEN DOCUMENT]
{current_doc_context if current_doc_context else "None available."}

[CASE FACTS - OTHER DOCUMENTS]
{other_docs_context if other_docs_context else "None available."}
"""

    groq_messages = [{"role": "system", "content": system_prompt}]

    for msg in history[:-1]:
        groq_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    groq_messages.append({
        "role": "user",
        "content": f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
    })

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
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