import time
import re
import httpx
from app.ingestion.vlr import fetch_page, VLR_BASE_URL, REQUEST_DELAY, PAGE_DELAY
from app.ingestion.vlr_upcoming import parse_upcoming_match, MatchNotForecastableError


class VlrSource:
    name = "vlr"

    def __init__(self):
        self.metrics = {"attempted": 0, "fetched": 0, "parsed": 0, "not_forecastable": 0, "parse_failures": 0}

    def discover_upcoming_matches(self, pages=1):
        if not 1 <= pages <= 10:
            raise ValueError("pages must be 1..10")
        self.metrics = dict.fromkeys(self.metrics, 0)
        def received(response):
            if response.is_success and re.match(r"^/\d+", response.url.path):
                self.metrics["fetched"] += 1
        with httpx.Client(headers={"User-Agent": "ClutchQuant/1.0"}, timeout=15, follow_redirects=True,
                          event_hooks={"response": [received]}) as client:
            for page in range(1, pages + 1):
                soup = fetch_page(client, f"{VLR_BASE_URL}/matches/?page={page}", retries=2)
                cards = soup.select("a.wf-module-item.match-item")
                if not cards:
                    raise ValueError("VLR listing has no match cards; cannot establish coverage")
                for card in cards:
                    self.metrics["attempted"] += 1
                    try:
                        data = parse_upcoming_match(client, card)
                        self.metrics["parsed"] += 1
                        yield data
                    except MatchNotForecastableError:
                        self.metrics["not_forecastable"] += 1
                    except Exception as error:
                        self.metrics["parse_failures"] += 1
                        from app.ingestion.vlr import extract_id
                        yield {"source": self.name, "external_id": str(extract_id(card.get("href")) or "unknown"),
                               "collection_error": type(error).__name__}
                    finally:
                        time.sleep(REQUEST_DELAY)
                time.sleep(PAGE_DELAY)
