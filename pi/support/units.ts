/**
 * Units: parallel tickets in one loop book. A todo that carries `observe`, `kind`, `lands`, or `agents` metadata is a
 * unit (an `anchor` alone is not), and so is the one open todo a child's name or brief names by ticket id. Each unit gets the phases of its own kind over the book's
 * entries that belong to it (its children's links, landings, reviews, its task-anchor runs, the `back` and `skip` given its task, the
 * edits in its trees) plus the entries nobody owns. A unit's trees are its workers' worktrees (or checkouts), else the loop's own repos;
 * its checks compare only those trees, so one unit's change leaves another unit's check alone. A loop with fewer than two units is read
 * as one loop, as before.
 */

import { statSync } from "node:fs";
import {
	type Book,
	type Entry,
	KINDS,
	type Kind,
	REVIEWERS,
	type Scope,
	type Task,
	type TreeCache,
	anchorCommand,
	anchorIsCommand,
	bases,
	findParentBooks,
	isOpenTask,
	latestTasks,
	loopObserve,
	observeList,
	ownBases,
	real,
	retiredEntry,
	taskOfEntry,
	todoEpoch,
	todoListEnd,
	validFollowup,
} from "./book.ts";
import { type Link, liveness } from "./host.ts";
import { type Inputs, OWN_ANCHOR, type Phases, UNIT_VERIFY, computePhases, droppedObservations, openObservation, reflectStatus } from "./phases.ts";

export type Unit = { id: number; subject: string; label: string; open: boolean; anchor?: string; observe: string[]; kind?: Kind; lands?: string; agents: string[] };

/** A ticket id in a child's name, brief, or branch: `MP-4366`, `mp4366-hq`, `fix-mp-4366-guard`. A number never starts with 0. */
const TICKET_KEY = /\b([A-Za-z]{1,10})-?([1-9]\d{1,5})\b/g;
/**
 * A ticket id in a todo subject: an uppercase key, a hyphen, and a number not starting with 0, standing alone (`MP-4366`) or followed
 * by a hyphen (`MP-4366-followup`), as a tracker writes it. A host name (`agent-tower-01`) or a dated lowercase name (`release-1117`,
 * `macq-1120`) names no ticket and makes no unit.
 */
const SUBJECT_TICKET = /(?<![\w-])([A-Z]{2,10})-([1-9]\d{1,5})(?!\w)/g;

const keyOf = (found: RegExpMatchArray): string => `${found[1].toLowerCase()}${found[2]}`;

/** Ticket ids in `text` as lowercase letters and digits, so `MP-4366` and a worker named `mp4366-hq` name the same ticket. */
export function ticketKeys(text: string): string[] {
	return [...new Set([...text.matchAll(TICKET_KEY)].map(keyOf))];
}

/** The ticket ids a todo subject names, by the stricter subject rule. */
function subjectTickets(subject: string): RegExpMatchArray[] {
	return [...subject.matchAll(SUBJECT_TICKET)];
}

const strings = (value: unknown): string[] => (Array.isArray(value) ? value : [value]).filter((item): item is string => typeof item === "string" && item.trim() !== "").map((item) => item.trim());

function ofTask(task: Task): Unit {
	const meta = task.metadata ?? {};
	const kind = KINDS.find((name) => name === meta.kind);
	const label = subjectTickets(task.subject)[0];
	return {
		id: task.id,
		subject: task.subject,
		label: label ? `${label[1].toUpperCase()}-${label[2]}` : `#${task.id}`,
		open: isOpenTask(task),
		...(typeof meta.anchor === "string" && meta.anchor.trim() ? { anchor: meta.anchor.trim() } : {}),
		observe: observeList(meta.observe),
		...(kind ? { kind } : {}),
		...(typeof meta.lands === "string" && meta.lands.trim() ? { lands: meta.lands.trim() } : {}),
		agents: strings(meta.agents),
	};
}

