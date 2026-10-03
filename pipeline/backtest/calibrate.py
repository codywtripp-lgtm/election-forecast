"""Fit the error structure (ErrParams) to backtest residuals, then score calibrated forecasts.

Errors e = truth − μ for all races in one (cycle, days-out) replay are jointly Gaussian (t-tails are
applied in simulation, ν fixed separately):

    Σ = diag(sd_r²) + s(t)²·(σ_nat² J + σ_div² D Dᵀ + σ_dem²/F · L Lᵀ)

σ_nat, σ_div, σ_dem, T0 are fit by maximum likelihood; σ_rp (race-level poll error, which also sets
the poll weight) is chosen on a grid by the same likelihood. Scores (Brier, log loss, calibration,
interval coverage) are computed leave-one-cycle-out: the error parameters used to score cycle C are
fit without C.
"""
from __future__ import annotations

import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import t as student_t

from pipeline.config import DB, MODEL
from pipeline.model.forecast import DIVISIONS, ErrParams, demo_loadings
from pipeline.states import DIVISION

RP_GRID = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)


def reblend(bt: pd.DataFrame, rp_ed: float, T0: float) -> pd.DataFrame:
    bt = bt.copy()
    s2 = 1 + bt["days_out"] / T0
    poll_v = bt["poll_var"] + rp_ed ** 2 * s2
    vp = bt["prior_sd"] ** 2
    has = bt["poll_avg"].notna()
    w = np.where(has, (1 / poll_v) / (1 / poll_v + 1 / vp), 0.0)
    bt["poll_weight"] = w
    bt["mu"] = np.where(has, w * bt["poll_avg"] + (1 - w) * bt["prior_mu"], bt["prior_mu"])
    bt["sd"] = np.where(has, (1 / poll_v + 1 / vp) ** -0.5, bt["prior_sd"])
    return bt


def _groups(bt: pd.DataFrame):
    for (_, _), g in bt.groupby(["cycle", "days_out"]):
        div = np.array([DIVISIONS.index(DIVISION[s]) for s in g["state"]])
        D = np.eye(len(DIVISIONS))[div]
        L = demo_loadings(g["state"])
        # plain numpy only inside the optimiser loop (pandas arithmetic there crashed on Windows)
        arrs = dict(days=float(g["days_out"].iloc[0]), sd2=g["sd"].to_numpy(float) ** 2,
                    e=(g["margin"].to_numpy(float) - g["mu"].to_numpy(float)))
        yield arrs, D @ D.T, L @ L.T / L.shape[1]


def neg_loglik(theta, groups, T0):
    nat, div, dem = np.exp(theta)
    total = 0.0
    for g, DD, LL in groups:
        s2 = 1 + g["days"] / T0
        S = np.diag(g["sd2"]) + s2 * (nat ** 2 + div ** 2 * DD + dem ** 2 * LL)
        e = g["e"]
        sign, logdet = np.linalg.slogdet(S)
        total += 0.5 * (logdet + e @ np.linalg.solve(S, e))
    return total


def fit_errors(bt: pd.DataFrame, base: ErrParams | None = None) -> tuple[ErrParams, float]:
    base = base or ErrParams()
    best = None
    for T0 in (30.0, 60.0, 120.0):
        for rp in RP_GRID:
            b = reblend(bt, rp, T0)
            groups = list(_groups(b))
            res = minimize(neg_loglik, x0=np.log([2.5, 1.5, 1.5]), args=(groups, T0), method="Nelder-Mead",
                           options=dict(maxiter=400, xatol=1e-3, fatol=1e-3))
            if best is None or res.fun < best[0]:
                nat, div, dem = np.exp(res.x)
                best = (res.fun, replace(base, nat_ed=float(nat), div_ed=float(div), dem_ed=float(dem),
                                         rp_ed=rp, T0=T0))
    return best[1], best[0]


def win_prob(bt: pd.DataFrame, ep: ErrParams) -> np.ndarray:
    """Marginal P(D-side wins), Student-t with the total marginal sd (shared + race)."""
    s2 = 1 + bt["days_out"] / ep.T0
    L = demo_loadings(bt["state"])
    dem_var = (L ** 2).sum(axis=1) / L.shape[1]
    total = np.sqrt(bt["sd"] ** 2 + s2 * (ep.nat_ed ** 2 + ep.div_ed ** 2 + ep.dem_ed ** 2 * dem_var))
    scale = total * np.sqrt((ep.df - 2) / ep.df)
    return student_t.cdf(bt["mu"] / scale, ep.df), total


