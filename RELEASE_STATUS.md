# NyayaSim release status: v1.0.0-rc1

Prepared 15–16 Nov 2026 on Windows 11 with Docker Desktop. Every result below was produced by
running the thing named; nothing is reported from a build alone.

| | |
|---|---|
| Branch | `nyayasim/foundation` |
| Code commit | `6e75e11` (on top of `87120d4`); this report is added in the commit the tag points to |
| Tag | `v1.0.0-rc1` (local; nothing has been pushed) |
| Package | `C:\Users\pande\Downloads\CONTRACT_IQ\NYAYASIM_FINAL_DEPLOY.zip`, about 198 MB, 303 files |
| Earlier packages, kept | `NYAYASIM_COMPLETE_PROJECT.zip`, `NYAYASIM_COMPLETE_PROJECT_before_15Nov_changes.zip` |
| Setup instructions | `DEPLOYMENT_GUIDE.md` |

It is a release candidate, not a public release: it deploys and works as described here, and the
items under "Manual steps" and "Limitations" still stand between it and real buyers.

## 1. What was implemented in this release

Since commit `8c68aee` (details in `CHANGES_2026-11-15.md`):

- Facts marked "Check" are left out of the calculator, hearing, agent, estimate and draft until
  the buyer confirms them.
- Deleting a single document or a whole case, with everything derived from it; adding documents
  to an existing case.
- The page as filed, with the passage marked on it (text-layer pages; scans show no mark).
- The public example is a recording of a real run on fictional documents, not hand-written data.
- Agent interest tool: it reported principal plus interest as "delay interest". Fixed.
- Rate limits on every costly route; live public figures; API docs off under HTTPS.
- Agent and Ask pages rebuilt.

In this session:

- `infra/backup.sh` and `infra/restore.sh` (whole database and uploaded files).
- `infra/deploy.sh` installs the trained classifier files.
- API image: `/srv/data/models` is created owned by the app user. Found by the clean deployment:
  copying the classifier files in as root left that folder unwritable, the search model could not
  be saved, and search silently fell back to keywords only.
- Container paths in scripts and the guide are passed inside `sh -c`, so Git Bash on Windows does
  not rewrite them.
