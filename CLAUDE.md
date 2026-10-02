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
- 2026-10-02: Docs approved (PR #1). Owner: OK to publish poll DB under CC BY-SA; accepts scope cuts; delegated modeling decisions; gave blanket permission to proceed (including merging).
- 2026-10-02: Data foundation (PR #2), model core (PR #3), site (PR #4). Python + Node installed locally (venv in `.venv`; Node via winget: add `%LOCALAPPDATA%/Microsoft/WinGet/Packages/OpenJS.NodeJS.LTS_*/node-*` to PATH).
- Workflows: `daily.yml` (named "forecast": ingest → model → commit data/history/manifest → build site → GitHub Pages, 2×/day + on push to main), `backtest.yml` (weekly refit of error params → `data/model/`), `tests.yml`.
- Site: SvelteKit 3 (`#lib/...ts` imports, `resolve()`/`asset()` from `$app/paths`), adapter-static, data read at build time from `site/static/data/2026` (generated, not committed).
- 2026-10-02: House (PR #5): `pipeline/house.py` (Wikipedia House pages + Downballot pres-by-CD sheets), House fundamentals, 435 districts in the same simulation, hex map.
- 2026-10-02: Sensitivity analysis (PR #6, `pipeline/sensitivity.py`, weekly), expert ratings benchmark (Cook/IE/Sabato on race pages, never a model input), LA/MS rules verified, weighting-method correction (PR #7: `data/manual/weighting_method.csv`, `pipeline/model/weighting.py`).
- Local runs never write tracked history/manifests (only when GITHUB_ACTIONS=true).
- Open items: code more pollsters' weighting methods (G5); approval/midterm regression (G9); CPS/CES turnout build (G10); House expert ratings; candidate quality + FEC fundraising; Phase 3 (scorecard after Nov 3, approval/generic-ballot/special-election trackers, 2027 + 2028 scaffolding, RSS).
- (old) Next (after House): Phase 2 polish (verify 2026 district lines, district lean, hex map); hand-code weighting methods (G5); approval/midterm regression (G9); CPS/CES turnout build (G10).
