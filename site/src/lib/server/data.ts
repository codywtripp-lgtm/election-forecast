import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(process.cwd(), 'static', 'data', '2026');

export function readData<T = unknown>(name: string): T {
	return JSON.parse(readFileSync(join(ROOT, name), 'utf-8')) as T;
}

export function hasData(name: string): boolean {
	return existsSync(join(ROOT, name));
}
