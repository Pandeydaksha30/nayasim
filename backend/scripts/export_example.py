"""Record the public example case from a REAL run, so the website's example shows nothing invented.

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.export_example --case <case id>

The case must be a demo case (fictional documents, made by scripts.demo_buyer_case) with a
completed hearing. The script calls this server's own API as the case owner and saves every
answer the case pages read: the case, each page's text, picture and highlights, the latest
hearing, the estimate, the draft, the questions asked and the latest agent runs.

Output:
  frontend/lib/example-snapshot.json      path -> recorded API answer (ids replaced by "demo")
  frontend/public/example/pages/*.png     page pictures

The buyer's documents in the example are fictional. The past orders, their quotes, the outcome
counts and the money figures are exactly what the system produced; nothing is edited by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db.models import Case, User
from app.db.session import get_engine
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "frontend" / "lib" / "example-snapshot.json"
OUT_PAGES = ROOT / "frontend" / "public" / "example" / "pages"
AGENT_RUNS_KEPT = 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="id of a demo case with a completed hearing")
    ap.add_argument(
        "--agent-runs", type=int, default=AGENT_RUNS_KEPT, help="how many of the latest agent runs to keep"
    )
    args = ap.parse_args()
    case_id = str(uuid.UUID(args.case))

    with Session(get_engine(), expire_on_commit=False) as s:
        case = s.get(Case, uuid.UUID(case_id))
        if case is None:
            print("error: case not found", file=sys.stderr)
            return 1
        if not case.is_demo:
            print("error: only a demo case (fictional documents) may be published", file=sys.stderr)
            return 1
        owner = s.get(User, case.user_id) if case.user_id else s.query(User).first()
        s.expunge_all()
    app.dependency_overrides[current_user] = lambda: owner
    client = TestClient(app)
    base = f"/api/v1/cases/{case_id}"

    def get(path: str):
        r = client.get(path)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r

    case_json = get(base).json()
    doc_alias = {d["id"]: f"doc-{i}" for i, d in enumerate(case_json["documents"], start=1)}

    def clean(obj):
        """Replace the real case and document ids everywhere in a recorded answer."""
        text = json.dumps(obj, ensure_ascii=False).replace(case_id, "demo")
        for real, alias in doc_alias.items():
            text = text.replace(real, alias)
        return json.loads(text)

    responses: dict[str, object] = {}

    def record(path: str, body) -> None:
        responses[clean(path)] = clean(body)

    case_out = {**case_json, "shared": True}
    record(base, case_out)

    OUT_PAGES.mkdir(parents=True, exist_ok=True)
    for old in OUT_PAGES.glob("*.png"):
        old.unlink()
    pictures = 0
    for d in case_json["documents"]:
        for n in range(1, d["page_count"] + 1):
            page = f"{base}/documents/{d['id']}/pages/{n}"
            record(page, get(page).json())
            img = get(f"{page}/image")
            if img is not None:
                (OUT_PAGES / f"{doc_alias[d['id']]}-{n}.png").write_bytes(img.content)
                pictures += 1
    for f in case_json["facts"]:
        path = (
            f"{base}/documents/{f['document_id']}/pages/{f['page_no']}/highlight"
            f"?start={f['char_start']}&end={f['char_end']}"
        )
        record(path, get(path).json())

    hearing = get(f"{base}/hearing")
    if hearing is None:
        print("error: this case has no completed hearing; run one first", file=sys.stderr)
        return 1
    record(f"{base}/hearing", hearing.json())
    record(f"{base}/hearing/active", None)
    record(f"{base}/estimate", get(f"{base}/estimate").json())
    record(f"{base}/draft", get(f"{base}/draft").json())
    record(f"{base}/questions", get(f"{base}/questions").json())
    runs = [r for r in get(f"{base}/agent/runs").json() if r["status"] != "running"][: args.agent_runs]
    record(f"{base}/agent/runs", runs)
    for r in runs:
        record(f"{base}/agent/runs/{r['id']}", r)

    snapshot = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": "Recorded from a real run on fictional buyer documents by scripts/export_example.py. "
        "Not edited by hand.",
        "responses": responses,
    }
    OUT_JSON.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    h = hearing.json()["result"]
    docs, facts = len(case_json["documents"]), len(case_json["facts"])
    print(f"case        {case_json['title']}: {docs} documents, {facts} facts")
    print(f"pages       {pictures} pictures -> {OUT_PAGES}")
    print(f"hearing     {len(h['precedents'])} orders, bench: {h['judge']['outcome']}")
    print(f"agent runs  {len(runs)}; questions {len(responses[clean(base + '/questions')])}")
    print(f"wrote       {OUT_JSON} ({OUT_JSON.stat().st_size // 1024} KB, {len(responses)} answers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
