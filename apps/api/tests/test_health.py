from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_expected_response() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "clutchquant-api",
        "version": "0.1.0",
    }

def test_readiness_starting_is_structured_and_retryable(monkeypatch):
    from sqlalchemy.exc import OperationalError
    from types import SimpleNamespace
    import app.main as main
    def unavailable():
        raise OperationalError("test", {}, Exception("offline"))
    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=unavailable))
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "starting", "database": "unavailable"}
    assert response.headers["retry-after"] == "5"
    assert client.get("/health").status_code == 200


def test_readiness_checks_actual_schema_head(monkeypatch):
    from types import SimpleNamespace
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    import app.main as main
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): pass
        def scalar(self, *args): return head
    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=Connection))
    assert client.get("/ready").json()["status"] == "ready"
    head = "old_revision"
    assert client.get("/ready").json()["database"] == "migrations_required"
