"""Public mood: hand-curated readings from published polls (data/manual/mood_polls.csv).

Question wording differs across pollsters for most of these topics, so they are shown as individual
readings with their source, not averaged. Every row must carry the URL of the pollster's (or a
reputable outlet's) published result; numbers are checked against that page before entry.
"""
from __future__ import annotations

import pandas as pd

from pipeline.config import MANUAL

TOPICS = {
    "right_track": "Is the country headed in the right direction?",
    "top_issue": "Most important issue",
    "economy_view": "The economy",
    "enthusiasm": "Enthusiasm about voting",
    "israel": "Israeli–Palestinian conflict: sympathies",
}


def mood_block() -> list[dict]:
    path = MANUAL / "mood_polls.csv"
    if not path.exists():
        return []
    m = pd.read_csv(path, dtype={"n": "string"})
    out = []
    for key, title in TOPICS.items():
        g = m[m["topic"] == key]
        if g.empty:
            continue
        polls = []
        for (pollster, end), pg in g.sort_values("end_date", ascending=False).groupby(["pollster", "end_date"], sort=False):
            r0 = pg.iloc[0]
            polls.append(dict(pollster=pollster, sponsor=None if pd.isna(r0["sponsor"]) else r0["sponsor"],
                              start=r0["start_date"], end=end, population=r0["population"],
                              n=None if pd.isna(r0["n"]) else int(r0["n"]), url=r0["url"],
                              note=None if pd.isna(r0["note"]) else r0["note"],
                              items=[dict(item=i, value=float(v)) for i, v in zip(pg["item"], pg["value"])]))
        polls.sort(key=lambda p: p["end"], reverse=True)
        out.append(dict(topic=key, title=title, polls=polls))
    return out
