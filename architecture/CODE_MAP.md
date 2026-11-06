# VIVA_CODE_MAP.md

A direct "professor asks X → open this file, this line" reference. Line numbers refer to the files
as copied into this `MID_VIVA` folder.

| What professor asks | File | Function / location |
| --- | --- | --- |
| Where is your RAG pipeline? | `backend/rag_pipeline.py` | Complete file |
| Where do you load documents? | `backend/rag_pipeline.py` | `_load_document()` — line 62 |
| Where do you split documents? | `backend/rag_pipeline.py` | `ingest_document()` — line 75; splitter config at lines 80–84 (`chunk_size=1000, chunk_overlap=150`) |
| Where are embeddings generated? | `backend/rag_pipeline.py` | `get_embeddings()` — line 40 |
| Which embedding model? | `backend/rag_pipeline.py` | `EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"` — line 32 |
| Where is the vector DB set up? | `backend/rag_pipeline.py` | `Chroma(...)` — line 91 (in `ingest_document()`) and line 104 (in `_get_vectorstore()`) |
| Where is retrieval (similarity search)? | `backend/rag_pipeline.py` | `similarity_search_with_score(question, k=k)` — line 152, inside `get_answer()` (line 143) |
| Where is the LLM configured/called? | `backend/rag_pipeline.py` | `get_llm()` — line 50 (setup); `get_llm().invoke(messages)` — line 172 (call) |
| Where is the final answer generated? | `backend/rag_pipeline.py` | `get_answer()` — line 143 |
| Where is the grounded system prompt? | `backend/rag_pipeline.py` | `SYSTEM_PROMPT` — line 127 |
| Where is benefits/obligations extraction? | `backend/rag_pipeline.py` | `analyze_benefits()` — line 177 |
| Where do you delete a document's data? | `backend/rag_pipeline.py` | `delete_document()` — line 111 |
| Where are the backend APIs defined? | `backend/main.py` | `/upload` line 51, `/chat` line 75, `/benefits` line 91, `DELETE /document/{doc_id}` line 102, `/health` line 108 |
| Where is CORS configured? | `backend/main.py` | `app.add_middleware(CORSMiddleware, ...)` — line 32 |
| Where does the frontend call the backend to ingest a document? | `frontend/page.tsx` | `ingestToRagBackend()` — line 384; `fetch(\`${RAG_API_URL}/upload\`...)` — line 387 |
| Where does the frontend call the backend to chat? | `frontend/page.tsx` | `fetch(\`${RAG_API_URL}/chat\`...)` — line 572 |
| Where does the frontend call the backend for benefits analysis? | `frontend/page.tsx` | `fetch(\`${RAG_API_URL}/benefits\`...)` — line 609 |
| Where does the frontend extract raw text for the document viewer (separate from RAG)? | `frontend/route.ts` | `POST` handler, whole file |

## Key Snippets

**Chunking configuration** (`backend/rag_pipeline.py`, inside `ingest_document()`):
```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)
```

**Embedding model** (`backend/rag_pipeline.py`):
```python
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
...
_embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL, threads=1)
```

**Retrieval call** (`backend/rag_pipeline.py`, inside `get_answer()`):
```python
results = vectorstore.similarity_search_with_score(question, k=k)   # k defaults to 4
```

**LLM call** (`backend/rag_pipeline.py`, inside `get_answer()`):
```python
_llm = ChatGroq(model=GROQ_MODEL, temperature=0.3, api_key=api_key)   # GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
...
response = get_llm().invoke(messages)
```

**Grounding instruction** (`backend/rag_pipeline.py`, `SYSTEM_PROMPT`):
```text
Answer the user's question using ONLY the contract excerpts provided below.
...
If the excerpts don't cover something, say so clearly rather than guessing
```
