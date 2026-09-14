import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import Match, MatchObservation, Team
from app.ingestion.provenance import captured_soup, record_parse
from app.artifacts import canonical_json, digest


VLR_BASE_URL = "https://www.vlr.gg"

REQUEST_DELAY = 0.75
PAGE_DELAY = 1.5

CHECKPOINT_FILE = Path(__file__).parent / "vlr_backfill_checkpoint.txt"


def fetch_page(client, url, retries=5):
    for attempt in range(1, retries + 1):
        try:
            response = client.get(url)
            soup = captured_soup(response)

            if response.status_code == 429:
                wait = 15 * attempt
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()

            return soup

        except httpx.HTTPError as error:
            if attempt == retries:
                raise

            wait = 5 * attempt

            print(
                f"Request failed: {error}. "
                f"Retrying in {wait}s..."
            )

            time.sleep(wait)

    raise RuntimeError("Failed to fetch page.")


def extract_id(href):
    if not href:
        return None

    match = re.search(r"/(\d+)/", href)

    if match:
        return int(match.group(1))

    return None


def safe_int(text):
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None


def parse_completed_match(client, match_card):
    href = match_card.get("href")

    vlr_id = extract_id(href)

    if vlr_id is None:
        raise RuntimeError("Could not find VLR match ID.")

    match_url = f"{VLR_BASE_URL}{href}"

    event_container = match_card.select_one(
        ".match-item-event"
    )

    event_parts = (
        list(event_container.stripped_strings)
        if event_container
        else []
    )

    stage = (
        event_parts[0]
        if len(event_parts) >= 1
        else None
    )

    event_name = (
        event_parts[1]
        if len(event_parts) >= 2
        else None
    )

    match_soup = fetch_page(
        client,
        match_url,
    )
    evidence = match_soup.__dict__.get("cq_evidence")
    try:
        data = parse_match_soup(match_soup, vlr_id, event_name, stage)
    except Exception as error:
        record_parse(evidence, "failed", entity={"vlr_match_id": vlr_id}, error=error)
        raise
    data["parse_sha256"] = record_parse(evidence, "parsed", entity={"vlr_match_id": vlr_id})
    # Event/stage came from the listing, so preserve that separate source too.
    parent = match_card
    while parent is not None:
        listing = parent.__dict__.get("cq_evidence")
        if listing:
            data["listing_evidence"] = listing
            break
        parent = parent.parent
    return data


def parse_match_soup(match_soup, vlr_id, event_name, stage):

    team1_link = match_soup.select_one(
        "a.match-header-link.mod-1"
    )

    team2_link = match_soup.select_one(
        "a.match-header-link.mod-2"
    )

    if team1_link is None or team2_link is None:
        raise RuntimeError(
            f"Could not find both teams for {vlr_id}"
        )

    team1 = {
        "vlr_id": extract_id(
            team1_link.get("href")
        ),
        "name": team1_link.get_text(
            " ",
            strip=True,
        ),
    }

    team2 = {
        "vlr_id": extract_id(
            team2_link.get("href")
        ),
        "name": team2_link.get_text(
            " ",
            strip=True,
        ),
    }

    score_elements = match_soup.select(
        ".match-header-vs-score-winner, "
        ".match-header-vs-score-loser"
    )

    team1_score = None
    team2_score = None

    if len(score_elements) >= 2:
        team1_score = safe_int(
            score_elements[0].get_text(strip=True)
        )

        team2_score = safe_int(
            score_elements[1].get_text(strip=True)
        )

    timestamp_element = match_soup.select_one(
        ".moment-tz-convert[data-utc-ts]"
    )

    scheduled_at = None

    if timestamp_element:
        timestamp_text = timestamp_element.get(
            "data-utc-ts"
        )

        try:
            scheduled_at = datetime.strptime(
                timestamp_text,
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=timezone.utc)

        except ValueError:
            scheduled_at = None

    return {
        "vlr_id": vlr_id,
        "team1": team1,
        "team2": team2,
        "team1_score": team1_score,
        "team2_score": team2_score,
        "event_name": event_name,
        "stage": stage,
        "status": "completed",
        "scheduled_at": scheduled_at,
        "evidence": match_soup.__dict__.get("cq_evidence"),
    }


def get_or_create_team(db, team_data):
    if team_data["vlr_id"] is None:
        raise RuntimeError(
            f"Missing VLR team ID for "
            f"{team_data['name']}"
        )

    team = (
        db.query(Team)
        .filter(
            Team.vlr_id == team_data["vlr_id"]
        )
        .first()
    )

    if team is None:
        team = Team(
            vlr_id=team_data["vlr_id"],
            name=team_data["name"],
        )

        db.add(team)
        db.flush()

    else:
        team.name = team_data["name"]

    return team


