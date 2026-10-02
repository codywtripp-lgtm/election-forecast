"""As-of replays of past cycles (METHODOLOGY §7).

For each past cycle C and as-of date (days before the election), the model is rebuilt using only
information available then:
  * pollster ratings fit on cycles < C
  * fundamentals fit on cycles < C
  * polls published on or before the as-of date
  * national environment N̂ = generic-ballot average as of that date
2018–2024 use full poll histories (538 archive). 2010–2016 use the final-21-day polls in raw_polls
(final forecast only — DATA_GAPS G3).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from pipeline.config import DB, RAW
from pipeline.model import fundamentals as fund
from pipeline.model import pollster_ratings as pr
from pipeline.model.average import AvgParams, adjust, averages, generic_trend_fn, lv_shift, poll_frame
from pipeline.model.data import national_house_vote, state_lean_table
from pipeline.model.forecast import ErrParams, blend
from pipeline.normalize.polls import pollster_key

ELECTION_DAYS = {2010: dt.date(2010, 11, 2), 2012: dt.date(2012, 11, 6), 2014: dt.date(2014, 11, 4),
                 2016: dt.date(2016, 11, 8), 2018: dt.date(2018, 11, 6), 2020: dt.date(2020, 11, 3),
                 2022: dt.date(2022, 11, 8), 2024: dt.date(2024, 11, 5)}
FULL_HISTORY = (2018, 2020, 2022, 2024)
DAYS_OUT = (120, 90, 60, 30, 14, 7, 1)


def race_frame(cycle: int) -> pd.DataFrame:
    """Contested D-vs-R Senate/governor races of a past cycle with truth, lean and incumbency."""
    t = fund.training_frame()
    t = t[t["cycle"] == cycle].copy()
    return t[["race_id", "cycle", "office", "state", "lean", "inc", "margin", "rule"] if "rule" in t else
             ["race_id", "cycle", "office", "state", "lean", "inc", "margin"]].assign(
        rule=lambda d: np.where(d["state"].eq("GA"), "majority_runoff", "plurality"))


def raw_polls_frame(cycle: int, results: pd.DataFrame) -> pd.DataFrame:
    """Final-21-day Senate/governor polls for 2010–2016 from raw_polls, mapped to our race ids."""
    r = pd.read_csv(RAW / "fte_archive" / "raw_polls.csv.gz")
    r = r[(r["cycle"] == cycle) & r["type_simple"].isin(["Sen-G", "Gov-G"])]
    r = pr._dside_margin(r)
    office = r["type_simple"].map({"Sen-G": "sen", "Gov-G": "gov"})
    # map each raw race to our race id; specials share a state → pick the race with the closest result
    res = results.set_index("race_id")["margin"]
    ids = []
    for st, off, act in zip(r["location"], office, r["actual_margin"]):
        cands = [i for i in (f"{cycle}-{off}-{st}", f"{cycle}-{off}-{st}-S") if i in res.index]
        ids.append(min(cands, key=lambda i: abs(res[i] - act)) if cands else None)
    end = pd.to_datetime(r["polldate"])
    df = pd.DataFrame({
        "qid": "raw:" + r["question_id"].astype(str), "poll_id": "raw:" + r["poll_id"].astype(str),
        "race_id": ids, "office": office.to_numpy(), "cycle": cycle, "pollster": r["pollster"],
        "pollster_key": r["pollster"].map(pollster_key), "partisan": r["partisan"].map(
            lambda x: x if x in ("DEM", "REP") else None), "internal": False,
        "sample_size": r["samplesize"], "population": "lv", "end_date": end, "start_date": end,
        "published": end, "mid_date": end, "margin": r["poll_margin"],
        "dem_pct": np.nan, "rep_pct": np.nan, "other_pct": 0.0, "other_rep": 0.0, "other_dem": 0.0,
    })
    return df.dropna(subset=["race_id"])


def ratings_before(cycle: int, hist: pd.DataFrame):
    return pr.fit(hist[hist["cycle"] < cycle])


def replay(cycles=tuple(ELECTION_DAYS), days_out=DAYS_OUT, ep: ErrParams | None = None,
           ap: AvgParams | None = None) -> pd.DataFrame:
    ep = ep or ErrParams()
    ap = ap or AvgParams()
    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    results = pd.read_parquet(DB / "results_races.parquet")
    hist = pr.historical_errors()
    out = []
    for cycle in cycles:
        E = ELECTION_DAYS[cycle]
        races = race_frame(cycle)
        if races.empty:
            continue
        ratings, rparams = ratings_before(cycle, hist)
        fmodel = fund.fit(exclude_cycle=None, train=fund.training_frame().query("cycle < @cycle"))
        if cycle in FULL_HISTORY:
            polls = poll_frame(q[q["cycle"] == cycle], a)
            dlist = days_out
        else:
            polls = raw_polls_frame(cycle, results[results["cycle"] == cycle])
            dlist = (1,)
        lv = lv_shift(polls, ap) if cycle in FULL_HISTORY else (0.0, 0.0)
        for d in dlist:
            as_of = E - dt.timedelta(days=d)
            if cycle in FULL_HISTORY:
                gt = generic_trend_fn(polls, ratings, rparams, as_of, E, ap)
                N_hat = gt(pd.Timestamp(as_of)) if gt else float(national_house_vote()[cycle])
            else:
                gt, N_hat = None, final_generic(cycle)
            adj = adjust(polls[polls["office"].isin(["sen", "gov", "generic"])], ratings, rparams, as_of, E, ap, gt, lv)
            avgs, _ = averages(adj, ap)
            tbl = blend(races, avgs, fmodel, N_hat, d, ep)
            tbl["days_out"] = d
            tbl["N_hat"] = N_hat
            tbl["N_true"] = float(national_house_vote()[cycle])
            out.append(tbl)
    return pd.concat(out, ignore_index=True)


def final_generic(cycle: int) -> float:
    """Mean of final-21-day generic-ballot polls (raw_polls) — N̂ for the 2010–2016 final replays."""
    r = pd.read_csv(RAW / "fte_archive" / "raw_polls.csv.gz")
    g = pr._dside_margin(r[(r["cycle"] == cycle) & (r["type_simple"] == "House-G-US")])
    return float(g["poll_margin"].mean())


if __name__ == "__main__":
    bt = replay()
    bt.to_parquet(DB / "backtest_replay.parquet", index=False)
    bt["err"] = bt["margin"] - bt["mu"]
    print(bt.groupby(["days_out"]).agg(mae=("err", lambda e: e.abs().mean()), n=("err", "size"),
                                       bias=("err", "mean")).round(2))
