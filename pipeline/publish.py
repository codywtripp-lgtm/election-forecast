"""Write the site's JSON, the run manifest, and append the forecast history.

site/static/data/2026/
  summary.json            national toplines + every race (compact)
  races/<race_id>.json    one race: probabilities, distribution, breakdown, polls with weights + reasons
  polls.json              poll database (all 2026 general-election polls)
  pollsters.json          our pollster ratings
  history.json            forecast over time (toplines + per-race)
  backtest.json           calibration / validation report
  manifests/<run_id>.json provenance
"""
from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DATA, MODEL, RUNS, SITE_DATA

HISTORY = DATA / "forecasts" / "history.csv"
NATIONAL_HISTORY = DATA / "forecasts" / "national_history.csv"


def _clean(x):
    """JSON-safe: NaN → None, numpy → python, round floats."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(x) or math.isinf(x) else round(float(x), 4)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.date().isoformat()
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    if x is pd.NA or x is pd.NaT:
        return None
    return x


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def weight_reasons(p: pd.Series) -> list[str]:
    """Plain-language reasons a poll's weight is what it is."""
    out = []
    if p["w_recency"] < 0.5:
        out.append(f"older poll ({int(p['age'])} days)")
    if not p["rated"]:
        out.append("pollster has no track record in our ratings")
    elif p["tau2"] <= 2.0:
        out.append("strong pollster track record")
    elif p["tau2"] >= 8.0:
        out.append("weak pollster track record")
    if p["w_sponsor"] < 1:
        out.append("partisan or campaign sponsor (half weight)")
    if p["w_herding"] < 1:
        out.append("pollster's results cluster suspiciously near the average")
    if p["w_frequency"] < 0.75:
        out.append("pollster has several recent polls of this race (weight shared)")
    if p["population"] in ("rv", "a"):
        out.append({"rv": "registered voters, shifted to likely-voter basis",
                    "a": "all adults, shifted to likely-voter basis"}[p["population"]])
    if abs(p.get("adj_house", 0)) >= 1:
        out.append(f"house effect correction {p['adj_house']:+.1f}")
    return out


def breakdown(r: pd.Series, coef: dict, N_hat: float) -> dict:
    """What drives the forecast: fundamentals terms, polls, and how they are blended."""
    c = coef[r["office"]]["coef"]
    return dict(
        fundamentals=dict(constant=c["const"], partisan_lean=c["lean"] * r["lean"],
                          national_environment=c["N"] * N_hat, incumbency=c["inc"] * r["inc"],
                          total=r["prior_mu"], sd=r["prior_sd"]),
        polls=dict(average=r.get("poll_avg"), n_polls=r.get("n_polls"), effective_n=r.get("n_eff"),
                   sd=None if pd.isna(r.get("poll_v")) else float(np.sqrt(r["poll_v"]))),
        blend=dict(poll_weight=r["poll_weight"], margin=r["mu"], sd=r["sd"]),
    )


