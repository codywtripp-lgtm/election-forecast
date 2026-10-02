"""Fundamentals prior (METHODOLOGY §4).

    margin_r = a_o + λ_o·lean_r + β_o·N + γ_o·inc_r + ε,   ε ~ N(0, σ_o²)

lean_r : state presidential lean (0.75·last + 0.25·previous, relative to national)       [A13]
N      : national House popular-vote margin (actual in the fit; generic-ballot average when forecasting)
inc_r  : +1 D-side incumbent running, −1 Republican incumbent running, 0 open seat          [A15]
Fit separately for Senate and governor (governors follow partisanship less: λ_gov < λ_sen) [A14]
on 2000–2024 contested D-vs-R races. Candidate quality and fundraising are not in the launch
version (DATA_GAPS G8, S13).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.config import DB
from pipeline.model.data import national_house_vote, state_lean_table

FIT_YEARS = range(2000, 2025, 2)
FEATURES = ["lean", "N", "inc"]
CYCLE_DECAY = 0.8   # weight per 2-year cycle back: incumbency and partisanship have changed since 2000


def inc_code(running: bool, inc_party: str | None) -> int:
    if not running or inc_party is None:
        return 0
    return -1 if inc_party == "REP" else 1


def training_frame() -> pd.DataFrame:
    r = pd.read_parquet(DB / "results_races.parquet")
    r = r[r["cycle"].isin(FIT_YEARS) & r["contested"] & ~r["top2_same_party"] & ~r["dem_is_ind"]]
    r = r[~((r["office"] == "sen") & (r["state"] == "LA"))]       # jungle-primary era
    r = r[r["race_id"] != "2020-sen-GA-S"]                          # all-party special
    lean = state_lean_table()
    r = r.merge(lean, on=["cycle", "state"], how="inner")
    r["N"] = r["cycle"].map(national_house_vote())
    r["inc"] = [inc_code(run, p) for run, p in zip(r["incumbent_running"], r["incumbent_cand_party"])]
    return r.dropna(subset=["margin", "lean", "N"])


def house_training_frame() -> pd.DataFrame:
    """2012–2024 contested D-vs-R House races with district lean on that cycle's lines."""
    r = pd.read_parquet(DB / "house_results.parquet")
    for c in ("contested", "top2_same_party", "dem_is_ind"):
        r[c] = r[c].fillna(False).astype(bool)
    r = r[r["contested"] & ~r["top2_same_party"] & ~r["dem_is_ind"]]
    r = r[r["state"] != "LA"]                                      # November jungle primaries before 2026
    r["district"] = r["race_id"].str[-2:].astype(int)
    lean = pd.read_parquet(DB / "house_lean.parquet")
    r = r.merge(lean[["cycle", "state", "district", "lean"]], on=["cycle", "state", "district"], how="inner")
    r["N"] = r["cycle"].map(national_house_vote())
    r["inc"] = [inc_code(run, p) for run, p in zip(r["incumbent_running"], r["incumbent_cand_party"])]
    return r.dropna(subset=["margin", "lean", "N"])


def fit(train: pd.DataFrame | None = None, exclude_cycle: int | None = None) -> dict:
    """OLS per office. exclude_cycle supports leave-one-cycle-out backtests."""
    if train is None:
        t = training_frame()
        if (DB / "house_results.parquet").exists():
            t = pd.concat([t, house_training_frame()], ignore_index=True)
    else:
        t = train
    if exclude_cycle is not None:
        t = t[t["cycle"] != exclude_cycle]
    out = {}
    for office, g in t.groupby("office"):
        X = np.column_stack([np.ones(len(g))] + [g[f].to_numpy(float) for f in FEATURES])
        y = g["margin"].to_numpy(float)
        w = CYCLE_DECAY ** ((g["cycle"].max() - g["cycle"].to_numpy()) / 2)
        sw = np.sqrt(w)
        coef, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
        resid = y - X @ coef
        n_eff = w.sum() ** 2 / (w ** 2).sum()
        sigma = float(np.sqrt(np.sum(w * resid ** 2) / w.sum() * n_eff / max(1, n_eff - X.shape[1])))
        cov = sigma ** 2 * np.linalg.inv((X * w[:, None]).T @ X)
        out[office] = dict(coef=dict(zip(["const"] + FEATURES, coef.round(4).tolist())),
                           se=dict(zip(["const"] + FEATURES, np.sqrt(np.diag(cov)).round(4).tolist())),
                           sigma=sigma, n=len(y))
    return out


def predict(model: dict, office: str, lean: float, N: float, inc: int) -> tuple[float, float]:
    c = model[office]["coef"]
    mu = c["const"] + c["lean"] * lean + c["N"] * N + c["inc"] * inc
    return float(mu), float(model[office]["sigma"])


if __name__ == "__main__":
    import json
    print(json.dumps(fit(), indent=1))
