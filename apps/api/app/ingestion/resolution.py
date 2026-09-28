"""Conservative canonical resolution. Source disagreements retain raw evidence."""
from datetime import datetime, timedelta, timezone
import logging
import re
import unicodedata

from sqlalchemy import or_, select, text
from app.artifacts import canonical_json, digest
from app.models import Match, MatchObservation, MatchSource, SourceIssue, Team, TeamAlias, TeamSourceIdentity

log = logging.getLogger(__name__)


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def issue(db, source, external_id, kind, details, match_id=None):
    key = digest(canonical_json([source, str(external_id), kind, {k: v for k, v in details.items() if k != "evidence"}, match_id]))
    if not db.scalar(select(SourceIssue).where(SourceIssue.issue_key == key)):
        db.add(SourceIssue(issue_key=key, source=source, external_id=str(external_id),
                           kind=kind, details=details, match_id=match_id,
                           created_at=datetime.now(timezone.utc)))
        db.flush()
        log.warning("%s source=%s external_id=%s canonical_id=%s details=%s", kind, source, external_id, match_id, details)


class UnresolvedTeam(ValueError):
    pass


def resolve_team(db, source, data):
    external = str(data.get("external_id") or data.get("vlr_id") or "")
    name = data.get("name", "").strip()
    if not external or not normalize(name) or normalize(name) in {"tbd", "unknown", "winner", "loser"}:
        raise UnresolvedTeam("Missing team identity")
    identity = db.scalar(select(TeamSourceIdentity).where(
        TeamSourceIdentity.source == source, TeamSourceIdentity.external_id == external))
    if identity:
        identity.external_name = name
        team = db.get(Team, identity.team_id)
        if source == "vlr":
            team.name = name
        return team
    legacy = db.scalar(select(Team).where(Team.vlr_id == int(external))) if source == "vlr" else None
    candidates = [legacy] if legacy else []
    matched_alias = False
    if not candidates:
        # A second identity from the same source is not a name-based rename.
        occupied = set(db.scalars(select(TeamSourceIdentity.team_id).where(TeamSourceIdentity.source == source)))
        teams = db.scalars(select(Team)).all()
        candidates = [t for t in teams if t.id not in occupied and
                      not (source == "vlr" and t.vlr_id is not None) and normalize(t.name) == normalize(name)]
        if not candidates:
            aliases = set(db.scalars(select(TeamAlias.team_id).where(
                TeamAlias.source.in_([source, "*"]), TeamAlias.normalized_alias == normalize(name))))
            matched_alias = True
            candidates = [t for t in teams if t.id in aliases and t.id not in occupied and
                          not (source == "vlr" and t.vlr_id is not None)]
    if not candidates:
        # Suffix stripping is a review suggestion, never sufficient identity proof.
        stem = lambda value: re.sub(r"\s+(esports|e sports|gaming)$", "", normalize(value))
        similar = [t.id for t in db.scalars(select(Team))
                   if stem(t.name) == stem(name) and normalize(t.name) != normalize(name)]
        if similar:
            raise UnresolvedTeam(f"Alias review required for {name}; candidate teams={similar}")
    if len(candidates) > 1:
        issue(db, source, external, "UNRESOLVED_TEAM", {"name": name, "candidates": [t.id for t in candidates]})
        raise UnresolvedTeam(name)
    if candidates and not matched_alias and candidates[0].vlr_id is None and not db.scalar(
            select(TeamSourceIdentity.id).where(TeamSourceIdentity.team_id == candidates[0].id)):
        raise UnresolvedTeam(f"Legacy unknown team {candidates[0].id} requires explicit identity review")
    team = candidates[0] if candidates else Team(name=name, vlr_id=int(external) if source == "vlr" else None)
    db.add(team)
    db.flush()
    if source == "vlr":
        team.vlr_id = int(external)
        team.name = name
    db.add(TeamSourceIdentity(team_id=team.id, source=source, external_id=external, external_name=name))
    db.flush()
    return team