def publish(run_id: str, manifest: dict, tbl: pd.DataFrame, national: dict, poll_table: pd.DataFrame,
            ratings: pd.DataFrame, avgs: pd.DataFrame, cands: pd.DataFrame) -> None:
    out = SITE_DATA / str(CYCLE)
    coef = manifest["fundamentals"]
    N_hat = manifest["N_hat"]
    updated = manifest["created_utc"]

    # ---- per-race files
    pt = poll_table.copy()
    races_compact = []
    for _, r in tbl.iterrows():
        rp = pt[pt["race_id"] == r["race_id"]].sort_values("end_date", ascending=False)
        polls = [dict(pollster=p["pollster"], sponsors=p["sponsors"], start=p["start_date"], end=p["end_date"],
                      n=p["sample_size"], population=p["population"], mode=p["mode"], partisan=p["partisan"],
                      dem=p["dem_pct"], rep=p["rep_pct"], margin_raw=p["margin"] - p.get("adj_rcv", 0.0),
                      adj=dict(population=p["adj_pop"], sponsor=p["adj_sponsor"], house=p["adj_house"],
                               trend=p["adj_trend"], rcv=p.get("adj_rcv", 0.0)),
                      margin_adj=p["adj_margin"], weight=p["weight_share"], reasons=weight_reasons(p),
                      url=p["url"])
                 for _, p in rp.iterrows()]
        others = cands[(cands["race_id"] == r["race_id"]) & ~cands["candidate_id"].isin([r["d_cid"], r["r_cid"]])]
        race = dict(
            race_id=r["race_id"], office=r["office"], state=r["state"], special=r["special"], rule=r["rule"],
            rule_verified=r["rule_verified"], incumbent=r["incumbent"], incumbent_party=r["incumbent_party"],
            d_side=dict(id=r["d_cid"], name=r["d_name"], party=r["d_party"]),
            rep=dict(id=r["r_cid"], name=r["r_name"], party="REP"),
            other_candidates=others[["name", "party_label"]].to_dict(orient="records"),
            p_dside=r["p_dside"], p_rep=1 - r["p_dside"], p_runoff=r["p_runoff"],
            margin=dict(mean=r["mu"], **{f"q{p}": r[f"m_q{p}"] for p in (5, 10, 25, 50, 75, 90, 95)}),
            margin_hist=r["hist"], p_by_scenario=r["p_dside_by_scenario"],
            breakdown=breakdown(r, coef, N_hat), polls=polls, run_id=run_id, updated=updated)
        _write(out / "races" / f"{r['race_id']}.json", race)
        races_compact.append(dict(id=r["race_id"], office=r["office"], state=r["state"], special=r["special"],
                                  d=r["d_name"], d_party=r["d_party"], r=r["r_name"], p=r["p_dside"],
                                  mu=r["mu"], q10=r["m_q10"], q90=r["m_q90"], poll_weight=r["poll_weight"],
                                  n_polls=0 if pd.isna(r.get("n_polls")) else int(r["n_polls"]),
                                  rule=r["rule"], p_runoff=r["p_runoff"], incumbent_party=r["incumbent_party"]))

    gen = avgs.set_index("race_id").loc[f"{CYCLE}-generic"]
    summary = dict(run_id=run_id, updated=updated, as_of=manifest["as_of"],
                   days_to_election=manifest["days_to_election"], election_date="2026-11-03",
                   n_sims=manifest["n_sims"], national=national,
                   generic_ballot=dict(margin=N_hat, dem=gen["dem_avg"], rep=gen["rep_avg"], n_polls=gen["n_polls"]),
                   scenarios=manifest["scenarios"], races=races_compact,
                   placeholders=[], attribution=["Polls: VoteHub (CC BY 4.0), 538 archive (CC BY 4.0), Wikipedia (CC BY-SA 4.0)",
                                                 "Results: MIT Election Data + Science Lab (CC0), Wikipedia"])
    _write(out / "summary.json", summary)

    # ---- poll database
    db = pt.sort_values("end_date", ascending=False)
    _write(out / "polls.json", [dict(race=p["race_id"], office=p["office"], state=p["state"], pollster=p["pollster"],
                                     sponsors=p["sponsors"], partisan=p["partisan"], start=p["start_date"],
                                     end=p["end_date"], n=p["sample_size"], pop=p["population"], mode=p["mode"],
                                     dem=p["dem_pct"], rep=p["rep_pct"], margin=p["margin"],
                                     adj=p["adj_margin"], w=p["weight_share"], url=p["url"])
                                for _, p in db.iterrows()])
    _write(out / "pollsters.json", ratings[["pollster", "n", "bias", "tau2", "herd_ratio", "herding", "group",
                                            "last_cycle", "mode"]].to_dict(orient="records"))
    report = MODEL / "backtest_report.json"
    if report.exists():
        _write(out / "backtest.json", json.loads(report.read_text()))

    # ---- history (committed CSV) → history.json
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    rows = tbl[["race_id", "p_dside", "mu", "m_q10", "m_q90"]].assign(run_id=run_id, as_of=manifest["as_of"])
    hist = pd.concat([pd.read_csv(HISTORY), rows]) if HISTORY.exists() else rows
    hist = hist.drop_duplicates(["as_of", "race_id"], keep="last")
    hist.to_csv(HISTORY, index=False)
    nat_row = pd.DataFrame([dict(as_of=manifest["as_of"], run_id=run_id,
                                 sen_p_rep=national["sen"]["p_rep_control"], sen_p_dem=national["sen"]["p_dem_control"],
                                 sen_dem_seats=national["sen"]["dem_seats_mean"],
                                 gov_dem_mean=national["gov"]["dem_seats_mean"], generic=N_hat)])
    nh = pd.concat([pd.read_csv(NATIONAL_HISTORY), nat_row]) if NATIONAL_HISTORY.exists() else nat_row
    nh = nh.drop_duplicates(["as_of"], keep="last")
    nh.to_csv(NATIONAL_HISTORY, index=False)
    _write(out / "history.json", dict(national=nh.to_dict(orient="records"),
                                      races={rid: g[["as_of", "p_dside", "mu", "m_q10", "m_q90"]].to_dict(orient="list")
                                             for rid, g in hist.groupby("race_id")}))

    # ---- manifest
    (RUNS / run_id).mkdir(parents=True, exist_ok=True)
    (RUNS / run_id / "manifest.json").write_text(json.dumps(_clean(manifest), indent=1))
    _write(out / "manifests" / f"{run_id}.json", manifest)
