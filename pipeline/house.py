"""House data: 2026 districts + nominees, 2012–2024 district results, and district partisan lean.

Sources
- Wikipedia "<year> United States House of Representatives elections" (MediaWiki API, CC BY-SA):
  one table row per district with incumbent, result text and candidates (with % for past years).
- The Downballot's presidential results by congressional district (public Google Sheets, attributed):
  2024/2020 results on the 2026 lines; earlier results on each cycle's lines.

Outputs (data/db): house_races.parquet, house_candidates.parquet, house_results.parquet, house_lean.parquet
"""
from __future__ import annotations

import io
import json
import re

import numpy as np
import pandas as pd

from pipeline.config import CYCLE, DB, RAW
from pipeline.ingest.snapshot import SESSION, read_snapshot, snapshot_path, write_snapshot
from pipeline.model.data import pres_margins
from pipeline.normalize.results import parse_candidates_pct
from pipeline.parties import norm_party
from pipeline.races import parse_candidates
from pipeline.states import to_abbr

API = "https://en.wikipedia.org/w/api.php"
HIST_YEARS = list(range(2012, 2025, 2))
DB_DIR = RAW / "downballot"

# Downballot sheets: file → (cycles using those lines, {pres_year: (dem_col, rep_col)} by header position)
SHEETS = {
    "lines2026.csv": dict(cycles=[2026]),
    "lines2024.csv": dict(cycles=[2024]),
    "lines2022.csv": dict(cycles=[2022]),
    "lines2020.csv": dict(cycles=[2020]),
    "lines2018.csv": dict(cycles=[2018]),
    "lines2016.csv": dict(cycles=[2016]),
    "lines2012.csv": dict(cycles=[2012, 2014]),
}
SHEET_URLS = {
    "lines2026.csv": ("1eZfaFI-c-PFOoKx1-zZA2MP0_dxRq_LVK0re3BOQqy0", "620838163"),
    "lines2024.csv": ("1ng1i_Dm_RMDnEvauH44pgE6JCUsapcuu8F2pCfeLWFo", "620838163"),
    "lines2022.csv": ("1CKngqOp8fzU22JOlypoxNsxL6KSAH920Whc-rd7ebuM", "1871835782"),
    "lines2020.csv": ("1XbUXnI9OyfAuhP5P3vWtMuGc5UJlrhXbzZo3AwMuHtk", "0"),
    "lines2018.csv": ("1zLNAuRqPauss00HDz4XbTH2HqsCzMe0pR8QmD1K8jk8", "0"),
    "lines2016.csv": ("1VfkHtzBTP5gf4jAu8tcVQgsBJ1IDvXEHjuMqYlOgYbA", "0"),
    "lines2012.csv": ("1xn6nCNM97oFDZ4M-HQgoUT3X4paOiSDsRMSuxbaOBdg", "0"),
}
PRES_NAMES = {"Harris": 2024, "Biden": 2020, "Clinton": 2016, "Obama": None}  # Obama: 2012 then 2008 by order


def download_sheets() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    for f, (sid, gid) in SHEET_URLS.items():
        r = SESSION.get(f"https://docs.google.com/spreadsheets/d/{sid}/export", params={"format": "csv", "gid": gid}, timeout=60)
        r.raise_for_status()
        (DB_DIR / f).write_bytes(r.content)


def district_code(label: str) -> tuple[str, int] | None:
    """'Texas 18' / 'Alaska at-large' / 'TX-18' / 'AK-AL' → ('TX', 18) / ('AK', 1)."""
    label = re.sub(r"\[.*?\]", "", str(label)).replace("\xa0", " ").strip()
    m = re.match(r"^([A-Z]{2})-(\d+|AL)$", label)
    if m:
        return m.group(1), 1 if m.group(2) == "AL" else int(m.group(2))
    m = re.match(r"^(.+?)\s+(\d+|at-large|At-large|at large)$", label)
    if not m:
        return None
    try:
        st = to_abbr(m.group(1))
    except KeyError:
        return None
    d = m.group(2)
    return st, 1 if not d.isdigit() else int(d)


