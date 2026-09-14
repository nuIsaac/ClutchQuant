from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.artifacts import write_bytes, write_json


def captured_soup(response):
    # This is observation time, never a claimed original publication time.
    received_at = datetime.now(timezone.utc).isoformat()
    raw_sha256 = write_bytes("raw", response.content)
    evidence = {
        "source_url": str(response.url),
        "received_at": received_at,
        "raw_sha256": raw_sha256,
        "http_status": response.status_code,
        "source": "vlr",
        "capture_version": "http-body-v1",
        "parsing_status": "not_attempted",
    }
    evidence["retrieval_sha256"] = write_json("retrievals", evidence)
    soup = BeautifulSoup(response.text, "html.parser")
    soup.__dict__["cq_evidence"] = evidence
    return soup


def record_parse(evidence, status, *, entity=None, error=None):
    """Append a parse receipt; never rewrite the original retrieval manifest."""
    if evidence is None:
        return None
    return write_json("parses", {
        "retrieval_sha256": evidence.get("retrieval_sha256"),
        "raw_sha256": evidence["raw_sha256"], "source_url": evidence["source_url"],
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "parser_version": "vlr-match-v2", "status": status,
        "entity": entity, "error_type": type(error).__name__ if error else None,
    })
