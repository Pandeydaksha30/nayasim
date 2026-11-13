"""The Gemini client falls back to the next model only when the first stays overloaded."""

from __future__ import annotations

import pytest
from google.genai import errors

from app.extraction.gemini import CallTimedOut, GeminiExtractor


def client(**kw) -> GeminiExtractor:
    return GeminiExtractor("test-key-not-real", "primary", min_interval_s=0, log=lambda _: None, **kw)


def test_overloaded_primary_falls_back_and_records_the_model(monkeypatch):
    g = client(fallback_models=("backup",))
    calls = []

    def fake(prompt, schema, model, retries):
        calls.append((model, retries))
        if model == "primary":
            raise errors.APIError(503, {"error": {"message": "high demand", "status": "UNAVAILABLE"}})
        return "answer"

    monkeypatch.setattr(g, "_propose", fake)
    assert g.propose("p", object) == "answer" and g.last_model == "backup"
    assert calls == [("primary", 4), ("backup", 2)]


def test_timeouts_also_fall_back_but_other_errors_do_not(monkeypatch):
    g = client(fallback_models=("backup",))
    monkeypatch.setattr(
        g, "_propose", lambda p, s, m, r: (_ for _ in ()).throw(CallTimedOut("x")) if m == "primary" else "ok"
    )
    assert g.propose("p", object) == "ok"

    def bad_request(p, s, m, r):
        raise errors.APIError(400, {"error": {"message": "bad schema", "status": "INVALID_ARGUMENT"}})

    monkeypatch.setattr(g, "_propose", bad_request)
    with pytest.raises(errors.APIError):
        g.propose("p", object)


def test_no_fallback_configured_raises_the_overload():
    g = client()
    g._propose = lambda *a: (_ for _ in ()).throw(  # type: ignore[method-assign]
        errors.APIError(503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
    )
    with pytest.raises(errors.APIError):
        g.propose("p", object)


def test_an_empty_api_key_means_no_key(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert Settings(_env_file=None).gemini_api_key is None
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert Settings(_env_file=None).gemini_api_key.get_secret_value() == "abc"
