"""VoteHub Polling API (CC BY 4.0, https://votehub.com/polls/api/). Attribution required on the site."""
from __future__ import annotations

import gzip
import json

from pipeline.ingest.snapshot import fetch, latest_snapshot, read_snapshot, snapshot_path, write_snapshot

URL = "https://api.votehub.com/polls"


def fetch_all() -> int:
    content = fetch(URL)
    polls = json.loads(content)
    write_snapshot(snapshot_path("votehub", "polls", "json"), content)
    return len(polls)


def load() -> list[dict]:
    return json.loads(read_snapshot(latest_snapshot("votehub", "polls")))


if __name__ == "__main__":
    print(fetch_all(), "polls")