/**
 * True when a checkpoint tick or drop of no task counts for `unit`: a unit that lists no items inherits the loop's, and the unit whose
 * own metadata the loop's list was written from (the first todo's) has that list, while its own list still equals it (a todo update
 * that changed it makes the ticks numbered for the old text no longer the unit's). A book written before entries named their source
 * matches by text: the unit whose list equals the loop's. Any other unit lists items of its own, whatever their text.
 */
function sharesLoopItems(unit: Unit, entries: Entry[]): boolean {
	if (unit.observe.length === 0) return true;
	const loop = loopObserve(entries);
	if (loop.source !== unit.id && !loop.legacy) return false;
	const items = observeList(loop.items);
	return unit.observe.length === items.length && unit.observe.every((item, i) => item === items[i]);
}

/** A task `anchor` alone is the todo's own check (a plain session may carry several); only coordination metadata makes a unit. */
const hasUnitMetadata = (unit: Unit): boolean => unit.observe.length > 0 || unit.kind !== undefined || unit.lands !== undefined || unit.agents.length > 0;

/** The tickets a todo names: in its subject, and its `followup` when that is a ticket id. */
export function taskTickets(task: Task): string[] {
	const followup = task.metadata?.followup;
	return [...new Set([...subjectTickets(task.subject).map(keyOf), ...(validFollowup(followup) ? ticketKeys(String(followup)) : [])])];
}

export type Units = {
	units: Unit[];
	/** Child id to the id of the unit it works for; a child absent from it belongs to the whole loop. */
	bound: Map<string, number>;
	/** Unit id to the repo roots that hold its code: its workers' worktrees (or checkouts), else the loop's own repos. */
	trees: Map<number, string[]>;
};

/** The todos as the book recorded them, for a reader that has no todo list (a child reading its parent's book). */
export function tasksFromEntries(entries: Entry[]): Task[] {
	return latestTasks(entries).map((entry) => {
		const metadata: Record<string, unknown> = {};
		for (const key of ["anchor", "observe", "kind", "lands", "agents", "followup"]) if (entry[key] !== undefined) metadata[key] = entry[key];
		return { id: entry.id as number, subject: String(entry.subject ?? ""), status: String(entry.status ?? "pending"), metadata };
	});
}

/** The latest link of each child. */
function latestLinks(entries: Entry[]): Map<string, Entry> {
	const latest = new Map<string, Entry>();
	for (const entry of entries) if (entry.stage === "link" && typeof entry.child === "string") latest.set(entry.child, entry);
	return latest;
}

const within = (root: string, path: string): boolean => path === root || path.startsWith(`${root}/`);

/** The repo root a linked child works in: the base its link recorded (its worktree), else the loop's own repo that holds its directory. */
function childRepo(entries: Entry[], link: Entry): string | undefined {
	const child = String(link.child);
	const base = bases(entries).find((item) => item.child === child);
	if (base) return base.repo;
	const worktree = link.worktree as { path?: unknown } | undefined;
	const dir = typeof worktree?.path === "string" ? real(worktree.path) : typeof link.cwd === "string" ? real(link.cwd) : undefined;
	if (!dir) return undefined;
	return ownBases(entries)
		.map((item) => item.repo)
		.filter((repo) => within(repo, dir))
		.sort((a, b) => b.length - a.length)[0];
}

/** The open todo that exactly one of `tickets` names, if exactly one does. */
export function todoForTickets(todos: Task[], tickets: string[]): number | undefined {
	if (tickets.length === 0) return undefined;
	const matches = todos.filter((task) => isOpenTask(task) && taskTickets(task).some((key) => tickets.includes(key)));
	return matches.length === 1 ? matches[0].id : undefined;
}

/**
 * The units of the loop and which unit each linked child works for: the unit whose `agents` names the child, else the one open todo that
 * holds a ticket id the child's name or brief holds, when exactly one does. A todo bound by ticket becomes a unit.
 */
