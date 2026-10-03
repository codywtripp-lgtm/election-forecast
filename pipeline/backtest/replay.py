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

from pipeline import specials
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


COLS = ["race_id", "cycle", "office", "state", "lean", "inc", "margin", "N"]


def all_training() -> pd.DataFrame:
    """Senate/governor (2000–2024) + House (2012–2024) contested races with truth, lean, incumbency."""
    t = fund.training_frame()[COLS]
    if (DB / "house_results.parquet").exists():
        h = fund.house_training_frame()
        t = pd.concat([t, h[COLS + ["district"]]], ignore_index=True)
    return t


def race_frame(cycle: int, train: pd.DataFrame | None = None) -> pd.DataFrame:
    t = all_training() if train is None else train
    t = t[t["cycle"] == cycle].copy()
    return t.assign(rule=np.where(t["state"].eq("GA"), "majority_runoff", "plurality"))


def raw_polls_frame(cycle: int, results: pd.DataFrame) -> pd.DataFrame:
    """Final-21-day Senate/governor polls for 2010–2016 from raw_polls, mapped to our race ids."""
    r = pd.read_csv(RAW / "fte_archive" / "raw_polls.csv.gz")
    r = r[(r["cycle"] == cycle) & r["type_simple"].isin(["Sen-G", "Gov-G", "House-G"])]
    r = pr._dside_margin(r)
    office = r["type_simple"].map({"Sen-G": "sen", "Gov-G": "gov", "House-G": "house"})
    # map each raw race to our race id; specials share a state → pick the race with the closest result
    res = results.set_index("race_id")["margin"]
    ids = []
    for st, off, act in zip(r["location"], office, r["actual_margin"]):
        if off == "house":
            s_, _, d_ = str(st).partition("-")
            st = f"{s_}-{int(d_):02d}" if d_.isdigit() else st
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
           ap: AvgParams | None = None, use_specials: bool = False) -> pd.DataFrame:
    # use_specials=True reproduces the Oct-2026 test (specials made every backtest metric slightly worse)
    ep = ep or ErrParams()
    ap = ap or AvgParams()
    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    results = pd.read_parquet(DB / "results_races.parquet")
    if (DB / "house_results.parquet").exists():
        results = pd.concat([results, pd.read_parquet(DB / "house_results.parquet")], ignore_index=True)
    train_all = all_training()
    hist = pr.historical_errors()
    boards = specials.all_boards() if use_specials else None
    out = []
    for cycle in cycles:
        E = ELECTION_DAYS[cycle]
        races = race_frame(cycle, train_all)
        fmodel = fund.fit(exclude_cycle=None, train=train_all[train_all["cycle"] < cycle])
        races = races[races["office"].isin(list(fmodel))]      # House needs ≥1 earlier House cycle to fit
        if races.empty:
            continue
        ratings, rparams = ratings_before(cycle, hist)
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
            if use_specials and cycle in FULL_HISTORY:
                N_hat = specials.national_blend(N_hat, ep.nat_ed * ep.scale(d), cycle, as_of, boards,
                                                exclude_cycle=cycle)["N"]
            adj = adjust(polls[polls["office"].isin(["sen", "gov", "house", "generic"])], ratings, rparams, as_of, E, ap, gt, lv)
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
