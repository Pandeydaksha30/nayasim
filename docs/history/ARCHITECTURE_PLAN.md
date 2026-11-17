# Implementation plan: document RAG and agent orchestration

Status: **plan only, nothing below is built.** Written 13 Nov 2026 after reading the current code
(schema, chunker, embedder, hearing graph, dependencies). No code will change until this plan is
approved. Each module is built, tested and documented on its own before the next one starts.

## 1. Where the project is today

| Capability | State | Code |
|---|---|---|
| Upload, text extraction, OCR, per-page text | Working | `app/buyer/documents.py`, tables `case_documents`, `case_document_pages` |
| Structured facts with page and quote | Working (demo cases) | `app/buyer/facts.py` |
| Chunking | Working, for public orders only | `app/ingestion/chunker.py` (`chunk_page`) |
| Embeddings | Working, local, for public orders only | `app/retrieval/embedder.py` (fastembed `BAAI/bge-small-en-v1.5`, 384 dimensions) |
| Vector + keyword search | Working, for public orders only | `app/retrieval/search.py`, table `order_chunks` (HNSW + GIN indexes) |
| Hearing | Working; a **fixed** LangGraph pipeline: buyer, builder, gate, judge, report | `app/hearing/graph.py` |
| Citation verification | Working; deterministic code, not a model | `app/verifier/citations.py` |
| Orchestrator that chooses tools | **Does not exist** | |
| Question answering over the user's document | **Does not exist** | |

So the honest starting point: retrieval-augmented generation exists over public orders inside the
hearing; the hearing's "agents" run in a fixed order and make no tool decisions. The plan adds the
two missing things: retrieval over the user's own documents, and a real decision loop.

## 2. Technology: keep what is installed

| Proposed in the brief | Recommendation | Reason |
|---|---|---|
| all-MiniLM-L6-v2 embeddings | **Keep `bge-small-en-v1.5`** | Already installed, same size (384), chosen by measurement, and 73,000 order chunks are embedded with it. Switching means re-embedding everything for no measured gain. |
| LangChain text splitters | **Keep `chunk_page`** | It already splits at sentence breaks and records character offsets per page, which the citation check needs. LangChain would be a large new dependency for one function. |
| PyMuPDF | **Keep `pypdfium2`** | Already installed and working. PyMuPDF is AGPL-licensed, which restricts distributing the project. |
| LangChain for RAG orchestration | **Not needed** | Retrieval, prompt assembly and verification are a few hundred lines of our own code, and are easier to test. |
| LangGraph for agents | **Yes, already installed** (`langgraph==1.2.20`) | Used by the hearing today. |
| Groq / Llama | **Optional second provider** | Useful because the Gemini free tier is often unavailable. Needs a key from you, and Groq's data-retention terms must be read before any non-demo text is sent. It plugs in behind the existing `LLM` protocol. |
| PostgreSQL + pgvector | **Yes, already used** | No separate vector database. |

**New dependencies: none** for modules 1 to 4. (Groq, if chosen, is called with `httpx`, already installed.)

## 3. Module 1: question answering over uploaded documents

### Flow

Upload (exists) → page text (exists) → **chunk** → **embed locally** → **store in pgvector** →
question → **retrieve from this case only** → **assemble context** → model answers in a fixed
schema → **every quoted citation is checked against the stored page by code** → answer with
document and page, or "not enough evidence".

### Database (migration `0009_case_document_chunks.py`)

```sql
CREATE TABLE case_document_chunks (
  id              bigserial PRIMARY KEY,
  case_id         uuid   NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  document_id     uuid   NOT NULL,
  page_no         int    NOT NULL,
  char_start      int    NOT NULL,
  char_end        int    NOT NULL,
  text            text   NOT NULL,
  tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  embedding       vector(384),
  embedding_model text,
  FOREIGN KEY (document_id, page_no)
    REFERENCES case_document_pages(document_id, page_no) ON DELETE CASCADE
);
CREATE INDEX ON case_document_chunks (case_id);
CREATE INDEX ON case_document_chunks USING gin (tsv);
CREATE INDEX ON case_document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE case_questions (            -- history and evaluation trace
  id          bigserial PRIMARY KEY,
  case_id     uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  question    text NOT NULL,
  result      jsonb NOT NULL,            -- answer, citations, chunk ids retrieved (not their text)
  created_at  timestamptz NOT NULL DEFAULT now()
);
```

A separate table from `order_chunks`, so the user's text and public orders can never be mixed by
a query mistake. The owner is `cases.user_id`: the chunk carries `case_id`, and every request
first passes the existing ownership check (`case_for`), which answers 404 for someone else's
case. I recommend **not** copying `user_id` onto each chunk: two copies of the owner can
disagree. If you want the column for the report, it can be added as a denormalised copy.

### Backend files

