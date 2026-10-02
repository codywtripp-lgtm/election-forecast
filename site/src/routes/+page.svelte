<script lang="ts">
	import { asset, resolve } from '$app/paths';
	import USMap from '#lib/components/USMap.svelte';
	import SeatHistogram from '#lib/components/SeatHistogram.svelte';
	import RaceTable from '#lib/components/RaceTable.svelte';
	import { CLASSES } from '#lib/colors.ts';
	import { inHundred, margin, raceTitle } from '#lib/format.ts';
	import type { RaceSummary } from '#lib/types.ts';

	let { data } = $props();
	const s = $derived(data.summary);
	let tab: 'sen' | 'gov' | 'house' = $state('sen');
	let scenario: string = $state('all');

	const races = $derived(s.races.filter((r: RaceSummary) => r.office === tab));
	const sen = $derived(s.national.sen);
	const gov = $derived(s.national.gov);
	const senView = $derived(scenario === 'all' ? sen : { ...sen, ...sen.by_scenario[scenario] });
	const govView = $derived(scenario === 'all' ? gov : { ...gov, ...gov.by_scenario[scenario] });
	const raceById = $derived(Object.fromEntries(s.races.map((r: RaceSummary) => [r.id, r])));
	const tipping = $derived(Object.entries(sen.tipping_point ?? {}).slice(0, 5) as [string, number][]);

	// ---- "simulate one election": replay one stored simulation draw from the model run
	type Samples = { race_ids: string[]; dside_wins: string[]; margins: number[][]; scenario: number[] };
	let samples: Samples | null = null;
	let sim: { k: number; winners: Record<string, boolean>; senD: number; senInd: number; govD: number; scenario: string } | null =
		$state(null);
	let simShown: Record<string, boolean> | null = $state(null);
	let running = $state(false);

	async function simulateOne() {
		if (running) return;
		running = true;
		samples ??= await (await fetch(asset('data/2026/samples.json'))).json();
		const S = samples!;
		const k = Math.floor(Math.random() * S.dside_wins[0].length);
		const winners: Record<string, boolean> = {};
		S.race_ids.forEach((id, j) => (winners[id] = S.dside_wins[j][k] === '1'));
		const wins = (office: string, dem: boolean) =>
			S.race_ids.filter((id) => raceById[id]?.office === office && winners[id] && (raceById[id].d_party === 'DEM') === dem).length;
		sim = {
			k,
			winners,
			scenario: s.scenarios[S.scenario[k]]?.label ?? '',
			senD: sen.holdover_dem + wins('sen', true),
			senInd: wins('sen', false),
			govD: gov.holdover_dem + wins('gov', true)
		};
		// reveal state by state, safest first and closest last
		const order = races.slice().sort((a: RaceSummary, b: RaceSummary) => Math.abs(b.p - 0.5) - Math.abs(a.p - 0.5));
		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		simShown = {};
		for (const r of order) {
			simShown = { ...simShown, [r.state]: winners[r.id] };
			if (!reduce) await new Promise((res) => setTimeout(res, 35));
		}
		running = false;
	}
	function clearSim() {
		sim = null;
		simShown = null;
	}
	function setTab(t: 'sen' | 'gov' | 'house') {
		tab = t;
		clearSim();
	}
</script>

<svelte:head>
	<title>2026 Election Forecast: Senate, Governor and House</title>
</svelte:head>

