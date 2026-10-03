"""Normalize polls from the 538 archive (2018–2024) and VoteHub (2025–) into canonical tables.

questions.parquet — one row per poll question (a poll can ask several matchups)
answers.parquet   — one row per answer option (candidate / Approve / Dem ...)
"""
from __future__ import annotations

import difflib
import re
from collections import Counter

import numpy as np
import pandas as pd

from pipeline.config import DB, MANUAL, RAW
from pipeline.ingest import votehub
from pipeline.states import to_abbr

FTE = RAW / "fte_archive"
FTE_OFFICES = {"senate": "sen", "governor": "gov", "house": "house", "president": "pres",
               "generic_ballot": "generic", "president_approval": "approval"}
# Senate class up in each regular cycle; any other class in that year is a special election.
SEN_CLASS = {2018: "Class I", 2020: "Class II", 2022: "Class III", 2024: "Class I", 2026: "Class II"}
VH_OFFICES = {"us-senator": "sen", "governor": "gov", "us-representative": "house",
              "generic-ballot": "generic", "approval": "approval"}

Q_COLS = ["qid", "source", "poll_id", "cycle", "office", "race_id", "state", "district", "stage",
          "pollster", "sponsors", "partisan", "internal", "start_date", "end_date", "sample_size",
          "population", "mode", "mode_source", "weighting_class", "url", "hypothetical", "subject",
          "published"]


def _date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="mixed").dt.date


def norm_population(p) -> str:
    p = str(p).lower().strip()
    return p if p in {"lv", "rv", "a", "v"} else "unknown"


def race_id(cycle, office, state, district=None, special=False):
    if office in {"generic", "approval"}:
        return None
    rid = f"{cycle}-{office}-{state}"
    if office in {"house", "pres"} and district is not None and not pd.isna(district):
        rid += f"-{int(district):02d}"
    if special:
        rid += "-S"
    return rid


def _fte_partisan(x) -> str | None:
    x = str(x)
    if x.startswith("DEM"):
        return "DEM"
    if x.startswith("REP"):
        return "REP"
    return None if x in {"nan", "None", "", "<NA>"} else "OTH"


def _state_or_none(s) -> str | None:
    if pd.isna(s):
        return "US"
    try:
        return to_abbr(str(s))
    except KeyError:
        return None


def _col(df: pd.DataFrame, name: str, default=None) -> pd.Series:
    return df[name] if name in df.columns else pd.Series([default] * len(df), index=df.index)


