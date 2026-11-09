import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import main, security
from app.database import get_db_names

TOKEN = "test-access-code-" * 3
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def sql(self, query, params=None):
        self.calls.append((query, params))
        self.query = query
        return self

    def collect(self):
        if "cortex.complete" in self.query:
            return [{"LLM_RESPONSE": '{"budget_max": 1000}'}]
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_TOKEN", TOKEN)
    monkeypatch.delenv("ALLOW_LOCAL_DEMO", raising=False)
    for name in ("RICHGO", "AJD", "SPH"):
        monkeypatch.setenv(f"SNOWFLAKE_DB_{name}", f"TEST_{name}")
    monkeypatch.setattr(main, "session", FakeSession())
    security._requests.clear()
    # Do not enter lifespan: no real Snowflake connection is created.
    return TestClient(main.app)


@pytest.mark.parametrize("path,payload,malicious", [
    ("/api/analyze-prompt", {"prompt": "$$'); SELECT 'injected"}, "$$'); SELECT 'injected"),
    ("/api/ask-dong", {"dong_name": "$$ injected", "question": "' injected"}, "$$ injected"),
    ("/api/rental-insight", {"dong_name": "동", "sgg_name": "구", "sd_name": "' OR 1=1 --"}, "' OR 1=1 --"),
])
def test_untrusted_values_are_bound(client, path, payload, malicious):
    response = client.post(path, json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    calls = main.session.calls
    assert calls
    assert all(malicious not in query for query, _ in calls)
    assert any(any(malicious in str(p) for p in (params or [])) for _, params in calls)


def test_budget_is_bound(client):
    result = client.post("/api/recommend-apartments", json={"budget_max": 123456}, headers=HEADERS)
    assert result.status_code == 200
    query, params = main.session.calls[0]
    assert "123456" not in query
    assert params == [123456]


@pytest.mark.parametrize("budget", ["1 OR 1=1", -1, 1.5, True, 100_000_000_000_001])
def test_invalid_budgets_never_reach_sql(client, budget):
    assert client.post("/api/recommend-apartments", json={"budget_max": budget}, headers=HEADERS).status_code == 422
    assert not main.session.calls


def test_missing_auth_and_disabled_configuration(client, monkeypatch):
    assert client.post("/api/analyze-prompt", json={"prompt": "hello"}).status_code == 401
    monkeypatch.delenv("DEMO_ACCESS_TOKEN")
    assert client.post("/api/analyze-prompt", json={"prompt": "hello"}, headers=HEADERS).status_code == 503
    assert not main.session.calls


def test_bounded_body_does_not_trust_content_length(client):
    response = client.post("/api/analyze-prompt", content=b"x" * 70_000,
                           headers={**HEADERS, "Content-Type": "application/json", "Content-Length": "1"})
    assert response.status_code == 413
    assert not main.session.calls


def test_provider_exception_is_not_disclosed(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("fake-sensitive-provider-details")
    monkeypatch.setattr(main.session, "sql", fail)
    response = client.post("/api/analyze-prompt", json={"prompt": "hello"}, headers=HEADERS)
    assert response.status_code == 500
    assert "fake-sensitive" not in response.text


def test_invalid_database_identifier(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_DB_RICHGO", 'db"; SELECT 1 --')
    with pytest.raises(RuntimeError, match="Invalid"):
        get_db_names()


def test_rate_limit(client):
    responses = [client.post("/api/analyze-prompt", json={"prompt": "hello"}, headers=HEADERS) for _ in range(21)]
    assert responses[-1].status_code == 429
    assert responses[-1].headers["retry-after"] == "60"
    assert len(main.session.calls) == 20

