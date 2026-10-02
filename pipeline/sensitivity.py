"""Sensitivity analysis (METHODOLOGY §8): re-run today's forecast under alternative assumptions and
publish how the headline odds move. Smaller simulation count than the daily run; same seed.

    python -m pipeline.sensitivity
Output: data/model/sensitivity.json (committed; shown on the methodology page)
"""
from __future__ import annotations

import datetime as dt
import json

from pipeline.config import MODEL
from pipeline.run import run_forecast

SIMS = 20_000

VARIANTS = [
    ("Baseline (as published)", {}),
    ("Turnout: 2024-like electorate only", {"scenario_weights": [1, 0, 0]}),
    ("Turnout: typical midterm only", {"scenario_weights": [0, 1, 0]}),
    ("Turnout: high-engagement midterm only", {"scenario_weights": [0, 0, 1]}),
    ("Likely-voter shift = 0 (no LV/RV adjustment)", {"lv": (0.0, 0.0)}),
    ("Likely-voter shift = historical midterm value (R+1.45)", {"lv": (-1.45, 0.3)}),
    ("National polling error +25%", {"nat_scale": 1.25}),
    ("National polling error −25%", {"nat_scale": 0.75}),
    ("Demographic error +50%", {"dem_scale": 1.5}),
    ("Fatter tails (ν = 3)", {"df": 3.0}),
    ("Thinner tails (ν = 10)", {"df": 10.0}),
]


def topline(n: dict) -> dict:
    out = dict(senate_dem=n["sen"]["p_dem_control"], senate_rep=n["sen"]["p_rep_control"],
               senate_dem_seats=n["sen"]["dem_seats_mean"], gov_dem=n["gov"]["dem_seats_mean"])
    if "house" in n:
        out.update(house_dem=n["house"]["p_dem_majority"], house_dem_seats=n["house"]["dem_seats_mean"])
    return out


def main() -> None:
    as_of = dt.date.today()
    rows = []
    for label, ov in VARIANTS:
        n = run_forecast(as_of, SIMS, overrides=ov, publish_outputs=False)
        rows.append(dict(variant=label, overrides={k: list(v) if isinstance(v, tuple) else v for k, v in ov.items()},
                         **{k: round(v, 4) for k, v in topline(n).items()}))
        print(label, rows[-1])
    (MODEL / "sensitivity.json").write_text(json.dumps(dict(as_of=as_of.isoformat(), sims=SIMS, rows=rows), indent=1))


if __name__ == "__main__":
    main()
