/**
 * The phase machine: each loop kind runs a fixed sequence of phases, and the book's evidence says which
 * phases are complete. Nothing here blocks; a phase entered while an earlier one is incomplete yields
 * one warning line that names what is missing and the `skip` escape. Phases regress by themselves when
 * evidence changes (a diff after verify, a spec edited back to proposed) and by `back` on request.
 */

import { existsSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, extname, isAbsolute, join, relative, resolve } from "node:path";
import {
	countsAsLanding,
	type Book,
	type Entry,
	type Kind,
	type Task,
	allFriction,
	anchorCommand,
	anchorIsCommand,
	artifactOnDisk,
	bases,
	contentHashes,
	currentKind,
	diffAgainstBases,
	isRunEntry,
	lastActIndex,
	lastIndex,
	observeItems,
	repoRootOf,
	specFolder,
	withChildActs,
} from "./book.ts";

export const SEQUENCES: Record<Kind, readonly string[]> = {
	quick: ["act", "check", "reflect", "close"],
	inline: ["anchor", "act", "verify", "reflect", "close"],
	reviewed: ["anchor", "act", "verify", "review", "reflect", "close"],
	durable: ["decide", "grill", "spec", "read", "approve", "design", "anchor", "act", "verify", "review", "reflect", "close"],
};

export type Status = { name: string; state: "done" | "skipped" | "missing"; note: string; /** Skipped by the evidence itself (no open rows, no friction), not by a `skip` declaration. */ auto?: boolean };

export type Phases = {
	kind: Kind | "undeclared";
	statuses: Status[];
	/** The last phase of the complete prefix, or `start`. */
	current: string;
	/** The first incomplete phase, `fix` when a check or review failed after the last change, else `close`. */
	next: string;
	missing: string;
	skipped: string[];
	backs: string[];
};

export type Inputs = { entries: Entry[]; cwd: string; todos: Task[]; env?: NodeJS.ProcessEnv };

// --- paths ---------------------------------------------------------------------------------------

const EXEMPT_IN_PROJECT = ["scratch", "docs/specs"];
const EXEMPT_ROOTS = [tmpdir(), "/tmp", "/var/folders"];
const EXEMPT_EXTENSIONS = [".md", ".txt", ".html", ".htm"];

/** The real path of `path`, resolving symlinks such as /var → /private/var through its nearest existing parent. */
function real(path: string): string {
	if (existsSync(path)) return realpathSync(path);
	const parent = dirname(path);
	return parent === path ? path : join(real(parent), basename(path));
}

