# Convey-AI Entity-Relationship Diagram (ERD)

This document outlines the data model for the Convey-AI platform. The system uses a hybrid database architecture:
1. **Supabase (PostgreSQL)** for structured, relational metadata and state.
2. **ChromaDB (Vector DB)** for semantic search over unstructured text and document chunks.

```mermaid
erDiagram
    %% SUPABASE (PostgreSQL) SCHEMA
    
    CASES {
        uuid id PK
        varchar title_number "UNIQUE"
        varchar status "e.g., active"
        timestamp created_at
    }

    CASE_DOCUMENTS {
        uuid id PK
        uuid case_id FK "References CASES.id"
        varchar title_number "Denormalized for quick access"
        varchar doc_type "e.g., TA6, TA7, OCE, TR1, EPC"
        varchar filename
        varchar file_url
        boolean processed "True when OCR & embedding is complete"
        timestamp created_at
    }

    %% CHROMADB (Vector Database) COLLECTIONS
    %% Represented here as entities to show relationships

    CHROMA_CASE_DOCUMENTS {
        string id PK "Format: {title_number}_{filename}_chunk_{i}"
        vector embedding "BAAI/bge-large-en-v1.5 vector"
        text document "The actual text chunk"
        json metadata "Contains: title_number, source, chunk_index"
    }

    CHROMA_FORMAT_LIBRARY {
        string id PK
        vector embedding
        text document "Enquiry text or standard UK legal template"
        json metadata "Contains: topic, enquiry_code, etc."
    }

    CHROMA_CHECKLISTS {
        string id PK
        vector embedding
        text document "Checklist items"
        json metadata "Contains: tenure type, mappings"
    }

    %% RELATIONSHIPS
    
    CASES ||--o{ CASE_DOCUMENTS : "has many"
    
    %% Conceptual relationships bridging SQL and Vector DBs
    CASES ||--o{ CHROMA_CASE_DOCUMENTS : "chunks belonging to (via title_number)"
    CASE_DOCUMENTS ||--o{ CHROMA_CASE_DOCUMENTS : "chunks extracted from (via source filename)"
```

## Architectural Notes

### PostgreSQL (Supabase)
*   **`cases`**: The root entity for a conveyancing matter. Identified primarily by the UK Land Registry `title_number` (e.g., "EX332661"). 
*   **`case_documents`**: Stores metadata about uploaded files. The actual physical files are stored in a local directory (`data/processed_pdfs`) on the Railway volume, while the metadata points to them.

### Vector DB (ChromaDB)
*   **`case_documents` (Collection)**: When a document is processed, its text is chunked and stored here. The `title_number` in the metadata allows the RAG pipeline to retrieve chunks strictly belonging to the active case, preventing data leakage between clients.
*   **`format_library` & `checklists` (Collections)**: Global knowledge bases. These store the standard legal texts, rules, and enquiry formats that the AI uses to evaluate case documents and draft responses. These are not tied to any specific case.
