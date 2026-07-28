# ocr.py — OCRs uploaded PDFs with Tesseract (via ocrmypdf), then extracts
# word-level text + bounding boxes (needed for PDF highlighting/citations)
# from the OCR'd result via PyMuPDF.
#
# Why OCR is necessary: many documents (e.g. HM Land Registry "official
# copies") are scanned images with no machine-readable text layer at all —
# reading them with PyMuPDF alone returns nothing but the odd digitally-
# stamped footer. force_ocr=True re-OCRs every page regardless of whether
# it already has a text layer, so partially-OCR'd PDFs can't slip through.

import os
import tempfile
import ocrmypdf
import fitz  # PyMuPDF


def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """
    OCRs the PDF, then extracts text with bounding boxes from every page.
    Returns page dimensions/blocks alongside the OCR'd PDF bytes — callers
    should persist ocr_pdf_bytes (the searchable copy), not the raw upload.
    """
    input_path = None
    output_path = None
    try:
        # Step 1: ocrmypdf needs real file paths, not bytes
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as input_file:
            input_file.write(pdf_bytes)
            input_path = input_file.name
        output_path = input_path[:-4] + "_ocr.pdf"

        # Step 2: Run OCR — adds a real, correctly-positioned text layer
        # over the scanned image so PyMuPDF can read it below.
        ocrmypdf.ocr(
            input_path,
            output_path,
            force_ocr=True,   # re-OCR every page, even ones with an existing text layer
            language="eng",   # English legal documents
            optimize=0,       # skip image optimization — faster, avoids errors
            oversample=300,   # higher effective DPI for small/blurry scanned text
            jobs=1,           # single-threaded — Railway's tier has limited CPU/memory
        )

        with open(output_path, "rb") as f:
            ocr_pdf_bytes = f.read()

        # Step 3: Extract text + bounding boxes from the now-OCR'd PDF
        doc = fitz.open(output_path)
        result = {
            "success": True,
            "pages": [],
            "filename": filename,
            "ocr_pdf_bytes": ocr_pdf_bytes,
        }

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get page dimensions in points
            page_width = page.rect.width
            page_height = page.rect.height

            # Extract text with bounding boxes
            blocks = []
            text_instances = page.get_text("words")  # Returns [x0, y0, x1, y1, word, ...]

            # Group words into blocks (simple approach - group by line)
            current_block = {"text": "", "bbox": None}

            for word in text_instances:
                x0, y0, x1, y1, word_text = word[:5]

                if current_block["bbox"] is None:
                    current_block["bbox"] = [x0, y0, x1, y1]
                else:
                    # Expand bbox to include this word
                    current_block["bbox"][0] = min(current_block["bbox"][0], x0)
                    current_block["bbox"][1] = min(current_block["bbox"][1], y0)
                    current_block["bbox"][2] = max(current_block["bbox"][2], x1)
                    current_block["bbox"][3] = max(current_block["bbox"][3], y1)

                current_block["text"] += word_text + " "

                # Check if this is the end of a line or block
                if len(current_block["text"]) > 100 or "\n" in current_block["text"]:
                    blocks.append({
                        "text": current_block["text"].strip(),
                        "bbox": current_block["bbox"]
                    })
                    current_block = {"text": "", "bbox": None}

            # Add any remaining text
            if current_block["text"].strip():
                blocks.append({
                    "text": current_block["text"].strip(),
                    "bbox": current_block["bbox"]
                })

            result["pages"].append({
                "page": page_num + 1,
                "blocks": blocks,
                "width": page_width,
                "height": page_height
            })

        doc.close()
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        # Both are temp copies — the durable copy lives in Supabase Storage
        # once the caller uploads ocr_pdf_bytes, so neither is kept on disk.
        for path in (input_path, output_path):
            if path and os.path.exists(path):
                os.remove(path)
