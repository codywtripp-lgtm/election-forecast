import { STATE_NAMES } from './geo';

export const OFFICE_LABEL: Record<string, string> = { sen: 'Senate', gov: 'Governor', house: 'House' };

export function pct(p: number, digits = 0): string {
	return `${(p * 100).toFixed(digits)}%`;
}

/** "68 in 100" — rounds to whole simulations-per-hundred but never shows 0 or 100 for non-certain events. */
export function inHundred(p: number): string {
	let n = Math.round(p * 100);
	if (n === 0 && p > 0) n = '<1' as unknown as number;
	if (n === 100 && p < 1) n = '>99' as unknown as number;
	return `${n} in 100`;
}

export function margin(m: number, d = 'D', r = 'R'): string {
	if (Math.abs(m) < 0.05) return 'Even';
	return m > 0 ? `${d}+${m.toFixed(1)}` : `${r}+${(-m).toFixed(1)}`;
}

const AT_LARGE = new Set(['AK', 'DE', 'ND', 'SD', 'VT', 'WY']);

export function raceTitle(r: { office: string; state: string; special?: boolean; district?: number | null; id?: string; race_id?: string }): string {
	const name = STATE_NAMES[r.state] ?? r.state;
	if (r.office === 'house') {
		const d = r.district ?? Number((r.id ?? r.race_id ?? '').slice(-2));
		return AT_LARGE.has(r.state) ? `${name} at-large House seat` : `${name}'s ${ordinal(d)} District`;
	}
	return `${name} ${OFFICE_LABEL[r.office]}${r.special ? ' (special)' : ''}`;
}

export function ordinal(n: number): string {
	const s = ['th', 'st', 'nd', 'rd'], v = n % 100;
	return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export function partyLetter(party: string | null | undefined): string {
	if (!party) return '?';
	return party === 'DEM' ? 'D' : party === 'REP' ? 'R' : party === 'IND' ? 'I' : party.slice(0, 1);
}

export function fmtDate(iso: string): string {
	const d = new Date(iso.length === 10 ? iso + 'T12:00:00' : iso);
	return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function fmtUpdated(iso: string): string {
	const d = new Date(iso);
	return d.toLocaleString('en-US', {
		month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
	});
}
