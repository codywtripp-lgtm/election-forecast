"""Paths and cycle constants shared by every stage."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
MANUAL = DATA / "manual"
DB = DATA / "db"
RUNS = ROOT / "runs"
SITE_DATA = ROOT / "site" / "static" / "data"

CYCLE = 2026
ELECTION_DATE = dt.date(2026, 11, 3)

USER_AGENT = "election-forecast/0.1 (+https://github.com/codywtripp-lgtm/election-forecast)"
