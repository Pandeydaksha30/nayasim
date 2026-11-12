# Demonstration guide

For a 5 to 7 minute demonstration of NyayaSim running on this laptop. Start-up commands are in
RUN_LOCAL.md; test evidence is in END_TO_END_TEST_REPORT.md.

## Before the professor arrives (10 minutes)

1. Start Docker Desktop, then the backend (with `-AllowDemo`) and the website (RUN_LOCAL.md).
2. Open http://localhost:3100 and http://localhost:8000/docs in two browser tabs.
3. Log in as the demo user (`data\demo-credentials.txt`) and open the case
   "Mehra v. Arvant Infra (DEMO)". Check that the Facts, Hearing and Report steps show content.
4. Keep `demo\sample-documents\` open in File Explorer for the upload step.
5. Run one hearing now. If it completes, the live step will most likely work; if Gemini is busy,
   plan to show the stored hearing instead (see "If Gemini fails").
6. Close other heavy programs. Keep the laptop on power.

## 1. Introduction (30 seconds)

"NyayaSim helps a home buyer prepare a RERA complaint for delayed possession or refund. The buyer
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
| 2:00 | **Questions**, then **Money** step | Interest is calculated by deterministic Python and shown payment by payment. Change the rate to show the figure move. |
| 2:45 | **Hearing** step: press Run (or open the stored one) | It runs in the background. Buyer advocate, builder advocate, then the judge. Each citation carries a "verified" mark: the quote was found on that page of that real order. Unverified arguments are removed before the judge sees them. |
| 4:00 | **Report** step | Amount estimate with the basis of the rate, and where the case is weak. Note the honest message when too few similar orders have a recorded outcome. |
| 4:30 | http://localhost:8000/docs | The API behind the site: accounts, cases, documents, facts, hearing, calculator. |

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
- No question-answering over an uploaded document, and uploaded documents are not embedded: the
  system extracts structured facts instead. Vector search covers the public orders only.
- The trained classifiers are evaluated from the command line and are not called by the website.
- Precedent search runs inside the hearing; there is no separate search page.
- The complaint draft page is a placeholder.
- Only fictional demo cases are sent to the language model, because the free tier may retain data.
  Real buyers' documents are blocked by the API until a zero-retention model is configured.
- Email is written to a local folder instead of being sent; Google sign-in is coded but not configured.
- Outcome prediction is well below a level anyone should rely on; the tool is for preparation,
  not legal advice.

## If Gemini fails during the demo

Symptoms: the hearing stays "running" for more than about two minutes, or ends with a message
about the model being busy (429 / 503).

1. Do not retry more than once.
2. Open the demo case's **Hearing** step: the last completed hearing is stored in the database and
   is shown without calling the model (two completed runs exist as of 12 Nov).
3. Say plainly: "The free model tier is overloaded right now, so this is the result of the run
   stored earlier today; the background job and storage are what you are seeing."
4. Everything else in the sequence (login, upload, OCR, facts already extracted, money, report,
   API docs) works without Gemini.

## Likely questions

| Question | Short answer |
|---|---|
| Is it JWT? | No. Server-side sessions with an HttpOnly cookie; the server stores only a hash of the token and can revoke sessions. |
| Is it RAG? | Retrieval over public orders feeds the advocates and judge, with citations verified by code. It is not a chat over the user's document. |
| Where is the vector database? | In PostgreSQL, through pgvector. No separate vector store. |
| Was the model trained? | The language model is used as is. Two small classifiers were trained and evaluated on a frozen, time-based split; results are reported as measured. |
| Why not 95%? | Labels are machine-made and inconsistent in places; results were not tuned on the test set. |
