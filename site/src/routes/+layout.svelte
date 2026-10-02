<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import SummaryBar from '#lib/components/SummaryBar.svelte';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';

	let { data, children } = $props();
	const nav = [
		{ href: '/', label: 'Forecast', routes: ['/', '/race/[id]', '/state/[st]'] },
		{ href: '/polls', label: 'Polls', routes: ['/polls'] },
		{ href: '/methodology', label: 'Methodology', routes: ['/methodology'] }
	] as const;
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<meta name="description" content="An independent, open-methodology forecast of the 2026 U.S. Senate, governor and House elections." />
</svelte:head>

<a class="sr-only" href="#main">Skip to content</a>
<header class="site-header">
	<div class="wrap head-row">
		<a class="brand" href={resolve('/')}>Open Forecast <span class="muted">2026</span></a>
		<nav aria-label="Main">
			{#each nav as n}
				<a href={resolve(n.href)} aria-current={(n.routes as readonly string[]).includes(page.route.id ?? '') ? 'page' : undefined}>{n.label}</a>
			{/each}
		</nav>
	</div>
	<SummaryBar bar={data.bar} />
</header>

<main id="main" class="wrap">
	{@render children()}
</main>

<footer class="wrap site-footer small muted">
	<p>
		Forecast run <code>{data.bar.run_id}</code>. Every number traces to versioned code and data —
		<a href="https://github.com/codywtripp-lgtm/election-forecast">source and run manifests on GitHub</a>.
		No prediction-market data is used anywhere on this site.
	</p>
	<p>
		Polls: <a href="https://votehub.com/polls/api/">VoteHub</a> (CC BY 4.0), FiveThirtyEight archive (CC BY 4.0),
		Wikipedia (CC BY-SA 4.0). Results: MIT Election Data + Science Lab (CC0). Demographics: U.S. Census ACS 2024.
		Our poll database is published under CC BY-SA 4.0.
	</p>
</footer>

<style>
	.site-header {
		position: sticky;
		top: 0;
		z-index: 20;
		background: color-mix(in srgb, var(--page) 92%, transparent);
		backdrop-filter: blur(8px);
		border-bottom: 1px solid var(--border);
	}
	@media (max-width: 640px) {
		.site-header { position: static; backdrop-filter: none; }
	}
	.head-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 10px; padding-bottom: 4px; flex-wrap: wrap; }
	.brand { font-weight: 700; color: var(--ink-1); text-decoration: none; letter-spacing: -0.01em; }
	nav { display: flex; gap: 16px; }
	nav a { color: var(--ink-2); text-decoration: none; font-size: 0.95rem; padding: 4px 0; }
	nav a[aria-current='page'] { color: var(--ink-1); box-shadow: inset 0 -2px 0 var(--ink-1); }
	main { padding-top: 20px; padding-bottom: 40px; min-height: 60vh; }
	.site-footer { border-top: 1px solid var(--border); padding-top: 16px; padding-bottom: 32px; }
</style>
