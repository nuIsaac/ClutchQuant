import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import Match, Team


VLR_BASE_URL = "https://www.vlr.gg"

REQUEST_DELAY = 0.75
PAGE_DELAY = 1.5

CHECKPOINT_FILE = Path(__file__).parent / "vlr_backfill_checkpoint.txt"


def fetch_page(client, url, retries=5):
    for attempt in range(1, retries + 1):
        try:
            response = client.get(url)

            if response.status_code == 429:
                wait = 15 * attempt
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

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