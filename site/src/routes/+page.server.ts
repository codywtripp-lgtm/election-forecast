import { hasData, readData } from '#lib/server/data.ts';
import type { Summary } from '#lib/types.ts';

export const load = () => ({
	summary: readData<Summary>('summary.json'),
	changes: hasData('changes.json') ? readData<any>('changes.json') : null
});
