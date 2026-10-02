"""Wikipedia pages via the MediaWiki parse API (CC BY-SA 4.0 — see docs/DATA_GAPS.md).

Used for the 2026 race list and nominees. Never scrapes article HTML directly.
"""
from __future__ import annotations

import json

from pipeline.ingest.snapshot import SESSION, latest_snapshot, read_snapshot, snapshot_path, write_snapshot

API = "https://en.wikipedia.org/w/api.php"

PAGES = {
    "senate_2026": "2026_United_States_Senate_elections",
    "governor_2026": "2026_United_States_gubernatorial_elections",
}


def fetch_page(key: str) -> str:
    r = SESSION.get(API, params={"action": "parse", "page": PAGES[key], "prop": "text|revid",
                                 "format": "json", "formatversion": 2}, timeout=60)
    r.raise_for_status()
    parsed = r.json()["parse"]
    payload = json.dumps({"page": PAGES[key], "revid": parsed["revid"], "html": parsed["text"]})
    write_snapshot(snapshot_path("wikipedia", key, "json"), payload.encode())
    return parsed["text"]


def load_page(key: str) -> dict:
    return json.loads(read_snapshot(latest_snapshot("wikipedia", key)))


if __name__ == "__main__":
    for k in PAGES:
        fetch_page(k)
        print("saved", k)
