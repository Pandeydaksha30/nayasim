"""Settings read from environment variables (or backend/.env)."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NYAYASIM_", extra="ignore")

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3100"

    # Local Docker database from infra/docker-compose.yml. Override in production.
    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 (::1) first, and Docker Desktop's
    # relay accepts that connection but never answers (the port is published on IPv4 only), so
    # connecting hangs. Measured: localhost 5.08 s (timeout + fallback), 127.0.0.1 0.03 s.
    database_url: str = (
        "postgresql+psycopg://nyayasim:nyayasim_local_only@127.0.0.1:5432/nyayasim?connect_timeout=10"
    )

    # Gemini key for field extraction. Read from GEMINI_API_KEY (Google's own variable name),
    # normally set in backend/.env, which git ignores. Never logged or printed.
    gemini_api_key: SecretStr | None = Field(None, validation_alias="GEMINI_API_KEY")
    # Model id. gemini-2.5-flash is still *listed* but returns 404 for new accounts (7 Nov 2026);
    # `extract_fields --check-key` makes a real call, so it catches that. Override with
    # NYAYASIM_GEMINI_MODEL in backend/.env.
    # First pass uses the fast model (measured ~4 s/order, 10 of 15 stored); orders it cannot
    # verify are re-run with the stronger one: extract_fields --retry-review --model gemini-3.8-flash
    gemini_model: str = "gemini-3.5-flash-lite"

    # Set true ONLY when the configured model does not retain or train on submitted data (a paid
    # no-retention agreement). Until then real buyers' documents are never sent to the model;
    # only cases marked is_demo (fictional documents) are.
    private_llm_ok: bool = False

    # Local embedding model for order search (fastembed, CPU). Chosen by measurement; see
    # docs/search.md. Its output size must equal the database column (EMBEDDING_DIM).
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # bge v1.5 retrieval convention: instruction on the query, nothing on passages.
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_doc_prefix: str = ""

    # Hearing agents: the stronger model (measured ~30-120 s per call on the free tier).
    hearing_model: str = "gemini-3.8-flash"
    hearing_thinking: str | None = "low"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
