# Data sources and gaps

Status key: **have** = verified accessible & usable · **check** = believed usable, terms/format not yet verified · **stub** = placeholder needed (files named `PLACEHOLDER_*`, shown on the site as such) · **excluded** = not used.

"Verified" below means checked on 2026-09-27; nothing has been downloaded yet.

## Sources

| # | Source | Use | Status | Licence / terms | Notes |
|---|---|---|---|---|---|
| S1 | VoteHub Polling API | live polls (races, generic ballot, approval) | check | CC BY 4.0 per search result; API page returned 403 to our fetcher | Need to confirm which races are covered and whether sponsor / mode / population are fields. Attribution required. |
| S2 | Wikipedia race poll tables (MediaWiki API) | live polls, gap-filling | check | **CC BY-SA 4.0** | Share-alike may extend to derived poll tables we publish. Decision needed (G1). Use the API, not scraping HTML. |
| S3 | 538 data archive (GitHub `fivethirtyeight/data`, `raw-polls.csv`, `*_polls_historical`) | pollster ratings, backtest | check | per-file licence in repo (to confirm) | 538 shut down Mar 2025; archive static. No weighting-method field. |
| S4 | Pollster releases (PDF/web) | methodology coding, missing polls | manual | per pollster | Hand-coded into `data/manual/`. |
| S5 | RealClearPolling | — | **excluded** | robots.txt returned 403 to automated fetch; terms not shown to permit reuse | Revisit only if terms allow. |
| S6 | Decision Desk HQ | — | **excluded** | paid/licensed API | |
| S7 | Prediction markets (Polymarket, Kalshi, PredictIt...) | — | **excluded** (hard rule) | | Never input, benchmark, or display. |
| S8 | MIT Election Data + Science Lab (Harvard Dataverse) | historical results | check | open (per-dataset licence) | Senate/House/governor/president 1976–2024. |
| S9 | State secretaries of state | certified results, 2025–26 specials, primary turnout | manual/check | public records | Formats vary by state. |
| S10 | Dave's Redistricting | district presidential results | check, likely avoid | site terms restrict bulk reuse (to verify) | Prefer S11/S12. |
| S11 | The Downballot pres-by-CD (2026 lines) / Cook–Leip | district lean on new lines | check | terms to verify | Fastest route for House lean. |
| S12 | Redistricting Data Hub precinct results + enacted plans | compute lean ourselves | check | free account; terms to verify | Fallback / cross-check of S11. |
| S13 | FEC API (api.open.fec.gov) | receipts, cash on hand | check | public, free API key | Key would go in Actions secret `FEC_API_KEY`. |
| S14 | BLS, BEA APIs | unemployment, real disposable income | check | public | |
| S15 | Census CPS Voting Supplement | turnout by group/state | check | public | 2010–2024. |
| S16 | Cooperative Election Study (Harvard Dataverse) | validated vote by group/state | check | open | For turnout scenarios. |
| S17 | Expert ratings (Cook, Sabato, Inside Elections) | **benchmark only** | check | copyright; store ratings (facts) with citation, not text | Wikipedia race pages tabulate them. |
| S18 | `us-atlas` (TopoJSON) | state shapes | check | ISC | |

## Known gaps (and what we do about them)

| # | Gap | Impact | Plan |
|---|---|---|---|
| G1 | Wikipedia CC BY-SA share-alike | may require publishing our poll database under BY-SA | **Owner decision.** Option: accept BY-SA for the poll DB (it's public anyway). |
| G2 | 2026 district lines: 10 states changed (TX, NC, OH, CA, UT, FL, TN, LA, AL; MO's new map blocked → 2022 map used). TN map has a pending legal challenge. Source: Wikipedia summary — **unverified** | House lean wrong if any state is wrong | Verify each state against its official enacted plan; record in `data/manual/district_plans.csv` with source URL. |
| G3 | Poll time-series pre-2018 not in the 538 archive (only final-21-day polls for 2010/2014) | 2010/2014 backtests are final-forecast only | Stated on methodology page. |
| G4 | 2025–26 special/off-year poll set | needed for δ_class (weighting correction) | Collect from Wikipedia/VoteHub + pollster releases. |
| G5 | **Weighting method not recorded anywhere in bulk** | δ_class weakly identified at launch | Hand-code from methodology statements, starting with the most prolific 2022/2025/2026 pollsters; UNK for the rest. Wide prior until coded. |
| G6 | Partisan-sponsor classification | sponsor penalty | Hand-maintained list, reviewed in PRs. |
| G7 | Transparency checklist per pollster | ratings | Hand-coded; starts with AAPOR TI membership list. |
| G8 | Candidate quality (prior office) for ~900 nominees | prior | Hand/semiautomated coding; races with missing data use "unknown" with average effect. |
| G9 | Approval + generic-ballot history 1946–2022 | national environment fit | Assemble from Gallup published series + published academic tables, cited per row. |
| G10 | Primary turnout by party, registration trends | turnout scenario weights | Collect for states that publish; missing states use national pattern. |
| G11 | Expert ratings history (2010–2024) | benchmark only | From Wikipedia race "predictions" tables, cited. |
| G12 | Runoff/majority rules per state; Louisiana 2026 closed primaries; Maine RCV scope | rule correctness | Verify each in `data/manual/race_rules.csv` with statute/SoS link. |
| G13 | Independent caucus intentions | chamber counting | Documented per candidate with source; shown on race page. |

## Placeholder policy
If a source is not ready at launch, the pipeline uses files under `data/placeholder/PLACEHOLDER_*`, the affected race/page shows a visible "placeholder data" badge, and the gap stays listed here. No invented numbers are ever presented as real.
