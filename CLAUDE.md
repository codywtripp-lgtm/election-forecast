# election-forecast

Independent, statistically rigorous election forecast site. Launch: Nov 3, 2026 midterms (35 Senate incl. OH + FL specials, 36 governors, 435 House). Built as a permanent multi-cycle platform (2027 specials/off-year, 2028 primaries + general, trackers).

## Owner
- Data viz/reporting background; new to GitHub and Claude Code. Works from phone: keep updates short, lead with what matters, spell out actions (e.g. "merge PR #N").
- No local Node or Python — all tests/builds/runs happen in GitHub Actions. Merging PRs is the owner's job.

## Hard rules
- **No prediction markets** (Polymarket, Kalshi, PredictIt, ...) as input, benchmark, or display.
- Respect robots.txt and terms of every source; prefer official APIs/bulk downloads.
- Every published number traces to reproducible code + versioned inputs (run manifest).
- Backtest before trusting output (2010/2014/2018/2022 midterms; 2016/2020/2024).
- Never fabricate data. Placeholders are labelled `PLACEHOLDER_*` and listed in `docs/DATA_GAPS.md`.
- Expert ratings are a benchmark only, never a model input.
- Public repo: no private data, ever. Secrets only in Actions secrets.

## Phases
1. (~10 days) data pipeline, poll DB, Senate + governor model, national map, summary bar, race pages.
2. (~2 weeks before election) House model (fundamentals-heavy), House hex map.
3. (post-election) accuracy scorecard, trackers, 2028 scaffolding.

## Docs
- `docs/METHODOLOGY.md` — model spec + assumption register [A#]
- `docs/ARCHITECTURE.md` — stack, schema, pipeline, provenance
- `docs/DATA_GAPS.md` — source status, licences, placeholders

## Status
- 2026-10-02: Docs drafted for owner review (PR). No code yet.
