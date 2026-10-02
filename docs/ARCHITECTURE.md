# Architecture (draft for review)

Goal: one engine that serves 2026 midterms at launch and later cycles (2027 specials/off-year, 2028 primaries + general) **without schema changes**. Everything published traces back to code + versioned inputs.

## Constraints that shape it
- The owner's machine has no Node or Python. **All builds, tests, model runs and site builds run in GitHub Actions.**
- Free hosting, no new accounts: GitHub repo + GitHub Actions + GitHub Pages.
- Public repo: **no private data, ever.** Anything private (e.g. future subscriber lists) lives in a separate private repo/store; this repo only reads public sources.

## Stack
| layer | choice | why |
|---|---|---|
| Pipeline + model | Python 3.12, pandas, numpy, scipy; PyMC only for offline fitting | fast daily run, easy to debug |
| Storage | **DuckDB + Parquet** committed to the repo; dated raw snapshots | simpler than Postgres, versioned by git, no server |
| Orchestration | GitHub Actions (cron + manual) | free, already used by the owner |
| Frontend | **SvelteKit + TypeScript + D3**, `adapter-static` | small bundles, fully static, D3 fits naturally |
| Hosting | GitHub Pages | same as market-tracker; can move to Cloudflare Pages later without code changes |

## Repo layout
```
pipeline/
  ingest/        one module per source: votehub, wikipedia_polls, fte_archive, fec,
                 medsl, districts, bls, bea, census_cps, ces, specials, expert_ratings
  normalize/     source → canonical tables (ids, candidates, parties, dates)
  model/         pollster_ratings, adjust, average, fundamentals, turnout,
                 simulate, rules (runoff/RCV/top-two), outputs
  backtest/      as-of replays, metrics, calibration, sensitivity
  publish/       write site JSON + run manifest
data/
  raw/<source>/<YYYY-MM-DD>/...      immutable snapshots, exactly as fetched
  manual/                             hand-coded CSVs (reviewed in PRs):
                                      weighting_method.csv, sponsors.csv,
                                      candidate_quality.csv, race_rules.csv,
                                      district_plans.csv (which map each state uses)
  db/*.parquet                        normalized tables
  placeholder/                        stubbed data — every file named PLACEHOLDER_*
runs/<run_id>/manifest.json           see "Provenance"
site/                                 SvelteKit app; reads site/static/data/**
tests/                                parsers + model math
.github/workflows/
```

## Data model (generic across cycles)
Keyed **cycle → office → jurisdiction → race → candidate**.

| table | key / notable columns |
|---|---|
| cycle | `2026`, type (midterm / presidential / off-year), election_date |
| office | `sen`, `gov`, `house`, `pres`, `pres_primary`, `state_sc`, ... |
| jurisdiction | `OH`, `TX-28`, plan_id (which district map) |
| race | `2026-sen-OH-special`; rules (plurality / majority-runoff / RCV / top-two), seat_class, is_special, holdover info |
| candidate | candidate_id, race_id, party, incumbent, prior_office, caucus_probs |
| pollster | ratings by run |
| poll | poll_id, pollster, sponsor, sponsor_partisan, field_start/end, n, population (LV/RV/A), mode, weighting_class, weighting_detail, source, source_url, fetched_at |
| poll_result | poll_id, race_id (or `generic`/`approval`), candidate_id, pct |
| result | certified results (race, candidate, votes, pct, source) |
| district_lean | jurisdiction, plan_id, pres_2020_margin, pres_2024_margin, source |
| fundamentals | date-stamped national inputs (generic avg, approval avg, econ) |
| forecast_race | run_id, race_id, candidate_id, win_prob, quantiles, breakdown JSON |
| forecast_national | run_id, office, control_prob, seat_hist, tipping_point |
| run | run_id, code_sha, started_at, input hashes, params hash |

2028 adds rows (office `pres`, `pres_primary`; jurisdictions `NE-2`, `ME-2`), not tables. The Electoral College model reuses `simulate` with electoral votes as seat weights.

## Daily pipeline (GitHub Actions)
```
ingest (snapshot raw) → normalize → validate → model → publish JSON → build site → deploy
```
- `daily.yml` — cron 2×/day through election day (1×/day after). Each step fails loudly; the site only deploys if validation passes, otherwise the previous forecast stays up and the failure is shown in the run log.
- `backtest.yml` — manual; re-runs the backtest + sensitivity, publishes calibration artifacts.
- `tests.yml` — on PRs: pytest (parsers on saved fixtures, model math), site type-check + build.
- `pages.yml` — site build + deploy.

## Provenance (every number traceable)
Each run writes `runs/<run_id>/manifest.json`:
- git SHA of the code, parameter file hash,
- SHA-256 of every input snapshot it read (`data/raw/...`, `data/manual/...`),
- output file hashes, simulation count and seed.

Every JSON file the site reads carries `run_id`; the site footer and each race page show it with a link to the manifest. Re-running a manifest's SHA on its inputs with its seed reproduces the numbers exactly (tested).

## Site
Static pages generated from JSON:
- **Summary bar** (all pages): Senate & House control odds in plain language ("Democrats win the House in 68 of 100 simulations"), expected seats, governor count, last updated.
- **Home**: tabs Senate / House / Governor. States shaded by win probability on a colorblind-safe diverging scale. **House uses a hex cartogram** (one hex per district) — also avoids needing shapefiles for the 10 redrawn states at launch. Tooltip on hover/tap, click → state page. A table view of the same data for screen readers and phones.
- **State page**: every race in the state.
- **Race page**: probability gauge, vote-share distribution, forecast-over-time, poll table (weight + reason for each: rating, methodology correction, recency, sample size, sponsor), "what's driving this forecast" breakdown, turnout-scenario toggle.
- **Poll database**: search/filter (race, pollster, population, method, dates); client-side over a compressed JSON index.
- **Methodology**: this document rendered, plus calibration charts, pollster ratings, assumption register, sensitivity results.
- Playful bit: "simulate one election" animates a single draw on the map.
- Standards: mobile-first, WCAG AA (contrast, keyboard, non-color encodings), small JS budget.

Map geometry: `us-atlas` state shapes (Census-based, ISC licence); the hex layout is generated by us (no licensing issue).

## Phase 3 hooks (architected now, built later)
- **Scorecard**: `forecast_race` + `result` + `expert_ratings` already share race ids.
- **Trackers** (approval, generic ballot, special-election overperformance): same averaging code, separate pages, run year-round.
- **Off-year / specials / 2028**: new cycle rows; race rules table covers runoff/RCV/primary formats.
- **Newsletter + RSS**: RSS is generated static; newsletter sign-ups would be private data → separate service/repo, never this repo.

## Repo size
Raw snapshots are kept compact (JSON/CSV gzip where large). If the repo nears ~500 MB, raw snapshots older than a cycle move to release assets with hashes kept in the manifest.
