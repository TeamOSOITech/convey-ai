# embeddings.py — converts text chunks to vectors and stores them in ChromaDB

import chromadb                                    # our vector database
from sentence_transformers import SentenceTransformer  # embedding model

# Step 1: Load the embedding model
# This runs locally on your machine — text never leaves your computer
# First time this runs it will download the model (~500MB) — wait for it
"""model = SentenceTransformer(
    "BAAI/bge-large-en-v1.5",
    cache_folder="./models"      # saves model here permanently
)"""

model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5",   # smaller model — fits in Railway free tier
    cache_folder="./models"
)

# Step 2: Create a ChromaDB client
# persist_directory means data is saved to disk, not lost when server restarts
client = chromadb.PersistentClient(path="./chroma_db")

# Step 3: Create our 3 collections (namespaces)
# get_or_create means it won't crash if collection already exists

# Collection 1 — case documents (uploaded contract packs)
case_collection = client.get_or_create_collection(
    name="case_documents",
    metadata={"description": "legal case documents uploaded by employees"}
)

# Collection 2 — format library (enquiry texts, TA6, TR1 language etc)
format_collection = client.get_or_create_collection(
    name="format_library",
    metadata={"description": "standard UK legal format templates and enquiry texts"}
)

# Collection 3 — checklists
checklist_collection = client.get_or_create_collection(
    name="checklists",
    metadata={"description": "freehold leasehold checklists and their enquiry mappings"}
)


def store_case_chunks(chunks: list, title_number: str):
    """
    Takes chunks from a case document and stores them in ChromaDB
    title_number is used to identify which case these chunks belong to
    e.g. "EX332661"
    """

    # Step 4: Convert each chunk's text to a vector
    texts = [chunk["text"] for chunk in chunks]        # extract just the text
    embeddings = model.encode(texts).tolist()           # convert to vectors

    # Step 5: Prepare data for ChromaDB
    ids = []         # unique ID for each chunk
    metadatas = []   # metadata for each chunk

    for i, chunk in enumerate(chunks):
        # each chunk needs a unique ID
        ids.append(f"{title_number}_chunk_{i}")

        # store metadata so we can filter by title number later
        metadatas.append({
            **chunk["metadata"],          # spread existing metadata (source, chunk_index etc)
            "title_number": title_number  # add title number so we can filter by case
        })

    # Step 6: Store everything in ChromaDB
    case_collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )

    return {
        "stored": len(chunks),
        "title_number": title_number,
        "collection": "case_documents"
    }


def search_case(query: str, title_number: str, n_results: int = 5):
    """
    Searches for relevant chunks in a specific case
    Returns the top n most relevant chunks
    """

    # Step 7: Convert the search query to a vector
    query_embedding = model.encode([query]).tolist()

    # Step 8: Search ChromaDB for similar vectors
    # where filter means only search within this specific case
    results = case_collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        where={"title_number": title_number}   # only search this case
    )

    return results

def search_formats(query: str, n_results: int = 3):
    """
    Searches format library for relevant enquiry texts
    """
    # Convert query to vector
    query_embedding = model.encode([query]).tolist()

    # Search format_library collection
    results = format_collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )

    return results