- Website image includes `public/` (the example's page pictures).
- `DEPLOYMENT_GUIDE.md` rewritten.
- Report page: order numbers no longer break across two lines.

## 2. Tests run and results

| Test | Result |
|---|---|
| Backend unit and API tests (`pytest`) | 260 passed, 0 failed |
| `ruff check` on the changed backend code | clean |
| Website type check (`tsc --noEmit`) | clean |
| Website production build (`next build`) | succeeds |
| End-to-end against the local app, through the website address (`scripts/e2e_check.py`) | setup 29, facts 5, hearing 5, insights 16, rag 9, agent 6, isolation 9, lifecycle 20, session 6: 105 passed, 0 failed |
| Workflow check against the clean Docker deployment (section 4) | 62 passed, 0 failed |

The facts, hearing, rag and agent stages called Google Gemini for real, on fictional demo
documents only.

### The eighteen flows

| # | Flow | How it was exercised | Result |
|---|---|---|---|
| 1 | Registration, login, logout | Clean deployment: sign-up, login refused before confirmation, confirmation link from the server outbox, wrong password refused, login, logout | Pass |
| 2 | Case creation | Local and clean deployment | Pass |
| 3 | Document upload | PDF and PNG; a non-PDF and a damaged PDF are refused with 422 | Pass |
| 4 | Text extraction and OCR | Text layer read without OCR; PNG read by Tesseract inside the container (confidence 94.7), amount found in the text | Pass |
| 5 | Fact review and confirmation | Local demo case with Gemini (e2e `facts`); confirmation covered by unit test | Pass |
| 6 | Unconfirmed facts never enter later steps | Unit test: a fact set to "review" disappears from payments total, hearing input and estimate, and returns after confirmation | Pass |
| 7 | Confirmed facts flow downstream | Same test; e2e `hearing` and `insights` on the demo case | Pass |
| 8 | Interest calculator | Rs 1,00,000 at 10%: 365 days of delay gives Rs 10,000.00; refund interest over 731 days gives Rs 20,027.40; same answer twice | Pass |
| 9 | Retrieval and citations | e2e `rag` (9 checks); clean deployment search in "hybrid" mode over own documents and over orders | Pass |
| 10 | Citations resolve to real orders and passages | Clean deployment: the returned passage was found by SQL on the named page of the named stored order | Pass |
| 11 | Agent and hearing in the demo environment | e2e `agent` (6) and `hearing` (5), live with Gemini | Pass |
| 12 | Report | e2e `insights`; example report served from the production container | Pass |
| 13 | Complaint draft | Local and clean deployment: built, with unknown items listed as missing | Pass |
| 14 | Single-document deletion | Local (file, text, chunks, facts gone) and clean deployment | Pass |
| 15 | Whole-case deletion | Clean deployment: 0 documents, chunks and facts left in the database, no file left on disk | Pass |
| 16 | User isolation | A second user gets 404 for the first user's case, page picture, passages and delete; e2e `isolation` 9 of 9 | Pass |
| 17 | Rate limits | Seventh fact-extraction call in ten minutes answers 429, locally and in the container | Pass |
| 18 | Mobile layout | Facts, Agent, Hearing and landing page measured at 375 px: no horizontal overflow | Pass (measured, see 5) |

Privacy rule, tested in the container with a model key present (a placeholder): fact extraction,
cited answers, the agent and the hearing all answer 403 for a real case, the case has no facts
afterwards, and a demo case cannot be created.

## 3. Docker build status

| Image | Result | Size |
|---|---|---|
| `nyayasim-api` (from `backend/`) | built from the extracted package | 1.83 GB |
| `nyayasim-web` (from `frontend/`) | built from the extracted package | 324 MB |

One website build failed with `An error occurred in next/font`: the build downloads the fonts
from Google Fonts and that download failed once. Running the same command again succeeded with no
change. If you see that error, run the build again.

## 4. Clean deployment status

Done from the ZIP, extracted to `C:\NyRC2`, away from the development folder, following
`DEPLOYMENT_GUIDE.md` section 4 (ports 3300 and 8300 so it could run beside the development app):

1. `docker compose ... up -d --build`: all services started.
2. Fresh database; the `migrate` service exited 0; schema version `0010`.
3. `curl /health` on the API and through the website: `{"status":"ok"}`.
4. `infra/import-data.sh`: 13,992 orders listed, 2,209 with text, 72,970 passages, 502 outcome records.
5. Classifier files copied in; the classifier endpoint answers.
6. Workflow check: 62 of 62.
7. API, website and migration logs: no traceback and no permission error.
8. `infra/backup.sh` wrote a 197 MB database file and a 64 MB files archive;
   `infra/restore.sh` restored them (2 users, 13,992 orders) and the site came back healthy.
9. The stack was then updated in place from the final package (the "Updating" path) and the
   workflow check passed 62 of 62 again.

The first attempt passed 60 of 62 and exposed the model-folder ownership defect described in
section 1; one of the two failures was a mistake in the check itself. Both were fixed and the
deployment was repeated from an empty database.

Not tested: the HTTPS profile (Caddy with a real domain and certificate), `infra/deploy.sh` on a
Linux server, real email delivery, Google sign-in in production, and a machine with no Docker
layer cache. The package this report ships in differs from the one deployed in step 9 only by
this file.

## 5. What was looked at by eye

Screenshots (headless Edge, 1280 px wide) of the example case were read for Facts, Agent, Ask,
Hearing and Report: layout, highlight position and figures are correct. One defect was found and
fixed (order numbers breaking across lines). **Not seen by eye:** the Dashboard and any other
signed-in page, the Calculator, Draft, Money, Documents and Questions pages, and true phone
rendering (the headless browser cannot go narrower than 500 px; phone width was measured in the
built-in browser instead).

## 6. Secrets check

The package was scanned after building: no `.env` file (only the four `.example` templates), no
string shaped like a Google API key, no `node_modules`, no virtual environment, no uploaded
documents, no outbox. The data file holds public regulator orders only.

## 7. Missing features

- AI analysis for real buyers (needs a no-retention model provider).
- Encryption at rest; automatic expiry of uploads.
- Job queue and worker; shared rate-limit store.
- Highlights on scanned pages; a PDF or Word export of the report and draft (the draft downloads as text).
- Monitoring, alerting, scheduled backups, continuous integration.
- Reranker; Hindi search; orders from any authority other than HRERA Gurugram; 11,783 listed
  orders not yet fetched.
- Privacy page grievance contact; legal review of the terms and privacy drafts.

## 8. Security and privacy limitations

- Real documents are never sent to the model; that rule is enforced in code and was tested. Do
  not set `NYAYASIM_PRIVATE_LLM_OK=true` without a written no-retention agreement.
- Uploaded files and extracted text are stored unencrypted in Docker volumes.
- Backups made by `infra/backup.sh` contain private documents and password hashes.
- One API process only: rate limits and running jobs are held in memory.
- The website's content security policy still allows inline scripts.
- No external security review has been done.
- The Gemini key in `backend/.env` on the development machine was pasted into a chat earlier and
  should be rotated. It is not in the package or in git.

## 9. Research integrity

No evaluation was run or changed in this release. The existing figures (rule 72.9%, single model
call 67.8%, classifiers 74.3% and 50.8%) are exploratory: the labels were extracted by a model,
none of the 502 has been checked by a person, features were extracted with the decision pages in
view, and the 2025 test period has been used more than once, so it is no longer sealed. The site
states this wherever a figure appears. `benchmark/split_v1.json` is unchanged. The frozen
protocol, gold annotation, leakage fixes and a new sealed test period are pending
(`AUDIT_2026-11-15.md` section 6).

## 10. Manual steps still required from you

1. Choose a server (4 GB memory or more) and a domain; run `infra/deploy.sh` there.
2. Set up an email provider (`SMTP_*`); without it nobody can confirm a new account.
3. Rotate the Gemini key.
4. Schedule `infra/backup.sh` and copy the files off the server.
5. Put the server's disk on encrypted storage.
6. Add a grievance contact to the privacy page and have the terms and privacy text reviewed.
7. Decide on a no-retention model provider before opening AI analysis to real buyers.
8. Push the branch and the tag when you are ready: `git push origin nyayasim/foundation v1.0.0-rc1`.
9. Remove the test folders `C:\NyRC1` and `C:\NyRC2` (left in place; they hold a copy of the
   package and one test backup, no real data).
10. Look at the signed-in pages once yourself before showing the site to anyone.
