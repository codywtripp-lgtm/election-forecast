"""Seats NOT on the 2026 ballot (holdovers), from Wikipedia's current senators / governors lists.

Senate: every senator except Class 2 (regular 2026 seats) and the seats with 2026 specials.
Governors: every state without a 2026 governor race.
Output: data/db/holdovers.parquet  (office, state, name, party)
"""
from __future__ import annotations

import io
import re

import pandas as pd

from pipeline.config import DB
from pipeline.ingest.wikipedia import PAGES, fetch_page, load_page
from pipeline.parties import norm_party
from pipeline.states import to_abbr

PAGES.setdefault("current_senators", "List_of_current_United_States_senators")
PAGES.setdefault("current_governors", "List_of_current_United_States_governors")


def _clean(c) -> str:
    return re.sub(r"\[.*?\]", "", str(c)).strip()


def senators(html: str) -> pd.DataFrame:
    for t in pd.read_html(io.StringIO(html)):
        cols = [_clean(c) for c in t.columns]
        if "Senator" in cols and "Class" in cols and len(t) >= 95:
            t.columns = cols
            party = t["Party.1"] if "Party.1" in t.columns else t["Party"]
            return pd.DataFrame({"state": t["State"].map(lambda s: to_abbr(_clean(s))),
                                 "name": t["Senator"].map(_clean), "party_label": party.map(_clean),
                                 "class": t["Class"].astype(str).str.extract(r"Class (\d)")[0].astype(int)})
    raise ValueError("senators table not found")


def governors(html: str) -> pd.DataFrame:
    for t in pd.read_html(io.StringIO(html)):
        cols = [_clean(c) for c in t.columns]
        if "State" in cols and "Governor" in cols and len(t) == 50:
            t.columns = cols
            party = t["Party.1"] if "Party.1" in t.columns else t["Party"]
            return pd.DataFrame({"state": t["State"].map(lambda s: to_abbr(re.sub(r"\(list\)", "", _clean(s)).strip())),
                                 "name": t["Governor"].map(_clean), "party_label": party.map(_clean)})
    raise ValueError("governors table not found")


def holdovers(races: pd.DataFrame) -> pd.DataFrame:
    sen = senators(load_page("current_senators")["html"])
    special_states = set(races[(races["office"] == "sen") & races["special"]]["state"])
    up = (sen["class"] == 2) | ((sen["class"] == 3) & sen["state"].isin(special_states))
    sen_h = sen[~up].assign(office="sen")
    gov = governors(load_page("current_governors")["html"])
    gov_states = set(races[races["office"] == "gov"]["state"])
    gov_h = gov[~gov["state"].isin(gov_states)].assign(office="gov")
    out = pd.concat([sen_h, gov_h], ignore_index=True)
    # Independents who caucus with Democrats (King, Sanders) count toward the Democratic caucus
    out["party"] = out["party_label"].map(norm_party)
    out["caucus"] = out["party"].where(out["party"] != "IND", "DEM")
    return out[["office", "state", "name", "party_label", "party", "caucus"]]


def main(fetch: bool = True) -> None:
    if fetch:
        fetch_page("current_senators")
        fetch_page("current_governors")
    races = pd.read_parquet(DB / "races.parquet")
    h = holdovers(races)
    n_sen, n_gov = (h.office == "sen").sum(), (h.office == "gov").sum()
    assert n_sen == 100 - (races.office == "sen").sum(), n_sen
    assert n_gov == 50 - (races.office == "gov").sum(), n_gov
    h.to_parquet(DB / "holdovers.parquet", index=False)
    print(h.groupby(["office", "caucus"]).size().to_dict())


if __name__ == "__main__":
    main()
