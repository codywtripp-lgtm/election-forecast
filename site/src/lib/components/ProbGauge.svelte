<script lang="ts">
	/** Horizontal split bar: D-side share of simulations vs Republican. A gauge that reads at a glance
	 *  and stays legible on a phone (a half-donut wastes width). */
	import { inHundred } from '#lib/format.ts';
	let { p, dName, rName }: { p: number; dName: string; rName: string } = $props();
</script>

<div class="gauge" role="img" aria-label="{dName} wins in {inHundred(p)} simulations, {rName} in {inHundred(1 - p)}">
	<div class="labels">
		<div class="side">
			<div class="name dem">{dName}</div>
			<div class="big dem num">{Math.round(p * 100)}<span class="pct">%</span></div>
		</div>
		<div class="side right">
			<div class="name rep">{rName}</div>
			<div class="big rep num">{Math.round((1 - p) * 100)}<span class="pct">%</span></div>
		</div>
	</div>
	<div class="track">
		<div class="d" style:width="{p * 100}%"></div>
		<div class="r" style:width="{(1 - p) * 100}%"></div>
		<div class="mid" aria-hidden="true"></div>
	</div>
	<p class="small muted">Share of simulated elections each candidate wins.</p>
</div>

<style>
	.labels { display: flex; justify-content: space-between; gap: 12px; }
	.side.right { text-align: right; }
	.name { font-weight: 600; }
	.big { font-size: clamp(2.2rem, 7vw, 3.2rem); font-weight: 700; line-height: 1; letter-spacing: -0.02em; }
	.pct { font-size: 0.5em; margin-left: 2px; }
	.track { position: relative; display: flex; height: 14px; border-radius: 7px; overflow: hidden; margin: 10px 0 6px; gap: 2px; background: var(--surface); }
	.d { background: var(--dem); border-radius: 7px 0 0 7px; transition: width 400ms ease; }
	.r { background: var(--rep); border-radius: 0 7px 7px 0; transition: width 400ms ease; }
	.mid { position: absolute; left: 50%; top: -3px; bottom: -3px; width: 2px; background: var(--ink-1); opacity: 0.5; }
</style>