# ------------------------------------------------------------------ presidential results by district

def read_sheet(f: str) -> pd.DataFrame:
    """Return district, pres_year, dem, rep (percent) from one Downballot sheet."""
    raw = pd.read_csv(DB_DIR / f, header=None, dtype=str)
    # the header row is the one naming a Democratic presidential candidate; data rows follow it
    is_names = raw.apply(lambda r: r.astype(str).str.strip().isin(["Harris", "Biden", "Clinton", "Obama"]).any(), axis=1)
    hdr_i = raw.index[is_names][0]
    names = raw.loc[hdr_i].tolist()
    body = raw.loc[hdr_i + 1:]
    rows = []
    obama_seen = 0
    col_years = {}
    for j, n in enumerate(names):
        n = str(n).strip()
        if n in ("Harris", "Biden", "Clinton", "Obama"):
            if n == "Obama":
                year = 2012 if obama_seen == 0 else 2008
                obama_seen += 1
            else:
                year = PRES_NAMES[n]
            col_years[year] = j
    for _, r in body.iterrows():
        dc = district_code(r[0])
        if dc is None:
            continue
        for year, j in col_years.items():
            d = pd.to_numeric(str(r[j]).replace("%", ""), errors="coerce")
            rp = pd.to_numeric(str(r[j + 1]).replace("%", ""), errors="coerce")
            if pd.notna(d) and pd.notna(rp):
                rows.append(dict(state=dc[0], district=dc[1], pres_year=year, dem=float(d), rep=float(rp)))
    return pd.DataFrame(rows)


def district_lean() -> pd.DataFrame:
    """lean[cycle, district] = 0.75·rel(last pres) + 0.25·rel(previous pres), relative to the national margin.
    Where only one is available on that cycle's lines, it gets full weight. For 2026 districts in redrawn
    states (no 2020 on the new lines) 2020 is imputed from 2024 + the state's 2020−2024 relative shift."""
    pm = pres_margins()
    nat = pm.groupby("year")["nat_margin"].first()
    st_rel = pm.set_index(["year", "state"])["rel"]
    out = []
    for f, meta in SHEETS.items():
        s = read_sheet(f)
        s["margin"] = s["dem"] - s["rep"]
        s["rel"] = s["margin"] - s["pres_year"].map(nat)
        piv = s.pivot_table(index=["state", "district"], columns="pres_year", values="rel")
        for cycle in meta["cycles"]:
            prior = sorted([y for y in piv.columns if y < cycle], reverse=True)
            if not prior:
                continue
            last = prior[0]
            prev = prior[1] if len(prior) > 1 else None
            for (st, d), row in piv.iterrows():
                a = row.get(last)
                if pd.isna(a):
                    continue
                b = row.get(prev) if prev else np.nan
                imputed = False
                if cycle == 2026 and pd.isna(b):
                    b = a + (st_rel.get((2020, st), np.nan) - st_rel.get((2024, st), np.nan))
                    imputed = True
                lean = 0.75 * a + 0.25 * b if pd.notna(b) else a
                out.append(dict(cycle=cycle, state=st, district=int(d), lean=float(lean), lean_last=float(a),
                                pres_last=last, lean_2020_imputed=imputed))
    return pd.DataFrame(out)


# ------------------------------------------------------------------ Wikipedia House pages

def house_page(year: int, refresh: bool = False) -> str:
    key = f"house_{year}"
    existing = sorted(snapshot_path("wikipedia", key, "json").parent.glob("*.gz"))
    if existing and not refresh:
        return json.loads(read_snapshot(existing[-1]))["html"]
    page = f"{year}_United_States_House_of_Representatives_elections"
    r = SESSION.get(API, params={"action": "parse", "page": page, "prop": "text|revid", "format": "json",
                                 "formatversion": 2}, timeout=120)
    r.raise_for_status()
    p = r.json()["parse"]
    write_snapshot(snapshot_path("wikipedia", key, "json"),
                   json.dumps({"page": page, "revid": p["revid"], "html": p["text"]}).encode())
    return p["text"]


