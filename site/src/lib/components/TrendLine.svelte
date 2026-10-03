<script lang="ts">
	import { scaleLinear, scaleTime } from 'd3-scale';
	import { area, line } from 'd3-shape';
	import { fmtDate } from '#lib/format.ts';

	/** One series over time with an 80% band and a zero line. Positive values read as "D"/"approve". */
	let {
		points,
		posLabel,
		negLabel,
		ariaLabel
	}: { points: { date: string; value: number; sd: number }[]; posLabel: string; negLabel: string; ariaLabel: string } =
		$props();
	const W = 640, H = 220, M = { t: 12, r: 52, b: 24, l: 8 };
	const parsed = $derived(points.map((p) => ({ ...p, d: new Date(p.date + 'T12:00:00') })));
	const x = $derived(scaleTime().domain([parsed[0].d, parsed[parsed.length - 1].d]).range([M.l, W - M.r]));
	const ext = $derived(Math.max(4, ...parsed.map((p) => Math.abs(p.value) + 1.3 * p.sd)));
	const y = $derived(scaleLinear().domain([-ext, ext]).nice().range([H - M.b, M.t]));
	const ticks = $derived(y.ticks(5));
	const band = $derived(
		area<(typeof parsed)[number]>()
			.x((p) => x(p.d))
			.y0((p) => y(p.value - 1.28 * p.sd))
			.y1((p) => y(p.value + 1.28 * p.sd))(parsed) ?? ''
	);
	const path = $derived(line<(typeof parsed)[number]>().x((p) => x(p.d)).y((p) => y(p.value))(parsed) ?? '');
	let hover: number | null = $state(null);
	const signed = $derived(posLabel === '+');
	const fmt = (v: number, digits = 1) =>
		Math.abs(v) < 0.05
			? signed ? '0' : 'Even'
			: signed
				? `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}`
				: v > 0 ? `${posLabel}+${v.toFixed(digits)}` : `${negLabel}+${(-v).toFixed(digits)}`;

	function move(e: MouseEvent) {
		const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
		const px = ((e.clientX - r.left) / r.width) * W;
		let best = 0;
		parsed.forEach((p, i) => {
			if (Math.abs(x(p.d) - px) < Math.abs(x(parsed[best].d) - px)) best = i;
		});
		hover = best;
	}
	const last = $derived(parsed[parsed.length - 1]);
</script>

<figure>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label={ariaLabel} onmousemove={move} onmouseleave={() => (hover = null)}>
		{#each ticks as t}
			<line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} class={t === 0 ? 'zero' : 'grid'} />
			<text x={W - M.r + 6} y={y(t) + 4} class="tick">{fmt(t, 0)}</text>
		{/each}
		<path d={band} class="band" class:neg={last.value < 0} />
		<path d={path} class="line" class:neg={last.value < 0} />
		<circle cx={x(last.d)} cy={y(last.value)} r="4" class="dot" class:neg={last.value < 0} />
		{#if hover !== null}
			<line x1={x(parsed[hover].d)} x2={x(parsed[hover].d)} y1={M.t} y2={H - M.b} class="cross" />
			<circle cx={x(parsed[hover].d)} cy={y(parsed[hover].value)} r="5" class="dot hl" class:neg={parsed[hover].value < 0} />
		{/if}
		<text x={M.l} y={H - 6} class="tick">{fmtDate(points[0].date)} {points[0].date.slice(0, 4)}</text>
		<text x={W - M.r} y={H - 6} text-anchor="end" class="tick">{fmtDate(points[points.length - 1].date)}</text>
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			Week of {fmtDate(parsed[hover].date)}: <strong>{fmt(parsed[hover].value)}</strong>
			(80% range {fmt(parsed[hover].value - 1.28 * parsed[hover].sd)} to {fmt(parsed[hover].value + 1.28 * parsed[hover].sd)})
		{:else}
			Latest: <strong>{fmt(last.value)}</strong>. Shaded band = 80% range of the average.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	.grid { stroke: var(--grid); }
	.zero { stroke: var(--axis); stroke-width: 1.5px; }
	.tick { font-size: 11px; fill: var(--ink-3); font-variant-numeric: tabular-nums; }
	.band { fill: var(--dem); opacity: 0.15; }
	.band.neg { fill: var(--rep); }
	.line { fill: none; stroke: var(--dem); stroke-width: 2px; }
	.line.neg { stroke: var(--rep); }
	.dot { fill: var(--dem); stroke: var(--surface); stroke-width: 2px; }
	.dot.neg { fill: var(--rep); }
	.dot.hl { stroke: var(--ink-1); }
	.cross { stroke: var(--ink-3); }
	figcaption { min-height: 1.5em; }
</style>
