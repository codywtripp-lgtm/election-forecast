<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { layout, hexPath } from '#lib/hexlayout.ts';
	import { classOf, fillVar } from '#lib/colors.ts';
	import { inHundred, margin as fmtMargin, partyLetter } from '#lib/format.ts';
	import { STATE_NAMES } from '#lib/geo.ts';
	import type { RaceSummary } from '#lib/types.ts';

	let { races, simWinners = null }: { races: RaceSummary[]; simWinners?: Record<string, boolean> | null } = $props();

	const byId = $derived(Object.fromEntries(races.map((r) => [r.id, r])));
	const counts = $derived(
		races.reduce((acc: Record<string, number>, r) => ((acc[r.state] = (acc[r.state] ?? 0) + 1), acc), {})
	);
	const L = $derived(layout(counts));
	const cells = $derived(
		L.hexes.map((h) => ({ ...h, id: `2026-house-${h.state}-${String(h.district).padStart(2, '0')}` }))
	);
	let hover: { r: RaceSummary; x: number; y: number } | null = $state(null);
	let wrap: HTMLDivElement | undefined = $state();

	function fill(id: string): string {
		const r = byId[id];
		if (!r) return 'var(--surface)';
		if (simWinners && id in simWinners) return simWinners[id] ? 'var(--dem)' : 'var(--rep)';
		return fillVar(r.p);
	}
	function show(e: MouseEvent | FocusEvent, id: string) {
		const r = byId[id];
		if (!r || !wrap) return;
		const box = wrap.getBoundingClientRect();
		const t = (e.target as SVGPathElement).getBoundingClientRect();
		hover = { r, x: t.left + t.width / 2 - box.left, y: t.top - box.top };
	}
	function open(id: string) {
		if (byId[id]) goto(resolve('/race/[id]', { id }));
	}
	const label = (r: RaceSummary) => `${STATE_NAMES[r.state]} ${r.id.slice(-2).replace(/^0/, '')}`;
</script>

<div class="hexmap" bind:this={wrap}>
	<svg viewBox={L.viewBox} role="group" aria-label="House forecast: one hexagon per district">
		{#each cells as c (c.id)}
			{@const r = byId[c.id]}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<path
				d={hexPath(c.x, c.y)}
				fill={fill(c.id)}
				role={r ? 'link' : undefined}
				tabindex={r ? 0 : undefined}
				aria-label={r ? `${label(r)}: ${r.d} ${inHundred(r.p)}` : undefined}
				onmouseenter={(e) => show(e, c.id)}
				onmouseleave={() => (hover = null)}
				onfocus={(e) => show(e, c.id)}
				onblur={() => (hover = null)}
				onclick={() => open(c.id)}
				onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open(c.id))}
			/>
		{/each}
		{#each L.labels as l}
			<text x={l.x} y={l.y} text-anchor="middle" class="st">{l.state}</text>
		{/each}
	</svg>
	{#if hover}
		{@const r = hover.r}
		<div class="tip" style:left="{Math.max(110, Math.min(hover.x, (wrap?.clientWidth ?? 600) - 110))}px" style:top="{hover.y}px" role="tooltip">
			<div class="tip-title">{label(r)}</div>
			<div class="tip-row"><span class="dem">{r.d} ({partyLetter(r.d_party)})</span><strong class="num">{inHundred(r.p)}</strong></div>
			{#if r.r}<div class="tip-row"><span class="rep">{r.r} (R)</span><strong class="num">{inHundred(1 - r.p)}</strong></div>{/if}
			<div class="tiny muted">{classOf(r.p).label}{#if r.n_polls === 0} · no polls{/if} · avg {fmtMargin(r.mu)}</div>
		</div>
	{/if}
</div>

<style>
	.hexmap { position: relative; width: 100%; max-width: 980px; margin: 0 auto; }
	svg { width: 100%; height: auto; display: block; }
	path { cursor: pointer; stroke: var(--surface); stroke-width: 0.6px; transition: fill 250ms ease; }
	path:hover, path:focus-visible { stroke: var(--ink-1); stroke-width: 1.5px; outline: none; }
	.st { font-size: 11px; font-weight: 600; fill: var(--ink-2); pointer-events: none; }
	.tip {
		position: absolute; transform: translate(-50%, calc(-100% - 10px)); background: var(--surface);
		border: 1px solid var(--border); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15); border-radius: 8px;
		padding: 8px 10px; pointer-events: none; min-width: 210px; font-size: 0.85rem; z-index: 5;
	}
	.tip-title { font-weight: 600; margin-bottom: 4px; }
	.tip-row { display: flex; justify-content: space-between; gap: 12px; }
</style>
