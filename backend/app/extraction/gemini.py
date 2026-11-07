"""Gemini client for field extraction (google-genai SDK).

Temperature 0 and a JSON response schema. Requests are spaced (free-tier rate limits)
and retried with back-off on 429/5xx; any other error is raised to the caller, which
reports it and leaves the order pending.
"""

from __future__ import annotations

import time

from app.extraction.order_fields import ProposedFields

# The SDK sends this to the server as the request deadline: at 120 s long orders (~40k chars)
# ended in "504 Deadline expired" every time, so allow 5 minutes.
REQUEST_TIMEOUT_S = 300


class GeminiExtractor:
    def __init__(
        self,
        api_key: str,
        model: str,
        min_interval_s: float = 4.0,
        max_retries: int = 4,
        log=print,
        thinking: str | None = "low",
    ) -> None:
        from google import genai
        from google.genai import types

        # Without a timeout a stalled request waits forever.
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000)
        )
        self.model = model
        # Extraction is copying, not reasoning: at the default level a call took 22-207 s.
        # None leaves the model's default; otherwise minimal | low | medium | high.
        self.thinking = thinking
        self.name = f"gemini:{model}" + (f":think-{thinking}" if thinking else "")
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.log = log
        self._last: float | None = None
        self.last_call_s: float | None = None

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
            thinking_config=(
                types.ThinkingConfig(thinking_level=types.ThinkingLevel(self.thinking.upper()))
                if self.thinking
                else None
            ),
        )
        delay = 15.0
        for attempt in range(self.max_retries + 1):
            self._wait()
            started = time.monotonic()
            try:
                resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
            except errors.APIError as e:
                retryable = e.code == 429 or (e.code or 0) >= 500
                reason = (e.message or str(e)).splitlines()[0][:160]
                if retryable and attempt < self.max_retries:
                    self.log(
                        f"    gemini {e.code} after {time.monotonic() - started:.0f} s: {reason}; "
                        f"retry {attempt + 1}/{self.max_retries} in {delay:.0f} s"
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except Exception as e:  # timeouts and network errors: also retried, and shown
                if attempt < self.max_retries:
                    self.log(
                        f"    gemini {type(e).__name__} after {time.monotonic() - started:.0f} s; "
                        f"retry {attempt + 1}/{self.max_retries} in {delay:.0f} s"
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            self.last_call_s = time.monotonic() - started
            if resp.parsed is not None:
                return resp.parsed
            return ProposedFields.model_validate_json(resp.text or "")
        raise RuntimeError("unreachable")


def ping(api_key: str, model: str) -> str:
    """One tiny real request. A model can be listed yet refuse calls, so listing is not enough."""
    from google import genai

    # Keep a reference: google-genai 2.x closes a client once it is garbage-collected, and an
    # inline Client(...) can be collected before the request is sent.
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents="Reply with the word: ok")
    return (resp.text or "").strip()[:20]


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
