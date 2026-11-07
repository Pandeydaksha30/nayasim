"""Summarise what is in the order store: coverage, text sources, OCR quality.

Usage (from backend/):  .\\.venv\\Scripts\\python.exe -m scripts.ingest_report
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.config import settings

QUERIES = {
    "orders registered / fetched": """
        SELECT count(*) AS registered, count(fetched_at) AS fetched FROM orders""",
    "fetched orders by text source": """
        SELECT text_source, count(*) AS orders, sum(page_count) AS pages
        FROM orders WHERE fetched_at IS NOT NULL GROUP BY 1 ORDER BY 1""",
    "OCR page confidence": """
        SELECT count(*) AS ocr_pages, round(avg(ocr_confidence), 1) AS mean,
               round(min(ocr_confidence), 1) AS min,
               count(*) FILTER (WHERE ocr_confidence < 60) AS below_60
        FROM order_pages WHERE text_source = 'ocr'""",
    "pages containing Devanagari (Hindi) text": """
        SELECT count(*) FILTER (WHERE text ~ '[\\u0900-\\u097F]') AS with_hindi, count(*) AS pages
        FROM order_pages""",
    "chunks": """
        SELECT count(*) AS chunks, round(avg(char_end - char_start)) AS avg_chars FROM order_chunks""",
    "fetch log": """
        SELECT count(*) AS requests, count(*) FILTER (WHERE error IS NOT NULL) AS errors FROM fetch_log""",
    "fetched by decision year": """
        SELECT extract(year FROM decided_on)::int AS year, count(*) AS fetched
        FROM orders WHERE fetched_at IS NOT NULL GROUP BY 1 ORDER BY 1""",
}


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        for title, sql in QUERIES.items():
            result = c.execute(text(sql))
            print(f"\n{title}")
            cols = list(result.keys())
            print("  " + " | ".join(cols))
            for row in result:
                print("  " + " | ".join("" if v is None else str(v) for v in row))


if __name__ == "__main__":
    main()
