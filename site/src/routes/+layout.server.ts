import { readData } from '#lib/server/data.ts';
import type { Summary } from '#lib/types.ts';

export const load = () => {
	const s = readData<Summary>('summary.json');
	return {
		bar: {
			updated: s.updated,
			run_id: s.run_id,
			days: s.days_to_election,
			sen: s.national.sen,
			gov: s.national.gov
		}
	};
};
