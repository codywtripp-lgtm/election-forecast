import { readData } from '#lib/server/data.ts';
import type { Summary } from '#lib/types.ts';
import type { EntryGenerator } from './$types';

export const entries: EntryGenerator = () =>
	[...new Set(readData<Summary>('summary.json').races.map((r) => r.state))].map((st) => ({ st }));

export const load = ({ params }) => {
	const s = readData<Summary>('summary.json');
	return { st: params.st, races: s.races.filter((r) => r.state === params.st) };
};
