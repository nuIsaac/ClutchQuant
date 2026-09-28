"""Authorized JSON export boundary. No scraping or anti-bot workaround.

Export timestamps are not trusted as historical availability. Local receipt and
processing establish availability, exactly as for a newly retrieved VLR page.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.artifacts import write_bytes


class ThespikeSource:
    name = "thespike"

    def __init__(self, path=None):
        self.path = path or os.getenv("THESPIKE_EXPORT_PATH")

    def discover_upcoming_matches(self, pages=1):
        if not self.path:
            raise RuntimeError("THESPIKE_EXPORT_PATH is not configured; authorized export required")
        path = Path(self.path)
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        if not 0 <= age <= 900:
            raise ValueError("THESPIKE export must be refreshed within 15 minutes")
        raw = path.read_bytes()
        if len(raw) > 5_000_000:
            raise ValueError("THESPIKE export exceeds 5 MB")
        records = json.loads(raw)
        if not isinstance(records, list) or len(records) > 500:
            raise ValueError("Expected at most 500 match records")
        received = datetime.now(timezone.utc)
        sha = write_bytes("raw", raw)
        for item in records:
            at = datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00"))
            if at.tzinfo is None:
                raise ValueError("Explicit schedule timezone required")
            url = item["source_url"]
            if urlparse(url).scheme != "https" or urlparse(url).hostname not in {"thespike.gg", "www.thespike.gg"}:
                raise ValueError("Expected THESPIKE HTTPS provenance URL")
            if item.get("status", "scheduled") != "scheduled" or any(item.get(k) is not None for k in ("team1_score", "team2_score")):
                raise ValueError("Phase A accepts upcoming schedules only")
            if at <= received:
                continue
            for key in ("external_id",):
                if not isinstance(item.get(key), (str, int)) or isinstance(item.get(key), bool) or not str(item[key]).strip():
                    raise ValueError("Missing external match identity")
            teams = []
            for key in ("team1", "team2"):
                team = item[key]
                if not isinstance(team.get("external_id"), (str, int)) or isinstance(team.get("external_id"), bool) or not str(team["external_id"]).strip() or not isinstance(team.get("name"), str) or not team["name"].strip():
                    raise ValueError("Missing external team identity")
                teams.append({"external_id": str(team["external_id"]), "name": team["name"]})
            yield dict(source=self.name, external_id=str(item["external_id"]), source_url=url,
                       team1=teams[0], team2=teams[1], scheduled_at=at,
                       event_name=item.get("event_name"), stage=item.get("stage"), best_of=item.get("best_of"),
                       status="scheduled", team1_score=None, team2_score=None,
                       evidence={"source": self.name, "received_at": received.isoformat(),
                                 "raw_sha256": sha, "source_url": url})
