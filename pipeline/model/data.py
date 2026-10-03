"""Model inputs derived from normalized tables: partisan lean, national environment, poll margins."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from pipeline.config import DB, MANUAL, RAW

PRES_YEARS = list(range(1976, 2025, 4))


@lru_cache
def pres_margins() -> pd.DataFrame:
    """Presidential D−R margin (% of total vote) by state and nationally, 1976–2024 (MEDSL)."""
    m = pd.read_csv(RAW / "medsl" / "president_1976_2024.csv.gz")
    m["party"] = m["party_simplified"].map({"DEMOCRAT": "DEM", "REPUBLICAN": "REP"})
    votes = m.pivot_table(index=["year", "state_po"], columns="party", values="candidatevotes", aggfunc="sum")
    total = m.groupby(["year", "state_po"])["totalvotes"].first()
    df = pd.DataFrame({"dem": votes["DEM"], "rep": votes["REP"], "total": total}).reset_index()
    df["margin"] = 100 * (df.dem - df.rep) / df.total
    nat = df.groupby("year")[["dem", "rep", "total"]].sum()
    nat["nat_margin"] = 100 * (nat.dem - nat.rep) / nat.total
    df = df.merge(nat["nat_margin"].reset_index(), on="year")
    df["rel"] = df["margin"] - df["nat_margin"]
    return df.rename(columns={"state_po": "state"})


def last_two_pres(cycle: int) -> tuple[int, int]:
    """Most recent two presidential elections strictly before `cycle` (a pres year uses the previous two)."""
    prior = [y for y in PRES_YEARS if y < cycle]
    return prior[-1], prior[-2]


LEAN_WEIGHTS = (0.75, 0.25)  # [A13]


@lru_cache
def state_lean_table() -> pd.DataFrame:
    """lean[cycle, state] = 0.75·rel(last pres) + 0.25·rel(previous pres)  (points, D positive)."""
    pm = pres_margins().set_index(["year", "state"])["rel"]
    rows = []
    for cycle in range(1998, 2031, 1):
        y1, y2 = last_two_pres(cycle)
        for st in pm.loc[y1].index:
            rows.append(dict(cycle=cycle, state=st,
                             lean=LEAN_WEIGHTS[0] * pm.loc[(y1, st)] + LEAN_WEIGHTS[1] * pm.loc[(y2, st)]))
    return pd.DataFrame(rows)


def state_lean(cycle: int, state: str) -> float:
    t = state_lean_table()
    return float(t[(t.cycle == cycle) & (t.state == state)]["lean"].iloc[0])


@lru_cache
def national_house_vote() -> pd.Series:
    return pd.read_csv(MANUAL / "national_house_vote.csv").set_index("cycle")["dem_margin"]


def pres_party(cycle: int) -> str:
    """Party of the sitting president during the campaign for `cycle`."""
    if cycle <= 2000:
        return "DEM"
    if cycle <= 2008:
        return "REP"
    if cycle <= 2016:
        return "DEM"
    if cycle <= 2020:
        return "REP"
    if cycle <= 2024:
        return "DEM"
    return "REP"


def is_midterm(cycle: int) -> bool:
    return cycle % 4 == 2


# ---------------------------------------------------------------- poll margins

MAX_UNMATCHED = 10.0
POP_RANK = {"lv": 0, "v": 1, "rv": 2, "a": 3, "unknown": 4}


def question_margins(q: pd.DataFrame, a: pd.DataFrame, d_side: dict[str, str] | None = None) -> pd.DataFrame:
    """D-side minus top-Republican margin per poll question (points of the full sample).

    d_side: optional race_id → candidate_id forcing which candidate is the D side
    (e.g. a Democratic-backed independent). Otherwise: Democratic candidate if present,
    else the strongest non-Republican.
    """
    a = a[a["qid"].isin(q["qid"])].copy()
    a["pct"] = pd.to_numeric(a["pct"], errors="coerce")
    a = a.dropna(subset=["pct"])
    rid = q.set_index("qid")["race_id"]
    out = []
    has_ids = "candidate_id" in a.columns
    for qid, g in a.groupby("qid", sort=False):
        g = g.sort_values("pct", ascending=False)
        if has_ids:
            # answers naming someone who is not on the November ballot (pre-primary hypotheticals):
            # if they hold ≥ MAX_UNMATCHED points the question isn't a test of the real matchup
            unmatched = g["candidate_id"].isna() & g["party"].isna()
            if g.loc[unmatched, "pct"].sum() >= MAX_UNMATCHED:
                continue
        rep = g[g["party"] == "REP"]
        forced = d_side.get(rid.get(qid)) if d_side else None
        if forced is not None:
            dem = g[g["candidate_id"] == forced]
        else:
            dem = g[g["party"] == "DEM"]
            if dem.empty:
                dem = g[~g["party"].isin(["REP"]) & g["party"].notna()]
        if dem.empty or rep.empty:
            continue
        d, r = float(dem["pct"].iloc[0]), float(rep["pct"].iloc[0])
        other = float(g["pct"].sum()) - d - r
        other_rep = float(rep["pct"].iloc[1:].sum())                      # e.g. 2nd/3rd Republicans (AK)
        other_dem = float(g[g["party"] == "DEM"]["pct"].sum()) - (d if dem["party"].iloc[0] == "DEM" else 0.0)
        out.append((qid, d, r, other, other_rep, other_dem, len(g)))
    m = pd.DataFrame(out, columns=["qid", "dem_pct", "rep_pct", "other_pct", "other_rep", "other_dem", "n_answers"])
    m["margin"] = m["dem_pct"] - m["rep_pct"]
    return q.merge(m, on="qid")


def choose_d_side(q: pd.DataFrame, a: pd.DataFrame, cands: pd.DataFrame) -> dict[str, str]:
    """Which candidate is the 'D side' of each 2026 race: the non-Republican with the highest average
    poll share, else the Democratic nominee, else the first non-Republican listed.
    Handles Dem-backed independents (NE, ID, SD) and three-way races (MT)."""
    gen = q[(q["stage"] == "general") & q["race_id"].isin(cands["race_id"])]
    sh = a[a["qid"].isin(gen["qid"]) & a["candidate_id"].notna() & (a["party"] != "REP")]
    stats = sh.groupby("candidate_id")["pct"].agg(["mean", "count"])
    out = {}
    for rid, g in cands.groupby("race_id"):
        nonrep = g[g["party"] != "REP"]
        polled = stats.reindex(nonrep["candidate_id"]).dropna()
        if len(polled):
            out[rid] = polled["mean"].idxmax()
        elif (nonrep["party"] == "DEM").any():
            out[rid] = nonrep[nonrep["party"] == "DEM"]["candidate_id"].iloc[0]
        elif len(nonrep):  # prefer an independent over minor parties
            out[rid] = nonrep.sort_values("party", key=lambda s: s.ne("IND"))["candidate_id"].iloc[0]
    return out


def choose_r_side(q: pd.DataFrame, a: pd.DataFrame, cands: pd.DataFrame) -> dict[str, str]:
    """Leading Republican per race (matters where several Republicans share a top-four ballot, AK):
    highest average poll share, else the incumbent, else the first listed."""
    gen = q[(q["stage"] == "general") & q["race_id"].isin(cands["race_id"])]
    sh = a[a["qid"].isin(gen["qid"]) & a["candidate_id"].notna() & (a["party"] == "REP")]
    stats = sh.groupby("candidate_id")["pct"].mean()
    out = {}
    for rid, g in cands[cands["party"] == "REP"].groupby("race_id"):
        polled = stats.reindex(g["candidate_id"]).dropna()
        if len(polled):
            out[rid] = polled.idxmax()
        elif g["incumbent"].any():
            out[rid] = g[g["incumbent"]]["candidate_id"].iloc[0]
        else:
            out[rid] = g["candidate_id"].iloc[0]
    return out


def one_question_per_poll(df: pd.DataFrame) -> pd.DataFrame:
    """A poll often reports LV and RV, or with/without third parties. Keep one per poll and race:
    likeliest-voter population first, then the version with the most candidates listed."""
    df = df.assign(_pop=df["population"].map(POP_RANK).fillna(5))
    df = df.sort_values(["poll_id", "race_id", "_pop", "n_answers"], ascending=[True, True, True, False])
    return df.drop_duplicates(["poll_id", "race_id"]).drop(columns="_pop")


def sampling_var(n: pd.Series | np.ndarray | float, n_default: float = 600.0) -> np.ndarray:
    """Variance of a poll margin from sampling alone, points². Var(d−r) ≈ 1e4·(p+q−(p−q)²)/n ≈ 1e4/n."""
    n = np.asarray(pd.to_numeric(n, errors="coerce"), dtype=float)
    n = np.where(np.isfinite(n) & (n > 0), n, n_default)
    return 1e4 / n
