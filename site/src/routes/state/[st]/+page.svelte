<script lang="ts">
	import { resolve } from '$app/paths';
	import { classOf, fillVar, inkVar } from '#lib/colors.ts';
	import { inHundred, margin, partyLetter, raceTitle } from '#lib/format.ts';
	import { STATE_NAMES } from '#lib/geo.ts';

	let { data } = $props();
</script>

<svelte:head><title>{STATE_NAMES[data.st]} 2026 election forecast</title></svelte:head>

<nav class="small"><a href={resolve('/')}>Forecast</a></nav>
<h1>{STATE_NAMES[data.st]}</h1>
<p class="muted">Statewide races on the 2026 ballot. House districts arrive with the House forecast (by October 20).</p>

<div class="grid-2">
	{#each data.races as r (r.id)}
		<a class="card race" href={resolve('/race/[id]', { id: r.id })}>
			<div class="top">
				<h2>{raceTitle(r)}</h2>
				<span class="pill" style:background={fillVar(r.p)} style:color={inkVar(r.p)}>{classOf(r.p).label}</span>
			</div>
			<div class="row"><span class="dem">{r.d} ({partyLetter(r.d_party)})</span><strong class="num">{inHundred(r.p)}</strong></div>
			<div class="row"><span class="rep">{r.r} (R)</span><strong class="num">{inHundred(1 - r.p)}</strong></div>
			<div class="small muted">Average simulated margin {margin(r.mu, partyLetter(r.d_party))} · {r.n_polls} polls</div>
		</a>
	{/each}
</div>

<style>
	.race { display: block; color: inherit; text-decoration: none; transition: border-color 120ms; }
	.race:hover { border-color: var(--ink-3); }
	.top { display: flex; justify-content: space-between; align-items: start; gap: 8px; }
	.row { display: flex; justify-content: space-between; margin: 4px 0; }
	.pill { font-size: 0.78rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
</style>
