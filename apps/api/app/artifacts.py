"""Content-addressed artifacts. Existing bytes are never replaced.

Use durable storage in production; this directory can be archived to S3 with
the same keys. Hash validation catches partial writes and modified artifacts.
"""

import hashlib
import json
import re
import gzip

import httpx

from app.settings import (ARTIFACT_ROOT, ARTIFACT_BACKEND, ARTIFACT_READ_ONLY,
                          SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ARTIFACT_BUCKET)


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
    if ARTIFACT_READ_ONLY:
        raise PermissionError("Artifact writes are disabled")
    key = digest(content)
    if ARTIFACT_BACKEND == "supabase":
        # No upsert: a successful remote write must precede any DB reference.
        response = remote_request("POST",kind,key,content=gzip.compress(content,mtime=0))
        if response.status_code in (400,409):
            if remote_read(kind,key) != content:
                raise ValueError("Remote artifact integrity failure")
        elif not response.is_success:
            raise RuntimeError(f"Artifact upload failed (HTTP {response.status_code})")
    cache_bytes(kind,key,content)
    return key


def cache_bytes(kind, key, content):
    path = artifact_path(kind, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError(f"Artifact integrity failure: {kind}/{key}")


def remote_request(method, kind, key, *, content=None):
    artifact_path(kind,key)  # Validate kinds/hash before constructing a URL.
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", SUPABASE_ARTIFACT_BUCKET):
        raise ValueError("Invalid artifact bucket name")
    route = "object/authenticated" if method == "GET" else "object"
    url = f"{SUPABASE_URL}/storage/v1/{route}/{SUPABASE_ARTIFACT_BUCKET}/v1/{kind}/{key}.gz"
    headers = {"Authorization":f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
               "apikey":SUPABASE_SERVICE_ROLE_KEY,"Content-Type":"application/gzip","x-upsert":"false"}
    # Never include response bodies, credentials, or signed URLs in error messages.
    return httpx.request(method,url,headers=headers,content=content,timeout=30,follow_redirects=False)


def remote_read(kind,key):
    response = remote_request("GET",kind,key)
    if response.status_code == 404:
        raise FileNotFoundError("Remote artifact missing")
    if not response.is_success:
        raise RuntimeError(f"Artifact download failed (HTTP {response.status_code})")
    try:
        content = gzip.decompress(response.content)
    except (OSError,EOFError) as error:
        raise ValueError("Invalid compressed artifact") from error
    if digest(content) != key:
        raise ValueError("Remote artifact hash mismatch")
    return content


def read_bytes(kind,key):
    path = artifact_path(kind,key)
    if not path.exists() and ARTIFACT_BACKEND == "supabase":
        cache_bytes(kind,key,remote_read(kind,key))
    content = path.read_bytes()
    if digest(content) != key:
        raise ValueError("Artifact hash mismatch")
    return content


def write_json(kind: str, value) -> str:
    return write_bytes(kind, canonical_json(value))


def read_json(kind: str, key: str):
    return json.loads(read_bytes(kind,key))
