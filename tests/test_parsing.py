import pandas as pd

from pipeline.normalize.polls import match_candidate, pollster_key, race_id
from pipeline.parties import norm_party
from pipeline.races import parse_candidates
from pipeline.states import to_abbr


def test_parse_candidates_strips_refs_and_reads_party():
    cell = "▌Jon Ossoff (Democratic)[79] ▌Mike Collins (Republican)[79]"
    assert parse_candidates(cell) == [("Jon Ossoff", "Democratic"), ("Mike Collins", "Republican")]


def test_parse_candidates_handles_name_with_initial():
    assert parse_candidates("▌Dan S. Sullivan (Republican)[72]") == [("Dan S. Sullivan", "Republican")]


def test_race_ids():
    assert race_id(2026, "sen", "OH", special=True) == "2026-sen-OH-S"
    assert race_id(2024, "house", "TX", 7) == "2024-house-TX-07"
    assert race_id(2024, "pres", "ME", 2.0) == "2024-pres-ME-02"
    assert race_id(2026, "generic", "US") is None


def test_party_normalisation():
    assert norm_party("DFL") == "DEM"
    assert norm_party("Republican") == "REP"
    assert norm_party("Legal Marijuana Now") == "OTH"


def test_state_names():
    assert to_abbr("Maine CD-2") == "ME"
    assert to_abbr("TX") == "TX"


def test_pollster_key_matches_across_sources():
    assert pollster_key("Marist University") == pollster_key("Marist College")
    assert pollster_key("Siena College/New York Times") == pollster_key("Siena/New York Times")


CANDS = pd.DataFrame({
    "candidate_id": ["a", "b", "c", "d"],
    "name": ["Mary Peltola", "Dan S. Sullivan", "Dan J. Sullivan", "Gerald Heikes"],
    "party": ["DEM", "REP", "REP", "REP"],
    "incumbent": [False, True, False, False],
})


def test_match_candidate_last_name_and_ambiguous_prefers_incumbent():
    assert match_candidate("Peltola", CANDS)["candidate_id"] == "a"
    assert match_candidate("Dan Sullivan", CANDS)["candidate_id"] == "b"


def test_match_candidate_tolerates_typo_but_not_strangers():
    healey = pd.DataFrame({"candidate_id": ["h"], "name": ["Maura Healey"], "party": ["DEM"], "incumbent": [True]})
    assert match_candidate("Maura Healy", healey)["candidate_id"] == "h"
    assert match_candidate("Seth Moulton", healey) is None


def test_questions_with_big_non_nominee_share_are_dropped():
    from pipeline.model.data import question_margins
    q = pd.DataFrame({"qid": ["a", "b"], "race_id": ["r", "r"]})
    a = pd.DataFrame({
        "qid": ["a", "a", "a", "b", "b"],
        "candidate": ["Hill", "Begich", "Schultz", "Hill", "Begich"],
        "candidate_id": ["r:hill", "r:begich", None, "r:hill", "r:begich"],
        "party": ["IND", "REP", None, "IND", "REP"],
        "pct": [20.0, 46.0, 32.0, 46.0, 54.0],
    })
    m = question_margins(q, a, d_side={"r": "r:hill"})
    assert m["qid"].tolist() == ["b"]   # 'a' had a 32% candidate who isn't on the ballot
