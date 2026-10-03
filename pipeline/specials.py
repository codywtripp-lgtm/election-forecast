"""Special elections vs. presidential baseline (The Downballot's special-elections Big Boards, 2017–2026).

Swing = special-election D−R margin − the most recent presidential D−R margin in the same district
(The Downballot's "Margin Dif." against the newest presidential column). Positive = Democrats ran ahead.

Uses:
  * tracker on the site (every race, rolling median)
  * a second estimate of the national environment (METHODOLOGY §4.1, [A12]):
        N_specials = national presidential margin (last election) + k · median swing
    k fit on past cycles (2018, 2020, 2022, 2024) using only specials held before October 1 of the
    election year, then blended with the generic-ballot estimate by inverse error variance.
Output: data/db/specials.parquet; data/model/specials_signal.json (fit, committed)
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from pipeline.config import DB, MODEL, RAW
from pipeline.model.data import national_house_vote, pres_margins

DIR = RAW / "downballot"
YEARS = range(2017, 2027)
CUTOFF_MD = (10, 1)
PRIOR_SD, PRIOR_DOF = 6.0, 4          # specials counted if held before Oct 1 of the election year
SOURCE = "https://www.the-downballot.com/p/data"


def _pct(x) -> float:
    try:
        return float(str(x).replace("%", "").replace(",", "").strip())
    except ValueError:
        return np.nan


def parse_board(year: int) -> pd.DataFrame:
    raw = pd.read_csv(DIR / f"specials_{year}.csv", header=None, dtype=str)
    hdr_i = raw.index[raw.apply(lambda r: r.astype(str).str.strip().eq("Date").any(), axis=1)][0]
    hdr = raw.loc[hdr_i].astype(str).str.strip().tolist()
    body = raw.loc[hdr_i + 1:]
    c_date, c_state, c_dist = hdr.index("Date"), hdr.index("State"), hdr.index("District")
    c_held, c_win = hdr.index("Held By"), hdr.index("Winner")
    c_margin = hdr.index("Margin")                           # special-election margin (first 'Margin')
    c_dif = hdr.index("Margin Dif.")                         # vs newest presidential baseline
    c_pres = c_dif - 1                                       # that baseline's margin
    rows = []
    for _, r in body.iterrows():
        date = pd.to_datetime(str(r[c_date]).strip(), format="%d-%b-%y", errors="coerce")
        if pd.isna(date):
            continue
        rows.append(dict(date=date.date(), state=str(r[c_state]).strip(), district=str(r[c_dist]).strip(),
                         held_by=str(r[c_held]).strip("() "), winner=str(r[c_win]).replace("✓", "").strip("() "),
                         flip="✓" in str(r[c_win]),
                         margin=_pct(r[c_margin]), pres_margin=_pct(r[c_pres]), swing=_pct(r[c_dif]),
                         official=str(r[0]).strip().lower() == "x", board_year=year))
    return pd.DataFrame(rows).dropna(subset=["swing"])


def all_boards() -> pd.DataFrame:
    return pd.concat([parse_board(y) for y in YEARS if (DIR / f"specials_{y}.csv").exists()], ignore_index=True)


def cycle_signal(df: pd.DataFrame, cycle: int, as_of: dt.date | None = None) -> dict:
    """Median swing of specials in the two years before an election, up to the as-of date."""
    start = dt.date(cycle - 1, 1, 1)
    end = as_of or dt.date(cycle, *CUTOFF_MD)
    g = df[(df["date"] >= start) & (df["date"] < end)]
    return dict(cycle=cycle, n=int(len(g)), median_swing=float(g["swing"].median()) if len(g) else np.nan,
                mean_swing=float(g["swing"].mean()) if len(g) else np.nan)


def nat_pres(cycle: int) -> float:
    pm = pres_margins()
    last = max(y for y in pm["year"].unique() if y < cycle)
    return float(pm[pm["year"] == last]["nat_margin"].iloc[0])


def fit(df: pd.DataFrame) -> dict:
    """N_true − nat_pres_last = k · median_swing ; k by least squares through the origin (one parameter,
    four cycles). Residual s.d. from leave-one-out predictions."""
    rows = []
    for c in (2018, 2020, 2022, 2024):
        s = cycle_signal(df, c)
        rows.append(dict(s, nat_pres=nat_pres(c), N_true=float(national_house_vote()[c])))
    t = pd.DataFrame(rows)
    t["y"] = t["N_true"] - t["nat_pres"]
    x, y = t["median_swing"].to_numpy(), t["y"].to_numpy()
    k = float(x @ y / (x @ x))
    loo = []
    for i in range(len(t)):
        m = np.arange(len(t)) != i
        ki = float(x[m] @ y[m] / (x[m] @ x[m]))
        loo.append(y[i] - ki * x[i])
    t["loo_err"] = loo
    return dict(k=k, loo_sd=float(np.sqrt(np.mean(np.square(loo)))), cycles=t.round(3).to_dict(orient="records"))


CURRENT_TABS = {2025: "415249345", 2026: "1173601967"}
BOARD_ID = "1JGk1r1VXnxBrAIVHz1C5HTB5jxCO6Zw4QNPivdhyWHw"


def download_current() -> None:
    """Refresh the 2025–26 Big Board tabs (older cycles are frozen files in the repo)."""
    from pipeline.ingest.snapshot import SESSION
    for year, gid in CURRENT_TABS.items():
        try:
            r = SESSION.get(f"https://docs.google.com/spreadsheets/d/{BOARD_ID}/export",
                            params={"format": "csv", "gid": gid}, timeout=60)
            r.raise_for_status()
            if b"Margin Dif." in r.content:          # sanity check before overwriting
                (DIR / f"specials_{year}.csv").write_bytes(r.content)
        except Exception as exc:                       # keep yesterday's file; the run must not fail on this
            print(f"specials {year}: download failed ({exc}); using the saved copy")


def main(download: bool = True) -> None:
    if download:
        download_current()
    df = all_boards()
    DB.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DB / "specials.parquet", index=False)
    f = fit(df)
    now = cycle_signal(df, 2026, as_of=dt.date.today())
    f["current"] = dict(now, nat_pres=nat_pres(2026), N_specials=nat_pres(2026) + f["k"] * now["median_swing"])
    f["source"] = SOURCE
    (MODEL / "specials_signal.json").write_text(json.dumps(f, indent=1, default=float))
    print(json.dumps(f, indent=1, default=float))


if __name__ == "__main__":
    main()


def national_blend(gb: float, gb_sd: float, cycle: int, as_of: dt.date, df: pd.DataFrame | None = None,
                   exclude_cycle: int | None = None) -> dict:
    """Inverse-variance blend of the generic-ballot environment with the special-election estimate.
    For backtests, k is refit without the cycle being forecast (exclude_cycle)."""
    df = all_boards() if df is None else df
    s = cycle_signal(df, cycle, as_of=as_of)
    if not s["n"] or np.isnan(s["median_swing"]):
        return dict(N=gb, w_specials=0.0, N_specials=None, n_specials=0)
    rows = [c for c in (2018, 2020, 2022, 2024) if c != exclude_cycle and c < cycle]
    if len(rows) < 2:
        return dict(N=gb, w_specials=0.0, N_specials=None, n_specials=s["n"])
    x = np.array([cycle_signal(df, c)["median_swing"] for c in rows])
    y = np.array([float(national_house_vote()[c]) - nat_pres(c) for c in rows])
    k = float(x @ y / (x @ x))
    # [A12] error variance shrunk toward a prior (6 pts, worth 4 cycles): 2–4 cycles can't pin it down
    s2 = float(np.mean((y - k * x) ** 2) * len(rows) / max(1, len(rows) - 1))
    resid_sd = float(np.sqrt((len(rows) * s2 + PRIOR_DOF * PRIOR_SD ** 2) / (len(rows) + PRIOR_DOF)))
    ns = nat_pres(cycle) + k * s["median_swing"]
    w = (1 / resid_sd ** 2) / (1 / resid_sd ** 2 + 1 / gb_sd ** 2)
    return dict(N=(1 - w) * gb + w * ns, w_specials=w, N_specials=ns, n_specials=s["n"],
                median_swing=s["median_swing"], k=k, specials_sd=resid_sd)