function within(root: string, target: string): boolean {
	const rel = relative(root, target);
	return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

/**
 * True for a file that is not code work: scratch and spec folders of the project or of any git repo the file lives in, and
 * temp files outside every repo. A file inside a git repo counts as work wherever the repo is, even under a temp dir.
 */
export function outsideWork(filePath: string, cwd: string): boolean {
	const root = real(cwd);
	const target = real(resolve(cwd, filePath));
	const inFolders = (base: string) => EXEMPT_IN_PROJECT.some((dir) => within(join(base, dir), target));
	if (within(root, target)) return inFolders(root);
	const repo = repoRootOf(target);
	if (repo) return inFolders(repo);
	return EXEMPT_ROOTS.some((tmp) => within(real(tmp), target));
}

/** Markdown, text, and HTML files and everything `outsideWork` names: an edit the anchor gate does not warn about. */
export function exempt(filePath: string, cwd: string): boolean {
	return EXEMPT_EXTENSIONS.includes(extname(filePath).toLowerCase()) || outsideWork(filePath, cwd);
}

// --- reach -----------------------------------------------------------------------------------------

/** What a change reaches, measured from its diff: the count an unreviewed loop is re-classified at, not the author's confidence. */
export type Reach = { source: string[]; modules: string[]; behavior: string[]; crossed: string[] };

/** The kinds that never run a review; a change past the reach thresholds asks them to re-classify. */
export const REVIEWLESS: ReadonlySet<string> = new Set(["quick", "inline"]);
const REACH_FILES = 3;
const REACH_MODULES = 2;

// `spec/` and `specs/` count as tests, the RSpec and Jasmine layout; a durable spec folder is outside work anyway.
const TEST_PATH = /(?:^|\/)(?:tests?|__tests__|testdata|fixtures|specs?)\/|\.(?:test|spec)\.[^/]+$|(?:^|\/)(?:test_[^/]+|conftest)\.py$|_test\.(?:py|go)$/i;
const LOCKFILE =
	/(?:^|\/)(?:package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|uv\.lock|poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum|Gemfile\.lock|composer\.lock|flake\.lock|pubspec\.lock|mix\.lock|packages\.lock\.json|Package\.resolved)$/;
/** Files that describe behavior to its users: a change to one beside source code changes what users were told. */
const BEHAVIOR = /(?:^|\/)(?:(?:README|CHANGELOG)(?:\.[a-z0-9]+)?|\.changelog\/[^/]+|[^/]+\.schema\.json)$/i;

/** Each path of the diff with its repo and repo-relative POSIX name, leaving out work outside the loop's code and paths still as the loop found them. */
function loopPaths(entries: Entry[], cwd: string): { repo: string; rel: string }[] {
	const repos = bases(entries).map((base) => base.repo);
	const found = new Map<string, Record<string, string>>();
	for (const entry of entries) if (entry.stage === "base" && entry.dirty && typeof entry.dirty === "object") found.set(String(entry.repo), entry.dirty as Record<string, string>);
	const paths = diffAgainstBases(entries)
		.paths.filter((path) => !outsideWork(path, cwd))
		.map((path) => {
			const repo = repos.find((root) => within(root, path)) ?? cwd;
			return { repo, rel: relative(repo, path).split("\\").join("/") };
		});
	const unchanged = new Set<string>();
	for (const repo of repos) {
		const dirty = found.get(repo) ?? {};
		const names = paths.filter((path) => path.repo === repo && path.rel in dirty).map((path) => path.rel);
		const now = names.length ? contentHashes(repo, names) : {};
		// An `unknown` hash proves nothing, so that path counts.
		for (const name of names) if (dirty[name] !== "unknown" && now[name] === dirty[name]) unchanged.add(`${repo}\0${name}`);
	}
	return paths.filter((path) => !unchanged.has(`${path.repo}\0${path.rel}`));
}

/**
 * The reach of the loop's diff against its bases: source files (not tests, lockfiles, behavior files, or what `exempt`
 * names), the top-level directories they sit in, and the behavior files changed beside them. Paths already dirty when
 * a base was recorded count once their content changes. A file at a repository root counts as a file, not a module.
 * `crossed` names each threshold passed: `files` at three source files, `modules` at two directories, `behavior` at one
 * behavior file.
 */
export function reachOf(entries: Entry[], cwd: string): Reach {
	const several = bases(entries).length > 1;
	const source: string[] = [];
	const behavior: string[] = [];
	const modules = new Set<string>();
	for (const { repo, rel } of loopPaths(entries, cwd)) {
		const shown = several ? `${basename(repo)}/${rel}` : rel;
		if (BEHAVIOR.test(rel)) behavior.push(shown);
		else if (!TEST_PATH.test(rel) && !LOCKFILE.test(rel) && !exempt(join(repo, rel), cwd)) {
			source.push(shown);
			if (rel.includes("/")) modules.add(`${several ? `${basename(repo)}/` : ""}${rel.slice(0, rel.indexOf("/"))}`);
		}
	}
	const counted = source.length > 0 ? behavior : [];
	const crossed = [
		...(source.length >= REACH_FILES ? ["files"] : []),
		...(modules.size >= REACH_MODULES ? ["modules"] : []),
		...(counted.length > 0 ? ["behavior"] : []),
	];
	return { source: source.sort(), modules: [...modules].sort(), behavior: counted.sort(), crossed };
}

/** The thresholds a `kind` call with a `reason` has answered so far. */
function answeredReach(entries: Entry[]): Set<string> {
	const answered = new Set<string>();
	for (const entry of entries) if (entry.stage === "kind" && typeof entry.reason === "string" && Array.isArray(entry.crossed)) for (const name of entry.crossed) answered.add(String(name));
	return answered;
}

/** The thresholds the reach crossed that no `kind` answer covers yet; empty for a reviewed or durable loop. */
export function unansweredReach(entries: Entry[], reach: Reach | undefined): string[] {
	if (!reach || !REVIEWLESS.has(currentKind(entries) ?? "inline")) return [];
	const answered = answeredReach(entries);
	return reach.crossed.filter((name) => !answered.has(name));
}

/** The one line that asks an unreviewed loop to re-classify; an undeclared loop is asked to declare its kind. */
export function reachLine(reach: Reach, kind: string | undefined): string {
	const modules = reach.modules.length ? ` / ${reach.modules.length} module${reach.modules.length === 1 ? "" : "s"} (${reach.modules.slice(0, 4).join(", ")}${reach.modules.length > 4 ? ", …" : ""})` : "";
	const told = reach.behavior.length ? ` / ${reach.behavior.slice(0, 3).join(", ")}${reach.behavior.length > 3 ? ", …" : ""}` : "";
	const ask = kind ? `kind with reason: reviewed, or why ${kind} fits` : "declare kind with intent and reason: reviewed, or why inline fits";
	return `reach ${reach.source.length} file${reach.source.length === 1 ? "" : "s"}${modules}${told}; ${ask}`;
}

// --- evidence ------------------------------------------------------------------------------------

type Ctx = Inputs & { seq: readonly string[]; folder?: string; lastAct: number };

const done = (name: string, note = ""): Status => ({ name, state: "done", note });
const missing = (name: string, note: string): Status => ({ name, state: "missing", note });

function same(a: string, b: string): boolean {
	const group = (name: string) => (name === "check" ? "verify" : name);
	return group(a) === group(b);
}

/** Entries before this index do not count for `name`: the latest `back` to this phase or an earlier one. */
function floor(entries: Entry[], seq: readonly string[], name: string): number {
	const at = seq.indexOf(name);
	let from = 0;
	entries.forEach((entry, index) => {
		if (entry.stage !== "back" || typeof entry.phase !== "string") return;
		const target = seq.findIndex((candidate) => same(candidate, entry.phase as string));
		if (target >= 0 && at >= target) from = index + 1;
	});
	return from;
}

function lastWhere(entries: Entry[], from: number, test: (entry: Entry) => boolean): number {
	for (let i = entries.length - 1; i >= from; i--) if (test(entries[i])) return i;
	return -1;
}

function skipEntry(entries: Entry[], from: number, name: string): Entry | undefined {
	const index = lastWhere(entries, from, (entry) => entry.stage === "skip" && typeof entry.phase === "string" && same(entry.phase, name));
	return index >= 0 ? entries[index] : undefined;
}

/** The latest recorded summary of an artifact since `from`; a loop that never wrote it falls back to the file on disk. */
function artifact(ctx: Ctx, name: string, from: number): Entry | undefined {
	// The file on disk is the current state (a `sed` edit through bash is not observed); entries are history.
	const disk = ctx.folder && from === 0 ? artifactOnDisk(ctx.folder, name, ctx.cwd) : undefined;
	if (disk) return disk;
	const index = lastWhere(ctx.entries, from, (entry) => entry.stage === name && entry.auto === true);
	return index >= 0 ? ctx.entries[index] : undefined;
}

const total = (counts: unknown): number => Object.values((counts ?? {}) as Record<string, number>).reduce((sum, n) => sum + Number(n), 0);

/** The index of the first spec entry in the latest run of proposed-or-approved spec entries, -1 when there is no entry for it, or undefined when the spec is not proposed. */
function proposedSince(ctx: Ctx): number | undefined {
	let start: number | undefined;
	let seen = false;
	ctx.entries.forEach((entry, index) => {
		if (entry.stage !== "spec" || entry.auto !== true) return;
		seen = true;
		const live = entry.status === "proposed" || entry.status === "approved";
		if (!live) start = undefined;
		else if (start === undefined) start = index;
	});
	if (seen) return start;
	const disk = ctx.folder ? artifactOnDisk(ctx.folder, "spec", ctx.cwd) : undefined;
	return disk && (disk.status === "proposed" || disk.status === "approved") ? -1 : undefined;
}

/**
 * The first observation the anchor lists that no passing `verify` with its checkpoint number follows the last landing, as `observe i/n: text`,
 * or undefined when all are closed. Before any landing every observation is open: it can be seen only on what landed.
 */
function openObservation(entries: Entry[], from: number): string | undefined {
	const items = observeItems(entries);
	if (items.length === 0) return undefined;
	const landed = lastWhere(entries, 0, countsAsLanding);
	for (let i = 0; i < items.length; i++) {
		const seen = landed < 0 ? -1 : lastWhere(entries, Math.max(from, landed + 1), (entry) => (entry.stage === "verify" || entry.stage === "check") && entry.checkpoint === i + 1);
		if (seen < 0 || entries[seen].result === "fail") return `observe ${i + 1}/${items.length}: ${items[i]}${landed < 0 ? " (after it lands)" : ""}`;
	}
	return undefined;
}

function evaluate(name: string, ctx: Ctx): Status {
	const { entries } = ctx;
	const from = floor(entries, ctx.seq, name);
	const skip = skipEntry(entries, from, name);
	if (skip) return { name, state: "skipped", note: String(skip.reason ?? skip.skip ?? "") };
	switch (name) {
		case "decide": {
			const decision = artifact(ctx, "decision", from);
			return total(decision?.counts) > 0 ? done(name) : missing(name, ctx.folder ? `${ctx.folder}/decision.md with decision rows (Status grounded, confirmed, or open)` : "decision.md with decision rows with Status grounded, confirmed, or open (no spec folder: name it in `intent` by calling `kind` again)");
		}
		case "grill": {
			const decision = artifact(ctx, "decision", from);
			if (!decision || total(decision.counts) === 0) return missing(name, "decision rows to grill");
			const open = Number((decision.counts as Record<string, number>).open ?? 0);
			if (open > 0) return missing(name, `${open} open decision row${open === 1 ? "" : "s"}`);
			const first = entries.find((entry) => entry.stage === "decision" && entry.auto === true);
			return first && Number((first.counts as Record<string, number>).open ?? 0) === 0 ? { name, state: "skipped", note: "no open rows", auto: true } : done(name);
		}
		case "spec": {
			const spec = artifact(ctx, "spec", from);
			return spec?.status === "proposed" || spec?.status === "approved" ? done(name) : missing(name, "spec.md with Status: proposed");
		}
		case "read": {
			const start = proposedSince(ctx);
			if (start === undefined) return missing(name, "a proposed spec to read");
			const index = lastWhere(entries, Math.max(from, start + 1), (entry) => entry.stage === "goldfish" && entry.ok !== false);
			if (index >= 0) return done(name, String(entries[index].source ?? ""));
			const wrote = entries.some((entry) => entry.stage === "spec" && entry.auto === true);
			const specs = entries.filter((entry) => entry.stage === "spec" && entry.auto === true);
			if (specs.length > 0 && start >= 0 && entries[start].status === "approved" && !entries.slice(0, start).some((entry) => entry.stage === "spec" && entry.status === "proposed")) return done(name, "spec approved");
			if (!wrote && from === 0 && artifact(ctx, "spec", 0)?.status === "approved") return done(name, "spec approved before this loop");
			return missing(name, "a fresh-context read of the spec (dispatch a subagent, or `anchorloop_stage fresh-read`)");
		}
		case "approve": {
			const spec = artifact(ctx, "spec", from);
			return spec?.status === "approved" && spec.approvedFrom === true ? done(name) : missing(name, `spec.md Status: approved with Approved from${spec?.status ? ` (now ${spec.status})` : ""}`);
		}
		case "design": {
			const design = artifact(ctx, "design", from);
			return design?.approach === true ? done(name) : missing(name, "design.md with its approach section filled");
		}
		case "anchor": {
			const index = lastWhere(entries, from, (entry) => entry.stage === "anchor");
			return index >= 0 ? done(name, String(entries[index].check ?? "")) : missing(name, "a `Reality anchor:` line, `metadata.anchor` on the first todo, or `anchor` on the kind call");
		}
		case "act":
			return lastWhere(entries, from, (entry) => entry.stage === "edit" || countsAsLanding(entry)) >= 0 ? done(name) : missing(name, "a change to the code");
		case "check":
		case "verify": {
			const index = lastWhere(entries, Math.max(from, ctx.lastAct + 1), isRunEntry);
			if (index < 0) {
				const command = anchorCommand(entries);
				if (!command) return missing(name, "a verify declaration or a run of the anchor");
				return missing(name, anchorIsCommand(entries) ? `a passing run of \`${command}\` after the last change` : "evidence for the anchor after the last change: a run of its command, or `verify` naming what you observed");
			}
			const entry = entries[index];
			if (entry.declared === true && entry.result === "fail") return missing(name, "the declared verify failed");
			if (entry.declared !== true && entry.exit !== 0) return missing(name, `the anchor exited ${entry.exit ?? "unknown"} after the last change`);
			if (ctx.seq.includes("decide") && !artifact(ctx, "verification", from)) return missing(name, `${ctx.folder ?? "docs/specs/<folder>"}/verification.md (a durable loop's verify also needs it)`);
			const reach = entry.reach as Reach | undefined;
			if (unansweredReach(entries, reach).length > 0) return missing(name, reachLine(reach as Reach, currentKind(entries)));
			const open = openObservation(entries, from);
			if (open) return missing(name, open);
			return done(name, entry.declared === true ? "declared" : "");
		}
		case "review": {
			const index = lastWhere(entries, Math.max(from, ctx.lastAct + 1), (entry) => entry.stage === "review");
			if (index < 0) return missing(name, "a review round after the last change with Blocking: P0=0 P1=0");
			const round = entries[index];
			if (round.blocking === false) return done(name);
			const rounds = entries.filter((entry) => entry.stage === "review");
			const stalled = rounds.length >= 2 && rounds.at(-1)?.blocking === true && rounds.at(-2)?.blocking === true;
			return missing(name, stalled ? "two consecutive review rounds still blocking: hand the trend to the user" : round.blocking === true ? "blocking review findings are open" : "the review verdict is unknown");
		}
		case "reflect": {
			const items = allFriction(entries, ctx.env);
			if (items.length === 0) return { name, state: "skipped", note: "no friction", auto: true };
			const open = items.filter((item) => !item.reflected).length;
			return open === 0 ? done(name) : missing(name, `${open} friction entr${open === 1 ? "y" : "ies"} without a reflect`);
		}
		default:
			return missing(name, name);
	}
}

/** The phase state of the loop kind recorded in the book. */
export function computePhases(book: Pick<Book, "entries">, inputs: Omit<Inputs, "entries">): Phases {
	const kind = currentKind(book.entries);
	const seq = SEQUENCES[kind ?? "inline"];
	const entries = withChildActs(book.entries);
	const ctx: Ctx = { ...inputs, entries, seq, folder: specFolder(entries, inputs.todos, inputs.cwd), lastAct: lastActIndex(entries) };
	const statuses = seq.filter((name) => name !== "close").map((name) => evaluate(name, ctx));
	let prefix = 0;
	while (prefix < statuses.length && statuses[prefix].state !== "missing") prefix++;
	const first = statuses[prefix];
	const reached = statuses.slice(0, prefix).filter((status) => status.state === "done").at(-1);
	let next = first ? first.name : "close";
	let note = first ? first.note : "";
	const last = ctx.lastAct;
	const verify = entries.map((entry, index) => ({ entry, index })).filter(({ entry, index }) => index > last && isRunEntry(entry)).at(-1)?.entry;
	const review = entries.map((entry, index) => ({ entry, index })).filter(({ entry, index }) => index > last && entry.stage === "review").at(-1)?.entry;
	if ((next === "verify" || next === "check") && last >= 0 && verify && verify.exit !== 0 && verify.declared !== true) next = "fix";
	else if (next === "review" && last >= 0 && review?.blocking === true) next = "fix";
	if (next === "fix") note = first?.note ?? "";
	const skipped = statuses.filter((status) => status.state === "skipped" && status.note !== "no friction").map((status) => `${status.name} (${status.note})`);
	const backs = book.entries.filter((entry) => entry.stage === "back").map((entry) => `${entry.phase} (${entry.reason})`);
	return {
		kind: kind ?? "undeclared",
		statuses,
		current: reached?.name ?? "start",
		next,
		missing: note,
		skipped,
		backs,
	};
}

/** The statuses of phases before `entering` that are incomplete. */
export function incompleteBefore(phases: Phases, entering: string): Status[] {
	const order = phases.statuses.map((status) => status.name);
	const at = entering === "close" ? order.length : order.findIndex((name) => same(name, entering));
	return phases.statuses.filter((status, index) => index < at && status.state === "missing");
}

/** One line: the phases still missing before the one entered. */
export function jumpLine(entering: string, missingBefore: Status[]): string {
	return `anchorloop: before ${entering}, still missing: ${missingBefore.map((status) => `${status.name} (${status.note})`).join("; ")}.`;
}

/** The phase line `read` and the close summary show. */
export function describe(phases: Phases): string {
	const parts = [`${phases.kind} · phase ${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}${phases.missing ? ` (missing: ${phases.missing})` : ""}`];
	if (phases.skipped.length) parts.push(`skipped: ${phases.skipped.join(", ")}`);
	if (phases.backs.length) parts.push(`back: ${phases.backs.join(", ")}`);
	return parts.join(" · ");
}

/** Remembers which incomplete phases a jump already warned about; a regression adds one and warns again. */
export class JumpMemory {
	private warned = new Map<string, Set<string>>();

	/** True when `missingNames` holds a phase not yet warned about for this book and entering phase. */
	fresh(bookId: string, entering: string, missingNames: string[]): boolean {
		const key = `${bookId}|${entering}`;
		const before = this.warned.get(key) ?? new Set<string>();
		const news = missingNames.some((name) => !before.has(name));
		if (missingNames.length === 0) this.warned.delete(key);
		else this.warned.set(key, new Set(missingNames));
		return news;
	}
}

export { lastIndex };
