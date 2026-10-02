<script lang="ts">
	import { geoPath } from 'd3-geo';
	import { feature, mesh } from 'topojson-client';
	import type { Topology, GeometryCollection } from 'topojson-specification';
	import us from 'us-atlas/states-albers-10m.json';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { FIPS_TO_ABBR } from '#lib/geo.ts';
	import { fillVar, classOf } from '#lib/colors.ts';
	import { inHundred, raceTitle, margin as fmtMargin } from '#lib/format.ts';
	import type { RaceSummary } from '#lib/types.ts';

	let {
		races,
		simWinners = null,
		label = 'Map of race forecasts by state'
	}: { races: RaceSummary[]; simWinners?: Record<string, boolean> | null; label?: string } = $props();

	const topo = us as unknown as Topology<{ states: GeometryCollection; nation: GeometryCollection }>;
	const path = geoPath();
	const states = (feature(topo, topo.objects.states) as unknown as GeoJSON.FeatureCollection).features.map((f) => ({
		abbr: FIPS_TO_ABBR[String(f.id).padStart(2, '0')],
		d: path(f) ?? '',
		centroid: path.centroid(f)
	}));
	const borders = path(mesh(topo, topo.objects.states, (a, b) => a !== b)) ?? '';
	const nation = path(mesh(topo, topo.objects.states, (a, b) => a === b)) ?? '';

	const byState = $derived(Object.fromEntries(races.map((r) => [r.state, r])));
	let hover: { r: RaceSummary; x: number; y: number } | null = $state(null);
	let wrap: HTMLDivElement | undefined = $state();

	function fill(abbr: string): string {
		const r = byState[abbr];
		if (!r) return 'var(--surface)';
		if (simWinners && abbr in simWinners) return simWinners[abbr] ? 'var(--dem)' : 'var(--rep)';
		return fillVar(r.p);
	}

	function show(e: MouseEvent | FocusEvent, abbr: string) {
		const r = byState[abbr];
		if (!r) return (hover = null);
		const box = wrap!.getBoundingClientRect();
		let x: number, y: number;
		if (e instanceof MouseEvent) {
			x = e.clientX - box.left;
			y = e.clientY - box.top;
		} else {
			const t = (e.target as SVGPathElement).getBoundingClientRect();
			x = t.left + t.width / 2 - box.left;
			y = t.top - box.top;
		}
		hover = { r, x, y };
	}

	function open(abbr: string) {
		const r = byState[abbr];
		if (r) goto(resolve('/race/[id]', { id: r.id }));
	}
</script>

<div class="map" bind:this={wrap}>
	<svg viewBox="0 0 975 610" role="group" aria-label={label}>
		{#each states as s (s.abbr)}
			{@const r = byState[s.abbr]}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<path
				d={s.d}
				fill={fill(s.abbr)}
				class:has={!!r}
				role={r ? 'link' : undefined}
				tabindex={r ? 0 : undefined}
				aria-label={r ? `${raceTitle(r)}: ${r.d} ${inHundred(r.p)} chance` : undefined}
				onmousemove={(e) => show(e, s.abbr)}
				onmouseleave={() => (hover = null)}
				onfocus={(e) => show(e, s.abbr)}
				onblur={() => (hover = null)}
				onclick={() => open(s.abbr)}
				onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open(s.abbr))}
			/>
		{/each}
		<path d={borders} class="borders" />
		<path d={nation} class="outline" />
	</svg>
	{#if hover}
		{@const r = hover.r}
		<div class="tip" style:left="{Math.min(hover.x, (wrap?.clientWidth ?? 600) - 120)}px" style:top="{hover.y}px" role="tooltip">
			<div class="tip-title">{raceTitle(r)}</div>
			<div class="tip-row"><span class="dem">{r.d}</span><strong class="num">{inHundred(r.p)}</strong></div>
			<div class="tip-row"><span class="rep">{r.r}</span><strong class="num">{inHundred(1 - r.p)}</strong></div>
			<div class="tiny muted">{classOf(r.p).label} · avg margin {fmtMargin(r.mu)}</div>
		</div>
	{/if}
</div>

<style>
	.map { position: relative; width: 100%; max-width: 880px; margin: 0 auto; }
	svg { width: 100%; height: auto; display: block; }
	path { transition: fill 250ms ease; }
	path.has { cursor: pointer; }
	path.has:hover, path.has:focus-visible { stroke: var(--ink-1); stroke-width: 2px; outline: none; }
	.borders { fill: none; stroke: var(--axis); stroke-width: 1px; pointer-events: none; }
	.outline { fill: none; stroke: var(--axis); stroke-width: 1px; pointer-events: none; }
	.tip {
		position: absolute;
		transform: translate(-50%, calc(-100% - 12px));
		background: var(--surface);
		border: 1px solid var(--border);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
		border-radius: 8px;
		padding: 8px 10px;
		pointer-events: none;
		min-width: 200px;
		font-size: 0.85rem;
		z-index: 5;
	}
	.tip-title { font-weight: 600; margin-bottom: 4px; }
	.tip-row { display: flex; justify-content: space-between; gap: 12px; }
</style>
