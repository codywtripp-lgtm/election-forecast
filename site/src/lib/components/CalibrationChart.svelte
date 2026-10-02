<script lang="ts">
	import { scaleLinear, scaleSqrt } from 'd3-scale';

	/** Reliability diagram: predicted win probability (x) vs how often that side actually won (y). */
	let { bins }: { bins: { predicted: number; observed: number; n: number }[] } = $props();
	const S = 320, M = 36;
	const x = scaleLinear().domain([0, 1]).range([M, S - 10]);
	const y = scaleLinear().domain([0, 1]).range([S - M, 10]);
	const r = $derived(scaleSqrt().domain([0, Math.max(...bins.map((b) => b.n))]).range([3, 14]));
	let hover: number | null = $state(null);
</script>

<figure>
	<svg viewBox="0 0 {S} {S}" role="img" aria-label="Calibration: predicted probability versus observed frequency">
		{#each [0, 0.25, 0.5, 0.75, 1] as t}
			<line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} class="grid" />
			<text x={M - 6} y={y(t) + 4} text-anchor="end" class="tick">{t * 100}%</text>
			<text x={x(t)} y={S - M + 16} text-anchor="middle" class="tick">{t * 100}%</text>
		{/each}
		<line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} class="diag" />
		{#each bins as b, i}
			<circle cx={x(b.predicted)} cy={y(b.observed)} r={r(b.n)} class="dot" class:hl={hover === i}
				role="presentation" onmouseenter={() => (hover = i)} onmouseleave={() => (hover = null)} />
		{/each}
		<text x={(x(0) + x(1)) / 2} y={S - 2} text-anchor="middle" class="axis-label">Forecast probability</text>
		<text transform="translate(10 {(y(0) + y(1)) / 2}) rotate(-90)" text-anchor="middle" class="axis-label">Actually won</text>
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			Forecast ≈{(bins[hover].predicted * 100).toFixed(0)}%: won {(bins[hover].observed * 100).toFixed(0)}% of {bins[hover].n} cases
		{:else}
			Dots on the diagonal mean "70% forecasts came true about 70% of the time". Dot size = number of forecasts.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; max-width: 420px; }
	svg { width: 100%; height: auto; display: block; }
	.grid { stroke: var(--grid); }
	.diag { stroke: var(--ink-3); stroke-dasharray: 4 3; }
	.dot { fill: var(--dem); fill-opacity: 0.85; stroke: var(--surface); stroke-width: 2px; }
	.dot.hl { stroke: var(--ink-1); }
	.tick { font-size: 10px; fill: var(--ink-3); }
	.axis-label { font-size: 11px; fill: var(--ink-2); }
	figcaption { min-height: 3em; }
</style>
