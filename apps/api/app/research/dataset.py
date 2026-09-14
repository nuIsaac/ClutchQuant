"""Export immutable datasets with evidence-backed, conservative availability."""

from collections import defaultdict
from datetime import datetime, timezone
import platform
import subprocess
from types import SimpleNamespace
from importlib.metadata import version

from sqlalchemy import select

from app.artifacts import digest, read_bytes, write_json
from app.match_eligibility import ELIGIBILITY_POLICY_VERSION, match_exclusion_reason
from app.models import Match, MatchObservation


def utc(value) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat() if value is not None else None


def code_identity() -> dict:
    # Source digest includes uncommitted implementation; a Git SHA alone is
    # insufficient in a working tree. No environment/credential files included.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = b"".join(
        str(path.relative_to(root)).replace("\\", "/").encode() + b"\0" + path.read_bytes()
        for path in sorted(root.rglob("*.py"))
    )
    def git(*args):
        try:
            process = subprocess.run(["git", *args], capture_output=True, text=True)
        except OSError:
            return None  # Minimal production images need not contain Git.
        return process.stdout.strip() if process.returncode == 0 else None
    return {
        "git_revision": git("rev-parse", "HEAD"),
        "source_sha256": digest(source),
        "python": platform.python_version(),
        "platform":platform.platform(),
        "dependencies": {name: version(name) for name in
                         ("scikit-learn", "numpy", "scipy", "sqlalchemy")},
    }


def export_dataset(db, as_of: datetime) -> tuple[str, dict]:
    as_of = utc(as_of)
    observations = defaultdict(list)
    raw_hashes = set()
    events = []
    payload_fields = SimpleNamespace(**{
        field:MatchObservation.payload[field].as_integer()
        for field in ("team1_id","team2_id","team1_score","team2_score")
    },status=MatchObservation.payload["status"].as_string(),
       scheduled_at=MatchObservation.payload["scheduled_at"].as_string())
    query = select(MatchObservation,match_exclusion_reason(payload_fields)).order_by(MatchObservation.id)
    for item, reason in db.execute(query):
        received, ingested = utc(item.received_at), utc(item.ingested_at)
        # Neither source receipt nor processing time alone proves the earlier
        # of the two was usable by the application.
        available = max(received, ingested)
        if available <= as_of:
            observations[item.match_id].append((available, item.payload))
            raw_hashes.add(item.raw_sha256)
            events.append({**item.payload,"id":item.match_id,"observation_id":item.id,
                           "raw_sha256":item.raw_sha256,"source_url":item.source_url,
                           "result_observed_at":iso(available),"exclusion_reason":reason})
    for raw_hash in raw_hashes:
        if digest(read_bytes("raw", raw_hash)) != raw_hash:
            raise ValueError("Raw evidence integrity failure")

    rows = []
    for match, reason in db.execute(select(Match, match_exclusion_reason()).order_by(Match.id)):
        scheduled = iso(match.scheduled_at)
        schedule_times, result_times = [], []
        ordered = sorted(observations[match.id],key=lambda pair:pair[0])
        prediction = None
        candidates = sorted({payload["scheduled_at"] for available,payload in ordered
                             if payload.get("status") == "scheduled" and payload.get("scheduled_at")
                             and available < utc(payload["scheduled_at"])},key=utc)
        for deadline in candidates:
            known_before = [pair for pair in ordered if pair[0] < utc(deadline)]
            available,payload = known_before[-1]
            if (payload.get("status") == "scheduled" and payload.get("scheduled_at")
                    and utc(payload["scheduled_at"]) == utc(deadline)
                    and payload.get("team1_id") != payload.get("team2_id")):
                prediction = {"scheduled_at":iso(utc(deadline)),"schedule_observed_at":iso(available),
                              "team1_id":payload["team1_id"],"team2_id":payload["team2_id"]}
                break
        prior = [pair for pair in ordered if scheduled and pair[0] < utc(scheduled)]
        for available, payload in ordered:
            if (payload.get("team1_id"), payload.get("team2_id")) != (match.team1_id, match.team2_id):
                result_times = []
                continue
            if (payload.get("status") == "scheduled" and payload.get("scheduled_at")
                    and scheduled and utc(payload["scheduled_at"]) == utc(scheduled)
                    and prior and (available,payload) == prior[-1]):
                schedule_times.append(available)
            if (payload.get("status") == "completed" and scheduled
                    and payload.get("scheduled_at")
                    and utc(payload["scheduled_at"]) == utc(scheduled) and
                    (payload.get("team1_score"), payload.get("team2_score")) ==
                    (match.team1_score, match.team2_score)):
                result_times.append(available)
            else:
                result_times = []
        rows.append({
            "id": match.id, "vlr_id": match.vlr_id,
            "team1_id": match.team1_id, "team2_id": match.team2_id,
            "team1_score": match.team1_score, "team2_score": match.team2_score,
            "status": match.status, "scheduled_at": scheduled,
            "event_name": match.event_name,
            "exclusion_reason": reason,
            "schedule_observed_at": iso(min(schedule_times)) if schedule_times else None,
            "result_observed_at": iso(min(result_times)) if result_times else None,
            "prediction":prediction,
        })
    payload = {
        "schema_version": 2, "as_of": iso(as_of),
        "eligibility_policy": ELIGIBILITY_POLICY_VERSION,
        "availability_policy": "observed-v1",
        "raw_sha256": sorted(raw_hashes), "rows": rows,"result_events":events,
    }
    return write_json("datasets", payload), payload
