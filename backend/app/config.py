"""Settings read from environment variables (or backend/.env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NYAYASIM_", extra="ignore")

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3100"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