| File | Change |
|---|---|
| `backend/migrations/versions/0009_case_document_chunks.py` | new |
| `backend/app/db/models.py` | add `CaseDocumentChunk`, `CaseQuestion` |
| `backend/app/buyer/chunks.py` | new: `index_document()` = `chunk_page` per page + `embed_documents` + insert |
| `backend/app/buyer/documents.py` | call `index_document()` after pages are stored (same worker thread as OCR) |
| `backend/app/retrieval/case_search.py` | new: hybrid search with `WHERE case_id = :case_id`, same rank fusion as `search.py` |
| `backend/app/rag/answer.py` | new: context assembly, prompt, schema, citation check, "insufficient evidence" rule |
| `backend/app/api/rag.py` | new router (below) |
| `backend/app/main.py` | register the router |
| `backend/scripts/index_case_documents.py` | new: index documents uploaded before this change |
| `backend/tests/test_case_rag.py` | new |

### Endpoints

| Endpoint | Purpose | Model call |
|---|---|---|
| `GET /api/v1/cases/{id}/passages?q=` | Retrieval only: the passages of this case's documents that match | None. Works for every case. |
| `POST /api/v1/cases/{id}/ask` `{question}` | Answer grounded in retrieved passages, with citations | Yes. Demo cases only until a zero-retention model is configured (same rule as the hearing; 403 otherwise). |
| `GET /api/v1/cases/{id}/questions` | Past questions and answers for this case | None |

Response of `/ask`: `answer`, `insufficient` (true/false), `citations[]` (document id, file name,
page, quote, `verified`), `retrieved[]` (chunk id, file name, page, score), `mode` (hybrid or keyword).

### Grounding rules, enforced by code

1. The model receives only the retrieved passages, each labelled `[D1]`, `[D2]`…, and must answer
   in a schema: `answer`, `citations: [{ref, quote}]`, `insufficient`.
2. Each quote is checked against the stored page text with the existing quote checker (exact
   match on numbers and meaning words). An unverified citation is removed.
3. If no citation survives, or the best retrieval score is below a threshold chosen on the
   development questions, the response is "The uploaded documents do not contain enough to answer
   this", with the passages shown.
4. Uploaded-document results and public-order results come from different tables and different
   endpoints, and are labelled as such everywhere.

### Frontend files

| File | Change |
|---|---|
| `frontend/app/cases/[id]/ask/page.tsx`, `live/ask-client.tsx`, `ask.module.css` | new step "Ask your documents": question box, answer, citations that open the page text, passages used |
| `frontend/app/cases/[id]/step-nav.tsx`, `layout.tsx` | add the step |
| `frontend/lib/insights-api.ts` | `askCase`, `searchPassages`, `listQuestions` |

### Tests for module 1

Chunks created on upload; deleted with the document; user B gets 404 for user A's case on all
three endpoints and never sees A's chunks; private case blocked from `/ask` but not from
`/passages`; invented quote removed; unanswerable question returns `insufficient`; existing order
search and hearing tests still pass.

## 4. Module 2: agent orchestration

A loop in which the model decides the next step from what it has seen so far. Built with
LangGraph, as a new graph next to the hearing graph.

```
objective → PLAN (model chooses: a tool + arguments, or "finish")
              ↓ tool                      ↑
            EXECUTE (code) → OBSERVE (result added to state) ─┘
              ↓ finish
            ANSWER (from observations only) → VERIFY (code checks every citation) → result
```

### Tools (all read-only)

| Tool | Does | Existing code reused |
|---|---|---|
| `search_documents(query)` | Passages from this case's documents | module 1 |
| `get_facts()` | Confirmed facts with pages | `app/buyer/facts.py` |
| `search_orders(query)` | Passages from public orders before today | `app/retrieval/search.py` |
| `verify_citation(order, page, quote)` | Is this quote in the stored order? | `app/verifier/citations.py` |
| `calculate_interest(rate)` | Delay interest / refund | `app/calculator/interest.py` |
| `outcome_estimate()` | How similar past orders ended | `app/insights/estimate.py` |

### Limits and failure handling

- At most 6 tool steps per run; at most 120 seconds in total; each model call under the existing
  deadline (`call_with_deadline`).
- A repeated identical tool call is refused and the model is told so.
- A tool error becomes an observation, not a crash. Two model failures in a row end the run with
  what has been gathered, marked incomplete.
- Final citations are verified by code whether or not the model chose to call `verify_citation`.

### Files and endpoints

