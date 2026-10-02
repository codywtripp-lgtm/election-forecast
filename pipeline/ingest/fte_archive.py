"""538 open data archive (CC BY 4.0). 538 shut down in March 2025; these files are frozen.

Poll histories (2018–2024) come from the Internet Archive's capture of projects.fivethirtyeight.com
(timestamp pinned below); pollster-rating files from github.com/fivethirtyeight/data.
"""
from __future__ import annotations

import time

from pipeline.config import RAW
from pipeline.ingest.snapshot import fetch, write_snapshot

WAYBACK_TS = "20250118200335"
POLL_FILES = [
    "senate_polls_historical", "governor_polls_historical", "house_polls_historical",
    "generic_ballot_polls_historical", "president_polls_historical", "president_approval_polls_historical",
]
GITHUB = {
    "raw_polls": "https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv",
    "pollster_ratings_combined": "https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/pollster-ratings-combined.csv",
}
DIR = RAW / "fte_archive"


def download() -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    for f in POLL_FILES:
        url = f"https://web.archive.org/web/{WAYBACK_TS}id_/https://projects.fivethirtyeight.com/polls-page/data/{f}.csv"
        write_snapshot(DIR / f"{f}.csv.gz", fetch(url))
        time.sleep(3)  # be polite to the Internet Archive
    for name, url in GITHUB.items():
        write_snapshot(DIR / f"{name}.csv.gz", fetch(url))


if __name__ == "__main__":
    download()
