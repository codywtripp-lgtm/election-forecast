<script lang="ts">
	import { fmtUpdated, inHundred } from '#lib/format.ts';
	import type { Chamber } from '#lib/types.ts';

	let { bar }: { bar: { updated: string; run_id: string; days: number; sen: Chamber; gov: Chamber } } = $props();
	const sen = $derived(bar.sen);
	const senLeader = $derived(
		(sen.p_dem_control ?? 0) >= (sen.p_rep_control ?? 0)
			? { party: 'Democrats', cls: 'dem', p: sen.p_dem_control ?? 0 }
			: { party: 'Republicans', cls: 'rep', p: sen.p_rep_control ?? 0 }
	);
	const govD = $derived(Math.round(bar.gov.dem_seats_mean));
	const govR = $derived(50 - govD);
</script>

<div class="bar wrap" role="region" aria-label="Forecast summary">
	<div class="item">
		<span class="label">Senate</span>
		<span><strong class={senLeader.cls}>{senLeader.party}</strong> win control in
			<strong class="num">{inHundred(senLeader.p)}</strong> simulations</span>
		<span class="seats num muted small">avg {sen.dem_seats_mean.toFixed(1)} D – {sen.rep_seats_mean.toFixed(1)} R</span>
	</div>
	<div class="item wide-only">
		<span class="label">House</span>
		<span class="muted">Forecast launches by Oct 20</span>
	</div>
	<div class="item wide-only">
		<span class="label">Governors</span>
		<span class="num"><strong class="dem">{govD} D</strong> · <strong class="rep">{govR} R</strong> <span class="muted small">expected after Nov 3</span></span>
	</div>
	<div class="item updated small muted">
		<span>Updated {fmtUpdated(bar.updated)}</span>
		<span class="wide-only">{bar.days} days to Election Day</span>
	</div>
</div>

<style>
	.bar {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 4px 20px;
		padding-top: 6px;
		padding-bottom: 8px;
		font-size: 0.9rem;
	}
	.item { display: flex; flex-direction: column; min-width: 0; }
	.label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2); font-weight: 600; }
	.updated { justify-content: center; }
	@media (max-width: 640px) {
		.bar { grid-template-columns: 1fr; font-size: 0.85rem; gap: 0; padding-bottom: 6px; }
		.seats, .wide-only, .label { display: none; }
		.updated { font-size: 0.75rem; }
	}
</style>
