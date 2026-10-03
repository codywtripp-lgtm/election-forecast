import { hasData, readData } from '#lib/server/data.ts';

export const load = () => ({ sc: hasData('scorecard.json') ? readData<any>('scorecard.json') : null });
