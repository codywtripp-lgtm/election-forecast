<script lang="ts">
	import CalibrationChart from '#lib/components/CalibrationChart.svelte';

	let { data } = $props();
	const bt = $derived(data.backtest);
	const DAYS = ['120', '90', '60', '30', '14', '7', '1'];
	let q = $state('');
	const pollsters = $derived(data.pollsters.filter((p: any) => !q || p.pollster.toLowerCase().includes(q.toLowerCase())));
	const base = $derived(bt?.baselines ?? {});
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

<article class="card doc">
	{@html data.html}
</article>

<style>
	.lede { font-size: 1.1rem; }
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
