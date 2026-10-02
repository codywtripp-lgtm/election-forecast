"""Historical Senate and governor results (2010–2025) from Wikipedia cycle pages via the MediaWiki API.

Each cycle page has a summary table: state, incumbent, incumbent party, result text, and candidates
with vote percentages ("▌ Katie Britt (Republican) 66.6% ▌Will Boyd (Democratic) 30.9%").
Percentages are rounded to 0.1 — fine for margins. Senate figures are cross-checked against MEDSL
(see tests/test_results.py).

Output: data/db/results_races.parquet (one row per race), data/db/results_candidates.parquet
"""
from __future__ import annotations

import io
import json
import re

import pandas as pd

from pipeline.config import DB
from pipeline.ingest.snapshot import SESSION, read_snapshot, snapshot_path, write_snapshot
from pipeline.parties import norm_party
from pipeline.states import to_abbr

API = "https://en.wikipedia.org/w/api.php"
SEN_YEARS = list(range(2010, 2025, 2))
GOV_YEARS = list(range(2010, 2026))
CAND_PCT = re.compile(r"^(?P<name>.+?)\s*\((?P<party>[^()]+)\)\s*(?P<pct>[\d.]+)\s*%")


def page_name(office: str, year: int) -> str:
    kind = "Senate" if office == "sen" else "gubernatorial"
    return f"{year}_United_States_{kind}_elections"


def fetch_cycle(office: str, year: int) -> dict:
    """Fetch once and cache as a snapshot (history pages rarely change)."""
    key = f"{office}_{year}"
    existing = sorted((snapshot_path("wikipedia", key, "json").parent).glob("*.gz"))
    if existing:
        return json.loads(read_snapshot(existing[-1]))
    r = SESSION.get(API, params={"action": "parse", "page": page_name(office, year), "prop": "text|revid",
                                 "format": "json", "formatversion": 2}, timeout=60)
    r.raise_for_status()
    if "error" in r.json():
        return {}
    p = r.json()["parse"]
    payload = {"page": page_name(office, year), "revid": p["revid"], "html": p["text"]}
    write_snapshot(snapshot_path("wikipedia", key, "json"), json.dumps(payload).encode())
    return payload


def parse_candidates_pct(cell: str) -> list[dict]:
    out = []
    for part in str(cell).split("▌"):
        part = re.sub(r"\[[^\]]*\]", "", part).strip()
        m = CAND_PCT.match(part)
        if m and m["name"].strip() not in {o["name"] for o in out}:  # a repeat = runoff round
            out.append(dict(name=m["name"].strip(), party_label=m["party"].strip(),
                            party=norm_party(m["party"]), pct=float(m["pct"])))
    return out


def _flat(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t.columns = [re.sub(r"\[.*?\]", "", str(c[-1] if isinstance(c, tuple) else c)).strip() for c in t.columns]
    return t.rename(columns={"States": "State"})


def parse_cycle(office: str, year: int, html: str) -> tuple[list[dict], list[dict]]:
    races, cands = {}, []
    inc_col = "Senator" if office == "sen" else "Governor"
    for t in pd.read_html(io.StringIO(html)):
        t = _flat(t)
        cand_col = next((c for c in t.columns if "andidates" in c), None)
        inc = inc_col if inc_col in t.columns else ("Incumbent" if "Incumbent" in t.columns else None)
        if cand_col is None or inc is None or "State" not in t.columns or "Party" not in t.columns:
            continue
        res_col = next((c for c in ("Result", "Results", "Status") if c in t.columns), None)
        for _, r in t.iterrows():
            label = str(r["State"])
            cl = parse_candidates_pct(r[cand_col])
            if len(cl) < 1 or sum(c["pct"] for c in cl) < 50:  # not a results row
                continue
            special = bool(re.search(r"\(Class|special", label, re.I))
            try:
                st = to_abbr(re.sub(r"\s*\(.*\)", "", label).strip())
            except KeyError:
                continue
            rid = f"{year}-{office}-{st}" + ("-S" if special else "")
            if rid in races:
                continue
            incumbent = re.sub(r"\[.*?\]", "", str(r[inc])).strip()
            races[rid] = dict(race_id=rid, cycle=year, office=office, state=st, special=special,
                              incumbent=incumbent, incumbent_party=norm_party(str(r["Party"])),
                              result_text=str(r[res_col]) if res_col else "")
            for c in cl:
                c.update(race_id=rid, incumbent=_same(c["name"], incumbent))
                cands.append(c)
    return list(races.values()), cands


def _same(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z ]", "", s.lower()).split()
    na, nb = norm(a), norm(b)
    return bool(na and nb) and na[-1] == nb[-1] and na[0][:1] == nb[0][:1]


def summarise(races: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """Per race: top DEM-side and REP candidate shares, two-party margin, winner."""
    rows = []
    for rid, g in cands.groupby("race_id"):
        g = g.sort_values("pct", ascending=False)
        rep = g[g.party == "REP"].head(1)
        # "D-side" = strongest non-Republican (King/Sanders/Osborn-type independents included)
        dem = g[g.party != "REP"].head(1)
        top2_same = len(g) >= 2 and g.iloc[0]["party"] == g.iloc[1]["party"]
        winner = g.iloc[0]
        d = float(dem.pct.iloc[0]) if len(dem) else 0.0
        rp = float(rep.pct.iloc[0]) if len(rep) else 0.0
        rows.append(dict(race_id=rid, dem_name=dem.name.iloc[0] if len(dem) else None,
                         rep_name=rep.name.iloc[0] if len(rep) else None,
                         dem_pct=d, rep_pct=rp, other_pct=max(0.0, 100 - d - rp),
                         margin=d - rp, margin_2p=(100 * (d - rp) / (d + rp)) if d + rp > 0 else None,
                         winner_name=winner["name"], winner_party=winner["party"],
                         contested=len(dem) > 0 and len(rep) > 0,
                         dem_is_ind=len(dem) > 0 and dem.party.iloc[0] != "DEM",
                         top2_same_party=bool(top2_same),
                         incumbent_running=bool(g.incumbent.any()),
                         incumbent_cand_party=g[g.incumbent].party.iloc[0] if g.incumbent.any() else None))
    return races.merge(pd.DataFrame(rows), on="race_id", how="left")


def main() -> None:
    all_r, all_c = [], []
    for office, years in (("sen", SEN_YEARS), ("gov", GOV_YEARS)):
        for y in years:
            page = fetch_cycle(office, y)
            if not page:
                continue
            r, c = parse_cycle(office, y, page["html"])
            all_r += r
            all_c += c
            print(office, y, len(r), "races")
    races = pd.DataFrame(all_r)
    cands = pd.DataFrame(all_c)
    out = summarise(races, cands)
    DB.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DB / "results_races.parquet", index=False)
    cands.to_parquet(DB / "results_candidates.parquet", index=False)


if __name__ == "__main__":
    main()
