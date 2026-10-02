<script lang="ts">
	import { scaleBand, scaleLinear } from 'd3-scale';

	/** Distribution of Democratic-caucus seats across simulations. Bars at or above `majority`
	 *  are D-coloured, below are R-coloured (the threshold also differs: R needs 50 with the VP). */
	let {
		hist,
		majority,
		repMajorityAt,
		total,
		unit = 'seats',
		highlight = null
	}: {
		hist: Record<string, number>;
		majority: number;
		repMajorityAt: number;
		total: number;
		unit?: string;
		highlight?: number | null;
	} = $props();

	const W = 640, H = 200, M = { t: 10, r: 8, b: 28, l: 8 };
	const entries = $derived(Object.entries(hist).map(([k, v]) => ({ k: +k, v })).sort((a, b) => a.k - b.k));
	const n = $derived(entries.reduce((s, e) => s + e.v, 0));
	const lo = $derived(Math.max(0, Math.min(...entries.map((e) => e.k)) - 1));
	const hi = $derived(Math.max(...entries.map((e) => e.k)) + 1);
	const keys = $derived(Array.from({ length: hi - lo + 1 }, (_, i) => lo + i));
	const x = $derived(scaleBand<number>().domain(keys).range([M.l, W - M.r]).paddingInner(0.12));
	const y = $derived(scaleLinear().domain([0, Math.max(...entries.map((e) => e.v)) || 1]).range([H - M.b, M.t]));
	const byK = $derived(Object.fromEntries(entries.map((e) => [e.k, e.v])));
	let hover: number | null = $state(null);
	const ticks = $derived(keys.filter((k) => k % 2 === 0 || keys.length < 14));

	function side(k: number): 'dem' | 'rep' | 'none' {
		if (k >= majority) return 'dem';
		if (total - k >= repMajorityAt) return 'rep';
		return 'none';
	}
</script>

<figure>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="Distribution of Democratic {unit} across simulations">
		{#each keys as k}
			{@const v = byK[k] ?? 0}
			{@const h = H - M.b - y(v)}
			{#if v > 0}
				<rect
					x={x(k)} y={y(v)} width={x.bandwidth()} height={Math.max(h, 1)} rx="3"
					class={side(k)} class:hl={highlight === k} class:dim={hover !== null && hover !== k}
				/>
			{/if}
			<rect
				role="presentation"
				x={x(k)} y={M.t} width={x.bandwidth()} height={H - M.b - M.t} fill="transparent"
				onmouseenter={() => (hover = k)} onmouseleave={() => (hover = null)}
			/>
		{/each}
		<line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} class="axis" />
		{#each ticks as k}
			<text x={(x(k) ?? 0) + x.bandwidth() / 2} y={H - 10} text-anchor="middle" class="tick">{k}</text>
		{/each}
		{#if x(majority) !== undefined}
			<line x1={(x(majority) ?? 0) - 2} x2={(x(majority) ?? 0) - 2} y1={M.t} y2={H - M.b} class="maj" />
		{/if}
	</svg>
	<figcaption class="small muted">
		{#if hover !== null}
			<strong class="num">{hover} D – {total - hover} R</strong>:
			{(((byK[hover] ?? 0) / n) * 100).toFixed(1)}% of simulations
		{:else}
			Democratic {unit} in each simulation (hover a bar). The dashed line marks {majority} — a Democratic majority.
		{/if}
	</figcaption>
</figure>

<style>
	figure { margin: 0; }
	svg { width: 100%; height: auto; display: block; }
	rect.dem { fill: var(--dem); }
	rect.rep { fill: var(--rep); }
	rect.none { fill: var(--axis); }
	rect.hl { stroke: var(--ink-1); stroke-width: 2px; }
	rect.dim { opacity: 0.45; }
	.axis { stroke: var(--axis); }
	.maj { stroke: var(--ink-2); stroke-dasharray: 4 3; }
	.tick { font-size: 11px; fill: var(--ink-3); font-variant-numeric: tabular-nums; }
	figcaption { min-height: 1.5em; margin-top: 4px; }
</style>
