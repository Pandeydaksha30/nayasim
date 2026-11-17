# Demonstration guide

For a 5 to 7 minute demonstration of ContractIQ running on this laptop. Start-up commands are in
RUN_LOCAL.md; test evidence is in TEST_REPORT.md.

## Before the professor arrives (15 minutes)

1. Start Docker Desktop, then run these in three PowerShell windows (details: RUN_LOCAL.md):

   ```powershell
   docker compose -f C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\infra\docker-compose.yml up -d
   powershell -ExecutionPolicy Bypass -File C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\scripts\dev-api.ps1 -AllowDemo
   powershell -ExecutionPolicy Bypass -File C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\scripts\dev-web.ps1
   ```

2. Open http://localhost:3100 (website) and http://localhost:8000/docs (API) in two browser tabs.
3. **Demo account.** It already exists on this machine: the email and password are in
   `data\demo-credentials.txt` (never shown on screen, not in the ZIP). On a new machine, create it
   and a ready demo case with:

   ```powershell
   cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\backend
   .\.venv\Scripts\python.exe -m scripts.e2e_check setup
   .\.venv\Scripts\python.exe -m scripts.e2e_check facts
   ```

   `setup` registers the user, confirms the email from `data\outbox\`, creates the case
   "Mehra v. Arvant Infra (DEMO)" and uploads the four fictional documents; `facts` extracts and
   confirms the facts. The newest case with that name on the dashboard is the prepared one.
4. Log in and open that case. Check that Facts, Ask your documents, Agent analysis, Hearing and
   Report show content. Run one hearing and one agent analysis now, so stored results exist as a
   backup (see "If Gemini fails").
5. Keep `demo\sample-documents\` open in File Explorer for the upload step.
6. Close other heavy programs. Keep the laptop on power.

## Fictional documents to upload

`demo\sample-documents\` (every name and number is invented): `agreement.pdf` (2 pages),
`receipts.pdf` (2 pages), `builder_letter.pdf` (1 page), `receipt_scan.png` (an image, read by OCR).
For a live upload: Dashboard, **New case**, tick the fictional demo option, then the Documents step.

## Questions to ask on "Ask your documents" (measured answers, 13 Nov)

| Ask | Expected |
|---|---|
| By what date did the builder promise possession? | "on or before 30th June 2021", cited to `agreement.pdf` page 2, marked verified |
| What is the total price of the apartment? | Rs. 72,00,000, `agreement.pdf` page 1 |
| How much cost escalation charge does the builder demand? | Rs. 1,44,000, `builder_letter.pdf` page 1 |
| What is the revised completion date for Tower C? | 31 December 2025, `builder_letter.pdf` page 1 |
| Who is the project architect? (not in the documents) | "The uploaded documents do not contain enough to answer this question." |

Wording of the answer varies slightly between runs; the value, the page and the "verified" mark
should not.

## Contract analysis (the mid-viva feature, now verified)

On the same **Ask your documents** step, press **Analyse the contract** (about 10 to 30 seconds).
Expected (live run of 17 Nov, 6 seconds, 5 clauses verified, 0 removed): clauses grouped by party
(the promoter's duty to hand over possession by 30 June 2021, the Rs 5 per sq ft per month delay
compensation, the allottee's duty to take possession within two months of the offer, and the
builder's unilateral revision of the completion date flagged as one-sided), each with its kind (obligation, right, penalty,
one-sided), the file, page and quote. Say: "At mid-viva this was an LLM summary with a score; now
a clause is shown only if its quote is found on the page, and dropped clauses are counted."
The exact clauses vary between runs; the quotes are always from the document.

## Agent analysis: exact steps

1. Open the case, step **Agent analysis**.
2. Paste this objective and press **Run analysis**:
   "Prepare a complete assessment of this buyer's case: what the documents say, relevant
   precedents, money owed at 10.80%, the likely outcome, and a simulated hearing with the judge's
   assessment."
3. Expected (live run of 13 Nov, about 90 seconds): the step list fills in while it runs:
   `delegate` to **document_analysis** (which called `search_documents`), `delegate` to
   **legal_research** (which called `search_orders`), `calculate_interest` with 10.80,
   `estimate_outcome`, `run_hearing`; then an answer with citations marked verified (5 verified,
   0 removed in that run) and the judge assessment below it.
4. Open "What came back" on a step to show the tool's observation. The "by" label shows which
   agent took the step.
5. The order and number of steps is chosen by the model and can differ between runs; that is the
   point. If a citation is removed, the page says how many: show it as the checker working.

Shorter objective if time is tight: "When was possession promised, how late is it, and what
interest could the buyer claim at 10.80%?" (about 20 seconds, no hearing).

## Hearing simulation: exact steps

1. Step **Simulated hearing**, press **Run hearing**. It runs in the background (60 to 90 seconds
   when Gemini is free); the page updates by itself.
2. Expected: buyer's arguments and builder's arguments, each with citations to real HRERA orders
   marked verified; arguments whose citation failed are listed as removed; then the bench's outcome
   (the runs on 13 Nov gave "partly allowed"), reasoning and up to three weak points.
3. Step **Report** then shows the amount, the rule-based estimate with its measured accuracy
   (72.9%), and the weak points. Step **Complaint draft** uses the verified citations.

## 1. Introduction (30 seconds)

"ContractIQ helps a home buyer prepare a RERA complaint for delayed possession or refund. The buyer
uploads their papers; the system reads the facts, calculates what is owed, and simulates a hearing
argued from real orders of the Haryana Real Estate Regulatory Authority, Gurugram. Its main design
rule is that nothing is invented: every fact shows the page it came from, every cited order is
checked against the stored text, and all money is calculated by ordinary code, not by the model."

## 2. Architecture and technology (1 minute)

| Layer | Technology |
|---|---|
| Website | Next.js 15, React 19, TypeScript, plain CSS |
| API | FastAPI (Python 3.12), SQLAlchemy, Alembic migrations |
| Database | PostgreSQL 17 with the pgvector extension, in Docker |
| Document reading | PDF text layer, Tesseract OCR for scans and images |
| Search over orders | Postgres full-text search + vector search (local `bge-small` embeddings), combined by reciprocal rank fusion |
| Hearing | LangGraph graph: buyer advocate, builder advocate, citation gate, judge |
| Language model | Google Gemini (free tier), used for reading facts and for the advocates and judge |
| Trained models | TF-IDF + logistic regression and rules, evaluated offline |
| Accounts | Argon2id passwords, server-side sessions in an HttpOnly cookie, rate limits, CSRF check |

Flow to describe: browser, Next.js (forwards `/api`), FastAPI, PostgreSQL. Public orders are
downloaded, split into chunks and embedded once; a hearing searches them, the agents argue, the
gate removes any argument whose citation cannot be found in the stored order.

## 3. Live sequence (4 minutes)

| Time | Show | Say |
|---|---|---|
| 0:00 | Landing page, then **Sign in** as the demo user | Accounts are real: hashed passwords, email verification, sessions. Other users cannot see this case. |
| 0:30 | **Dashboard**, open the demo case, **Documents** step. Upload `receipt_scan.png` into a new demo case, or show the four files already uploaded. | PDFs are read from their text layer; this image was read by OCR on this machine. |
| 1:15 | **Facts** step | Each fact shows its document, page and the exact quote. A value whose quote is not found in the document is rejected by code. The buyer confirms each fact. |
| 1:40 | **Ask your documents** step: ask "By what date did the builder promise possession?", then "Who is the architect?" | The documents were split into chunks and embedded locally when uploaded. The answer cites file and page; the quote was found word for word by code. The second question gets "not enough in the documents" instead of a guess. |
| 2:00 | **Questions**, then **Money** step | Interest is calculated by deterministic Python and shown payment by payment. Change the rate to show the figure move. |
| 2:45 | **Hearing** step: press Run (or open the stored one) | It runs in the background. Buyer advocate, builder advocate, then the judge. Each citation carries a "verified" mark: the quote was found on that page of that real order. Unverified arguments are removed before the judge sees them. |
| 3:30 | **Agent analysis** step: run example 1 or 3 | The model chooses the next tool each step (documents, facts, calculator, outcome estimate, past orders, specialist agents, the hearing); code runs it and the step list shows what came back. Limited to 6 steps and 7 minutes. Citations in the answer are checked by code; failed ones are removed and counted. |
| 4:00 | **Report** step | Amount estimate with the basis of the rate, the rule-based outcome estimate with its measured accuracy, and where the case is weak. |
| 4:20 | **Complaint draft** step | Put together by code from the confirmed facts and the citations that passed verification. Blanks in brackets where something is not known. Download as text. |
| 4:40 | **Search orders** in the top bar | Keyword plus meaning-based search over the public orders; then paste part of an order into the classifier box to show the trained model and its measured accuracy. |
| 5:10 | http://localhost:8000/docs | The API behind the site: accounts, cases, documents, facts, hearing, calculator. |

Optional, if asked about the database:

```powershell
docker exec infra-postgres-1 psql -U nyayasim -d nyayasim -c "select count(*) as orders from orders; select count(*) as chunks, count(embedding) as embedded from order_chunks; select id, status from hearing_runs;"
```

Optional, if asked about the trained models (offline, takes about a minute, prints validation and
test scores from the frozen split):

```powershell
cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\backend
.\.venv\Scripts\python.exe -m scripts.train_classifier --task claim_type
```

Note: that command scores the held-out test set again and overwrites the saved model file, so run
it only if asked. Otherwise show the numbers in MODEL_TRAINING_GUIDE.md.

## 4. Results to state (1 minute)

| Component | Measured on held-out orders |
|---|---|
| Citation checker | Precision 100%, recall 98.3%; all fabricated citations caught |
| Outcome prediction (allowed / partly / dismissed) | Best method 72.9% (a simple rule); language model with the parties' filings 67.8%; trained classifier 50.8% |
| Claim type (refund / delay / other) | 74.3%, macro-F1 0.455 (rule on the relief section plus trained model) |

Data: 13,992 orders listed, 2,209 downloaded with text, about 73,000 chunks, 502 orders labelled by
the model. Labels have not yet been checked by people, which limits how far the accuracy numbers
can be trusted.

## 5. Limitations to state openly

- Runs locally; it is not deployed to a public address.
- Question answering over uploaded documents is evaluated on 40 questions over the fictional demo
  documents (all correct on both halves), which is a small, easy set: it tests the pipeline, not
  real agreements.
- The specialist agents and the hearing are bounded: specialists get 3 steps and a fixed tool
  set, and the hearing's own order of roles is fixed. Tool choices of the orchestrator and the
  specialists are made by the model; whether it delegates varies from run to run.
- The trained classifiers work on the text of an order, not on a buyer's own papers; for a buyer's case the site shows the rule-based estimate.
- The complaint draft is a starting point with blanks, to be checked by the complainant or an advocate.
- Only fictional demo cases are sent to the language model, because the free tier may retain data.
  Real buyers' documents are blocked by the API until a zero-retention model is configured.
- Email is written to a local folder instead of being sent. Google sign-in works for the test accounts added in the Google console.
- Outcome prediction is well below a level anyone should rely on; the tool is for preparation,
  not legal advice.

## If Gemini fails during the demo

What the app does by itself: when the model answers "high demand" (503) or times out, the call is
retried twice (15 s, 30 s) and then sent to a second Gemini model (`gemini-3.6-flash`). So a busy
moment shows up as a slower step, not an error. If both models are unavailable:

1. Do not retry more than once.
2. **Hearing:** the Hearing step shows the last completed hearing from the database without
   calling the model.
3. **Agent analysis:** the page opens the latest saved run with all its steps; "Earlier runs" at
   the bottom lists the others.
4. **Ask your documents:** "Earlier questions" shows saved answers with their citations.
5. Say plainly: "The free model tier is overloaded right now, so this is the stored result of an
   earlier run; what you see is read from the database."
6. Login, upload, OCR, chunking, passage search, facts already extracted, money, report, order
   search, classifier and API docs work without Gemini.
7. To show the agent loop itself without any model, run
   `.\.venv\Scripts\python.exe -m pytest -q tests/test_agent.py` in `backend`: the same loop with a
   scripted stand-in model (9 tests). Say that it is scripted; it is not a Gemini run.

## Likely questions

| Question | Short answer |
|---|---|
| Is it JWT? | No. Server-side sessions with an HttpOnly cookie; the server stores only a hash of the token and can revoke sessions. |
| Is it RAG? | Yes, twice: over the buyer's own documents (Ask step, per-case chunks in pgvector) and over public orders (hearing, search). Every citation is verified by code. |
| Is the agent autonomous? | Within limits: the model chooses each tool and its arguments from what it has seen (the step list proves it), code executes, and hard limits stop it. It cannot write anything except saving a hearing of the same case. |
| Where is the vector database? | In PostgreSQL, through pgvector. No separate vector store. |
| Was the model trained? | The language model is used as is. Two small classifiers were trained and evaluated on a frozen, time-based split; results are reported as measured. |
| Why not 95%? | Labels are machine-made and inconsistent in places; results were not tuned on the test set. |
