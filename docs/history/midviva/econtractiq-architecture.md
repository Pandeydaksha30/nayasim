 explains the data flow across the two moving pieces demonstrated in thismid-viva:
the Next.js frontend and the FastAPI + LangChain RAG backend.

## Diagram

```text
                ┌─────────────────┐
                │    Frontend     │
                │    Next.js      │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │    FastAPI      │
                │    Backend      │
                └────────┬────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Document Loader          User Query
              │                     │
              ▼                     ▼
          Chunking              Embedding
              │                     │
              ▼                     │
          Embeddings ◄──────────────┘
              │
              ▼
          ChromaDB
              │
              ▼
      Similarity Search
              │
              ▼
       Relevant Chunks
              │
              ▼
       Groq / LLaMA LLM
              │
              ▼
        Final Response
              │
              ▼
           Frontend
```

