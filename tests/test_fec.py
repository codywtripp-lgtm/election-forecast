import numpy as np
import pandas as pd

from pipeline.fec import FLOOR, _last, match, race_money


FEC = pd.DataFrame({
    "cycle": [2026] * 4, "office": ["house"] * 4, "state": ["NY"] * 4, "district": [17, 17, 17, 3],
    "party": ["DEM", "REP", "DEM", "DEM"], "last": ["conley", "lawler", "smith", "conley"],
    "indiv": [3_000_000.0, 1_000_000.0, 50.0, 9.0],
})


def test_last_name_handles_suffixes():
    assert _last("Thomas Kean Jr.") == "kean"


def test_match_by_district_party_and_last_name():
    assert match(FEC, 2026, "house", "NY", 17, "Cait Conley", "DEM") == 3_000_000.0
    assert match(FEC, 2026, "house", "NY", 17, "Nobody Here", "DEM") is None


def test_money_is_log_ratio_and_unknown_when_unmatched():
    races = pd.DataFrame({"race_id": ["a", "b"], "cycle": [2026, 2026], "office": ["house", "house"],
                          "state": ["NY", "NY"], "district": [17, 17], "dem_name": ["Cait Conley", "Ghost"],
                          "rep_name": ["Mike Lawler", "Mike Lawler"], "d_party": ["DEM", "DEM"]})
    m = race_money(races, FEC).set_index("race_id")
    assert m.loc["a", "money"] == np.log((3e6 + FLOOR) / (1e6 + FLOOR))
    assert np.isnan(m.loc["b", "money"])
