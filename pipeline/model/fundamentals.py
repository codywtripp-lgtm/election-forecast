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
import os

FEATURES = ["lean", "N", "inc"]
# [A17] fundraising (FEC individual contributions, log D/R ratio). Backtest (Oct 2026): House Brier −3%
# (30 days) / −4% (120 days); Senate mixed; no governor data → used for the House only.
# MODEL_MONEY=all|none overrides for comparison runs.
MONEY_OFFICES = {"all": ("sen", "house"), "none": ()}.get(os.environ.get("MODEL_MONEY", ""), ("house",))


# [A16] incumbent's past overperformance (candidate-strength proxy) for Senate/governor. Backtest (Oct 2026):
# governor Brier −8.5% at 120 days, −6% at 60; Senate −1–2%; election-eve neutral. MODEL_INCOVER=off to compare.
INCOVER_OFFICES = () if os.environ.get("MODEL_INCOVER", "") == "off" else ("sen", "gov")


def features_for(office: str) -> list[str]:
    return (FEATURES + (["money"] if office in MONEY_OFFICES else [])
            + (["inc_over"] if office in INCOVER_OFFICES else []))


def _same_person(a, b) -> bool:
    import re
    norm = lambda s: re.sub(r"[^a-z ]", "", str(s).lower()).split()
    na, nb = norm(a), norm(b)
    return bool(na and nb) and na[-1] == nb[-1] and na[0][:1] == nb[0][:1]


def incumbent_overperformance(cycle: int, office: str, state: str, incumbent: str,
                              results: pd.DataFrame) -> float:
    """How far the incumbent's last win beat partisanship + environment:
    prev D-side margin − prev state lean − prev national House margin (sign: + = D-side strong).
    0 if no earlier race in our data. Odd-year governor races use the following even year's N."""
    prev = results[(results["office"] == office) & (results["state"] == state) & (results["cycle"] < cycle)]
    prev = prev.sort_values("cycle", ascending=False)
    for r in prev.itertuples():
        if _same_person(r.winner_name, incumbent) and pd.notna(r.margin):
            lean = state_lean_table()
            lv = lean[(lean["cycle"] == r.cycle) & (lean["state"] == state)]["lean"]
            hv = national_house_vote()
            nyear = r.cycle if r.cycle in hv.index else r.cycle + 1
            if lv.empty or nyear not in hv.index:
                return 0.0
            return float(r.margin - lv.iloc[0] - hv[nyear])
    return 0.0


def attach_money(t: pd.DataFrame) -> pd.DataFrame:
    path = DB / "money.parquet"
    if not path.exists():
        return t.assign(money=0.0)
    m = pd.read_parquet(path)[["race_id", "money", "dem_indiv", "rep_indiv"]]
    t = t.drop(columns=["money", "dem_indiv", "rep_indiv"], errors="ignore").merge(m, on="race_id", how="left")
    t["money"] = t["money"].fillna(0.0).clip(-6, 6)       # unknown → neutral; cap extreme ratios
    return t
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
    allres = pd.read_parquet(DB / "results_races.parquet")
    r["inc_over"] = [incumbent_overperformance(c, o, s, inc, allres) if run else 0.0
                     for c, o, s, inc, run in zip(r["cycle"], r["office"], r["state"], r["incumbent"], r["incumbent_running"])]
    r["inc_over"] = r["inc_over"].clip(-60, 60)
    return attach_money(r.dropna(subset=["margin", "lean", "N"]))


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
    r["inc_over"] = 0.0          # House: not used (district lines change too often for a clean comparison)
    return attach_money(r.dropna(subset=["margin", "lean", "N"]))


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
    if "money" not in t.columns:
        t = t.assign(money=0.0)
    if "inc_over" not in t.columns:
        t = t.assign(inc_over=0.0)
    t = t.assign(inc_over=t["inc_over"].fillna(0.0))
    for office, g in t.groupby("office"):
        feats = [f for f in features_for(office) if f in FEATURES or g[f].abs().sum() > 0]  # no data → drop
        X = np.column_stack([np.ones(len(g))] + [g[f].to_numpy(float) for f in feats])
        y = g["margin"].to_numpy(float)
        w = CYCLE_DECAY ** ((g["cycle"].max() - g["cycle"].to_numpy()) / 2)
        sw = np.sqrt(w)
        coef, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
        resid = y - X @ coef
        n_eff = w.sum() ** 2 / (w ** 2).sum()
        sigma = float(np.sqrt(np.sum(w * resid ** 2) / w.sum() * n_eff / max(1, n_eff - X.shape[1])))
        cov = sigma ** 2 * np.linalg.pinv((X * w[:, None]).T @ X)
        out[office] = dict(coef=dict(zip(["const"] + feats, coef.round(4).tolist())),
                           se=dict(zip(["const"] + feats, np.sqrt(np.diag(cov)).round(4).tolist())),
                           sigma=sigma, n=len(y))
    return out


def predict(model: dict, office: str, lean: float, N: float, inc: int, money: float = 0.0,
            inc_over: float = 0.0) -> tuple[float, float]:
    c = model[office]["coef"]
    mu = (c["const"] + c["lean"] * lean + c["N"] * N + c["inc"] * inc + c.get("money", 0.0) * money
          + c.get("inc_over", 0.0) * inc_over)
    return float(mu), float(model[office]["sigma"])


if __name__ == "__main__":
    import json
    print(json.dumps(fit(), indent=1))
