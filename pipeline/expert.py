"""Expert race ratings (Cook Political Report, Inside Elections, Sabato's Crystal Ball) — BENCHMARK ONLY.

Never an input to the model (hard rule). Stored so race pages can show them for comparison and so the
post-election scorecard can compare our forecasts with theirs. Ratings are facts tabulated on the
Wikipedia 2026 Senate / governor pages (with citations there); we store the label and the date.

Output: data/db/expert_ratings.parquet (latest), data/benchmarks/expert_ratings.csv (dated history, committed)
"""
from __future__ import annotations

import datetime as dt
import io
import os
import re

import pandas as pd

from pipeline.config import CYCLE, DATA, DB
from pipeline.ingest.wikipedia import load_page
from pipeline.states import to_abbr

RATERS = {"Cook": "Cook Political Report", "IE": "Inside Elections", "Sabato": "Sabato's Crystal Ball"}
HISTORY = DATA / "benchmarks" / "expert_ratings.csv"


def _clean(s) -> str:
    return re.sub(r"\[.*?\]", "", str(s)).strip()


def parse(page_key: str, office: str) -> pd.DataFrame:
    rows = []
    for t in pd.read_html(io.StringIO(load_page(page_key)["html"])):
        if not (isinstance(t.columns, pd.MultiIndex) and any("Ratings" in str(c[0]) for c in t.columns)):
            continue
        cols = {c: _clean(c[1]) for c in t.columns}
        key_col = next(c for c in t.columns if cols[c] in ("State", "District"))
        for _, r in t.iterrows():
            label = _clean(r[key_col])
            if office == "house":
                from pipeline.house import district_code
                dc = district_code(label)
                if dc is None:
                    continue
                rid = f"{CYCLE}-house-{dc[0]}-{dc[1]:02d}"
            else:
                special = bool(re.search(r"special|\(Class", label, re.I))
                try:
                    st = to_abbr(re.sub(r"\s*\(.*\)", "", label).strip())
                except KeyError:
                    continue
                rid = f"{CYCLE}-{office}-{st}" + ("-S" if special else "")
            for c in t.columns:
                name = cols[c]
                m = re.match(r"^(Cook|IE|Sabato)\s+(.*)$", name)
                if m and pd.notna(r[c]):
                    rows.append(dict(race_id=rid, rater=RATERS[m.group(1)], rating=_clean(r[c]),
                                     rating_date=m.group(2).strip()))
        break
    return pd.DataFrame(rows)


def main() -> None:
    parts = [parse("senate_2026", "sen"), parse("governor_2026", "gov")]
    try:
        parts.append(parse("house_ratings_2026", "house"))   # competitive districts only
    except FileNotFoundError:
        pass
    df = pd.concat(parts, ignore_index=True)
    DB.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DB / "expert_ratings.parquet", index=False)
    if os.environ.get("GITHUB_ACTIONS") != "true":   # tracked history is written by the scheduled run only
        print(df.groupby("rater").size().to_dict())
        return
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    stamped = df.assign(fetched=dt.date.today().isoformat())
    hist = pd.concat([pd.read_csv(HISTORY), stamped]) if HISTORY.exists() else stamped
    hist.drop_duplicates(["race_id", "rater", "rating", "rating_date"]).to_csv(HISTORY, index=False)
    print(df.groupby("rater").size().to_dict())


if __name__ == "__main__":
    main()
