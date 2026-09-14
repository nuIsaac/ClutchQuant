from datetime import datetime

import httpx

from app.artifacts import artifact_path, digest
from app.ingestion.provenance import captured_soup


def test_raw_invalid_source_is_kept_before_parsing(tmp_path,monkeypatch):
    import app.artifacts as artifacts
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    raw = b"<html>invalid match structure</html>"
    response = httpx.Response(200,content=raw,request=httpx.Request("GET","https://example.invalid/fixture"))
    soup = captured_soup(response)
    evidence = soup.__dict__["cq_evidence"]
    assert evidence["raw_sha256"] == digest(raw)
    assert artifact_path("raw",evidence["raw_sha256"]).read_bytes() == raw
    assert datetime.fromisoformat(evidence["received_at"]).tzinfo is not None
    assert list((tmp_path/"retrievals").iterdir())


def test_failed_parse_keeps_link_to_raw_receipt(tmp_path,monkeypatch):
    import json
    import pytest
    from bs4 import BeautifulSoup
    import app.artifacts as artifacts
    from app.ingestion import vlr
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    response = httpx.Response(200,content=b"<html>unknown markup</html>",
                              request=httpx.Request("GET","https://example.invalid/123/fixture"))
    soup = captured_soup(response)
    monkeypatch.setattr(vlr,"fetch_page",lambda *_:soup)
    card = BeautifulSoup('<a href="/123/fixture"></a>',"html.parser").a
    with pytest.raises(RuntimeError,match="both teams"):
        vlr.parse_completed_match(None,card)
    receipt = json.loads(next((tmp_path/"parses").iterdir()).read_text())
    assert receipt["status"] == "failed"
    assert receipt["retrieval_sha256"] == soup.__dict__["cq_evidence"]["retrieval_sha256"]
    assert receipt["entity"]["vlr_match_id"] == 123
