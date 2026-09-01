import argparse
import time

from app.database import SessionLocal
from app.ingestion.vlr_stats import (
    fetch_page,
    parse_maps,
    save_maps,
)
from app.models import Match, MatchMap


VLR_BASE_URL = "https://www.vlr.gg"
REQUEST_DELAY = 0.75
DEFAULT_LIMIT = 25


def get_matches_missing_stats(db, limit):
    query = (
        db.query(Match)
        .outerjoin(
            MatchMap,
            MatchMap.match_id == Match.id,
        )
        .filter(
            Match.status == "completed",
            Match.vlr_id.is_not(None),
            MatchMap.id.is_(None),
        )
        .order_by(
            Match.scheduled_at.desc().nullslast(),
            Match.id.desc(),
        )
    )

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def backfill_stats(limit=DEFAULT_LIMIT):
    db = SessionLocal()

    total_saved = 0
    total_failed = 0

    try:
        matches = get_matches_missing_stats(
            db,
            limit,
        )

        total_matches = len(matches)

        print(
            f"Found {total_matches} completed "
            "matches missing detailed stats."
        )

        for index, match in enumerate(
            matches,
            start=1,
        ):
            vlr_id = match.vlr_id
            url = f"{VLR_BASE_URL}/{vlr_id}"

            try:
                soup = fetch_page(url)
                maps = parse_maps(soup)

                if not maps:
                    raise RuntimeError(
                        "No completed maps were parsed."
                    )

                save_maps(
                    db,
                    match,
                    maps,
                )

                db.commit()

                player_rows = sum(
                    len(map_data["players"])
                    for map_data in maps
                )

                total_saved += 1

                print(
                    f"[{index}/{total_matches}] "
                    f"{vlr_id} SAVED: "
                    f"{len(maps)} maps, "
                    f"{player_rows} player rows"
                )

            except KeyboardInterrupt:
                db.rollback()

                print()
                print("Stats backfill stopped.")
                print(
                    "Saved matches will be skipped "
                    "when the command is restarted."
                )
                break

            except Exception as error:
                db.rollback()

                total_failed += 1

                print(
                    f"[{index}/{total_matches}] "
                    f"{vlr_id} FAILED: {error}"
                )

            if index < total_matches:
                time.sleep(REQUEST_DELAY)

    finally:
        db.close()

    print()
    print("=" * 60)
    print("STATS BACKFILL SUMMARY")
    print("=" * 60)
    print("Matches saved:", total_saved)
    print("Failed:", total_failed)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Backfill VLR map and player statistics "
            "for completed matches."
        )
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Maximum number of matches to process "
            f"(default: {DEFAULT_LIMIT})."
        ),
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="Process every match currently missing stats.",
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    return args


def main():
    args = parse_arguments()

    limit = None if args.all else args.limit

    backfill_stats(limit=limit)


if __name__ == "__main__":
    main()