<section class="hero">
	<h1>2026 midterm forecast</h1>
	<p class="lede">
		{#if (senView.p_dem_control ?? 0) >= (senView.p_rep_control ?? 0)}
			<strong class="dem">Democrats</strong> win the Senate in <strong class="num">{inHundred(senView.p_dem_control ?? 0)}</strong>
			simulations; <strong class="rep">Republicans</strong> keep it in <strong class="num">{inHundred(senView.p_rep_control ?? 0)}</strong>.
		{:else}
			<strong class="rep">Republicans</strong> keep the Senate in <strong class="num">{inHundred(senView.p_rep_control ?? 0)}</strong>
			simulations; <strong class="dem">Democrats</strong> flip it in <strong class="num">{inHundred(senView.p_dem_control ?? 0)}</strong>.
		{/if}
		{#if (senView.p_independents_decide ?? 0) >= 0.005}
			In {inHundred(senView.p_independents_decide ?? 0)}, neither party reaches a majority without an independent.
		{/if}
	</p>
	<p class="small muted">
		Based on {s.n_sims.toLocaleString()} simulations of every race, {s.days_to_election} days before Election Day.
		Generic ballot average: <strong>{margin(s.generic_ballot.margin)}</strong> ({s.generic_ballot.n_polls} polls).
	</p>

	<div class="scen" role="group" aria-label="Turnout scenario">
		<span class="tiny muted">Turnout scenario:</span>
		<button aria-pressed={scenario === 'all'} onclick={() => (scenario = 'all')}>All (weighted)</button>
		{#each s.scenarios as sc}
			<button
				aria-pressed={scenario === sc.key}
				onclick={() => (scenario = sc.key)}
				title="{sc.label}: shifts every margin {sc.shift >= 0 ? '+' : ''}{sc.shift} pts toward Democrats; weight {sc.weight * 100}%"
				>{sc.label}</button
			>
		{/each}
	</div>
</section>

<div class="grid-2">
	<section class="card">
		<h2>Senate seats</h2>
		<p class="small muted">
			{sen.holdover_dem} Democratic-caucus and {sen.holdover_rep} Republican seats are not on the ballot. Democrats need 51;
			Republicans need 50 (the Vice President breaks ties).
		</p>
		<SeatHistogram hist={sen.dem_seats_hist} majority={51} repMajorityAt={50} total={100} highlight={sim?.senD ?? null} />
		{#if scenario !== 'all'}
			<p class="small">
				Under this scenario: Democrats {inHundred(senView.p_dem_control ?? 0)}, Republicans {inHundred(senView.p_rep_control ?? 0)}.
			</p>
		{/if}
	</section>
	<section class="card">
		<h2>Tipping-point races</h2>
		<p class="small muted">How often each race delivers the deciding Senate seat in the simulations.</p>
		<ol class="tp">
			{#each tipping as [id, share]}
				{@const r = raceById[id]}
				{#if r}
					<li>
						<a href={resolve('/race/[id]', { id })}>{raceTitle(r)}</a>
						<span class="bar" style:width="{share * 400}px" aria-hidden="true"></span>
						<span class="num small muted">{(share * 100).toFixed(0)}%</span>
					</li>
				{/if}
			{/each}
		</ol>
		<h3 style="margin-top:1rem">Governors</h3>
		<p class="small">
			Expected after Election Day: <strong class="dem">{govView.dem_seats_mean.toFixed(1)} D</strong> ·
			<strong class="rep">{govView.rep_seats_mean.toFixed(1)} R</strong>. Democrats hold a majority of governorships in
			<strong>{inHundred(govView.p_dem_majority ?? 0)}</strong> simulations.
		</p>
	</section>
</div>

<section class="card map-card">
	<div class="tabs" role="tablist" aria-label="Office">
		<button role="tab" aria-selected={tab === 'sen'} onclick={() => setTab('sen')}>Senate</button>
		<button role="tab" aria-selected={tab === 'gov'} onclick={() => setTab('gov')}>Governor</button>
		<button role="tab" aria-selected={tab === 'house'} onclick={() => setTab('house')}>House</button>
	</div>

	{#if tab === 'house'}
		<div class="house-soon">
			<h2>House forecast: coming by October 20</h2>
			<p class="muted">
				The House model is mostly fundamentals (district lean on the 2026 lines, national environment, incumbency), because most of
				the 435 districts have little or no polling. Ten states redrew their maps for 2026, and we are verifying each one before
				publishing. The House view will be a hex map, so small urban districts are not hidden.
			</p>
		</div>
	{:else}
		<div class="sim-row">
			<button class="sim-btn" onclick={simulateOne} disabled={running}>🎲 Simulate one election</button>
			{#if sim}
				<span class="small" aria-live="polite">
					Draw #{sim.k + 1}:
					{#if tab === 'sen'}
						<strong class="dem">{sim.senD} D</strong> · <strong class="rep">{100 - sim.senD - sim.senInd} R</strong>
						{#if sim.senInd}· {sim.senInd} independent{sim.senInd > 1 ? 's' : ''}{/if}
					{:else}
						<strong class="dem">{sim.govD} D</strong> · <strong class="rep">{50 - sim.govD} R</strong> governors
					{/if}
					<span class="muted">({sim.scenario})</span>
				</span>
				<button class="small" onclick={clearSim}>Back to probabilities</button>
			{/if}
		</div>
		<USMap {races} simWinners={simShown} label="{tab === 'sen' ? 'Senate' : 'Governor'} forecast map" />
		<div class="legend small" aria-label="Legend">
			{#if simShown}
				<span><span class="swatch" style:background="var(--dem)"></span> D side wins this draw</span>
				<span><span class="swatch" style:background="var(--rep)"></span> R wins this draw</span>
			{:else}
				{#each CLASSES as c}
					<span><span class="swatch" style:background="var(--c-{c.key})"></span> {c.label}</span>
				{/each}
				<span><span class="swatch none"></span> No race</span>
			{/if}
		</div>
		<p class="tiny muted">
			Toss-up 40–60%, Lean 60–75%, Likely 75–95%, Safe 95%+. Blue is the Democratic nominee or, where an independent is the main
			challenger (Idaho, Montana, Nebraska, South Dakota Senate), that independent.
		</p>
	{/if}
</section>

{#if tab !== 'house'}
	<section class="card">
		<h2>All {tab === 'sen' ? 'Senate' : 'governor'} races</h2>
		<RaceTable {races} caption="{tab === 'sen' ? 'Senate' : 'Governor'} race forecasts" />
	</section>
{/if}

<style>
	.hero { margin-bottom: 16px; }
	.lede { font-size: clamp(1.1rem, 2.6vw, 1.35rem); max-width: 46em; }
	.scen { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
	.scen button { font-size: 0.82rem; padding: 4px 10px; }
	.card { margin-bottom: 16px; }
	.tp { padding-left: 1.2em; margin: 0; }
	.tp li { margin: 6px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.tp .bar { display: inline-block; height: 8px; border-radius: 4px; background: var(--axis); max-width: 40%; }
	.tabs { display: flex; gap: 6px; margin-bottom: 12px; }
	.sim-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; min-height: 36px; }
	.sim-btn { font-weight: 600; }
	.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; }
	.swatch.none { background: var(--surface); outline: 1px solid var(--axis); }
	.house-soon { padding: 24px 0; max-width: 40em; }
</style>
