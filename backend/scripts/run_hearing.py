"""Run a simulated hearing for a (demo) case with the real model and print a readable summary.

Usage (from backend/):  .\\.venv\\Scripts\\python.exe -m scripts.run_hearing <case id>
"""

from __future__ import annotations

import faulthandler
import sys
import time
import uuid

from sqlalchemy.orm import Session

from app.api.hearing import _embedder, get_hearing_llm
from app.db.session import get_engine
from app.hearing.runner import run_case_hearing


def main() -> int:
    case_id = uuid.UUID(sys.argv[1])
    # If anything hangs, print where every thread is, every 15 minutes.
    faulthandler.dump_traceback_later(900, repeat=True)
    llm = get_hearing_llm()
    original = llm.propose

    def logged(prompt, schema):
        role = schema.__name__
        started = time.monotonic()
        print(f"  calling the model for {role}...", flush=True)
        out = original(prompt, schema)
        print(f"  {role} answered in {time.monotonic() - started:.0f} s", flush=True)
        return out

    llm.propose = logged
    t = time.monotonic()
    with Session(get_engine()) as s:
        run = run_case_hearing(s, case_id, llm, _embedder())
        s.commit()
        r = run.result
    print(f"run {run.id}: {run.status} in {time.monotonic() - t:.0f} s with {run.models}\n")
    print(f"precedents: {len(r['precedents'])}; shares: {r['outcome_shares']}")
    print(f"award: {r['award']}\n")
    for side in ("buyer", "builder"):
        for a in r["arguments"][side]:
            cites = ", ".join(f"{c['complaint_no']} p.{c['page_no']}" for c in a["citations"])
            print(f"[{side} KEPT] {a['heading']}  ({cites})")
    for a in r["arguments"]["removed"]:
        bad = [c.get("reasons") for c in a["citations"] if c.get("status") != "verified"]
        print(f"[{a['side']} REMOVED: {a['removed_because']}] {a['heading']}  {bad[:1]}")
    j = r["judge"]
    print(f"\nJUDGE: {j['outcome']}\n{j['reasoning']}")
    print(f"judge citations kept {len(j['citations'])}, removed {len(j['citations_removed'])}")
    for w in j["weak_points"]:
        print(f"  weak point: {w['title']} -> {w['fix']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
