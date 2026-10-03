"""Blend polls with the fundamentals prior and simulate correlated outcomes (METHODOLOGY §4.3, §6).

Per race r (margin = D-side − Republican, points of the full vote):
    prior    m_prior ~ N(μ_prior, σ_o²)                              race-specific fundamentals error
    polls    m_poll  ~ N(avg, poll_var + σ_rp(t)²)                   sampling + house + race-level poll error
    blend    μ_r = precision-weighted; sd_r = (1/v_prior + 1/v_poll)^-½
Shared errors added in simulation (Student-t, unit variance, ν = df):
    national σ_nat(t) · ε_nat
    region   σ_div(t) · ε_division(r)                                 9 Census divisions
    demog.   σ_dem(t) · Σ_f z_rf ε_f / √F                             Hispanic, Black, white non-college, college
    race     sd_r · ε_r
σ(t) = σ_ed · √(1 + t / T0), t = days to election                     [A23]
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from pipeline.config import DB
from pipeline.model import fundamentals as fund
from pipeline.states import DIVISION

DEMO_FACTORS = ["hispanic", "black", "white_nc", "college"]
DIVISIONS = sorted(set(DIVISION.values()))


@dataclass
class ErrParams:
    nat_ed: float = 2.5     # [A24] national error sd at election day (fit by backtest)
    div_ed: float = 1.5
    dem_ed: float = 1.5
    rp_ed: float = 3.0      # race-level poll-average error sd at election day
    T0: float = 60.0
    df: float = 5.0         # [A22]
    runoff_sd: float = 3.0  # [A28] runoff swing vs general-election margin
    other_sd: float = 1.5   # minor-candidate share uncertainty (majority/runoff rules)

    def scale(self, days: int) -> float:
        return float(np.sqrt(1 + max(days, 0) / self.T0))


REDRAWN_2026 = {"TX", "NC", "OH", "CA", "UT", "FL", "TN", "LA", "AL"}  # ACS districts are on the old lines


def demo_loadings(states: pd.Series, districts: pd.Series | None = None) -> np.ndarray:
    """Standardised demographic shares (z-scores using state-level moments). House districts use
    their own ACS 2024 shares, except in states redrawn for 2026 (the ACS has the old lines),
    which fall back to the state's shares."""
    from pipeline.ingest.census import features  # reads the committed ACS snapshot, no network
    f = features()
    st = f[(f["level"] == "state") & f["state"].notna()].set_index("state")[DEMO_FACTORS]
    mu, sd = st.mean(), st.std()
    out = ((st - mu) / sd).reindex(states).fillna(0.0).to_numpy()
    if districts is None:
        return out
    cd = f[(f["level"] == "cd") & f["state"].notna() & f["district"].notna()]
    z_cd = {(s, int(d)): ((row - mu) / sd).to_numpy()
            for s, d, (_, row) in zip(cd["state"], cd["district"], cd[DEMO_FACTORS].iterrows())}
    for i, (s, d) in enumerate(zip(states, districts)):
        if d is None or pd.isna(d) or s in REDRAWN_2026:
            continue
        # ACS numbers at-large districts 0 (or 98); ours are 1
        key = (s, int(d)) if (s, int(d)) in z_cd else (s, 0)
        if key in z_cd:
            out[i] = z_cd[key]
    return out


def blend(races: pd.DataFrame, avgs: pd.DataFrame, fmodel: dict, N_hat: float, days: int,
          ep: ErrParams) -> pd.DataFrame:
    """races needs: race_id, office, state, lean, inc. Returns prior / poll / blended mean and sd."""
    df = races.merge(avgs, on="race_id", how="left")
    money = df["money"].fillna(0.0) if "money" in df else pd.Series(0.0, index=df.index)
    pri = [fund.predict(fmodel, o, l, N_hat, i, m) for o, l, i, m in zip(df["office"], df["lean"], df["inc"], money)]
    df["prior_mu"] = [p[0] for p in pri]
    df["prior_sd"] = [p[1] for p in pri]
    s = ep.scale(days)
    df["poll_v"] = df["poll_var"] + (ep.rp_ed * s) ** 2
    has = df["poll_avg"].notna()
    vp = df["prior_sd"] ** 2
    w_poll = np.where(has, (1 / df["poll_v"]) / (1 / df["poll_v"] + 1 / vp), 0.0)
    df["poll_weight"] = w_poll
    df["mu"] = np.where(has, w_poll * df["poll_avg"] + (1 - w_poll) * df["prior_mu"], df["prior_mu"])
    df["sd"] = np.where(has, (1 / df["poll_v"] + 1 / vp) ** -0.5, df["prior_sd"])
    return df


