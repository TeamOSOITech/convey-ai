# chatbot.py — handles all AI chat functionality

import os
from groq import Groq
from dotenv import load_dotenv
from embeddings import search_case, search_formats

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def ask_question(question: str, title_number: str, history: list = []) -> dict:
    """
    General Q&A with conversation memory
    history is the full list of previous messages
    """

    # Search case documents for relevant chunks
    search_results = search_case(
        query=question,
        title_number=title_number,
        n_results=8
    )
    relevant_chunks = search_results["documents"][0]
    context = "\n\n".join(relevant_chunks)

    system_prompt = f"""You are a UK conveyancing legal assistant.
You help solicitors and legal employees understand property documents.
Answer questions based ONLY on the context provided below.
If the answer is not in the context, say "I cannot find that information in this document."
Be precise, professional and detailed in your answers.
Always provide complete information — do not give short answers.
Use UK legal terminology.

DOCUMENT CONTEXT:
{context}"""

    # Build messages array with full history
    # This gives Groq memory of the whole conversation
    groq_messages = [{"role": "system", "content": system_prompt}]

    # Add previous messages from history (excluding the current question)
    for msg in history[:-1]:  # exclude last message as we add it separately
        groq_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Add current question
    groq_messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=groq_messages,
        max_tokens=2048
    )

    return {
        "type": "question",
        "answer": response.choices[0].message.content,
        "title_number": title_number,
        "chunks_used": len(relevant_chunks)
    }


def raise_enquiry(issue: str, title_number: str, history: list = []) -> dict:
    """
    Generates case-specific enquiry text with conversation memory
    """

    # Search format library for matching enquiry template
    format_results = search_formats(query=issue, n_results=2)
    format_chunks = format_results["documents"][0]
    format_metadata = format_results["metadatas"][0]

    # Search case documents for relevant facts
    case_results = search_case(
        query=issue,
        title_number=title_number,
        n_results=5
    )
    case_chunks = case_results["documents"][0]

    format_context = "\n\n".join(format_chunks)
    case_context = "\n\n".join(case_chunks)

    best_match = format_metadata[0] if format_metadata else {}
    enquiry_code = best_match.get("code", "Unknown")
    enquiry_topic = best_match.get("topic", "Unknown")

    system_prompt = f"""You are a UK conveyancing legal assistant at a solicitors firm.
Your job is to generate formal legal enquiry text to be sent to the seller's solicitors.
Use professional UK conveyancing language throughout.
Generate ONLY the enquiry text — no explanations, no preamble, no sign-off.
Replace placeholders like (year), (insert date), (insert name) with actual values from the case facts.
If you cannot find a specific value, keep the placeholder but flag it with [PLEASE COMPLETE].

ENQUIRY TEMPLATE:
{format_context}

CASE FACTS:
{case_context}"""

    # Build messages with history for memory
    groq_messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in history[:-1]:
        groq_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Add current request
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