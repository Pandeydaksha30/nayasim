"""Create a FICTIONAL demo case, upload generated documents and extract facts with the real model.

Usage (from backend/):  .\\.venv\\Scripts\\python.exe -m scripts.demo_buyer_case

Every name, project and number here is invented (the "Mehra v. Arvant Infra" demo). The case
is marked is_demo, which is the only kind the privacy rule lets go to a data-retaining model.
"""

from __future__ import annotations

import time

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.buyer.documents import store_document
from app.buyer.facts import extract_case_facts
from app.buyer.questions import questions_for
from app.config import settings
from app.db.models import Case, Fact
from app.db.session import get_engine
from app.extraction.gemini import GeminiExtractor
from app.ingestion.pdf_text import find_ocr

AGREEMENT = [
    "AGREEMENT FOR SALE (DEMO - FICTIONAL)\n\nThis Agreement for Sale is made at Greater Noida on 2nd May 2018 "
    "between Arvant Infra Private Limited, a company incorporated under the Companies Act, 2013 (the "
    "'Promoter'), and Ms. Ananya Mehra (the 'Allottee').\n\nThe Promoter is developing the project known as "
    "Skyline Residency, registered with the Real Estate Regulatory Authority under registration number "
    "UPRERAPRJ-DEMO-0417.\n\n1.1 The Promoter agrees to sell and the Allottee agrees to purchase Apartment "
    "No. C-1204 on the twelfth floor of Tower C, having a carpet area of 1,450 square feet.\n\n1.2 The Total "
    "Price of the Apartment is Rs. 72,00,000/- (Rupees Seventy-Two Lakh only), payable as per the "
    "construction-linked plan in Schedule C.",
    "7. POSSESSION OF THE APARTMENT\n\n7.1 The Promoter shall hand over possession of the Apartment to the "
    "Allottee on or before 30th June 2021, unless there is delay due to force majeure as defined in "
    "clause 9.\n\n7.2 If the Promoter fails to hand over possession by the date in clause 7.1, the Promoter "
    "shall pay the Allottee compensation at Rs. 5/- per square foot of carpet area per month for the "
    "period of delay.\n\n7.3 The Allottee shall take possession within two months of the written offer of "
    "possession, failing which holding charges shall apply.",
]
RECEIPTS = [
    "ARVANT INFRA PRIVATE LIMITED (DEMO - FICTIONAL)\nRECEIPT No. AR/0912\n\nReceived with thanks from "
    "Ms. Ananya Mehra the sum of Rs. 7,20,000/- by RTGS dated 12.03.2018 towards booking of Apartment C-1204.",
    "ARVANT INFRA PRIVATE LIMITED (DEMO - FICTIONAL)\nRECEIPT No. AR/1187\n\nReceived with thanks from "
    "Ms. Ananya Mehra the sum of Rs. 14,40,000/- by cheque dated 10.05.2018 towards allotment of "
    "Apartment C-1204.",
]
LETTER = [
    "ARVANT INFRA PRIVATE LIMITED (DEMO - FICTIONAL)\nDate: 10.02.2024\n\nSub: Revised completion schedule, "
    "Skyline Residency Tower C\n\nOwing to circumstances beyond our control, the revised completion date "
    "for Tower C is 31 December 2025. Allottees are requested to pay a cost escalation charge of "
    "Rs. 1,44,000/- before the offer of possession.",
]


def pdf(pages: list[str]) -> bytes:
    doc = FPDF()
    doc.set_font("Helvetica", size=11)
    for body in pages:
        doc.add_page()
        doc.multi_cell(0, 6, body)
    return bytes(doc.output())


def main() -> None:
    if settings.gemini_api_key is None:
        raise SystemExit("GEMINI_API_KEY is not set in backend/.env")
    extractor = GeminiExtractor(settings.gemini_api_key.get_secret_value(), settings.gemini_model,
                                min_interval_s=0)
    with Session(get_engine()) as s:
        case = Case(title="Mehra v. Arvant Infra (DEMO)", claim_type="delayed_possession", is_demo=True)
        s.add(case)
        s.flush()
        for name, kind, pages in (("agreement.pdf", "agreement", AGREEMENT),
                                  ("receipts.pdf", "receipt", RECEIPTS),
                                  ("builder_letter.pdf", "builder_letter", LETTER)):
            d = store_document(s, case.id, name, kind, pdf(pages), find_ocr())
            print(f"uploaded {name}: {d.page_count} pages")
        t = time.monotonic()
        summary = extract_case_facts(s, case.id, extractor)
        s.commit()
        print(f"\nextracted {summary['facts']} facts from {summary['documents']} documents "
              f"in {time.monotonic() - t:.0f} s; rejected {len(summary['rejected'])}; errors {summary['errors']}")
        facts = s.query(Fact).filter(Fact.case_id == case.id).order_by(Fact.key).all()
        for f in facts:
            print(f"  {f.label:24} {f.value:28} p.{f.page_no} [{f.confidence}]  \"{' '.join(f.quote.split())[:70]}\"")
        for r in summary["rejected"]:
            print(f"  REJECTED {r['document']} {r['field']}: {r['reason']}")
        by_key: dict[str, list[str]] = {}
        for f in facts:
            by_key.setdefault(f.key, []).append(f.value)
        print("\nfollow-up questions:")
        for q in questions_for(by_key):
            print(f"  - {q.question}")
        print(f"\ncase id: {case.id}")


if __name__ == "__main__":
    main()
