"""Poll adjustments and per-race polling averages (METHODOLOGY §2–3).

Every poll keeps a per-step breakdown (raw → population → sponsor → house effect → trend) and the
components of its weight, so the race page can show why each poll counts as much as it does.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pipeline.model import pollster_ratings as pr
from pipeline.model.data import one_question_per_poll, question_margins, sampling_var


@dataclass
class AvgParams:
    # [A5] LV − RV shift: prior from 2018/2022/2024 paired polls, updated with current-cycle pairs
    lv_prior_mean: float = -0.9
    lv_prior_sd: float = 1.0
    rv_minus_a: float = 0.4          # RV − adult shift (paired polls 2018–2024 average)
    rv_minus_a_sd: float = 0.5
    # [A8] partisan sponsors (relative error vs field, 2014–2024): DEM +2.8, REP −3.9
    sponsor_shift: dict = field(default_factory=lambda: {"DEM": -2.8, "REP": 3.85})
    sponsor_weight: float = 0.5
    herding_weight: float = 0.75     # [A3]
    n_cap: float = 1500.0            # [A7]
    # [A6] recency: weight = exp(−age / τ), τ = tau_base + tau_slope · days to election
    tau_base: float = 10.0
    tau_slope: float = 0.25
    trend_beta: float = 0.75         # share of national generic-ballot movement applied to stale polls
    house_sd: float = 2.0            # prior sd of a pollster's house effect around its historical bias
    max_age_days: int = 365


def poll_frame(q: pd.DataFrame, a: pd.DataFrame, offices=("sen", "gov", "generic", "house"),
               d_side: dict | None = None) -> pd.DataFrame:
    """Margins for general-election questions, one per poll and race."""
    q = q[q["office"].isin(offices) & (q["stage"] == "general") & ~q["hypothetical"]].copy()
    q.loc[q["office"] == "generic", "race_id"] = q.loc[q["office"] == "generic", "cycle"].astype(str) + "-generic"
    m = question_margins(q, a, d_side)
    m = one_question_per_poll(m)
    m["end_date"] = pd.to_datetime(m["end_date"])
    m["published"] = pd.to_datetime(m["published"]).where(lambda s: s >= m["end_date"], m["end_date"])
    m["mid_date"] = m["end_date"] - (m["end_date"] - pd.to_datetime(m["start_date"])) / 2
    return m


def lv_shift(polls: pd.DataFrame, p: AvgParams) -> tuple[float, float]:
    """Posterior LV−RV shift: prior × current-cycle paired LV/RV releases of the same poll."""
    key = ["pollster", "end_date", "race_id"]
    piv = polls.pivot_table(index=key, columns="population", values="margin", aggfunc="mean")
    if {"lv", "rv"} <= set(piv.columns):
        d = (piv["lv"] - piv["rv"]).dropna()
    else:
        d = pd.Series(dtype=float)
    if len(d) < 3:
        return p.lv_prior_mean, p.lv_prior_sd
    se2 = max(d.var(ddof=1), 1.0) / len(d)
    w0, w1 = 1 / p.lv_prior_sd ** 2, 1 / se2
    return (w0 * p.lv_prior_mean + w1 * d.mean()) / (w0 + w1), (w0 + w1) ** -0.5


def adjust(polls: pd.DataFrame, ratings: pd.DataFrame, rparams: dict, as_of: dt.date,
           election: dt.date, p: AvgParams, generic_trend=None, lv=None) -> pd.DataFrame:
    """Apply population + sponsor corrections and compute weights (before house effects)."""
    as_of_ts = pd.Timestamp(as_of)
    df = polls[(polls["published"] <= as_of_ts) & (polls["end_date"] >= as_of_ts - pd.Timedelta(days=p.max_age_days))].copy()
    if df.empty:
        return df
    lv_mean, _ = lv if lv is not None else (p.lv_prior_mean, 0)
    df["adj_pop"] = np.select([df["population"].eq("rv"), df["population"].eq("a")],
                              [lv_mean, lv_mean + p.rv_minus_a], 0.0)
    df["adj_sponsor"] = df["partisan"].map(p.sponsor_shift).fillna(0.0)
    rated = [pr.lookup(ratings, rparams, x) for x in df["pollster"]]
    df["hist_bias"] = [r["bias"] for r in rated]
    df["tau2"] = [r["tau2"] for r in rated]
    df["herding"] = [r["herding"] for r in rated]
    df["rated"] = [r["rated"] for r in rated]
    n = pd.to_numeric(df["sample_size"], errors="coerce").clip(upper=p.n_cap)
    df["sv"] = sampling_var(n)
    days_left = max(0, (election - as_of).days)
    tau = p.tau_base + p.tau_slope * days_left
    df["age"] = (as_of_ts - df["mid_date"]).dt.days.clip(lower=0)
    df["w_recency"] = np.exp(-df["age"] / tau)
    df["w_quality"] = (df["sv"].median() + 3.0) / (df["sv"] + df["tau2"])  # 1/variance, normalised
    df["w_sponsor"] = np.where(df["partisan"].isin(["DEM", "REP"]) | df["internal"], p.sponsor_weight, 1.0)
    df["w_herding"] = np.where(df["herding"], p.herding_weight, 1.0)
    # a pollster's many polls of the same race share its error → split its weight (√ rule)
    per = df.groupby(["race_id", "pollster"])["w_recency"].transform("sum")
    df["w_frequency"] = 1 / np.sqrt(np.maximum(per / df["w_recency"].clip(lower=1e-9), 1.0))
    df["adj_trend"] = 0.0
    if generic_trend is not None:
        now = generic_trend(as_of_ts)
        df["adj_trend"] = p.trend_beta * (now - df["mid_date"].map(generic_trend))
        df.loc[df["office"] == "generic", "adj_trend"] = 0.0
    df["weight"] = df["w_recency"] * df["w_quality"] * df["w_sponsor"] * df["w_herding"] * df["w_frequency"]
    df["margin_pre_house"] = df["margin"] + df["adj_pop"] + df["adj_sponsor"] + df["adj_trend"]
    return df


def house_effects(df: pd.DataFrame, p: AvgParams, iters: int = 3) -> pd.Series:
    """Current-cycle house effects, shrunk toward each pollster's historical bias (prior sd house_sd)."""
    h = df.groupby("pollster")["hist_bias"].first()
    for _ in range(iters):
        x = df["margin_pre_house"] - df["pollster"].map(h)
        avg = (x * df["weight"]).groupby(df["race_id"]).sum() / df["weight"].groupby(df["race_id"]).sum()
        resid = df["margin_pre_house"] - df["race_id"].map(avg)
        v = df["sv"] + df["tau2"]
        num = (resid / v).groupby(df["pollster"]).sum()
        den = (1 / v).groupby(df["pollster"]).sum()
        prior = df.groupby("pollster")["hist_bias"].first()
        h = (prior / p.house_sd ** 2 + num) / (1 / p.house_sd ** 2 + den)
        h = h - np.average(h, weights=den)  # house effects are relative: centre on the field
    return h


