import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { marked } from 'marked';
import { hasData, readData } from '#lib/server/data.ts';

export const load = () => {
	// The methodology page is the repo's own docs/METHODOLOGY.md, so the page and the spec can't drift apart.
	const md = readFileSync(join(process.cwd(), '..', 'docs', 'METHODOLOGY.md'), 'utf-8');
	const html = marked.parse(md, { async: false }) as string;
	const backtest = hasData('backtest.json') ? readData<any>('backtest.json') : null;
	const sensitivity = hasData('sensitivity.json') ? readData<any>('sensitivity.json') : null;
	const weighting = (readData<any>('summary.json') as any).weighting_correction ?? null;
	const pollsters = (readData<any[]>('pollsters.json') ?? [])
		.filter((p: any) => p.n >= 15 && p.last_cycle >= 2018)
		.sort((a: any, b: any) => a.tau2 - b.tau2);
	const changelog = readFileSync(join(process.cwd(), '..', 'data', 'manual', 'changelog.csv'), 'utf-8')
		.trim().split(/\r?\n/).slice(1)
		.map((l) => { const i = l.indexOf(','); return { date: l.slice(0, i), change: l.slice(i + 1).replace(/^"|"$/g, '') }; })
		.reverse();
	return { html, backtest, pollsters, sensitivity, weighting, changelog };
};
