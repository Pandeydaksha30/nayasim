"""NyayaSim API entry point.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.calculations import router as calculations_router
from app.api.cases import router as cases_router
from app.api.hearing import router as hearing_router
from app.config import settings
from app.middleware import SecurityMiddleware

log = logging.getLogger("nyayasim")


def _housekeeping_once() -> None:
    from sqlalchemy.orm import Session

    from app.auth.service import purge_expired
    from app.db.session import get_engine

    with Session(get_engine()) as s:
        counts = purge_expired(s)
        s.commit()
    log.info("Housekeeping: removed %s", counts)


async def _housekeeping_loop() -> None:
    """Daily: expired sessions and email links, and audit events past their retention period."""
    while True:
        try:
            await asyncio.to_thread(_housekeeping_once)
        except Exception:  # noqa: BLE001 - logged with traceback, retried tomorrow
            log.exception("Housekeeping failed")
        await asyncio.sleep(24 * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_housekeeping_loop())
    yield
    task.cancel()


app = FastAPI(title="NyayaSim API", version="0.2.0", lifespan=lifespan)

app.add_middleware(SecurityMiddleware)

# Only the configured frontend origins; no wildcard with credentials (fixed from ContractIQ).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # the session cookie; never combined with a wildcard origin
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(calculations_router)
app.include_router(cases_router)
app.include_router(hearing_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