def averages(df: pd.DataFrame, p: AvgParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-race averages, per-poll table with final adjusted margins and weights)."""
    if df.empty:
        return pd.DataFrame(columns=["race_id", "poll_avg", "poll_var", "n_polls", "n_eff", "other_avg"]), df
    h = house_effects(df, p)
    df = df.copy()
    df["adj_house"] = -df["pollster"].map(h).fillna(0.0)
    df["adj_margin"] = df["margin_pre_house"] + df["adj_house"]
    rows = []
    for rid, g in df.groupby("race_id"):
        w = g["weight"].to_numpy()
        if w.sum() <= 0:
            continue
        wn = w / w.sum()
        mean = float(np.sum(wn * g["adj_margin"]))
        var = float(np.sum(wn ** 2 * (g["sv"] + g["tau2"])))
        rows.append(dict(race_id=rid, poll_avg=mean, poll_var=var, n_polls=len(g),
                         n_eff=float(1 / np.sum(wn ** 2)), weight_sum=float(w.sum()),
                         other_avg=float(np.sum(wn * g["other_pct"])),
                         dem_avg=float(np.sum(wn * g["dem_pct"])), rep_avg=float(np.sum(wn * g["rep_pct"]))))
    df["weight_share"] = df["weight"] / df.groupby("race_id")["weight"].transform("sum")
    return pd.DataFrame(rows), df


def generic_trend_fn(polls: pd.DataFrame, ratings, rparams, as_of: dt.date, election: dt.date, p: AvgParams):
    """Smoothed national generic-ballot average as a function of date (for trend adjustment)."""
    g = polls[(polls["office"] == "generic") & (polls["published"] <= pd.Timestamp(as_of))]
    if len(g) < 10:
        return None
    dates = pd.date_range(g["mid_date"].min(), pd.Timestamp(as_of), freq="7D")
    vals = []
    for d in dates:
        adj = adjust(g, ratings, rparams, d.date(), election, p)
        adj = adj[adj["mid_date"] <= d]
        if len(adj) < 3:
            vals.append(np.nan)
            continue
        vals.append(float(np.average(adj["margin_pre_house"], weights=adj["weight"])))
    s = pd.Series(vals, index=dates).interpolate().bfill().ffill()

    def f(ts):
        ts = pd.Timestamp(ts)
        if ts <= s.index[0]:
            return float(s.iloc[0])
        if ts >= s.index[-1]:
            return float(s.iloc[-1])
        return float(np.interp(ts.value, s.index.asi8, s.to_numpy()))
    return f