export function unitsOf(entries: Entry[], todos: Task[]): Units {
	const units = todos.map(ofTask).filter(hasUnitMetadata);
	const bound = new Map<string, number>();
	const latest = latestLinks(entries);
	for (const link of latest.values()) {
		const child = String(link.child);
		const named = units.find((unit) => unit.agents.includes(String(link.name ?? "")) || unit.agents.includes(child));
		if (named) {
			bound.set(child, named.id);
			continue;
		}
		const tickets = Array.isArray(link.tickets) ? link.tickets.map(String) : [];
		const id = todoForTickets(todos, tickets);
		const task = todos.find((item) => item.id === id);
		if (!task) continue;
		bound.set(child, task.id);
		if (!units.some((unit) => unit.id === task.id)) units.push(ofTask(task));
	}
	const own = ownBases(entries).map((base) => base.repo);
	const trees = new Map<number, string[]>();
	for (const unit of units) {
		// A reviewer reads a unit's code and writes none, so its checkout is not one of the unit's trees.
		const workers = [...latest.values()].filter((link) => bound.get(String(link.child)) === unit.id && !REVIEWERS.has(String(link.agent ?? "")));
		const repos = [...new Set(workers.map((link) => childRepo(entries, link)).filter((repo): repo is string => repo !== undefined))];
		trees.set(unit.id, repos.length ? repos : [...new Set(own)]);
	}
	return { units: units.sort((a, b) => a.id - b.id), bound, trees };
}

/** The unit `child` is bound to among the todos of `entries`, in a loop of two or more units. */
function boundUnit(entries: Entry[], child: string): Unit | undefined {
	const found = unitsOf(entries, tasksFromEntries(entries));
	return found.units.length >= 2 ? unitById(found, found.bound.get(child) ?? -1) : undefined;
}

/** True when a todo of the current list, in any status, names the child `link` records: by its `agents`, or by a ticket of the link. */
function namedByCurrentList(entries: Entry[], link: Entry): boolean {
	const names = [String(link.child), String(link.name ?? "")];
	const tickets = Array.isArray(link.tickets) ? link.tickets.map(String) : [];
	return tasksFromEntries(entries).some((task) => ofTask(task).agents.some((agent) => names.includes(agent)) || taskTickets(task).some((key) => tickets.includes(key)));
}

/**
 * The anchor a linked child inherits: the anchor of the unit it is bound to in a loop of two or more units (none when that unit has no
 * anchor of its own: the loop's anchor is another ticket's), else its parent's loop anchor command. A child linked under an earlier
 * todo list (its parent's book was adopted, or its todos cleared, while it worked) that no todo of the current list names keeps the
 * unit it was dispatched for: the todos of the list its link was recorded under.
 * Once a todo of the current list names it, the current list decides, whatever the todo's status or the number of units.
 */
export function childAnchor(id: string, env: NodeJS.ProcessEnv = process.env): string | undefined {
	for (const book of findParentBooks(id, env)) {
		const { entries } = book;
		let unit = boundUnit(entries, id);
		const linked = entries.findLastIndex((entry) => entry.stage === "link" && entry.child === id);
		if (!unit && linked >= 0 && linked < todoEpoch(entries) && !namedByCurrentList(entries, entries[linked])) unit = boundUnit(entries.slice(0, todoListEnd(entries, linked)), id);
		if (unit) return unit.anchor;
		const anchor = anchorCommand(entries);
		if (anchor && anchorIsCommand(entries)) return anchor;
	}
	return undefined;
}

/** The unit a dispatch or result works for: the one open todo its brief names by ticket, else the unit its child is bound to. */
export function unitOfDispatch(found: Units, todos: Task[], child: string | undefined, brief: string): number | undefined {
	const named = todoForTickets(todos, ticketKeys(brief));
	if (named !== undefined && found.units.some((unit) => unit.id === named)) return named;
	return child === undefined ? undefined : found.bound.get(child);
}

