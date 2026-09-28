from typing import Protocol, Iterable


class DataSource(Protocol):
    name: str

    def discover_upcoming_matches(self, pages: int = 1) -> Iterable[dict]: ...
