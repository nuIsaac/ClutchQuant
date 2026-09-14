"""Content-addressed artifacts. Existing bytes are never replaced.

Use durable storage in production; this directory can be archived to S3 with
the same keys. Hash validation catches partial writes and modified artifacts.
"""

import hashlib
import json
import re

from app.settings import ARTIFACT_ROOT


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def artifact_path(kind: str, sha256: str):
    if kind not in {"raw", "retrievals", "datasets", "reports", "runs", "parses", "jobs"}:
        raise ValueError("Unsupported artifact kind")
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("Invalid SHA-256")
    return ARTIFACT_ROOT / kind / sha256


def write_bytes(kind: str, content: bytes) -> str:
    key = digest(content)
    path = artifact_path(kind, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError(f"Artifact integrity failure: {kind}/{key}")
    return key


def write_json(kind: str, value) -> str:
    return write_bytes(kind, canonical_json(value))


def read_json(kind: str, key: str):
    content = artifact_path(kind, key).read_bytes()
    if digest(content) != key:
        raise ValueError("Artifact hash mismatch")
    return json.loads(content)
