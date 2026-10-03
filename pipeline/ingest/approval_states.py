"""Statewide Trump job-approval polls from Wikipedia's "Opinion polling on the second Trump presidency"
(MediaWiki API, CC BY-SA). Each state has its own section with a table of individual polls.

Output: data/db/state_approval_polls.parquet (state, pollster, end_date, n, population, approve, disapprove, net)
"""
from __future__ import annotations

import io
import json
import re

import pandas as pd

from pipeline.config import DB
from pipeline.ingest.snapshot import SESSION, latest_snapshot, read_snapshot, snapshot_path, write_snapshot
from pipeline.states import NAME_TO_ABBR

API = "https://en.wikipedia.org/w/api.php"
PAGE = "Opinion_polling_on_the_second_Trump_presidency"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def fetch() -> None:
    secs = SESSION.get(API, params={"action": "parse", "page": PAGE, "prop": "sections", "format": "json",
                                    "formatversion": 2}, timeout=60).json()["parse"]["sections"]
    start = next(i for i, s in enumerate(secs) if s["line"].startswith("Statewide job approval"))
    out = {}
    for s in secs[start + 1:]:
        if int(s["level"]) <= 2:
            break
        if s["line"] in NAME_TO_ABBR:
            html = SESSION.get(API, params={"action": "parse", "page": PAGE, "prop": "text", "section": s["index"],
                                            "format": "json", "formatversion": 2}, timeout=60).json()["parse"]["text"]
            out[s["line"]] = html
    write_snapshot(snapshot_path("wikipedia", "trump_state_approval", "json"), json.dumps(out).encode())


def _pct(x) -> float:
    m = re.search(r"([\d.]+)", str(x))
    return float(m.group(1)) if m else float("nan")


def _end_date(text: str, default_year: int = 2026):
    """'April 28–May 3, 2025' / 'September 24-28' → end date."""
    t = re.sub(r"\[.*?\]", "", str(text)).replace("–", "-").replace("—", "-")
    years = re.findall(r"(20\d\d)", t)
    year = int(years[-1]) if years else default_year
    parts = re.findall(rf"({MONTHS})\s*(\d{{1,2}})?(?:\s*-\s*(\d{{1,2}}))?", t)
    if not parts:
        return None
    month, d1, d2 = parts[-1]
    day = d2 or d1 or "15"
    return pd.to_datetime(f"{month} {day} {year}", errors="coerce")


def parse() -> pd.DataFrame:
    data = json.loads(read_snapshot(latest_snapshot("wikipedia", "trump_state_approval")))
    rows = []
    for state, html in data.items():
        for t in pd.read_html(io.StringIO(html)):
            cols = [re.sub(r"\[.*?\]", "", str(c[-1] if isinstance(c, tuple) else c)).strip() for c in t.columns]
            t.columns = cols
            if not {"Approve", "Disapprove"} <= set(cols):
                continue
            src = next((c for c in cols if "source" in c.lower() or "poll" in c.lower()), cols[0])
            date_c = next((c for c in cols if "date" in c.lower()), None)
            size_c = next((c for c in cols if "sample" in c.lower()), None)
            for _, r in t.iterrows():
                end = _end_date(r[date_c]) if date_c else None
                ap, dis = _pct(r["Approve"]), _pct(r["Disapprove"])
                if end is None or pd.isna(end) or pd.isna(ap) or pd.isna(dis):
                    continue
                size = str(r[size_c]) if size_c else ""
                n = pd.to_numeric(re.sub(r"[^\d]", "", size.split()[0]) if size.split() else "", errors="coerce")
                pop = "lv" if "LV" in size or "Likely" in size else ("rv" if "RV" in size or "Registered" in size else "a")
                rows.append(dict(state=NAME_TO_ABBR[state], pollster=re.sub(r"\[.*?\]", "", str(r[src])).strip(),
                                 end_date=end.date(), n=n, population=pop, approve=ap, disapprove=dis,
                                 net=ap - dis))
    return pd.DataFrame(rows)


def main(refresh: bool = True) -> None:
    if refresh:
        fetch()
    df = parse()
    df.to_parquet(DB / "state_approval_polls.parquet", index=False)
    print(len(df), "state approval polls;", df.groupby("state").size().to_dict())


if __name__ == "__main__":
    main(refresh=False)
