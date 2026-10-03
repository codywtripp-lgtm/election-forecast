<script lang="ts">
	import TrendLine from '#lib/components/TrendLine.svelte';
	import SpecialsChart from '#lib/components/SpecialsChart.svelte';

	let { data } = $props();
	const t = $derived(data.t);
	const sp = $derived(t?.specials ?? []);
	const flips = $derived(sp.filter((r: any) => r.flip));
	const dFlips = $derived(flips.filter((r: any) => r.winner === 'D').length);
	const fit = $derived(t?.specials_fit);
</script>

<svelte:head><title>Trackers: generic ballot, Trump approval and special elections</title></svelte:head>

<h1>Trackers</h1>
<p class="muted">
	Running averages that update with every forecast run, built with the same pollster ratings and adjustments as the forecast.
</p>

{#if t}
	<section class="card">
		<h2>Generic congressional ballot</h2>
		<p class="small muted">Which party voters say they'll back for the House. Likely-voter basis, house effects removed. This is the
			national environment the forecast uses.</p>
		<TrendLine points={t.generic_ballot} posLabel="D" negLabel="R" ariaLabel="Generic ballot average over time" />
	</section>

	<section class="card">
		<h2>Donald Trump: net approval</h2>
		<p class="small muted">Approve minus disapprove, all adults, registered and likely voters (no likely-voter conversion for approval).</p>
		<TrendLine points={t.approval} posLabel="+" negLabel="−" ariaLabel="Net approval over time" />
	</section>

	{#if sp.length}
		<section class="card">
			<h2>Special elections vs. the 2024 baseline</h2>
			<p class="small">
				{sp.length} contested special elections since January 2025. Median swing toward
				{sp[sp.length - 1].median_to_date >= 0 ? 'Democrats' : 'Republicans'}:
				<strong>{Math.abs(sp[sp.length - 1].median_to_date).toFixed(1)} points</strong>. Seats flipped: {flips.length}
				({dFlips} to Democrats, {flips.length - dFlips} to Republicans).
			</p>
			<SpecialsChart races={sp} />
			{#if fit}
				<p class="tiny muted">
					Do specials predict November? We tested it: for 2018–2024, mapping each cycle's median special-election swing to
					the national House vote missed by {fit.loo_sd.toFixed(1)} points on average (the generic ballot misses by about 3).
					In 2024 Democrats ran {fit.cycles[3].median_swing} points ahead in specials, then lost the House vote by
					{Math.abs(fit.cycles[3].N_true).toFixed(1)}. Blending specials into the forecast made our backtest slightly worse,
					so they are shown here but <strong>not used</strong> by the model.
				</p>
			{/if}
			<p class="tiny muted">Data: {t.attribution}.</p>
		</section>
	{/if}
{:else}
	<p class="muted">Tracker data is not available yet.</p>
{/if}

<style>
	.card { margin-bottom: 16px; }
</style>
