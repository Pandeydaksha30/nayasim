"""Check that Postgres is reachable, trying each address with a 5-second timeout.

Usage (from backend/):  .\\.venv\\Scripts\\python.exe -m scripts.check_db
"""

import time

import psycopg
from sqlalchemy.engine import make_url

from app.config import settings

url = make_url(settings.database_url)
for host in dict.fromkeys([url.host or "127.0.0.1", "127.0.0.1", "localhost", "::1"]):
    t = time.time()
    try:
        with psycopg.connect(
            host=host,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            dbname=url.database,
            connect_timeout=5,
        ) as c:
            version = c.execute("select version()").fetchone()[0][:40]
        print(f"{host:10} OK   {time.time() - t:.2f}s  {version}")
    except Exception as e:  # noqa: BLE001 - this is a diagnostic; every failure is printed
        print(f"{host:10} FAIL {time.time() - t:.2f}s  {type(e).__name__}: {str(e)[:120]}")
