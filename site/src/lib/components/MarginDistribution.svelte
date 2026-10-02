<script lang="ts">
	import { scaleLinear } from 'd3-scale';
	import { margin as fmt } from '#lib/format.ts';

	/** Histogram of simulated final margins (bins of 2 points from −60 to +60). */
	let { hist, dLetter = 'D', median }: { hist: number[]; dLetter?: string; median: number } = $props();
	const W = 640, H = 170, M = { t: 8, r: 8, b: 26, l: 8 };
	const edges = Array.from({ length: 61 }, (_, i) => -60 + i * 2);
	const total = $derived(hist.reduce((a, b) => a + b, 0));
	// trim to the populated range (+ padding) so the shape fills the chart
	const first = $derived(Math.max(0, hist.findIndex((v) => v / total > 0.001) - 2));
	const last = $derived(Math.min(hist.length - 1, hist.length - 1 - [...hist].reverse().findIndex((v) => v / total > 0.001) + 2));
	const x = $derived(scaleLinear().domain([edges[first], edges[last + 1]]).range([M.l, W - M.r]));
	const y = $derived(scaleLinear().domain([0, Math.max(...hist)]).range([H - M.b, M.t]));
	const ticks = $derived(x.ticks(7));
	let hover: number | null = $state(null);
</script>

<figure>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="Distribution of simulated margins; median {fmt(median, dLetter)}">
		{#each hist as v, i}
			{#if i >= first && i <= last}
				{@const x0 = x(edges[i])}
				{@const w = x(edges[i + 1]) - x0 - 1.5}
				<rect x={x0} y={y(v)} width={Math.max(w, 0.5)} height={H - M.b - y(v)} rx="2"
					class={edges[i] >= 0 ? 'dem' : 'rep'} class:dim={hover !== null && hover !== i} />
				<rect role="presentation" x={x0} y={M.t} width={w + 1.5} height={H - M.b - M.t} fill="transparent"
					onmouseenter={() => (hover = i)} onmouseleave={() => (hover = null)} />
			{/if}
		{/each}
		<line x1={x(0)} x2={x(0)} y1={M.t} y2={H - M.b} class="zero" />
		<line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} class="axis" />
		{#each ticks as t}
			<text x={x(t)} y={H - 8} text-anchor="middle" class="tick">{t === 0 ? 'Even' : t > 0 ? `${dLetter}+${t}` : `R+${-t}`}</text>
		{/each}
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			{fmt(edges[hover] + 1, dLetter)} (±1): {((hist[hover] / total) * 100).toFixed(1)}% of simulations
		{:else}
			Final margin across simulations. Median {fmt(median, dLetter)}.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	.dem { fill: var(--dem); }
	.rep { fill: var(--rep); }
	.dim { opacity: 0.45; }
	.zero { stroke: var(--ink-2); stroke-dasharray: 3 3; }
	.axis { stroke: var(--axis); }
	.tick { font-size: 11px; fill: var(--ink-3); }
	figcaption { min-height: 1.5em; }
</style>
