"""Tests for the Flask server endpoints."""

import json
import pytest

from src.server import create_app
from src.utils import DataFetcher


@pytest.fixture
def client():
    fetcher = DataFetcher(use_synthetic=True)
    app = create_app(fetcher=fetcher)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_signal_endpoint(client):
    resp = client.get("/signal/AAPL?interval=1h")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ticker"] == "AAPL"
    assert "rating" in data
    assert "score" in data
    assert "signals" in data


def test_webhook_missing_fields(client):
    resp = client.post("/webhook", data=json.dumps({"foo": "bar"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_webhook_valid(client):
    payload = {"ticker": "AAPL", "price": 150.0, "action": "buy"}
    resp = client.post("/webhook", data=json.dumps(payload),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "processed"
    assert data["ticker"] == "AAPL"
