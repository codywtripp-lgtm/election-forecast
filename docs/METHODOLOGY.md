# Methodology

## Launch status (October 2026)

What is live, and what is not yet (no number on the site comes from anything in the "not yet" column):

| Component | Live now | Not yet / simplified |
|---|---|---|
| Pollster ratings (§1) | Fit on ~17,800 final-21-day polls with results, 1998–2024 | Transparency checklist is AAPOR/Roper membership only |
| Poll adjustments (§2) | Likely-voter shift, partisan-sponsor correction, house effects, recency + generic-ballot trend, sample-size cap, herding penalty, ranked-choice transfers | — |
| Weighting-method correction (§2.6) | 11 of the most prolific pollsters hand-coded from their own methodology statements (≈40% of 2026 polls); class corrections estimated from 2025 NJ/VA governor polls and fed into house-effect priors | Few coded pollsters in completed races → corrections heavily shrunk (sd ≈ 1.3–1.7 pts); 2022-midterm comparison not done (G5) |
| National environment (§4.1) | Our generic-ballot average (400+ polls) | Approval / midterm-penalty / economy regression not yet fit (needs 1946–2022 history, G9); a month out the generic ballot dominates it |
| Race prior (§4.2) | Partisan lean, national environment, incumbency (fit 2000–2024, recent cycles weighted more) | Candidate quality and fundraising not yet in (G8, S13) |
| Turnout scenarios (§5) | Three scenarios in every simulation, toggle on the site | Launch version sizes the scenarios from the measured likely-vs-registered-voter gap, not yet from CPS/CES group turnout |
| Simulation (§6) | 50,000 correlated draws; national, 9 regional, 4 demographic factors (ACS 2024), Student-t; GA runoff, AK/ME RCV, independents | — |
| Validation (§7) | As-of backtest 2010–2024, leave-one-cycle-out scoring, published on this page | — |
| House (§4.2, §6) | All 435 districts: district lean on the 2026 lines (The Downballot's presidential-by-district results), national environment, incumbency (fit on 2,619 contested races 2012–2024), polls where they exist (~50 districts), same correlated simulation; uncontested and same-party top-two seats fixed | Candidate quality/fundraising not in; ACS district demographics are on the old lines for the 10 redrawn states (state-level demographics used there) |

Numbers below marked "start" were the pre-fit design values; fitted values are recorded in `data/model/` and in each run's manifest.

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

γ is estimated from paired releases (same pollster, same field period, both RV and LV toplines). **The sign is not assumed.** Fitted values:

- History (538 archive): LV − RV = −1.25 (2018), −1.64 (2022), −0.24 (2024) points (negative = LV more Republican).
- 2026 paired releases so far: **+0.91 ± 0.36** (LV *more Democratic*, consistent with high-propensity voters shifting toward Democrats since 2024).
- Model: prior N(−0.9, 1.0²) updated with the current-cycle pairs → about **+0.7 ± 0.34** today; it updates automatically as more pairs arrive.

Adults → RV: +0.4 (2018–2024 paired average). **[A5, high]**

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
- an additive correction toward the opposing party, fit from historical sponsored-vs-independent residuals (fitted 2014–2024: Democratic-sponsored polls ran **2.8 pts** more Democratic than the field, Republican-sponsored **3.9 pts** more Republican), and
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

**As implemented (Oct 2026).**

*Classes* (coded from each pollster's own published methodology; `data/manual/weighting_method.csv` lists the statement and date for every code): **PV** weights to recalled past presidential vote · **PID** weights to party ID / registration / voter-file party but not recalled vote · **DEMO** demographics only · **UNK** not coded. Coded so far: PV — YouGov, Morning Consult, Ipsos, UNH, Change Research, Marquette; PID — Emerson, NYT/Siena (voter-file party + modeled past vote), Echelon, Quantus; DEMO — Fox News (Beacon/Shaw). Joint polls take a class only if all partners share it.

*Estimation.* Completed 2025–26 races with results (so far the 2025 New Jersey and Virginia governor races, polls in the final 35 days). The **pollster** is the unit (one pollster's many polls count once, with variance τ_h² + σ²/n). For each class, the difference between its mean error and the all-pollster mean error is shrunk toward 0 with prior N(0, 2²).

At launch: every 2025 poll underestimated the Democrats (field mean error −7.6 pts). Relative to that field, the one coded PV pollster ran +5.2 more Democratic (shrunk to **δ_PV = +1.5 ± 1.7**), PID −0.2 (→ −0.1 ± 1.3), DEMO −0.5 (→ −0.2 ± 1.6). These rest on 5 coded pollsters, so they are weak evidence and are treated that way.

*How it is applied.* Only differences between classes are identifiable from polls alone, so δ enters each pollster's **house-effect prior** (prior mean = historical bias + δ_class, prior variance = 2² + sd_class²), centred so the class corrections average to zero across today's polls. Pollsters with many 2026 polls are judged mostly by their own current house effect; thinly polled ones lean on their class. The 2025 field-wide miss is **not** imported as a directional correction (same rule as the national polling error). Effect at launch: Democratic Senate-control odds +0.5 pts.

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

**Launch status:** N̂ = our adjusted generic-ballot average (likely-voter basis, house effects, sponsor corrections). The approval/midterm-penalty/economy regression is not fit yet (G9). The published backtest scores use this same generic-ballot-only N̂, and the error in N̂ is part of the national error term.

Special-election overperformance (2025–26 results vs. baseline partisanship) enters as an extra signal on N with a weight fit on 2017–18 and 2021–22. **[A12, med]**

**Tested Oct 2026, not used.** Data: The Downballot's special-election Big Boards, 2017–2026 (every contested state-legislative and congressional special, swing vs. the newest presidential result in the district). Model: N − national presidential margin = k · median swing of specials held before Oct 1, fit on 2018–2024, leave-one-cycle-out error **7.2 pts** (the generic ballot's is ≈2.9); blended by inverse variance (error variance shrunk toward a 6-pt prior). In the as-of backtest the blend made every metric slightly worse (e.g. Brier 0.0439 → 0.0440 at 30 days, MAE +0.05 to +0.15 pts), so the forecast uses the generic ballot alone. 2024 is the cautionary case: Democrats ran 4.5 pts ahead in specials and lost the House vote by 2.6. Specials are shown on the Trackers page (2025–26 median swing D+13).

### 4.2 Race-level prior
```
m_r,prior = λ_office · lean_r + N + inc_r + quality_r + money_r + regional_r
```
- `lean_r`: partisan lean = weighted 2024 (0.75) and 2020 (0.25) presidential margin relative to national, **on the 2026 lines** for House districts. **[A13, med]**
- `λ_office`: how strongly the office follows partisanship. ~1 for House, < 1 for Senate, notably < 1 for governors (governors routinely win against lean). Fit per office. **[A14, med]**
- `inc_r`: incumbency advantage, fit per office and decaying by cycle (it has shrunk sharply since the 1990s). **[A15, med]**
- `quality_r`: challenger held prior elected office (state legislature / statewide / congressional), coded per candidate. **[A16, low]**
- `money_r`: log ratio of candidate receipts (FEC). Endogenous (money follows expected competitiveness), so we cap its coefficient and test robustness. **[A17, med]**

Coefficients fit on 2000–2024 contested D-vs-R races, weighted 0.8× per cycle back (incumbency was worth much more in the 2000s). Fitted at launch:

| | constant | lean | N | incumbency | residual s.d. | races |
|---|---|---|---|---|---|---|
| Senate | +1.8 | 0.80 | 0.78 | ±8.4 | 10.0 | 416 |
| Governor | −2.5 | 0.44 | 0.59 | ±13.4 | 13.8 | 255 |
| House | +1.0 | 0.92 | 0.77 | ±5.4 | 6.9 | 2,619 |

House lean uses the presidential results on each cycle's own district lines (2012–2024 lines for the fit, 2026 lines for the forecast). In the 10 states redrawn for 2026 only 2024 results exist on the new lines; 2020 is imputed from 2024 plus the state's 2020→2024 shift (flag `lean_2020_imputed`). Missouri uses its 2022 map (the 2025 map is blocked).

Quality and fundraising terms are not in the launch version (G8, S13).

**Incumbent strength (added Oct 3, Senate and governor).** inc_over = the incumbent's last winning margin − that cycle's state lean − that cycle's national House margin (capped at ±60), 0 for open seats. It captures candidates who run far ahead of their party (e.g. Vermont's Phil Scott, about 78 points ahead of partisanship in 2024). Fitted coefficients: governor ≈ 0.48 (s.e. 0.10), Senate ≈ 0.26 (s.e. 0.07); fundamentals error fell from 13.8 to 12.3 pts (governor) and 10.0 to 9.6 (Senate). Backtest: governor Brier −8.5% at 120 days and −6% at 60 days, Senate −1–2%, election-eve neutral. Not used for the House (district lines change too often for a clean comparison). [A16]

**Fundraising (added Oct 3, House only).** money = log((D + $5k)/(R + $5k)) of the nominees' *individual* contributions (FEC bulk all-candidate summaries, public domain; self-funding, loans and transfers excluded), matched by state, district and last name; an unmatched nominee → treated as even. Fitted House coefficient ≈ 0.9 pts per log unit (a 3:1 money edge ≈ 1 pt). Backtest: House Brier −3% at 30 days, −4% at 120 days; Senate mixed, so not used there; governors have no FEC data. **Caveat:** historical FEC files are end-of-cycle totals (they include October–December money), so the backtest gain is somewhat optimistic; the 2026 file is as of the latest filings and refreshes daily. [A17] Independents running as the main non-Republican (Idaho, Montana, Nebraska, South Dakota Senate) use the same Senate equation, a simplification covered by the wide uncertainty on those races.

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

**Launch version (simplified, labelled on the site).** The group-level build above needs CPS + CES state tables that are not ingested yet (G10). Until then, each scenario is a uniform margin shift anchored on the one direct 2026 measurement of who turns out, the likely-voter vs registered-voter gap γ (§2.2):

| Scenario | Shift (points toward D) | Weight |
|---|---|---|
| S1 2024-like electorate | −(\|γ\| + se)·sign(γ) ≈ −1.0 | 0.25 |
| S2 typical midterm (what LV screens assume) | 0 | 0.50 |
| S3 high-engagement midterm | +(\|γ\| + se)·sign(γ) ≈ +1.0 | 0.25 |

Weights are not yet updated from special-election or primary turnout. In the launch run, Democratic Senate control moves from about 49% (S1) to 73% (S3), so this is a high-sensitivity assumption.

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

**Comparisons:** our model vs. polls-only, fundamentals-only, and expert ratings (benchmark only, converted to probabilities by a published mapping — DATA_GAPS G11; not built yet).

**Update (Oct 3, 2026): the House is now in the backtest** (2,273 district-races 2014–2024; full poll histories 2018–2024, final-weeks polls 2014–2016; House fundamentals fit only on earlier cycles; backtest districts use their state's demographics because historical district lines differ from the ACS lines). Error sizes are now fit jointly on all three offices: national 2.8, regional 1.0, demographic 1.05, race-level poll error 5.0 (Election Day s.d.), T₀ = 120 days. Leave-one-cycle-out scores:

| Office | Races (1 day out) | Brier 30 days | Brier 1 day | Winner right | 80% range covers |
|---|---|---|---|---|---|
| Senate | 258 | 0.045 | 0.040 | 94% | 86% |
| Governor | 187 | 0.039 | 0.056 | 92% | 80% |
| House | 2,273 | 0.029 | 0.028 | 96% | 85% |

House calibration: forecasts of 60–70% came true 52–62% of the time (slightly overconfident in that band); elsewhere close to the diagonal. The joint refit moved Democratic Senate-control odds from 60% to 57% on Oct 3.

**Results at launch (leave-one-cycle-out, Senate + governor, 2010–2024):**

| | Brier | Log loss | Winner right | 80% range covers |
|---|---|---|---|---|
| Model, 1 day out | 0.047 | 0.156 | 93% | ~80% |
| Model, 30 days out | 0.044 | 0.149 | 93% | 82% |
| Model, 120 days out | 0.060 | 0.206 | 92% | 90% |
| Polls only (polled races) | 0.060 | 0.197 | 92% | 81% |
| Model on the same polled races | 0.052 | 0.174 | 92% | 81% |
| Fundamentals only | 0.080 | 0.262 | 88% | 90% |

Fitted error structure (Election Day s.d., points): national 2.8, regional 0.6, demographic 2.1, race-level poll error 4.0; growth with time T₀ = 120 days; Student-t ν = 5. The weekly backtest job refits these and the methodology page always shows the current values.

**Known weakness:** national poll misses by cycle were +0.1, +3.1, −3.7, −3.9, +0.1, −6.6, −1.9, −3.6 (2010→2024; negative = polls too Democratic). Because most recent misses ran the same way, Democrats forecast at 10–40% won less often than predicted. We do **not** add a directional correction, because the sign flipped in 2012 and 2018. The size of these misses is carried by the national error term instead.

**Publication:** calibration charts and metrics on the methodology page, regenerated by the backtest job.

---

## 8. Sensitivity analysis

**Live:** `pipeline/sensitivity.py` re-runs the day's forecast under the variants below and publishes the table on the methodology page (refreshed weekly with the backtest). At launch, Democratic Senate-control odds ranged from 48% (2024-like electorate) to 72% (high-engagement midterm), and fell to 52% if the historical midterm likely-voter shift (R+1.45) were used instead of the 2026 evidence; error-size and tail-shape changes moved them by 1–3 points.

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
