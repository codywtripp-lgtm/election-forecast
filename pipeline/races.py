"""Build the 2026 race and candidate tables from Wikipedia snapshots + data/manual/race_rules.csv.

Output: data/db/races.parquet, data/db/candidates.parquet
"""
from __future__ import annotations

import io
import re

import pandas as pd

from pipeline.config import CYCLE, DB, MANUAL
from pipeline.ingest.wikipedia import load_page
from pipeline.parties import norm_party
from pipeline.states import to_abbr

CAND_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<party>[^()]+)\)\s*(\[[^\]]*\])*\s*$")


def parse_candidates(cell: str) -> list[tuple[str, str]]:
    """'▌Jon Ossoff (Democratic)[79] ▌Mike Collins (Republican)[79]' → [(name, party_label), ...]"""
    out = []
    for part in str(cell).split("▌"):
        part = re.sub(r"\[[^\]]*\]", "", part).strip()
        if not part:
            continue
        m = CAND_RE.match(part)
        if m:
            out.append((m["name"].strip(), m["party"].strip()))
    return out


def race_id(cycle: int, office: str, state: str, special: bool = False, district: int | None = None) -> str:
    rid = f"{cycle}-{office}-{state}"
    if district is not None:
        rid += f"-{district:02d}"
    if special:
        rid += "-S"
    return rid


def _tables_with(html: str, needed: set[str]) -> list[pd.DataFrame]:
    out = []
    for t in pd.read_html(io.StringIO(html)):
        cols = [c[-1] if isinstance(c, tuple) else c for c in t.columns]
        if needed <= set(cols):
            t.columns = cols
            out.append(t)
    return out


def build_senate(html: str) -> tuple[list[dict], list[dict]]:
    races, cands = [], []
    for t in _tables_with(html, {"State", "Senator", "Party", "Candidates"}):
        for _, r in t.iterrows():
            state_label = str(r["State"])
            special = "(Class" in state_label  # special-election table labels the seat class
            st = to_abbr(re.sub(r"\s*\(.*\)", "", state_label))
            rid = race_id(CYCLE, "sen", st, special)
            status = r.get("Results", r.get("Status", ""))
            races.append(dict(race_id=rid, cycle=CYCLE, office="sen", state=st, district=None, special=special,
                              incumbent=r["Senator"], incumbent_party=norm_party(r["Party"]), status=str(status)))
            for name, plabel in parse_candidates(r["Candidates"]):
                cands.append(dict(race_id=rid, name=name, party_label=plabel, party=norm_party(plabel),
                                  incumbent=_same_person(name, r["Senator"])))
    return races, cands


def build_governor(html: str) -> tuple[list[dict], list[dict]]:
    races, cands = [], []
    for t in _tables_with(html, {"State", "Governor", "Party", "Candidates"}):
        for _, r in t.iterrows():
            st = to_abbr(str(r["State"]))
            rid = race_id(CYCLE, "gov", st)
            races.append(dict(race_id=rid, cycle=CYCLE, office="gov", state=st, district=None, special=False,
                              incumbent=r["Governor"], incumbent_party=norm_party(r["Party"]), status=str(r["Status"])))
            for name, plabel in parse_candidates(r["Candidates"]):
                cands.append(dict(race_id=rid, name=name, party_label=plabel, party=norm_party(plabel),
                                  incumbent=_same_person(name, r["Governor"])))
    return races, cands


def _same_person(a: str, b: str) -> bool:
    clean = lambda s: re.sub(r"\[.*?\]", "", str(s)).strip().lower()
    return clean(a) == clean(b)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    r1, c1 = build_senate(load_page("senate_2026")["html"])
    r2, c2 = build_governor(load_page("governor_2026")["html"])
    races = pd.DataFrame(r1 + r2)
    cands = pd.DataFrame(c1 + c2)
    rules = pd.read_csv(MANUAL / "race_rules.csv")
    rules = rules[rules.cycle == CYCLE][["office", "state", "rule", "runoff_date", "verified"]]
    races = races.merge(rules, on=["office", "state"], how="left")
    races["rule"] = races["rule"].fillna("plurality")
    races["rule_verified"] = races.pop("verified").fillna("default")
    cands["candidate_id"] = cands["race_id"] + ":" + cands["name"].str.lower().str.replace(r"[^a-z]+", "-", regex=True)
    return races, cands


def main() -> None:
    races, cands = build()
    DB.mkdir(parents=True, exist_ok=True)
    races.to_parquet(DB / "races.parquet", index=False)
    cands.to_parquet(DB / "candidates.parquet", index=False)
    print(races.groupby("office").size().to_dict(), len(cands), "candidates")


if __name__ == "__main__":
    main()
