<script lang="ts">
	import { resolve } from '$app/paths';
	import CalibrationChart from '#lib/components/CalibrationChart.svelte';

	let { data } = $props();
	const bt = $derived(data.backtest);
	const DAYS = ['120', '90', '60', '30', '14', '7', '1'];
	let q = $state('');
	const pollsters = $derived(data.pollsters.filter((p: any) => !q || p.pollster.toLowerCase().includes(q.toLowerCase())));
	const base = $derived(bt?.baselines ?? {});
	const fmtDelta = (d: number) => {
		const pts = Math.round(d * 100);
		return pts === 0 ? ' (±0)' : ` (${pts > 0 ? '+' : '−'}${Math.abs(pts)})`;
	};
</script>

<svelte:head><title>Methodology: how the 2026 forecast works</title></svelte:head>

<h1>Methodology</h1>
<p class="lede muted">
	Everything this forecast does, every assumption it makes, and how well it would have done in past elections.
</p>

{#if bt}
	<section class="card">
		<h2>How well does it work? Backtest, 2010–2024</h2>
		<p class="small">
			We re-ran the model as it would have looked before each past election, using only the polls, results and pollster
			track records available at the time. The error settings used to score each year were fit without that year.
		</p>
		<div class="grid-2">
			<CalibrationChart bins={bt.calibration} />
			<div>
				<div class="table-scroll">
					<table class="small">
						<thead><tr><th>Days before election</th><th class="num">Races</th><th class="num">Brier ↓</th><th class="num">Log loss ↓</th><th class="num">Winner right</th><th class="num">80% range covered</th></tr></thead>
						<tbody>
							{#each DAYS as d}
								{@const s = bt.loco_by_days_out[d]}
								{#if s}
									<tr><td>{d}</td><td class="num">{s.n}</td><td class="num">{s.brier.toFixed(3)}</td><td class="num">{s.log_loss.toFixed(3)}</td><td class="num">{(s.accuracy * 100).toFixed(0)}%</td><td class="num">{(s.coverage80 * 100).toFixed(0)}%</td></tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>
				{#if bt.loco_by_office}
					<h3 style="margin-top:12px">By office</h3>
					<div class="table-scroll">
						<table class="small">
							<thead><tr><th>Office</th><th class="num">Races (1 day out)</th><th class="num">Brier, 30 days</th><th class="num">Brier, 1 day</th><th class="num">Winner right, 1 day</th><th class="num">80% covered, 1 day</th></tr></thead>
							<tbody>
								{#each [['sen', 'Senate'], ['gov', 'Governor'], ['house', 'House']] as [k, label]}
									{@const o = bt.loco_by_office[k]}
									{#if o}
										<tr><td>{label}</td><td class="num">{o['1'].n}</td><td class="num">{o['30'].brier.toFixed(3)}</td><td class="num">{o['1'].brier.toFixed(3)}</td>
											<td class="num">{(o['1'].accuracy * 100).toFixed(0)}%</td><td class="num">{(o['1'].coverage80 * 100).toFixed(0)}%</td></tr>
									{/if}
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
				<h3 style="margin-top:12px">Against simpler approaches (all dates)</h3>
				<table class="small">
					<thead><tr><th>Method</th><th class="num">Brier ↓</th><th class="num">Winner right</th></tr></thead>
					<tbody>
						{#each Object.entries(base) as [k, v]}
							<tr><td>{k.replaceAll('_', ' ')}</td><td class="num">{(v as any).brier.toFixed(3)}</td><td class="num">{((v as any).accuracy * 100).toFixed(0)}%</td></tr>
						{/each}
					</tbody>
				</table>
				<p class="tiny muted">
					Honest caveat: in 2016–2024 polls overstated Democrats in most cycles, so Democrats given 10–40% chances won less often
					than forecast. We do not build in a correction for this, because the direction has flipped before (2012 and 2018). This is the forecast's biggest known risk.
				</p>
			</div>
		</div>
		<p class="tiny muted">
			Fitted error sizes at Election Day: national {bt.error_params.nat_ed.toFixed(1)} pts, regional {bt.error_params.div_ed.toFixed(1)},
			demographic {bt.error_params.dem_ed.toFixed(1)}, race-level poll error {bt.error_params.rp_ed.toFixed(1)}; Student-t tails
			(ν = {bt.error_params.df}).
		</p>
	</section>
{/if}

{#if data.sensitivity}
	<section class="card">
		<h2>How much do the assumptions matter?</h2>
		<p class="small">
			The same forecast re-run ({data.sensitivity.as_of}, {data.sensitivity.sims.toLocaleString()} simulations each) with one
			assumption changed at a time. Rows that move the numbers a lot are the assumptions to watch.
		</p>
		<div class="table-scroll">
			<table class="small">
				<thead>
					<tr><th>Variant</th><th class="num">Senate: D control</th><th class="num">House: D majority</th><th class="num">Senate D seats</th><th class="num">House D seats</th></tr>
				</thead>
				<tbody>
					{#each data.sensitivity.rows as r, i}
						{@const b = data.sensitivity.rows[0]}
						<tr class:base={i === 0}>
							<td>{r.variant}</td>
							<td class="num">{Math.round(r.senate_dem * 100)}%{#if i > 0}<span class="delta">{fmtDelta(r.senate_dem - b.senate_dem)}</span>{/if}</td>
							<td class="num">{r.house_dem !== undefined ? Math.round(r.house_dem * 100) + '%' : '–'}{#if i > 0 && r.house_dem !== undefined}<span class="delta">{fmtDelta(r.house_dem - b.house_dem)}</span>{/if}</td>
							<td class="num">{r.senate_dem_seats.toFixed(1)}</td>
							<td class="num">{r.house_dem_seats !== undefined ? r.house_dem_seats.toFixed(0) : '–'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

{#if data.weighting}
	<section class="card">
		<h2>Weighting-method correction</h2>
		<p class="small">
			Polls that weight to past vote (PV), to party (PID) or to demographics only (DEMO) can miss in different ways. We hand-code
			each pollster's method from its own published statement and estimate how each class missed in completed 2025–26 races
			relative to all polls. Estimates are shrunk toward zero and used only as differences between classes.
		</p>
		<table class="small">
			<thead><tr><th>Class</th><th class="num">Pollsters</th><th class="num">Polls</th><th class="num">Raw difference</th><th class="num">Correction used</th></tr></thead>
			<tbody>
				{#each ['PV', 'PID', 'DEMO'] as c}
					{@const w = data.weighting[c]}
					{#if w}
						<tr><td>{c}</td><td class="num">{w.n_pollsters}</td><td class="num">{w.n_polls}</td>
							<td class="num">{w.raw_diff !== undefined ? (w.raw_diff >= 0 ? '+' : '−') + Math.abs(w.raw_diff).toFixed(1) : '–'}</td>
							<td class="num">{w.delta >= 0 ? '+' : '−'}{Math.abs(w.delta).toFixed(1)} ± {w.sd.toFixed(1)}</td></tr>
					{/if}
				{/each}
			</tbody>
		</table>
		{#if data.weighting._field_mean_error}
			<p class="tiny muted">
				For context, all {data.weighting._field_mean_error.n_polls} polls in those races averaged
				{Math.abs(data.weighting._field_mean_error.delta).toFixed(1)} points too {data.weighting._field_mean_error.delta < 0 ? 'Republican' : 'Democratic'};
				that field-wide miss is handled by the national error term, not by this correction.
			</p>
		{/if}
	</section>
{/if}

<section class="card">
	<h2>Pollster ratings</h2>
	<p class="small">
		Our own ratings, from about 17,800 final-weeks polls with certified results (1998–2024). <strong>Extra error</strong> is the
		variance beyond what sample size alone explains (lower is better). <strong>Lean</strong> is the pollster's average miss relative
		to other polls of the same races (+ = toward Democrats). Pollsters with short records are shrunk toward the average.
	</p>
	<input type="search" placeholder="Find a pollster" bind:value={q} aria-label="Find a pollster" />
	<div class="table-scroll">
		<table class="small">
			<thead><tr><th>Pollster</th><th class="num">Polls rated</th><th class="num">Extra error</th><th class="num">Lean</th><th>Flags</th></tr></thead>
			<tbody>
				{#each pollsters.slice(0, 80) as p}
					<tr>
						<td>{p.pollster}</td>
						<td class="num">{p.n}</td>
						<td class="num">{p.tau2.toFixed(1)}</td>
						<td class="num">{p.bias >= 0 ? 'D+' : 'R+'}{Math.abs(p.bias).toFixed(1)}</td>
						<td>{#if p.herding}<span class="chip">possible herding</span>{/if}{#if p.group === 'aapor'}<span class="chip">AAPOR/Roper</span>{/if}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</section>

<p class="small">After Election Day, the <a href={resolve('/scorecard')}>scorecard</a> grades the final forecast against results and the expert ratings.</p>

<section class="card">
	<h2>Model changelog</h2>
	<p class="small muted">Every change to the method, newest first. Daily updates note when movement comes from a change here rather than new data.</p>
	<ul class="log">
		{#each data.changelog as e}<li><span class="num small muted">{e.date}</span> {e.change}</li>{/each}
	</ul>
</section>

<article class="card doc">
	{@html data.html}
</article>

<style>
	.lede { font-size: 1.1rem; }
	tr.base td { font-weight: 700; }
	.log { padding-left: 1.1em; margin: 0; }
	.log li { margin: 4px 0; }
	.delta { color: var(--ink-3); font-weight: 400; margin-left: 4px; font-size: 0.85em; }
	.card { margin-bottom: 16px; }
	input[type='search'] {
		font: inherit; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border);
		background: var(--surface); color: var(--ink-1); margin-bottom: 8px; min-width: 240px;
	}
	.doc :global(table) { font-size: 0.85rem; display: block; overflow-x: auto; }
	.doc :global(pre) { overflow-x: auto; background: var(--surface-2); padding: 10px; border-radius: 6px; font-size: 0.85rem; }
	.doc :global(code) { font-size: 0.9em; }
	.doc :global(h2) { margin-top: 1.6em; }
	.doc { max-width: 100%; overflow-wrap: anywhere; }
</style>
