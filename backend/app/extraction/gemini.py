"""Gemini client for field extraction (google-genai SDK).

Temperature 0 and a JSON response schema. Requests are spaced (free-tier rate limits)
and retried with back-off on 429/5xx; any other error is raised to the caller, which
reports it and leaves the order pending.
"""

from __future__ import annotations

import time

from app.extraction.order_fields import ProposedFields


class GeminiExtractor:
    def __init__(self, api_key: str, model: str, min_interval_s: float = 4.0, max_retries: int = 4) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"gemini:{model}"
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self._last: float | None = None

    def _wait(self) -> None:
        if self._last is not None:
            gap = self.min_interval_s - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
        self._last = time.monotonic()

    def propose(self, prompt: str) -> ProposedFields:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ProposedFields,
        )
        delay = 15.0
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
            except errors.APIError as e:
                retryable = e.code == 429 or (e.code or 0) >= 500
                if retryable and attempt < self.max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            if resp.parsed is not None:
                return resp.parsed
            return ProposedFields.model_validate_json(resp.text or "")
        raise RuntimeError("unreachable")


def list_models(api_key: str) -> list[str]:
    """Model names this key can call with generateContent (used to pick/confirm the model)."""
    from google import genai

    client = genai.Client(api_key=api_key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.removeprefix("models/"))
    return sorted(names)
