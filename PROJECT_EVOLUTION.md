# ContractIQ: from mid-viva to final viva

## Problem statement (final)

Home buyers in India sign long builder–buyer agreements they do not fully understand, and when
the builder delays possession they must work out what the contract promised, what they are owed,
and whether a complaint before the Real Estate Regulatory Authority is worth filing. Lawyers'
time is expensive, and general-purpose AI chatbots answer contract questions fluently but
without showing where an answer comes from, invent figures and cite cases that do not exist.

**ContractIQ** started (mid-viva, as eContractIQ) as an AI assistant for understanding a contract:
upload it, ask questions, and see each party's benefits and obligations. For the final viva it
has evolved into a **real-estate contract intelligence and legal dispute support platform**. It
still reads and explains the contract, and now also extracts and verifies the key facts, computes
the buyer's financial claim with deterministic code, retrieves real precedents from public RERA
orders, simulates a hearing with advocate, defence and judge agents, and drafts the complaint
and report.

The design rule throughout: **nothing is shown unless it can be traced to a source.** Every
answer, fact and citation is checked by code against the stored document or order, and all money
is calculated by code, never by the language model.

## Three versions compared

| Capability | eContractIQ (mid-viva) | NyayaSim (intermediate build) | ContractIQ (final viva) |
|---|---|---|---|
| Upload documents | PDF, DOCX, TXT, MD | PDF and images (JPG/PNG), up to 100 pages | Same as NyayaSim |
| Read scanned pages | No | Yes, Tesseract OCR | Yes locally; **not on Render's native runtime** (no Tesseract there) |
| Chunking | LangChain splitter, 1000 chars, 150 overlap | Own sentence-boundary chunker with page and character offsets | Same as NyayaSim |
| Embeddings | all-MiniLM-L6-v2 (fastembed) | bge-small-en-v1.5 (fastembed, 384 dims), chosen by measurement | Same as NyayaSim |
| Vector store | ChromaDB, one folder per document | PostgreSQL + pgvector, keyword + vector search fused | Same as NyayaSim |
| Chat with the contract | Yes (Groq Llama 4 Scout), last 6 messages as context | Yes (Gemini), each answer checked: quote must be on the page, numbers must match; "not enough in the documents" otherwise | Same as NyayaSim, carried over |
| Sources shown | Excerpt preview with a similarity score | File, page and the exact verified quote | Same as NyayaSim |
| Benefits and obligations of each party | Yes: two-stage LLM extraction, score 1–10, no check | No | **Yes, restored**: rights, obligations, penalties and one-sided terms per party, each quote checked against the page; unverified clauses dropped and counted |
| Delete a document | Yes | Yes (and a whole case), with everything derived from it | Same |
| User accounts and privacy | None; CORS open to all origins | Accounts, email confirmation, sessions, per-user cases (others get 404), rate limits; real documents never sent to the model | Same |
| Fact extraction and verification | No | Dates, payments, possession date, each with page and quote; buyer confirms; unconfirmed facts never used later | Same |
| Financial claim calculator | No | Delay interest and refund, deterministic, per payment | **Audited and corrected** (FINANCIAL_CALCULATOR_AUDIT.md): offer-of-possession end date, verified Rule 15 source, current 10.80% rate |
| Legal precedent retrieval | No | 2,209 HRERA Gurugram orders (~73,000 passages), search with a decision-date cutoff | Same |
| Citation verification | No | Code checks every cited quote against the stored order (precision 100%, recall 98.3% on held-out orders) | Same |
| Simulated hearing | No | Buyer's advocate, builder's advocate, citation gate, judge (LangGraph) | Same |
| Agentic analysis | No | Orchestrator chooses tools; specialist agents for documents, research, claims; bounded steps; every step saved | Same |
| Outcome estimate and classifiers | No | Rule-based estimate (72.9% on held-out orders); claim-type classifier (74.3%) | Same; reported as exploratory |
| Complaint draft and report | No | Built by code from verified facts and citations | Same |
| Deployment | Local only | Docker Compose + Caddy (tested locally, never public) | **Vercel (website) + Render native Python (API) + Render PostgreSQL**; configuration written, not yet deployed |

## What is new for the final viva, and what is not

Developed in the intermediate NyayaSim build and carried over unchanged in function: everything in
the middle column. It is not presented as new in the final version.

Changed for the final viva:

1. Name, logo and positioning: ContractIQ, real-estate contract intelligence.
2. The mid-viva contract analysis (benefits and obligations per party) is back, rebuilt on the
   current retrieval with code-checked quotes (`backend/app/rag/clauses.py`, on the "Ask your
   documents" step).
3. Calculator audit and its fixes.
4. Deployment moved from Docker to Vercel and Render.

Mid-viva features not carried over, and why:

| Mid-viva feature | Status | Reason |
|---|---|---|
| DOCX, TXT and MD upload | Not carried over | Builder–buyer papers arrive as PDFs and scans; DOCX support would add a new dependency |
| Chat memory of the last 6 messages | Not carried over | Each answer is checked against the documents on its own; earlier questions and answers are saved and listed instead |
| Groq Llama model | Replaced by Gemini in the NyayaSim build | One provider; a Gemini fallback model handles busy periods |
| ChromaDB | Replaced by pgvector | One database for users, cases, orders and vectors, with per-case filtering in SQL |

The mid-viva code and its documents are kept in `docs/history/midviva/`.