def _t(rng, shape, df):
    """Student-t draws rescaled to unit variance."""
    return rng.standard_t(df, size=shape) * np.sqrt((df - 2) / df)


def simulate(tbl: pd.DataFrame, days: int, ep: ErrParams, n_sims: int = 50_000, seed: int = 2026) -> dict:
    """Draw correlated margins. Returns margins (n_sims × races) plus helper arrays."""
    rng = np.random.default_rng(seed)
    R = len(tbl)
    s = ep.scale(days)
    nat = _t(rng, (n_sims, 1), ep.df) * ep.nat_ed * s
    div_idx = np.array([DIVISIONS.index(DIVISION[st]) for st in tbl["state"]])
    div = (_t(rng, (n_sims, len(DIVISIONS)), ep.df) * ep.div_ed * s)[:, div_idx]
    L = demo_loadings(tbl["state"], tbl["district"] if "district" in tbl else None)  # R × F
    dem = (_t(rng, (n_sims, L.shape[1]), ep.df) @ L.T) * ep.dem_ed * s / np.sqrt(L.shape[1])
    race = (_t(rng, (n_sims, R), ep.df) * tbl["sd"].to_numpy()).astype(np.float32)
    margins = tbl["mu"].to_numpy().astype(np.float32) + (nat + div + dem).astype(np.float32) + race
    return dict(margins=margins, national=nat[:, 0], rng=rng)


def outcomes(tbl: pd.DataFrame, sims: dict, ep: ErrParams) -> np.ndarray:
    """D-side wins (bool, n_sims × races), applying majority/runoff rules."""
    m = sims["margins"]
    rng = sims["rng"]
    win = m > 0
    for j, rule in enumerate(tbl["rule"].fillna("plurality")):
        if rule != "majority_runoff":
            continue
        other = np.clip(tbl["other_hat"].iloc[j] + rng.normal(0, ep.other_sd, m.shape[0]), 0, 20)
        d = (100 - other) / 2 + m[:, j] / 2
        r = (100 - other) / 2 - m[:, j] / 2
        runoff = (d <= 50) & (r <= 50)
        rm = m[:, j] + rng.normal(0, ep.runoff_sd, m.shape[0])
        win[:, j] = np.where(runoff, rm > 0, d > 50)
        sims.setdefault("runoff", {})[tbl["race_id"].iloc[j]] = runoff
    return win


def other_hat(tbl: pd.DataFrame) -> pd.Series:
    """Expected minor-candidate share (for majority rules): poll average if available, else 2%."""
    return tbl.get("other_avg", pd.Series(np.nan, index=tbl.index)).clip(lower=0).fillna(2.0)


def race_summary(tbl: pd.DataFrame, sims: dict, win: np.ndarray) -> pd.DataFrame:
    m = sims["margins"]
    q = np.percentile(m, [5, 10, 25, 50, 75, 90, 95], axis=0)
    out = tbl.copy()
    out["p_dside"] = win.mean(axis=0)
    for i, p in enumerate([5, 10, 25, 50, 75, 90, 95]):
        out[f"m_q{p}"] = q[i]
    out["p_runoff"] = [float(sims.get("runoff", {}).get(r, np.zeros(1)).mean()) for r in tbl["race_id"]]
    return out


def params_dict(ep: ErrParams) -> dict:
    return asdict(ep)


def days_to(election: dt.date, as_of: dt.date) -> int:
    return max(0, (election - as_of).days)
