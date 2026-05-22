# zip_processor.py — handles contract pack ZIP uploads
# Unpacks ZIP, identifies document types, processes each PDF

import zipfile      # built into Python — handles ZIP files
import os
import tempfile     # for creating temp folders during processing
import shutil       # for deleting temp folders after processing

# Keyword mapping — looks at filename to guess document type
# Add more keywords as you learn your firm's naming conventions
DOC_TYPE_KEYWORDS = {
    "TA6": ["ta6", "property information", "pif", "seller"],
    "TA7": ["ta7", "leasehold", "fittings", "contents", "fcf"],
    "TA10": ["ta10", "fittings and contents"],
    "TR1": ["tr1", "transfer"],
    "OCE": ["official copy", "oce", "title register", "hmlr"],
    "LEASE": ["lease", "underlease", "tenancy"],
    "EPC": ["epc", "energy performance"],
    "CONTRACT": ["contract", "draft contract"],
    "SEARCHES": ["search", "drainage", "environmental", "local authority"],
    "MORTGAGE": ["mortgage", "charge", "lender"],
}

def identify_doc_type(filename: str) -> str:
    """
    Guesses document type from filename
    Returns the doc type string or 'OTHER' if no match found
    """
    filename_lower = filename.lower()

    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in filename_lower:
                return doc_type

    return "OTHER"  # default if no keyword matches


def extract_zip(zip_bytes: bytes) -> list:
    """
    Takes a ZIP file as bytes
    Extracts all PDFs and returns list of (filename, pdf_bytes, doc_type)
    """
    extracted = []

    # Create a temp directory to extract files into
    temp_dir = tempfile.mkdtemp()

    try:
        # Write zip bytes to a temp file
        zip_path = os.path.join(temp_dir, "contract_pack.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        # Open and extract the ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Walk through extracted files and find all PDFs
        for root, dirs, files in os.walk(temp_dir):
            for filename in files:
                # Only process PDF files
                if filename.lower().endswith(".pdf"):
                    file_path = os.path.join(root, filename)

                    # Read the PDF bytes
                    with open(file_path, "rb") as f:
                        pdf_bytes = f.read()

                    # Guess the document type from filename
                    doc_type = identify_doc_type(filename)

                    extracted.append({
                        "filename": filename,
                        "pdf_bytes": pdf_bytes,
                        "doc_type": doc_type
                    })

        print(f"Extracted {len(extracted)} PDFs from ZIP")
        return extracted

    finally:
        # Always clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)