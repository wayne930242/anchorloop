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

export const KINDS = ["quick", "inline", "reviewed", "durable"] as const;
export type Kind = (typeof KINDS)[number];

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

function real(path: string): string {
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
	return env.PI_SUBAGENT_ID || undefined;
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
		owner: child ? env.PI_SUBAGENT_NAME || child : "main",
		session: (child ? env.PI_SUBAGENT_SESSION : undefined) || who.sessionManager.getSessionFile?.() || null,
		cwd: real(who.cwd),
		opened: new Date().toISOString(),
	};
	const lines = ["# anchorloop loop book", ...Object.entries(header).map(([key, value]) => `${key}: ${JSON.stringify(value)}`), "entries:", ""];
	appendBytes(path, lines.join("\n"), true);
	return { path, header, entries: [] };
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
	const stem = basename(path, ".yml");
	let n = 1;
	while (existsSync(join(dirname(path), `${stem}.closed-${n}.yml`))) n++;
	renameSync(path, join(dirname(path), `${stem}.closed-${n}.yml`));
}

export type ChildBook = { book: Book; tag: string };

/** The books of the child `id` among all projects: its earlier closed loops (`~1`, `~2`) in order, then the current one (no tag). */
export function findChildBooks(id: string, env: NodeJS.ProcessEnv = process.env): ChildBook[] {
	const root = booksRoot(env);
	if (!existsSync(root)) return [];
	const found: ChildBook[] = [];
	for (const project of readdirSync(root)) {
		const agents = join(root, project, "agents");
		let files: string[];
		try {
			files = readdirSync(agents);
		} catch {
			continue;
		}
		const aside = files
			.map((file) => ASIDE.exec(basename(file, ".yml")))
			.filter((match): match is RegExpExecArray => match !== null && match[1] === safe(id))
			.sort((a, b) => Number(a[2]) - Number(b[2]));
		for (const match of aside) {
			const book = parseBook(join(agents, `${match[0]}.yml`));
			if (book) found.push({ book, tag: `~${match[2]}` });
		}
		const book = parseBook(join(agents, `${safe(id)}.yml`));
		if (book) found.push({ book, tag: "" });
	}
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
	try {
		unlinkSync(path);
	} catch {
		// Already gone.
	}
	tidy(dirname(path));
}

export type Sweep = { deleted: string[]; open: string[] };

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
					if (!slug || project === slug) result.open.push(`${book.path} (${currentKind(book.entries) ?? "no kind"}: ${currentIntent(book.entries) ?? "no intent"})`);
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

const NOT_STAGES = new Set(["base", "link", "close", "task", "taskrun", "verification", "skip", "back", "friction", "reflect", "goldfish"]);

/** The stages the book shows, in order of first appearance; `edit` entries read as `act`. */
export function stagesDone(entries: Entry[]): string[] {
	const seen: string[] = [];
	for (const entry of entries) {
		if (NOT_STAGES.has(entry.stage)) continue;
		const name = entry.stage === "edit" ? "act" : entry.stage;
		if (!seen.includes(name)) seen.push(name);
	}
	return seen;
}

export function lastIndex(entries: Entry[], ...stages: string[]): number {
	for (let i = entries.length - 1; i >= 0; i--) if (stages.includes(entries[i].stage)) return i;
	return -1;
}

/**
 * The book's entries with the change entries and anchor runs of its linked children merged in by time, each marked `child`, so
 * a coordinator whose edits are all made by children still shows an act, and a child's anchor run on what the coordinator
 * now holds is its verify. A child's run drops its reach, which the child's own loop answers. Children are linked only
 * through pi-herdr-agents (`PI_SUBAGENT_ID`); pi itself has no subagents. Indexes into the result differ from indexes into
 * `entries`.
 */
