"""ACS 2024 1-year table-based summary files (no API key needed): state + congressional-district rows.

Tables: B03002 (race / Hispanic origin), B15003 (education, 25+), C15002H (education, white non-Hispanic 25+).
Snapshots keep only state (0400000US) and 119th-Congress district (5001900US) rows.
Output features (data/db/demographics.parquet), shares of adults 25+ / total population:
  hispanic, black, white_nc (white non-Hispanic without a bachelor's), college (bachelor's+)
"""
from __future__ import annotations

import io

import pandas as pd

from pipeline.config import DB, RAW
from pipeline.ingest.snapshot import fetch, write_snapshot
from pipeline.states import STATES

BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/1YRData/acsdt1y2024-{t}.dat"
TABLES = ["b03002", "b15003", "c15002h"]
DIR = RAW / "census_acs2024"
FIPS_TO_ABBR = {f"{s[2]:02d}": s[1] for s in STATES}


def download() -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        text = fetch(BASE.format(t=t)).decode("utf-8")
        lines = text.splitlines()
        keep = [lines[0]] + [l for l in lines[1:] if l.startswith(("0400000US", "5001900US"))]
        write_snapshot(DIR / f"{t}.dat.gz", "\n".join(keep).encode())


def _read(t: str) -> pd.DataFrame:
    return pd.read_csv(DIR / f"{t}.dat.gz", sep="|", dtype={"GEO_ID": str}).set_index("GEO_ID")


def features() -> pd.DataFrame:
    race, edu, wedu = _read("b03002"), _read("b15003"), _read("c15002h")
    df = pd.DataFrame(index=race.index)
    df["hispanic"] = race["B03002_E012"] / race["B03002_E001"]
    df["black"] = race["B03002_E004"] / race["B03002_E001"]
    ba = edu[[f"B15003_E{i:03d}" for i in range(22, 26)]].sum(axis=1)
    df["college"] = ba / edu["B15003_E001"]
    # C15002H: male 002 (total), 006 bachelor's+ ; female 007 (total), 011 bachelor's+
    w_nc = (wedu["C15002H_E002"] - wedu["C15002H_E006"]) + (wedu["C15002H_E007"] - wedu["C15002H_E011"])
    df["white_nc"] = w_nc / edu["B15003_E001"]
    df = df.reset_index()
    df["level"] = df["GEO_ID"].str[:3].map({"040": "state", "500": "cd"})
    df["state"] = df["GEO_ID"].str[9:11].map(FIPS_TO_ABBR)
    df["district"] = pd.to_numeric(df["GEO_ID"].str[11:13].where(df["level"] == "cd"), errors="coerce")
    return df


def main() -> None:
    download()
    f = features()
    f.to_parquet(DB / "demographics.parquet", index=False)
    print(f.groupby("level").size().to_dict())
    print(f[f.level == "state"].describe().round(3))


if __name__ == "__main__":
    main()
