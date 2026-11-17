"""API tests: the HTTP layer returns exactly what the calculator computes, as strings."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def body(**overrides):
    b = {
        "payments": [
            {"paid_on": "2020-01-01", "amount": "100000", "reference": "R1"},
            {"paid_on": "2021-07-01", "amount": "100000", "reference": "R2"},
        ],
        "possession_promised": "2020-07-01",
        "extension_months": 6,
        "annual_rate_pct": "10",
        "as_of": "2022-01-01",
        "rate_source": "test",
    }
    b.update(overrides)
    return b


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_interest_endpoint_matches_hand_calculation():
    res = client.post("/api/v1/calculations/interest", json=body())
    assert res.status_code == 200, res.text
    data = res.json()
    # 1 Jul 2020 + 6 months = 1 Jan 2021.
    assert data["possession_due"] == "2021-01-01"
    # Delay: R1 from 1 Jan 2021 (365 days) = 10,000.00; R2 from 1 Jul 2021 (184 days) = 5,041.10
    assert [r["interest"] for r in data["delay"]["rows"]] == ["10000.00", "5041.10"]
    assert data["delay"]["interest"] == "15041.10"
    assert data["delay"]["principal"] == "200000"
    # Refund: R1 731 days = 20,027.40; R2 184 days = 5,041.10; total = 2,25,068.50
    assert data["refund"]["interest"] == "25068.50"
    assert data["refund"]["total"] == "225068.50"


def test_rejects_negative_amount_with_422():
    res = client.post(
        "/api/v1/calculations/interest",
        json=body(payments=[{"paid_on": "2020-01-01", "amount": "-1"}]),
    )
    assert res.status_code == 422


def test_rejects_empty_payments_with_422():
    assert client.post("/api/v1/calculations/interest", json=body(payments=[])).status_code == 422


def test_cors_allows_only_configured_origin():
    ok = client.options(
        "/api/v1/calculations/interest",
        headers={"Origin": "http://localhost:3100", "Access-Control-Request-Method": "POST"},
    )
    bad = client.options(
        "/api/v1/calculations/interest",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3100"
    assert "access-control-allow-origin" not in bad.headers


def test_offer_of_possession_stops_delay_interest_two_months_later():
    # Offer 1 Sep 2021 -> delay interest to 1 Nov 2021. R1: 304 days = 8,328.77; R2: 123 days = 3,369.86.
    data = client.post("/api/v1/calculations/interest", json=body(offer_of_possession="2021-09-01")).json()
    assert data["delay_until"] == "2021-11-01"
    assert data["delay_until_basis"] == "offer of possession plus two months"
    assert [r["interest"] for r in data["delay"]["rows"]] == ["8328.77", "3369.86"]
    # The refund is unaffected: it runs to the date the money is returned.
    assert data["refund"]["interest"] == "25068.50"
    # Without an offer, the calculation date is the end.
    assert client.post("/api/v1/calculations/interest", json=body()).json()["delay_until"] == "2022-01-01"
