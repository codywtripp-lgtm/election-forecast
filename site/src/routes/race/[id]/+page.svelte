<script lang="ts">
	import { resolve } from '$app/paths';
	import ProbGauge from '#lib/components/ProbGauge.svelte';
	import MarginDistribution from '#lib/components/MarginDistribution.svelte';
	import ForecastHistory from '#lib/components/ForecastHistory.svelte';
	import { classOf } from '#lib/colors.ts';
	import { fmtDate, fmtUpdated, inHundred, margin, partyLetter, raceTitle } from '#lib/format.ts';
	import { STATE_NAMES } from '#lib/geo.ts';

	let { data } = $props();
	const r = $derived({ ...data.race, d_side: { ...data.race.d_side, name: data.race.d_side.name ?? 'No Democrat' }, rep: { ...data.race.rep, name: data.race.rep.name ?? 'No Republican' } });
	const dL = $derived(partyLetter(r.d_side.party));
	let scenario = $state('all');
	const p = $derived(scenario === 'all' ? r.p_dside : r.p_by_scenario[scenario]);
	const b = $derived(r.breakdown);
	let showAll = $state(false);
	const polls = $derived(showAll ? r.polls : r.polls.slice(0, 12));

	const RULES: Record<string, string> = {
		plurality: 'Most votes wins.',
		majority_runoff: 'A candidate needs a majority (over 50%); otherwise the top two meet in a runoff on December 1.',
		rcv: 'Ranked-choice voting: if nobody has a majority of first choices, the last-place candidate is eliminated and their votes transfer.',
		top4_rcv: 'Top-four primary, then ranked-choice voting in November. Same-party minor candidates\' votes are assumed to transfer mostly to their party\'s leader.',
		top_two: 'Top-two primary: the two November candidates were set in the June primary.',
		majority_legislature: 'If nobody wins a majority, the state legislature picks the winner. Modeled as most-votes-wins (the legislature has historically chosen the plurality winner).'
	};
	const sign = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1);
</script>

<svelte:head>
	<title>{raceTitle(r)} 2026 forecast: {r.d_side.name} vs. {r.rep.name}</title>
</svelte:head>

