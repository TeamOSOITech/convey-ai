# chatbot.py — handles all AI chat functionality with improved RAG

import os
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv
from embeddings import case_collection, format_collection, model
import re

load_dotenv()

# ── 3-Model Fallback Chain ────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

_MODELS = [
    ("gemini", "gemini-2.5-flash-lite"),                  
    ("gemini", "gemini-2.0-flash-lite"),                  
    ("groq",   "openai/gpt-oss-120b"),                    
]

def call_llm(system_prompt: str, conversation: list, user_message: str) -> str:
    errors = {}
    for provider, model_name in _MODELS:
        try:
            if provider == "gemini":
                return _call_gemini(model_name, system_prompt, conversation, user_message)
            else:
                return _call_groq(model_name, system_prompt, conversation, user_message)
        except Exception as err:
            label = f"{provider}/{model_name}"
            errors[label] = str(err)
            print(f"[chatbot] ⚠ '{label}' failed: {err} — trying next model...")
    error_summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
    raise RuntimeError(f"All 3 LLM models failed. Errors — {error_summary}")

def _call_gemini(model_name: str, system_prompt: str, conversation: list, user_message: str) -> str:
    def _build_history(conv):
        history = []
        for msg in conv:
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})
        return history

    gm = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)
    chat = gm.start_chat(history=_build_history(conversation))
    resp = chat.send_message(user_message)
    return resp.text.strip()

def _call_groq(model_name: str, system_prompt: str, conversation: list, user_message: str) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    response = _groq_client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=2048
    )
    return response.choices[0].message.content.strip()

def get_current_document_context(query_embedding: list, title_number: str, current_document: str, max_chunks: int = 5) -> list:
    """Fetches chunks STRICTLY from the currently open document."""
    current_document = current_document.strip()
    results = case_collection.query(
        query_embeddings=query_embedding,
        n_results=max_chunks,
        where={
            "$and": [
                {"title_number": {"$eq": title_number.upper()}},
                {"source": {"$eq": current_document}}
            ]
        },
        include=["documents", "metadatas"]
    )
    chunks = []
    if results["documents"] and len(results["documents"][0]) > 0:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append({
                "text": doc,
                "metadata": meta
            })
    return chunks

def get_diverse_context(query_embedding: list, title_number: str, max_per_doc: int = 4, total_max: int = 15, exclude_document: str = None) -> list:
    """Fetches chunks from MULTIPLE documents, excluding the open document."""
    where_clause = {"title_number": {"$eq": title_number.upper()}}
    if exclude_document:
        where_clause = {
            "$and": [
                {"title_number": {"$eq": title_number.upper()}},
                {"source": {"$ne": exclude_document.strip()}}
            ]
        }

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

    for doc, meta in zip(docs, metas):
        source = meta.get("source", "Unknown_Document")
        if source not in diverse_chunks:
            diverse_chunks[source] = []
        if len(diverse_chunks[source]) < max_per_doc:
            diverse_chunks[source].append({
                "text": doc,
                "metadata": meta
            })

    final_chunks = []
    for source_chunks in diverse_chunks.values():
        final_chunks.extend(source_chunks)
    return final_chunks[:total_max]

# chatbot.py - Fix the ask_question function

