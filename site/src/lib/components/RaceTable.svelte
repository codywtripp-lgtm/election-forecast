<script lang="ts">
	import { resolve } from '$app/paths';
	import { classOf, fillVar, inkVar } from '#lib/colors.ts';
	import { margin, partyLetter, raceTitle } from '#lib/format.ts';
	import type { RaceSummary } from '#lib/types.ts';

	let { races, caption }: { races: RaceSummary[]; caption: string } = $props();
	let q = $state('');
	let sort: 'close' | 'state' | 'dem' = $state('close');

	const rows = $derived(
		races
			.filter((r) => !q || `${raceTitle(r)} ${r.d} ${r.r}`.toLowerCase().includes(q.toLowerCase()))
			.sort((a, b) =>
				sort === 'close' ? Math.abs(a.p - 0.5) - Math.abs(b.p - 0.5)
				: sort === 'dem' ? b.p - a.p
				: a.state.localeCompare(b.state)
			)
	);
</script>

<div class="controls">
	<label class="small">
		<span class="sr-only">Search races</span>
		<input type="search" placeholder="Search state or candidate" bind:value={q} />
	</label>
	<div class="sorts" role="group" aria-label="Sort races">
		<button aria-pressed={sort === 'close'} onclick={() => (sort = 'close')}>Closest</button>
		<button aria-pressed={sort === 'dem'} onclick={() => (sort = 'dem')}>Most D</button>
		<button aria-pressed={sort === 'state'} onclick={() => (sort = 'state')}>A–Z</button>
	</div>
</div>
<div class="table-scroll">
	<table>
		<caption class="sr-only">{caption}</caption>
		<thead>
			<tr>
				<th>Race</th>
				<th>Candidates</th>
				<th class="num">Chance</th>
				<th class="num">Avg margin</th>
				<th>Rating</th>
			</tr>
		</thead>
		<tbody>
			{#each rows as r (r.id)}
				<tr>
					<td><a href={resolve('/race/[id]', { id: r.id })}>{raceTitle(r)}</a></td>
					<td class="small">
						<span class="dem">{r.d} ({partyLetter(r.d_party)})</span><br />
						<span class="rep">{r.r} (R)</span>
					</td>
					<td class="num">
						<span class="dem">{Math.round(r.p * 100)}%</span><br />
						<span class="rep">{Math.round((1 - r.p) * 100)}%</span>
					</td>
					<td class="num small">{margin(r.mu, partyLetter(r.d_party))}</td>
					<td>
						<span class="pill" style:background={fillVar(r.p)} style:color={inkVar(r.p)}>{classOf(r.p).label}</span>
						{#if r.p_runoff > 0.05}<span class="chip">runoff {Math.round(r.p_runoff * 100)}%</span>{/if}
						{#if r.n_polls === 0}<span class="chip">no polls</span>{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; justify-content: space-between; margin-bottom: 8px; }
	input[type='search'] {
		font: inherit; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border);
		background: var(--surface); color: var(--ink-1); min-width: 220px;
	}
	.sorts { display: flex; gap: 6px; }
	.sorts button { font-size: 0.85rem; padding: 4px 10px; }
	.pill { display: inline-block; font-size: 0.78rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
	td { font-size: 0.92rem; }
</style>
