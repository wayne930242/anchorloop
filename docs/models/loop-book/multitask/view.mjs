// The family checks: both units on one line, then what the turn shows.
import { step as words, units } from "./words.mjs";

export const title = `a coordinator with two units (${process.env.MULTITASK_DESIGN ?? "today"})`;

export function state(v) {
	const parts = [units(v)];
	if (v.closed) return "closed";
	if (v.handed) parts.push("new session");
	if (v.idle) parts.push("turn over");
	return parts.join("; ");
}

export const step = words;
