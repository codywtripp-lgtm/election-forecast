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


POS = ("approve", "favorable")
NEG = ("disapprove", "unfavorable")


def net_frame(q: pd.DataFrame, a: pd.DataFrame, office: str, subject: str) -> pd.DataFrame:
    """Net (approve − disapprove, or favorable − unfavorable) per poll for one subject."""
    q = q[(q["office"] == office) & (q["source"] == "votehub") & (q["subject"] == subject)].copy()
    aa = a[a["qid"].isin(q["qid"])].assign(ans=lambda d: d["answer"].str.lower().str.strip())
    pos = aa[aa["ans"].isin(POS)].groupby("qid")["pct"].max()
    neg = aa[aa["ans"].isin(NEG)].groupby("qid")["pct"].max()
    q["dem_pct"], q["rep_pct"] = q["qid"].map(pos), q["qid"].map(neg)
    q["margin"] = q["dem_pct"] - q["rep_pct"]
    q = q.dropna(subset=["margin"])
    q["race_id"] = "net"
    q["other_pct"], q["other_rep"], q["other_dem"], q["n_answers"] = 0.0, 0.0, 0.0, 2
    q = one_question_per_poll(q)
    q["end_date"] = pd.to_datetime(q["end_date"])
    q["published"] = pd.to_datetime(q["published"]).where(lambda s: s >= q["end_date"], q["end_date"])
    q["mid_date"] = q["end_date"] - (q["end_date"] - pd.to_datetime(q["start_date"])) / 2
    return q


SERIES = [  # key, office, subject, label
    ("approval", "approval", "Donald Trump", "Donald Trump: net job approval"),
    ("trump_fav", "favorability", "Donald Trump", "Donald Trump: net favorability"),
    ("vance_fav", "favorability", "JD Vance", "JD Vance: net favorability"),
    ("congress", "approval", "Congress", "Congress: net approval"),
    ("scotus", "approval", "Supreme Court", "Supreme Court: net approval"),
]


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
    # approval/favorability have no election date; a short horizon keeps recency decay moderate (τ ≈ 3 weeks)
    nets = {}
    for key, office, subject, label in SERIES:
        f = net_frame(q, a, office, subject)
        if len(f) >= 10:
            nets[key] = dict(label=label, points=weekly_series(f, "net", ratings, rparams, ap, (0.0, 0.0), as_of,
                                                               as_of + dt.timedelta(days=40)), n_polls=int(len(f)))
    appr = nets.get("approval", {}).get("points", [])

    sp = pd.read_parquet(DB / "specials.parquet")
    sp = sp[sp["date"] >= dt.date(2025, 1, 1)].sort_values("date")
    sp["median_to_date"] = sp["swing"].expanding().median()
    specials = sp[["date", "state", "district", "held_by", "winner", "flip", "margin", "pres_margin", "swing",
                   "median_to_date"]].assign(date=lambda d: d["date"].astype(str)).to_dict(orient="records")
    sig = json.loads((DB.parent / "model" / "specials_signal.json").read_text()) \
        if (DB.parent / "model" / "specials_signal.json").exists() else None

    from pipeline.ingest.fred import economy_block
    from pipeline.mood import mood_block
    out = dict(as_of=as_of.isoformat(), generic_ballot=generic, approval=appr, nets=nets, specials=specials,
               economy=economy_block(), mood=mood_block(),
               specials_fit=sig, attribution="Special elections: The Downballot's Big Boards (the-downballot.com/p/data)")
    path = SITE_DATA / str(CYCLE) / "trackers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":"), default=float))
    print(len(generic), "generic weeks;", {k: len(v["points"]) for k, v in nets.items()}, len(specials), "specials")


if __name__ == "__main__":
    main()
