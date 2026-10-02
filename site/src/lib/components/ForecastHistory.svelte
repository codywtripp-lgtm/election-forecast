<script lang="ts">
	import { scaleLinear, scaleTime } from 'd3-scale';
	import { line } from 'd3-shape';
	import { fmtDate } from '#lib/format.ts';

	/** Win probability over time for the D side (the R line is its mirror, so one line + 50% reference). */
	let { dates, p, election, dName }: { dates: string[]; p: number[]; election: string; dName: string } = $props();
	const W = 640, H = 180, M = { t: 10, r: 44, b: 24, l: 8 };
	const parsed = $derived(dates.map((d) => new Date(d + 'T12:00:00')));
	const x = $derived(
		scaleTime()
			.domain([parsed[0] ?? new Date(), new Date(election + 'T12:00:00')])
			.range([M.l, W - M.r])
	);
	const y = scaleLinear().domain([0, 1]).range([H - M.b, M.t]);
	const path = $derived(line<number>().x((_, i) => x(parsed[i])).y((v) => y(v))(p) ?? '');
	let hover: number | null = $state(null);

	function move(e: MouseEvent) {
		const svg = e.currentTarget as SVGSVGElement;
		const pt = svg.getBoundingClientRect();
		const px = ((e.clientX - pt.left) / pt.width) * W;
		let best = 0;
		parsed.forEach((d, i) => { if (Math.abs(x(d) - px) < Math.abs(x(parsed[best]) - px)) best = i; });
		hover = best;
	}
</script>

<figure>
	{#if p.length < 2}
		<p class="small muted">The forecast history starts with the first published run ({dates[0] ? fmtDate(dates[0]) : 'today'}). The chart fills in as daily runs accumulate.</p>
	{/if}
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="{dName} chance of winning over time" onmousemove={move} onmouseleave={() => (hover = null)}>
		{#each [0, 0.25, 0.5, 0.75, 1] as t}
			<line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} class={t === 0.5 ? 'half' : 'grid'} />
			<text x={W - M.r + 6} y={y(t) + 4} class="tick">{t * 100}%</text>
		{/each}
		<path d={path} class="line" />
		{#each p as v, i}
			{#if p.length < 8 || i === p.length - 1}
				<circle cx={x(parsed[i])} cy={y(v)} r="4" class="dot" />
			{/if}
		{/each}
		{#if hover !== null}
			<line x1={x(parsed[hover])} x2={x(parsed[hover])} y1={M.t} y2={H - M.b} class="cross" />
			<circle cx={x(parsed[hover])} cy={y(p[hover])} r="5" class="dot hl" />
		{/if}
		<text x={M.l} y={H - 6} class="tick">{parsed[0] ? fmtDate(dates[0]) : ''}</text>
		<text x={W - M.r} y={H - 6} text-anchor="end" class="tick">Nov 3</text>
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			{fmtDate(dates[hover])}: {dName} {Math.round(p[hover] * 100)}%
		{:else}
			{dName}'s chance of winning, by forecast date.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	.grid { stroke: var(--grid); }
	.half { stroke: var(--axis); stroke-dasharray: 4 3; }
	.tick { font-size: 11px; fill: var(--ink-3); font-variant-numeric: tabular-nums; }
	.line { fill: none; stroke: var(--dem); stroke-width: 2px; }
	.dot { fill: var(--dem); stroke: var(--surface); stroke-width: 2px; }
	.dot.hl { stroke: var(--ink-1); }
	.cross { stroke: var(--ink-3); }
	figcaption { min-height: 1.5em; }
</style>
