import pandas as pd
import pytest

from pipeline.approval_map import fit
from pipeline.ingest.approval_states import _end_date
from pipeline.mood import mood_block


def test_end_date_parsing():
    assert str(_end_date("April 28–May 3, 2025").date()) == "2025-05-03"
    assert str(_end_date("September 24-28").date()) == "2026-09-28"


def test_state_fit_recovers_partisan_slope():
    series = pd.Series({pd.Timestamp("2026-01-01"): -10.0, pd.Timestamp("2026-12-31"): -10.0})
    lean = {"AA": 20.0, "BB": -20.0, "CC": 0.0}
    rows = [dict(state=s, end_date=pd.Timestamp("2026-06-01").date(), net=-10.0 - 1.0 * lean[s]) for s in lean for _ in range(5)]
    f = fit(pd.DataFrame(rows), lean, series)
    assert f["b"] == pytest.approx(-1.0, abs=0.05)
    assert abs(f["u"]["CC"]["u"]) < 0.5


def test_mood_block_groups_by_poll_with_sources():
    blocks = mood_block()
    assert blocks and all(p["url"].startswith("http") for b in blocks for p in b["polls"])
