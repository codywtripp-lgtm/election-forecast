<script lang="ts">
	import TrendLine from '#lib/components/TrendLine.svelte';
	import SpecialsChart from '#lib/components/SpecialsChart.svelte';
	import MiniLine from '#lib/components/MiniLine.svelte';
	import { fmtDate } from '#lib/format.ts';

	let { data } = $props();
	const t = $derived(data.t);
	const sp = $derived(t?.specials ?? []);
	const flips = $derived(sp.filter((r: any) => r.flip));
	const dFlips = $derived(flips.filter((r: any) => r.winner === 'D').length);
	const fit = $derived(t?.specials_fit);
	const otherNets = $derived(Object.entries(t?.nets ?? {}).filter(([k]) => k !== 'approval') as [string, any][]);
	const popLabel: Record<string, string> = { a: 'adults', rv: 'registered voters', lv: 'likely voters' };
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

	{#if otherNets.length}
		<section class="card">
			<h2>Approval and favorability</h2>
			<p class="small muted">Net (approve − disapprove, or favorable − unfavorable), same averaging as above.</p>
			<div class="grid-2">
				{#each otherNets as [k, v]}
					<div>
						<h3>{v.label}</h3>
						<TrendLine points={v.points} posLabel="+" negLabel="−" ariaLabel="{v.label} over time" />
						<p class="tiny muted">{v.n_polls} polls.</p>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	{#if t.mood?.length}
		<section class="card">
			<h2>Public mood</h2>
			<p class="small muted">
				Recent published results on what voters are feeling. Pollsters word these questions differently, so we show each
				result with its source instead of averaging them.
			</p>
			<div class="mood">
				{#each t.mood as m}
					<div class="mood-topic">
						<h3>{m.title}</h3>
						{#each m.polls.slice(0, m.topic === 'right_track' ? 4 : 3) as pl}
							<div class="reading">
								<div class="tiny muted">
									<a href={pl.url} rel="noopener external">{pl.pollster}{pl.sponsor ? ` / ${pl.sponsor}` : ''}</a>,
									{fmtDate(pl.end)} {pl.end.slice(0, 4)} · {popLabel[pl.population] ?? pl.population}
								</div>
								{#each pl.items as it}
									<div class="item"><span class="small">{it.item}</span>
										<span class="bar" style:width="{it.value * 1.6}px" aria-hidden="true"></span>
										<strong class="num small">{it.value}%</strong></div>
								{/each}
								{#if pl.note}<div class="tiny muted">{pl.note}</div>{/if}
							</div>
						{/each}
					</div>
				{/each}
			</div>
		</section>
	{/if}

	{#if t.economy?.length}
		<section class="card">
			<h2>The economy</h2>
			<p class="small muted">Official data: what voters are living through. Sources: U.S. Bureau of Labor Statistics, Bureau of
				Economic Analysis, Energy Information Administration, and University of Michigan Surveys of Consumers, via FRED (Federal
				Reserve Bank of St. Louis).</p>
			<div class="econ">
				{#each t.economy as e}
					<MiniLine points={e.points} unit={e.unit} label={e.label} />
				{/each}
			</div>
		</section>
	{/if}

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
	.mood { display: grid; gap: 16px 28px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
	.reading { margin-bottom: 10px; }
	.item { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
	.item .small { flex: 1; }
	.bar { display: inline-block; height: 6px; border-radius: 3px; background: var(--axis); max-width: 120px; }
	.econ { display: grid; gap: 16px 24px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
</style>
