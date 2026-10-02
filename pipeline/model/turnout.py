"""Turnout scenario module (METHODOLOGY §5) — launch version.

The 2026 electorate is a distribution over three scenarios. The launch version anchors the size of
the composition effect on the one direct, current-cycle measurement we have: how much a likely-voter
screen moves the same poll's margin (LV − RV, estimated from paired 2026 releases, γ ± se).

    S1  2024-like electorate          shift = −(|γ| + se)·sign(γ)   (registered-voter-like electorate)
    S2  typical midterm electorate     shift = 0                      (what LV screens model)
    S3  high-engagement midterm        shift = +(|γ| + se)·sign(γ)   (screen effect amplified)

Weights (prior, not yet updated): 0.25 / 0.50 / 0.25.  [A19, A20 — high sensitivity, published]
Planned upgrade (DATA_GAPS G10): CPS group turnout + CES group preferences per state, and weights
updated from 2025–26 special-election and primary turnout.
"""
from __future__ import annotations

SCENARIOS = [
    dict(key="s1_2024_like", label="2024-like electorate", weight=0.25),
    dict(key="s2_typical_midterm", label="Typical midterm electorate", weight=0.50),
    dict(key="s3_high_engagement", label="High-engagement midterm", weight=0.25),
]


def scenario_shifts(lv: tuple[float, float]) -> tuple[list[float], list[float], list[dict]]:
    gamma, se = lv
    size = abs(gamma) + se
    sign = 1.0 if gamma >= 0 else -1.0
    shifts = [-sign * size, 0.0, sign * size]
    probs = [s["weight"] for s in SCENARIOS]
    meta = [dict(s, shift=round(x, 2)) for s, x in zip(SCENARIOS, shifts)]
    return shifts, probs, meta
