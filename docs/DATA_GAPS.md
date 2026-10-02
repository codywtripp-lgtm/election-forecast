# Data sources and gaps

Status key: **live** = ingested and used by the forecast · **check** = believed usable, not ingested yet · **excluded** = not used.
Last reviewed 2026-10-02.

## Sources

| # | Source | Use | Status | Licence / terms | Notes |
|---|---|---|---|---|---|
| S1 | VoteHub Polling API (`api.votehub.com/polls`) | 2025–26 polls: Senate, governor, House, generic ballot, approval | **live** (twice daily) | CC BY 4.0, confirmed on the API page; attribution in site footer | Fields: pollster, sponsors, partisan flag, internal flag, dates, n, population, answers (names only). **No mode, no weighting method, no candidate party.** Mode is filled from 538's record for the same pollster (flagged `inferred_538`); party is matched to nominees by name (`data/manual/candidate_aliases.csv` for edge cases). The website itself says scraping is prohibited; we use only the published API. |
| S2 | Wikipedia (MediaWiki parse API) | 2026 race list + nominees; 2000–2025 Senate/governor results; current senators/governors | **live** | CC BY-SA 4.0. Owner approved publishing our poll database under CC BY-SA. | Snapshotted per fetch with revision id. Senate results cross-checked against MEDSL (83% within 0.3 pts; gaps explained by fusion voting, jungle primaries, write-ins). |
| S3 | 538 archive | pollster ratings (`raw_polls.csv`, 1998–2022), backtest poll histories 2018–2024 | **live** (frozen) | CC BY 4.0 (repo licence) | Poll-history CSVs no longer served by 538 (redirect to ABC); taken from the Internet Archive capture of 2025-01-18 (timestamp pinned in `pipeline/ingest/fte_archive.py`). |
| S4 | Pollster releases (PDF/web) | methodology coding | not started | per pollster | Needed for G5. |
| S5 | RealClearPolling | — | **excluded** | robots/terms do not permit automated reuse (403 to our fetcher) | |
| S6 | Decision Desk HQ | — | **excluded** | paid/licensed | |
| S7 | Prediction markets (Polymarket, Kalshi, PredictIt...) | — | **excluded** (hard rule) | | Never input, benchmark, or display. |
| S8 | MIT Election Data + Science Lab | Senate 1976–2024, President by state 1976–2024 | **live** | CC0 | **House 1976–2024 requires a Dataverse "guestbook" form (name/email) — not downloaded.** Needed for Phase 2 history; owner can download once, or we use Wikipedia House pages. |
| S9 | State secretaries of state | certified results, specials, primary turnout | not started | public records | |
| S10 | Dave's Redistricting | — | avoid | terms restrict bulk reuse | |
| S11 | The Downballot pres-by-CD (2026 lines) / Cook–Leip | House lean on new lines | check | terms to verify | Phase 2. |
| S12 | Redistricting Data Hub precinct results + enacted plans | compute lean ourselves | check | free account required | Phase 2 fallback. |
| S13 | FEC API | fundraising | not started | free API key (Actions secret `FEC_API_KEY`) | Not in launch fundamentals. |
| S14 | BLS, BEA | economy | not started | public | Not in launch fundamentals (G9). |
| S15 | Census ACS 2024 1-year (table-based summary files) | state + district demographics for correlated errors | **live** | public domain | The Census *API* now requires a key; the summary files on www2.census.gov do not. District rows are on the 2024 (119th Congress) lines. |
| S15b | Census CPS Voting Supplement | turnout by group/state | not started | public | For the full turnout-scenario build (G10). |
| S16 | Cooperative Election Study | validated vote by group | not started | open | For G10. |
| S17 | Expert ratings (Cook, Sabato, Inside Elections) | **benchmark only** | not started | store ratings (facts) with citation | Wikipedia race pages tabulate them (G11). |
| S18 | `us-atlas` TopoJSON | state map | **live** | ISC | |
| S19 | Clerk of the House | 2024 national House vote | **live** (one number) | public | Entered in `data/manual/national_house_vote.csv` with citation; 1998–2022 from 538 `raw_polls.csv`. |

## Known gaps (and what we do about them)

| # | Gap | Impact | Plan / status |
|---|---|---|---|
| G1 | Wikipedia CC BY-SA share-alike | poll database licence | **Resolved:** owner approved publishing the poll database under CC BY-SA 4.0. |
| G2 | 2026 district lines: 10 states changed (TX, NC, OH, CA, UT, FL, TN, LA, AL; MO's new map blocked → 2022 map). TN map under legal challenge. **Unverified** (Wikipedia summary). | House lean wrong if any state is wrong | Phase 2: verify each against the official enacted plan; `data/manual/district_plans.csv` with source URLs. ACS district demographics are on the old (2024) lines. |
| G3 | Poll histories before 2018 | 2010–2016 backtests are final-forecast only | Stated on the methodology page. |
| G4 | 2025–26 special/off-year poll set | needed for δ_class | VoteHub has NJ/VA 2025 governor polls; results needed. |
| G5 | **Weighting method not recorded anywhere in bulk** | δ_class not applied at launch (all polls UNK) | Hand-code the most prolific 2026 pollsters from their methodology statements. |
| G6 | Partisan-sponsor classification | sponsor penalty | Using VoteHub's partisan flag and 538's `partisan` field. |
| G7 | Transparency checklist | ratings | Launch uses AAPOR/Roper membership (from 538) as the transparency group. |
| G8 | Candidate quality (prior office) | prior | Not in launch fundamentals. |
| G9 | Approval + generic-ballot history 1946–2022 | national environment regression | Not in launch; N̂ = generic-ballot average. |
| G10 | Group turnout (CPS) and preferences (CES); special-election and primary turnout | turnout scenarios | Launch scenarios are anchored on the measured LV−RV gap; weights fixed 25/50/25. |
| G11 | Expert ratings history | benchmark only | Not built. |
| G12 | Election rules | correctness | `data/manual/race_rules.csv`. **Unverified:** Louisiana (first closed-primary cycle) and Mississippi general-election rules for Senate, both modeled as plurality. Vermont governor: legislature picks if no majority; modeled as plurality. |
| G13 | Independent caucus intentions | Senate control counting | `data/manual/caucus.csv`: Osborn (NE), Bodnar (MT), Achilles (ID), Bengs (SD) all set to 50% Democratic caucus, unverified. |
| G14 | Two candidates named Dan Sullivan in Alaska's Senate race | poll matching | Handled with `candidate_overrides.csv` / `candidate_aliases.csv`. |

## Placeholder policy
If a source is not ready, the affected component is left out (not faked) and listed above; anything shown on the site that rests on placeholder data carries a visible badge. **No placeholder data is used in the launch forecast.**
