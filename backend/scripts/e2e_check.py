"""End-to-end check of the running local app, through the website address (so the /api forwarding
and the session cookie are tested too). Uses only FICTIONAL documents (the "Mehra v. Arvant Infra"
demo from scripts/demo_buyer_case.py).

Usage (from backend/, with the API started with -AllowDemo and the website running):
  .\\.venv\\Scripts\\python.exe -m scripts.e2e_check setup      # user, login, case, uploads, negatives
  .\\.venv\\Scripts\\python.exe -m scripts.e2e_check facts      # fact extraction (calls Gemini)
  .\\.venv\\Scripts\\python.exe -m scripts.e2e_check hearing    # start a hearing and wait for it
  .\\.venv\\Scripts\\python.exe -m scripts.e2e_check session    # logout, login again

The demo user's password is generated once and kept in data/demo-credentials.txt (git-ignored);
it is never printed. Each line of output is one check: PASS, FAIL or INFO.
"""

from __future__ import annotations

import io
import json
import quopri
import re
import secrets
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from scripts.demo_buyer_case import AGREEMENT, LETTER, RECEIPTS, pdf

ROOT = Path(__file__).resolve().parents[2]
SITE = "http://localhost:3100"
API = SITE + "/api/v1"
CREDS = ROOT / "data" / "demo-credentials.txt"
STATE = ROOT / "data" / "e2e_state.json"
SAMPLES = ROOT / "demo" / "sample-documents"
EMAIL = "demo.student@example.com"
HEADERS = {"Origin": SITE}
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append(("PASS" if ok else "FAIL", name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)
    return ok


def info(name: str, detail: str = "") -> None:
    print(f"INFO  {name}  {detail}".rstrip(), flush=True)


def password() -> str:
    if not CREDS.exists():
        CREDS.parent.mkdir(parents=True, exist_ok=True)
        CREDS.write_text(f"email: {EMAIL}\npassword: {secrets.token_urlsafe(12)}aA1!\n", encoding="utf-8")
    return CREDS.read_text(encoding="utf-8").split("password: ")[1].strip()


def receipt_png() -> bytes:
    """A fictional receipt as an image, to exercise OCR."""
    img = Image.new("RGB", (1700, 700), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    lines = [
        "ARVANT INFRA PRIVATE LIMITED (DEMO - FICTIONAL)",
        "RECEIPT No. AR/1433",
        "Received with thanks from Ms. Ananya Mehra",
        "the sum of Rs. 10,80,000/- by RTGS dated 15.09.2018",
        "towards instalment of Apartment C-1204.",
    ]
    for i, line in enumerate(lines):
        d.text((80, 80 + i * 100), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def sample_files() -> dict[str, tuple[str, bytes]]:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    files = {
        "agreement.pdf": ("agreement", pdf(AGREEMENT)),
        "receipts.pdf": ("receipt", pdf(RECEIPTS)),
        "builder_letter.pdf": ("builder_letter", pdf(LETTER)),
        "receipt_scan.png": ("receipt", receipt_png()),
    }
    for name, (_, data) in files.items():
        if not (SAMPLES / name).exists():
            (SAMPLES / name).write_bytes(data)
    return {name: (kind, (SAMPLES / name).read_bytes()) for name, (kind, _) in files.items()}


def latest_verify_token() -> str | None:
    outbox = ROOT / "data" / "outbox"
    for f in sorted(outbox.glob("*.txt"), reverse=True):
        text = quopri.decodestring(f.read_bytes()).decode("utf-8", "replace")
        if EMAIL in text and "verify-email?token=" in text:
            return re.search(r"verify-email\?token=([A-Za-z0-9_\-=]+)", text).group(1)
    return None


def client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=180, follow_redirects=False)


def login(c: httpx.Client) -> httpx.Response:
    return c.post(f"{API}/auth/login", json={"email": EMAIL, "password": password()})


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def setup() -> None:
    c = client()
    check("site opens", c.get(SITE + "/").status_code == 200)
    check("health through the site", c.get(SITE + "/health").json() == {"status": "ok"})
    r = c.get(SITE + "/dashboard")
    check("dashboard without login redirects to /login", r.status_code == 307, r.headers.get("location", ""))
    check("API without login is refused", c.get(f"{API}/cases").status_code == 401)

    r = login(c)
    if r.status_code != 200:
        r = c.post(
            f"{API}/auth/signup",
            json={"name": "Demo Student", "email": EMAIL, "password": password(), "accept_terms": True},
        )
        check("signup accepted", r.status_code == 202, f"HTTP {r.status_code}")
        r = login(c)
        check("login before email verification is refused", r.status_code != 200, f"HTTP {r.status_code}")
        token = latest_verify_token()
        check("verification link written to data/outbox", token is not None)
        r = c.post(f"{API}/auth/verify-email", json={"token": token})
        check("email verified with the outbox link", r.status_code == 200, f"HTTP {r.status_code}")
        r = login(c) if "nyayasim_session" not in c.cookies else r
    else:
        info("demo user already exists; signup skipped")
    check("login", r.status_code == 200 or "nyayasim_session" in c.cookies, f"HTTP {r.status_code}")
    set_cookie = " ".join(v for k, v in r.headers.multi_items() if k.lower() == "set-cookie").lower()
    check(
        "session cookie is HttpOnly and SameSite=Lax",
        "httponly" in set_cookie and "samesite=lax" in set_cookie,
    )
    me = c.get(f"{API}/auth/me")
    check("GET /auth/me returns the user", me.status_code == 200 and me.json()["email"] == EMAIL)
    bad = client().post(f"{API}/auth/login", json={"email": EMAIL, "password": "wrong-password-1A!"})
    check("wrong password is refused", bad.status_code in (400, 401), f"HTTP {bad.status_code}")
    r = httpx.post(
        f"{API}/cases", json={"title": "x"}, headers={"Origin": "http://evil.example"}, cookies=c.cookies
    )
    check(
        "request from another origin is refused (CSRF check)", r.status_code == 403, f"HTTP {r.status_code}"
    )
    check("dashboard page with login", c.get(SITE + "/dashboard").status_code == 200)

    r = c.post(
        f"{API}/cases",
        json={"title": "Mehra v. Arvant Infra (DEMO)", "claim_type": "delayed_possession", "is_demo": True},
    )
    check("create demo case", r.status_code == 201, f"HTTP {r.status_code}")
    case_id = r.json()["id"]
    check("case appears in the list", any(x["id"] == case_id for x in c.get(f"{API}/cases").json()))

    docs = {}
    for name, (kind, data) in sample_files().items():
        t = time.monotonic()
        r = c.post(f"{API}/cases/{case_id}/documents", data={"kind": kind}, files={"file": (name, data)})
        ok = check(
            f"upload {name}", r.status_code == 201, f"HTTP {r.status_code}, {time.monotonic() - t:.1f} s"
        )
        if ok:
            d = r.json()
            docs[name] = d["id"]
            p = c.get(f"{API}/cases/{case_id}/documents/{d['id']}/pages/1").json()
            words = len(p["text"].split())
            check(
                f"text read from {name}",
                words > 15,
                f"{d.get('page_count')} page(s), page 1: {words} words, source {p['text_source']}, "
                f"OCR confidence {p['ocr_confidence']}",
            )
            if name.endswith(".png"):
                check(
                    "OCR text of the image contains the amount",
                    "10,80,000" in p["text"],
                    p["text"][:80].replace("\n", " "),
                )

    up = f"{API}/cases/{case_id}/documents"
    r = c.post(up, data={"kind": "receipt"}, files={"file": ("empty.pdf", b"")})
    check(
        "empty upload is refused with a message",
        r.status_code in (400, 422),
        f"HTTP {r.status_code}: {r.text[:90]}",
    )
    r = c.post(up, data={"kind": "receipt"}, files={"file": ("notes.txt", b"just some text")})
    check(
        "unsupported format is refused with a message",
        r.status_code == 422,
        f"HTTP {r.status_code}: {r.text[:90]}",
    )
    r = c.post(up, data={"kind": "receipt"}, files={"file": ("fake.pdf", b"%PDF-1.4 this is not a real pdf")})
    check(
        "damaged PDF is refused, not a server error",
        r.status_code == 422,
        f"HTTP {r.status_code}: {r.text[:90]}",
    )
    r = c.post(up, data={"kind": "nonsense"}, files={"file": ("a.pdf", b"%PDF")})
    check("unknown document type is refused", r.status_code == 422, f"HTTP {r.status_code}")
    r = client().post(up, data={"kind": "receipt"}, files={"file": ("a.pdf", b"%PDF")})
    check("upload without login is refused", r.status_code == 401, f"HTTP {r.status_code}")
    r = c.get(f"{API}/cases/00000000-0000-4000-8000-000000000000")
    check("unknown case gives 404", r.status_code == 404, f"HTTP {r.status_code}")

    r = c.post(f"{API}/cases", json={"title": "Private case (privacy check)", "claim_type": "refund"})
    private_id = r.json()["id"]
    c.post(
        f"{API}/cases/{private_id}/documents",
        data={"kind": "receipt"},
        files={"file": ("receipts.pdf", pdf(RECEIPTS))},
    )
    r = c.post(f"{API}/cases/{private_id}/facts/extract")
    check(
        "non-demo case: fact extraction by the external model is blocked",
        r.status_code == 403,
        f"HTTP {r.status_code}: {r.text[:110]}",
    )
    r = c.post(f"{API}/cases/{private_id}/hearing")
    check(
        "non-demo case: hearing is blocked",
        r.status_code in (403, 422),
        f"HTTP {r.status_code}: {r.text[:110]}",
    )

    STATE.write_text(
        json.dumps({"case_id": case_id, "private_case_id": private_id, "docs": docs}), encoding="utf-8"
    )
    info("demo case id", case_id)


def facts() -> None:
    c = client()
    check("login", login(c).status_code == 200)
    case_id = load_state()["case_id"]
    t = time.monotonic()
    r = c.post(f"{API}/cases/{case_id}/facts/extract", timeout=900)
    if not check(
        "fact extraction (Gemini)",
        r.status_code == 200,
        f"HTTP {r.status_code}, {time.monotonic() - t:.0f} s: {r.text[:200]}",
    ):
        return
    info("extraction summary", json.dumps({k: v for k, v in r.json().items() if k != "rejected"})[:300])
    case = c.get(f"{API}/cases/{case_id}").json()
    fs = case.get("facts", [])
    check("facts are stored", len(fs) > 0, f"{len(fs)} facts")
    check(
        "every fact has a source document, page and quote",
        all(f.get("page_no") and f.get("quote") for f in fs),
    )
    for f in fs:
        info(
            "fact",
            f"{f.get('label')}: {f.get('value')} (page {f.get('page_no')}, confidence {f.get('confidence')})",
        )
    done = [c.post(f"{API}/cases/{case_id}/facts/{f['id']}/confirm").status_code for f in fs]
    check("facts confirmed", all(s == 200 for s in done), f"{len(done)} confirmed")
    info("questions", json.dumps(case.get("questions", []))[:400])


def hearing() -> None:
    c = client()
    check("login", login(c).status_code == 200)
    case_id = load_state()["case_id"]
    r = c.post(f"{API}/cases/{case_id}/hearing")
    if not check(
        "hearing accepted as a background job", r.status_code == 202, f"HTTP {r.status_code}: {r.text[:300]}"
    ):
        return
    run = r.json()
    check(
        "second start while running is refused", c.post(f"{API}/cases/{case_id}/hearing").status_code == 409
    )
    t = time.monotonic()
    while run["status"] == "running" and time.monotonic() - t < 1500:
        time.sleep(15)
        run = c.get(f"{API}/cases/{case_id}/hearing/runs/{run['id']}").json()
    took = time.monotonic() - t
    check(
        "hearing completed",
        run["status"] == "completed",
        f"status {run['status']} after {took:.0f} s; {str(run.get('error'))[:200]}",
    )
    (ROOT / "data" / "e2e_hearing_run.json").write_text(json.dumps(run, indent=1), encoding="utf-8")
    if run["status"] == "completed":
        latest = c.get(f"{API}/cases/{case_id}/hearing")
        check(
            "result stored and returned by GET /hearing",
            latest.status_code == 200 and latest.json()["id"] == run["id"],
        )
        info("result keys", ", ".join(sorted((run.get("result") or {}).keys())))


def session() -> None:
    c = client()
    check("login", login(c).status_code == 200)
    check("logout", c.post(f"{API}/auth/logout").status_code == 200)
    check("after logout the session is refused", c.get(f"{API}/auth/me").status_code == 401)
    check("login again", login(c).status_code == 200)
    check("session works again", c.get(f"{API}/auth/me").status_code == 200)
    case_id = load_state().get("case_id")
    if case_id:
        check(
            "the demo case is still there after logging in again",
            c.get(f"{API}/cases/{case_id}").status_code == 200,
        )


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "setup"
    {"setup": setup, "facts": facts, "hearing": hearing, "session": session}[stage]()
    failed = [r for r in results if r[0] == "FAIL"]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)