def score(bt: pd.DataFrame, p: np.ndarray, total_sd) -> dict:
    y = (bt["margin"] > 0).astype(float).to_numpy()
    p = np.clip(p, 1e-4, 1 - 1e-4)
    z80 = 1.2816
    inside = np.abs(bt["margin"] - bt["mu"]) <= z80 * total_sd
    return dict(n=len(y), brier=float(np.mean((p - y) ** 2)),
                log_loss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
                accuracy=float(np.mean((p > 0.5) == (y == 1))),
                coverage80=float(np.mean(inside)), mae=float(np.mean(np.abs(bt["margin"] - bt["mu"]))))


def calibration_bins(y, p, bins=(0, .05, .15, .25, .35, .45, .55, .65, .75, .85, .95, 1.0001)):
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.cut(df["p"], bins, right=False)
    g = df.groupby("bin", observed=True).agg(predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size"))
    return g.reset_index(drop=True)


def loco(bt: pd.DataFrame) -> pd.DataFrame:
    """Leave-one-cycle-out: fit error params without cycle C, score C."""
    rows = []
    for c in sorted(bt["cycle"].unique()):
        ep, _ = fit_errors(bt[bt["cycle"] != c])
        b = reblend(bt[bt["cycle"] == c], ep.rp_ed, ep.T0)
        p, tot = win_prob(b, ep)
        b = b.assign(p=p, total_sd=tot, rp_ed=ep.rp_ed, nat_ed=ep.nat_ed)
        rows.append(b)
    return pd.concat(rows, ignore_index=True)


def baselines(bt: pd.DataFrame, ep: ErrParams) -> dict:
    """Polls-only (where polls exist) and fundamentals-only, same error structure."""
    out = {}
    b = reblend(bt, ep.rp_ed, ep.T0)
    p, tot = win_prob(b, ep)
    out["model"] = score(b, p, tot)
    pol = b[b["poll_avg"].notna()].copy()
    pol["mu"], pol["sd"] = pol["poll_avg"], np.sqrt(pol["poll_var"] + ep.rp_ed ** 2 * (1 + pol["days_out"] / ep.T0))
    p, tot = win_prob(pol, ep)
    out["polls_only (polled races)"] = score(pol, p, tot)
    out["model (polled races)"] = score(b[b["poll_avg"].notna()], *win_prob(b[b["poll_avg"].notna()], ep))
    fun = b.copy()
    fun["mu"], fun["sd"] = fun["prior_mu"], fun["prior_sd"]
    p, tot = win_prob(fun, ep)
    out["fundamentals_only"] = score(fun, p, tot)
    return out


def main() -> None:
    bt = pd.read_parquet(DB / "backtest_replay.parquet")
    ep, nll = fit_errors(bt)
    print("fitted", asdict(ep), round(nll, 1))
    cv = loco(bt)
    by_days = {int(d): score(g, g["p"].to_numpy(), g["total_sd"]) for d, g in cv.groupby("days_out")}
    by_cycle = {int(c): score(g, g["p"].to_numpy(), g["total_sd"]) for c, g in cv[cv["days_out"] == 1].groupby("cycle")}
    cal = calibration_bins((cv["margin"] > 0).astype(float), cv["p"])
    report = dict(error_params=asdict(ep), loco_by_days_out=by_days, loco_final_by_cycle=by_cycle,
                  calibration=cal.round(3).to_dict(orient="records"), baselines=baselines(bt, ep))
    (DB / "backtest_report.json").write_text(json.dumps(report, indent=1))
    # versioned, committed: the daily run reads these calibrated parameters
    (MODEL / "error_params.json").write_text(json.dumps(asdict(ep), indent=1))
    (MODEL / "backtest_report.json").write_text(json.dumps(report, indent=1))
    cv.to_parquet(DB / "backtest_loco.parquet", index=False)
    print(json.dumps({k: report[k] for k in ("loco_by_days_out", "baselines")}, indent=1))
    print(cal.round(3).to_string())


if __name__ == "__main__":
    main()
