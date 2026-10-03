"""Evergreen trackers: generic-ballot average, presidential net approval, special-election swing.

Same averaging machinery as the forecast (pollster ratings, sponsor correction, house effects, recency),
evaluated weekly. Approval is not converted to a likely-voter basis (that adjustment is for vote margins).

    python -m pipeline.trackers        → site/static/data/2026/trackers.json
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DB, ELECTION_DATE, SITE_DATA
from pipeline.model import pollster_ratings as pr
from pipeline.model.average import AvgParams, adjust, averages, lv_shift, poll_frame
from pipeline.model.data import one_question_per_poll

START = dt.date(2025, 2, 1)


def approval_frame(q: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Net approval (approve − disapprove) for the sitting president, one row per poll."""
    q = q[(q["office"] == "approval") & (q["source"] == "votehub") & (q["subject"] == "Donald Trump")].copy()
    aa = a[a["qid"].isin(q["qid"])]
    ap = aa[aa["answer"].str.lower().str.startswith("approve")].groupby("qid")["pct"].max()
    dis = aa[aa["answer"].str.lower().str.startswith("disapprove")].groupby("qid")["pct"].max()
    q["dem_pct"], q["rep_pct"] = q["qid"].map(ap), q["qid"].map(dis)
    q["margin"] = q["dem_pct"] - q["rep_pct"]
    q = q.dropna(subset=["margin"])
    q["race_id"] = "approval"
    q["other_pct"], q["other_rep"], q["other_dem"], q["n_answers"] = 0.0, 0.0, 0.0, 2
    q = one_question_per_poll(q)
    q["end_date"] = pd.to_datetime(q["end_date"])
    q["published"] = pd.to_datetime(q["published"]).where(lambda s: s >= q["end_date"], q["end_date"])
    q["mid_date"] = q["end_date"] - (q["end_date"] - pd.to_datetime(q["start_date"])) / 2
    return q


def weekly_series(frame: pd.DataFrame, race_id: str, ratings, rparams, ap: AvgParams, lv, end: dt.date,
                  election: dt.date) -> list[dict]:
    out = []
    d = START
    while d <= end:
        adj = adjust(frame, ratings, rparams, d, election, ap, None, lv)
        if len(adj) >= 3:
            avgs, _ = averages(adj, ap)
            row = avgs.set_index("race_id").loc[race_id] if race_id in set(avgs["race_id"]) else None
            if row is not None:
                out.append(dict(date=d.isoformat(), value=round(float(row["poll_avg"]), 2),
                                sd=round(float(np.sqrt(row["poll_var"])), 2), n=int(row["n_polls"])))
        d += dt.timedelta(days=7)
    return out


def main(as_of: dt.date | None = None) -> None:
    as_of = as_of or dt.date.today()
    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    ratings, rparams = pr.fit()
    ap = AvgParams()
    gen = poll_frame(q[(q["cycle"] == CYCLE) & (q["office"] == "generic")], a, offices=("generic",))
    lv = lv_shift(poll_frame(q[q["cycle"] == CYCLE], a), ap)
    generic = weekly_series(gen, f"{CYCLE}-generic", ratings, rparams, ap, lv, as_of, ELECTION_DATE)
    # approval has no election date; use a far horizon so recency decay stays moderate (τ ≈ 3 weeks)
    appr = weekly_series(approval_frame(q, a), "approval", ratings, rparams, ap, (0.0, 0.0), as_of,
                         as_of + dt.timedelta(days=40))

    sp = pd.read_parquet(DB / "specials.parquet")
    sp = sp[sp["date"] >= dt.date(2025, 1, 1)].sort_values("date")
    sp["median_to_date"] = sp["swing"].expanding().median()
    specials = sp[["date", "state", "district", "held_by", "winner", "flip", "margin", "pres_margin", "swing",
                   "median_to_date"]].assign(date=lambda d: d["date"].astype(str)).to_dict(orient="records")
    sig = json.loads((DB.parent / "model" / "specials_signal.json").read_text()) \
        if (DB.parent / "model" / "specials_signal.json").exists() else None

    out = dict(as_of=as_of.isoformat(), generic_ballot=generic, approval=appr, specials=specials,
               specials_fit=sig, attribution="Special elections: The Downballot's Big Boards (the-downballot.com/p/data)")
    path = SITE_DATA / str(CYCLE) / "trackers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":"), default=float))
    print(len(generic), "generic weeks;", len(appr), "approval weeks;", len(specials), "specials")


if __name__ == "__main__":
    main()
