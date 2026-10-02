<script lang="ts">
	import { onMount } from 'svelte';
	import { asset, resolve } from '$app/paths';
	import { fmtDate, margin, OFFICE_LABEL } from '#lib/format.ts';
	import { STATE_NAMES } from '#lib/geo.ts';

	type Poll = {
		race: string; office: string; state: string; pollster: string; sponsors: string; partisan: string | null;
		start: string; end: string; n: number | null; pop: string; mode: string; dem: number | null; rep: number | null;
		margin: number; adj: number; w: number; url: string | null;
	};
	let polls: Poll[] = $state([]);
	let loading = $state(true);
	let q = $state('');
	let office = $state('all');
	let pop = $state('all');
	let hidePartisan = $state(false);
	let limit = $state(100);

	onMount(async () => {
		polls = await (await fetch(asset('data/2026/polls.json'))).json();
		loading = false;
	});

	const label = (p: Poll) => (p.office === 'generic' ? 'Generic ballot' : `${STATE_NAMES[p.state] ?? p.state} ${OFFICE_LABEL[p.office] ?? p.office}`);
	const filtered = $derived(
		polls.filter(
			(p) =>
				(office === 'all' || p.office === office) &&
				(pop === 'all' || p.pop === pop) &&
				(!hidePartisan || !p.partisan) &&
				(!q || `${label(p)} ${p.pollster} ${p.sponsors}`.toLowerCase().includes(q.toLowerCase()))
		)
	);
	function csv() {
		const cols = ['race', 'pollster', 'sponsors', 'partisan', 'start', 'end', 'n', 'pop', 'mode', 'dem', 'rep', 'margin', 'adj', 'url'] as const;
		const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
		const body = [cols.join(','), ...filtered.map((p) => cols.map((c) => esc(p[c])).join(','))].join('\n');
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([body], { type: 'text/csv' }));
		a.download = 'polls-2026.csv';
		a.click();
	}
</script>

<svelte:head><title>2026 poll database: every Senate, governor, House and generic-ballot poll</title></svelte:head>

<h1>Poll database</h1>
<p class="muted">
	Every 2026 general-election poll we track, with our adjusted margin (likely-voter basis, house effect, sponsor and trend
	corrections) and its weight in today's average. Free to reuse under CC BY-SA 4.0 (data from VoteHub and Wikipedia).
</p>

<div class="filters card">
	<input type="search" placeholder="Search race, pollster or sponsor" bind:value={q} aria-label="Search polls" />
	<label class="small">Office
		<select bind:value={office}>
			<option value="all">All</option><option value="sen">Senate</option><option value="gov">Governor</option>
			<option value="house">House</option><option value="generic">Generic ballot</option>
		</select>
	</label>
	<label class="small">Population
		<select bind:value={pop}>
			<option value="all">All</option><option value="lv">Likely voters</option><option value="rv">Registered voters</option><option value="a">Adults</option>
		</select>
	</label>
	<label class="small"><input type="checkbox" bind:checked={hidePartisan} /> Hide partisan sponsors</label>
	<button onclick={csv} disabled={loading}>Download CSV</button>
</div>

{#if loading}
	<p class="muted">Loading polls…</p>
{:else}
	<p class="small muted" aria-live="polite">{filtered.length.toLocaleString()} polls</p>
	<div class="table-scroll card">
		<table>
			<thead>
				<tr><th>Race</th><th>Pollster</th><th>Dates</th><th class="num">Sample</th><th class="num">D–R</th><th class="num">Margin</th><th class="num">Adjusted</th><th class="num">Weight</th></tr>
			</thead>
			<tbody>
				{#each filtered.slice(0, limit) as p}
					<tr>
						<td class="small">
							{#if p.office === 'sen' || p.office === 'gov'}<a href={resolve('/race/[id]', { id: p.race })}>{label(p)}</a>{:else}{label(p)}{/if}
						</td>
						<td class="small">
							{#if p.url}<a href={p.url} rel="noopener external">{p.pollster}</a>{:else}{p.pollster}{/if}
							{#if p.partisan}<span class="chip">{p.partisan === 'DEM' ? 'D' : 'R'} sponsor</span>{/if}
							{#if p.sponsors}<div class="tiny muted">{p.sponsors}</div>{/if}
						</td>
						<td class="small">{fmtDate(p.start)}–{fmtDate(p.end)}</td>
						<td class="num small">{p.n ? Math.round(p.n).toLocaleString() : '?'} {p.pop.toUpperCase()}</td>
						<td class="num small">{#if p.dem !== null}<span class="dem">{p.dem}</span>–<span class="rep">{p.rep}</span>{/if}</td>
						<td class="num small">{margin(p.margin)}</td>
						<td class="num small">{margin(p.adj)}</td>
						<td class="num small">{(p.w * 100).toFixed(0)}%</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if filtered.length > limit}
		<button onclick={() => (limit += 200)}>Show more</button>
	{/if}
{/if}

<style>
	.filters { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; margin-bottom: 12px; }
	input[type='search'], select {
		font: inherit; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border);
		background: var(--surface); color: var(--ink-1);
	}
	input[type='search'] { flex: 1 1 240px; border-radius: 999px; padding: 6px 12px; }
	label { display: inline-flex; gap: 6px; align-items: center; }
</style>
