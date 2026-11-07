"""Settings read from environment variables (or backend/.env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NYAYASIM_", extra="ignore")

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3100"

    # Local Docker database from infra/docker-compose.yml. Override in production.
    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 (::1) first, and Docker Desktop's
    # relay accepts that connection but never answers (the port is published on IPv4 only), so
    # connecting hangs. Measured: localhost 5.08 s (timeout + fallback), 127.0.0.1 0.03 s.
    database_url: str = "postgresql+psycopg://nyayasim:nyayasim_local_only@127.0.0.1:5432/nyayasim?connect_timeout=10"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
