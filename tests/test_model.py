import numpy as np
import pandas as pd
import pytest

from pipeline.model.average import AvgParams, house_effects, lv_shift
from pipeline.model.data import sampling_var
from pipeline.model.forecast import ErrParams, _t, blend, outcomes
from pipeline.model.fundamentals import inc_code
from pipeline.model.turnout import scenario_shifts
from pipeline.run import rcv_adjust, tipping_from_margins


def test_sampling_var_and_default():
    assert sampling_var(1000)[()] == pytest.approx(10.0)
    assert sampling_var(np.nan)[()] == pytest.approx(1e4 / 600)


def test_student_t_draws_have_unit_variance():
    x = _t(np.random.default_rng(0), (400_000,), 5.0)
    assert x.var() == pytest.approx(1.0, rel=0.03)


def test_lv_shift_is_prior_without_pairs_and_moves_with_evidence():
    p = AvgParams()
    empty = pd.DataFrame(columns=["pollster", "end_date", "race_id", "population", "margin"])
    assert lv_shift(empty, p) == (p.lv_prior_mean, p.lv_prior_sd)
    rows = []
    for i in range(20):
        rows += [dict(pollster=f"P{i}", end_date="2026-09-01", race_id="x", population="lv", margin=3.0),
                 dict(pollster=f"P{i}", end_date="2026-09-01", race_id="x", population="rv", margin=1.0 + (i % 3 - 1))]
    mean, sd = lv_shift(pd.DataFrame(rows), p)
    assert 1.0 < mean < 2.0 and sd < p.lv_prior_sd


def test_house_effects_are_centred_and_recover_a_lean():
    rng = np.random.default_rng(1)
    rows = []
    for race in range(20):
        truth = rng.normal(0, 5)
        for pollster, lean in (("A", 3.0), ("B", 0.0), ("C", -3.0)):
            rows.append(dict(race_id=f"r{race}", pollster=pollster, margin_pre_house=truth + lean,
                             weight=1.0, sv=1.0, tau2=0.5, hist_bias=0.0))
    h = house_effects(pd.DataFrame(rows), AvgParams(house_sd=5.0))
    assert h.mean() == pytest.approx(0, abs=1e-6)
    assert h["A"] == pytest.approx(3.0, abs=0.3) and h["C"] == pytest.approx(-3.0, abs=0.3)


def test_blend_is_precision_weighted():
    races = pd.DataFrame(dict(race_id=["a", "b"], office=["sen", "sen"], state=["OH", "OH"], lean=[0.0, 0.0], inc=[0, 0]))
    avgs = pd.DataFrame(dict(race_id=["a"], poll_avg=[10.0], poll_var=[0.0]))
    fmodel = {"sen": {"coef": {"const": 0.0, "lean": 1.0, "N": 1.0, "inc": 0.0}, "sigma": 4.0}}
    ep = ErrParams(rp_ed=4.0, T0=1e9)
    t = blend(races, avgs, fmodel, N_hat=0.0, days=0, ep=ep)
    a, b = t.set_index("race_id").loc["a"], t.set_index("race_id").loc["b"]
    assert a["poll_weight"] == pytest.approx(0.5) and a["mu"] == pytest.approx(5.0)
    assert b["poll_weight"] == 0 and b["mu"] == 0 and b["sd"] == pytest.approx(4.0)


def test_runoff_rule_requires_majority():
    tbl = pd.DataFrame(dict(race_id=["ga"], rule=["majority_runoff"], other_hat=[10.0]))
    sims = dict(margins=np.array([[2.0]] * 2000 + [[30.0]] * 2000), rng=np.random.default_rng(0))
    win = outcomes(tbl, sims, ErrParams(other_sd=0.001, runoff_sd=0.001))
    runoff = sims["runoff"]["ga"]
    assert runoff[:2000].all() and not runoff[2000:].any()   # D 46% → runoff; D 60% → outright
    assert win.all()


def test_inc_code():
    assert inc_code(True, "REP") == -1 and inc_code(True, "DEM") == 1 and inc_code(False, "REP") == 0


def test_scenario_shifts_symmetric_around_typical_midterm():
    shifts, probs, meta = scenario_shifts((0.7, 0.3))
    assert shifts == [-1.0, 0.0, 1.0] and sum(probs) == pytest.approx(1)


def test_rcv_transfers_same_party_minor_votes():
    polls = pd.DataFrame(dict(race_id=["ak", "oh"], margin=[10.0, 10.0], other_rep=[12.0, 12.0], other_dem=[0.0, 0.0]))
    out = rcv_adjust(polls, {"ak"})
    assert out["margin"].tolist() == [1.0, 10.0]


def test_tipping_point_picks_median_seat():
    t = pd.DataFrame(dict(race_id=["a", "b", "c"]))
    m = np.array([[-5.0, 1.0, 5.0]])          # R wins a; D wins b, c
    w = m > 0
    # hold_r = 49 → R reaches 50 with race a; D (hold 48) reaches 50 only → R controls, tipping = a
    tp = tipping_from_margins(t, m, w, hold_d=48, hold_r=49, is_ind=np.zeros(3, bool), caucus_d=np.zeros((1, 3), bool))
    assert tp["a"] == 1.0
