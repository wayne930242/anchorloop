/**
 * The loop book: one YAML file per open loop, kept under the agent dir.
 * A header is written once; every later fact is one JSON flow-mapping line under `entries:`, appended
 * with a single O_APPEND write, so parallel writers never interleave and the file stays valid YAML.
 * Each extension reads the book from disk, so no state is shared between extensions in memory.
 */

import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { closeSync, constants, copyFileSync, existsSync, mkdirSync, mkdtempSync, openSync, readdirSync, readFileSync, realpathSync, renameSync, rmdirSync, rmSync, statSync, unlinkSync, utimesSync, writeSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { childId as hostChildId, childName, childSession } from "./host.ts";

export const KINDS = ["quick", "inline", "reviewed", "durable"] as const;
/** The subagent roles whose `Blocking:` verdict is a review round. */
export const REVIEWERS: ReadonlySet<string> = new Set(["reviewer", "adversarial-reviewer"]);
export type Kind = (typeof KINDS)[number];

/** Entries arrays are append-only: nothing replaces, removes or edits an entry in place. The event memos (friction by array length) rely on it. */
export type Entry = { ts: string; stage: string; [key: string]: unknown };
export type Book = { path: string; header: Record<string, unknown>; entries: Entry[] };

/** What the book needs to know about the calling session. */
export type Who = {
	cwd: string;
	sessionManager: { getSessionId?(): string; getSessionFile?(): string | undefined; getBranch(): unknown[] };
};

const STALE_BOOK_MS = 7 * 24 * 60 * 60 * 1000;
const STALE_UNSAVED_MS = 24 * 60 * 60 * 1000;

export function booksRoot(env: NodeJS.ProcessEnv = process.env): string {
	if (env.ANCHORLOOP_BOOKS_DIR) return env.ANCHORLOOP_BOOKS_DIR;
	return join(env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent"), "anchorloop", "books");
}

export function real(path: string): string {
	try {
		return realpathSync(path);
	} catch {
		return resolve(path);
	}
}

export function projectSlug(cwd: string): string {
	return real(cwd).replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(-80) || "root";
}

export function childId(env: NodeJS.ProcessEnv = process.env): string | undefined {
	return hostChildId(env);
}

function safe(id: string): string {
	return id.replace(/[^A-Za-z0-9._-]/g, "_");
}

/** Runs an event handler so a book I/O failure never blocks the tool or the turn it observes. */
export function guarded<Args extends unknown[], Result>(handler: (...args: Args) => Result): (...args: Args) => Result | undefined {
	return (...args) => {
		try {
			const result = handler(...args);
			if (result instanceof Promise) return result.catch(() => undefined) as Result;
			return result;
		} catch {
			return undefined;
		}
	};
}

export function bookPath(who: Who, env: NodeJS.ProcessEnv = process.env): string {
	const dir = join(booksRoot(env), projectSlug(who.cwd));
	const child = childId(env);
	if (child) return join(dir, "agents", `${safe(child)}.yml`);
	return join(dir, `${safe(who.sessionManager.getSessionId?.() || `pid-${process.pid}`)}.yml`);
}

export function parseBook(path: string): Book | undefined {
	let text: string;
	try {
		text = readFileSync(path, "utf-8");
	} catch {
		return undefined;
	}
	const header: Record<string, unknown> = {};
	const entries: Entry[] = [];
	let inEntries = false;
	for (const line of text.split("\n")) {
		if (!line || line.startsWith("#")) continue;
		if (line === "entries:") {
			inEntries = true;
		} else if (inEntries) {
			if (!line.startsWith("- ")) continue;
			try {
				entries.push(JSON.parse(line.slice(2)) as Entry);
			} catch {
				// A line that is not an entry is skipped; the book stays readable.
			}
		} else {
			const split = line.indexOf(": ");
			if (split < 0) continue;
			try {
				header[line.slice(0, split)] = JSON.parse(line.slice(split + 2));
			} catch {
				// A header line that is not JSON is skipped.
			}
		}
	}
	return { path, header, entries };
}

export function openBook(who: Who, env: NodeJS.ProcessEnv = process.env): Book | undefined {
	return parseBook(bookPath(who, env));
}

/** A subagent that closed its loop keeps its book for main; such a book is no longer an open loop. */
export function isClosed(book: Book): boolean {
	return book.entries.at(-1)?.stage === "close";
}

/** The open loop's book, or undefined when there is none or the book was closed. */
export function openLoop(who: Who, env: NodeJS.ProcessEnv = process.env): Book | undefined {
	const book = openBook(who, env);
	return book && !isClosed(book) ? book : undefined;
}

/** Opens `path` for appending; only a new book may create the file, so a book swept away is never recreated without its header. */
function openForAppend(path: string, create: boolean): number {
	const flags = create ? "a" : constants.O_WRONLY | constants.O_APPEND;
	try {
		return openSync(path, flags);
	} catch (error) {
		// Another session's sweep may remove the directory between mkdir and open; a new book recreates it once.
		if (!create || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
		mkdirSync(dirname(path), { recursive: true });
		return openSync(path, flags);
	}
}

function appendBytes(path: string, text: string, create = false): void {
	if (basename(dirname(path)) === "agents") childBooksChanged();
	const fd = openForAppend(path, create);
	try {
		const bytes = Buffer.from(text);
		const written = writeSync(fd, bytes);
		if (written !== bytes.length) throw new Error(`short write: ${written} of ${bytes.length} bytes`);
	} finally {
		closeSync(fd);
	}
}

export function createBook(who: Who, env: NodeJS.ProcessEnv = process.env): Book {
	const path = bookPath(who, env);
	if (existsSync(path)) {
		// A child's closed book is kept for main to read; a new loop of the child must not delete it.
		const old = parseBook(path);
		if (childId(env) && old && isClosed(old)) setAside(path);
		else deleteBook(path);
	}
	mkdirSync(dirname(path), { recursive: true });
	const child = childId(env);
	const header = {
		// Unique per loop: the file name follows the session, so a reopened loop must not reuse an old id.
		id: `${basename(path, ".yml")}-${randomUUID().slice(0, 8)}`,
		owner: child ? childName(env) || child : "main",
		session: (child ? childSession(env) : undefined) || who.sessionManager.getSessionFile?.() || null,
		cwd: real(who.cwd),
		opened: new Date().toISOString(),
	};
	const lines = ["# anchorloop loop book", ...Object.entries(header).map(([key, value]) => `${key}: ${JSON.stringify(value)}`), "entries:", ""];
	appendBytes(path, lines.join("\n"), true);
	return { path, header, entries: [] };
}

/** What `adoptBook` answers: the adopted book, or why the id was refused. */
export type Adopted = { book: Book; refused?: undefined } | { book?: undefined; refused: string };

/**
 * The book whose header id is `id`, wherever it lives under the books root, with whether it is a subagent's. Every move leaves a
 * marker that keeps the id, so a book handed off again is found past its markers; a marker answers only when no book holds the id.
 */
function findBookById(id: string, root: string): { book: Book; project: string; child: boolean } | undefined {
	let projects: string[];
	try {
		projects = readdirSync(root);
	} catch {
		return undefined;
	}
	let marker: { book: Book; project: string; child: boolean } | undefined;
	for (const project of projects) {
		for (const [dir, child] of [[join(root, project), false], [join(root, project, "agents"), true]] as const) {
			let files: string[];
			try {
				files = readdirSync(dir).filter((file) => file.endsWith(".yml"));
			} catch {
				continue;
			}
			for (const file of files) {
				const book = parseBook(join(dir, file));
				if (book?.header.id !== id) continue;
				if (!movedTo(book)) return { book, project, child };
				marker ??= { book, project, child };
			}
		}
	}
	return marker;
}

/** Where a moved book went, when the book at its old path is the closed marker `adoptBook` leaves there. */
export function movedTo(book: Book): { session: string; id: string; ts: string } | undefined {
	const last = book.entries.at(-1);
	if (last?.stage !== "close" || last.verdict !== "moved") return undefined;
	return { session: String(last.to ?? "another session"), id: String(book.header.id ?? basename(book.path, ".yml")), ts: last.ts };
}

/** The entries a loop records as it opens, before any evidence: a session whose loop holds only these may still resume another book. */
const OPENING_STAGES: ReadonlySet<string> = new Set(["kind", "anchor", "observe", "base", "task"]);

/**
 * Adopts the open book another main session of this project handed off, by the id its handoff names (`read` shows it): the book
 * moves to this session's path with this session's file in its header, so what its units proved and what the notice asked carry
 * over, and an `adopt` entry names where it came from. The old path keeps a closed marker naming this session, so the session that
 * left the book is told on its next call instead of losing it silently. An id that is unknown, closed, a subagent's, another
 * project's, or asked for while this session's own loop already holds evidence is refused with the reason. The `task` entries this
 * session recorded before resuming are appended to the adopted book, so a child reading it finds those todos' unit metadata.
 */
export function adoptBook(who: Who, id: string, env: NodeJS.ProcessEnv = process.env): Adopted {
	if (childId(env) !== undefined) return { refused: "a subagent session cannot resume a book; only a main session resumes a handed-off book" };
	const path = bookPath(who, env);
	const own = parseBook(path);
	// What this session recorded before it resumed: the todos it created, whose unit metadata a child reads from the adopted book.
	let carried: Entry[] = [];
	if (own && !isClosed(own)) {
		if (own.header.id === id) return { book: own };
		carried = own.entries.filter((entry) => entry.stage === "task");
		if (own.entries.some((entry) => !OPENING_STAGES.has(entry.stage))) {
			return { refused: `this session's own loop ${String(own.header.id)} already holds evidence; \`resume\` goes on the first \`kind\` or todo, before the loop records anything` };
		}
	}
	const found = findBookById(id, booksRoot(env));
	if (!found) return { refused: `no book has the id \`${id}\`; copy the id from the \`book:\` line of the old session's \`anchorloop_stage read\`` };
	const old = found.book;
	if (found.project !== projectSlug(who.cwd)) return { refused: `book ${id} belongs to another project (${String(old.header.cwd ?? found.project)}); resume it from that directory` };
	if (found.child || old.header.owner !== "main") return { refused: `book ${id} is a subagent's book (${String(old.header.owner)}); only a main session's book can be resumed` };
	const moved = movedTo(old);
	if (moved) return { refused: `book ${id} was already resumed by ${moved.session}` };
	if (isClosed(old)) return { refused: `book ${id} is closed (${String(old.entries.at(-1)?.verdict ?? "no verdict")}); open a new loop instead` };
	if (old.path === path) return { refused: `book ${id} is this session's own book` };
	const session = who.sessionManager.getSessionFile?.() || null;
	let text: string;
	try {
		text = readFileSync(old.path, "utf-8");
	} catch {
		return { refused: `book ${id} vanished while it was being resumed` };
	}
	// The header names the session that owns the book, which the sweep checks; entries are copied as they are.
	const lines = text.split("\n");
	const body = lines.map((line) => (line.startsWith("session: ") ? `session: ${JSON.stringify(session)}` : line)).join("\n");
	mkdirSync(dirname(path), { recursive: true });
	const temp = `${path}.adopt-${process.pid}`;
	appendBytes(temp, body, true);
	renameSync(temp, path);
	// The old path becomes a closed marker under the old header: its session reads where the book went and records nothing more in it.
	const header = lines.slice(0, Math.max(0, lines.indexOf("entries:")));
	const marker = `${old.path}.moved-${process.pid}`;
	const close = { ts: new Date().toISOString(), stage: "close", verdict: "moved", to: session, book: basename(path, ".yml") };
	appendBytes(marker, [...header, "entries:", `- ${JSON.stringify(close)}`, ""].join("\n"), true);
	renameSync(marker, old.path);
	const book = parseBook(path);
	if (!book) return { refused: `book ${id} vanished while it was being resumed` };
	book.entries.push(appendEntry(path, "adopt", { from: basename(old.path, ".yml"), id, session: old.header.session ?? null }));
	// Later than the adopted entries, so this session's own todo of an id wins, as its todo list does.
	for (const { ts: _ts, stage: _stage, ...fields } of carried) book.entries.push(appendEntry(path, "task", fields));
	return { book };
}

export function appendEntry(path: string, stage: string, fields: Record<string, unknown> = {}): Entry {
	const entry: Entry = { ts: new Date().toISOString(), stage, ...fields };
	try {
		appendBytes(path, `- ${JSON.stringify(entry)}\n`);
	} catch (error) {
		// The book was swept or deleted under this session; there is nothing left to record in.
		if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
	}
	return entry;
}

const ASIDE = /^(.+)\.closed-(\d+)$/;

/** Renames a closed book to the next free `<id>.closed-<n>.yml`, which main reads with the child's later loops. */
function setAside(path: string): void {
	childBooksChanged();
	const stem = basename(path, ".yml");
	let n = 1;
	while (existsSync(join(dirname(path), `${stem}.closed-${n}.yml`))) n++;
	renameSync(path, join(dirname(path), `${stem}.closed-${n}.yml`));
}

/** The open books of the sessions that linked the child `id`, newest first: the inverse of `findChildBooks`. */
export function findParentBooks(id: string, env: NodeJS.ProcessEnv = process.env): Book[] {
	const root = booksRoot(env);
	if (!existsSync(root)) return [];
	const found: { book: Book; mtime: number }[] = [];
	for (const project of readdirSync(root)) {
		let files: string[];
		try {
			files = readdirSync(join(root, project)).filter((file) => file.endsWith(".yml"));
		} catch {
			continue;
		}
		for (const file of files) {
			const path = join(root, project, file);
			try {
				const book = parseBook(path);
				if (book && !isClosed(book) && book.entries.some((entry) => entry.stage === "link" && entry.child === id)) found.push({ book, mtime: statSync(path).mtimeMs });
			} catch {
				// The book vanished mid-scan.
			}
		}
	}
	return found.sort((a, b) => b.mtime - a.mtime).map((item) => item.book);
}

/** The command the session that linked child `id` holds as its anchor, when that anchor is a command; the run a child's `check` records. */
export function parentAnchor(id: string, env: NodeJS.ProcessEnv = process.env): string | undefined {
	for (const book of findParentBooks(id, env)) {
		const anchor = anchorCommand(book.entries);
		if (anchor && anchorIsCommand(book.entries)) return anchor;
	}
	return undefined;
}

export type ChildBook = { book: Book; tag: string };

/** The child book files of one project's `agents/` dir for one child: its set-aside loops by number, and whether its current book is there. */
type ChildFiles = { agents: string; asides: { n: number; tag: string; file: string }[]; current: boolean };

/** Every project's child book files under `root`, by child file id, in project order: one listing of the root and of each `agents/` dir. */
function indexChildBooks(root: string): Map<string, ChildFiles[]> {
	const index = new Map<string, ChildFiles[]>();
	if (!existsSync(root)) return index;
	for (const project of readdirSync(root)) {
		const agents = join(root, project, "agents");
		let files: string[];
		try {
			files = readdirSync(agents);
		} catch {
			continue;
		}
		const here = new Map<string, ChildFiles>();
		const of = (key: string): ChildFiles => {
			let found = here.get(key);
			if (!found) {
				found = { agents, asides: [], current: false };
				here.set(key, found);
				const list = index.get(key);
				if (list) list.push(found);
				else index.set(key, [found]);
			}
			return found;
		};
		for (const file of files) {
			const stem = basename(file, ".yml");
			const match = ASIDE.exec(stem);
			if (match) of(match[1]).asides.push({ n: Number(match[2]), tag: `~${match[2]}`, file: `${match[0]}.yml` });
			if (file === `${stem}.yml`) of(stem).current = true;
		}
	}
	return index;
}

/** The books of the child `id` among all projects: its earlier closed loops (`~1`, `~2`) in order, then the current one (no tag). */
export function findChildBooks(id: string, env: NodeJS.ProcessEnv = process.env): ChildBook[] {
	const root = booksRoot(env);
	const books = eventTrees?.books;
	const key = `${root}\0${safe(id)}`;
	const cached = books?.children.get(key);
	if (cached) return cached;
	let index = books?.indexes.get(root);
	if (!index) {
		index = indexChildBooks(root);
		books?.indexes.set(root, index);
	}
	const found: ChildBook[] = [];
	for (const { agents, asides, current } of index.get(safe(id)) ?? []) {
		for (const aside of [...asides].sort((a, b) => a.n - b.n)) {
			const book = parseBook(join(agents, aside.file));
			if (book) found.push({ book, tag: aside.tag });
		}
		const book = current ? parseBook(join(agents, `${safe(id)}.yml`)) : undefined;
		if (book) found.push({ book, tag: "" });
	}
	books?.children.set(key, found);
	return found;
}

function removeIfEmpty(dir: string): boolean {
	try {
		rmdirSync(dir);
		return true;
	} catch {
		return false;
	}
}

/** Removes the `agents/` and project directories a deleted book leaves empty. */
function tidy(dir: string): void {
	if (!removeIfEmpty(dir)) return;
	const parent = dirname(dir);
	if (basename(dir) === "agents") removeIfEmpty(parent);
}

export function deleteBook(path: string): void {
	childBooksChanged();
	try {
		unlinkSync(path);
	} catch {
		// Already gone.
	}
	tidy(dirname(path));
}

export type OpenBook = { path: string; kind: string; intent: string; mtimeMs: number };
export type Sweep = { deleted: string[]; open: OpenBook[] };

function sessionGone(book: Book): boolean {
	if (Date.now() - statSync(book.path).mtimeMs > STALE_BOOK_MS) return true;
	const session = book.header.session;
	return typeof session === "string" ? !existsSync(session) : Date.now() - statSync(book.path).mtimeMs > STALE_UNSAVED_MS;
}

/**
 * Deletes books whose owner session file is gone, and child books that no open book links and whose own
 * session file is gone too; a running child whose parent has not linked it yet stays. Lists the deletions
 * of every project but only the open books of the project `cwd` belongs to.
 */
export function sweep(env: NodeJS.ProcessEnv = process.env, cwd?: string): Sweep {
	const root = booksRoot(env);
	const result: Sweep = { deleted: [], open: [] };
	if (!existsSync(root)) return result;
	const slug = cwd ? projectSlug(cwd) : undefined;
	const linked = new Set<string>();
	const children: Book[] = [];
	// Other sessions create and tidy books concurrently, so a directory or file can vanish mid-walk; skip it.
	for (const project of readdirSync(root)) {
		try {
			const dir = join(root, project);
			if (!statSync(dir).isDirectory()) continue;
			for (const file of readdirSync(dir)) {
				if (!file.endsWith(".yml")) continue;
				try {
					const book = parseBook(join(dir, file));
					if (!book) continue;
					if (sessionGone(book)) {
						deleteBook(book.path);
						result.deleted.push(book.path);
						continue;
					}
					if ((!slug || project === slug) && !movedTo(book)) result.open.push({ path: book.path, kind: currentKind(book.entries) ?? "no kind", intent: currentIntent(book.entries) ?? "no intent", mtimeMs: statSync(book.path).mtimeMs });
					for (const entry of book.entries) if (entry.stage === "link" && typeof entry.child === "string") linked.add(safe(entry.child));
				} catch {
					// This book vanished; the rest of the project still counts.
				}
			}
			const agents = join(dir, "agents");
			if (existsSync(agents)) {
				for (const file of readdirSync(agents)) {
					const child = file.endsWith(".yml") ? parseBook(join(agents, file)) : undefined;
					if (child) children.push(child);
				}
			}
		} catch {
			// Vanished under a concurrent tidy.
		}
	}
	for (const child of children) {
		try {
			const stem = basename(child.path, ".yml");
			if (linked.has(ASIDE.exec(stem)?.[1] ?? stem) || !sessionGone(child)) continue;
			deleteBook(child.path);
			result.deleted.push(child.path);
		} catch {
			// Vanished under a concurrent tidy.
		}
	}
	for (const project of readdirSync(root)) {
		const dir = join(root, project);
		removeIfEmpty(join(dir, "agents"));
		removeIfEmpty(dir);
	}
	return result;
}

// --- derived state -------------------------------------------------------------------------------

export function currentKind(entries: Entry[]): Kind | undefined {
	const found = [...entries].reverse().find((entry) => entry.stage === "kind" && typeof entry.kind === "string");
	return found?.kind as Kind | undefined;
}

export function currentIntent(entries: Entry[]): string | undefined {
	const found = [...entries].reverse().find((entry) => entry.stage === "kind" && typeof entry.intent === "string");
	return found?.intent as string | undefined;
}

const NOT_STAGES = new Set(["base", "link", "send", "push", "adopt", "notice", "result", "watch", "observe", "close", "task", "taskrun", "verification", "skip", "back", "friction", "reflect", "goldfish"]);

/** A landing that counts: git confirmed a watched branch in the ref. A declared sha no watched branch explains is recorded but is neither the act nor a point to observe from. */
export const countsAsLanding = (entry: Entry): boolean => entry.stage === "land" && entry.verified !== false && entry.rule !== "declared";

/** The stages the book shows, in order of first appearance; `edit` entries read as `act`. */
export function stagesDone(entries: Entry[]): string[] {
	const seen: string[] = [];
	for (const entry of entries) {
		if (NOT_STAGES.has(entry.stage)) continue;
		const name = entry.stage === "edit" || (entry.stage === "land" && countsAsLanding(entry)) ? "act" : entry.stage;
		if (!seen.includes(name)) seen.push(name);
	}
	return seen;
}

export function lastIndex(entries: Entry[], ...stages: string[]): number {
	for (let i = entries.length - 1; i >= 0; i--) if (stages.includes(entries[i].stage)) return i;
	return -1;
}

/**
 * The book's entries with the change entries of its linked children merged in by time, each marked `child`, so a coordinator
 * whose edits are all made by children still shows an act. Indexes into the result differ from indexes into `entries`.
 */
export function withChildActs(entries: Entry[], env: NodeJS.ProcessEnv = process.env): Entry[] {
	const acts: Entry[] = [];
	for (const id of childIds(entries)) {
		for (const { book } of findChildBooks(id, env)) acts.push(...book.entries.filter((entry) => entry.stage === "edit").map((entry) => ({ ...entry, child: id })));
	}
	if (acts.length === 0) return entries;
	acts.sort((a, b) => a.ts.localeCompare(b.ts));
	const merged: Entry[] = [];
	for (const entry of entries) {
		while (acts.length && acts[0].ts < entry.ts) merged.push(acts.shift() as Entry);
		merged.push(entry);
	}
	return [...merged, ...acts];
}

/** A landing changes what the coordinator holds only when it pushed or merged it itself and the ref now differs from what was checked. */
const reopensVerify = (entry: Entry): boolean => countsAsLanding(entry) && entry.self === true && entry.exact !== true;

/** A change entry: a production write or edit, a commit or merge, a landing the coordinator made that no check covered. */
export const isChange = (entry: Entry): boolean => entry.stage === "edit" || reopensVerify(entry);

/** The index of the latest change entry, or -1. */
export function lastActIndex(entries: Entry[]): number {
	for (let i = entries.length - 1; i >= 0; i--) if (isChange(entries[i])) return i;
	return -1;
}

/** The working-state tree of each repo a run or dispatch recorded (`treeAt`: repo root to tree), or undefined for an entry that recorded none. */
export function treeAtOf(entry: Entry): Record<string, string> | undefined {
	const at = entry.treeAt;
	if (!at || typeof at !== "object" || Array.isArray(at)) return undefined;
	const found = Object.entries(at as Record<string, unknown>).filter((pair): pair is [string, string] => typeof pair[1] === "string");
	return found.length ? Object.fromEntries(found) : undefined;
}

/** Working trees computed during one reading of the book, so each repo is built once however many units ask. */
export type TreeCache = Map<string, string | undefined>;

function treeNow(repo: string, cache?: TreeCache): string | undefined {
	if (cache?.has(repo)) return cache.get(repo);
	const tree = existsSync(repo) ? workingTree(repo) : undefined;
	cache?.set(repo, tree);
	return tree;
}

/** Which recorded trees a reading compares with the working state: a unit compares only its own trees; a loop of one unit compares all. */
export type Scope = { comparable?: (repo: string) => boolean; cache?: TreeCache };

/**
 * True while the trees `entry` recorded still hold: each comparable repo's working tree is the one recorded (a repo git cannot
 * build a tree for any more, such as a removed worktree, proves nothing and counts as unchanged). An entry with no trees holds.
 */
export function treesHold(entry: Entry, scope: Scope = {}): boolean {
	const at = treeAtOf(entry);
	if (!at) return true;
	for (const [repo, tree] of Object.entries(at)) {
		if (scope.comparable && !scope.comparable(repo)) continue;
		const now = treeNow(repo, scope.cache);
		if (now !== undefined && now !== tree) return false;
	}
	return true;
}

/**
 * True while the run at `index` stands for the code it checked. A run that recorded the tree its command ran in stands while that tree
 * is unchanged and no later change entry names that repo (or names none); a change in another repo, a note git ignores, or a worker's
 * edit in its own worktree leaves it. A run with no recorded tree (an older book, a declared verify) stands until any later change.
 */
export function runStands(entries: Entry[], index: number, scope: Scope = {}): boolean {
	const at = treeAtOf(entries[index]);
	for (let i = index + 1; i < entries.length; i++) {
		if (!isChange(entries[i])) continue;
		const repo = typeof entries[i].repo === "string" ? (entries[i].repo as string) : undefined;
		if (!at || repo === undefined || repo in at) return false;
	}
	return treesHold(entries[index], scope);
}

/**
 * The index a review counts from: its reviewer's dispatch (the `link` or `send` entry its `from` names), not its result. A dispatch
 * held in another unit's entries is placed by time, before any entry of the same instant. A review that names no dispatch counts from itself.
 */
export function dispatchIndex(entries: Entry[], index: number): number {
	const review = entries[index];
	const from = typeof review.from === "string" ? review.from : undefined;
	if (from === undefined) return index;
	for (let i = index - 1; i >= 0; i--) {
		const entry = entries[i];
		if ((entry.stage === "link" || entry.stage === "send") && entry.child === review.child && entry.ts === from) return i;
	}
	const at = entries.findIndex((entry) => entry.ts >= from);
	return at < 0 || at > index ? index : at;
}

/** True while the review at `index` covers the code: no change since its reviewer was dispatched, and the trees it was given still hold. */
export function reviewStands(entries: Entry[], index: number, scope: Scope = {}): boolean {
	const from = dispatchIndex(entries, index);
	for (let i = from; i < entries.length; i++) if (isChange(entries[i])) return false;
	return treesHold(entries[index], scope);
}

export function reviews(entries: Entry[]): Entry[] {
	return entries.filter((entry) => entry.stage === "review");
}

export function isBlocking(entry: Entry): boolean {
	return entry.blocking === true;
}

/** True when the two latest review rounds both still had blocking findings. */
export function reviewsStalled(entries: Entry[]): boolean {
	const rounds = reviews(entries);
	return rounds.length >= 2 && isBlocking(rounds[rounds.length - 1]) && isBlocking(rounds[rounds.length - 2]);
}

export function reviewTrend(entries: Entry[]): string {
	const rounds = reviews(entries);
	if (rounds.length === 0) return "no review";
	return `${rounds.length} round(s): ${rounds.map((round) => (round.blocking === true ? `blocking${round.p0 !== undefined ? ` P0=${round.p0} P1=${round.p1}` : ""}` : round.blocking === false ? "clear" : "unknown")).join(" → ")}`;
}

/** A review that still covers the code (see `reviewStands`) with no blocking finding on it. */
export function reviewClearAfterLastAct(raw: Entry[], scope: Scope = {}): boolean {
	const entries = withChildActs(raw);
	const review = lastIndex(entries, "review");
	return review >= 0 && entries[review].blocking === false && reviewStands(entries, review, scope);
}

/** The latest anchor text, matched against bash commands; an anchor that never occurs in a command is verified by declaration. */
export function anchorCommand(entries: Entry[]): string | undefined {
	return latestAnchor(entries);
}

/** The latest anchor of either kind, for display. */
export function latestAnchor(entries: Entry[]): string | undefined {
	const found = [...entries].reverse().find((entry) => entry.stage === "anchor" && typeof entry.check === "string");
	return found?.check as string | undefined;
}

/** The post-land observations the loop's anchor lists, from the latest `observe` entry. */
export function observeItems(entries: Entry[]): string[] {
	const found = [...entries].reverse().find((entry) => entry.stage === "observe" && Array.isArray(entry.items));
	return found ? (found.items as unknown[]).map(String) : [];
}

/** A run of the anchor, or a declared verify of the run checkpoint: a verify or check entry that is not one of the observations. */
export const isRunEntry = (entry: Entry): boolean => (entry.stage === "verify" || entry.stage === "check") && entry.checkpoint === undefined;

/** True when the anchor was stated as a command (a `kind` or todo anchor), or a stated line was later run as one; prose is never quoted back as a command. */
export function anchorIsCommand(entries: Entry[]): boolean {
	const found = [...entries].reverse().find((entry) => entry.stage === "anchor" && typeof entry.check === "string");
	if (!found) return false;
	return found.line !== true || entries.some((entry) => (entry.stage === "verify" || entry.stage === "check") && entry.command === found.check);
}

function evidenceLine(entry: Entry): string {
	return `${entry.stage} ${entry.declared ? `declared: ${entry.note ?? entry.result}` : `exit ${entry.exit ?? "unknown"}${entry.last ? `: ${entry.last}` : ""}`}`;
}

/** The latest check or verify entry when it still stands for the code it checked (see `runStands`), else undefined. */
export function verifyAfterLastAct(raw: Entry[], scope: Scope = {}): Entry | undefined {
	const entries = withChildActs(raw);
	let index = -1;
	for (let i = entries.length - 1; i >= 0 && index < 0; i--) if (isRunEntry(entries[i])) index = i;
	return index >= 0 && runStands(entries, index, scope) ? entries[index] : undefined;
}

export function childIds(entries: Entry[]): string[] {
	return entries.filter((entry) => entry.stage === "link" && typeof entry.child === "string").map((entry) => entry.child as string);
}

/** One line per linked child book that exists. */
export function childLines(entries: Entry[], env: NodeJS.ProcessEnv = process.env): string[] {
	const lines: string[] = [];
	for (const id of childIds(entries)) {
		const link = entries.find((entry) => entry.stage === "link" && entry.child === id);
		for (const { book: child, tag } of findChildBooks(id, env)) {
			const lastCheck = [...child.entries].reverse().find((entry) => entry.stage === "check" || entry.stage === "verify");
			const friction = frictionOf(child.entries).length;
			lines.push(
				`${link?.name ?? id}${tag}: ${currentKind(child.entries) ?? "no kind"}${isClosed(child) ? " (closed)" : ""}; stages ${stagesDone(child.entries).join(", ") || "none"}; ${lastCheck ? evidenceLine(lastCheck) : "no check"}${friction ? `; ${friction} friction` : ""}`,
			);
		}
	}
	return lines;
}

// --- friction and reflection ---------------------------------------------------------------------

export function frictionOf(entries: Entry[]): Entry[] {
	return entries.filter((entry) => entry.stage === "friction");
}

export type FrictionItem = { ref: string; owner: string; tried: string; found: string; led_by: string; reflected: boolean; class?: string; action?: string };

function coveringReflect(entries: Entry[], refs: string[]): Entry | undefined {
	return entries.find((entry) => entry.stage === "reflect" && Array.isArray(entry.friction) && entry.friction.some((id: unknown) => refs.includes(String(id))));
}

function item(owner: string, ref: string, entry: Entry, reflect: Entry | undefined): FrictionItem {
	return {
		ref,
		owner,
		tried: String(entry.tried),
		found: String(entry.found),
		led_by: String(entry.led_by ?? "none"),
		reflected: reflect !== undefined,
		...(reflect ? { class: String(reflect.class), action: String(reflect.action ?? "") } : {}),
	};
}

/**
 * Every friction entry of the book and of its linked children, each with the reflect that covers it, if any. Inside `withTrees` the
 * list is computed once per entries array and books root while the array keeps its length and no child book changes.
 */
export function allFriction(entries: Entry[], env: NodeJS.ProcessEnv = process.env): FrictionItem[] {
	const books = eventTrees?.books;
	const root = booksRoot(env);
	const memo = books?.friction.get(entries)?.get(root);
	if (memo && memo.length === entries.length) return memo.items;
	const items = frictionItems(entries, env);
	if (books) {
		const byRoot = books.friction.get(entries) ?? new Map();
		byRoot.set(root, { length: entries.length, items });
		books.friction.set(entries, byRoot);
	}
	return items;
}

function frictionItems(entries: Entry[], env: NodeJS.ProcessEnv): FrictionItem[] {
	const items = frictionOf(entries).map((entry) => item("main", String(entry.id), entry, coveringReflect(entries, [String(entry.id)])));
	for (const id of childIds(entries)) {
		const link = entries.find((entry) => entry.stage === "link" && entry.child === id);
		for (const { book: child, tag } of findChildBooks(id, env)) {
			const label = `${String(link?.name ?? id)}${tag}`;
			for (const entry of frictionOf(child.entries)) {
				const reflect = coveringReflect(entries, [`${label}#${entry.id}`, `${id}${tag}#${entry.id}`]) ?? coveringReflect(child.entries, [String(entry.id)]);
				items.push(item(label, `${label}#${entry.id}`, entry, reflect));
			}
		}
	}
	return items;
}

export type RetryPair = { key: string; fail: number; pass: number };

/** Regressions: a run that failed after the same command had passed in this loop, and then passed again. A failure before any pass is red-first work, not a retry. */
export function retryPairs(entries: Entry[]): RetryPair[] {
	const pairs: RetryPair[] = [];
	const passed = new Set<string>();
	const failed = new Map<string, number>();
	entries.forEach((entry, index) => {
		if (entry.declared === true) return;
		const key = entry.stage === "taskrun" ? `task#${entry.id}` : entry.stage === "verify" || entry.stage === "check" ? `anchor:${String(entry.command ?? "")}` : undefined;
		if (!key || typeof entry.exit !== "number") return;
		if (entry.exit !== 0) {
			if (passed.has(key) && !failed.has(key)) failed.set(key, index);
		} else {
			if (failed.has(key)) {
				pairs.push({ key, fail: failed.get(key) as number, pass: index });
				failed.delete(key);
			}
			passed.add(key);
		}
	});
	return pairs;
}

// --- todos ---------------------------------------------------------------------------------------

export type Task = { id: number; subject: string; status: string; metadata?: Record<string, unknown> };

const TASK_STATUSES = new Set(["pending", "in_progress", "completed", "deleted"]);

export function taskDetails(value: unknown): Task[] | undefined {
	if (!value || typeof value !== "object") return undefined;
	const tasks = (value as { tasks?: unknown }).tasks;
	if (!Array.isArray(tasks)) return undefined;
	const valid = tasks.every((task) => task && typeof task.subject === "string" && TASK_STATUSES.has(task.status));
	return valid ? (tasks as Task[]) : undefined;
}

/** The todo list as of the latest `rpiv-todo-state` entry, else the latest `todo` tool result, on the branch. */
export function replayTodos(branch: unknown[]): Task[] {
	let fromEntries: Task[] | undefined;
	let fromResults: Task[] | undefined;
	for (const raw of branch) {
		const entry = raw as { type?: string; customType?: string; data?: unknown; message?: { role?: string; toolName?: string; details?: unknown } };
		if (entry.type === "custom") {
			if (entry.customType === "rpiv-todo-state") fromEntries = taskDetails(entry.data) ?? fromEntries;
		} else if (entry.type === "message" && entry.message?.role === "toolResult" && entry.message.toolName === "todo") {
			fromResults = taskDetails(entry.message.details) ?? fromResults;
		}
	}
	return (fromEntries ?? fromResults ?? []).filter((task) => task.status !== "deleted");
}

export const isOpenTask = (task: Task): boolean => task.status === "pending" || task.status === "in_progress";

const TICKET = /^(#\d+|[A-Za-z][A-Za-z0-9]*-\d+)$/;

/** True when `followup` is a ticket id, `memory`, or `drop — <reason>`. */
export function validFollowup(followup: unknown): boolean {
	if (typeof followup !== "string") return false;
	const value = followup.trim();
	return TICKET.test(value) || value === "memory" || /^drop\s*[—–-]\s*\S/.test(value);
}

// --- git -----------------------------------------------------------------------------------------

// A git call that takes longer than this fails quietly (the book never blocks a tool); the suite raises it so a loaded machine does not.
const GIT_TIMEOUT_MS = ((n) => (Number.isInteger(n) && n >= 1000 ? n : 5000))(Number(process.env.ANCHORLOOP_GIT_TIMEOUT_MS));

export function git(cwd: string, args: string[], env?: NodeJS.ProcessEnv): string | undefined {
	try {
		return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf-8", timeout: GIT_TIMEOUT_MS, stdio: ["ignore", "pipe", "ignore"], env: env ?? process.env }).trim();
	} catch {
		return undefined;
	}
}

/**
 * The child books one event has read: the index of each books root, each child's books, and each book's friction list. A book
 * this process writes, deletes, or sets aside under an `agents/` dir clears them; a main session's own appends do not.
 */
type EventBooks = {
	indexes: Map<string, Map<string, ChildFiles[]>>;
	children: Map<string, ChildBook[]>;
	friction: WeakMap<Entry[], Map<string, { length: number; items: FrictionItem[] }>>;
	/** Repo roots by path: a path's repo does not change within one event. */
	roots: Map<string, string | undefined>;
};

const noBooks = (): EventBooks => ({ indexes: new Map(), children: new Map(), friction: new WeakMap(), roots: new Map() });

// The working trees and child books of the event `withTrees` runs: each repo's tree is built once however many readings ask for it.
let eventTrees: { cache: TreeCache; build: boolean; books: EventBooks } | undefined;

function childBooksChanged(): void {
	if (!eventTrees) return;
	const { books } = eventTrees;
	books.indexes.clear();
	books.children.clear();
	books.friction = new WeakMap();
}

/**
 * Runs `fn` as one event's reading of the working state: every `workingTree` call in it shares one tree per repo, built at most
 * once. With `build: false` (the footer) nothing more is built: a tree this event has not read is unknown, which a recorded tree
 * counts as unchanged. The event also lists the books root once for every child book it reads (`findChildBooks`) and computes
 * a book's friction once (`allFriction`). A nested call joins the outer event's trees and books. `fn` must not await.
 */
export function withTrees<T>(fn: () => T, options: { build?: boolean } = {}): T {
	const outer = eventTrees;
	eventTrees = { cache: outer?.cache ?? new Map(), build: (outer?.build ?? true) && (options.build ?? true), books: outer?.books ?? noBooks() };
	try {
		return fn();
	} finally {
		eventTrees = outer;
	}
}

/**
 * The tree a commit of everything in `repo`'s working state would have (tracked and untracked, ignored files and `scratch/`
 * left out), built in a copy of the index so the repo's own index is untouched; undefined when git cannot build it.
 * Inside `withTrees` the event's tree of `repo` is shared.
 */
export function workingTree(repo: string): string | undefined {
	if (!eventTrees) return buildTree(repo);
	const { cache, build } = eventTrees;
	if (cache.has(repo) || !build) return cache.get(repo);
	const tree = buildTree(repo);
	cache.set(repo, tree);
	return tree;
}

function buildTree(repo: string): string | undefined {
	const index = git(repo, ["rev-parse", "--path-format=absolute", "--git-path", "index"]);
	if (!index) return undefined;
	const dir = mkdtempSync(join(tmpdir(), "anchorloop-tree-"));
	try {
		const env = { ...process.env, GIT_INDEX_FILE: join(dir, "index") };
		if (existsSync(index)) {
			// The copy keeps the index's mtime: git trusts an entry's stat only when it is older than the index, and a file
			// changed in the second the index was written but kept its size would otherwise be taken as unchanged.
			copyFileSync(index, env.GIT_INDEX_FILE);
			const { atime, mtime } = statSync(index);
			utimesSync(env.GIT_INDEX_FILE, atime, mtime);
		}
		if (git(repo, ["add", "-A", "--", ".", ":(exclude)scratch"], env) === undefined) return undefined;
		return git(repo, ["write-tree"], env);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
}

/** The working-state tree of each repo in `repos`, leaving out a repo git cannot build one for. */
export function workingTrees(repos: Iterable<string>): string[] {
	return [...new Set(repos)].map(workingTree).filter((tree): tree is string => tree !== undefined);
}

/** The `treeAt` field for `repos`: each repo root with its working-state tree now, leaving out a repo git cannot build one for. */
export function treeAtField(repos: Iterable<string>): { treeAt?: Record<string, string> } {
	const at: Record<string, string> = {};
	for (const repo of new Set(repos)) {
		const tree = workingTree(repo);
		if (tree) at[repo] = tree;
	}
	return Object.keys(at).length ? { treeAt: at } : {};
}

/** True when git ignores `path` in its repo: such a file is in no diff, so writing it changes no code. */
export function ignoredByGit(path: string): boolean {
	const dir = existingDir(dirname(resolve(path)));
	return git(dir, ["check-ignore", "-q", "--", resolve(path)]) !== undefined;
}

const CD_STEP = /^cd\s+("[^"]*"|'[^']*'|\S+)\s*(?:&&|;)\s*/;

/**
 * The command without the leading `cd <dir> &&` (or `;`) steps whose directory is one of `roots`, the roots of the loop's
 * repos, so one anchor run from two checkouts reads the same; a `cd` into a subdirectory stays, since it runs other tests.
 */
export function anchorBody(command: string, roots: string[], cwd: string): string {
	let rest = command.trim();
	for (let step = CD_STEP.exec(rest); step; step = CD_STEP.exec(rest)) {
		const target = step[1].replace(/^(["'])(.*)\1$/, "$2").replace(/^~(?=\/|$)/, homedir());
		if (!roots.includes(real(resolve(cwd, target)))) break;
		rest = rest.slice(step[0].length);
	}
	return rest.replace(/\s+/g, " ");
}

/**
 * The linked child whose latest run of `anchor` passed on exactly the state the coordinator holds: the trees that run
 * recorded are the coordinator's `trees`, no more and no fewer, so a repo only one side worked in is never taken as checked.
 * `roots` and `cwd` are the coordinator's repo roots and directory. Only a pi-herdr-agents child is linked
 * (`PI_SUBAGENT_ID`); pi itself has no subagents.
 */
export function adoptableRun(entries: Entry[], anchor: string, trees: string[], roots: string[], cwd: string, env: NodeJS.ProcessEnv = process.env): { name: string; child: string; run: Entry } | undefined {
	const body = anchorBody(anchor, roots, cwd);
	const held = new Set(trees);
	for (const id of childIds(entries)) {
		const runs = findChildBooks(id, env).flatMap(({ book }) => {
			const home = String(book.header.cwd ?? "");
			const here = home ? repoRootOf(join(home, "_")) : undefined;
			const childRoots = [...ownBases(book.entries).map((base) => base.repo), ...(here ? [here] : [])];
			return book.entries.filter((entry) => entry.stage === "check" && typeof entry.command === "string" && anchorBody(entry.command, childRoots, home) === body);
		});
		const run = runs.sort((a, b) => a.ts.localeCompare(b.ts)).at(-1);
		const checked = new Set(Array.isArray(run?.trees) ? (run.trees as unknown[]).map(String) : []);
		if (run && run.exit === 0 && checked.size === held.size && [...checked].every((tree) => held.has(tree))) {
			const link = entries.find((entry) => entry.stage === "link" && entry.child === id);
			return { name: String(link?.name ?? id), child: id, run };
		}
	}
	return undefined;
}

/**
 * The latest `check` of the linked child `id` that ran the coordinator's `anchor` (any check when the coordinator has no
 * anchor command), when it passed: a later failing run withdraws an earlier pass, whatever tree it ran on. Used for a landing: the ref now holds the child's change, and the integrator's gates ran on it.
 */
export function passingRunOf(entries: Entry[], id: string, anchor: string | undefined, roots: string[], cwd: string, env: NodeJS.ProcessEnv = process.env): { name: string; run: Entry } | undefined {
	const body = anchor ? anchorBody(anchor, roots, cwd) : undefined;
	const runs = findChildBooks(id, env).flatMap(({ book }) => {
		const home = String(book.header.cwd ?? "");
		const here = home ? repoRootOf(join(home, "_")) : undefined;
		const childRoots = [...ownBases(book.entries).map((base) => base.repo), ...(here ? [here] : [])];
		return book.entries.filter((entry) => entry.stage === "check" && (body === undefined || (typeof entry.command === "string" && anchorBody(entry.command, childRoots, home) === body)));
	});
	const run = runs.sort((a, b) => a.ts.localeCompare(b.ts)).at(-1);
	if (!run || run.exit !== 0) return undefined;
	const link = entries.find((entry) => entry.stage === "link" && entry.child === id);
	return { name: String(link?.name ?? id), run };
}

function existingDir(path: string): string {
	let dir = path;
	while (!existsSync(dir) && dirname(dir) !== dir) dir = dirname(dir);
	return dir;
}

/** The repo root and HEAD that contain `path`, or undefined outside a repo or before its first commit. */
export function repoOf(path: string): { repo: string; head: string } | undefined {
	const dir = existingDir(dirname(resolve(path)));
	const repo = git(dir, ["rev-parse", "--show-toplevel"]);
	const head = repo ? git(repo, ["rev-parse", "HEAD"]) : undefined;
	return repo && head ? { repo: real(repo), head } : undefined;
}

/** The root of the git repo containing `path`, or undefined outside a repo. */
export function repoRootOf(path: string): string | undefined {
	const roots = eventTrees?.books.roots;
	// Git answers for the nearest existing directory, so that is the key: sibling paths under a missing directory share one spawn.
	const dir = existingDir(dirname(resolve(path)));
	if (roots?.has(dir)) return roots.get(dir);
	const repo = git(dir, ["rev-parse", "--show-toplevel"]);
	const root = repo ? real(repo) : undefined;
	roots?.set(dir, root);
	return root;
}

export type Base = { repo: string; head: string; /** The linked child whose repo this is, when a link recorded the base. */ child?: string };

export function bases(entries: Entry[]): Base[] {
	return entries.filter((entry) => entry.stage === "base").map((entry) => ({ repo: String(entry.repo), head: String(entry.head), ...(entry.via === "link" && typeof entry.child === "string" ? { child: entry.child } : {}) }));
}

/** The bases of the repos the loop itself works in; a child's repo, recorded when it was linked, is not one of them. */
export function ownBases(entries: Entry[]): Base[] {
	return bases(entries).filter((base) => base.child === undefined);
}

/**
 * The content hash of each of `names` in `repo`, `deleted` for a path that is gone, and `unknown` for one git cannot hash
 * (a directory or submodule). One such path fails the batch, so the batch falls back to hashing each path alone.
 */
export function contentHashes(repo: string, names: string[]): Record<string, string> {
	const found: Record<string, string> = {};
	const present = names.filter((name) => existsSync(join(repo, name)));
	for (const name of names) if (!present.includes(name)) found[name] = "deleted";
	const batch = present.length ? git(repo, ["hash-object", "--", ...present])?.split("\n") : [];
	present.forEach((name, index) => {
		found[name] = (batch ? batch[index] : git(repo, ["hash-object", "--", name])) || "unknown";
	});
	return found;
}

/** The paths already changed or untracked in `repo` against `head`, with their content hashes: work the loop found, not made. */
function dirtyAt(repo: string, head: string): Record<string, string> {
	const changed = git(repo, ["diff", "--name-only", head])?.split("\n") ?? [];
	const untracked = git(repo, ["ls-files", "--others", "--exclude-standard"])?.split("\n") ?? [];
	return contentHashes(repo, [...new Set([...changed, ...untracked].filter(Boolean))].slice(0, 500));
}

/** Adds the repo of `path` to the book with its HEAD, and the paths already dirty there, when the book has no base for it yet. */
export function touchRepo(book: Book, path: string): boolean {
	const found = repoOf(path);
	if (!found) return false;
	if (ownBases(book.entries).some((base) => base.repo === found.repo)) return false;
	const entry = appendEntry(book.path, "base", { ...found, dirty: dirtyAt(found.repo, found.head) });
	book.entries.push(entry);
	return true;
}

/**
 * Adds the repo at `dir` with its pre-command HEAD after a `verb` (merge, pull, or cherry-pick) first seen through bash: the
 * reflog entry before the run of `verb` entries on top. ORIG_HEAD is not used, since cherry-pick leaves an old one in place.
 */
export function touchRepoBeforeMerge(book: Book, dir: string, verb: string): boolean {
	const found = repoOf(join(dir, "_"));
	if (!found || ownBases(book.entries).some((base) => base.repo === found.repo)) return false;
	const reflog = git(found.repo, ["reflog", "-n", "50", "--format=%H %gs"])?.split("\n").filter(Boolean) ?? [];
	// A conflict resolved with `--continue` logs `commit (<verb>)` instead of `<verb>`.
	const ofVerb = (line: string) => line.slice(41).startsWith(verb) || line.slice(41).startsWith(`commit (${verb})`);
	const first = reflog.findIndex((line) => !ofVerb(line));
	const before = reflog.length > 0 && ofVerb(reflog[0]) && first > 0 ? reflog[first].slice(0, 40) : undefined;
	// A rebasing pull leaves the old HEAD off HEAD's history; their merge base keeps the pulled commits in the diff.
	// The dirty snapshot is the uncommitted work against HEAD, so the merged files stay the loop's change.
	const base = before === undefined ? undefined : git(found.repo, ["merge-base", before, "HEAD"]);
	book.entries.push(appendEntry(book.path, "base", { repo: found.repo, head: base || found.head, dirty: dirtyAt(found.repo, found.head) }));
	return true;
}

export type Diff = { summary: string; files: string[]; paths: string[] };

/** The latest `result` entry of a linked child, or undefined before it returned. */
export function resultOf(entries: Entry[], child: string): Entry | undefined {
	return [...entries].reverse().find((entry) => entry.stage === "result" && entry.child === child);
}

/** The diff of each base's repo against its recorded HEAD, as one summary line per repo and the changed files. A child's repo that is gone keeps its last handoff as the line. */
export function diffAgainstBases(entries: Entry[]): Diff {
	const lines: string[] = [];
	const files: string[] = [];
	const paths: string[] = [];
	const own = new Set(ownBases(entries).map((base) => base.repo));
	for (const { repo, head, child } of bases(entries)) {
		// A repo the loop works in itself is diffed once, against its own base.
		if (child !== undefined && own.has(repo)) continue;
		const stat = git(repo, ["diff", "--shortstat", head]);
		const names = git(repo, ["diff", "--name-only", head])?.split("\n").filter(Boolean) ?? [];
		const untracked = git(repo, ["ls-files", "--others", "--exclude-standard"])?.split("\n").filter(Boolean) ?? [];
		if (stat === undefined) {
			const handoff = child === undefined ? undefined : resultOf(entries, child);
			if (handoff && (typeof handoff.headSha === "string" || Array.isArray(handoff.changedFiles))) {
				const ahead = typeof handoff.commitsAhead === "number" ? `${handoff.commitsAhead} commit${handoff.commitsAhead === 1 ? "" : "s"} ahead` : "handoff";
				lines.push(`${basename(repo)}: ${ahead}${typeof handoff.headSha === "string" ? ` at ${handoff.headSha.slice(0, 9)}` : ""} (worktree gone)`);
				files.push(...((handoff.changedFiles as unknown[]) ?? []).map((name) => `${basename(repo)}/${String(name)}`));
			} else {
				lines.push(`${basename(repo)}: diff unavailable`);
			}
			continue;
		}
		if (stat) lines.push(`${basename(repo)}: ${stat}`);
		files.push(...names.map((name) => `${basename(repo)}/${name}`), ...untracked.map((name) => `${basename(repo)}/${name}`));
		paths.push(...[...names, ...untracked].map((name) => join(repo, name)));
	}
	return { summary: lines.join("\n") || (bases(entries).length ? "no tracked changes" : "no repository"), files, paths };
}

export function diffText(diff: Diff, limit = 1200): string {
	const shown = diff.files.slice(0, 30).join(", ");
	return `${diff.summary}${shown ? `\nfiles: ${shown}${diff.files.length > 30 ? ", …" : ""}` : ""}`.slice(0, limit);
}

// --- durable artifacts ---------------------------------------------------------------------------

const ARTIFACT = /(?:^|\/)docs\/specs\/[^/]+\/(decision|spec|design|verification)\.md$/;

export function artifactKind(path: string): "decision" | "spec" | "design" | "verification" | undefined {
	return ARTIFACT.exec(path.replace(/\\/g, "/"))?.[1] as "decision" | "spec" | "design" | "verification" | undefined;
}

const hash = (text: string): string => createHash("sha1").update(text).digest("hex").slice(0, 8);

function sections(text: string): Record<string, string> {
	const found: Record<string, string> = {};
	let heading: string | undefined;
	let body: string[] = [];
	const flush = () => {
		if (heading === undefined) return;
		let key = heading;
		for (let n = 2; key in found; n++) key = `${heading} #${n}`;
		found[key] = hash(body.join("\n").trim());
	};
	for (const line of text.split("\n")) {
		const match = /^#{1,6}\s+(.*\S)\s*$/.exec(line);
		if (match) {
			flush();
			heading = match[1];
			body = [];
		} else {
			body.push(line);
		}
	}
	flush();
	return found;
}

function tableRows(text: string): string[][] {
	return text
		.split("\n")
		.filter((line) => /^\s*\|.*\|\s*$/.test(line))
		.map((line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()))
		.filter((cells) => cells.length >= 2 && !cells.every((cell) => /^:?-{2,}:?$/.test(cell)));
}

function previous(entries: Entry[], stage: string, path: string): Entry | undefined {
	return [...entries].reverse().find((entry) => entry.stage === stage && entry.auto === true && entry.path === path);
}

/** The entry fields summarising `text` of an artifact, compared with the book's last entry for the same file. */
export function summarizeArtifact(entries: Entry[], path: string, text: string): { stage: string; fields: Record<string, unknown> } | undefined {
	const kind = artifactKind(path);
	if (!kind) return undefined;
	const before = previous(entries, kind, path);
	const fields: Record<string, unknown> = { auto: true, path };
	if (kind === "decision") {
		const rows = tableRows(text).filter((cells) => ["grounded", "confirmed", "open"].includes(cells[cells.length - 1].toLowerCase()));
		const state: Record<string, string> = {};
		const questions: Record<string, string> = {};
		const counts: Record<string, number> = { grounded: 0, confirmed: 0, open: 0 };
		for (const cells of rows) {
			const status = cells[cells.length - 1].toLowerCase();
			counts[status]++;
			state[hash(cells[0])] = status;
			questions[hash(cells[0])] = cells[0];
		}
		const old = (before?.rowState ?? {}) as Record<string, string>;
		fields.counts = counts;
		fields.changed = Object.keys(state).filter((key) => old[key] !== state[key]).map((key) => questions[key]);
		fields.rowState = state;
		return { stage: kind, fields };
	}
	const now = sections(text);
	const old = (before?.sections ?? {}) as Record<string, string>;
	fields.sections = now;
	fields.changed = Object.keys(now).filter((heading) => old[heading] !== now[heading]);
	if (before) fields.removed = Object.keys(old).filter((heading) => !(heading in now));
	if (kind === "spec") {
		fields.status = /^\s*Status:\s*(\S+)/m.exec(text)?.[1] ?? null;
		fields.approvedFrom = /^\s*Approved from:\s*\S/m.test(text);
	}
	if (kind === "design") fields.approach = approachFilled(text);
	if (kind === "verification") {
		const counts: Record<string, number> = { pass: 0, fail: 0, unknown: 0 };
		for (const cells of tableRows(text)) {
			const result = cells[cells.length - 1].toLowerCase();
			if (result in counts) counts[result]++;
		}
		fields.counts = counts;
	}
	return { stage: kind, fields };
}

/** True when a heading named Approach (or 做法) has text under it, subsections included. */
export function approachFilled(text: string): boolean {
	const lines = text.split("\n");
	const start = lines.findIndex((line) => /^#{1,6}\s+.*(approach|做法)/i.test(line));
	if (start < 0) return false;
	const depth = /^(#+)/.exec(lines[start])?.[1].length ?? 1;
	for (const line of lines.slice(start + 1)) {
		const heading = /^(#+)\s/.exec(line);
		if (heading && heading[1].length <= depth) break;
		if (line.trim() && !heading) return true;
	}
	return false;
}

const SPEC_FOLDER = /docs\/specs\/[^\s/#"'`)\]]+/;

/** The spec folder of the loop: the one a recorded artifact lives in, else one named by the intent or a todo, if it exists. */
export function specFolder(entries: Entry[], todos: Task[], cwd: string): string | undefined {
	const artifact = [...entries].reverse().find((entry) => typeof entry.path === "string" && artifactKind(entry.path));
	if (artifact) return dirname(artifact.path as string);
	const texts = [
		currentIntent(entries) ?? "",
		...entries.filter((entry) => entry.stage === "task").flatMap((entry) => [String(entry.subject ?? ""), ...((entry.refs ?? []) as { ref: string }[]).map((item) => item.ref)]),
		...todos.flatMap((task) => [task.subject, ...refsOf(task.metadata), String(task.metadata?.anchor ?? "")]),
	];
	for (const text of texts) {
		const found = SPEC_FOLDER.exec(text)?.[0];
		if (found && existsSync(resolve(cwd, found))) return found;
	}
	return undefined;
}

/** The artifact `name` in `folder` as a summary entry read from disk, for a loop that did not write it. */
export function artifactOnDisk(folder: string, name: string, cwd: string): Entry | undefined {
	const path = join(folder, `${name}.md`);
	try {
		const text = readFileSync(resolve(cwd, path), "utf-8");
		const summary = summarizeArtifact([], path, text);
		return summary ? { ts: "", stage: summary.stage, ...summary.fields } : undefined;
	} catch {
		return undefined;
	}
}

// --- todo links ----------------------------------------------------------------------------------

const MARKDOWN = /\.(md|markdown)$/i;

const isMarkdownRef = (ref: string): boolean => MARKDOWN.test(ref.split("#")[0]);

/** The `ref` metadata of a task as pointers: `<path>#<heading>` into markdown, or the path of any other file. */
export function refsOf(metadata: Record<string, unknown> | undefined): string[] {
	const ref = metadata?.ref;
	const list = Array.isArray(ref) ? ref : [ref];
	return list.filter((item): item is string => typeof item === "string" && item.trim() !== "" && (item.includes("#") || !isMarkdownRef(item)));
}

/**
 * The line range of the section `<path>#<heading>` names, such as `L88-L101`, or `missing` when the file or heading is gone.
 * A ref to a file that is not markdown has no headings to resolve and returns "" (shown as given). Relative paths resolve against
 * the cwd, the loop's repos, and the folders of recorded artifacts.
 */
export function resolveRef(ref: string, cwd: string, entries: Entry[]): string {
	if (!isMarkdownRef(ref)) return "";
	const split = ref.indexOf("#");
	if (split < 0) return "";
	const path = ref.slice(0, split);
	const heading = ref.slice(split + 1).trim();
	const dirs = [
		cwd,
		...bases(entries).map((base) => base.repo),
		...new Set(entries.filter((entry) => typeof entry.path === "string").map((entry) => dirname(resolve(cwd, entry.path as string)))),
	];
	for (const dir of dirs) {
		let lines: string[];
		try {
			lines = readFileSync(resolve(dir, path), "utf-8").split("\n");
		} catch {
			continue;
		}
		const found = lines.map((line) => /^(#{1,6})\s+(.*\S)\s*$/.exec(line));
		let start = found.findIndex((match) => match?.[2] === heading);
		if (start < 0) start = found.findIndex((match) => match?.[2].toLowerCase() === heading.toLowerCase());
		if (start < 0) continue;
		const depth = found[start]?.[1].length ?? 1;
		let end = lines.length;
		for (let i = start + 1; i < lines.length; i++) {
			const match = found[i];
			if (match && match[1].length <= depth) {
				end = i;
				break;
			}
		}
		while (end > start + 1 && !lines[end - 1].trim()) end--;
		return `L${start + 1}-L${end}`;
	}
	return "missing";
}

/**
 * The latest `task` entry of each task id, in id order. The todos are those of the session that holds the book: an `adopt` entry
 * retires every task recorded before it, since those ids name the old session's todo list, which the new session does not have.
 * The new session's todos (carried in by the adopt, or created after it) then reuse those ids, and a child binds by ticket to its units.
 */
export function latestTasks(entries: Entry[]): Entry[] {
	const byId = new Map<number, Entry>();
	for (const entry of entries) {
		if (entry.stage === "adopt") byId.clear();
		else if (entry.stage === "task" && typeof entry.id === "number") byId.set(entry.id, entry);
	}
	return [...byId.values()].sort((a, b) => (a.id as number) - (b.id as number));
}

export const TASK_LEGEND = "#id status subject — anchor (last exit) — ref → line range; missing = heading gone";

/** One line per live task: its own anchor with the last exit code of a matching bash call, and its refs with current line ranges. */
export function taskLines(entries: Entry[], todos: Task[], cwd: string): string[] {
	const live = new Map(todos.map((task) => [task.id, task]));
	const exits = new Map<number, Entry>();
	for (const entry of entries) if (entry.stage === "taskrun" && typeof entry.id === "number") exits.set(entry.id, entry);
	return latestTasks(entries)
		.filter((entry) => live.has(entry.id as number))
		.map((entry) => {
			const task = live.get(entry.id as number);
			const run = exits.get(entry.id as number);
			const anchor = typeof entry.anchor === "string" ? `${entry.anchor}${run ? ` (exit ${run.exit})` : ""}` : "loop anchor";
			const refs = ((entry.refs ?? []) as { ref: string }[]).map((item) => {
				const range = resolveRef(item.ref, cwd, entries);
				return range ? `${item.ref} → ${range}` : item.ref;
			});
			const followup = task?.metadata?.followup ?? entry.followup;
			return [`#${entry.id} ${task?.status} ${task?.subject}`, anchor, ...(refs.length ? [refs.join(", ")] : []), ...(followup !== undefined ? [`followup: ${String(followup)}`] : [])].join(" — ");
		});
}
