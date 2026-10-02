"""Our own pollster ratings (METHODOLOGY §1).

Inputs: final-21-day polls with certified results — 538 raw_polls (1998–2022) + 2024 polls from the
538 archive scored against 2024 results. For each poll in a race with ≥3 polls:

    e_i = poll margin − actual margin
    r_i = e_i − (mean error of the *other* polls in that race)      # relative to the field

Per pollster p (recent cycles weighted more):
    bias_p   = shrunk mean of r_i                                     (house effect prior)
    tau2_p   = shrunk excess variance: E[r_i²] − sampling var − var of the LOO field mean
    herding  = E[r_i²] / expected E[r_i²]  (≪ 1 → results hug the field)

Shrinkage: x̂ = (n_eff·x_raw + k·x_group)/(n_eff + k); group = AAPOR/Roper transparency members vs not.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.config import DB, RAW
from pipeline.model.data import pres_margins, sampling_var
from pipeline.normalize.polls import pollster_key

CYCLE_DECAY = 0.85        # per 2-year cycle back from the newest  [A1]
MIN_RACE_POLLS = 3
HERD_THRESHOLD = 0.5      # [A3]
HERD_MIN_N = 10
TYPE_MAP = {"Sen-G": "sen", "Gov-G": "gov", "Pres-G": "pres", "House-G": "house", "House-G-US": "generic"}


def _dside_margin(r: pd.DataFrame) -> pd.DataFrame:
    """raw_polls stores cand1 − cand2; convert to DEM − REP where both are present."""
    d1 = r["cand1_party"].eq("DEM") & r["cand2_party"].eq("REP")
    d2 = r["cand1_party"].eq("REP") & r["cand2_party"].eq("DEM")
    sign = np.where(d1, 1.0, np.where(d2, -1.0, np.nan))
    out = r.assign(poll_margin=sign * (r["cand1_pct"] - r["cand2_pct"]),
                   actual_margin=sign * (r["cand1_actual"] - r["cand2_actual"]))
    return out.dropna(subset=["poll_margin", "actual_margin"])


def historical_errors() -> pd.DataFrame:
    r = pd.read_csv(RAW / "fte_archive" / "raw_polls.csv.gz")
    r = r[r["type_simple"].isin(TYPE_MAP)]
    r = _dside_margin(r)
    df = pd.DataFrame({
        "race": r["race_id"].astype(str), "cycle": r["cycle"], "office": r["type_simple"].map(TYPE_MAP),
        "pollster": r["pollster"], "pollster_key": r["pollster"].map(pollster_key),
        "methodology": r["methodology"], "aapor": r["aapor_roper"].astype(str).eq("True"),
        "partisan": r["partisan"].fillna(""), "n": r["samplesize"],
        "days_out": r["time_to_election"], "poll_margin": r["poll_margin"], "actual_margin": r["actual_margin"],
    })
    return pd.concat([df, errors_2024()], ignore_index=True)


def errors_2024() -> pd.DataFrame:
    """2024 polls (last 21 days) from the 538 archive vs 2024 results (Senate, governor, president)."""
    from pipeline.model.data import one_question_per_poll, question_margins

    q = pd.read_parquet(DB / "questions.parquet")
    a = pd.read_parquet(DB / "answers.parquet")
    q = q[(q["cycle"] == 2024) & (q["source"] == "538") & q["office"].isin(["sen", "gov", "pres"])
          & (q["stage"] == "general") & ~q["hypothetical"]]
    q = q.assign(days_out=(pd.Timestamp("2024-11-05") - pd.to_datetime(q["end_date"])).dt.days)
    q = q[q["days_out"].between(0, 21)]
    m = one_question_per_poll(question_margins(q, a))
    res = pd.read_parquet(DB / "results_races.parquet")
    actual = res[res["cycle"] == 2024].set_index("race_id")["margin"].to_dict()
    pm = pres_margins()
    for _, row in pm[pm["year"] == 2024].iterrows():
        actual[f"2024-pres-{row['state']}"] = row["margin"]
    actual["2024-pres-US"] = float(pm[pm["year"] == 2024]["nat_margin"].iloc[0])
    m["actual_margin"] = m["race_id"].map(actual)
    m = m.dropna(subset=["actual_margin"])
    return pd.DataFrame({
        "race": m["race_id"], "cycle": 2024, "office": m["office"], "pollster": m["pollster"],
        "pollster_key": m["pollster_key"], "methodology": m["mode"], "aapor": np.nan,
        "partisan": m["partisan"].fillna(""), "n": m["sample_size"], "days_out": m["days_out"],
        "poll_margin": m["margin"], "actual_margin": m["actual_margin"],
    })


def relative_errors(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["e"] = df["poll_margin"] - df["actual_margin"]
    df["sv"] = sampling_var(df["n"])
    g = df.groupby("race")
    df["m"] = g["e"].transform("size")
    df = df[df["m"] >= MIN_RACE_POLLS].copy()
    g = df.groupby("race")
    df["loo_mean"] = (g["e"].transform("sum") - df["e"]) / (df["m"] - 1)
    df["r"] = df["e"] - df["loo_mean"]
    newest = df["cycle"].max()
    df["w"] = CYCLE_DECAY ** ((newest - df["cycle"]) / 2)
    return df


def fit(df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    df = relative_errors(historical_errors() if df is None else df)
    # transparency group from the latest known AAPOR/Roper flag per pollster
    aapor = df.dropna(subset=["aapor"]).groupby("pollster_key")["aapor"].last()
    df["group"] = df["pollster_key"].map(aapor).map({True: "aapor", False: "other"}).fillna("other")

    # global non-sampling variance of a poll around the truth-minus-field-error
    tau2_global = max(1.0, float(np.average(df["r"] ** 2 - df["sv"], weights=df["w"])))
    # expected r² for a poll with no extra error and no herding: own sv + tau2 + LOO mean variance
    df["exp_r2"] = df["sv"] + tau2_global + (df["sv"].mean() + tau2_global) / (df["m"] - 1)
    df["excess"] = df["r"] ** 2 - df["exp_r2"] + tau2_global   # unbiased-ish estimate of tau2_p per poll
    # herding: spread vs what sampling noise alone would produce (a real pollster can't beat that)
    df["exp_r2_sampling"] = df["sv"] + df["sv"].mean() / (df["m"] - 1)

    group_tau2 = df.groupby("group").apply(lambda g: np.average(g["excess"], weights=g["w"])).clip(lower=1.0)
    group_bias = pd.Series(0.0, index=group_tau2.index)

    agg = df.groupby("pollster_key").apply(lambda g: pd.Series({
        "pollster": g["pollster"].iloc[-1],
        "n": len(g), "n_eff": g["w"].sum(),
        "bias_raw": np.average(g["r"], weights=g["w"]),
        "tau2_raw": np.average(g["excess"], weights=g["w"]),
        "herd_ratio": float(np.average(g["r"] ** 2, weights=g["w"]) / np.average(g["exp_r2_sampling"], weights=g["w"])),
        "group": g["group"].iloc[-1],
        "last_cycle": g["cycle"].max(),
        "mode": g["methodology"].dropna().iloc[-1] if g["methodology"].notna().any() else "unknown",
    }), include_groups=False).reset_index()

    k_bias, k_tau = shrinkage_k(agg, df)
    gt = agg["group"].map(group_tau2)
    gb = agg["group"].map(group_bias)
    agg["bias"] = (agg["n_eff"] * agg["bias_raw"] + k_bias * gb) / (agg["n_eff"] + k_bias)
    agg["tau2"] = ((agg["n_eff"] * agg["tau2_raw"] + k_tau * gt) / (agg["n_eff"] + k_tau)).clip(lower=0.5)
    agg["shrink_weight"] = agg["n_eff"] / (agg["n_eff"] + k_tau)
    agg["herding"] = (agg["herd_ratio"] < HERD_THRESHOLD) & (agg["n"] >= HERD_MIN_N)
    params = dict(tau2_global=tau2_global, k_bias=k_bias, k_tau=k_tau,
                  group_tau2=group_tau2.to_dict(), n_polls=len(df), n_races=df["race"].nunique())
    return agg.sort_values("n", ascending=False), params


def shrinkage_k(agg: pd.DataFrame, df: pd.DataFrame) -> tuple[float, float]:
    """Method of moments: k = (within-pollster variance per poll) / (between-pollster variance)."""
    big = agg[agg["n"] >= 10]
    within_b = float(np.average(df["r"] ** 2, weights=df["w"]))           # var of one r_i
    between_b = max(1e-3, float(big["bias_raw"].var() - (within_b / big["n_eff"]).mean()))
    within_t = float(df["excess"].var())
    between_t = max(1e-3, float(big["tau2_raw"].var() - (within_t / big["n_eff"]).mean()))
    return float(np.clip(within_b / between_b, 2, 200)), float(np.clip(within_t / between_t, 2, 200))


def lookup(ratings: pd.DataFrame, params: dict, pollster: str) -> dict:
    """Rating for a (possibly joint 'A/B') pollster. Unknown pollsters get the 'other' group prior."""
    by_key = ratings.set_index("pollster_key")
    key = pollster_key(pollster)
    if key in by_key.index:
        row = by_key.loc[key]
        return dict(bias=float(row["bias"]), tau2=float(row["tau2"]), herding=bool(row["herding"]),
                    rated=True, n=int(row["n"]))
    parts = [pollster_key(p) for p in str(pollster).split("/")]
    hits = [by_key.loc[p] for p in parts if p in by_key.index]
    if hits:
        return dict(bias=float(np.mean([h["bias"] for h in hits])), tau2=float(np.mean([h["tau2"] for h in hits])),
                    herding=any(bool(h["herding"]) for h in hits), rated=True, n=int(sum(h["n"] for h in hits)))
    return dict(bias=0.0, tau2=float(params["group_tau2"].get("other", params["tau2_global"])),
                herding=False, rated=False, n=0)


def main() -> None:
    ratings, params = fit()
    ratings.to_parquet(DB / "pollster_ratings.parquet", index=False)
    print(params)
    print(ratings.head(25)[["pollster", "n", "bias", "tau2", "herd_ratio", "herding", "group"]].round(2).to_string())


if __name__ == "__main__":
    main()
