import time

import httpx

from app.database import SessionLocal
from app.ingestion.vlr import (
    PAGE_DELAY,
    REQUEST_DELAY,
    VLR_BASE_URL,
    extract_id,
    fetch_page,
    parse_completed_match,
    save_match,
)
from app.models import Match


class MatchNotForecastableError(Exception):
    pass


def parse_upcoming_match(client, match_card):
    # Upcoming and completed VLR pages use the same
    # match-header structure.
    try:
        data = parse_completed_match(
            client,
            match_card,
        )

    except RuntimeError as error:
        if "Could not find both teams" in str(error):
            raise MatchNotForecastableError(
                "Both teams are not known yet."
            ) from error

        raise

    if (
        data["team1"]["vlr_id"] is None
        or data["team2"]["vlr_id"] is None
    ):
        raise MatchNotForecastableError(
            "Both teams are not known yet."
        )

    if data["scheduled_at"] is None:
        raise MatchNotForecastableError(
            "The start time is not known yet."
        )

    data["team1_score"] = None
    data["team2_score"] = None
    data["status"] = "scheduled"

    return data


def sync_upcoming_matches():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    total_synced = 0
    total_skipped = 0
    total_failed = 0

    db = SessionLocal()

    try:
        with httpx.Client(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:

            page = 1

            while True:
                print()
                print("=" * 60)
                print(f"UPCOMING PAGE {page}")
                print("=" * 60)

                url = (
                    f"{VLR_BASE_URL}"
                    f"/matches/?page={page}"
                )

                soup = fetch_page(
                    client,
                    url,
                )

                match_cards = soup.select(
                    "a.wf-module-item.match-item"
                )

                if not match_cards:
                    print("No more upcoming matches found.")
                    break

                for index, match_card in enumerate(
                    match_cards,
                    start=1,
                ):
                    vlr_id = extract_id(
                        match_card.get("href")
                    )

                    if vlr_id is None:
                        total_failed += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            "UNKNOWN FAILED: "
                            "missing VLR match ID"
                        )
                        continue

                    existing_match = (
                        db.query(Match)
                        .filter(
                            Match.vlr_id == vlr_id
                        )
                        .first()
                    )

                    if (
                        existing_match is not None
                        and existing_match.status == "completed"
                    ):
                        total_skipped += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{vlr_id} SKIPPED: "
                            "already completed"
                        )
                        continue

                    try:
                        data = parse_upcoming_match(
                            client,
                            match_card,
                        )

                        save_match(
                            db,
                            data,
                        )

                        db.commit()

                        total_synced += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{vlr_id} SYNCED: "
                            f"{data['team1']['name']} vs. "
                            f"{data['team2']['name']}"
                        )

                    except MatchNotForecastableError as error:
                        db.rollback()

                        total_skipped += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{vlr_id} SKIPPED: {error}"
                        )

                    except Exception as error:
                        db.rollback()

                        total_failed += 1

                        print(
                            f"[{index}/"
                            f"{len(match_cards)}] "
                            f"{vlr_id} FAILED: {error}"
                        )

                    time.sleep(REQUEST_DELAY)

                page += 1

                time.sleep(PAGE_DELAY)

    except KeyboardInterrupt:
        db.rollback()

        print()
        print("Upcoming-match sync stopped.")

    finally:
        db.close()

    print()
    print("=" * 60)
    print("UPCOMING MATCH SYNC SUMMARY")
    print("=" * 60)
    print("Matches synced:", total_synced)
    print("Not forecastable:", total_skipped)
    print("Failed:", total_failed)


def main():
    sync_upcoming_matches()


if __name__ == "__main__":
    main()