| File | Change |
|---|---|
| `backend/migrations/versions/0010_agent_runs.py` | new table `agent_runs` (case, objective, status, `steps` jsonb, `result` jsonb, times), like `hearing_runs` |
| `backend/app/agent/tools.py` | new: tool definitions with typed arguments |
| `backend/app/agent/orchestrator.py` | new: the LangGraph loop |
| `backend/app/agent/jobs.py` | new: background run, reusing the pattern in `app/hearing/jobs.py` |
| `backend/app/api/agent.py` | new router |
| `backend/tests/test_agent.py` | new, with a scripted stand-in model |
| `frontend/app/cases/[id]/research/…` | new page: objective box, live list of steps (tool, reason, what came back), final answer |

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/cases/{id}/agent` `{objective}` | Start a run (202), demo cases only |
| `GET /api/v1/cases/{id}/agent/runs/{run}` | Status, steps so far, result |
| `GET /api/v1/cases/{id}/agent/runs` | Past runs |

## 5. Module 3: specialised agents

What each one is, stated without inflation:

| Agent | What it will be | New or existing |
|---|---|---|
| Document analysis | Sub-loop limited to `search_documents` and `get_facts`; returns clauses with pages | New, on module 1 |
| Legal research | Sub-loop limited to `search_orders`; may reformulate the query up to twice when results do not match the claim | New decision step; search exists |
| Claim analysis | Turns facts into the claims and reliefs available, using the estimate and the relief wording | New |
| Citation verification | **Code, not a model.** It stays deterministic; that is its value | Exists |
| Buyer and builder advocates | As today, plus one bounded rebuttal round | Exists; rebuttal new |
| Judge | As today | Exists |
| Orchestrator | Module 2; can hand a task to the agents above | New |

Files: `backend/app/agent/agents.py` (new), `backend/app/hearing/graph.py` (rebuttal round,
research step), tests extended in `tests/test_hearing.py` and `tests/test_agent.py`.

## 6. Module 4: evaluation

Kept apart from the frozen classifier benchmark; nothing here touches the held-out ML test set.

| What | How | Needs a person? |
|---|---|---|
| Question set | 40 questions over the fictional sample documents: 30 answerable with the gold page and gold answer, 10 unanswerable. Half for development, half held back. `data/eval/doc_qa.jsonl` | I can draft it (the documents are invented, so the answers are known); you review it |
| Retrieval precision@5, recall@5, MRR | Gold page among retrieved pages | No |
| Citation correctness | Cited page equals gold page and quote verified | No |
| Abstention | Unanswerable questions answered "insufficient" | No |
| Answer correctness | Key value (date, amount, name) present in the answer | No for factual questions |
| Faithfulness and relevance | Each answer sentence supported by a verified quote (computed), plus a 1 to 5 rating sheet | Rating sheet: yes |
| Agent runs | Expected tool per objective vs chosen tool, steps used, failures, time | Expected tools: I draft, you review |

Files: `backend/scripts/eval_rag.py`, `backend/scripts/eval_agent.py`, `RAG_EVALUATION.md`.
Limit to state in the report: questions over invented documents measure the pipeline, not
performance on real agreements.

## 7. Security and privacy

| Risk | Control |
|---|---|
| One user reading another's document chunks | Every query filtered by `case_id` after the ownership check; chunks in their own table; tests with two users |
| User text sent to a model that may retain it | `/ask` and `/agent` allowed only for demo cases while `NYAYASIM_PRIVATE_LLM_OK=false`; retrieval-only endpoint needs no model |
| Instructions hidden inside an uploaded document | Document text is passed as quoted data; all tools are read-only; the answer must cite, and citations are checked by code |
| Runaway loops and cost | Step, time and repeat limits; per-user rate limit on `/ask` and `/agent` |
| Sensitive text in logs | Traces store chunk ids and short summaries, not page text |
| Deletion | Chunks, questions and agent runs cascade when the case or account is deleted |

## 8. Order, size and checks

| Step | Work | Rough size | Done when |
|---|---|---|---|
| 1 | Module 1 backend + tests | 2 days | Unit tests and a live API check pass, two-user isolation shown |
| 2 | Module 1 page | 1 day | End-to-end stage added to `scripts/e2e_check.py` passes |
| 3 | Module 4 for RAG | 1 day | `RAG_EVALUATION.md` with numbers from the held-back questions |
| 4 | Module 2 | 3 days | Scripted-model tests for limits and failures; live run recorded |
| 5 | Module 3 | 2 to 3 days | Hearing tests still pass; rebuttal and research steps tested |
| 6 | Module 4 for agents, documentation | 1 to 2 days | Report tables filled from saved runs |

After each step: backend tests, frontend type-check, live API check, isolation check, documents
updated, commit on a branch with a tag before the step.

## 9. Decisions needed from you

1. Approve keeping the current embedding model, chunker and PDF reader (section 2).
2. Owner stored through `case_id` only, or also a copied `user_id` column on each chunk.
3. Second model provider: stay on Gemini only, or add Groq (needs your key and a check of its retention terms).
4. Whether I draft the 40 evaluation questions for your review.
5. When to start: this is about two weeks of work and should begin after your demonstration.
