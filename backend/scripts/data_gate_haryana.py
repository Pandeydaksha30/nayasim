"""Week 1 data gate for HRERA Gurugram (reproducible version of the 7 Nov 2026 check).

Fetches the public decisions table, counts orders with PDFs, then downloads a random
sample slowly and records whether each PDF has a text layer.

Usage:  uv run python scripts/data_gate_haryana.py --sample 50 --out ../data/gate
Needs:  pypdf  (uv add --dev pypdf)
"""

from __future__ import annotations

import argparse
import html
import io
import json
import random
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

LIST_URL = "https://haryanarera.gov.in/admincontrol/judgements/2"
USER_AGENT = "Mozilla/5.0 (NyayaSim research; slow fetch)"
DELAY_S = 2.5


def fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_table(page: str) -> list[dict]:
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", page, flags=re.S):
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        ]
        links = re.findall(r"href=[\"']([^\"']+)", tr)
        if len(cells) >= 6:
            pdf = links[0] if links else None
            rows.append({"complaint": cells[1], "type": cells[4], "decided": cells[5], "pdf": pdf})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import pypdf  # imported here so the listing step works without it

    args.out.mkdir(parents=True, exist_ok=True)
    rows = parse_table(fetch(LIST_URL).decode("utf-8", errors="ignore"))
    complaints = [r for r in rows if r["type"] == "HRERA Complaints" and r["pdf"]]
    with_pdf = sum(1 for r in rows if r["pdf"])
    print(f"rows={len(rows)} with_pdf={with_pdf} complaints_with_pdf={len(complaints)}")
    print("by year:", sorted(Counter(r["decided"][-4:] for r in complaints).items()))

    random.seed(args.seed)
    results = []
    for r in random.sample(complaints, min(args.sample, len(complaints))):
        rec = dict(r)
        try:
            data = fetch(r["pdf"], timeout=60)
            rec["bytes"] = len(data)
            rec["is_pdf"] = data[:4] == b"%PDF"
            if rec["is_pdf"]:
                (args.out / f"{r['complaint']}.pdf").write_bytes(data)
                reader = pypdf.PdfReader(io.BytesIO(data))
                rec["pages"] = len(reader.pages)
                rec["chars"] = sum(len(p.extract_text() or "") for p in reader.pages)
        except Exception as e:  # recorded, never silently dropped
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        results.append(rec)
        print(json.dumps(rec), flush=True)
        time.sleep(DELAY_S)

    (args.out / "results.json").write_text(json.dumps(results, indent=1))
    pdfs = [r for r in results if r.get("is_pdf")]
    text = [r for r in pdfs if r.get("chars", 0) > 500]
    print(
        f"pdf={len(pdfs)}/{len(results)} text_layer={len(text)} scanned={len(pdfs) - len(text)} "
        f"errors={sum('error' in r for r in results)}"
    )


if __name__ == "__main__":
    main()
