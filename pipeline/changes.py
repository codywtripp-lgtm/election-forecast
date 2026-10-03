"""What changed since the previous day's forecast, and an RSS feed of daily updates.

Reads the committed forecast history (data/forecasts/*.csv) and writes
  site/static/data/2026/changes.json   latest day vs the previous day (chamber odds + biggest movers)
  site/static/feed.xml                 RSS 2.0, one item per forecast day (last 30 days)
"""
from __future__ import annotations

import datetime as dt
import json
from email.utils import format_datetime
from xml.sax.saxutils import escape

import pandas as pd

from pipeline.config import CYCLE, DATA, SITE_DATA

SITE_URL = "https://codywtripp-lgtm.github.io/election-forecast"
HISTORY = DATA / "forecasts" / "history.csv"
NATIONAL = DATA / "forecasts" / "national_history.csv"
MOVE_MIN = 0.03          # report races whose D-side chance moved ≥ 3 points


def _names() -> dict:
    s = json.loads((SITE_DATA / str(CYCLE) / "summary.json").read_text(encoding="utf-8"))
    return {r["id"]: r for r in s["races"]}


def race_label(r: dict) -> str:
    from pipeline.states import ABBR_TO_NAME
    st = ABBR_TO_NAME.get(r["state"], r["state"])
    if r["office"] == "house":
        return f"{r['state']}-{str(r.get('district') or r['id'][-2:]).zfill(2)}"
    return f"{st} {'Senate' if r['office'] == 'sen' else 'Governor'}{' (special)' if r.get('special') else ''}"


def day_diff(hist: pd.DataFrame, nat: pd.DataFrame, today: str, prev: str, names: dict) -> dict:
    a = hist[hist["as_of"] == prev].set_index("race_id")["p_dside"]
    b = hist[hist["as_of"] == today].set_index("race_id")["p_dside"]
    d = (b - a).dropna()
    movers = []
    for rid, delta in d[d.abs() >= MOVE_MIN].sort_values(key=abs, ascending=False).head(10).items():
        r = names.get(rid)
        if r:
            movers.append(dict(id=rid, label=race_label(r), d=r["d"], r=r["r"], p_before=float(a[rid]),
                               p_now=float(b[rid]), delta=float(delta)))
    n0 = nat[nat["as_of"] == prev].iloc[-1] if (nat["as_of"] == prev).any() else None
    n1 = nat[nat["as_of"] == today].iloc[-1]
    nat_out = {}
    for k in ("sen_p_dem", "house_p_dem", "generic"):
        if k in n1 and pd.notna(n1[k]):
            nat_out[k] = dict(now=float(n1[k]), before=None if n0 is None or pd.isna(n0.get(k)) else float(n0[k]))
    changes = model_changes(prev, today)
    return dict(as_of=today, previous=prev, national=nat_out, movers=movers, model_changes=changes)


def model_changes(prev: str | None, today: str) -> list[str]:
    """Method changes logged in data/manual/changelog.csv after the previous day, up to today."""
    from pipeline.config import MANUAL
    path = MANUAL / "changelog.csv"
    if not path.exists() or prev is None:
        return []
    log = pd.read_csv(path)
    return log[(log["date"] > prev) & (log["date"] <= today)]["change"].tolist()


def describe(c: dict) -> tuple[str, str]:
    n = c["national"]

    def pct(k):
        x = n.get(k)
        if not x:
            return ""
        s = f"{round(x['now'] * 100)}%"
        if x["before"] is not None:
            dlt = round((x["now"] - x["before"]) * 100)
            s += f" ({'+' if dlt > 0 else ''}{dlt})" if dlt else " (no change)"
        return s
    title = f"Forecast {c['as_of']}: Democrats win the Senate {pct('sen_p_dem')}, House {pct('house_p_dem')}"
    lines = [title + "."]
    if c.get("model_changes"):
        lines.append("Method changes today (some movement reflects these): " + " ".join(c["model_changes"]))
    if c["movers"]:
        lines.append("Biggest moves: " + "; ".join(
            f"{m['label']} ({m['d']} {round(m['p_before'] * 100)}% → {round(m['p_now'] * 100)}%)" for m in c["movers"][:6]) + ".")
    else:
        lines.append("No race moved 3 points or more.")
    return title, " ".join(lines)


def main() -> None:
    if not HISTORY.exists() or not NATIONAL.exists():
        print("no history yet")
        return
    hist = pd.read_csv(HISTORY)
    nat = pd.read_csv(NATIONAL)
    names = _names()
    days = sorted(nat["as_of"].unique())
    out_dir = SITE_DATA / str(CYCLE)
    if len(days) >= 2:
        latest = day_diff(hist, nat, days[-1], days[-2], names)
    else:
        latest = dict(as_of=days[-1], previous=None, national={}, movers=[])
    (out_dir / "changes.json").write_text(json.dumps(latest), encoding="utf-8")

    items = []
    for i in range(len(days) - 1, max(-1, len(days) - 31), -1):
        prev = days[i - 1] if i > 0 else None
        c = day_diff(hist, nat, days[i], prev, names) if prev else dict(as_of=days[i], national={}, movers=[])
        if not prev:
            n1 = nat[nat["as_of"] == days[i]].iloc[-1]
            c["national"] = {k: dict(now=float(n1[k]), before=None) for k in ("sen_p_dem", "house_p_dem")
                             if k in n1 and pd.notna(n1[k])}
        title, desc = describe(c)
        pub = dt.datetime.fromisoformat(days[i]).replace(hour=12, tzinfo=dt.timezone.utc)
        items.append(f"<item><title>{escape(title)}</title><link>{SITE_URL}/</link>"
                     f"<guid isPermaLink=\"false\">forecast-{days[i]}</guid><pubDate>{format_datetime(pub)}</pubDate>"
                     f"<description>{escape(desc)}</description></item>")
    feed = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>Open Forecast 2026</title><link>{SITE_URL}/</link>"
            "<description>Daily updates to an independent, open-methodology forecast of the 2026 U.S. elections.</description>"
            "<language>en-us</language>" + "".join(items) + "</channel></rss>")
    (SITE_DATA.parent / "feed.xml").write_text(feed, encoding="utf-8")
    print("changes:", len(latest["movers"]), "movers; feed items:", len(items))


if __name__ == "__main__":
    main()
