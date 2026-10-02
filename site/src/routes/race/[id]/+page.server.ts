import { readData } from '#lib/server/data.ts';
import type { Summary } from '#lib/types.ts';
import type { EntryGenerator } from './$types';

export const entries: EntryGenerator = () =>
	readData<Summary>('summary.json').races.map((r) => ({ id: r.id }));

type History = { races: Record<string, { as_of: string[]; p_dside: number[]; mu: number[]; m_q10: number[]; m_q90: number[] }> };

export const load = ({ params }) => {
	const race = readData<any>(`races/${params.id}.json`);
	const history = readData<History>('history.json').races[params.id] ?? null;
	const summary = readData<Summary>('summary.json');
	return { race, history, scenarios: summary.scenarios, election: summary.election_date };
};