export type Dispatch = { child: string; index: number; /** The unit the dispatch works for; absent for the whole loop. */ task?: number };

/**
 * How long after its last write to its session a gone child still counts as out: 1 s poll + 0.5 s sidecar wait + 15 s handoff
 * git (pi-herdr-agents maestro/adapters/pi/pi-harness-adapter.ts:584, completion.ts:129-136, maestro/runtime/worktree-operations.ts:46),
 * rounded up. A child killed in the middle of work counts for the same time, then stops. A dispatch with `accept` waits longer: the
 * child runs the check itself before it settles, possibly after its last write to the session, and the host reruns it after the child
 * exits and delivers the result after that (maestro/runtime/pi-run-session.ts:746), so twice its link's `acceptSec`, the check's
 * timeout, is added.
 */
export const DELIVERY_GRACE_MS = 30_000;

/** True when the child's session file was written within the delivery grace: a result that has not arrived yet is still on its way. */
function deliveryPending(sessionFile: unknown, acceptSec: unknown): boolean {
	if (typeof sessionFile !== "string") return false;
	const grace = DELIVERY_GRACE_MS + (typeof acceptSec === "number" && acceptSec > 0 ? 2 * acceptSec * 1000 : 0);
	try {
		return Date.now() - statSync(sessionFile).mtimeMs < grace;
	} catch {
		return false;
	}
}

/**
 * The dispatches still out: for each child, its latest `link` or `send` when no `result` of that child follows it, while its host does
 * not say the child is gone (a killed pane or a rebooted box never sends a result). A child that finished exits before its result is
 * delivered (pi-herdr-agents polls the child's `.exit` sidecar once a second, then takes the worktree handoff, up to 15 s of git, before
 * it sends the message), so a gone child whose session file was written within `DELIVERY_GRACE_MS` still counts as out. A link
 * recorded before links carried `cwd` comes from a book that kept no results, so it is not counted as out.
 */
