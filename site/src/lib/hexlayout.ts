/**
 * House hex layout: one equal-size hexagon per district, grouped into a compact cluster per state,
 * clusters placed near each state's real position and pushed apart until they don't overlap.
 * Deterministic (same output on the server and in the browser). Within a state, districts are
 * placed in number order along a hex spiral — positions inside a state are NOT geographic.
 */
import { geoPath } from 'd3-geo';
import { feature } from 'topojson-client';
import type { Topology, GeometryCollection } from 'topojson-specification';
import us from 'us-atlas/states-albers-10m.json';
import { FIPS_TO_ABBR } from './geo.ts';

export interface Hex { id: string; state: string; district: number; x: number; y: number }
export interface StateLabel { state: string; x: number; y: number }

const R = 14; // hex radius (px in the 975×610 frame)
const W = Math.sqrt(3) * R;

/** First n cells of a hex spiral in axial coordinates. */
function spiral(n: number): [number, number][] {
	const out: [number, number][] = [[0, 0]];
	const dirs: [number, number][] = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
	for (let ring = 1; out.length < n; ring++) {
		let q = -ring, r = ring; // start at direction 4 * ring
		for (let side = 0; side < 6 && out.length < n; side++) {
			for (let step = 0; step < ring && out.length < n; step++) {
				out.push([q, r]);
				q += dirs[side][0];
				r += dirs[side][1];
			}
		}
	}
	return out.slice(0, n);
}

export function hexPath(cx: number, cy: number, r = R - 0.8): string {
	let d = '';
	for (let i = 0; i < 6; i++) {
		const a = (Math.PI / 180) * (60 * i - 30);
		d += `${i ? 'L' : 'M'}${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
	}
	return d + 'Z';
}

// Manual nudges for anchors that sit badly once clusters grow (Northeast corridor, islands).
const NUDGE: Record<string, [number, number]> = {
	AK: [60, -40], HI: [40, 0], FL: [30, 0], NJ: [30, 10], MD: [20, 25], DE: [35, 25], CT: [30, 10], RI: [40, 10],
	MA: [35, 0], NH: [15, -10], VT: [0, -20], ME: [10, -10], DC: [20, 30]
};

export function layout(counts: Record<string, number>): { hexes: Hex[]; labels: StateLabel[]; viewBox: string } {
	const topo = us as unknown as Topology<{ states: GeometryCollection }>;
	const path = geoPath();
	const fc = feature(topo, topo.objects.states) as unknown as GeoJSON.FeatureCollection;
	const anchors: Record<string, [number, number]> = {};
	for (const f of fc.features) {
		const st = FIPS_TO_ABBR[String(f.id).padStart(2, '0')];
		if (!st) continue;
		const [x, y] = path.centroid(f);
		const n = NUDGE[st] ?? [0, 0];
		anchors[st] = [x + n[0], y + n[1]];
	}
	const states = Object.keys(counts).filter((s) => anchors[s]).sort();
	const nodes = states.map((s) => ({
		s, x: anchors[s][0], y: anchors[s][1], ax: anchors[s][0], ay: anchors[s][1],
		rad: R * 1.05 * Math.sqrt(counts[s] * 1.2) + R * 0.9
	}));
	// relax: pairwise separation + weak pull to anchor
	for (let it = 0; it < 400; it++) {
		for (let i = 0; i < nodes.length; i++) {
			for (let j = i + 1; j < nodes.length; j++) {
				const a = nodes[i], b = nodes[j];
				let dx = b.x - a.x, dy = b.y - a.y;
				let d = Math.hypot(dx, dy) || 0.01;
				const min = a.rad + b.rad + 2;
				if (d < min) {
					const push = (min - d) / 2;
					dx /= d; dy /= d;
					a.x -= dx * push; a.y -= dy * push;
					b.x += dx * push; b.y += dy * push;
				}
			}
		}
		for (const n of nodes) {
			n.x += (n.ax - n.x) * 0.02;
			n.y += (n.ay - n.y) * 0.02;
		}
	}
	const hexes: Hex[] = [];
	const labels: StateLabel[] = [];
	for (const n of nodes) {
		const cells = spiral(counts[n.s]);
		cells.forEach(([q, r], k) => {
			hexes.push({
				id: '', state: n.s, district: k + 1,
				x: n.x + W * (q + r / 2), y: n.y + 1.5 * R * r
			});
		});
		const top = Math.min(...cells.map(([, r]) => n.y + 1.5 * R * r));
		labels.push({ state: n.s, x: n.x, y: top - R - 3 });
	}
	const xs = hexes.map((h) => h.x), ys = [...hexes.map((h) => h.y), ...labels.map((l) => l.y)];
	const pad = 16;
	const minX = Math.min(...xs) - pad, minY = Math.min(...ys) - pad;
	const viewBox = `${minX.toFixed(0)} ${minY.toFixed(0)} ${(Math.max(...xs) - minX + pad).toFixed(0)} ${(Math.max(...ys) - minY + pad).toFixed(0)}`;
	return { hexes, labels, viewBox };
}
