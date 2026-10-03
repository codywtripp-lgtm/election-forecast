"""Post-election accuracy scorecard (Phase 3): our final forecast vs. results, and vs. expert ratings.

Activates automatically once 2026 results with vote percentages appear on the Wikipedia cycle pages
(on or after Election Day). Until results are certified the page labels them "unofficial".

Expert ratings are converted to probabilities with a fixed mapping published BEFORE the election
(RATING_PROB below), so the comparison can't be tuned after the fact.

    python -m pipeline.scorecard   → site/static/data/2026/scorecard.json
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DATA, DB, ELECTION_DATE, SITE_DATA

# Probability the Democratic / D-side candidate wins, by rating (published 2026-10-03, never changed after)
RATING_PROB = {
    "solid d": 0.97, "safe d": 0.97, "likely d": 0.85, "lean d": 0.70, "tilt d": 0.60,
    "tossup": 0.50, "toss-up": 0.50, "tilt r": 0.40, "lean r": 0.30, "likely r": 0.15,
    "solid r": 0.03, "safe r": 0.03,
}
FINAL_AS_OF = ELECTION_DATE.isoformat()


def rating_prob(label: str) -> float | None:
    key = str(label).lower().replace("(flip)", "").strip()
    return RATING_PROB.get(key)


def metrics(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    y = np.asarray(y, float)
    return dict(n=int(len(y)), brier=float(np.mean((p - y) ** 2)),
                log_loss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
                correct=int(np.sum((p > 0.5) == (y == 1))), wrong=int(np.sum((p > 0.5) != (y == 1))))


def score(forecast: pd.DataFrame, results: pd.DataFrame, expert: pd.DataFrame | None = None) -> dict:
    """forecast: race_id, office, p_dside, mu, m_q10, m_q90 · results: race_id, margin (D-side − R)."""
    df = forecast.merge(results[["race_id", "margin"]], on="race_id", how="inner")
    df["y"] = (df["margin"] > 0).astype(float)
    out = dict(overall=metrics(df["p_dside"], df["y"]),
               by_office={o: metrics(g["p_dside"], g["y"]) for o, g in df.groupby("office")},
               mae=float(np.mean(np.abs(df["margin"] - df["mu"]))),
               covered80=float(np.mean((df["margin"] >= df["m_q10"]) & (df["margin"] <= df["m_q90"]))))
    df["miss"] = df["margin"] - df["mu"]
    out["misses"] = df.loc[(df["p_dside"] > 0.5) != (df["y"] == 1),
                           ["race_id", "p_dside", "mu", "margin"]].round(3).to_dict(orient="records")
    out["national_miss"] = float(df["miss"].mean())
    if expert is not None and len(expert):
        rows = []
        for rater, g in expert.groupby("rater"):
            g = g.assign(p_exp=g["rating"].map(rating_prob)).dropna(subset=["p_exp"])
            m = g.merge(df[["race_id", "p_dside", "y"]], on="race_id")
            if len(m):
                rows.append(dict(rater=rater, races=int(len(m)), theirs=metrics(m["p_exp"], m["y"]),
                                 ours_same_races=metrics(m["p_dside"], m["y"])))
        out["vs_experts"] = rows
    return out


def final_forecast() -> pd.DataFrame:
    h = pd.read_csv(DATA / "forecasts" / "history.csv")
    h = h[h["as_of"] <= FINAL_AS_OF]
    last = h.sort_values("as_of").groupby("race_id").tail(1)
    last["office"] = last["race_id"].str.split("-").str[1]
    return last


def results_2026() -> pd.DataFrame:
    """2026 results once Wikipedia carries vote percentages (empty before)."""
    from pipeline.house import house_page, parse_house
    from pipeline.normalize.results import fetch_cycle, parse_cycle, summarise
    frames = []
    for office in ("sen", "gov"):
        page = fetch_cycle(office, CYCLE, refresh=True) if dt.date.today() > ELECTION_DATE else {}
        if page:
            r, c = parse_cycle(office, CYCLE, page["html"])
            if r and c:
                frames.append(summarise(pd.DataFrame(r), pd.DataFrame(c)))
    if dt.date.today() > ELECTION_DATE:
        r, c = parse_house(CYCLE, house_page(CYCLE, refresh=True), with_pct=True)
        if len(c):
            frames.append(summarise(r, c))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["race_id", "margin"])


def main() -> None:
    out = dict(cycle=CYCLE, rating_mapping=RATING_PROB, final_as_of=FINAL_AS_OF, status="pending")
    res = results_2026()
    if len(res) >= 50:
        exp_path = DATA / "benchmarks" / "expert_ratings.csv"
        expert = None
        if exp_path.exists():
            e = pd.read_csv(exp_path)
            expert = e.sort_values("fetched").groupby(["race_id", "rater"]).tail(1)   # final rating per rater
        out.update(score(final_forecast(), res, expert), status="unofficial", results_races=int(len(res)))
    path = SITE_DATA / str(CYCLE) / "scorecard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, default=float))
    print(out["status"], out.get("overall"))


if __name__ == "__main__":
    main()
