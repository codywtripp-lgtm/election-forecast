import { hasData, readData } from '#lib/server/data.ts';
import type { Summary } from '#lib/types.ts';

export const load = () => ({
	summary: readData<Summary>('summary.json'),
	changes: hasData('changes.json') ? readData<any>('changes.json') : null,
	trackers: hasData('trackers.json') ? { approval: readData<any>('trackers.json').approval } : null,
	approvalStates: hasData('approval_states.json') ? readData<any>('approval_states.json') : null
});
