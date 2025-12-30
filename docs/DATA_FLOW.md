# Data Flow Documentation

## 1. Document Ingestion Pipeline
This pipeline describes how raw files are transformed into searchable vector embeddings.

```mermaid
sequenceDiagram
    participant User
    participant API as Ingestion API
    participant Parser as MarkItDown/Parser
    participant Chunker as Hierarchical Chunker
    participant Embed as Embedding Model (Ollama)
    participant DB as PGVector Database

    User->>API: Upload File (PDF/DOCX)
    API->>Parser: Parse File Content
    Parser-->>API: Extracted Text (Markdown)
    API->>Chunker: Split Text into Hierarchical Chunks
    Chunker-->>API: List of Chunks (Child + Parent Summary)
    
    loop For Each Chunk
        API->>Embed: Generate Embedding (Chunk Text)
        Embed-->>API: Vector[768]
    end

    API->>DB: Store Document Metadata + Chunks + Vectors
    DB-->>API: Confirmation
    API-->>User: Upload Success
```

### Process Details
1. **Upload**: User sends a file via the web interface.
2. **Parsing**: 
   - `MarkItDown` is used to convert binary formats (PDF, DOCX) into clean text/markdown.
   - Text is cleaned to remove artifacts.
3. **Chunking**:
   - **Hierarchical Chunking**: The text is split into larger logical blocks (Parents) and smaller retrieval units (Children).
   - Summaries are generated for parent blocks to enhance context.
4. **Embedding**:
   - Each chunk's content is sent to the local embedding model (e.g., `nomic-embed-text`).
   - A 768-dimensional vector is returned.
5. **Storage**:
   - The original text, the hierarchical relationships (ParentID), and the vectors are stored in the `DocumentChunk` table.

## 2. RAG Retrieval & Chat Pipeline
This pipeline describes how a user question is answered using the knowledge base.

```mermaid
sequenceDiagram
    participant User
    participant Chat as Chat Service
    participant Embed as Embedding Model
    participant DB as Vector Store
    participant LLM as LLM (Ollama)

    User->>Chat: Send Message ("What is X?")
    Chat->>Embed: Embed Query
    Embed-->>Chat: Query Vector
    
    Chat->>DB: Similarity Search (Cosine Distance)
    Note right of DB: Retrieve top K chunks + Parent Context
    DB-->>Chat: Relevant Context Blocks

    Chat->>LLM: Construct Prompt (System + Context + History + User Query)
    loop Stream Response
        LLM-->>Chat: Token
        Chat-->>User: Token via SSE
    end
    
    Chat->>DB: Save Chat History
```

### Process Details
1. **Query Embedding**: The user's message is converted into the same vector space as the documents.
2. **Vector Search**: The system queries the `DocumentChunk` table for vectors with the smallest cosine distance to the query vector.
3. **Context Assembly**: 
   - Retrieved chunks are assembled. 
   - If hierarchical chunking is active, parent summaries may be included to provide broader context.
4. **Prompt Engineering**:
   - A strict System Prompt instructs the LLM to use *only* the provided context.
   - The Context and recent Chat History are combined with the user's query.
5. **Generation**: The LLM generates the response, which is streamed back to the user in real-time.