def _tables(html: str):
    for t in pd.read_html(io.StringIO(html)):
        t.columns = [re.sub(r"\[.*?\]", "", str(c[-1] if isinstance(c, tuple) else c)).strip() for c in t.columns]
        cand = next((c for c in t.columns if "andidates" in c), None)
        inc = next((c for c in ("Member", "Representative", "Incumbent") if c in t.columns), None)
        if "Location" in t.columns and "District" not in t.columns:
            t = t.rename(columns={"Location": "District"})
        if cand and inc and "District" in t.columns:
            yield t, cand, inc


def parse_house(year: int, html: str, with_pct: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per district (regular election; later rows override special-election rows)."""
    races, cands = {}, {}
    res_col_names = ("Results", "Result", "Status")
    for t, cand_col, inc_col in _tables(html):
        res_col = next((c for c in res_col_names if c in t.columns), None)
        for _, r in t.iterrows():
            dc = district_code(r["District"])
            if dc is None:
                continue
            st, d = dc
            rid = f"{year}-house-{st}-{d:02d}"
            text = str(r[res_col]) if res_col else ""
            if "special" in text.lower() and "New member elected" in text and rid in races:
                continue
            party_col = "Party" if "Party" in t.columns else None
            incumbent = re.sub(r"\[.*?\]", "", str(r[inc_col])).strip()
            if incumbent.lower().startswith("none"):
                incumbent = ""
            races[rid] = dict(race_id=rid, cycle=year, office="house", state=st, district=d, special=False,
                              incumbent=incumbent, incumbent_party=norm_party(str(r[party_col])) if party_col else "OTH",
                              result_text=text)
            if with_pct:
                cl = parse_candidates_pct(r[cand_col])
            else:
                cl = [dict(name=n, party_label=p, party=norm_party(p)) for n, p in parse_candidates(r[cand_col])]
            for c in cl:
                c.update(race_id=rid, incumbent=_same(c["name"], incumbent))
            cands[rid] = cl
    return pd.DataFrame(races.values()), pd.DataFrame([c for cl in cands.values() for c in cl])


def _same(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z ]", "", s.lower()).split()
    na, nb = norm(a), norm(b)
    return bool(na and nb) and na[-1] == nb[-1] and na[0][:1] == nb[0][:1]


def results_history() -> pd.DataFrame:
    from pipeline.normalize.results import summarise
    rs, cs = [], []
    for y in HIST_YEARS:
        r, c = parse_house(y, house_page(y), with_pct=True)
        rs.append(r)
        cs.append(c)
    races, cands = pd.concat(rs, ignore_index=True), pd.concat(cs, ignore_index=True)
    return summarise(races, cands)


def main(refresh_2026: bool = True) -> None:
    races, cands = parse_house(CYCLE, house_page(CYCLE, refresh=refresh_2026), with_pct=False)
    cands["candidate_id"] = cands["race_id"] + ":" + cands["name"].str.lower().str.replace(r"[^a-z]+", "-", regex=True)
    rules = {"CA": "top_two", "WA": "top_two", "GA": "majority_runoff", "AK": "top4_rcv", "ME": "rcv"}
    races["rule"] = races["state"].map(rules).fillna("plurality")
    races["rule_verified"] = np.where(races["state"].isin(list(rules)), "yes", "default")
    lean = district_lean()
    hist = results_history()
    DB.mkdir(parents=True, exist_ok=True)
    races.to_parquet(DB / "house_races.parquet", index=False)
    cands.to_parquet(DB / "house_candidates.parquet", index=False)
    hist.to_parquet(DB / "house_results.parquet", index=False)
    lean.to_parquet(DB / "house_lean.parquet", index=False)
    print(len(races), "2026 districts;", len(cands), "candidates;", len(hist), "historical races;",
          lean.groupby("cycle").size().to_dict())


if __name__ == "__main__":
    main()
