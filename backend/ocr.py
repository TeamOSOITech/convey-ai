# ocr.py — handles all OCR related tasks

import ocrmypdf # type: ignore
import fitz # type: ignore
import tempfile
import os
from PIL import ImageFile # type: ignore

ImageFile.LOAD_TRUNCATED_IMAGES = True

# This is the folder where we permanently save OCR'd PDFs
DATA_DIR = os.getenv("DATA_DIR", "./data")
PROCESSED_FOLDER = f"{DATA_DIR}/processed_pdfs"

def process_pdf(input_pdf_bytes: bytes, filename: str) -> dict:
    """
    Takes a PDF as raw bytes and original filename
    Returns extracted text + saves the selectable PDF permanently
    """

    # Step 1: Save uploaded bytes to a temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as input_file:
        input_file.write(input_pdf_bytes)
        input_path = input_file.name

    # Step 2: Build the permanent output path using original filename
    # e.g. processed_pdfs/Lease4_ocr.pdf
    # Handle both uppercase and lowercase PDF extensions
    # Remove any existing _ocr suffix first, then add it cleanly
    clean_filename = filename\
        .replace(" ", "_")\
        .replace(",", "")\
        .replace("(", "")\
        .replace(")", "")

    # Handle both uppercase and lowercase extensions
    if clean_filename.upper().endswith(".PDF"):
        clean_filename = clean_filename[:-4]  # remove extension

    # Remove any existing _ocr suffix to avoid double _ocr_ocr
    if clean_filename.endswith("_ocr"):
        clean_filename = clean_filename[:-4]

    # Add _ocr.pdf cleanly
    clean_filename = clean_filename + "_ocr.pdf"
    output_path = os.path.join(PROCESSED_FOLDER, clean_filename)

    # Step 3: Make sure the processed_pdfs folder exists
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    try:
        # Step 4: Run OCR — reads scanned images and adds real text layer
        ocrmypdf.ocr(
            input_path,
            output_path,
            force_ocr=True,
            language="eng",
            optimize=0,
            oversample=300,  # minimal memory usage for free tier
            jobs=1,         # single threaded to reduce memory
        )

        # Step 5: Extract text from the OCR'd PDF
        extracted_text = ""
        pdf_document = fitz.open(output_path)
        page_count = len(pdf_document)

        for page in pdf_document:
            extracted_text += page.get_text()

        pdf_document.close()

        return {
            "success": True,
            "text": extracted_text,
            "pages": page_count,
            "saved_pdf": output_path    # path where the selectable PDF is saved
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        # Step 6: Only delete the temp INPUT file
        # We keep the output PDF permanently this time
        if os.path.exists(input_path):
            os.remove(input_path)