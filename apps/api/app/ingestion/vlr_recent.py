"""Bounded reconciliation for recent results; never resumes an old page cursor."""

import argparse
import json
import logging
import time

import httpx

from app.database import SessionLocal
from app.ingestion.vlr import VLR_BASE_URL, REQUEST_DELAY, fetch_page, parse_completed_match, save_match

logger = logging.getLogger(__name__)


def sync_recent_results(pages=2):
    if not 1 <= pages <= 10:
        raise ValueError("pages must be between 1 and 10")
    saved, failed = 0, 0
    with SessionLocal() as db, httpx.Client(headers={"User-Agent":"Mozilla/5.0"},timeout=30,follow_redirects=True) as client:
        for page in range(1,pages+1):
            soup = fetch_page(client,f"{VLR_BASE_URL}/matches/results/?page={page}")
            cards = soup.select("a.wf-module-item.match-item")
            if not cards:
                raise RuntimeError("No result cards found; verify source markup before continuing")
            for card in cards:
                try:
                    save_match(db,parse_completed_match(client,card))
                    db.commit()
                    saved += 1
                except Exception:
                    db.rollback()
                    failed += 1
                    logger.exception("Recent result failed",extra={"match_href":card.get("href")})
                time.sleep(REQUEST_DELAY)
    return {"saved":saved,"failed":failed,"pages":pages}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages",type=int,default=2)
    args = parser.parse_args()
    result = sync_recent_results(args.pages)
    print(json.dumps(result))
    raise SystemExit(1 if result["failed"] else 0)
