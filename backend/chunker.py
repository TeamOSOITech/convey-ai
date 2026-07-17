# chunker.py — splits OCR blocks into chunks while preserving coordinates

from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " "]
)

def chunk_page(
    blocks: list,
    source_filename: str,
    title_number: str,
    page: int,
    page_width: float = 1.0,
    page_height: float = 1.0
):
    """
    Splits one PDF page into chunks while preserving the bounding
    box of each chunk for later highlighting.
    
    Args:
        blocks: List of text blocks with bbox coordinates
        source_filename: Name of the source PDF
        title_number: Case reference
        page: Page number
        page_width: Width of the page in points
        page_height: Height of the page in points
    """
    
    # Build one page string while remembering where each block starts
    page_text = ""
    block_positions = []
    
    for block in blocks:
        start = len(page_text)
        page_text += block["text"] + "\n\n"
        end = len(page_text)
        
        # Store bbox as normalized coordinates (0-1)
        bbox = block.get("bbox", [0, 0, 1, 1])
        block_positions.append({
            "start": start,
            "end": end,
            "bbox": [
                bbox[0] / page_width if page_width else bbox[0],
                bbox[1] / page_height if page_height else bbox[1],
                bbox[2] / page_width if page_width else bbox[2],
                bbox[3] / page_height if page_height else bbox[3]
            ]
        })
    
    # Split the page text
    raw_chunks = _splitter.split_text(page_text)
    chunks = []
    search_start = 0
    
    for i, chunk in enumerate(raw_chunks):
        # Find where this chunk begins inside the page
        chunk_start = page_text.find(chunk, search_start)
        if chunk_start == -1:
            chunk_start = search_start
        chunk_end = chunk_start + len(chunk)
        search_start = max(chunk_end - _splitter._chunk_overlap, 0)
        
        # Find every block that overlaps this chunk
        used_boxes = []
        for block in block_positions:
            if block["start"] < chunk_end and block["end"] > chunk_start:
                used_boxes.append(block["bbox"])
        
        # Compute one bbox covering the entire chunk
        if used_boxes:
            x0 = min(b[0] for b in used_boxes)
            y0 = min(b[1] for b in used_boxes)
            x1 = max(b[2] for b in used_boxes)
            y1 = max(b[3] for b in used_boxes)
            bbox = [x0, y0, x1, y1]
        else:
            bbox = None
        
        chunks.append({
            "text": chunk,
            "metadata": {
                "source": source_filename,
                "title_number": title_number,
                "page": page,
                "bbox": bbox,
                "chunk_index": i,
                "total_chunks": len(raw_chunks)
            }
        })
    
    return chunks