export function withChildWork(entries: Entry[], env: NodeJS.ProcessEnv = process.env): Entry[] {
	const acts: Entry[] = [];
	for (const id of childIds(entries)) {
		for (const { book } of findChildBooks(id, env)) {
			for (const entry of book.entries) {
				if (entry.stage === "edit") acts.push({ ...entry, child: id });
				else if (entry.stage === "check") {
					const { reach: _reach, ...run } = entry;
					acts.push({ ...run, child: id });
				}
			}
		}
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

/**
 * The index of the latest change entry (a production write or edit, a commit), or -1. A merge that lands a tree an earlier
 * passing anchor run checked (a child's run in its worktree, then a fast-forward) changes nothing that run did not see.
 */
export function lastActIndex(entries: Entry[]): number {
	const checked = new Set<string>();
	let last = -1;
	entries.forEach((entry, index) => {
		if (entry.stage === "check" && entry.exit === 0 && Array.isArray(entry.trees)) for (const tree of entry.trees) checked.add(String(tree));
		if (entry.stage === "edit" && !(typeof entry.tree === "string" && checked.has(entry.tree))) last = index;
	});
	return last;
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

/** A review recorded after the last change with no blocking finding on it. */
export function reviewClearAfterLastAct(raw: Entry[]): boolean {
	const entries = withChildWork(raw);
	const review = lastIndex(entries, "review");
	return review >= 0 && review > lastActIndex(entries) && entries[review].blocking === false;
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

function evidenceLine(entry: Entry): string {
	return `${entry.stage} ${entry.declared ? `declared: ${entry.note ?? entry.result}` : `exit ${entry.exit ?? "unknown"}${entry.last ? `: ${entry.last}` : ""}`}`;
}

/** The latest check or verify entry after the last change, or undefined when none follows it. */
export function verifyAfterLastAct(raw: Entry[]): Entry | undefined {
	const entries = withChildWork(raw);
	const index = lastIndex(entries, "check", "verify");
	return index >= 0 && index > lastActIndex(entries) ? entries[index] : undefined;
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

/** Every friction entry of the book and of its linked children, each with the reflect that covers it, if any. */
export function allFriction(entries: Entry[], env: NodeJS.ProcessEnv = process.env): FrictionItem[] {
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

function git(cwd: string, args: string[], env?: NodeJS.ProcessEnv): string | undefined {
	try {
		return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf-8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"], env: env ?? process.env }).trim();
	} catch {
		return undefined;
	}
}

/**
 * The tree a commit of everything in `repo`'s working state would have (tracked and untracked, ignored files and `scratch/`
 * left out), built in a copy of the index so the repo's own index is untouched; undefined when git cannot build it.
 */
export function workingTree(repo: string): string | undefined {
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

/** The tree of `repo`'s HEAD commit. */
export function headTree(repo: string): string | undefined {
	return git(repo, ["rev-parse", "HEAD^{tree}"]);
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
	const repo = git(existingDir(dirname(resolve(path))), ["rev-parse", "--show-toplevel"]);
	return repo ? real(repo) : undefined;
}

export function bases(entries: Entry[]): { repo: string; head: string }[] {
	return entries.filter((entry) => entry.stage === "base").map((entry) => ({ repo: String(entry.repo), head: String(entry.head) }));
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
	if (bases(book.entries).some((base) => base.repo === found.repo)) return false;
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
	if (!found || bases(book.entries).some((base) => base.repo === found.repo)) return false;
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

/** The diff of each base's repo against its recorded HEAD, as one summary line per repo and the changed files. */
export function diffAgainstBases(entries: Entry[]): Diff {
	const lines: string[] = [];
	const files: string[] = [];
	const paths: string[] = [];
	for (const { repo, head } of bases(entries)) {
		const stat = git(repo, ["diff", "--shortstat", head]);
		const names = git(repo, ["diff", "--name-only", head])?.split("\n").filter(Boolean) ?? [];
		const untracked = git(repo, ["ls-files", "--others", "--exclude-standard"])?.split("\n").filter(Boolean) ?? [];
		if (stat === undefined) {
			lines.push(`${basename(repo)}: diff unavailable`);
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

/** The latest `task` entry of each task id, in id order. */
export function latestTasks(entries: Entry[]): Entry[] {
	const byId = new Map<number, Entry>();
	for (const entry of entries) if (entry.stage === "task" && typeof entry.id === "number") byId.set(entry.id, entry);
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
