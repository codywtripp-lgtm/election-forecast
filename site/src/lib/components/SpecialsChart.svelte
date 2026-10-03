<script lang="ts">
	import { scaleLinear, scaleTime } from 'd3-scale';
	import { line } from 'd3-shape';
	import { fmtDate } from '#lib/format.ts';

	type Sp = { date: string; state: string; district: string; winner: string; flip: boolean; margin: number; pres_margin: number; swing: number; median_to_date: number };
	let { races }: { races: Sp[] } = $props();
	const W = 640, H = 260, M = { t: 12, r: 52, b: 24, l: 8 };
	const pts = $derived(races.map((r) => ({ ...r, d: new Date(r.date + 'T12:00:00') })));
	const x = $derived(scaleTime().domain([pts[0].d, pts[pts.length - 1].d]).range([M.l + 6, W - M.r - 6]));
	const ext = $derived(Math.min(60, Math.max(20, ...pts.map((p) => Math.abs(p.swing) + 2))));
	const y = $derived(scaleLinear().domain([-ext, ext]).nice().range([H - M.b, M.t]));
	const med = $derived(line<(typeof pts)[number]>().x((p) => x(p.d)).y((p) => y(p.median_to_date))(pts) ?? '');
	let hover: number | null = $state(null);
	const fmt = (v: number) => (v === 0 ? '0' : v > 0 ? `D+${v}` : `R+${-v}`);
</script>

<figure>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="Special election results compared with the 2024 presidential result in the same district">
		{#each y.ticks(6) as t}
			<line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} class={t === 0 ? 'zero' : 'grid'} />
			<text x={W - M.r + 6} y={y(t) + 4} class="tick">{fmt(t)}</text>
		{/each}
		{#each pts as p, i}
			<circle cx={x(p.d)} cy={y(p.swing)} r={hover === i ? 6 : 4} class={p.swing >= 0 ? 'd' : 'r'} class:flip={p.flip}
				role="presentation" onmouseenter={() => (hover = i)} onmouseleave={() => (hover = null)} />
		{/each}
		<path d={med} class="med" />
		<text x={M.l} y={H - 6} class="tick">{fmtDate(races[0].date)} {races[0].date.slice(0, 4)}</text>
		<text x={W - M.r} y={H - 6} text-anchor="end" class="tick">{fmtDate(races[races.length - 1].date)}</text>
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			{@const p = pts[hover]}
			{fmtDate(p.date)} {p.date.slice(0, 4)}, {p.state} {p.district}: result {fmt(p.margin)} vs. 2024 president {fmt(p.pres_margin)} →
			<strong>swing {fmt(p.swing)}</strong>{p.flip ? ' (seat flipped)' : ''}
		{:else}
			Each dot is one special election (state legislative or congressional): how much better Democrats (blue, above zero) or
			Republicans (red, below) did than the 2024 presidential result there. Ringed dots flipped the seat. The line is the
			median swing to date.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	.grid { stroke: var(--grid); }
	.zero { stroke: var(--axis); stroke-width: 1.5px; }
	.tick { font-size: 11px; fill: var(--ink-3); }
	circle { stroke: var(--surface); stroke-width: 1.5px; cursor: default; }
	circle.d { fill: var(--dem); }
	circle.r { fill: var(--rep); }
	circle.flip { stroke: var(--ink-1); stroke-width: 2px; }
	.med { fill: none; stroke: var(--ink-2); stroke-width: 2px; stroke-dasharray: 5 3; }
	figcaption { min-height: 3em; }
</style>
