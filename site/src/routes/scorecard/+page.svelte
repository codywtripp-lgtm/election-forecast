<script lang="ts">
	import { resolve } from '$app/paths';
	let { data } = $props();
	const sc = $derived(data.sc);
	const OFFICES: Record<string, string> = { sen: 'Senate', gov: 'Governor', house: 'House' };
</script>

<svelte:head><title>Scorecard: how accurate was the 2026 forecast?</title></svelte:head>

<h1>Scorecard</h1>

{#if !sc || sc.status === 'pending'}
	<section class="card">
		<h2>Results pending</h2>
		<p>
			After Election Day (November 3) this page scores our final forecast against the results, race by race, and
			against the major expert ratings. It fills in automatically as results come in, and is labelled
			<em>unofficial</em> until states certify.
		</p>
		<p class="small">What will be measured:</p>
		<ul class="small">
			<li><strong>Brier score</strong> and <strong>log loss</strong> (lower is better): how good the probabilities were, not just the calls.</li>
			<li>Races called right and wrong, with every miss listed.</li>
			<li>Whether the 80% ranges contained the result about 80% of the time.</li>
			<li>The size and direction of the national polling miss.</li>
			<li>The same scores for Cook, Inside Elections and Sabato on the same races.</li>
		</ul>
		{#if sc}
			<h3>Expert-rating conversion (fixed before the election)</h3>
			<p class="small muted">To compare ratings with probabilities, each rating is converted to a win probability for the Democratic side
				using this table, published on October 3 and not changed afterwards.</p>
			<table class="small mapping">
				<tbody>
					{#each Object.entries(sc.rating_mapping) as [k, v]}
						<tr><td>{k}</td><td class="num">{Math.round((v as number) * 100)}%</td></tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>
{:else}
	<p class="muted">
		Results are <strong>{sc.status}</strong> ({sc.results_races} races so far). Final forecast as of {sc.final_as_of}.
	</p>
	<section class="card">
		<h2>Overall</h2>
		<table class="small">
			<thead><tr><th>Office</th><th class="num">Races</th><th class="num">Right</th><th class="num">Wrong</th><th class="num">Brier ↓</th><th class="num">Log loss ↓</th></tr></thead>
			<tbody>
				{#each Object.entries(sc.by_office) as [o, m]}
					{@const x = m as any}
					<tr><td>{OFFICES[o] ?? o}</td><td class="num">{x.n}</td><td class="num">{x.correct}</td><td class="num">{x.wrong}</td><td class="num">{x.brier.toFixed(3)}</td><td class="num">{x.log_loss.toFixed(3)}</td></tr>
				{/each}
				<tr class="tot"><td>All</td><td class="num">{sc.overall.n}</td><td class="num">{sc.overall.correct}</td><td class="num">{sc.overall.wrong}</td><td class="num">{sc.overall.brier.toFixed(3)}</td><td class="num">{sc.overall.log_loss.toFixed(3)}</td></tr>
			</tbody>
		</table>
		<p class="small">
			80% ranges contained the result in <strong>{Math.round(sc.covered80 * 100)}%</strong> of races. Average miss
			{sc.mae.toFixed(1)} points; on average results were {Math.abs(sc.national_miss).toFixed(1)} points more
			{sc.national_miss >= 0 ? 'Democratic' : 'Republican'} than our forecast.
		</p>
	</section>
	{#if sc.vs_experts?.length}
		<section class="card">
			<h2>Against the expert ratings</h2>
			<table class="small">
				<thead><tr><th>Rater</th><th class="num">Races</th><th class="num">Their Brier</th><th class="num">Our Brier (same races)</th><th class="num">Their wrong</th><th class="num">Our wrong</th></tr></thead>
				<tbody>
					{#each sc.vs_experts as e}
						<tr><td>{e.rater}</td><td class="num">{e.races}</td><td class="num">{e.theirs.brier.toFixed(3)}</td><td class="num">{e.ours_same_races.brier.toFixed(3)}</td><td class="num">{e.theirs.wrong}</td><td class="num">{e.ours_same_races.wrong}</td></tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}
	<section class="card">
		<h2>Races we got wrong</h2>
		{#if sc.misses.length}
			<ul>
				{#each sc.misses as m}
					<li><a href={resolve('/race/[id]', { id: m.race_id })}>{m.race_id}</a>: we gave the Democratic side {Math.round(m.p_dside * 100)}%; result {m.margin >= 0 ? 'D' : 'R'}+{Math.abs(m.margin).toFixed(1)}</li>
				{/each}
			</ul>
		{:else}
			<p>None.</p>
		{/if}
	</section>
{/if}

<style>
	.card { margin-bottom: 16px; }
	.mapping { max-width: 260px; }
	tr.tot td { font-weight: 700; }
</style>
