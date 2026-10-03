<script lang="ts">
	import { scaleLinear, scaleTime } from 'd3-scale';
	import { line } from 'd3-shape';
	import { fmtDate } from '#lib/format.ts';

	/** Small line chart for an economic series (its own scale, latest value labelled, hover readout). */
	let { points, unit, label }: { points: { date: string; value: number }[]; unit: string; label: string } = $props();
	const W = 320, H = 130, M = { t: 10, r: 10, b: 20, l: 34 };
	const p = $derived(points.map((q) => ({ ...q, d: new Date(q.date + 'T12:00:00') })));
	const x = $derived(scaleTime().domain([p[0].d, p[p.length - 1].d]).range([M.l, W - M.r]));
	const y = $derived(scaleLinear().domain([Math.min(...p.map((q) => q.value)), Math.max(...p.map((q) => q.value))]).nice(4).range([H - M.b, M.t]));
	const d = $derived(line<(typeof p)[number]>().x((q) => x(q.d)).y((q) => y(q.value))(p) ?? '');
	let hover: number | null = $state(null);
	const fmt = (v: number) => (unit === '$/gal' ? `$${v.toFixed(2)}` : unit === '%' ? `${v.toFixed(1)}%` : v.toFixed(1));
	function move(e: MouseEvent) {
		const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
		const px = ((e.clientX - r.left) / r.width) * W;
		let best = 0;
		p.forEach((q, i) => { if (Math.abs(x(q.d) - px) < Math.abs(x(p[best].d) - px)) best = i; });
		hover = best;
	}
	const last = $derived(p[p.length - 1]);
</script>

<figure>
	<figcaption class="small"><strong>{label}</strong>: <span class="num">{fmt(last.value)}</span> <span class="tiny muted">({fmtDate(last.date)} {last.date.slice(0, 4)})</span></figcaption>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label} over time" onmousemove={move} onmouseleave={() => (hover = null)}>
		{#each y.ticks(4) as t}
			<line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} class="grid" />
			<text x={M.l - 4} y={y(t) + 3} text-anchor="end" class="tick">{fmt(t)}</text>
		{/each}
		<path {d} class="ln" />
		{#if hover !== null}
			<line x1={x(p[hover].d)} x2={x(p[hover].d)} y1={M.t} y2={H - M.b} class="cross" />
			<circle cx={x(p[hover].d)} cy={y(p[hover].value)} r="3.5" class="dot" />
		{/if}
		<text x={M.l} y={H - 4} class="tick">{p[0].date.slice(0, 4)}</text>
	</svg>
	<div class="tiny muted read">{#if hover !== null}{fmtDate(p[hover].date)} {p[hover].date.slice(0, 4)}: {fmt(p[hover].value)}{/if}</div>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	.grid { stroke: var(--grid); }
	.tick { font-size: 10px; fill: var(--ink-3); }
	.ln { fill: none; stroke: var(--ink-2); stroke-width: 2px; }
	.dot { fill: var(--ink-1); }
	.cross { stroke: var(--ink-3); }
	.read { min-height: 1.3em; }
</style>
