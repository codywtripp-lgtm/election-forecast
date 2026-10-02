import numpy as np
import pandas as pd
import pytest

from pipeline.model.average import AvgParams, house_effects
from pipeline.model.weighting import PRIOR_SD, classify, estimate


def test_classify_exact_and_joint_pollsters():
    got = classify(pd.Series(["YouGov", "Emerson College", "Nobody Polling", "YouGov/Morning Consult", "YouGov/Emerson College"]))
    assert got.tolist() == ["PV", "PID", "UNK", "PV", "UNK"]  # mixed joint classes stay unknown


def test_estimate_shrinks_and_counts_pollsters_not_polls():
    # one PV pollster with many polls 4 pts more D than the field; PID pollsters at the field mean
    rows = [dict(pollster="YouGov", err=-4.0, race_id="r")] * 20
    rows += [dict(pollster=p, err=-8.0, race_id="r") for p in ("Emerson College", "Echelon Insights", "Quantus Insights")]
    est = estimate(pd.DataFrame(rows))
    pv = est["PV"]
    assert pv["n_pollsters"] == 1 and pv["n_polls"] == 20
    assert 0 < pv["delta"] < pv["raw_diff"]          # shrunk toward 0
    assert pv["sd"] < PRIOR_SD
    assert est["UNK"]["delta"] == 0.0


def test_class_prior_moves_sparse_pollster_house_effect():
    # pollster X has a single poll; its class prior (+3) should pull its house effect up
    rows = []
    for race in range(10):
        for pollster in ("A", "B", "C"):
            rows.append(dict(race_id=f"r{race}", pollster=pollster, margin_pre_house=0.0, weight=1.0, sv=4.0,
                             tau2=1.0, hist_bias=0.0, delta_class=0.0, delta_sd=0.0))
    rows.append(dict(race_id="r0", pollster="X", margin_pre_house=0.0, weight=1.0, sv=4.0, tau2=1.0,
                     hist_bias=0.0, delta_class=3.0, delta_sd=0.0))
    h = house_effects(pd.DataFrame(rows), AvgParams(house_sd=1.0))
    assert h["X"] > 1.0
    assert all(abs(h[p]) < 0.3 for p in ("A", "B", "C"))   # well-polled pollsters stay near the field