def load_fte() -> tuple[pd.DataFrame, pd.DataFrame]:
    qs, ans = [], []
    for f, office in FTE_OFFICES.items():
        d = pd.read_csv(FTE / f"{f}_polls_historical.csv.gz", low_memory=False)
        d["qid"] = "538:" + d["question_id"].astype("int64").astype(str)
        if "ranked_choice_reallocated" in d.columns:  # keep first-choice results only
            d = d[d["ranked_choice_reallocated"].astype(str) != "True"]
        first = d.groupby("qid", sort=False).first().reset_index()
        q = pd.DataFrame({"qid": first["qid"], "source": "538",
                          "poll_id": "538:" + first["poll_id"].astype(str)})
        if "cycle" in first.columns:
            q["cycle"] = first["cycle"].astype("Int64")
        else:  # approval file has no cycle: use end-date year
            q["cycle"] = _date(first["end_date"]).map(lambda x: x.year).astype("Int64")
        q["office"] = office
        st = _col(first, "state")
        q["state"] = st.map(_state_or_none)
        if office == "house":
            q["district"] = _col(first, "seat_number")
        else:  # president polls of Maine CD-2 / Nebraska CD-2 are their own jurisdiction
            q["district"] = st.astype(str).str.extract(r"CD-(\d+)")[0].astype(float)
        before = len(q)
        keep = q["state"].notna()
        q, first = q[keep].copy(), first[keep]
        if before - len(q):
            print(f"  {f}: dropped {before - len(q)} questions outside the 50 states + DC")
        if office == "sen":
            special = [sn != SEN_CLASS.get(int(c)) for sn, c in zip(first["seat_name"], first["cycle"])]
        else:
            special = [False] * len(first)
        q["race_id"] = [race_id(c, office, s, dd, sp) for c, s, dd, sp in
                        zip(q["cycle"], q["state"], q["district"], special)]
        q["subject"] = _col(first, "politician") if office == "approval" else None
        q["stage"] = _col(first, "stage", "general").fillna("general")
        q["pollster"] = first["pollster"]
        q["sponsors"] = _col(first, "sponsors").fillna("")
        q["partisan"] = _col(first, "partisan").map(_fte_partisan)
        q["internal"] = _col(first, "internal").astype(str).eq("True")
        q["start_date"] = _date(first["start_date"])
        q["end_date"] = _date(first["end_date"])
        q["sample_size"] = pd.to_numeric(first["sample_size"], errors="coerce")
        q["population"] = first["population"].map(norm_population)
        meth = _col(first, "methodology")
        q["mode"] = meth.fillna("unknown")
        q["mode_source"] = np.where(meth.isna(), "unknown", "538")
        q["weighting_class"] = "UNK"
        q["url"] = _col(first, "url")
        q["hypothetical"] = _col(first, "hypothetical").astype(str).eq("True")
        q["published"] = _date(_col(first, "created_at").fillna(first["end_date"]))
        qs.append(q[Q_COLS])
        d = d[d["qid"].isin(q["qid"])]
        if office == "generic":  # wide file: dem / rep columns
            first = first[first["qid"].isin(q["qid"])]
            for col, party in (("dem", "DEM"), ("rep", "REP")):
                ans.append(pd.DataFrame({"qid": first["qid"], "answer": col.title(), "candidate": col.title(),
                                         "party": party, "pct": first[col]}))
        elif office == "approval":  # wide file: yes / no
            first = first[first["qid"].isin(q["qid"])]
            for col, label in (("yes", "Approve"), ("no", "Disapprove")):
                ans.append(pd.DataFrame({"qid": first["qid"], "answer": label, "candidate": label,
                                         "party": None, "pct": first[col]}))
        else:
            ans.append(pd.DataFrame({
                "qid": d["qid"], "answer": d["answer"],
                "candidate": _col(d, "candidate_name").fillna(d["answer"]),
                "party": _col(d, "party"), "pct": d["pct"]}))
    return pd.concat(qs, ignore_index=True), pd.concat(ans, ignore_index=True)


VH_STAGE = re.compile(r"\b(Democratic|Republican|DFL)\b|Primary|Jungle", re.I)


