# routes/smart_extract.py — General-purpose AI document extraction
#
# User selects documents and writes free-form extraction instructions.
# The AI reads each document and returns structured markdown results.
# One file per request — frontend loops sequentially to avoid Vercel 100s timeout.

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from embeddings import case_collection
from auth_utils import require_auth

router = APIRouter()


class SmartExtractRequest(BaseModel):
    title_number: str   # e.g. "EX332661"
    filename:     str   # exact filename as stored in ChromaDB
    instructions: str   # user's free-form extraction rules


@router.post("/smart-extract")
async def smart_extract_route(req: SmartExtractRequest, _user=Depends(require_auth)):
    """
    Runs a user-defined extraction prompt over a single document.
    Fetches all ChromaDB chunks for the file, concatenates them into full_text,
    then asks Gemini to extract whatever the user's instructions describe.
    Returns { filename, result } where result is markdown-formatted output.
    """
    try:
        from title_report import gemini_model

        tn = req.title_number.upper()

        # Fetch every chunk for this specific file
        results = case_collection.get(
            where={
                "$and": [
                    {"title_number": {"$eq": tn}},
                    {"source":       {"$eq": req.filename}}
                ]
            }
        )

        if not results["ids"]:
            return JSONResponse(
                status_code=404,
                content={"detail": f"No content found for '{req.filename}' in case {tn}. Has this document been uploaded and ingested?"}
            )

        # Sort chunks by chunk_index so the text is in reading order
        chunks_with_meta = list(zip(results["documents"], results["metadatas"]))
        chunks_with_meta.sort(key=lambda x: x[1].get("chunk_index", 0))
        full_text = "\n\n".join([chunk for chunk, _ in chunks_with_meta])

        prompt = f"""You are a highly experienced UK legal assistant.
You have been given one legal document and a set of extraction instructions.
Your job is to read the document carefully and extract exactly what the instructions ask for.

EXTRACTION INSTRUCTIONS:
{req.instructions}

RULES:
- Format your output clearly in markdown (use **bold** headings, bullet points, tables where appropriate).
- If a requested piece of information is not present in the document, write: *[Not found in this document]*
- Do not add commentary or waffle — give only what was asked for.
- Be precise. Quote exact text where useful.

DOCUMENT: {req.filename}

DOCUMENT TEXT:
{full_text}"""

        response = gemini_model.generate_content(prompt)
        extraction = response.text.strip()

        return {
            "filename": req.filename,
            "result":   extraction
        }

    except Exception as e:
        print(f"[/smart-extract] Error for {req.filename}: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Extraction failed for '{req.filename}': {str(e)}"}
        )