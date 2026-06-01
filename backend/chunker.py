# chunker.py — splits extracted text into smaller chunks for the AI

from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str, source_filename: str) -> list:
    """
    Takes a big block of text and splits it into smaller overlapping chunks
    Returns a list of chunks with metadata
    """

    # Step 1: Create the text splitter
    # chunk_size = max characters per chunk
    # chunk_overlap = how many characters overlap between chunks
    # overlap is important so we don't lose context at the boundaries
    # e.g. if a sentence starts at end of chunk 1, it also appears at start of chunk 2
    splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,    # bigger chunks = more context kept together
    chunk_overlap=200,  # bigger overlap = less chance of losing context
    separators=["\n\n", "\n", ".", " "]
    )

    # Step 2: Split the text into chunks
    raw_chunks = splitter.split_text(text)

    # Step 3: Add metadata to each chunk
    # Metadata tells ChromaDB WHERE this chunk came from
    # Very important for retrieval later
    chunks_with_metadata = []

    for i, chunk in enumerate(raw_chunks):
        chunks_with_metadata.append({
            "text": chunk,                    # the actual chunk text
            "metadata": {
                "source": source_filename,    # which document this came from
                "chunk_index": i,             # position of chunk in document
                "total_chunks": len(raw_chunks)  # total chunks in this document
            }
        })

    return chunks_with_metadata