"""Candidate fundraising from FEC bulk "all candidates" summaries (weballYY.zip, public domain).

Measure: individual contributions (TTL_INDIV_CONTRIB) — excludes self-funding, loans and transfers.
Race feature: money = log((D + 5,000) / (R + 5,000)) for the D-side and Republican nominees,
matched to our race tables by state, office, district and last name.

Caveat for backtests: historical files are end-of-cycle totals (include October–December money),
so a backtest of this feature is somewhat optimistic; the 2026 file is as of the latest filings.

    python -m pipeline.fec   → data/db/money.parquet (race_id, money, dem_indiv, rep_indiv)
"""
from __future__ import annotations

import io
import re
import zipfile

import numpy as np
import pandas as pd

from pipeline.config import DB, RAW
from pipeline.ingest.snapshot import SESSION

DIR = RAW / "fec"
CYCLES = (2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026)
COLS = ["cand_id", "name", "ici", "pty_cd", "party", "receipts", "trans_from", "disb", "trans_to", "coh_bop",
        "coh_cop", "cand_contrib", "cand_loans", "other_loans", "cand_loan_repay", "other_loan_repay", "debts",
        "indiv", "state", "district", "spec", "prim", "run", "gen", "gen_pct", "other_cmte", "party_contrib",
        "cvg_end", "indiv_refunds", "cmte_refunds"]
FLOOR = 5_000.0


def download(cycle: int) -> None:
    yy = str(cycle)[2:]
    r = SESSION.get(f"https://www.fec.gov/files/bulk-downloads/{cycle}/weball{yy}.zip", timeout=120)
    r.raise_for_status()
    (DIR / f"weball{yy}.zip").write_bytes(r.content)


def read(cycle: int) -> pd.DataFrame:
    yy = str(cycle)[2:]
    with zipfile.ZipFile(DIR / f"weball{yy}.zip") as z:
        raw = z.read(z.namelist()[0]).decode("latin-1")
    df = pd.read_csv(io.StringIO(raw), sep="|", header=None, names=COLS, dtype=str)
    df["office"] = df["cand_id"].str[0].map({"H": "house", "S": "sen"})
    df["indiv"] = pd.to_numeric(df["indiv"], errors="coerce").fillna(0.0)
    df["district"] = pd.to_numeric(df["district"], errors="coerce").fillna(0).astype(int)
    df["party"] = df["party"].map({"DEM": "DEM", "DFL": "DEM", "REP": "REP"}).fillna("OTH")
    df["last"] = df["name"].str.split(",").str[0].str.strip().str.lower().str.replace(r"[^a-z]", "", regex=True)
    df["cycle"] = cycle
    return df[df["office"].notna()]


def _last(name: str | None) -> str:
    if not isinstance(name, str):
        return ""
    parts = [p for p in re.sub(r"[^A-Za-z\- ]", " ", name).split() if p.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    return re.sub(r"[^a-z]", "", parts[-1].lower()) if parts else ""


def match(fec: pd.DataFrame, cycle: int, office: str, state: str, district: int | None, name: str | None,
          party: str | None) -> float | None:
    g = fec[(fec["cycle"] == cycle) & (fec["office"] == office) & (fec["state"] == state)]
    if office == "house":
        d = 0 if district in (None, 1) and len(g[g["district"] == 0]) else district
        g = g[g["district"].isin([d, district])]
    ln = _last(name)
    hit = g[g["last"] == ln]
    if party in ("DEM", "REP"):
        hp = hit[hit["party"] == party]
        hit = hp if len(hp) else hit
    if hit.empty:
        return None
    return float(hit["indiv"].max())


def race_money(races: pd.DataFrame, fec: pd.DataFrame) -> pd.DataFrame:
    """races: race_id, cycle, office, state, district, dem_name, rep_name, d_party."""
    rows = []
    for r in races.itertuples():
        if r.office not in ("house", "sen"):
            continue
        dist = None if pd.isna(getattr(r, "district", np.nan)) else int(r.district)
        d = match(fec, r.cycle, r.office, r.state, dist, r.dem_name, getattr(r, "d_party", "DEM"))
        rp = match(fec, r.cycle, r.office, r.state, dist, r.rep_name, "REP")
        if d is None and rp is None:
            continue
        # a nominee missing from the FEC file (late entrant, unmatched name) → unknown, not $0
        money = float(np.log((d + FLOOR) / (rp + FLOOR))) if d is not None and rp is not None else np.nan
        rows.append(dict(race_id=r.race_id, dem_indiv=d, rep_indiv=rp, money=money))
    return pd.DataFrame(rows)


def main(refresh: bool = True) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    if refresh:
        try:
            download(2026)
        except Exception as exc:  # keep the saved file
            print("FEC 2026 download failed:", exc)
    fec = pd.concat([read(c) for c in CYCLES if (DIR / f"weball{str(c)[2:]}.zip").exists()], ignore_index=True)
    # historical races (results) + 2026 races (nominees)
    hist = pd.read_parquet(DB / "results_races.parquet")
    if (DB / "house_results.parquet").exists():
        hist = pd.concat([hist, pd.read_parquet(DB / "house_results.parquet")], ignore_index=True)
    hist["district"] = np.where(hist["race_id"].str.contains("-house-"), hist["race_id"].str[-2:], np.nan)
    hist = hist[hist["cycle"].isin(CYCLES)]
    from pipeline.model.data import choose_d_side, choose_r_side
    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    races = pd.read_parquet(DB / "races.parquet")
    cands = pd.read_parquet(DB / "candidates.parquet")
    if (DB / "house_races.parquet").exists():
        races = pd.concat([races, pd.read_parquet(DB / "house_races.parquet")], ignore_index=True)
        cands = pd.concat([cands, pd.read_parquet(DB / "house_candidates.parquet")], ignore_index=True)
    ds, rs = choose_d_side(q, a, cands), choose_r_side(q, a, cands)
    name = cands.set_index("candidate_id")["name"]
    party = cands.set_index("candidate_id")["party"]
    cur = races.assign(dem_name=races["race_id"].map(lambda r: name.get(ds.get(r))),
                       rep_name=races["race_id"].map(lambda r: name.get(rs.get(r))),
                       d_party=races["race_id"].map(lambda r: party.get(ds.get(r))))
    out = pd.concat([race_money(hist, fec), race_money(cur, fec)], ignore_index=True)
    out.to_parquet(DB / "money.parquet", index=False)
    cyc = out["race_id"].str[:4]
    print(out.groupby(cyc).size().to_dict())


if __name__ == "__main__":
    import os
    main(refresh=os.environ.get("GITHUB_ACTIONS") == "true")
