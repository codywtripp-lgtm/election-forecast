"""Trump net approval by state — an ESTIMATE, labelled as such on the site.

    state net approval ≈ national net approval (our average, same date) + b · state lean + u_state

b (how strongly approval follows partisanship) and u_state (a state's own deviation) are estimated from
statewide approval polls (Wikipedia's tables, 2025–26). b has a prior N(−1.0, 0.3²): approval of a
president tracks the presidential vote roughly one-for-one. u_state is shrunk toward 0 by how many
polls the state has; states with no polls get u = 0 and a wider uncertainty.

Output: site/static/data/2026/approval_states.json
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DB, SITE_DATA
from pipeline.model.data import state_lean_table
from pipeline.states import STATES

B_PRIOR, B_PRIOR_SD = -1.0, 0.3
TAU_STATE = 4.0        # prior s.d. of a state's own deviation (points of net approval)
POLL_SD = 6.0          # s.d. of one state poll around the state's true value (sampling + house + timing)


def national_series() -> pd.Series:
    t = json.loads((SITE_DATA / str(CYCLE) / "trackers.json").read_text())
    s = pd.Series({pd.Timestamp(p["date"]): p["value"] for p in t["approval"]}).sort_index()
    return s


def nat_at(series: pd.Series, d) -> float:
    d = pd.Timestamp(d)
    return float(np.interp(d.value, series.index.asi8, series.to_numpy()))


def fit(polls: pd.DataFrame, lean: dict, series: pd.Series) -> dict:
    p = polls.copy()
    p["nat"] = [nat_at(series, d) for d in p["end_date"]]
    p["y"] = p["net"] - p["nat"]
    p["lean"] = p["state"].map(lean)
    p = p.dropna(subset=["lean"])
    x, y = p["lean"].to_numpy(), p["y"].to_numpy()
    # b: Bayesian regression through the origin, noise var = POLL_SD² + TAU_STATE²
    v = POLL_SD ** 2 + TAU_STATE ** 2
    prec = 1 / B_PRIOR_SD ** 2 + (x @ x) / v
    b = (B_PRIOR / B_PRIOR_SD ** 2 + (x @ y) / v) / prec
    b_sd = prec ** -0.5
    p["resid"] = p["y"] - b * p["lean"]
    u = {}
    for st, g in p.groupby("state"):
        w = len(g) / POLL_SD ** 2
        post_var = 1 / (1 / TAU_STATE ** 2 + w)
        u[st] = dict(u=float(post_var * w * g["resid"].mean()), sd=float(np.sqrt(post_var)), n=int(len(g)))
    return dict(b=float(b), b_sd=float(b_sd), n_polls=int(len(p)), n_states=int(p["state"].nunique()),
                resid_sd=float(p["resid"].std()), u=u)


def main() -> None:
    polls = pd.read_parquet(DB / "state_approval_polls.parquet")
    lt = state_lean_table()
    lean = lt[lt["cycle"] == CYCLE].set_index("state")["lean"].to_dict()
    series = national_series()
    f = fit(polls, lean, series)
    nat_now = float(series.iloc[-1])
    rows = []
    for name, ab, *_ in STATES:
        if ab == "DC" or ab not in lean:
            continue
        uu = f["u"].get(ab, dict(u=0.0, sd=TAU_STATE, n=0))
        est = nat_now + f["b"] * lean[ab] + uu["u"]
        sd = float(np.sqrt(uu["sd"] ** 2 + (f["b_sd"] * lean[ab]) ** 2))
        latest = polls[polls["state"] == ab].sort_values("end_date").tail(1)
        rows.append(dict(state=ab, net=round(est, 1), sd=round(sd, 1), n_polls=uu["n"],
                         latest_poll=None if latest.empty else dict(
                             pollster=latest["pollster"].iloc[0], end=str(latest["end_date"].iloc[0]),
                             net=float(latest["net"].iloc[0]))))
    out = dict(as_of=dt.date.today().isoformat(), national_net=round(nat_now, 1), fit=dict(
        b=round(f["b"], 3), b_sd=round(f["b_sd"], 3), n_polls=f["n_polls"], n_states=f["n_states"],
        resid_sd=round(f["resid_sd"], 2)), states=rows,
        method="Estimate: national net approval + b × state partisan lean + the state's own deviation from its "
               "polls (shrunk toward zero). States without polls rely on partisanship alone.")
    (SITE_DATA / str(CYCLE) / "approval_states.json").write_text(json.dumps(out))
    print(out["fit"], "national", nat_now)
    print(sorted([(r["state"], r["net"]) for r in rows], key=lambda x: x[1])[:5], "...",
          sorted([(r["state"], r["net"]) for r in rows], key=lambda x: x[1])[-5:])


if __name__ == "__main__":
    main()