<nav class="crumbs small"><a href={resolve('/')}>Forecast</a> / <a href={resolve('/state/[st]', { st: r.state })}>{STATE_NAMES[r.state]}</a></nav>
<h1>{raceTitle(r)}</h1>
<p class="muted small">
	{r.d_side.name} ({dL}) vs. {r.rep.name} (R)
	{#if r.other_candidates.length}· also on the ballot: {r.other_candidates.map((c: any) => `${c.name} (${c.party_label})`).join(', ')}{/if}
	<br />Incumbent: {r.incumbent} ({partyLetter(r.incumbent_party)}) · Updated {fmtUpdated(r.updated)}
</p>

<div class="grid-2">
	<section class="card">
		<ProbGauge {p} dName={r.d_side.name} rName={r.rep.name} />
		<p>
			<strong class="pill-text">{classOf(p).label}.</strong>
			{r.d_side.name} wins in {inHundred(p)} simulations{#if r.p_runoff > 0.02}; {Math.round(r.p_runoff * 100)}% of simulations go to a December runoff{/if}.
			The average simulated result is <strong>{margin(r.margin.mean, dL)}</strong>; 80% of simulations fall between
			{margin(r.margin.q10, dL)} and {margin(r.margin.q90, dL)}.
		</p>
		<div class="scen" role="group" aria-label="Turnout scenario">
			<span class="tiny muted">Turnout scenario:</span>
			<button aria-pressed={scenario === 'all'} onclick={() => (scenario = 'all')}>All</button>
			{#each data.scenarios as sc}
				<button aria-pressed={scenario === sc.key} onclick={() => (scenario = sc.key)}>{sc.label}</button>
			{/each}
		</div>
		<p class="tiny muted">Rules: {RULES[r.rule] ?? r.rule}{#if r.rule_verified === 'no'} (rule still being verified){/if}</p>
	</section>
	<section class="card">
		<h2>Range of outcomes</h2>
		<MarginDistribution hist={r.margin_hist} dLetter={dL} median={r.margin.q50} />
	</section>
</div>

<section class="card">
	<h2>What is driving this forecast</h2>
	<div class="drivers">
		<div>
			<h3>Fundamentals <span class="muted small">(no polls)</span></h3>
			<table class="small">
				<tbody>
					<tr><td>Baseline ({r.office === 'sen' ? 'Senate' : 'governor'} races)</td><td class="num">{sign(b.fundamentals.constant)}</td></tr>
					<tr><td>State partisan lean</td><td class="num">{sign(b.fundamentals.partisan_lean)}</td></tr>
					<tr><td>National environment (generic ballot)</td><td class="num">{sign(b.fundamentals.national_environment)}</td></tr>
					<tr><td>Incumbency</td><td class="num">{sign(b.fundamentals.incumbency)}</td></tr>
					<tr class="total"><td>Fundamentals estimate</td><td class="num">{margin(b.fundamentals.total, dL)}</td></tr>
				</tbody>
			</table>
			<p class="tiny muted">Uncertainty ±{b.fundamentals.sd.toFixed(0)} pts (1 s.d.). Positive numbers favor {r.d_side.name}.</p>
		</div>
		<div>
			<h3>Polls</h3>
			{#if b.polls.average !== null && b.polls.average !== undefined}
				<p class="small">
					Adjusted polling average: <strong>{margin(b.polls.average, dL)}</strong> from {b.polls.n_polls} polls
					(worth about {b.polls.effective_n.toFixed(1)} independent polls after weighting), ±{b.polls.sd.toFixed(1)} pts.
				</p>
			{:else}
				<p class="small">No polls yet. This forecast relies entirely on fundamentals.</p>
			{/if}
			<h3>Blend</h3>
			<div class="blend" role="img" aria-label="Polls get {Math.round(b.blend.poll_weight * 100)}% of the weight">
				<div class="bp" style:width="{b.blend.poll_weight * 100}%"></div>
			</div>
			<p class="small">
				Polls get <strong>{Math.round(b.blend.poll_weight * 100)}%</strong> of the weight, fundamentals
				{100 - Math.round(b.blend.poll_weight * 100)}%. The weight on polls rises as more and better polls come in and as Election
				Day approaches. Combined: <strong>{margin(b.blend.margin, dL)}</strong>. Then the simulation adds national, regional and
				demographic polling-error terms shared with other races.
			</p>
		</div>
	</div>
</section>

{#if r.expert_ratings?.length}
	<section class="card">
		<h2>Expert ratings <span class="muted small">(for comparison only)</span></h2>
		<p class="small muted">
			Shown as a benchmark. They are <strong>not</strong> used anywhere in our model. After the election we will score our
			forecast and these ratings side by side.
		</p>
		<ul class="experts">
			{#each r.expert_ratings as e}
				<li><span class="small">{e.rater}</span> <strong>{e.rating}</strong> <span class="tiny muted">({e.rating_date})</span></li>
			{/each}
		</ul>
		<p class="tiny muted">Ratings as tabulated on Wikipedia's 2026 race pages.</p>
	</section>
{/if}

<section class="card">
	<h2>Forecast over time</h2>
	{#if data.history}
		<ForecastHistory dates={data.history.as_of} p={data.history.p_dside} election={data.election} dName={r.d_side.name} />
	{/if}
</section>

<section class="card">
	<h2>Polls</h2>
	{#if r.polls.length === 0}
		<p class="muted">No general-election polls of this matchup yet.</p>
	{:else}
		<p class="small muted">
			Weight = this poll's share of the current average. Adjustments are in points toward {r.d_side.name} (+) or {r.rep.name} (−).
		</p>
		<div class="table-scroll">
			<table class="polls">
				<thead>
					<tr>
						<th>Pollster</th><th>Dates</th><th class="num">Sample</th><th class="num">Result</th>
						<th class="num">Adjusted</th><th class="num">Weight</th><th>Why this weight</th>
					</tr>
				</thead>
				<tbody>
					{#each polls as pl}
						<tr>
							<td>
								{#if pl.url}<a href={pl.url} rel="noopener external">{pl.pollster}</a>{:else}{pl.pollster}{/if}
								{#if pl.sponsors}<div class="tiny muted">for {pl.sponsors}</div>{/if}
								{#if pl.partisan}<span class="chip">{pl.partisan === 'DEM' ? 'D' : 'R'} sponsor</span>{/if}
								{#if pl.weighting && pl.weighting !== 'UNK'}<span class="chip" title="Weighting method (see methodology)">{pl.weighting}</span>{/if}
							</td>
							<td class="small">{fmtDate(pl.start)}–{fmtDate(pl.end)}</td>
							<td class="num small">{pl.n ? Math.round(pl.n).toLocaleString() : '?'} {pl.population.toUpperCase()}</td>
							<td class="num small">
								{#if pl.dem !== null}<span class="dem">{pl.dem}</span>–<span class="rep">{pl.rep}</span><br />{/if}
								<span class="muted">{margin(pl.margin_raw, dL)}</span>
							</td>
							<td class="num small" title="population {sign(pl.adj.population)} · sponsor {sign(pl.adj.sponsor)} · house {sign(pl.adj.house)} · trend {sign(pl.adj.trend)}{pl.adj.rcv ? ` · ranked-choice ${sign(pl.adj.rcv)}` : ''}">
								{margin(pl.margin_adj, dL)}
							</td>
							<td class="num small">
								<span class="wbar" style:width="{Math.min(60, pl.weight * 120)}px" aria-hidden="true"></span>
								{(pl.weight * 100).toFixed(0)}%
							</td>
							<td class="tiny">{pl.reasons.join('; ') || 'standard weight'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if r.polls.length > 12}
			<button onclick={() => (showAll = !showAll)}>{showAll ? 'Show fewer' : `Show all ${r.polls.length} polls`}</button>
		{/if}
	{/if}
</section>

<p class="tiny muted">Run <code>{r.run_id}</code>. <a href={resolve('/methodology')}>How this forecast works</a>.</p>

<style>
	.crumbs { margin-bottom: 8px; }
	.card { margin-bottom: 16px; }
	.scen { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
	.scen button { font-size: 0.8rem; padding: 3px 10px; }
	.drivers { display: grid; gap: 20px; grid-template-columns: 1fr; }
	@media (min-width: 760px) { .drivers { grid-template-columns: 1fr 1fr; } }
	.drivers td { padding: 5px 6px; }
	tr.total td { font-weight: 700; border-top: 2px solid var(--axis); }
	.blend { height: 10px; border-radius: 5px; background: var(--axis); overflow: hidden; margin: 4px 0 8px; }
	.bp { height: 100%; background: var(--ink-2); border-radius: 5px; }
	.polls td { font-size: 0.88rem; }
	.experts { list-style: none; padding: 0; margin: 0 0 8px; display: flex; gap: 8px 24px; flex-wrap: wrap; }
	.wbar { display: inline-block; height: 6px; border-radius: 3px; background: var(--ink-3); margin-right: 4px; vertical-align: middle; }
</style>
