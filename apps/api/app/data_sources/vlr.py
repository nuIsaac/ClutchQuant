import time
import httpx
from app.ingestion.vlr import fetch_page, VLR_BASE_URL, REQUEST_DELAY, PAGE_DELAY
from app.ingestion.vlr_upcoming import parse_upcoming_match, MatchNotForecastableError


class VlrSource:
    name = "vlr"

    def discover_upcoming_matches(self, pages=1):
        if not 1 <= pages <= 10:
            raise ValueError("pages must be 1..10")
        with httpx.Client(headers={"User-Agent": "ClutchQuant/1.0"}, timeout=15, follow_redirects=True) as client:
            for page in range(1, pages + 1):
                soup = fetch_page(client, f"{VLR_BASE_URL}/matches/?page={page}", retries=2)
                cards = soup.select("a.wf-module-item.match-item")
                if not cards:
                    break
                for card in cards:
                    try:
                        yield parse_upcoming_match(client, card)
                    except MatchNotForecastableError:
                        pass
                    except Exception as error:
                        from app.ingestion.vlr import extract_id
                        yield {"source": self.name, "external_id": str(extract_id(card.get("href")) or "unknown"),
                               "collection_error": type(error).__name__}
                    finally:
                        time.sleep(REQUEST_DELAY)
                time.sleep(PAGE_DELAY)
