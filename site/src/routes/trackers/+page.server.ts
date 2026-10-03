import { hasData, readData } from '#lib/server/data.ts';

export const load = () => ({ t: hasData('trackers.json') ? readData<any>('trackers.json') : null });
