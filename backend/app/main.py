"""NyayaSim API entry point.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.calculations import router as calculations_router
from app.config import settings

app = FastAPI(title="NyayaSim API", version="0.1.0")

# Only the configured frontend origins; no wildcard with credentials (fixed from ContractIQ).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(calculations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