def save_match(db, data):
    evidence = data.get("evidence")
    evidence_key = None
    if evidence:
        evidence_key = digest(canonical_json({
            "retrieval": evidence, "vlr_match_id": data["vlr_id"], "parser": "vlr-match-v2",
            "status": data["status"],
        }))
        existing = db.query(MatchObservation).filter_by(evidence_key=evidence_key).first()
        if existing is not None:
            return db.get(Match, existing.match_id)
    team1 = get_or_create_team(
        db,
        data["team1"],
    )

    team2 = get_or_create_team(
        db,
        data["team2"],
    )

    match = (
        db.query(Match)
        .filter(
            Match.vlr_id == data["vlr_id"]
        )
        .first()
    )

    if match is None:
        match = Match(
            vlr_id=data["vlr_id"],
            team1_id=team1.id,
            team2_id=team2.id,
        )

        db.add(match)

    match.team1_id = team1.id
    match.team2_id = team2.id

    match.team1_score = data["team1_score"]
    match.team2_score = data["team2_score"]

    match.event_name = data["event_name"]
    match.stage = data["stage"]
    match.status = data["status"]
    match.scheduled_at = data["scheduled_at"]

    evidence = data.get("evidence")
    if evidence is not None:
        db.flush()
        received_at = datetime.fromisoformat(evidence["received_at"])
        db.add(MatchObservation(
            match_id=match.id,
            received_at=received_at,
            ingested_at=datetime.now(timezone.utc),
            raw_sha256=evidence["raw_sha256"],
            source_url=evidence["source_url"],
            evidence_key=evidence_key,
            payload={
                "vlr_match_id": data["vlr_id"],
                "team1": data["team1"], "team2": data["team2"],
                "parser_version": "vlr-match-v2", "parse_sha256": data.get("parse_sha256"),
                "retrieval_sha256": evidence.get("retrieval_sha256"),
                "listing_evidence": data.get("listing_evidence"),
                "team1_id": team1.id, "team2_id": team2.id,
                "team1_score": match.team1_score, "team2_score": match.team2_score,
                "status": match.status,
                "scheduled_at": match.scheduled_at.isoformat() if match.scheduled_at else None,
                "event_name": match.event_name, "stage": match.stage,
            },
        ))
    return match


def already_complete(db, vlr_id):
    match = (
        db.query(Match)
        .filter(
            Match.vlr_id == vlr_id
        )
        .first()
    )

    if match is None:
        return False

    return (
        match.status == "completed"
        and match.team1_score is not None
        and match.team2_score is not None
    )


def load_checkpoint():
    if not CHECKPOINT_FILE.exists():
        return 1

    try:
        return int(
            CHECKPOINT_FILE
            .read_text()
            .strip()
        )

    except ValueError:
        return 1


def save_checkpoint(page):
    CHECKPOINT_FILE.write_text(
        str(page)
    )


def backfill_all_results():
    start_page = load_checkpoint()

    print(
        f"Starting historical backfill "
        f"at page {start_page}."
    )

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    total_saved = 0
    total_skipped = 0
    total_failed = 0

    db = SessionLocal()

    try:
        with httpx.Client(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:

            page = start_page

            while True:
                print()
                print("=" * 60)
                print(f"PAGE {page}")
                print("=" * 60)

                url = (
                    f"{VLR_BASE_URL}"
                    f"/matches/results/?page={page}"
                )

                soup = fetch_page(
                    client,
                    url,
                )

                match_cards = soup.select(
                    "a.wf-module-item.match-item"
                )

                if not match_cards:
                    print(
                        "No more matches found."
                    )
                    break

                page_saved = 0
                page_skipped = 0
                page_failed = 0

                for index, match_card in enumerate(
                    match_cards,
                    start=1,
                ):
                    href = match_card.get("href")

                    vlr_id = extract_id(href)

                    if vlr_id is None:
                        page_failed += 1
                        total_failed += 1
                        continue

                    try:
                        if already_complete(
                            db,
                            vlr_id,
                        ):
                            page_skipped += 1
                            total_skipped += 1

                            print(
                                f"[{index}/"
                                f"{len(match_cards)}] "
                                f"{vlr_id} SKIPPED"
                            )

                            continue

                        data = parse_completed_match(
                            client,
                            match_card,
                        )

                        save_match(
                            db,
                            data,
                        )

                        db.commit()

                        page_saved += 1
                        total_saved += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{data['team1']['name']} "
                            f"{data['team1_score']} - "
                            f"{data['team2_score']} "
                            f"{data['team2']['name']}"
                        )

                        time.sleep(
                            REQUEST_DELAY
                        )

                    except Exception as error:
                        db.rollback()

                        page_failed += 1
                        total_failed += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{vlr_id} FAILED: "
                            f"{error}"
                        )

                print()
                print(
                    f"Page {page} complete."
                )
                print(
                    f"Saved: {page_saved}"
                )
                print(
                    f"Skipped: {page_skipped}"
                )
                print(
                    f"Failed: {page_failed}"
                )

                page += 1

                save_checkpoint(page)

                time.sleep(PAGE_DELAY)

    except KeyboardInterrupt:
        print()
        print("Backfill stopped.")
        print(
            "Your checkpoint was saved."
        )

    finally:
        db.close()

    print()
    print("=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)

    print(
        "New matches saved:",
        total_saved,
    )

    print(
        "Already existing:",
        total_skipped,
    )

    print(
        "Failed:",
        total_failed,
    )


if __name__ == "__main__":
    backfill_all_results()
