import pandas as pd
import pytest

from pipeline.config import DB
from pipeline.scorecard import rating_prob, score


def test_rating_mapping():
    assert rating_prob("Lean D (flip)") == 0.70 and rating_prob("Solid R") == 0.03 and rating_prob("Tossup") == 0.5
    assert rating_prob("weird") is None


def test_scorecard_on_2024_backtest_finals():
    """Run the scorecard code path on the 2024 backtest's final forecasts vs. 2024 results."""
    path = DB / "backtest_loco.parquet"
    if not path.exists():
        pytest.skip("needs a local backtest run (pipeline.backtest.calibrate)")
    bt = pd.read_parquet(path)
    f = bt[(bt["cycle"] == 2024) & (bt["days_out"] == 1)].rename(columns={"p": "p_dside"})
    f = f.assign(m_q10=f["mu"] - 1.28 * f["total_sd"], m_q90=f["mu"] + 1.28 * f["total_sd"])
    res = f[["race_id", "margin"]]
    exp = pd.DataFrame({"race_id": f["race_id"].iloc[:5], "rater": "X", "rating": "Tossup"})
    out = score(f[["race_id", "office", "p_dside", "mu", "m_q10", "m_q90"]], res, exp)
    assert out["overall"]["n"] == len(f) and out["overall"]["brier"] < 0.1
    assert 0.6 < out["covered80"] <= 1.0
    assert out["vs_experts"][0]["races"] == 5
