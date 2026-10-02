"""Daily 2026 forecast run: polls + fundamentals → simulations → site JSON + run manifest.

    python -m pipeline.run [--as-of YYYY-MM-DD] [--sims 50000]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from dataclasses import asdict

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DATA, DB, ELECTION_DATE, MANUAL, MODEL, RAW, RUNS, SITE_DATA
from pipeline.model import fundamentals as fund
from pipeline.model import pollster_ratings as pr
from pipeline.model.average import AvgParams, adjust, averages, generic_trend_fn, lv_shift, poll_frame
from pipeline.model.data import choose_d_side, choose_r_side, state_lean
from pipeline.model.forecast import ErrParams, blend, days_to, other_hat, outcomes, simulate
from pipeline.model.turnout import SCENARIOS, scenario_shifts

RCV_TRANSFER = 0.75   # [A25] net share of a same-party minor candidate's votes reaching their party's leader


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def house_lean_2026() -> dict:
    hl = pd.read_parquet(DB / "house_lean.parquet")
    hl = hl[hl["cycle"] == CYCLE]
    return {(r.state, int(r.district)): float(r.lean) for r in hl.itertuples()}


def fixed_outcome(office: str, rule: str, g: pd.DataFrame, dcid: str | None, rcid: str | None) -> str | None:
    """Races whose winning side is already certain: no Republican on the ballot, no D-side
    (Democrat or independent) on the ballot, or a same-party top-two general (CA/WA)."""
    parties = set(g["party"])
    if rule == "top_two" and len(g) == 2 and len(parties) == 1:
        return "D" if parties == {"DEM"} else ("R" if parties == {"REP"} else None)
    d_party = g.set_index("candidate_id")["party"].get(dcid) if dcid else None
    if rcid is None and d_party in ("DEM", "IND"):
        return "D"
    if rcid is not None and d_party not in ("DEM", "IND"):
        return "R"
    return None


def race_table(races: pd.DataFrame, cands: pd.DataFrame, d_side: dict, r_side: dict) -> pd.DataFrame:
    by_id = cands.set_index("candidate_id")
    hlean = house_lean_2026() if (races["office"] == "house").any() else {}
    rows = []
    for r in races.itertuples():
        g = cands[cands["race_id"] == r.race_id]
        dcid = d_side.get(r.race_id)
        rcid = r_side.get(r.race_id)
        inc_cand = g[g["incumbent"]]
        inc = 0
        if len(inc_cand):
            inc = -1 if inc_cand["party"].iloc[0] == "REP" else (1 if inc_cand["candidate_id"].iloc[0] == dcid else 0)
        district = getattr(r, "district", None)
        district = None if district is None or pd.isna(district) else int(district)
        lean = hlean.get((r.state, district), np.nan) if r.office == "house" else state_lean(CYCLE, r.state)
        rows.append(dict(race_id=r.race_id, office=r.office, state=r.state, district=district, special=r.special,
                         rule=r.rule, rule_verified=r.rule_verified, incumbent=r.incumbent,
                         incumbent_party=r.incumbent_party, inc=inc, lean=lean,
                         fixed=fixed_outcome(r.office, r.rule, g, dcid, rcid),
                         d_cid=dcid, d_name=by_id.loc[dcid, "name"] if dcid else None,
                         d_party=by_id.loc[dcid, "party"] if dcid else None,
                         r_cid=rcid, r_name=by_id.loc[rcid, "name"] if rcid else None))
    return pd.DataFrame(rows)


def rcv_adjust(polls: pd.DataFrame, rcv_races: set) -> pd.DataFrame:
    """For RCV races, estimate final-round margin: same-party minor candidates transfer to their leader."""
    polls = polls.copy()
    mask = polls["race_id"].isin(rcv_races)
    polls["adj_rcv"] = np.where(mask, RCV_TRANSFER * (polls["other_dem"] - polls["other_rep"]), 0.0)
    polls["margin"] = polls["margin"] + polls["adj_rcv"]
    return polls


MAJORITY = {"sen": None, "gov": 26, "house": 218}


def chamber(tbl: pd.DataFrame, win: np.ndarray, holdovers: pd.DataFrame, rng, office: str,
            caucus: dict) -> dict:
    idx = np.where(tbl["office"].to_numpy() == office)[0]
    t = tbl.iloc[idx]
    w = win[:, idx]
    n = w.shape[0]
    h = holdovers[holdovers["office"] == office]
    hold_d = int((h["caucus"] == "DEM").sum())
    hold_r = int((h["caucus"] == "REP").sum())
    # independents on the D side: caucus draw per simulation
    is_ind = (t["d_party"] != "DEM").to_numpy()
    p_dem = np.array([caucus.get(c, 0.5) for c in t["d_cid"]])
    caucus_d = rng.random((n, len(t))) < p_dem
    d_seats = hold_d + (w & (~is_ind | caucus_d)).sum(axis=1)
    r_seats = hold_r + (~w).sum(axis=1)
    ind_out = (w & is_ind & ~caucus_d).sum(axis=1)
    res = dict(holdover_dem=hold_d, holdover_rep=hold_r, seats_up=len(t),
               dem_seats_mean=float(d_seats.mean()), rep_seats_mean=float(r_seats.mean()),
               dem_seats_hist={int(k): int(v) for k, v in zip(*np.unique(d_seats, return_counts=True))},
               rep_seats_hist={int(k): int(v) for k, v in zip(*np.unique(r_seats, return_counts=True))})
    if office == "sen":
        rep_control = r_seats >= 50          # Republican VP breaks ties
        dem_control = d_seats >= 51
        res.update(p_rep_control=float(rep_control.mean()), p_dem_control=float(dem_control.mean()),
                   p_independents_decide=float((~rep_control & ~dem_control).mean()),
                   p_any_independent_wins=float((w & is_ind).any(axis=1).mean()))
    else:
        maj = MAJORITY[office]
        res.update(p_dem_majority=float((d_seats >= maj).mean()), p_rep_majority=float((r_seats >= maj).mean()),
                   majority=maj)
    return res


def tipping_from_margins(t: pd.DataFrame, m: np.ndarray, w: np.ndarray, hold_d: int, hold_r: int,
                         is_ind: np.ndarray, caucus_d: np.ndarray, rep_need: int = 50, dem_need: int = 51) -> pd.Series:
    n, R = m.shape
    counts = np.zeros(R)
    counts_d = (w & (~is_ind | caucus_d))
    r_seats = hold_r + (~w).sum(axis=1)
    d_seats = hold_d + counts_d.sum(axis=1)
    for k in range(n):
        if r_seats[k] >= rep_need:
            order = np.argsort(m[k])                # most Republican first
            need = rep_need - hold_r
            cum = np.cumsum(~w[k][order])
        elif d_seats[k] >= dem_need:
            order = np.argsort(-m[k])               # most D-side first
            need = dem_need - hold_d
            cum = np.cumsum(counts_d[k][order])
        else:
            continue
        pos = int(np.searchsorted(cum, need))
        if need <= 0 or pos >= R:
            continue
        counts[order[pos]] += 1
    return pd.Series(counts / max(1, counts.sum()), index=t["race_id"])


def main() -> None:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--as-of", default=None)
    ap_.add_argument("--sims", type=int, default=50_000)
    args = ap_.parse_args()
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    national = run_forecast(as_of, args.sims)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk.startswith("p_") or kk.endswith("_mean")}
                      for k, v in national.items() if isinstance(v, dict)}, indent=1))


def run_forecast(as_of: dt.date, sims_n: int, overrides: dict | None = None, publish_outputs: bool = True) -> dict:
    """The whole daily forecast. `overrides` (sensitivity runs only) can set:
    lv=(mean, sd), nat_scale, dem_scale, df, scenario_weights=[w1, w2, w3]."""
    ov = overrides or {}

    class _A:  # keep the body below unchanged: it refers to args.sims
        sims = sims_n
    args = _A()
    E = ELECTION_DATE
    days = days_to(E, as_of)

    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    races = pd.read_parquet(DB / "races.parquet")
    cands = pd.read_parquet(DB / "candidates.parquet")
    if (DB / "house_races.parquet").exists():
        races = pd.concat([races, pd.read_parquet(DB / "house_races.parquet")], ignore_index=True)
        cands = pd.concat([cands, pd.read_parquet(DB / "house_candidates.parquet")], ignore_index=True)
    holdovers = pd.read_parquet(DB / "holdovers.parquet")
    caucus = pd.read_csv(MANUAL / "caucus.csv").set_index("candidate_id")["p_caucus_dem"].to_dict()

    ratings, rparams = pr.fit()
    fmodel = fund.fit()
    ep = ErrParams(**json.loads((MODEL / "error_params.json").read_text()))
    if "nat_scale" in ov:
        ep.nat_ed *= ov["nat_scale"]
    if "dem_scale" in ov:
        ep.dem_ed *= ov["dem_scale"]
    if "df" in ov:
        ep.df = ov["df"]
    ap = AvgParams()

    d_side = choose_d_side(q, a, cands)
    tbl = race_table(races, cands, d_side, choose_r_side(q, a, cands))
    polls = poll_frame(q[q["cycle"] == CYCLE], a, d_side=d_side)
    polls = rcv_adjust(polls, set(tbl.loc[tbl["rule"].isin(["rcv", "top4_rcv"]), "race_id"]))
    lv = ov.get("lv", lv_shift(polls, ap))
    gt = generic_trend_fn(polls, ratings, rparams, as_of, E, ap)
    from pipeline.model.weighting import estimate as estimate_delta
    delta = estimate_delta()
    adj = adjust(polls, ratings, rparams, as_of, E, ap, gt, lv, delta=delta)
    avgs, poll_table = averages(adj, ap)
    gen = avgs.set_index("race_id").loc[f"{CYCLE}-generic"]
    N_hat = float(gen["poll_avg"])

    tbl = blend(tbl, avgs, fmodel, N_hat, days, ep)
    tbl["other_hat"] = other_hat(tbl)
    # certain outcomes: one side is not on the ballot, so the margin is not modeled
    fixed = tbl["fixed"].to_numpy()
    tbl.loc[tbl["fixed"].notna(), "poll_weight"] = 0.0

    # turnout scenarios: each simulation draws one; shift applied to its margins  [A19, A20]
    shifts, probs, scen_meta = scenario_shifts(lv)
    if "scenario_weights" in ov:
        probs = list(ov["scenario_weights"])
    sims = simulate(tbl, days, ep, n_sims=args.sims, seed=int(as_of.strftime("%Y%m%d")))
    rng = sims["rng"]
    scen = rng.choice(len(SCENARIOS), size=args.sims, p=probs)
    sims["margins"] = sims["margins"] + np.asarray(shifts)[scen][:, None]
    win = outcomes(tbl, sims, ep)
    for j in np.where(pd.notna(fixed))[0]:
        win[:, j] = fixed[j] == "D"

    m = sims["margins"]
    tbl["p_dside"] = win.mean(axis=0)
    for p in (5, 10, 25, 50, 75, 90, 95):
        tbl[f"m_q{p}"] = np.percentile(m, p, axis=0)
    bins = np.arange(-60, 62, 2)
    tbl["hist"] = [np.histogram(np.clip(m[:, j], -59.9, 59.9), bins=bins)[0].tolist() for j in range(m.shape[1])]
    tbl["p_runoff"] = [float(sims.get("runoff", {}).get(r, np.zeros(1)).mean()) for r in tbl["race_id"]]
    tbl["p_dside_by_scenario"] = [
        {s["key"]: float(win[scen == i, j].mean()) for i, s in enumerate(SCENARIOS)} for j in range(len(tbl))]

    national = {}
    offices = [o for o in ("sen", "gov", "house") if (tbl["office"] == o).any()]
    for office in offices:
        national[office] = chamber(tbl, win, holdovers, rng, office, caucus)
        national[office]["by_scenario"] = {
            s["key"]: chamber(tbl, win[scen == i], holdovers, np.random.default_rng(i), office, caucus)
            for i, s in enumerate(SCENARIOS) if (scen == i).any()}
        for v in national[office]["by_scenario"].values():
            v.pop("dem_seats_hist", None), v.pop("rep_seats_hist", None)
    sen_idx = np.where(tbl["office"] == "sen")[0]
    t_sen = tbl.iloc[sen_idx]
    is_ind = (t_sen["d_party"] != "DEM").to_numpy()
    caucus_d = rng.random((args.sims, len(t_sen))) < np.array([caucus.get(c, 0.5) for c in t_sen["d_cid"]])
    h = holdovers[holdovers["office"] == "sen"]
    tp = tipping_from_margins(t_sen, m[:, sen_idx], win[:, sen_idx], int((h["caucus"] == "DEM").sum()),
                              int((h["caucus"] == "REP").sum()), is_ind, caucus_d)
    national["sen"]["tipping_point"] = tp.sort_values(ascending=False).head(10).round(4).to_dict()
    if "house" in national:
        hi = np.where(tbl["office"] == "house")[0]
        th = tbl.iloc[hi]
        tp_h = tipping_from_margins(th, m[:, hi], win[:, hi], 0, 0, (th["d_party"] != "DEM").to_numpy(),
                                    np.zeros((args.sims, len(th)), bool), rep_need=218, dem_need=218)
        national["house"]["tipping_point"] = tp_h.sort_values(ascending=False).head(10).round(4).to_dict()

    if not publish_outputs:
        return national

    # 400 stored draws for the site's "simulate one election" button
    k = min(400, args.sims)
    samples = dict(race_ids=tbl["race_id"].tolist(),
                   dside_wins=["".join("1" if x else "0" for x in win[:k, j]) for j in range(len(tbl))],
                   scenario=scen[:k].tolist())
    national["samples"] = samples

    from pipeline.publish import publish
    run_id = f"{as_of.isoformat()}-{git_sha()[:7]}"
    inputs = sorted(p for p in (RAW).rglob("*.gz")) + sorted(MANUAL.glob("*.csv")) + sorted(MODEL.glob("*.json"))
    manifest = dict(run_id=run_id, as_of=as_of.isoformat(), days_to_election=days, code_sha=git_sha(),
                    created_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    n_sims=args.sims, seed=int(as_of.strftime("%Y%m%d")),
                    error_params=asdict(ep), avg_params=asdict(ap), lv_shift=dict(mean=lv[0], sd=lv[1]),
                    N_hat=N_hat, scenarios=scen_meta, fundamentals=fmodel, ratings_params=rparams,
                    weighting_correction=delta,
                    inputs={str(p.relative_to(DATA.parent)).replace("\\", "/"): sha256(p) for p in inputs})
    publish(run_id, manifest, tbl, national, poll_table, ratings, avgs, cands)
    return national


if __name__ == "__main__":
    main()
