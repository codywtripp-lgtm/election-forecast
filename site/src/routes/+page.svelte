<script lang="ts">
	import { asset, resolve } from '$app/paths';
	import USMap from '#lib/components/USMap.svelte';
	import HexMap from '#lib/components/HexMap.svelte';
	import ApprovalMap from '#lib/components/ApprovalMap.svelte';
	import Sparkline from '#lib/components/Sparkline.svelte';
	import SeatHistogram from '#lib/components/SeatHistogram.svelte';
	import RaceTable from '#lib/components/RaceTable.svelte';
	import { APPROVAL_CLASSES, CLASSES } from '#lib/colors.ts';
	import { fmtDate, inHundred, margin, raceTitle } from '#lib/format.ts';
	import type { RaceSummary } from '#lib/types.ts';

	let { data } = $props();
	const s = $derived(data.summary);
	let tab: 'sen' | 'gov' | 'house' | 'approval' = $state('sen');
	const appr = $derived(data.trackers?.approval ?? []);
	const apprNow = $derived(appr.length ? appr[appr.length - 1].value : null);
	const appr30 = $derived(appr.length > 5 ? appr[appr.length - 5].value : null);
	const apprTrend = $derived(appr.slice(-14).map((p: { value: number }) => p.value));
	const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`;
	let scenario: string = $state('all');

	const races = $derived(s.races.filter((r: RaceSummary) => r.office === tab));
	const sen = $derived(s.national.sen);
	const gov = $derived(s.national.gov);
	const house = $derived(s.national.house);
	const houseView = $derived(house && scenario !== 'all' ? { ...house, ...house.by_scenario[scenario] } : house);
	const houseTipping = $derived(Object.entries(house?.tipping_point ?? {}).slice(0, 5) as [string, number][]);
	const senView = $derived(scenario === 'all' ? sen : { ...sen, ...sen.by_scenario[scenario] });
	const govView = $derived(scenario === 'all' ? gov : { ...gov, ...gov.by_scenario[scenario] });
	const raceById = $derived(Object.fromEntries(s.races.map((r: RaceSummary) => [r.id, r])));
	const tipping = $derived(Object.entries(sen.tipping_point ?? {}).slice(0, 5) as [string, number][]);

	// ---- "simulate one election": replay one stored simulation draw from the model run
	type Samples = { race_ids: string[]; dside_wins: string[]; scenario: number[] };
	let samples: Samples | null = null;
	let sim: { k: number; winners: Record<string, boolean>; senD: number; senInd: number; govD: number; houseD: number; scenario: string } | null =
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
			govD: gov.holdover_dem + wins('gov', true),
			houseD: wins('house', true)
		};
		// reveal state by state, safest first and closest last
		const order = races.slice().sort((a: RaceSummary, b: RaceSummary) => Math.abs(b.p - 0.5) - Math.abs(a.p - 0.5));
		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		simShown = {};
		const key = (r: RaceSummary) => (tab === 'house' ? r.id : r.state);
		const step = tab === 'house' ? 15 : 1; // reveal House districts in batches
		for (let i = 0; i < order.length; i += step) {
			const batch = Object.fromEntries(order.slice(i, i + step).map((r: RaceSummary) => [key(r), winners[r.id]]));
			simShown = { ...simShown, ...batch };
			if (!reduce) await new Promise((res) => setTimeout(res, 35));
		}
		running = false;
	}
	function clearSim() {
		sim = null;
		simShown = null;
	}
	function setTab(t: 'sen' | 'gov' | 'house' | 'approval') {
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
			In {inHundred(senView.p_independents_decide ?? 0)} simulations, neither party reaches a majority without an independent.
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

{#if apprNow !== null}
	<section class="card approval-card">
		<div>
			<div class="label-sm">Trump job approval</div>
			<div class="big-num" style:color={apprNow >= 0 ? 'var(--approve)' : 'var(--disapprove)'}>{signed(apprNow)}</div>
			<div class="small muted">net (approve − disapprove), our polling average
				{#if appr30 !== null}· {apprNow - appr30 >= 0 ? 'up' : 'down'} {Math.abs(apprNow - appr30).toFixed(1)} in 4 weeks{/if}</div>
		</div>
		<Sparkline values={apprTrend} label="Net approval over the last 14 weeks" />
		<div class="small links">
			<button onclick={() => { setTab('approval'); document.querySelector('.map-card')?.scrollIntoView({ behavior: 'smooth' }); }}>By state →</button>
			<a href={resolve('/trackers')}>All trackers →</a>
		</div>
	</section>
{/if}

{#if data.changes?.previous}
	{@const c = data.changes}
	<section class="card changes">
		<h2>Since {fmtDate(c.previous)}</h2>
		<p class="small">
			{#each [['sen_p_dem', 'Senate'], ['house_p_dem', 'House']] as [k, label]}
				{@const x = c.national[k]}
				{#if x && x.before !== null}
					{@const dl = Math.round((x.now - x.before) * 100)}
					<span class="chg">{label}: Democrats {Math.round(x.before * 100)}% → <strong>{Math.round(x.now * 100)}%</strong>
						{#if dl}<span class={dl > 0 ? 'dem' : 'rep'}>({dl > 0 ? '+' : '−'}{Math.abs(dl)})</span>{/if}</span>
				{/if}
			{/each}
		</p>
		{#if c.movers.length}
			<ul class="movers">
				{#each c.movers.slice(0, 6) as m}
					<li>
						<a href={resolve('/race/[id]', { id: m.id })}>{m.label}</a>
						<span class="small muted">{m.d}</span>
						<span class="num small">{Math.round(m.p_before * 100)}% → <strong>{Math.round(m.p_now * 100)}%</strong></span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="small muted">No race moved 3 points or more.</p>
		{/if}
		{#if c.model_changes?.length}
			<p class="tiny muted">Some of this movement comes from method changes, not new data:
				{c.model_changes.join(' ')} <a href={resolve('/methodology')}>Changelog</a>.</p>
		{/if}
	</section>
{/if}

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

{#if tab === 'house' && houseView}
	<div class="grid-2">
		<section class="card">
			<h2>House seats</h2>
			<p class="lede-sm">
				{#if (houseView.p_dem_majority ?? 0) >= (houseView.p_rep_majority ?? 0)}
					<strong class="dem">Democrats</strong> win the House in <strong>{inHundred(houseView.p_dem_majority ?? 0)}</strong> simulations.
				{:else}
					<strong class="rep">Republicans</strong> keep the House in <strong>{inHundred(houseView.p_rep_majority ?? 0)}</strong> simulations.
				{/if}
				Average: {houseView.dem_seats_mean.toFixed(0)} D – {houseView.rep_seats_mean.toFixed(0)} R. A majority is 218.
			</p>
			{#if house}<SeatHistogram hist={house.dem_seats_hist} majority={218} repMajorityAt={218} total={435} highlight={sim?.houseD ?? null} />{/if}
		</section>
		<section class="card">
			<h2>House tipping-point districts</h2>
			<ol class="tp">
				{#each houseTipping as [id, share]}
					{@const r = raceById[id]}
					{#if r}
						<li>
							<a href={resolve('/race/[id]', { id })}>{raceTitle(r)}</a>
							<span class="bar" style:width="{share * 1200}px" aria-hidden="true"></span>
							<span class="num small muted">{(share * 100).toFixed(1)}%</span>
						</li>
					{/if}
				{/each}
			</ol>
			<p class="tiny muted">
				Most House districts have no public polls, so the House forecast leans on fundamentals: district partisan lean on the 2026
				lines, the national environment and incumbency. {s.races.filter((r) => r.office === 'house' && r.n_polls > 0).length} districts
				have at least one poll.
			</p>
		</section>
	</div>
{/if}

<section class="card map-card">
	<div class="tabs" role="tablist" aria-label="Office">
		<button role="tab" aria-selected={tab === 'sen'} onclick={() => setTab('sen')}>Senate</button>
		<button role="tab" aria-selected={tab === 'gov'} onclick={() => setTab('gov')}>Governor</button>
		<button role="tab" aria-selected={tab === 'house'} onclick={() => setTab('house')}>House</button>
		{#if data.approvalStates}<button role="tab" aria-selected={tab === 'approval'} onclick={() => setTab('approval')}>Trump approval</button>{/if}
	</div>

	{#if tab === 'approval' && data.approvalStates}
		{@const a = data.approvalStates}
		<p class="small">Estimated Trump net approval (approve − disapprove) in each state. National average: <strong>{signed(a.national_net)}</strong>.</p>
		<ApprovalMap rows={a.states} />
		<div class="legend small" aria-label="Legend">
			{#each APPROVAL_CLASSES as c}
				<span><span class="swatch" style:background="var(--a-{c.key})"></span> {c.label}</span>
			{/each}
		</div>
		<p class="tiny muted">
			These are estimates, not polls. Most states have few or no public approval polls, so each state is the national average
			adjusted by its partisan lean (each point of lean moves net approval about {Math.abs(a.fit.b).toFixed(2)} points, fit on
			{a.fit.n_polls} state polls in {a.fit.n_states} states) plus what its own polls say. Hover a state for its latest poll.
		</p>
	{:else if tab === 'house' && !house}
		<div class="house-soon">
			<h2>House forecast: coming soon</h2>
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
					{:else if tab === 'gov'}
						<strong class="dem">{sim.govD} D</strong> · <strong class="rep">{50 - sim.govD} R</strong> governors
					{:else}
						<strong class="dem">{sim.houseD} D</strong> · <strong class="rep">{435 - sim.houseD} R</strong> House seats
					{/if}
					<span class="muted">({sim.scenario})</span>
				</span>
				<button class="small" onclick={clearSim}>Back to probabilities</button>
			{/if}
		</div>
		{#if tab === 'house'}
			<HexMap {races} simWinners={simShown} />
		{:else}
			<USMap {races} simWinners={simShown} label="{tab === 'sen' ? 'Senate' : 'Governor'} forecast map" />
		{/if}
		<div class="legend small" aria-label="Legend">
			{#if simShown}
				<span><span class="swatch" style:background="var(--dem)"></span> D side wins this draw</span>
				<span><span class="swatch" style:background="var(--rep)"></span> R wins this draw</span>
			{:else}
				{#each CLASSES as c}
					<span><span class="swatch" style:background="var(--c-{c.key})"></span> {c.label}</span>
				{/each}
				{#if tab !== 'house'}<span><span class="swatch none"></span> No race</span>{/if}
			{/if}
		</div>
		<p class="tiny muted">
			Toss-up 40–60%, Lean 60–75%, Likely 75–95%, Safe 95%+. Blue is the Democratic nominee or, where an independent is the main
			challenger (Idaho, Montana, Nebraska, South Dakota Senate), that independent.
			{#if tab === 'house'}One hexagon per district, grouped by state; positions within a state are not geographic.{/if}
		</p>
	{/if}
</section>

{#if tab !== 'approval' && (tab !== 'house' || house)}
	<section class="card">
		<h2>All {tab === 'sen' ? 'Senate' : tab === 'gov' ? 'governor' : 'House'} races</h2>
		<RaceTable {races} caption="{tab === 'sen' ? 'Senate' : 'Governor'} race forecasts" competitiveDefault={tab === 'house'} />
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
	.lede-sm { font-size: 1.05rem; }
	.approval-card { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; justify-content: space-between; }
	.label-sm { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2); font-weight: 600; }
	.big-num { font-size: 2.2rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
	.approval-card .links { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
	.changes .chg { margin-right: 18px; display: inline-block; }
	.movers { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px 20px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
	.movers li { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
</style>