def save_source_match(db, data):
    source = data.get("source", "vlr")
    external = str(data.get("external_id") or data.get("vlr_id"))
    # Shared transaction lock also covers standalone legacy ingestion commands.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(731940272)"))
    evidence = data.get("evidence")
    key_payload = ({"retrieval": evidence, "vlr_match_id": int(external), "parser": "vlr-match-v2", "status": data["status"]}
                   if source == "vlr" else {"retrieval": evidence, "source": source, "id": external, "status": data["status"]})
    evidence_key = digest(canonical_json(key_payload)) if evidence else None
    if evidence_key:
        existing = db.scalar(select(MatchObservation).where(MatchObservation.evidence_key == evidence_key))
        if existing:
            return db.get(Match, existing.match_id)
    a, b = resolve_team(db, source, data["team1"]), resolve_team(db, source, data["team2"])
    if a.id == b.id:
        raise UnresolvedTeam("Both participants resolved to the same team")
    link = db.scalar(select(MatchSource).where(MatchSource.source == source, MatchSource.external_id == external))
    match = db.get(Match, link.match_id) if link else None
    if match is None and source == "vlr":
        match = db.scalar(select(Match).where(Match.vlr_id == int(external)))
    at = data.get("scheduled_at")
    if match is None and at and normalize(data.get("event_name")):
        nearby = db.scalars(select(Match).where(
            or_((Match.team1_id == a.id) & (Match.team2_id == b.id),
                (Match.team1_id == b.id) & (Match.team2_id == a.id)),
            Match.scheduled_at.between(at - timedelta(hours=2), at + timedelta(hours=2)))).all()
        candidates = []
        for m in nearby:
            if normalize(m.event_name) != normalize(data.get("event_name")):
                continue
            links = db.scalars(select(MatchSource).where(MatchSource.match_id == m.id)).all()
            if any(s.source == source for s in links) or (source == "vlr" and m.vlr_id is not None):
                continue
            if m.stage and data.get("stage") and normalize(m.stage) != normalize(data["stage"]):
                continue
            formats = {s.details.get("best_of") for s in links} - {None}
            if data.get("best_of") and formats and data["best_of"] not in formats:
                continue
            # Without matching stage, tighten schedule tolerance to 30 minutes.
            if not (m.stage and data.get("stage")) and abs((utc(m.scheduled_at) - utc(at)).total_seconds()) > 1800:
                continue
            candidates.append(m)
        if len(candidates) == 1:
            match = candidates[0]
        elif len(candidates) > 1:
            issue(db, source, external, "AMBIGUOUS_MATCH", {"candidates": [m.id for m in candidates]})
    created = match is None
    if created:
        match = Match(team1_id=a.id, team2_id=b.id, vlr_id=int(external) if source == "vlr" else None)
        db.add(match)
        db.flush()
    incoming = {key: data.get(key) for key in ("scheduled_at", "event_name", "stage", "status", "team1_score", "team2_score")}
    if not created and (a.id, b.id) == (match.team2_id, match.team1_id):
        incoming["team1_score"], incoming["team2_score"] = incoming["team2_score"], incoming["team1_score"]
    elif not created and (a.id, b.id) != (match.team1_id, match.team2_id):
        issue(db, source, external, "SOURCE_CONFLICT", {"field": "teams", "canonical": [match.team1_id, match.team2_id], "incoming": [a.id, b.id], "evidence": evidence}, match.id)
        return match
    other_links = db.scalars(select(MatchSource).where(MatchSource.match_id == match.id, MatchSource.source != source)).all()
    # VLR remains authority for shared records; a THESPIKE-only record owns its values.
    accepts = source == "vlr" or (match.vlr_id is None and not other_links)
    for field, value in incoming.items():
        old = getattr(match, field)
        different = old != value
        if old is not None and value is not None:
            if field == "scheduled_at":
                different = abs((utc(old) - utc(value)).total_seconds()) > 300
            elif field in {"event_name", "stage"}:
                different = normalize(old) != normalize(value)
            if different and other_links:
                issue(db, source, external, "SOURCE_CONFLICT", {"field": field, "canonical": str(old), "incoming": str(value), "evidence": evidence}, match.id)
        if created or accepts:
            # Never let an upcoming listing erase a completed result.
            if match.status == "completed" and data["status"] == "scheduled":
                continue
            setattr(match, field, value)
    if source == "vlr":
        match.vlr_id = int(external)
    now = datetime.now(timezone.utc)
    if not link:
        link = MatchSource(match_id=match.id, source=source, external_id=external,
                           first_seen_at=now, source_url="")
        db.add(link)
    link.last_seen_at = now
    link.last_synced_at = now
    link.source_url = data.get("source_url") or (evidence or {}).get("source_url") or f"https://www.{source}.gg/{external}"
    link.details = {**{k: v.isoformat() if isinstance(v, datetime) else v for k, v in incoming.items()},
                    "best_of": data.get("best_of"), "team1": data["team1"], "team2": data["team2"], "evidence": evidence}
    # Conflicting secondary schedules/results remain in provenance, not training.
    accepted = all(getattr(match, k) == v or (k == "scheduled_at" and v and getattr(match, k) and utc(getattr(match, k)) == utc(v)) for k, v in incoming.items())
    if evidence and accepted:
        payload = {**link.details, "team1_id": match.team1_id, "team2_id": match.team2_id,
                   "source": source, "vlr_match_id": match.vlr_id, "parser_version": "source-match-v1",
                   "parse_sha256": data.get("parse_sha256"), "listing_evidence": data.get("listing_evidence"),
                   "retrieval_sha256": evidence.get("retrieval_sha256")}
        db.add(MatchObservation(match_id=match.id, received_at=datetime.fromisoformat(evidence["received_at"]),
            ingested_at=now, raw_sha256=evidence["raw_sha256"], source_url=link.source_url,
            evidence_key=evidence_key, payload=payload))
    db.flush()
    return match
