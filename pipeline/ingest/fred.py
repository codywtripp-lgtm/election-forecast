"""Economic indicators from FRED (Federal Reserve Bank of St. Louis) graph CSVs — no API key.

UMCSENT  University of Michigan consumer sentiment (© University of Michigan; cited)
CPIAUCSL CPI, all urban consumers (BLS) → year-over-year inflation
UNRATE   unemployment rate (BLS)
GASREGW  regular gasoline, US average $/gal, weekly (EIA)
DSPIC96  real disposable personal income (BEA) → year-over-year growth

Output: data/raw/fred/<id>.csv (snapshot) and the economy block of trackers.json
"""
from __future__ import annotations

import io

import pandas as pd

from pipeline.config import RAW
from pipeline.ingest.snapshot import fetch

DIR = RAW / "fred"
SERIES = {
    "UMCSENT": dict(label="Consumer sentiment (U. Michigan)", unit="index", transform="level",
                    source="University of Michigan Surveys of Consumers, via FRED"),
    "CPIAUCSL": dict(label="Inflation (CPI, year over year)", unit="%", transform="yoy",
                     source="U.S. Bureau of Labor Statistics, via FRED"),
    "UNRATE": dict(label="Unemployment rate", unit="%", transform="level",
                   source="U.S. Bureau of Labor Statistics, via FRED"),
    "GASREGW": dict(label="Gas price (regular, US average)", unit="$/gal", transform="level",
                    source="U.S. Energy Information Administration, via FRED"),
    "DSPIC96": dict(label="Real disposable income (year over year)", unit="%", transform="yoy",
                    source="U.S. Bureau of Economic Analysis, via FRED"),
}
START = "2023-01-01"


def download() -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    for sid in SERIES:
        try:
            (DIR / f"{sid}.csv").write_bytes(fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"))
        except Exception as exc:     # keep the previous snapshot
            print(f"FRED {sid} failed: {exc}")


def load(sid: str) -> pd.Series:
    df = pd.read_csv(DIR / f"{sid}.csv")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    s = df.dropna().set_index("date")["value"]
    if SERIES[sid]["transform"] == "yoy":
        s = (s / s.shift(12) - 1) * 100
    return s.dropna()


def economy_block() -> list[dict]:
    out = []
    for sid, meta in SERIES.items():
        if not (DIR / f"{sid}.csv").exists():
            continue
        s = load(sid)
        s = s[s.index >= START]
        out.append(dict(id=sid, **meta, points=[dict(date=d.date().isoformat(), value=round(float(v), 2))
                                                for d, v in s.items()]))
    return out


if __name__ == "__main__":
    download()
    for b in economy_block():
        print(b["id"], b["points"][-1])
