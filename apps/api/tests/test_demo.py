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


def test_transient_download_retries_without_exposing_transport_details(remote, monkeypatch):
    delays = []
    monkeypatch.setattr(artifacts.time, "sleep", delays.append)
    content = b"verified evidence"
    responses = iter([httpx.ReadTimeout("sensitive transport details"),
                      httpx.Response(429, headers={"retry-after": "5"}),
                      httpx.Response(200, content=gzip.compress(content))])
    def request(*args, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(artifacts.httpx, "request", request)
    assert artifacts.remote_read("raw", artifacts.digest(content)) == content
    assert delays == [1, 5]


def test_uncertain_upload_verifies_conflict_instead_of_overwriting(remote, monkeypatch):
    original = artifacts.httpx.request
    attempts = []
    monkeypatch.setattr(artifacts.time, "sleep", lambda _: None)
    def request(method, url, **kwargs):
        attempts.append(method)
        response = original(method, url, **kwargs)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("response lost after write")
        return response
    monkeypatch.setattr(artifacts.httpx, "request", request)
    content = b"immutable evidence"
    assert artifacts.write_bytes("raw", content) == artifacts.digest(content)
    assert attempts == ["POST", "POST", "GET"]
    assert len(remote) == 1


@pytest.mark.parametrize("failure", [429, 503, "timeout"])
def test_retries_are_bounded_and_failure_never_caches(remote, monkeypatch, failure):
    attempts, delays = [], []
    monkeypatch.setattr(artifacts.time, "sleep", delays.append)
    def request(*args, **kwargs):
        attempts.append(1)
        if failure == "timeout":
            raise httpx.ReadTimeout("secret detail")
        return httpx.Response(failure, headers={"retry-after": "3600"})
    monkeypatch.setattr(artifacts.httpx, "request", request)
    with pytest.raises(RuntimeError) as error:
        artifacts.write_bytes("raw", b"evidence")
    assert "secret" not in str(error.value)
    assert len(attempts) == 4
    assert len(delays) == 3 and max(delays) <= 30
    assert not artifacts.artifact_path("raw", artifacts.digest(b"evidence")).exists()


@pytest.mark.parametrize("status", [401, 403, 404, 507])
def test_permanent_storage_errors_do_not_retry(remote, monkeypatch, status):
    monkeypatch.setattr(artifacts.time, "sleep", lambda _: pytest.fail("Permanent error retried"))
    monkeypatch.setattr(artifacts.httpx, "request", lambda *a, **k: httpx.Response(status))
    assert artifacts.remote_request("GET", "raw", "a" * 64).status_code == status
