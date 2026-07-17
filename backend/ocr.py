# ocr.py - Add page dimension extraction

def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """
    Process a PDF file: extract text with bounding boxes using OCR.
    Returns page dimensions along with text blocks.
    """
    try:
        import fitz  # PyMuPDF
        
        # Open the PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result = {
            "success": True,
            "pages": [],
            "filename": filename
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