/**
 * Units: parallel tickets in one loop book. A todo that carries `observe`, `kind`, `lands`, or `agents` metadata is a
 * unit (an `anchor` alone is not), and so is the one open todo a child's name or brief names by ticket id. Each unit gets the phases of its own kind over the book's
 * entries that belong to it (its children's links, landings, reviews, its task-anchor runs) plus the entries nobody owns. A loop with fewer
 * than two units is read as one loop, as before.
 */

import { type Book, type Entry, KINDS, type Kind, type Task, isOpenTask, validFollowup } from "./book.ts";
import { type Inputs, type Phases, computePhases } from "./phases.ts";

export type Unit = { id: number; subject: string; label: string; open: boolean; anchor?: string; observe: string[]; kind?: Kind; lands?: string; agents: string[] };

const TICKET_KEY = /\b([A-Za-z]{1,10})-?(\d{2,6})\b/g;
const TICKET_LABEL = /\b([A-Za-z]{1,10})-(\d{2,6})\b/;

/** Ticket ids in `text` as lowercase letters and digits, so `MP-4366` and a worker named `mp4366-hq` name the same ticket. */
export function ticketKeys(text: string): string[] {
	return [...new Set([...text.matchAll(TICKET_KEY)].map((found) => `${found[1].toLowerCase()}${found[2]}`))];
}

const strings = (value: unknown): string[] => (Array.isArray(value) ? value : [value]).filter((item): item is string => typeof item === "string" && item.trim() !== "").map((item) => item.trim());

function ofTask(task: Task): Unit {
	const meta = task.metadata ?? {};
	const kind = KINDS.find((name) => name === meta.kind);
	const label = TICKET_LABEL.exec(task.subject);
	return {
		id: task.id,
		subject: task.subject,
		label: label ? `${label[1].toUpperCase()}-${label[2]}` : `#${task.id}`,
		open: isOpenTask(task),
		...(typeof meta.anchor === "string" && meta.anchor.trim() ? { anchor: meta.anchor.trim() } : {}),
		observe: strings(meta.observe),
		...(kind ? { kind } : {}),
		...(typeof meta.lands === "string" && meta.lands.trim() ? { lands: meta.lands.trim() } : {}),
		agents: strings(meta.agents),
	};
}

/** A task `anchor` alone is the todo's own check (a plain session may carry several); only coordination metadata makes a unit. */
const hasUnitMetadata = (unit: Unit): boolean => unit.observe.length > 0 || unit.kind !== undefined || unit.lands !== undefined || unit.agents.length > 0;

/** The tickets a todo names: in its subject, and its `followup` when that is a ticket id. */
function taskTickets(task: Task): string[] {
	const followup = task.metadata?.followup;
	return ticketKeys(`${task.subject} ${validFollowup(followup) ? String(followup) : ""}`);
}

export type Units = { units: Unit[]; /** Child id to the id of the unit it works for; a child absent from it belongs to the whole loop. */ bound: Map<string, number> };

/**
 * The units of the loop and which unit each linked child works for: the unit whose `agents` names the child, else the one open todo that
 * holds a ticket id the child's name or brief holds, when exactly one does. A todo bound by ticket becomes a unit.
 */
export function unitsOf(entries: Entry[], todos: Task[]): Units {
	const units = todos.map(ofTask).filter(hasUnitMetadata);
	const bound = new Map<string, number>();
	const latest = new Map<string, Entry>();
	for (const entry of entries) if (entry.stage === "link" && typeof entry.child === "string") latest.set(entry.child, entry);
	for (const link of latest.values()) {
		const child = String(link.child);
		const named = units.find((unit) => unit.agents.includes(String(link.name ?? "")) || unit.agents.includes(child));
		if (named) {
			bound.set(child, named.id);
			continue;
		}
		const tickets = Array.isArray(link.tickets) ? link.tickets.map(String) : [];
		const matches = tickets.length ? todos.filter((task) => isOpenTask(task) && taskTickets(task).some((key) => tickets.includes(key))) : [];
		if (matches.length !== 1) continue;
		bound.set(child, matches[0].id);
		if (!units.some((unit) => unit.id === matches[0].id)) units.push(ofTask(matches[0]));
	}
	return { units: units.sort((a, b) => a.id - b.id), bound };
}

/** The unit with this todo id, if the loop has one. */
export const unitById = (found: Units, id: number): Unit | undefined => found.units.find((unit) => unit.id === id);

/** The children that belong to `unit` (named for it, or for no unit at all). */
export function childrenOf(entries: Entry[], found: Units, unit: Unit): string[] {
	return [...new Set(entries.filter((entry) => entry.stage === "link" && typeof entry.child === "string").map((entry) => String(entry.child)))].filter((child) => !found.bound.has(child) || found.bound.get(child) === unit.id);
}

/**
 * The book's entries as `unit` sees them: everything nobody owns, the links, results, landings, adopted runs and reviews of its children,
 * and its own task-anchor runs as verify entries; the unit's kind, anchor and observe list come last, so they win over the loop's.
 */
export function unitEntries(entries: Entry[], unit: Unit, found: Units): Entry[] {
	const mine = (child: unknown): boolean => typeof child !== "string" || !found.bound.has(child) || found.bound.get(child) === unit.id;
	const kept: Entry[] = [];
	for (const entry of entries) {
		switch (entry.stage) {
			case "taskrun":
				if (entry.id === unit.id) kept.push({ ...entry, stage: "verify", task: unit.id });
				break;
			case "link":
			case "result":
			case "land":
				if (mine(entry.child)) kept.push(entry);
				break;
			case "verify":
			case "check":
				if (entry.task !== undefined) {
					if (entry.task === unit.id) kept.push(entry);
				} else if (entry.child !== undefined) {
					if (mine(entry.child)) kept.push(entry);
				} else if (entry.checkpoint !== undefined ? unit.observe.length === 0 : unit.anchor === undefined) {
					kept.push(entry);
				}
				break;
			case "review":
				if (mine(entry.child)) kept.push(entry);
				break;
			default:
				kept.push(entry);
		}
	}
	const ts = entries.at(-1)?.ts ?? new Date().toISOString();
	if (unit.kind) kept.push({ ts, stage: "kind", kind: unit.kind });
	if (unit.anchor) kept.push({ ts, stage: "anchor", check: unit.anchor });
	if (unit.observe.length) kept.push({ ts, stage: "observe", items: unit.observe });
	return kept;
}

export type UnitRow = { unit: Unit; phases: Phases };

/** The loop's phases, and a row per unit when the loop has two or more. The loop's own phases are those of the first unit not yet done. */
export function computeLoop(book: Pick<Book, "entries">, inputs: Omit<Inputs, "entries">): { phases: Phases; rows: UnitRow[] } {
	const found = unitsOf(book.entries, inputs.todos);
	if (found.units.length < 2) return { phases: computePhases(book, inputs), rows: [] };
	const rows = found.units.map((unit) => ({ unit, phases: computePhases({ entries: unitEntries(book.entries, unit, found) }, inputs) }));
	return { phases: (rows.find((row) => row.phases.next !== "close") ?? rows[rows.length - 1]).phases, rows };
}

/** `MP-4366 reviewed · act ✓ → verify (missing: …)`. */
export function unitLine(row: UnitRow): string {
	const { phases } = row;
	return `${row.unit.label} ${phases.kind} · ${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}${phases.missing ? ` (missing: ${phases.missing})` : ""}`;
}
