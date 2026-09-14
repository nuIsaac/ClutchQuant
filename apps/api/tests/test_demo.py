import gzip
import os
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, text

from app import artifacts, pipeline


def test_real_postgres_overlap_skips_before_any_write(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires the isolated PostgreSQL test database")
    engine = create_engine(url)
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "write_json", lambda *a: pytest.fail("Overlap wrote evidence"))
    try:
        with engine.connect() as guard:
            guard.execute(text("SELECT pg_advisory_lock(:id)"), {"id": pipeline.LOCK_ID})
            try:
                assert pipeline.run_cycle(forecast_first=True) == {"status": "SKIPPED_OVERLAP"}
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": pipeline.LOCK_ID})
    finally:
        engine.dispose()


@pytest.fixture
def remote(monkeypatch, tmp_path):
    objects = {}
    monkeypatch.setattr(artifacts, "ARTIFACT_ROOT", tmp_path / "first")
    monkeypatch.setattr(artifacts, "ARTIFACT_BACKEND", "supabase")
    monkeypatch.setattr(artifacts, "ARTIFACT_READ_ONLY", False)
    monkeypatch.setattr(artifacts, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(artifacts, "SUPABASE_SERVICE_ROLE_KEY", "test-only")
    def request(method, url, **kwargs):
        assert kwargs["headers"]["x-upsert"] == "false"
        key = url.split("/v1/", 2)[-1]
        if method == "POST":
            if key in objects:
                return httpx.Response(409)
            objects[key] = kwargs["content"]
            return httpx.Response(200)
        assert "/object/authenticated/" in url
        return httpx.Response(200, content=objects[key]) if key in objects else httpx.Response(404)
    monkeypatch.setattr(artifacts.httpx, "request", request)
    return objects


def test_shared_immutable_artifacts(remote, monkeypatch, tmp_path):
    content = b'{"evidence":"original"}'
    key = artifacts.write_bytes("raw", content)
    assert key == artifacts.digest(content)
    assert artifacts.write_bytes("raw", content) == key
    assert gzip.decompress(next(iter(remote.values()))) == content
    monkeypatch.setattr(artifacts, "ARTIFACT_ROOT", tmp_path / "second")
    monkeypatch.setattr(artifacts, "ARTIFACT_READ_ONLY", True)
    assert artifacts.read_bytes("raw", key) == content
    with pytest.raises(PermissionError):
        artifacts.write_bytes("raw", content)


def test_storage_failure_never_caches_success(remote, monkeypatch):
    monkeypatch.setattr(artifacts.httpx, "request", lambda *a, **k: httpx.Response(507))
    with pytest.raises(RuntimeError):
        artifacts.write_bytes("raw", b"evidence")
    assert not artifacts.artifact_path("raw", artifacts.digest(b"evidence")).exists()


def test_remote_corruption_is_rejected(remote, monkeypatch, tmp_path):
    key = artifacts.write_bytes("raw", b"original")
    remote[next(iter(remote))] = gzip.compress(b"modified")
    monkeypatch.setattr(artifacts, "ARTIFACT_ROOT", tmp_path / "empty")
    with pytest.raises(ValueError, match="hash mismatch"):
        artifacts.read_bytes("raw", key)


@pytest.mark.parametrize("demo,expected", [(True, ["upcoming", "freeze", "results", "score"]),
                                          (False, ["results", "upcoming", "freeze", "score"])])
def test_cycle_order(monkeypatch, demo, expected):
    steps = []
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def scalar(self, *args): return True
        def execute(self, *args): pass
        def add(self, *args): pass
        def commit(self): pass
    monkeypatch.setattr(pipeline, "engine", SimpleNamespace(connect=Session))
    monkeypatch.setattr(pipeline, "SessionLocal", Session)
    monkeypatch.setattr(pipeline, "write_json", lambda *args: "0" * 64)
    def collect(name):
        steps.append(name)
        return {"failed": 0}
    monkeypatch.setattr(pipeline, "sync_upcoming_matches", lambda _: collect("upcoming"))
    monkeypatch.setattr(pipeline, "sync_recent_results", lambda _: collect("results"))
    monkeypatch.setattr(pipeline, "generate", lambda *a, **k: steps.append("freeze"))
    monkeypatch.setattr(pipeline, "snapshot_current", lambda: ("0" * 64, {}))
    def score(*args):
        steps.append("score")
        return "0" * 64, {"counts": {}}
    monkeypatch.setattr(pipeline, "build_report", score)
    assert pipeline.run_cycle(forecast_first=demo)["status"] == "SUCCEEDED"
    assert steps == expected