def load_votehub(fte_modes: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, ans = [], []
    for p in votehub.load():
        office = VH_OFFICES.get(p["poll_type"])
        if office is None:
            continue
        if office == "approval" and p.get("subject") != "Donald Trump":
            continue
        subj = p.get("subject") or ""
        m = re.match(r"^(\d{4})\s*(.*)$", subj)
        cycle = int(m.group(1)) if m else int(str(p["end_date"])[:4])
        rest = m.group(2) if m else subj
        stage = "primary" if VH_STAGE.search(rest) else ("runoff" if "Runoff" in rest else "general")
        state, district = "US", None
        if office in {"sen", "gov"}:
            name = VH_STAGE.sub("", rest).replace("Runoff", "").strip()
            try:
                state = to_abbr(name)
            except KeyError:
                continue
        elif office == "house":
            seat = p.get("seat_name") or rest
            mm = re.match(r"([A-Z]{2})-(\d+)", str(seat))
            if not mm:
                continue
            state, district = mm.group(1), int(mm.group(2))
        if office == "approval":
            cycle = int(str(p["end_date"])[:4])
        elif office == "generic":
            cycle = 2026
        qid = "vh:" + p["id"]
        pollster = p["pollster"]
        mode = fte_modes.get(pollster_key(pollster))
        rows.append(dict(
            qid=qid, source="votehub", poll_id=qid, cycle=cycle, office=office,
            race_id=race_id(cycle, office, state, district, False), state=state, district=district,
            stage=stage, pollster=pollster, sponsors="; ".join(p.get("sponsors") or []),
            partisan=p.get("partisan") if p.get("partisan") in {"DEM", "REP"} else None,
            internal=bool(p.get("internal")),
            start_date=pd.Timestamp(p["start_date"]).date(), end_date=pd.Timestamp(p["end_date"]).date(),
            sample_size=p.get("sample_size"), population=norm_population(p.get("population")),
            mode=mode or "unknown", mode_source="inferred_538" if mode else "unknown",
            weighting_class="UNK", url=p.get("url"), hypothetical=False,
            subject="Donald Trump" if office == "approval" else subj,
            published=pd.Timestamp(p.get("created_at") or p["end_date"]).date()))
        for a in p["answers"]:
            party = {"Dem": "DEM", "Rep": "REP"}.get(a["choice"]) if office == "generic" else None
            ans.append(dict(qid=qid, answer=a["choice"], candidate=a["choice"], party=party, pct=a["pct"]))
    return pd.DataFrame(rows, columns=Q_COLS), pd.DataFrame(ans)


def pollster_key(name: str) -> str:
    """Loose pollster key for cross-source matching."""
    s = str(name).lower().replace("&", " and ")
    s = re.sub(r"\b(university|college|poll(ing|s)?|research|group|inc|llc|the|institute|center|"
               r"associates|strategies|survey|partners|analytics|insights?)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def fte_mode_by_pollster(q: pd.DataFrame) -> dict[str, str]:
    """Most common 538-recorded mode per pollster, used (flagged) when VoteHub has no mode."""
    known = q[q["mode_source"] == "538"]
    out = {}
    for key, g in known.assign(k=known["pollster"].map(pollster_key)).groupby("k"):
        out[key] = Counter(g["mode"]).most_common(1)[0][0]
    return out


def _last(name: str) -> str:
    parts = [x for x in re.sub(r"[^A-Za-z\- ]", " ", str(name)).split()
             if x.lower() not in {"jr", "sr", "ii", "iii"}]
    return parts[-1].lower() if parts else ""


def match_candidate(name: str, race_cands: pd.DataFrame):
    hits = race_cands[race_cands["name"].map(_last) == _last(name)]
    if len(hits) == 0:  # tolerate small typos ("Healy" for "Healey"), needs same first initial
        close = race_cands[race_cands["name"].map(
            lambda n: difflib.SequenceMatcher(None, _last(n), _last(name)).ratio() >= 0.85
            and str(n)[:1].lower() == str(name)[:1].lower())]
        hits = close
    if len(hits) == 1:
        return hits.iloc[0]
    if len(hits) > 1:  # e.g. several "Sullivan"s in Alaska: require first name too
        first = str(name).lower().split()[0]
        exact = hits[hits["name"].str.lower().str.split().str[0] == first]
        if len(exact) >= 1:
            return exact.sort_values("incumbent", ascending=False).iloc[0]
    return None


def attach_parties(q: pd.DataFrame, a: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """VoteHub answers carry names only. Match to 2026 nominees by last name within the race."""
    a = a.copy()
    race_of = q.set_index("qid")["race_id"].to_dict()
    stage_of = q.set_index("qid")["stage"].to_dict()
    by_race = {rid: g for rid, g in cands.groupby("race_id")}
    aliases = pd.read_csv(MANUAL / "candidate_aliases.csv")
    alias = {(r.race_id, r.poll_name): r.candidate_id for r in aliases.itertuples()}
    by_id = cands.set_index("candidate_id")
    cid, party = [], []
    for qid_, name, p in zip(a["qid"], a["candidate"], a["party"]):
        rid = race_of.get(qid_)
        found = None
        if (rid, name) in alias and stage_of.get(qid_) == "general":
            found = by_id.loc[alias[(rid, name)]].copy()
            found["candidate_id"] = alias[(rid, name)]
        elif rid in by_race and stage_of.get(qid_) == "general":
            found = match_candidate(name, by_race[rid])
        cid.append(found["candidate_id"] if found is not None else None)
        party.append(found["party"] if found is not None else p)
    a["candidate_id"] = cid
    a["party"] = party
    return a


def fix_2026_specials(q: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """VoteHub doesn't mark specials. In 2026 OH and FL have only a special Senate race."""
    special = set(races.loc[races["special"], "race_id"])
    regular = set(races["race_id"])
    q = q.copy()
    for rid in special:
        base = rid[:-2]
        if base not in regular:
            q.loc[q["race_id"] == base, "race_id"] = rid
    return q


def load_extra(vq: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hand-entered polls that VoteHub is missing (data/manual/extra_polls.csv, each with a source URL).
    Dropped automatically if VoteHub carries the same pollster/race within 3 days of the end date."""
    path = MANUAL / "extra_polls.csv"
    if not path.exists():
        return pd.DataFrame(columns=Q_COLS), pd.DataFrame(columns=["qid", "answer", "candidate", "party", "pct"])
    m = pd.read_csv(path, dtype=str)
    rows, ans = [], []
    vq_end = pd.to_datetime(vq["end_date"])
    for r in m.itertuples():
        district = int(r.district) if isinstance(r.district, str) and r.district.strip() else None
        rid = race_id(int(r.cycle), r.office, r.state, district, False)
        end = pd.Timestamp(r.end_date)
        dup = vq[(vq["race_id"] == rid) & (vq["pollster"].map(pollster_key) == pollster_key(r.pollster))
                 & ((vq_end - end).abs() <= pd.Timedelta(days=3))]
        if len(dup):
            continue
        qid = "manual:" + r.poll_id
        rows.append(dict(qid=qid, source="manual", poll_id=qid, cycle=int(r.cycle), office=r.office, race_id=rid,
                         state=r.state, district=district, stage="general", pollster=r.pollster,
                         sponsors=r.sponsors if isinstance(r.sponsors, str) else "",
                         partisan=r.partisan if r.partisan in ("DEM", "REP") else None, internal=False,
                         start_date=pd.Timestamp(r.start_date).date(), end_date=end.date(),
                         sample_size=pd.to_numeric(r.sample_size, errors="coerce"), population=norm_population(r.population),
                         mode="unknown", mode_source="unknown", weighting_class="UNK", url=r.url, hypothetical=False,
                         subject=f"{r.cycle} {r.state}", published=pd.Timestamp(r.published).date()))
        for part in str(r.answers).split("|"):
            name, _, pct = part.rpartition(":")
            ans.append(dict(qid=qid, answer=name.strip(), candidate=name.strip(), party=None, pct=float(pct)))
    return pd.DataFrame(rows, columns=Q_COLS), pd.DataFrame(ans)


def main() -> None:
    fq, fa = load_fte()
    vq, va = load_votehub(fte_mode_by_pollster(fq))
    xq, xa = load_extra(vq)
    vq, va = pd.concat([vq, xq], ignore_index=True), pd.concat([va, xa], ignore_index=True)
    races = pd.read_parquet(DB / "races.parquet")
    cands = pd.read_parquet(DB / "candidates.parquet")
    if (DB / "house_candidates.parquet").exists():
        cands = pd.concat([cands, pd.read_parquet(DB / "house_candidates.parquet")], ignore_index=True)
    vq = fix_2026_specials(vq, races)
    va = attach_parties(vq, va, cands)
    fa["candidate_id"] = None
    q = pd.concat([fq, vq], ignore_index=True)
    a = pd.concat([fa, va], ignore_index=True)
    q["pollster_key"] = q["pollster"].map(pollster_key)
    # weighting-method classes are coded from current methodology statements → 2025– polls only
    from pipeline.model.weighting import classify
    cur = q["source"].isin(["votehub", "manual"])
    q.loc[cur, "weighting_class"] = classify(q.loc[cur, "pollster"]).to_numpy()
    for c in ("district", "sample_size"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q["cycle"] = q["cycle"].astype("Int64")
    q.to_parquet(DB / "questions.parquet", index=False)
    a.to_parquet(DB / "answers.parquet", index=False)
    print(q.groupby(["source", "office"]).size().to_string())


if __name__ == "__main__":
    main()
