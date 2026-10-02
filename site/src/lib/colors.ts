/** Diverging blue (D side) ↔ red (R) with a neutral gray toss-up band (dataviz reference palette).
 *  Seven ordered classes; the CSS variables carry light/dark steps. */
export const CLASSES = [
	{ key: 'safe-r', label: 'Safe R', min: 0, max: 0.05 },
	{ key: 'likely-r', label: 'Likely R', min: 0.05, max: 0.25 },
	{ key: 'lean-r', label: 'Lean R', min: 0.25, max: 0.4 },
	{ key: 'tossup', label: 'Toss-up', min: 0.4, max: 0.6 },
	{ key: 'lean-d', label: 'Lean D', min: 0.6, max: 0.75 },
	{ key: 'likely-d', label: 'Likely D', min: 0.75, max: 0.95 },
	{ key: 'safe-d', label: 'Safe D', min: 0.95, max: 1.0001 }
] as const;

export type ClassKey = (typeof CLASSES)[number]['key'];

export function classOf(pD: number): (typeof CLASSES)[number] {
	return CLASSES.find((c) => pD >= c.min && pD < c.max) ?? CLASSES[3];
}

export function fillVar(pD: number): string {
	return `var(--c-${classOf(pD).key})`;
}

/** Text colour on a filled class (per-theme tokens, so contrast holds in light and dark). */
export function inkVar(pD: number): string {
	return `var(--on-${classOf(pD).key})`;
}
