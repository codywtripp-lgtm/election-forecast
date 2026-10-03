<script lang="ts">
	import { scaleLinear } from 'd3-scale';
	import { line } from 'd3-shape';
	/** Compact trend line (no axes); the last point is marked. Colour by sign of the latest value. */
	let { values, label, posVar = 'var(--approve)', negVar = 'var(--disapprove)' }:
		{ values: number[]; label: string; posVar?: string; negVar?: string } = $props();
	const W = 220, H = 48;
	const x = $derived(scaleLinear().domain([0, Math.max(1, values.length - 1)]).range([2, W - 6]));
	const y = $derived(scaleLinear().domain([Math.min(...values, 0), Math.max(...values, 0)]).range([H - 4, 4]));
	const d = $derived(line<number>().x((_, i) => x(i)).y((v) => y(v))(values) ?? '');
	const last = $derived(values[values.length - 1]);
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label={label}>
	<line x1="0" x2={W} y1={y(0)} y2={y(0)} class="zero" />
	<path {d} fill="none" stroke={last >= 0 ? posVar : negVar} stroke-width="2" />
	<circle cx={x(values.length - 1)} cy={y(last)} r="3.5" fill={last >= 0 ? posVar : negVar} />
</svg>

<style>
	svg { width: 100%; max-width: 220px; height: auto; display: block; }
	.zero { stroke: var(--axis); stroke-dasharray: 3 3; }
</style>
