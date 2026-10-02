import json

from pipeline.ingest.snapshot import read_snapshot
from pipeline.config import RAW
from pipeline.normalize.results import parse_candidates_pct, parse_cycle


def test_runoff_round_is_ignored():
    cell = ("▌ Raphael Warnock (Democratic) 49.4% ▌Herschel Walker (Republican) 48.5% "
            "▌Chase Oliver (Libertarian) 2.1% ▌ Raphael Warnock (Democratic) 51.4% ▌Herschel Walker (Republican) 48.6%")
    got = parse_candidates_pct(cell)
    assert [c["pct"] for c in got] == [49.4, 48.5, 2.1]


def test_nd_democratic_npl_is_dem():
    got = parse_candidates_pct("▌ Kevin Cramer (Republican) 66.3% ▌Katrina Christiansen (Democratic–NPL) 33.3%")
    assert [c["party"] for c in got] == ["REP", "DEM"]


def test_2022_senate_snapshot_parses_all_races():
    path = sorted((RAW / "wikipedia" / "sen_2022").glob("*.gz"))[-1]
    races, cands = parse_cycle("sen", 2022, json.loads(read_snapshot(path))["html"])
    ids = {r["race_id"] for r in races}
    assert len(races) == 36  # 34 regular + CA and OK specials
    assert {"2022-sen-GA", "2022-sen-OK-S", "2022-sen-CA-S", "2022-sen-PA"} <= ids
