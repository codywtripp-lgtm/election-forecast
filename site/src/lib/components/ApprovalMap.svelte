<script lang="ts">
	import { geoPath } from 'd3-geo';
	import { feature, mesh } from 'topojson-client';
	import type { Topology, GeometryCollection } from 'topojson-specification';
	import us from 'us-atlas/states-albers-10m.json';
	import { FIPS_TO_ABBR, STATE_NAMES } from '#lib/geo.ts';
	import { approvalFill } from '#lib/colors.ts';
	import { fmtDate } from '#lib/format.ts';

	type Row = { state: string; net: number; sd: number; n_polls: number; latest_poll: { pollster: string; end: string; net: number } | null };
	let { rows }: { rows: Row[] } = $props();

	const topo = us as unknown as Topology<{ states: GeometryCollection }>;
	const path = geoPath();
	const states = (feature(topo, topo.objects.states) as unknown as GeoJSON.FeatureCollection).features.map((f) => ({
		abbr: FIPS_TO_ABBR[String(f.id).padStart(2, '0')],
		d: path(f) ?? ''
	}));
	const borders = path(mesh(topo, topo.objects.states, (a, b) => a !== b)) ?? '';
	const by = $derived(Object.fromEntries(rows.map((r) => [r.state, r])));
	let hover: { r: Row; x: number; y: number } | null = $state(null);
	let wrap: HTMLDivElement | undefined = $state();
	const fmt = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(0)}`;

	function show(e: MouseEvent | FocusEvent, abbr: string) {
		const r = by[abbr];
		if (!r || !wrap) return;
		const box = wrap.getBoundingClientRect();
		const t = (e.target as SVGPathElement).getBoundingClientRect();
		hover = { r, x: t.left + t.width / 2 - box.left, y: t.top - box.top };
	}
</script>

<div class="map" bind:this={wrap}>
	<svg viewBox="0 0 975 610" role="group" aria-label="Estimated Trump net approval by state">
		{#each states as s (s.abbr)}
			{@const r = by[s.abbr]}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<path d={s.d} fill={r ? approvalFill(r.net) : 'var(--surface)'} tabindex={r ? 0 : undefined}
				aria-label={r ? `${STATE_NAMES[s.abbr]}: estimated net approval ${fmt(r.net)}` : undefined}
				onmouseenter={(e) => show(e, s.abbr)} onmouseleave={() => (hover = null)}
				onfocus={(e) => show(e, s.abbr)} onblur={() => (hover = null)} />
		{/each}
		<path d={borders} class="borders" />
	</svg>
	{#if hover}
		{@const r = hover.r}
		<div class="tip" style:left="{Math.max(110, Math.min(hover.x, (wrap?.clientWidth ?? 600) - 110))}px" style:top="{hover.y}px" role="tooltip">
			<div class="tip-title">{STATE_NAMES[r.state]}</div>
			<div>Estimated net approval <strong class="num">{fmt(r.net)}</strong> <span class="tiny muted">(±{(1.28 * r.sd).toFixed(0)})</span></div>
			{#if r.latest_poll}
				<div class="tiny muted">Latest state poll: {r.latest_poll.pollster}, {fmtDate(r.latest_poll.end)}: {fmt(r.latest_poll.net)}</div>
			{:else}
				<div class="tiny muted">No state polls: estimate from national approval and partisanship</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.map { position: relative; width: 100%; max-width: 880px; margin: 0 auto; }
	svg { width: 100%; height: auto; display: block; }
	path:hover, path:focus-visible { stroke: var(--ink-1); stroke-width: 2px; outline: none; }
	.borders { fill: none; stroke: var(--surface); stroke-width: 1px; pointer-events: none; }
	.tip {
		position: absolute; transform: translate(-50%, calc(-100% - 10px)); background: var(--surface);
		border: 1px solid var(--border); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15); border-radius: 8px;
		padding: 8px 10px; pointer-events: none; min-width: 220px; font-size: 0.85rem; z-index: 5;
	}
	.tip-title { font-weight: 600; margin-bottom: 4px; }
</style>