def ask_question(
    question: str,
    title_number: str,
    history: list = [],
    current_document: str = None
) -> dict:
    """
    Ask a question against a case and return citation metadata
    including page and bounding boxes for PDF highlighting.
    """
    query_embedding = model.encode([question]).tolist()
    
    # ----------------------------------------------------------
    # Search Chroma - Context Weighted Retrieval
    # ----------------------------------------------------------
    current_doc_chunks = []
    other_doc_chunks = []
    
    if current_document:
        current_doc_chunks = get_current_document_context(
            query_embedding, title_number, current_document, max_chunks=5
        )
        other_doc_chunks = get_diverse_context(
            query_embedding, title_number, max_per_doc=3, total_max=10, 
            exclude_document=current_document
        )
    else:
        other_doc_chunks = get_diverse_context(
            query_embedding, title_number, max_per_doc=4, total_max=15
        )
    
    # Combine chunks
    all_chunks = current_doc_chunks + other_doc_chunks
    
    if not all_chunks:
        return {
            "type": "question",
            "answer": "I cannot find any documents in this case.",
            "chunks": [],
            "title_number": title_number,
            "chunks_used": 0
        }
    
    # ----------------------------------------------------------
    # Build LLM Context with Citations
    # ----------------------------------------------------------
    context_sections = []
    citations = []  # This will store the citation metadata
    retrieved_chunks = []
    
    for idx, chunk_data in enumerate(all_chunks):
        cid = f"C{idx + 1}"
        meta = chunk_data["metadata"]
        text = chunk_data["text"]
        
        context_sections.append(f"""
[{cid}]
Source: {meta.get('source')}
Page: {meta.get('page')}
Content: {text}
""")
        
        # Store citation with ALL metadata needed for highlighting
        citation = {
            "id": cid,
            "source": meta.get("source"),
            "page": meta.get("page"),
            "bbox": meta.get("bbox"),
            "chunk_index": meta.get("chunk_index")
        }
        citations.append(citation)
        
        retrieved_chunks.append({
            "text": text,
            "metadata": meta
        })
    
    context = "\n".join(context_sections)
    
    # ----------------------------------------------------------
    # THE IMPROVED RAG PROMPT
    # ----------------------------------------------------------
    system_prompt = f"""You are an expert UK conveyancing legal assistant. You are reading OCR-extracted text from scanned legal documents.

CRITICAL RULES - FOLLOW THESE EXACTLY:

1. **ONLY use information explicitly stated in the provided context.**
2. **NEVER assume, infer, or hallucinate information.** If you don't know, say so.
3. **Every factual statement MUST have a citation ID at the end.**
   - Format: [C1], [C2], [C5][C8]
   - Example: "The lease grants rights of support [C2]. The tenant must pay the service charge [C5][C8]."
4. **NEVER use these formats:** [REF1], [1], (Page 4), (Source...), [Source: ...], or 【C1】
5. **ONLY use [C#] format for citations.**
6. **Be precise and direct.** No preamble like "Based on the documents..." or "I can see that..."
7. **Use UK legal terminology** as it appears in the documents.

CONTEXT:
{context}

Remember: Extract facts. Cite every claim with [C#]. Never invent. Be precise.
"""
    
    conversation = [
        {
            "role": msg["role"],
            "content": msg["content"]
        }
        for msg in history[:-1]
    ]
    
    answer = call_llm(
        system_prompt,
        conversation,
        question
    )
    
    # Extract citations from the answer
    seen = set()
    answer_citations = []
    
    # Look for [C#] pattern in the answer
    import re
    citation_matches = re.findall(r'\[C(\d+)\]', answer)
    print(f"[chatbot] Found citations in answer: {citation_matches}")  # Debug log
    
    for idx_str in citation_matches:
        idx = int(idx_str) - 1
        if idx < len(citations):
            cite = citations[idx]
            key = f"{cite['source']}:{cite['page']}"
            if key not in seen:
                answer_citations.append(cite)
                seen.add(key)
    
    print(f"[chatbot] Returning {len(answer_citations)} citations")  # Debug log
    
    return {
        "type": "question",
        "answer": answer,
        "chunks": answer_citations,  # This MUST be populated
        "title_number": title_number,
        "chunks_used": len(retrieved_chunks)
    }

def raise_enquiry(issue: str, title_number: str, history: list = [], current_document: str = None) -> dict:
    """Generates case-specific enquiry text with Context-Weighted RAG."""
    query_embedding = model.encode([issue]).tolist()

    # 1. Fetch standard format wording
    format_results = format_collection.query(
        query_embeddings=query_embedding,
        n_results=1,
        include=["documents", "metadatas"]
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
        current_doc_chunks = get_current_document_context(
            query_embedding, title_number, current_document, max_chunks=4
        )
        other_doc_chunks = get_diverse_context(
            query_embedding, title_number, max_per_doc=2, total_max=6, 
            exclude_document=current_document
        )
    else:
        other_doc_chunks = get_diverse_context(
            query_embedding, title_number, max_per_doc=3, total_max=8
        )

    current_context = "\n\n".join([c["text"] for c in current_doc_chunks])
    other_context = "\n\n".join([c["text"] for c in other_doc_chunks])

    system_prompt = f"""You are a senior UK conveyancing solicitor drafting formal legal enquiries.

TASK:
Using the FORMAT LIBRARY template as your base, draft a formal legal enquiry populated with real facts from the case documents.

RULES:
1. Use the FORMAT LIBRARY as the structural template and legal wording base.
2. Fill in dates, names, addresses using facts from [CURRENTLY OPEN DOCUMENT] first, then [OTHER DOCUMENTS].
3. OCR text is noisy — interpret values intelligently but flag uncertain readings.
4. Output ONLY the enquiry text itself. No covering note, no "Dear Sirs", no explanation.
5. For any value you cannot find, insert [PLEASE COMPLETE] inline.
6. Use formal UK conveyancing language throughout.

FORMAT LIBRARY TEMPLATE:
{format_context if format_context else "No template found. Draft manually based on facts."}

[CASE FACTS - CURRENTLY OPEN DOCUMENT]
{current_context if current_context else "None available."}

[CASE FACTS - OTHER DOCUMENTS]
{other_context if other_context else "None available."}"""

    prior_turns = []
    for msg in history[:-1]:
        prior_turns.append({"role": msg["role"], "content": msg["content"]})

    generated_text = call_llm(
        system_prompt=system_prompt,
        conversation=prior_turns,
        user_message=f"Generate the formal enquiry text for enquiry {enquiry_code} — {enquiry_topic}. Issue: {issue}"
    )

    return {
        "type": "enquiry",
        "enquiry_code": enquiry_code,
        "enquiry_topic": enquiry_topic,
        "generated_text": generated_text,
        "title_number": title_number
    }