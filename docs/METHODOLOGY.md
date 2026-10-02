# Methodology (draft for review)

Status: **design only — nothing here has been fit yet.** Numbers in this document are *priors or starting values*, labelled as such. Every one gets replaced by a backtest-fitted value (or confirmed) before the forecast is published, and the fitted value is logged with its run.

Every modeling assumption is tagged **[A#]** with a sensitivity rating:
- **low** — plausible alternatives move race probabilities < 1 pt and chamber odds < 1 pt
- **med** — moves close races by a few points, chamber odds 1–5 pts
- **high** — can move chamber odds > 5 pts; gets a published sensitivity run

The full assumption register is at the end (§9).

Hard rules that shape the model:
- No prediction markets anywhere — not as input, benchmark, or display.
- Expert ratings (Cook, Sabato, Inside Elections) are a **benchmark only**, never an input.
- Every published number traces to a run manifest (code SHA + input snapshot hashes). See ARCHITECTURE.md.

---

## 0. Quantity being forecast

For a standard two-major-party race *r*, the core quantity is the **two-party Democratic margin** `m_r = D% − R%` (in points, of the two-party vote). Third-party/independent share is modeled separately as `o_r` and the full vote shares are recovered from (`m_r`, `o_r`). Races that don't fit this frame (top-two same-party, strong independents, RCV, runoffs) are handled in §6.

Win probability = share of simulations in which the candidate wins under that race's rules.

---

## 1. Pollster ratings (our own)

**Data:** 538 `raw-polls.csv` (polls in the final 21 days of races 1998–2024, with certified results) — the open archive left after 538 shut down. Extended with 2025–26 special/off-year polls we collect.

**Error model.** For poll *i* by pollster *p* in race-cycle *c*:

```
e_i = (poll margin_i − actual margin_c)
e_i = η_c + b_p + ε_i ,   ε_i ~ N(0, s_i² + σ_p²)
```

- `η_c` — race-level shared error (all pollsters missed the same way). Removing it is what lets us judge a pollster *relative to the field* rather than punishing everyone polling a race that broke late.
- `b_p` — pollster **bias** (signed, systematic lean).
- `s_i²` — pure sampling variance from sample size.
- `σ_p` — pollster's **excess error** beyond sampling. This is the main "accuracy" score.

**Shrinkage.** Pollsters with few polls are pulled toward a group mean (empirical Bayes):

```
σ̂_p = w_p · raw_p + (1 − w_p) · group_mean ,   w_p = n_p / (n_p + k)
```

`k` is fit by method of moments on the archive. The group mean depends on transparency (below), so a new transparent pollster starts better than a new opaque one. **[A1, med]** — k and the group structure.

**Transparency.** Ordinal 0–3 from a disclosure checklist: publishes topline + crosstabs; discloses mode and field dates; discloses weighting targets; AAPOR Transparency Initiative member / Roper archive. Hand-coded (DATA_GAPS G7). **[A2, low]**

**Herding.** For each pollster, compare the spread of its results around the contemporaneous polling average to the spread expected from sampling alone:

```
H_p = observed variance of (poll − average) / expected sampling variance
```

`H_p` well below 1 (we start at < 0.5 with ≥ 10 polls) indicates clustering on the average. Herding pollsters get a weight penalty (they add less independent information), not a bias correction. **[A3, low]**

**Output:** a rating table (bias, excess error, transparency, herding flag, n, shrinkage weight) published on the methodology page.

---

## 2. Poll adjustments

Applied in this order; each poll's adjusted margin and weight are stored with a per-step breakdown so the race page can show *why* a poll has the weight it has.

### 2.1 House effects (current cycle)
Within the cycle, each pollster's systematic lean relative to the average of other pollsters on the same races/dates, fit hierarchically:

```
h_p ~ N(δ_class(p), τ_h²)
```

i.e. house effects are centred on their **methodology class** correction (§2.6), so the two don't double-count: δ captures what a whole class of methods does, `h_p` captures what this pollster does beyond its class. A pollster with few current polls falls back to its historical bias `b_p` (shrunk). **[A4, med]**

### 2.2 Population → likely voters
RV and adult samples are shifted to an LV basis:

```
adj_LV = margin_RV + γ(cycle_type, president_party)
```

γ is estimated from paired releases (same pollster, same field period, both RV and LV toplines) in the 538 archive, separately for midterms. Historically the LV screen helped the out-party/GOP in midterms; in 2026 the president's party is Republican, and recent cycles suggest the higher-propensity electorate has shifted toward Democrats, so **the sign is not assumed** — it comes from the data, with the 2018/2022 paired polls weighted most. Adult samples get γ_A = γ plus an extra adult→RV step, and a larger variance. **[A5, high]**

### 2.3 Recency
```
w_recency = exp(−age_days / τ(t)) ,   τ shrinks as election day approaches
```
Stale polls are also **trend-adjusted**: shifted by the movement in the national generic-ballot average since they were in the field, scaled by the race's sensitivity to national swing. τ(t) fit by backtest. **[A6, med]**

### 2.4 Sample size
```
w_n = sqrt(min(n, n_cap) / 600)
```
`n_cap` (start: 1,500) stops very large online panels dominating — their real error is driven by non-sampling error, not n. **[A7, low]**

### 2.5 Partisan / campaign sponsors
Polls sponsored by a campaign, party committee, or allied group get:
- an additive correction toward the opposing party, fit from historical sponsored-vs-independent residuals (prior ≈ 2–4 pts), and
- a weight multiplier (start: 0.5).

Sponsor classification is hand-maintained (DATA_GAPS G6). **[A8, med]**

### 2.6 Weighting-method correction (important)
Polls are **not** discarded for weighting to 2024 recalled vote. Each poll gets a methodology class:

| class | description |
|---|---|
| RV24 | weights to recalled 2024 vote (or past vote generally) |
| PID | weights to party ID / registration |
| DEMO | demographics only (incl. education) |
| UNK | not disclosed |

Correction parameter `δ_class` (additive on margin, DEMO = 0 reference) with explicit uncertainty. Estimated from:
1. **2025–26 special and off-year elections** (NJ/VA 2025 governor, special House elections, state supreme court races, etc.): class-level residual of final polls vs. results.
2. **2022 midterm** polls weighted to 2020 recalled vote vs. other classes against certified 2022 results — the closest historical analogue (midterm after a presidential, past-vote weighting).

**Honest caveat:** the 538 archive doesn't record weighting method. Classes must be hand-coded from methodology statements (DATA_GAPS G5). At launch the evidence will be thin, so `δ_class` will be wide:

```
prior: δ_class ~ N(0, 2.0²) for RV24, PID, UNK
posterior: updated with whatever coded polls exist; logged with n and SE
```

In simulation, δ is **drawn per simulation** from its posterior, not fixed — uncertainty about the correction feeds into the forecast spread. It gets a published sensitivity run (§8). **[A9, high]**

### 2.7 Combined weight
```
w_i = rating_p · w_recency · w_n · w_sponsor · w_herding
```
All components are shown on the race page poll table.

---

## 3. Polling average (per race)

A weighted average of adjusted margins, with the shared national trend borrowed for sparse races:

- Each race's average = Σ wᵢ · adj_marginᵢ / Σ wᵢ.
- Its uncertainty `σ_poll,r²` = sampling variance (effective n) + house-effect uncertainty + δ uncertainty + an **average-to-outcome** term that grows with days to election (fit by backtest).
- A race with < 1 effective poll is "fundamentals-led" and labelled as such on the site.

A full state-space model (Kalman/PyMC) is a Phase 3 upgrade; the weighted average with trend adjustment is the launch version because it's debuggable and fast. **[A10, low]**

---

## 4. Fundamentals prior

### 4.1 National environment
Expected national House popular-vote margin:

```
N = β₀ + β₁ · generic_ballot_avg + β₂ · net_approval_avg + β₃ · midterm_penalty(pres_party) + β₄ · econ
```

- generic ballot and approval are our own averages (same machinery as §2–3, using VoteHub + archive polls);
- midterm penalty: the president's party (R in 2026) historically loses ground in midterms;
- econ: real disposable income growth (BEA), unemployment change (BLS). Weak in the literature — we expect a small coefficient and will show it.

Fit on midterms 1946–2022 (approval + generic-ballot history needs hand assembly — DATA_GAPS G9). With ~19 midterms this is a small-sample regression: coefficients are ridge-shrunk and their uncertainty enters the simulation. **[A11, high]**

Special-election overperformance (2025–26 results vs. baseline partisanship) enters as an extra signal on N with a weight fit on 2017–18 and 2021–22. **[A12, med]**

### 4.2 Race-level prior
```
m_r,prior = λ_office · lean_r + N + inc_r + quality_r + money_r + regional_r
```
- `lean_r`: partisan lean = weighted 2024 (0.75) and 2020 (0.25) presidential margin relative to national, **on the 2026 lines** for House districts. **[A13, med]**
- `λ_office`: how strongly the office follows partisanship. ~1 for House, < 1 for Senate, notably < 1 for governors (governors routinely win against lean). Fit per office. **[A14, med]**
- `inc_r`: incumbency advantage, fit per office and decaying by cycle (it has shrunk sharply since the 1990s). **[A15, med]**
- `quality_r`: challenger held prior elected office (state legislature / statewide / congressional), coded per candidate. **[A16, low]**
- `money_r`: log ratio of candidate receipts (FEC). Endogenous (money follows expected competitiveness), so we cap its coefficient and test robustness. **[A17, med]**

Coefficients fit on 2010–2024 races. Prior variance `σ_prior,r²` from backtest residuals by office and days-out.

### 4.3 Blending polls and prior
Precision weighting:

```
μ_r = (m_prior / σ_prior² + m_poll / σ_poll²) / (1/σ_prior² + 1/σ_poll²)
```

This makes the poll weight rise automatically as polls get more numerous / better rated (σ_poll shrinks) and as election day nears (the average-to-outcome term shrinks). Races without polls → μ_r = m_prior. The weight on polls is shown on each race page. **[A18, med]**

---

## 5. Turnout scenario module

The 2026 electorate is modeled as a **distribution over three scenarios**, not a point estimate:

| scenario | definition |
|---|---|
| S1 — 2024-like | composition matches 2024 validated voters |
| S2 — typical midterm | historical midterm drop-off applied: older, higher-propensity, more college-educated, lower young/irregular-voter share |
| S3 — high-engagement midterm | drop-off like 2018: midterm composition but with higher turnout among young and low-propensity voters |

**Building them.** Group-level turnout from Census CPS Voting Supplement (2010–2024) by state × age × education × race; historical midterm/presidential turnout ratios by state; group vote preferences from the Cooperative Election Study (CES, validated vote) 2022 and 2024. A scenario's effect on race *r*:

```
Δm_r(s) = Σ_g (share_g,r(s) − share_g,r(base)) · margin_g,r
```

**Avoiding double counting.** LV polls already embed a turnout model. The scenario shift is applied fully to the fundamentals prior and RV/A polls, and only a fraction `κ` (start 0.5) to LV polls. **[A19, high]**

**Weights.** Prior P(S1, S2, S3) = (0.25, 0.50, 0.25), updated by: 2025–26 special-election turnout vs. baseline, 2026 primary turnout by party, and registration trends where available. The update rule is simple and documented (likelihood from how each indicator behaved in 2010/2014/2018/2022). **[A20, high]**

The forecast integrates over scenarios (each simulation draws a scenario). The race page has a toggle showing the forecast conditional on each scenario. Labeled as a modeling assumption on the methodology page.

---

## 6. Simulation

**Engine:** custom numpy Monte Carlo (≥ 40,000 draws; default 50,000). PyMC/NumPyro is reserved for fitting components offline, not for the daily run. **[A21, low]**

For each simulation *k*:

```
s_k        ~ Categorical(P(S1,S2,S3))
δ_k        ~ posterior of δ_class
national_k ~ σ_nat(t) · t_ν
region_k,j ~ σ_reg(t) · t_ν                     (Census divisions, 9)
demo_k,f   ~ σ_dem(t) · t_ν                     (factors: non-college white, Black, Hispanic, college grad, urbanicity)
race_k,r   ~ σ_race,r(t) · t_ν

m_k,r = μ_r(s_k, δ_k) + national_k + region_k,j(r) + Σ_f L_r,f · demo_k,f + race_k,r
```

- `L_r,f` = race's demographic loadings (district/state share of each group, centred). This is what makes a polling miss with e.g. Hispanic voters move TX, FL, NV, AZ, and the CA/TX House seats together.
- **Fat tails:** Student's t with ν fit by backtest (start ν = 5). **[A22, med]**
- **Shrinking uncertainty:** every σ(t) = σ_ED · sqrt(1 + t / T₀), t = days to election; σ_ED and T₀ fit by backtest. **[A23, med]**
- Error-component sizes (national vs. regional vs. demographic vs. race) fit on 2016–2024 polling misses. **[A24, high]** — correlation structure drives chamber odds more than any single race.

### Special cases
| case | handling |
|---|---|
| **CA, WA top-two** | Candidates in the general are known after the primary. Same-party generals (D vs D) → seat certain for that party; the race page shows the candidate-level contest from polls/prior with wide uncertainty. |
| **AK top-four + RCV** | Simulate first-choice shares for each candidate, then eliminate & transfer with transfer rates from the 2022/2024 AK RCV tabulations. **[A25, med]** |
| **ME RCV** | RCV applies to federal generals (Senate, House) — same transfer logic, transfer rates from 2018–2024 ME tabulations. **Maine's governor general is plurality** (verify). |
| **GA runoffs** | If no candidate > 50% (simulated minor-party share `o_r` matters), a runoff is simulated: same race draw + runoff-specific turnout shift + extra noise. Chamber control can be reported as "decided in runoff" with its probability. Other states with general-election majority rules get the same treatment (to verify per state — DATA_GAPS G12). |
| **Louisiana** | 2026 is the first cycle of closed party primaries for Congress (verify); general-election rules confirmed before modeling. |
| **Strong independents** | Modeled as a three-way race (share via polls + prior), plus a **caucus parameter** (probability they caucus with each party) used for chamber counting. **[A26, med]** |
| **Uncontested seats** | Probability 1 for the sole major-party candidate; still counted in seat totals. |
| **Senate control** | 51 seats, or 50 + VP (VP is Republican). Holdover seats added as fixed counts. |

### Outputs per run
- Per race: win probability per candidate, vote-share distribution (quantiles + histogram bins), μ breakdown (prior, polls, each adjustment, scenario effect).
- National: chamber-control probability, seat histogram, expected seats, governor count distribution, **tipping-point race** (in each simulation, order seats by margin from the winning party's side and take the seat that delivers the majority; report frequencies).
- Time series: every run's toplines appended; forecast history is a chart.

---

## 7. Validation (backtest before trusting anything)

**Cycles:** midterms 2010, 2014, 2018, 2022; presidential 2016, 2020, 2024.

**As-of discipline:** forecasts are re-run as they would have looked on dates before each election (e.g. 90/60/30/14/7/1 days out) using only data dated before the as-of date. Data limitations: full poll time-series in the 538 archive start in ~2018; for 2010/2014 only the final-21-day polls in `raw-polls.csv` are available, so those years validate the **final** forecast only (DATA_GAPS G3).

**Metrics** (by office and days-out): Brier score, log loss, calibration curves (predicted vs. observed win rate in bins), vote-share MAE and interval coverage (80% intervals should cover ~80%).

**Comparisons:** our model vs. polls-only, fundamentals-only, and expert ratings (benchmark only, converted to probabilities by a published mapping — DATA_GAPS G11).

**Publication:** calibration charts and metrics on the methodology page, regenerated by the backtest job.

---

## 8. Sensitivity analysis

Published runs re-computing 2026 toplines (chamber odds, expected seats, top-10 race probabilities) under:
- turnout scenario weights: each scenario at 100%; (0.5, 0.25, 0.25) / (0.25, 0.25, 0.5)
- δ_class: posterior mean ± 1 and ± 2 SE; δ = 0
- LV adjustment γ: ± 1 SE, and γ = 0
- κ (scenario pass-through to LV polls): 0, 0.5, 1
- ν (tail fatness): 3, 5, 10
- error-component split (A24): national share ± 25%

---

## 9. Assumption register

| ID | Assumption | Starting value / approach | Sensitivity | How tested |
|---|---|---|---|---|
| A1 | Pollster rating shrinkage strength & groups | EB, k by method of moments | med | backtest with/without ratings |
| A2 | Transparency score structure | 0–3 checklist | low | rating stability |
| A3 | Herding threshold & penalty | H < 0.5, n ≥ 10 | low | backtest |
| A4 | House effects centred on methodology class | hierarchical | med | backtest; compare un-centred |
| A5 | RV/A → LV shift γ (sign from data) | paired polls, midterms | **high** | sensitivity run |
| A6 | Recency decay τ(t) + trend adjustment | fit | med | backtest |
| A7 | Sample-size cap | n_cap = 1,500 | low | backtest |
| A8 | Partisan sponsor correction | 2–4 pts prior, ×0.5 weight | med | archive residuals |
| A9 | Weighting-method correction δ_class | N(0, 2²) prior → posterior | **high** | sensitivity run |
| A10 | Weighted average (not state-space) | — | low | backtest vs. simple alternatives |
| A11 | National environment regression | ridge on 1946–2022 midterms | **high** | leave-one-cycle-out |
| A12 | Special-election signal weight | fit on 2017–18, 2021–22 | med | leave-one-cycle-out |
| A13 | Lean = 0.75·2024 + 0.25·2020 | fixed | med | try 1.0/0.0, 0.5/0.5 |
| A14 | Office-specific lean coefficient λ | fit | med | backtest |
| A15 | Incumbency advantage (decaying) | fit | med | backtest |
| A16 | Candidate quality = prior elected office | coded | low | backtest |
| A17 | Fundraising coefficient (capped) | fit, capped | med | with/without |
| A18 | Precision-weighted blend | — | med | calibration by days-out |
| A19 | Scenario pass-through to LV polls κ | 0.5 | **high** | sensitivity run |
| A20 | Scenario weights & update rule | (0.25, 0.5, 0.25) prior | **high** | sensitivity run |
| A21 | numpy Monte Carlo, 50k draws | — | low | convergence check (seed variation < 0.5 pt) |
| A22 | Student-t tails | ν = 5 start | med | sensitivity run |
| A23 | Uncertainty vs. time σ(t) | fit | med | calibration by days-out |
| A24 | Error component split / correlation | fit on 2016–2024 misses | **high** | sensitivity run |
| A25 | RCV transfer rates | from AK/ME tabulations | med | AK/ME backtest |
| A26 | Independent caucus probability | per candidate, documented | med | shown on race page |

Known structural limits (stated on the site): only ~7 cycles of good poll data; correlated polling misses are the dominant risk and are hard to estimate from so few cycles; mid-decade redistricting means House lean on the new lines has no track record.
