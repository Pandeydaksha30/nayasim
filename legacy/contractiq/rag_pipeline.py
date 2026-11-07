import os
import shutil

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

CHROMA_DIR = "chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # free, runs locally, ONNX-optimized for low memory
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


_embeddings = None


def get_embeddings() -> FastEmbedEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL, threads=1)
    return _embeddings


_llm = None


def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        _llm = ChatGroq(model=GROQ_MODEL, temperature=0.3, api_key=api_key)
    return _llm


# ── Loading & chunking ──

def _load_document(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".docx":
        loader = Docx2txtLoader(file_path)
    elif ext in (".txt", ".md"):
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
    return loader.load()


def ingest_document(file_path: str, doc_id: str) -> int:
    """Parse, chunk, embed, and persist a document under a Chroma collection
    named after doc_id. Returns the number of chunks stored."""
    docs = _load_document(file_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    if not chunks:
        raise ValueError("No extractable text found in document.")

    persist_dir = os.path.join(CHROMA_DIR, doc_id)
    vectorstore = Chroma(
        collection_name=doc_id,
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )
    vectorstore.add_documents(chunks)
    return len(chunks)


def _get_vectorstore(doc_id: str) -> Chroma:
    persist_dir = os.path.join(CHROMA_DIR, doc_id)
    if not os.path.isdir(persist_dir):
        raise ValueError(f"No document found for doc_id='{doc_id}'. Upload it first.")
    return Chroma(
        collection_name=doc_id,
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )


def delete_document(doc_id: str) -> None:
    persist_dir = os.path.join(CHROMA_DIR, doc_id)
    if os.path.isdir(persist_dir):
        try:
            vectorstore = Chroma(
                collection_name=doc_id,
                embedding_function=get_embeddings(),
                persist_directory=persist_dir,
            )
            vectorstore.delete_collection()
        finally:
            shutil.rmtree(persist_dir, ignore_errors=True)


# ── Retrieval + generation ──

SYSTEM_PROMPT = """You are a legal document analyst. Answer the user's question using \
ONLY the contract excerpts provided below.

Rules:
- Use plain, simple language — no legalese
- When relevant, mention which excerpt you're referencing (e.g. "Excerpt 2 says...")
- If asked what happens if someone does X, explain the consequences clearly
- If asked who benefits, compare both parties fairly
- Flag any unfair, one-sided, or risky clauses when relevant
- If the excerpts don't cover something, say so clearly rather than guessing

--- CONTRACT EXCERPTS ---
{context}
--- END EXCERPTS ---"""


def get_answer(doc_id: str, question: str, history: list | None = None, k: int = 4) -> dict:
    """Embed the question, retrieve the top-k most similar chunks from this
    document's vector store, and ask Groq to answer grounded in them."""
    history = history or []
    vectorstore = _get_vectorstore(doc_id)

    # similarity_search_with_score returns (Document, distance) pairs.
    # Chroma's default distance is cosine distance, so smaller = more similar;
    # we convert to an approximate 0-1 "relevance" score for display purposes only.
    results = vectorstore.similarity_search_with_score(question, k=k)

    context = "\n\n---\n\n".join(
        f"[Excerpt {i + 1}] {doc.page_content}" for i, (doc, _score) in enumerate(results)
    )
    sources = [
        {
            "excerpt": i + 1,
            "preview": doc.page_content[:200],
            "relevance_score": round(max(0.0, 1 - score), 3),
        }
        for i, (doc, score) in enumerate(results)
    ]

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
    for msg in history[-6:]:
        role = msg.get("role", "user")
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": question})

    response = get_llm().invoke(messages)

    return {"answer": response.content, "sources": sources}


def analyze_benefits(doc_id: str) -> str:
    """Run the chunk-extract-then-synthesize pipeline to identify benefits and obligations."""
    vectorstore = _get_vectorstore(doc_id)
    
    # Retrieve top 5 most relevant chunks to benefits and obligations
    query = "benefits obligations rights liabilities penalties"
    results = vectorstore.similarity_search(query, k=5)
    
    CHUNK_EXTRACTION_PROMPT = """Extract ALL benefits, obligations, and key clauses from this contract section for EACH party involved.
For each item found, provide:
- The party name (e.g., Landlord, Tenant, Buyer, Seller)
- A brief description of the benefit or obligation
- The exact clause text or section reference
- A significance score from 1-10

Format each finding as a line like: PARTY | BENEFIT_DESCRIPTION | CLAUSE_REFERENCE | SCORE
If this section contains no relevant benefits or obligations, respond with NO_RELEVANT_INFO.

--- DOCUMENT CHUNK ---
{chunk}
--- END CHUNK ---"""
    
    llm = get_llm()
    chunk_results = []
    
    # Process sequentially to avoid free-tier rate limits on Groq
    for doc in results:
        messages = [
            {"role": "system", "content": "You are a legal document analyst specialized in extracting structured information from contract sections."},
            {"role": "user", "content": CHUNK_EXTRACTION_PROMPT.format(chunk=doc.page_content)}
        ]
        try:
            resp = llm.invoke(messages)
            if "NO_RELEVANT_INFO" not in resp.content:
                chunk_results.append(resp.content)
        except Exception as e:
            print(f"Warning: Failed to extract from chunk: {e}")
            
    if not chunk_results:
        return "[]"
        
    aggregated_extractions = "\n\n---\n\n".join(chunk_results)
    
    SYNTHESIS_PROMPT = f"""You have received raw extracted benefits and obligations from multiple sections of a legal contract. 
Your job is to synthesize these into a clean, deduplicated JSON array.

Here are the raw extractions from the document analysis:

{aggregated_extractions}

Now produce the final output as a JSON array with the following format (and nothing else before or after the JSON):
[
  {{"party": "Party A (use actual name from document)", "benefit": "Brief benefit description", "clause": "The exact clause text or section reference", "score": 8}},
  {{"party": "Party B (use actual name from document)", "benefit": "Brief benefit description", "clause": "The exact clause text or section reference", "score": 7}}
]

Rules:
- Include 3-5 benefits per party
- Deduplicate similar benefits across chunks
- Use actual party names from the document
- Score should be 1-10 indicating significance
- Each item MUST use the exact key "benefit" (do NOT use keys like "obligation" or "description" for the description field; put all findings under the "benefit" key)
- Ensure the JSON is valid and parseable"""

    synthesis_messages = [
        {"role": "system", "content": "You are a legal contract analyst. Produce only valid JSON output."},
        {"role": "user", "content": SYNTHESIS_PROMPT}
    ]
    
    final_response = llm.invoke(synthesis_messages)
    return final_response.content
