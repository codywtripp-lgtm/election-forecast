"""Weighting-method correction δ_class (METHODOLOGY §2.6).

Classes (hand-coded per pollster from its own methodology statement, data/manual/weighting_method.csv):
  PV   weights to recalled past presidential vote (2024 or 2020)
  PID  weights to party ID / party registration / voter-file party, but not recalled vote
  DEMO demographics only
  UNK  not coded

Estimation — completed 2025–26 races with results (launch: NJ + VA governor 2025, polls in the last
35 days). The pollster is the unit: each pollster's mean error is one observation with variance
τ_h² + σ²/n_polls, so one prolific pollster can't stand in for a whole class.

    d_c   = precision-weighted mean error of class c − the same for all pollsters
    δ_c   = d_c · P/(P + v_c)        prior δ_c ~ N(0, PRIOR_SD²)  (shrinkage)
    sd_c  = sqrt(P·v_c/(P + v_c))

Only differences BETWEEN classes are used: when applied, corrections are centred so the weighted
average correction across today's polls is zero. The field-wide miss in 2025 is not imported as a
directional correction (same rule as for the national polling error).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.config import DB, MANUAL
from pipeline.normalize.polls import pollster_key

PRIOR_SD = 2.0          # [A9]
TAU_H = 2.0             # pollster-level error around its class
SIGMA = 3.5             # per-poll error around the pollster mean (sampling + noise)
WINDOW_DAYS = 35
CLASSES = ("PV", "PID", "DEMO", "UNK")


def class_map() -> dict[str, str]:
    m = pd.read_csv(MANUAL / "weighting_method.csv")
    return {pollster_key(p): c for p, c in zip(m["pollster"], m["class"])}


def classify(pollsters: pd.Series) -> pd.Series:
    cmap = class_map()

    def one(p: str) -> str:
        k = pollster_key(p)
        if k in cmap:
            return cmap[k]
        parts = [cmap.get(pollster_key(x)) for x in str(p).split("/")]
        parts = [x for x in parts if x]
        return parts[0] if len(set(parts)) == 1 else "UNK"
    return pollsters.map(one)


def completed_race_errors() -> pd.DataFrame:
    """Final-window poll errors for completed 2025–26 races that have results."""
    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    res = pd.read_parquet(DB / "results_races.parquet")
    rc = pd.read_parquet(DB / "results_candidates.parquet")
    done = res[res["cycle"] >= 2025]
    rows = []
    for _, race in done.iterrows():
        st, cyc, office = race["state"], race["cycle"], race["office"]
        subj = f"{cyc} {_state_name(st)}"
        v = q[(q["subject"] == subj) & (q["office"] == office) & (q["stage"] == "general")].copy()
        if v.empty:
            continue
        v["end_date"] = pd.to_datetime(v["end_date"])
        v = v[v["end_date"] >= v["end_date"].max() - pd.Timedelta(days=WINDOW_DAYS)]
        party = dict(zip(rc[rc["race_id"] == race["race_id"]]["name"], rc[rc["race_id"] == race["race_id"]]["party"]))
        aa = a[a["qid"].isin(v["qid"])].assign(party=lambda d: d["candidate"].map(party))
        dem = aa[aa["party"] == "DEM"].groupby("qid")["pct"].max()
        rep = aa[aa["party"] == "REP"].groupby("qid")["pct"].max()
        v["err"] = v["qid"].map(dem) - v["qid"].map(rep) - race["margin"]
        rows.append(v.dropna(subset=["err"])[["pollster", "err"]].assign(race_id=race["race_id"]))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["pollster", "err", "race_id"])


def _state_name(st: str) -> str:
    from pipeline.states import ABBR_TO_NAME
    return ABBR_TO_NAME[st]


def estimate(errors: pd.DataFrame | None = None) -> dict[str, dict]:
    e = completed_race_errors() if errors is None else errors
    out = {c: dict(delta=0.0, sd=PRIOR_SD, n_pollsters=0, n_polls=0) for c in CLASSES}
    out["UNK"]["sd"] = 0.0
    if e.empty:
        return out
    e = e.assign(cls=classify(e["pollster"]))
    per = e.groupby(["pollster", "cls"])["err"].agg(["mean", "size"]).reset_index()
    per["var"] = TAU_H ** 2 + SIGMA ** 2 / per["size"]
    w = 1 / per["var"]
    mu_all = float(np.sum(w * per["mean"]) / np.sum(w))
    for c in ("PV", "PID", "DEMO"):
        g = per[per["cls"] == c]
        if g.empty:
            continue
        wc = 1 / g["var"]
        mu_c = float(np.sum(wc * g["mean"]) / np.sum(wc))
        v_c = float(1 / np.sum(wc))
        P = PRIOR_SD ** 2
        out[c] = dict(delta=(mu_c - mu_all) * P / (P + v_c), sd=float(np.sqrt(P * v_c / (P + v_c))),
                      n_pollsters=int(len(g)), n_polls=int(g["size"].sum()), raw_diff=mu_c - mu_all)
    out["_field_mean_error"] = dict(delta=mu_all, sd=0.0, n_pollsters=int(len(per)), n_polls=int(per["size"].sum()))
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(estimate(), indent=1))