export function outDispatches(entries: Entry[], found?: Units): Dispatch[] {
	const latest = new Map<string, number>();
	entries.forEach((entry, index) => {
		if ((entry.stage === "link" || entry.stage === "send") && typeof entry.child === "string") latest.set(entry.child, index);
	});
	const out: Dispatch[] = [];
	for (const [child, index] of latest) {
		const dispatch = entries[index];
		if (dispatch.stage === "link" && typeof dispatch.cwd !== "string") continue;
		if (entries.slice(index + 1).some((entry) => entry.stage === "result" && entry.child === child)) continue;
		const link = entries.find((entry) => entry.stage === "link" && entry.child === child);
		const sessionFile = typeof dispatch.sessionFile === "string" ? dispatch.sessionFile : link?.sessionFile;
		// Only a `link` carries a check: a follow-up `send` goes to a persistent child, which takes no `accept`.
		const acceptSec = dispatch.stage === "link" ? dispatch.acceptSec : undefined;
		if (liveness({ ...(link ?? {}), child, ...(typeof sessionFile === "string" ? { sessionFile } : {}) } as Link) === "gone" && !deliveryPending(sessionFile, acceptSec)) continue;
		const task = taskOfEntry(entries, index) ?? found?.bound.get(child);
		out.push({ child, index, ...(task !== undefined ? { task } : {}) });
	}
	return out;
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
 * The loop's anchor and its untasked runs are no unit's: in a coordinator book the loop anchor is whichever ticket set it, so a unit
 * without an anchor of its own reads none and its anchor phase names its todo. An entry recorded for a todo of an earlier todo list
 * (before an `adopt` or a `todo clear`) belongs to no unit: the unit that now holds that id is another todo, which earns its own evidence.
 */
export function unitEntries(entries: Entry[], unit: Unit, found: Units): Entry[] {
	const mine = (child: unknown): boolean => typeof child !== "string" || !found.bound.has(child) || found.bound.get(child) === unit.id;
	const ownTrees = found.trees.get(unit.id) ?? [];
	// A change counts for the units whose trees hold its repo; one no unit's tree holds, or whose repo is unknown, counts for every unit.
	const touches = (repo: unknown): boolean =>
		typeof repo !== "string" || ownTrees.length === 0 || ownTrees.includes(repo) || ![...found.trees.values()].some((trees) => trees.includes(repo));
	const kept: Entry[] = [];
	const epoch = todoEpoch(entries);
	// A checkpoint tick or drop of no task addresses the loop's own items, so it counts for the units that have them.
	const shares = sharesLoopItems(unit, entries);
	for (const [index, entry] of entries.entries()) {
		// A task-tied entry of an earlier todo list is evidence for a todo that is gone.
		if (retiredEntry(entries, index, epoch)) continue;
		switch (entry.stage) {
			case "taskrun":
				if (entry.id === unit.id) kept.push({ ...entry, stage: "verify", task: unit.id });
				break;
			case "link":
			case "result":
				if (mine(entry.child)) kept.push(entry);
				break;
			case "send":
			case "land":
			case "review":
				if (entry.task !== undefined ? entry.task === unit.id : mine(entry.child)) kept.push(entry);
				break;
			case "edit":
				if (touches(entry.repo)) kept.push(entry);
				break;
			case "anchor":
				break;
			case "back":
			case "skip":
				if (entry.task !== undefined ? entry.task === unit.id : entry.stage === "skip" && entry.phase === "observe" ? shares : true) kept.push(entry);
				break;
			case "verify":
			case "check":
				if (entry.task !== undefined) {
					if (entry.task === unit.id) kept.push(entry);
				} else if (entry.child !== undefined) {
					if (mine(entry.child)) kept.push(entry);
				} else if (entry.checkpoint !== undefined && shares) {
					kept.push(entry);
				}
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

/** The book as the loop's own items see it: a tick, drop, or check addressed to a task is that unit's, so it is left out. */
function loopLevelEntries(entries: Entry[]): Entry[] {
	const epoch = todoEpoch(entries);
	return entries.filter((entry, index) => !retiredEntry(entries, index, epoch) && !((entry.stage === "verify" || entry.stage === "check" || entry.stage === "skip") && entry.task !== undefined));
}

/**
 * The loop's phases, and a row per unit when the loop has two or more. The loop's own phases are those of the first open unit not yet
 * done (a completed todo's missing evidence is the close's to name, not the live line's), else of the first unit not yet done, with the
 * loop's one reflect phase in place of the units' (friction is the loop's, so a unit row never waits on it).
 * When every unit lists items of its own, none reads the loop's list, so the loop's items are read here: an item still open is
 * `loopOpen`, and it holds the loop's line at verify, and the close, until it is ticked or dropped; a dropped one is carried in `skipped`.
 */
export function computeLoop(book: Pick<Book, "entries">, inputs: Omit<Inputs, "entries">): { phases: Phases; rows: UnitRow[]; found: Units; loopOpen?: string } {
	const found = unitsOf(book.entries, inputs.todos);
	const cache: TreeCache = inputs.scope?.cache ?? new Map();
	if (found.units.length < 2) return { phases: computePhases(book, { ...inputs, scope: { ...inputs.scope, cache } }), rows: [], found };
	const rows = found.units.map((unit) => ({ unit, phases: computePhases({ entries: unitEntries(book.entries, unit, found) }, { ...inputs, scope: unitScope(found, unit, cache), unit: unit.id }) }));
	const chosen = rows.find((row) => row.unit.open && row.phases.next !== "close") ?? rows.find((row) => row.phases.next !== "close") ?? rows[rows.length - 1];
	// A `skip` of reflect with no task reaches every unit, so the chosen unit holds it; otherwise the loop's friction decides.
	const declared = chosen.phases.statuses.find((status) => status.name === "reflect" && status.state === "skipped" && status.auto !== true);
	const reflect = declared ?? reflectStatus(book.entries, inputs.env);
	const orphaned = !found.units.some((unit) => sharesLoopItems(unit, book.entries));
	const loopEntries = loopLevelEntries(book.entries);
	const loopOpen = orphaned ? openObservation(loopEntries, 0) : undefined;
	// A drop of a unit's own item is named with the unit; a drop of a loop item that a unit reads is the same text on each of them.
	const shared = new Set(droppedObservations(loopEntries));
	const unitDrops = rows.flatMap((row) => row.phases.skipped.filter((text) => text.startsWith("observe ") && !shared.has(text)).map((text) => `${row.unit.label} ${text}`));
	const skipped = [...chosen.phases.skipped.filter((text) => !text.startsWith("observe ")), ...shared, ...unitDrops];
	const phases: Phases = { ...chosen.phases, statuses: chosen.phases.statuses.map((status) => (status.name === "reflect" ? reflect : status)), skipped };
	if (loopOpen) {
		phases.next = phases.next === "close" ? "verify" : phases.next;
		phases.missing = phases.missing ? `${phases.missing}; ${loopOpen}` : loopOpen;
	} else if (phases.next === "close" && reflect.state === "missing") {
		phases.next = "reflect";
		phases.missing = reflect.note;
	}
	return { phases, rows, found, ...(loopOpen ? { loopOpen } : {}) };
}

/** The trees a unit's readings compare: its own trees, or all when it has none it can tell. */
export function unitScope(found: Units, unit: Unit, cache?: TreeCache): Scope {
	const trees = found.trees.get(unit.id) ?? [];
	return { ...(trees.length ? { comparable: (repo: string) => trees.includes(repo) } : {}), ...(cache ? { cache } : {}) };
}

/** `MP-4366 reviewed · act ✓ → verify (missing: …)`. */
export function unitLine(row: UnitRow): string {
	const { phases } = row;
	return `${row.unit.label} ${phases.kind} · ${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}${phases.missing ? ` (missing: ${phases.missing})` : ""}`;
}

const BRIEF_LIMIT = 40;

/**
 * What a widget line names as missing: `anchor run` for a pending anchor run (`anchor run or verify` for a unit, which a declared `verify`
 * with its task also closes), `own anchor` for a unit without one, else the note cut to one short phrase.
 */
export function briefMissing(missing: string): string {
	if (/^a passing run of `/.test(missing)) return missing.includes(`, or ${UNIT_VERIFY}`) ? "anchor run or verify" : "anchor run";
	if (missing.startsWith(`${OWN_ANCHOR} (`)) return OWN_ANCHOR;
	const flat = missing.replace(/\s+/g, " ").trim();
	return flat.length > BRIEF_LIMIT ? `${flat.slice(0, BRIEF_LIMIT - 1).trimEnd()}…` : flat;
}

/** A unit's state in the widget: `unitLine` without the label, with the missing note cut short; `read` keeps the full note. */
function widgetState(row: UnitRow): string {
	const { phases } = row;
	return `${phases.kind} · ${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}${phases.missing ? ` (missing: ${briefMissing(phases.missing)})` : ""}`;
}

const ROW_LABELS = 4;

/**
 * The units' lines in the widget below the editor: units in the same state share one line that names them (`MP-3506, MP-3507 inline ·
 * start → anchor (missing: own anchor)`), at most four labels and `+N`, in the order of their first unit. Only open todos get a line:
 * the widget shows the work still in hand, and `read` and the close name what a completed todo left unproved.
 */
export function unitWidgetLines(rows: UnitRow[]): string[] {
	const groups = new Map<string, string[]>();
	for (const row of rows.filter((item) => item.unit.open)) groups.set(widgetState(row), [...(groups.get(widgetState(row)) ?? []), row.unit.label]);
	return [...groups].map(([state, labels]) => `${labels.slice(0, ROW_LABELS).join(", ")}${labels.length > ROW_LABELS ? ` +${labels.length - ROW_LABELS}` : ""} ${state}`);
}
