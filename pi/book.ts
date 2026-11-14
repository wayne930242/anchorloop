/**
 * pi extension: the loop book. The first `todo` create opens a loop and its book as `inline`, its intent the first todo's subject
 * and its anchor a stated `Reality anchor:` line or the todo's `metadata.anchor`; a `kind` declaration opens one too. The agent declares only
 * what the program cannot observe (`kind` to choose `reviewed` or `durable`, a non-command `verify`,
 * `fresh-read`, `friction`, `reflect`, `skip`, `back`, `close`); the extension derives the rest from
 * evidence: production edits, the exit code of the anchor command, reviewer results, durable artifacts,
 * and the fresh-reader subagent. A phase machine over that evidence warns once per jump and never blocks;
 * only `close` refuses, while a todo is neither done nor disposed of.
 */

import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
	type Book,
	type Entry,
	KINDS,
	allFriction,
	anchorCommand,
	appendEntry,
	countsAsLanding,
	artifactKind,
	bases,
	real,
	projectSlug,
	childId,
	childIds,
	childLines,
	createBook,
	currentIntent,
	currentKind,
	deleteBook,
	diffAgainstBases,
	findChildBooks,
	frictionOf,
	git,
	guarded,
	isOpenTask,
	latestTasks,
	observeItems,
	openLoop,
	ownBases,
	repoOf,
	replayTodos,
	refsOf,
	repoRootOf,
	retryPairs,
	resolveRef,
	reviewTrend,
	reviews,
	reviewsStalled,
	specFolder,
	stagesDone,
	summarizeArtifact,
	taskLines,
	taskDetails,
	taskOfEntry,
	type Sweep,
	sweep,
	touchRepo,
	touchRepoBeforeMerge,
	validFollowup,
	verifyAfterLastAct,
	workingTrees,
	adoptableRun,
	REVIEWERS,
	treeAtField,
	ignoredByGit,
	passingRunOf,
	adoptBook,
	movedTo,
	parseBook,
	bookPath,
	resultOf,
	type TreeCache,
	withTrees,
} from "./support/book.ts";
import { type Link, dispatchFrom, isChild, linkFrom, resultFrom } from "./support/host.ts";
import { classify } from "./support/jev.ts";
import { PUSH, pushRefspecs } from "./support/pushes.ts";
import { sweepProjectDirs } from "./support/projects.ts";
import { checkLandings, declareLanded, integrationRef, landLines, linkNotes, partialLines, pushedSince, refSha, remoteTips, watchesRefs, watchTips } from "./support/landing.ts";
import { linkOfResult, priorSpawns } from "./support/links.ts";
import { orphanLines } from "./support/orphans.ts";
import { REVIEWLESS, SEQUENCES, describe, incompleteBefore, outsideWork, reachLine, reachOf, unansweredReach } from "./support/phases.ts";
import { type Snapshot, snapshot } from "./support/snapshot.ts";
import { childAnchor, childrenOf, computeLoop, taskTickets, ticketKeys, todoForTickets, unitById, unitLine, unitOfDispatch, unitsOf, unitWidgetLine } from "./support/units.ts";

export const SESSION_ENTRY = "anchorloop-loop";
const STAGES = ["kind", "verify", "fresh-read", "friction", "reflect", "skip", "back", "landed", "close", "read"] as const;
const BLOCKING = /Blocking\s*:?\**\s*:?\s*P0\s*=\s*(\d+)\D{0,5}P1\s*=\s*(\d+)/gi;
const ANCHOR_LINE = /Reality anchor:[ \t]*(.*)/;

type Params = {
	stage: (typeof STAGES)[number];
	kind?: (typeof KINDS)[number];
	intent?: string;
	anchor?: string;
	note?: string;
	result?: "pass" | "fail";
	tried?: string;
	found?: string;
	led_by?: string;
	friction?: (string | number)[];
	class?: "misdirection" | "gap" | "resolved";
	action?: string;
	phase?: string;
	reason?: string;
	verdict?: "landed" | "blocked" | "abandoned";
	view?: "summary" | "all";
	sha?: string;
	ref?: string;
	task?: number;
	observe?: string[];
	checkpoint?: number;
	resume?: string;
};

/** The fields of a `tool_result` event the book reads. */
type ToolResultEvent = { toolName: string; toolCallId: string; input: unknown; content?: unknown; details?: unknown; isError?: boolean; structuredContent?: unknown };

type Block = { type?: string; text?: string };
type BranchEntry = { type?: string; message?: { role?: string; content?: unknown } };

/** The P0 and P1 counts of the last `Blocking: P0=<n> P1=<m>` line in a reviewer report, tolerant of markdown emphasis. */
export function parseBlocking(text: string): { p0: number; p1: number } | undefined {
	const found = [...text.matchAll(BLOCKING)].at(-1);
	return found ? { p0: Number(found[1]), p1: Number(found[2]) } : undefined;
}

function textOf(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return (content as Block[]).map((block) => (block && typeof block.text === "string" ? block.text : "")).filter(Boolean).join("\n");
}

/** `text` cut to `limit` characters, the cut marked. */
function clip(text: string, limit = 120): string {
	return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

const SHOWN_BOOKS = 3;

/** The session_start summary: counts on one line, then the newest open books of this project and where the rest are. */
function sweepLines(swept: Sweep, projects = 0): string[] {
	const counts = [
		...(swept.open.length ? [`${swept.open.length} open loop book${swept.open.length === 1 ? "" : "s"} in this project`] : []),
		...(swept.deleted.length ? [`${swept.deleted.length} stale deleted`] : []),
		...(projects ? [`${projects} stale project dir${projects === 1 ? "" : "s"} removed`] : []),
	];
	if (counts.length === 0) return [];
	const newest = [...swept.open].sort((a, b) => b.mtimeMs - a.mtimeMs);
	const day = (ms: number) => {
		const date = new Date(ms);
		return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
	};
	const rest = newest.length - SHOWN_BOOKS;
	return [
		counts.join(", "),
		...newest.slice(0, SHOWN_BOOKS).map((book) => `  ${day(book.mtimeMs)} ${book.kind}: ${clip(book.intent, 80)}`),
		...(rest > 0 ? [`  … ${rest} more in ${dirname(newest[0].path)}`] : []),
	];
}

const ANSI = /\x1b\[[0-9;]*[A-Za-z]/g;
// Stack frames and traceback headers say where, not what; the key line says what failed.
const FRAME = /^(?:at\s|File\s"|Traceback\b|\^+$)/;
const KEY_LINES = [
	/^(?:FAILED|ERROR)\b/,
	/^E\s+\S/,
	/^[\w.]+(?:Error|Exception|Warning)\b:?/,
	/\b(?:error|fatal|panic|exception)\b/i,
	/\bfail(?:ed|ure|s)?\b/i,
];

/** The one line of a failed run's output that says what failed, at most 120 characters; the last line when none does. */
function keyLine(text: string): string {
	const raw = text.replace(ANSI, "").split("\n");
	// A Python frame's next line, indented under it, is the source it quotes, not the failure.
	const quoted = (index: number) => /^\s/.test(raw[index]) && /^\s*File\s"/.test(raw[index - 1] ?? "");
	const lines = raw.flatMap((line, index) => {
		const trimmed = line.trim();
		return trimmed && !FRAME.test(trimmed) && !quoted(index) ? [trimmed] : [];
	});
	for (const pattern of KEY_LINES) {
		const hit = lines.find((line) => pattern.test(line));
		if (hit) return clip(hit);
	}
	return clip(lines.at(-1) ?? "");
}

function lastLine(text: string): string {
	return (
		text
			.split("\n")
			.map((line) => line.trim())
			.filter(Boolean)
			.at(-1) ?? ""
	).slice(0, 200);
}

/** The exit code of a bash tool result: the structured code, else 0 when the call did not error, else the code the message names. */
export function bashExit(event: { isError?: boolean; structuredContent?: unknown; content?: unknown }): number | null {
	const code = (event.structuredContent as { exit_code?: unknown } | undefined)?.exit_code;
	if (typeof code === "number") return code;
	if (event.isError !== true) return 0;
	const named = /Command exited with code (\d+)/.exec(textOf(event.content));
	return named ? Number(named[1]) : null;
}

/** The command with quoted strings and comments blanked out, keeping every index, so quoted text never counts as a run or a separator. */
function unquoted(command: string): string {
	// One left-to-right pass, so whichever starts first wins: a quote, or a `#` that starts a word and comments out its line.
	// Newlines inside quotes are kept, since they still separate commands for the scan.
	return command.replace(/'[^']*'|"(?:\\.|[^"\\])*"|(^|\s)#[^\n]*/g, (span) => span.replace(/[^\n]/g, " "));
}

/** Runs of spaces and tabs collapsed, so `pytest  -q` is `pytest -q`; applied to the command and the anchor alike. */
const squeezed = (text: string): string => text.replace(/[ \t]+/g, " ");

/** Text before a run with `VAR=value` and simple wrappers (`uv run`, `time`, `timeout N`, `env`, `npx`, `pnpm exec`, `bunx`) peeled off its end. */
function beforeRun(text: string): string {
	return text.replace(/(\b\w+=\S*\s+|\buv\s+run\s+|\btime\s+|\btimeout\s+[^\s;&|]+\s+|\benv\s+|\b(?:npx|bunx)\s+(?:-\S+\s+)*|\bpnpm\s+exec\s+)+$/, "");
}

// `cd` and `export` change what a check tests, so they are not setup.
const SETUP_SEGMENT = /^\s*(\.|source\b|set\b|\w+=)/;

// A command position: the start, after a separator, a `{` or `(`, or after `if`, `then`, `while` and the like.
// A `{` counts only where it opens a group itself, not as a literal argument (`echo { x }`).
const SEPARATOR_OR_GROUP = String.raw`(?:^|&&|\|\||[;|!\n(])(?:\s*\{)?`;
const COMMAND_POSITION = new RegExp(String.raw`${SEPARATOR_OR_GROUP}\s*((if|then|elif|else|while|until|do)\s+)*$`);
// What voids the exit of a run after it: `x || run` may never run it, `! run` inverts its code.
const VOIDS_EXIT = /(!|\|\|)\s*(\(\s*|cd\s+\S+\s*&&\s*)*$/;
// `x=$(run)` as a whole command: the command's exit is the substitution's.
const ASSIGNMENT = new RegExp(String.raw`(${SEPARATOR_OR_GROUP})(\s*(?:\w+=\S*\s+)*\w+=)$`);

type Opening = { open: number; sub: boolean };

/** The parentheses still open at `at`; `sub` marks `$(`, `<(` and `>(`, whose exit is not the call's. */
function openings(masked: string, at: number): Opening[] {
	const stack: Opening[] = [];
	for (let i = 0; i < at; i++) {
		if (masked[i] === "(") stack.push({ open: i, sub: i > 0 && "$<>".includes(masked[i - 1]) });
		else if (masked[i] === ")") stack.pop();
	}
	return stack;
}

/** The text with every closed parenthesized span blanked, so a `set -o pipefail` inside a finished subshell is not seen. */
function withoutClosedGroups(text: string): string {
	const chars = [...text];
	const stack: number[] = [];
	chars.forEach((char, i) => {
		if (char === "(") stack.push(i);
		else if (char === ")" && stack.length > 0) chars.fill(" ", stack.pop() as number, i + 1);
	});
	return chars.join("");
}

/** The index of the `)` that closes the `(` at `open`, or undefined. */
function closing(masked: string, open: number): number | undefined {
	let depth = 0;
	for (let i = open; i < masked.length; i++) {
		if (masked[i] === "(") depth++;
		else if (masked[i] === ")" && --depth === 0) return i;
	}
	return undefined;
}

type Located = { at: number; anchor: string; masked: string; leads: number[]; depth: number };

/**
 * Where a run at `at` stands, or undefined when its exit is not the call's: inside `$(`, `<(` or `>(` unless the substitution is the
 * whole of an assignment (`x=$(run)`). `leads` are the positions whose prefix may void the exit: the run, each enclosing `(`, the assignment.
 */
function placement(masked: string, at: number): Pick<Located, "leads" | "depth"> | undefined {
	const stack = openings(masked, at);
	const leads = [at];
	const subs = stack.filter((group) => group.sub);
	if (subs.length > 1 || (subs.length === 1 && stack.at(-1) !== subs[0])) return undefined;
	for (const group of stack) {
		if (!group.sub) {
			leads.push(group.open);
			continue;
		}
		const assignment = masked[group.open - 1] === "$" ? ASSIGNMENT.exec(masked.slice(0, group.open - 1)) : null;
		if (!assignment || beforeRun(masked.slice(group.open + 1, at)).trim() !== "") return undefined;
		// Only redirects may follow the substitution; a further word, assignment, or substitution makes its own exit the call's.
		const close = closing(masked, group.open);
		if (close === undefined) return undefined;
		const tail = masked.slice(close + 1).split(/&&|\|\||[;|\n]|(?<![<>])&(?![>&])/)[0];
		if (!/^(\s*\d*[<>]{1,2}&?\s*[^\s$`(<>]+)*\s*$/.test(tail)) return undefined;
		leads.push(assignment.index + assignment[1].length);
	}
	return { leads, depth: stack.length };
}

function locate(command: string, anchorText: string): Located | undefined {
	const text = squeezed(command);
	const masked = unquoted(text);
	const segments = squeezed(anchorText).split("&&").map((segment) => segment.trim());
	const candidates = [squeezed(anchorText).trim()];
	if (segments.length > 1 && segments.slice(0, -1).every((segment) => SETUP_SEGMENT.test(segment))) candidates.push(segments.at(-1)!);
	for (const anchor of candidates) {
		if (!anchor) continue;
		let found: Located | undefined;
		for (let at = text.indexOf(anchor); at >= 0; at = text.indexOf(anchor, at + 1)) {
			// The anchor's own quotes match the command's; only its first character must lie outside quotes and comments.
			if (masked.charAt(at) !== text.charAt(at)) continue;
			const after = masked.charAt(at + anchor.length);
			if (!COMMAND_POSITION.test(beforeRun(masked.slice(0, at))) || !(after === "" || /[\s;&|)]/.test(after))) continue;
			const where = placement(masked, at);
			if (where) found = { at, anchor, masked, ...where };
		}
		if (found) return found;
	}
	return undefined;
}

/**
 * Where `command` runs `anchor` as a command (at the start, or after `&&`, `||`, `;`, `|`, `!`, `(`, `{`, a newline or `then`, outside quotes,
 * past any `VAR=value` prefixes and wrappers), as the last such run, or undefined. The full anchor is tried first; an anchor whose earlier
 * `&&` segments only set up the environment (`. venv/bin/activate && pytest -q`) also matches on its last segment.
 */
export function anchorRun(command: string, anchorText: string): { at: number; anchor: string } | undefined {
	const found = locate(command, anchorText);
	return found && { at: found.at, anchor: found.anchor };
}

/**
 * The exit to record for a bash call that ran `anchor`: the call's exit code, except `unknown` when something after the anchor
 * can replace it: `||`, `;`, a newline, `&`, or a pipe straight after the anchor unless `set -o pipefail` is in effect before it.
 * A chain `anchor && other` keeps a failed anchor's code, so it stands.
 */
export function anchorExit(command: string, anchorText: string, exit: number | null): number | "unknown" {
	if (exit === null) return "unknown";
	const run = locate(command, anchorText);
	if (!run) return "unknown";
	const { at, anchor, masked, leads, depth } = run;
	// `! anchor` inverts the code and `x || anchor` may never run it; the same holds for the group or assignment around it.
	if (leads.some((lead) => VOIDS_EXIT.test(beforeRun(masked.slice(0, lead))))) return "unknown";
	// Inside a subshell, a pipefail set or the exit of what follows is not this shell's.
	const rest = masked.slice(at + anchor.length);
	// The last `set -o pipefail` or `set +o pipefail` before the anchor decides.
	const toggles = [...withoutClosedGroups(masked.slice(0, at)).matchAll(/\bset\b[^;&|\n]*?([-+])\w*o\s+pipefail\b/g)];
	if (depth > 0 && toggles.length === 0 && /\|(?!\|)/.test(rest)) return "unknown";
	const pipefail = toggles.at(-1)?.[1] === "-";
	let chained = false;
	// `&&` keeps a failed anchor's exit; `||`, `;`, and a newline can replace it, and so can a pipe
	// straight after the anchor unless pipefail is set.
	for (const [separator] of rest.matchAll(/&&|\|\||\||(?<![<>&])&(?![&>])|;|\n/g)) {
		if (separator === "&&") chained = true;
		else if (separator === "|") {
			if (!chained && !pipefail) return "unknown";
		} else return "unknown";
	}
	return exit;
}

const GIT_ARG = String.raw`(?:"[^"]*"|'[^']*'|\S+)`;
// Global options git accepts before the verb: `-C <dir>`, `-c <k=v>`, `--git-dir=<dir>`, `--no-pager`, and the like.
const GIT_OPTION = String.raw`\s+(?:-[Cc]\s+${GIT_ARG}|--(?:git-dir|work-tree|namespace|exec-path|config-env)(?:=|\s+)${GIT_ARG}|--(?:no-pager|paginate|no-replace-objects|bare|literal-pathspecs|no-optional-locks)|-p)`;
const GIT_MERGE = new RegExp(String.raw`\bgit((?:${GIT_OPTION})*)\s+(merge|cherry-pick|pull)(?=\s|$)`, "g");
// Arguments that make the verb do no work, or end one: only the words up to the next separator count.
const GIT_NO_WORK = /(^|\s)--(abort|quit|skip|dry-run)\b/;

/** The first `git merge`, `cherry-pick` or `pull` at a command position that does work, with the directory it runs in. */
export function mergeRun(command: string): { verb: string; dir: string } | undefined {
	const masked = unquoted(command);
	for (const match of command.matchAll(GIT_MERGE)) {
		const at = match.index;
		if (masked.slice(at, at + 3) !== "git" || !COMMAND_POSITION.test(beforeRun(masked.slice(0, at)))) continue;
		if (GIT_NO_WORK.test(command.slice(at + match[0].length).split(/[|;&\n]/)[0])) continue;
		// The repo is the nearest `cd` before the verb, moved on by each `-C` of the verb itself.
		const cds = [...command.slice(0, at).matchAll(/\bcd\s+(\S+)/g)];
		const unquote = (word: string) => word.replace(/^(["'])(.*)\1$/, "$2").replace(/^~(?=\/|$)/, homedir());
		const dirs = [...match[1].matchAll(new RegExp(String.raw`-C\s+(${GIT_ARG})`, "g"))].map((found) => unquote(found[1]));
		return { verb: match[2], dir: dirs.reduce((base, dir) => resolve(base, dir), unquote(cds.at(-1)?.[1] ?? ".")) };
	}
	return undefined;
}

/** True when `before` changes into a directory that is not one of the repo `roots`: a run after it tests something else. */
function cdsOutside(before: string, roots: string[], cwd: string): boolean {
	for (const found of before.matchAll(/\bcd\s+("[^"]*"|'[^']*'|[^\s;&|]+)/g)) {
		const target = found[1].replace(/^(["'])(.*)\1$/, "$2").replace(/^~(?=\/|$)/, homedir());
		if (!roots.includes(real(resolve(cwd, target)))) return true;
	}
	return false;
}

/** The directory a run at `at` in `command` runs in: `cwd` moved by each `cd` before it. */
function ranIn(command: string, at: number, cwd: string): string {
	let dir = cwd;
	for (const found of command.slice(0, at).matchAll(/\bcd\s+("[^"]*"|'[^']*'|[^\s;&|]+)/g)) {
		dir = resolve(dir, found[1].replace(/^(["'])(.*)\1$/, "$2").replace(/^~(?=\/|$)/, homedir()));
	}
	return dir;
}

/** The text a `Reality anchor:` line states in an assistant message, if any. */
function statedAnchor(message: { role?: string; content?: unknown } | undefined): string | undefined {
	if (message?.role !== "assistant") return undefined;
	const found = ANCHOR_LINE.exec(textOf(message.content));
	return found ? found[1].trim().slice(0, 300) || "(stated on the next line)" : undefined;
}

const WIDGET_KEY = "anchorloop";

const reply = (text: string) => ({ content: [{ type: "text" as const, text }], details: undefined });

export default function (pi: ExtensionAPI) {
	const subagent = isChild();
	// Watched-ref tips taken before each bash call, by call id.
	const tipsBefore = new Map<string, Record<string, string>>();
	// The remote-tracking tips of the loop's own repos before a bash call that may push, by call id: the branches it pushes are cars.
	const remotesBefore = new Map<string, Map<string, Record<string, string>>>();
	function todosOf(ctx: ExtensionContext) {
		return replayTodos(ctx.sessionManager.getBranch());
	}

	function phasesOf(book: Book, ctx: ExtensionContext) {
		return computeLoop(book, { cwd: ctx.cwd, todos: todosOf(ctx) }).phases;
	}

	/** The line that tells the agent Jev did not accept a returned subagent as the fresh read, while the read is still open. */
	function freshReadLine(book: Book, phases: ReturnType<typeof phasesOf>): string[] {
		const last = [...book.entries].reverse().find((entry) => entry.stage === "goldfish");
		const open = phases.statuses.find((status) => status.name === "read")?.state === "missing";
		return open && last?.source === "jev" && last.ok === false ? [`fresh read by ${String(last.child || "a subagent")} judged not fresh — declare \`fresh-read\` if it was`] : [];
	}

	function summaryLines(book: Book, ctx: ExtensionContext): string[] {
		const cache: TreeCache = new Map();
		const looped = computeLoop(book, { cwd: ctx.cwd, todos: todosOf(ctx), scope: { cache } });
		const { phases } = looped;
		const verify = [...book.entries].reverse().find((entry) => entry.stage === "verify" || entry.stage === "check");
		const open = todosOf(ctx).filter(isOpenTask).length;
		const friction = allFriction(book.entries);
		return [
			describe(phases),
			...looped.rows.map(unitLine),
			`intent: ${currentIntent(book.entries) ?? "not declared"}`,
			`last ${verify?.stage ?? "verify"}: ${verify ? `${verify.declared ? `declared ${verify.result}` : `exit ${verify.exit ?? "unknown"}`}${verify.last ? ` — ${verify.last}` : ""}${verifyAfterLastAct(book.entries, { cache }) ? "" : " (before the last change)"}` : "none"}`,
			`reviews: ${reviewTrend(book.entries)}; open todos: ${open}; friction: ${friction.length} (${friction.filter((item) => !item.reflected).length} unreflected)`,
			...childLines(book.entries).map((line) => `child ${line}`),
			...linkNotes(book.entries),
			...landLines(book.entries),
			...partialLines(book.entries),
			...orphanLines(book.entries),
			...friction.filter((item) => item.owner !== "main").map((item) => `friction ${item.ref}: ${item.tried} → ${item.found}${item.reflected ? ` [${item.class}]` : ""}`),
			...freshReadLine(book, phases),
		];
	}

	function recordTasks(book: Book, details: unknown, input: { action?: unknown; id?: unknown }, cwd: string): void {
		// A clear empties the list and restarts its ids at 1: the ids recorded so far name todos that are gone.
		if (input.action === "clear") {
			book.entries.push(appendEntry(book.path, "reset", {}));
			return;
		}
		const tasks = taskDetails(details) ?? [];
		const known = new Set(latestTasks(book.entries).map((entry) => entry.id));
		const touched = input.action === "create" ? tasks.filter((task) => !known.has(task.id)) : tasks.filter((task) => task.id === Number(input.id));
		for (const task of touched) {
			const refs = refsOf(task.metadata).map((ref) => ({ ref, range: resolveRef(ref, cwd, book.entries) }));
			const { anchor, followup, observe, kind, lands, agents } = task.metadata ?? {};
			// The unit metadata is kept too, so a child reading this book finds the unit it works for and that unit's anchor.
			book.entries.push(
				appendEntry(book.path, "task", {
					id: task.id,
					subject: task.subject,
					status: task.status,
					...(typeof anchor === "string" ? { anchor } : {}),
					...(Array.isArray(observe) ? { observe: observe.map(String) } : {}),
					...(typeof kind === "string" ? { kind } : {}),
					...(typeof lands === "string" ? { lands } : {}),
					...(Array.isArray(agents) ? { agents: agents.map(String) } : typeof agents === "string" ? { agents: [agents] } : {}),
					...(refs.length ? { refs } : {}),
					...(followup !== undefined ? { followup } : {}),
				}),
			);
		}
	}

	/** A `Reality anchor:` line stated since the last user message, recorded when a loop opens after it. */
	function recordPriorAnchor(book: Book, ctx: ExtensionContext): void {
		const branch = ctx.sessionManager.getBranch() as BranchEntry[];
		for (let i = branch.length - 1; i >= 0; i--) {
			const message = branch[i].type === "message" ? branch[i].message : undefined;
			if (!message) continue;
			if (message.role === "user") return;
			const stated = statedAnchor(message);
			if (stated) {
				book.entries.push(appendEntry(book.path, "anchor", { check: stated, line: true }));
				return;
			}
		}
	}

	/**
	 * Records a child the loop spawned: who and where it works, the ref its work will land on with that ref's tip now, and a base for
	 * its repo at the commit it started from, so the coordinator's diff includes the worker's change while its worktree exists.
	 */
	function recordLink(book: Book, link: Link, ctx: ExtensionContext): void {
		const cwd = ctx.cwd;
		const source = resolve(cwd, link.cwd ?? ".");
		const tickets = ticketKeys(`${link.name ?? ""} ${link.task ?? ""}`);
		// The unit this child works for may name the ref its work lands on.
		const found = unitsOf([...book.entries, { ts: "", stage: "link", child: link.child, name: link.name, tickets }], todosOf(ctx));
		const unit = unitById(found, found.bound.get(link.child) ?? -1);
		const tree = link.worktree?.path && existsSync(link.worktree.path) ? link.worktree.path : undefined;
		const ref = integrationRef(source, link, unit?.lands);
		const tip = ref ? refSha(tree ?? source, ref) : undefined;
		book.entries.push(
			appendEntry(book.path, "link", {
				child: link.child,
				name: link.name,
				agent: link.agent,
				...(link.sessionFile ? { sessionFile: link.sessionFile } : {}),
				...(tickets.length ? { tickets } : {}),
				cwd: source,
				...(link.worktree ? { worktree: link.worktree } : {}),
				...(link.acceptSec !== undefined ? { acceptSec: link.acceptSec } : {}),
				...(ref ? { ref, ...(tip ? { refSha: tip } : {}) } : {}),
				// A reviewer's verdict is of the code as it was when it was dispatched: the trees it was given.
				...(REVIEWERS.has(String(link.agent ?? "")) ? treeAtField(reviewedRepos(book, cwd)) : {}),
			}),
		);
		const where = repoOf(join(tree ?? source, "_"));
		if (where && !bases(book.entries).some((base) => base.repo === where.repo)) {
			book.entries.push(appendEntry(book.path, "base", { repo: where.repo, head: tree ? link.worktree?.baseSha ?? where.head : where.head, via: "link", child: link.child, dirty: {} }));
		}
	}

	/** The repos a reviewer reads: the loop's own repos, the one the session runs in, and each linked child's repo. */
	function reviewedRepos(book: Book, cwd: string): string[] {
		const here = repoRootOf(join(cwd, "_"));
		return [...new Set([...bases(book.entries).map((base) => base.repo), ...(here ? [here] : [])])].filter((repo) => existsSync(repo));
	}

	/**
	 * Records a follow-up task sent to a linked child (`subagent_send`, `subagent_resume`) as its own dispatch: the unit its brief names by
	 * ticket, and for a reviewer the trees it is given. A persistent reviewer's verdicts then count for the unit each brief names.
	 */
	function recordSend(book: Book, toolName: string, input: unknown, details: unknown, ctx: ExtensionContext): void {
		const dispatch = dispatchFrom(toolName, input, details);
		if (!dispatch) return;
		const link = [...book.entries].reverse().find(
			(entry) =>
				entry.stage === "link" &&
				((dispatch.id !== undefined && entry.child === dispatch.id) || (dispatch.sessionFile !== undefined && entry.sessionFile === dispatch.sessionFile) || (dispatch.name !== undefined && entry.name === dispatch.name)),
		);
		if (!link) return;
		const child = String(link.child);
		const todos = todosOf(ctx);
		const found = unitsOf(book.entries, todos);
		const task = unitOfDispatch(found, todos, child, dispatch.task);
		const tickets = ticketKeys(dispatch.task);
		book.entries.push(
			appendEntry(book.path, "send", {
				child,
				name: link.name,
				...(tickets.length ? { tickets } : {}),
				...(task !== undefined ? { task } : {}),
				...(REVIEWERS.has(String(link.agent ?? "")) ? treeAtField(reviewedRepos(book, ctx.cwd)) : {}),
			}),
		);
	}

	/** Links the children spawned before this loop opened and not yet returned. */
	function recordPriorLinks(book: Book, ctx: ExtensionContext): void {
		for (const link of priorSpawns(ctx.sessionManager.getBranch(), SESSION_ENTRY)) recordLink(book, link, ctx);
	}

	/** True while no `kind` call has chosen the kind: the loop still holds the `inline` a todo create opened it with. */
	function kindIsDefault(entries: Entry[]): boolean {
		return !entries.some((entry) => entry.stage === "kind" && typeof entry.kind === "string" && entry.auto !== true);
	}

	// A child looks up the anchor it inherits (its unit's, else its parent's loop anchor) on each bash call; the lookup scans books, so it is kept for a few seconds.
	let parent: { at: number; anchor: string | undefined } | undefined;
	function parentAnchorNow(): string | undefined {
		const id = childId();
		if (id === undefined) return undefined;
		if (!parent || Date.now() - parent.at > 5000) parent = { at: Date.now(), anchor: childAnchor(id) };
		return parent.anchor;
	}

	/** A child's book, opened from its own evidence (a production edit, a commit, a run of its parent's anchor) with no todo: inline, the parent's anchor as its anchor. */
	function openFromEvidence(ctx: ExtensionContext, base?: { repo: string; head: string }): Book {
		const book = createBook(ctx);
		if (base) book.entries.push(appendEntry(book.path, "base", { ...base, dirty: {} }));
		else touchRepo(book, join(ctx.cwd, "_"));
		book.entries.push(appendEntry(book.path, "kind", { kind: "inline", auto: true, intent: clip(`work of ${String(book.header.owner)}`, 200) }));
		recordPriorAnchor(book, ctx);
		const anchor = anchorCommand(book.entries) ? undefined : parentAnchorNow();
		if (anchor) book.entries.push(appendEntry(book.path, "anchor", { check: anchor, parent: true }));
		return book;
	}

	/** Opens a child's book for a bash call that ran its parent's anchor or committed a production change; undefined for any other call. */
	function openChildFromBash(ctx: ExtensionContext, event: { input: unknown; isError?: boolean; structuredContent?: unknown; content?: unknown }): Book | undefined {
		const command = String((event.input as { command?: unknown }).command ?? "");
		const anchor = parentAnchorNow();
		if (anchor && anchorRun(command, anchor)) return openFromEvidence(ctx);
		if (bashExit(event) !== 0 || !/\bgit\b[^|;&]*\bcommit\b/.test(command)) return undefined;
		const repo = repoRootOf(join(ctx.cwd, "_"));
		const head = repo ? git(repo, ["rev-parse", "HEAD"]) : undefined;
		const names = repo ? (git(repo, ["show", "--name-only", "--format=", "HEAD"]) ?? "").split("\n").filter(Boolean) : [];
		if (!repo || !head || !names.some((name) => !outsideWork(join(repo, name), ctx.cwd))) return undefined;
		const book = openFromEvidence(ctx, { repo, head: git(repo, ["rev-parse", "HEAD~1"]) ?? head });
		book.entries.push(appendEntry(book.path, "edit", { via: "commit" }));
		return book;
	}

	/** Opens the loop at the first todo create as `inline`: the first todo's subject is the intent, a stated `Reality anchor:` line or its `metadata.anchor` the anchor. */
	function openFromTodo(ctx: ExtensionContext, details: unknown): Book {
		const book = createBook(ctx);
		touchRepo(book, join(ctx.cwd, "_"));
		const first = (taskDetails(details) ?? [])[0];
		book.entries.push(appendEntry(book.path, "kind", { kind: "inline", auto: true, ...(first?.subject ? { intent: clip(first.subject.replace(/\s+/g, " ").trim(), 200) } : {}) }));
		recordPriorAnchor(book, ctx);
		recordPriorLinks(book, ctx);
		const anchor = first?.metadata?.anchor;
		if (typeof anchor === "string" && anchor.trim() && !anchorCommand(book.entries)) book.entries.push(appendEntry(book.path, "anchor", { check: anchor.trim() }));
		const inherited = !anchorCommand(book.entries) ? parentAnchorNow() : undefined;
		if (inherited) book.entries.push(appendEntry(book.path, "anchor", { check: inherited, parent: true }));
		const observe = first?.metadata?.observe;
		if (Array.isArray(observe) && observe.length > 0) book.entries.push(appendEntry(book.path, "observe", { items: observe.map((item) => clip(String(item), 200)).slice(0, 10) }));
		return book;
	}

	/** Adopts the book a handoff names by its id (`resume` on the first `kind`, or the first todo's `metadata.resume`); see `adoptBook`. */
	function resumeBook(ctx: ExtensionContext, id: string): ReturnType<typeof adoptBook> {
		const adopted = adoptBook(ctx, id.trim());
		if (adopted.book) touchRepo(adopted.book, join(ctx.cwd, "_"));
		return adopted;
	}

	/**
	 * The answer for a session whose book another session resumed: the marker at its path names that session. Read once, then removed,
	 * so the next call opens a loop of its own; undefined when this session's book was not moved.
	 */
	function movedNotice(ctx: ExtensionContext): string | undefined {
		const path = bookPath(ctx);
		const marker = parseBook(path);
		const moved = marker ? movedTo(marker) : undefined;
		if (!moved) return undefined;
		deleteBook(path);
		return `anchorloop: this session's loop book ${moved.id} was resumed by session ${moved.session} at ${moved.ts}, so nothing more is recorded here; continue the work in that session, or declare \`kind\` to open a new loop in this one.`;
	}

	function close(book: Book, ctx: ExtensionContext, verdict: string): { text: string; snapshot?: Snapshot } {
		const todos = replayTodos(ctx.sessionManager.getBranch());
		const undisposed = todos.filter((task) => isOpenTask(task) && !validFollowup(task.metadata?.followup));
		if (undisposed.length > 0) {
			throw new Error(
				`Cannot close: ${undisposed.length} todo(s) are pending or in progress without metadata.followup (a ticket id, \`memory\`, or \`drop — <reason>\`):\n` +
					undisposed.map((task) => `- #${task.id} ${task.subject}`).join("\n"),
			);
		}
		const kept = childId() !== undefined;
		const kind = currentKind(book.entries);
		const looped = computeLoop(book, { cwd: ctx.cwd, todos });
		const phases = looped.phases;
		// A loop of several units is complete only when each is: every unit's missing phases are named with the unit.
		const missing = looped.rows.length
			? looped.rows.flatMap((row) => incompleteBefore(row.phases, "close").map((status) => ({ ...status, name: `${row.unit.label} ${status.name}` })))
			: incompleteBefore(phases, "close");
		const diff = diffAgainstBases(book.entries);
		const friction = allFriction(book.entries);
		const phaseList = phases.statuses.map((status) => ({ phase: status.name, state: status.state === "skipped" && status.auto ? "auto-skipped" : status.state === "missing" ? "not shown complete" : status.state, ...(status.state === "skipped" ? { note: status.note } : {}) }));
		const summary = {
			intent: currentIntent(book.entries) ?? null,
			kind: kind ?? null,
			verdict,
			stages: stagesDone(book.entries),
			phases: phaseList,
			reviewRounds: reviews(book.entries).length,
			reviewTrend: reviewTrend(book.entries),
			diff: diff.summary,
			skipped: phases.skipped,
			back: phases.backs,
			friction: friction.map((item) => ({ ref: item.ref, owner: item.owner, tried: item.tried, found: item.found, led_by: item.led_by, class: item.class ?? null, action: item.action ?? null })),
			followups: todos.filter((task) => isOpenTask(task)).map((task) => ({ task: task.subject, followup: task.metadata?.followup })),
		};
		const unreflected = friction.filter((item) => !item.reflected);
		// The agent has just done the finished phases, so the result names only what is left.
		const text = [
			`closed (${verdict}).`,
			...(missing.length ? [`${verdict === "landed" ? "not complete" : "not reached"}: ${missing.map((status) => (verdict === "landed" ? `${status.name} (${status.note})` : status.name)).join("; ")}.`] : []),
			...(unreflected.length ? [`unreflected friction: ${unreflected.map((item) => `${item.ref} (${item.found})`).join("; ")}.`] : []),
		].join(" ");
		if (kept) {
			// A child's book stays for the main session to read and delete.
			appendEntry(book.path, "close", { verdict, summary: text.slice(0, 500) });
			return { text: `${text} The book stays for the main session.` };
		}
		// Jev judges the loop as it stood at close; the book is gone by the time the result is judged.
		const snap = kind === "quick" ? undefined : snapshot(book, ctx);
		pi.appendEntry(SESSION_ENTRY, summary);
		// Collect first: each delete drops the event's child-book index, so deleting inside the loop would re-index per link.
		const children = withTrees(() => childIds(book.entries).flatMap((id) => findChildBooks(id)));
		for (const { book: child } of children) deleteBook(child.path);
		deleteBook(book.path);
		return { text: `${text} Clear the todo list.`, snapshot: snap };
	}

	pi.registerTool({
		name: "anchorloop_stage",
		label: "Loop stage",
		description:
			"Loop book; the first `todo` create opens an inline loop. stage: kind (kind, intent, anchor, observe: checks after landing; reason to change the kind or answer a reach notice; resume: a handoff's book id), verify (note; checkpoint: an observe item; else a check not run in bash), fresh-read, friction (tried, found, led_by), reflect (friction ids like `worker#2`, class, action), skip/back (phase, reason), landed (sha, ref, task: an owner's notice; checked in git), close (verdict; refuses while an open todo lacks metadata.followup), read. Edits, anchor runs, reviews, specs are read from evidence.",
		parameters: {
			type: "object",
			properties: {
				stage: { type: "string", enum: [...STAGES] },
				kind: { type: "string", enum: [...KINDS] },
				intent: { type: "string" },
				anchor: { type: "string", description: "the check command" },
				note: { type: "string" },
				result: { type: "string", enum: ["pass", "fail"] },
				tried: { type: "string" },
				found: { type: "string" },
				led_by: { type: "string", description: "the misleading instruction, or `none`" },
				friction: { type: "array", items: { type: ["string", "number"] } },
				class: { type: "string", enum: ["misdirection", "gap", "resolved"] },
				action: { type: "string" },
				phase: { type: "string" },
				reason: { type: "string" },
				verdict: { type: "string", enum: ["landed", "blocked", "abandoned"] },
				view: { type: "string", enum: ["summary", "all"] },
				sha: { type: "string" },
				ref: { type: "string" },
				task: { type: "number" },
				observe: { type: "array", items: { type: "string" } },
				checkpoint: { type: "number" },
				resume: { type: "string" },
			},
			required: ["stage"],
			additionalProperties: false,
		},
		async execute(toolCallId: string, raw: unknown, signal: unknown, onUpdate: unknown, ctx: ExtensionContext) {
			try {
				return withTrees(() => stageTool(toolCallId, raw, signal, onUpdate, ctx));
			} finally {
				guarded(showStatus)(ctx);
			}
		},
	});

	function stageTool(_toolCallId: string, raw: unknown, _signal: unknown, _onUpdate: unknown, ctx: ExtensionContext) {
		const params = raw as Params;
		const { stage } = params;
		if (!(STAGES as readonly string[]).includes(stage)) throw new Error(`unknown stage \`${String(stage)}\`; declare one of ${STAGES.join(", ")}`);
		let book = openLoop(ctx);
		if (!book) {
			const moved = movedNotice(ctx);
			if (moved) return reply(moved);
		}
		let resumed: string | undefined;
		if (stage === "kind" && params.resume !== undefined) {
			// Only the book a handoff names is adopted, and only before this session's own loop holds evidence.
			if (book?.header.id !== params.resume) {
				const adopted = resumeBook(ctx, params.resume);
				if (!adopted.book) throw new Error(`resume refused: ${adopted.refused}`);
				book = adopted.book;
			}
			resumed = `resumed book ${params.resume}`;
		}
		if (!book && stage === "kind") {
			// A todo create in the same batch may not have landed yet; whichever comes first opens the loop.
			if (!params.kind || !params.intent) throw new Error("the first kind declaration needs `kind` and a one-line `intent`");
			book = createBook(ctx);
			recordPriorAnchor(book, ctx);
			recordPriorLinks(book, ctx);
		}
		if (!book) return reply("No loop is open, so nothing was recorded. A loop opens with the first `todo` create or `kind`.");
		const had = currentKind(book.entries);
		const sequence = SEQUENCES[had ?? "inline"];
		if (stage === "read") {
			// The id a handoff names, so the session that takes over can pass it as `resume`.
			const lines = [...summaryLines(book, ctx), ...taskLines(book.entries, todosOf(ctx), ctx.cwd), `book: ${String(book.header.id ?? "no id")}`];
			if (params.view === "all") lines.push("entries:", ...book.entries.map((entry) => JSON.stringify(entry).slice(0, 300)));
			return reply(lines.join("\n"));
		}
		if (stage === "landed") {
			// The ref may have moved since the last event; the state check records that landing first.
			checkLandings(book);
			const todos = todosOf(ctx);
			const found = unitsOf(book.entries, todos);
			const unit = params.task === undefined ? undefined : unitById(found, params.task);
			if (params.task !== undefined && !unit) throw new Error(`task ${String(params.task)} is not a unit of this loop`);
			const todo = unit ? todos.find((task) => task.id === unit.id) : undefined;
			return reply(declareLanded(book, { sha: params.sha, ref: params.ref, note: params.note, ...(unit ? { children: childrenOf(book.entries, found, unit), task: unit.id, tickets: todo ? taskTickets(todo) : [] } : {}) }).text);
		}
		if (stage === "close") {
			if (!params.verdict) throw new Error("close needs a verdict: landed, blocked, or abandoned");
			const closed = close(book, ctx, params.verdict);
			return { content: [{ type: "text" as const, text: closed.text }], details: closed.snapshot ? { snapshot: closed.snapshot } : undefined };
		}
		if (stage === "kind") {
			if (!params.kind && !params.intent && !params.anchor && !params.reason && !params.observe?.length && !resumed) throw new Error("kind needs `kind`, `intent`, `anchor`, `observe`, or `reason`");
			if (!had && (!params.kind || !params.intent)) throw new Error("the first kind declaration needs `kind` and a one-line `intent`");
			// The kind a todo create defaulted to is not a choice yet, so choosing another needs no reason.
			const changed = had !== undefined && params.kind !== undefined && had !== params.kind;
			if (changed && !params.reason && !kindIsDefault(book.entries)) throw new Error(`changing the kind from ${had} to ${params.kind} needs \`reason\`: the reach grew, the user added scope, a user-owned decision appeared, or the change turned out smaller`);
			touchRepo(book, join(ctx.cwd, "_"));
			if (params.kind || params.intent || params.reason) {
				// A reason answers the reach measured now, so a later threshold asks again.
				const answer = params.reason ? { reason: params.reason, crossed: reachOf(book.entries, ctx.cwd).crossed } : {};
				appendEntry(book.path, "kind", { kind: params.kind ?? had, ...(params.intent ? { intent: params.intent } : {}), ...answer });
			}
			if (params.anchor) appendEntry(book.path, "anchor", { check: params.anchor });
			if (params.observe?.length) appendEntry(book.path, "observe", { items: params.observe.map((item) => clip(String(item), 200)).slice(0, 10) });
			return reply(resumed ?? "ok");
		}
		if (stage === "verify") {
			if (!params.note) throw new Error("verify needs a `note` saying what was observed");
			const result = params.result ?? "pass";
			const recorded = childId() !== undefined || had === "quick" ? "check" : "verify";
			const todos = todosOf(ctx);
			const found = unitsOf(book.entries, todos);
			const unit = params.task === undefined ? undefined : unitById(found, params.task);
			if (params.task !== undefined && !unit) throw new Error(`task ${String(params.task)} is not a unit of this loop (a todo with observe, kind, lands, or agents metadata)`);
			// With two or more units a verify counts for one of them only, so the tool asks which instead of recording one that counts for none.
			if (!unit && found.units.length >= 2) throw new Error(`verify needs \`task\` in a loop of ${found.units.length} units: ${found.units.map((item) => `${item.label} (task ${item.id})`).join(", ")}`);
			if (params.checkpoint !== undefined) {
				const items = unit ? unit.observe : observeItems(book.entries);
				if (!Number.isInteger(params.checkpoint) || params.checkpoint < 1 || params.checkpoint > items.length) {
					const listing = unit ? undefined : found.units.find((item) => item.observe.length > 0);
					const where = items.length
						? `1 to ${items.length}`
						: listing
							? `none listed on the loop; todo #${listing.id} ${listing.label === `#${listing.id}` ? `"${clip(listing.subject, 60)}"` : listing.label} lists ${listing.observe.length}: give \`task: ${listing.id}\``
							: "none listed: give `observe` on the kind call";
					throw new Error(`checkpoint ${String(params.checkpoint)} is not an observation of this ${unit ? `unit (${unit.label})` : "loop"} (${where})`);
				}
				appendEntry(book.path, recorded, { declared: true, note: params.note, result, exit: result === "pass" ? 0 : 1, checkpoint: params.checkpoint, ...(unit ? { task: unit.id } : {}) });
				return reply(book.entries.some(countsAsLanding) ? "ok" : "ok (an observation counts once the work has landed)");
			}
			const entry = appendEntry(book.path, recorded, { declared: true, note: params.note, result, exit: result === "pass" ? 0 : 1, ...(unit ? { task: unit.id } : {}), ...reachField(book, ctx.cwd) });
			book.entries.push(entry);
			const notice = reachNotice(book, entry);
			return reply(notice ? `ok\n${notice}` : "ok");
		}
		if (stage === "fresh-read") {
			appendEntry(book.path, "goldfish", { source: "declared", ...(params.note ? { note: params.note } : {}) });
			return reply("ok");
		}
		if (stage === "friction") {
			if (!params.tried || !params.found) throw new Error("friction needs `tried` and `found`");
			const id = frictionOf(book.entries).length + 1;
			appendEntry(book.path, "friction", { id, tried: params.tried, found: params.found, led_by: params.led_by || "none" });
			return reply(`friction #${id}`);
		}
		if (stage === "reflect") {
			const known = allFriction(book.entries).map((item) => item.ref);
			const ids = (params.friction ?? []).map(String);
			if (ids.length === 0 || !params.class) throw new Error(`reflect needs \`friction\` ids (${known.join(", ") || "none recorded"}) and \`class\``);
			const unknown = ids.filter((id) => !known.includes(id));
			if (unknown.length) throw new Error(`unknown friction ${unknown.join(", ")}; known: ${known.join(", ") || "none"}`);
			appendEntry(book.path, "reflect", { friction: ids, class: params.class, ...(params.action ? { action: params.action } : {}) });
			return reply("ok");
		}
		// skip and back; with `task`, they reach only that unit, and the phase is one of that unit's kind
		const phase = params.phase;
		const units = params.task === undefined ? undefined : unitsOf(book.entries, todosOf(ctx));
		const unit = units && params.task !== undefined ? unitById(units, params.task) : undefined;
		if (params.task !== undefined && !unit) throw new Error(`task ${String(params.task)} is not a unit of this loop (a todo with observe, kind, lands, or agents metadata)`);
		const kindOf = unit?.kind ?? had;
		const known = (unit?.kind ? SEQUENCES[unit.kind] : sequence).filter((name) => name !== "close");
		if (!phase || !known.includes(phase)) throw new Error(`${stage} needs \`phase\`, one of ${known.join(", ")} for ${unit ? `${unit.label}, a` : "a"} ${kindOf ?? "undeclared"} ${unit ? "unit" : "loop"}`);
		if (!params.reason) throw new Error(`${stage} needs a \`reason\``);
		appendEntry(book.path, stage, { phase, reason: params.reason, ...(unit ? { task: unit.id } : {}) });
		return reply("ok");
	}

	pi.on(
		"session_start",
		guarded((_event, ctx) => {
			const swept = sweep(process.env, ctx.cwd);
			// The daily sweep of project dirs whose checkout is gone; a failure is shown, not hidden, and does not stop the start-up.
			let projects = { removed: 0, log: "" };
			let failed: string | undefined;
			try {
				const found = sweepProjectDirs(process.env, projectSlug(ctx.cwd));
				projects = { removed: found.removed.length, log: found.log };
			} catch (error) {
				failed = `project dir sweep failed: ${error instanceof Error ? error.message : String(error)}`;
			}
			const [summary, ...lines] = sweepLines(swept, projects.removed);
			if (projects.removed) lines.push(`  removed project dirs are listed in ${projects.log}`);
			if (failed) lines.push(failed);
			const open = openLoop(ctx);
			if (open) withTrees(() => {
				checkLandings(open);
				lines.push(...orphanLines(open.entries).map((line) => `child ${line}`));
			});
			if (summary !== undefined || lines.length > 0) ctx.ui.notify([`anchorloop${summary ? `: ${summary}` : ""}`, ...lines].join("\n"), "info");
			showStatus(ctx);
		}),
	);

	pi.on(
		"tool_call",
		guarded((event, ctx) => {
			if (event.toolName === "bash") {
				// The tips of the watched refs before the call, so a ref the call itself moves is told from one moved elsewhere.
				const book = openLoop(ctx);
				if (book) tipsBefore.set(event.toolCallId, watchTips(book));
				const command = String((event.input as { command?: unknown }).command ?? "");
				if (book && PUSH.test(command) && watchesRefs(book.entries)) {
					remotesBefore.set(event.toolCallId, new Map(ownBases(book.entries).filter((base) => existsSync(base.repo)).map((base) => [base.repo, remoteTips(base.repo)])));
				}
				return;
			}
			if (event.toolName !== "write" && event.toolName !== "edit") return;
			const path = (event.input as { path?: unknown }).path;
			if (typeof path !== "string") return;
			let book = openLoop(ctx);
			// A child's first production edit opens its book, before the file changes, so the base is the state it started from.
			if (!book && childId() !== undefined && !artifactKind(path) && !outsideWork(path, ctx.cwd)) book = openFromEvidence(ctx);
			if (book) touchRepo(book, resolve(ctx.cwd, path));
		}),
	);

	/**
	 * Records each branch a bash call pushed (git says so: the remote-tracking ref moved by this checkout's own push) as a car this session
	 * sends, bound to the unit whose ticket its name holds; its landing in the integration ref then counts for that unit.
	 */
	function recordPushes(book: Book, before: Map<string, Record<string, string>>, command: string, ctx: ExtensionContext): void {
		const named = pushRefspecs(command);
		const todos = todosOf(ctx);
		const found = unitsOf(book.entries, todos);
		for (const [repo, tips] of before) {
			for (const pushed of pushedSince(repo, tips, named)) {
				const task = todoForTickets(todos, ticketKeys(pushed.ref));
				const unit = task === undefined ? undefined : unitById(found, task);
				book.entries.push(appendEntry(book.path, "push", { repo, ...pushed, ...(unit ? { task: unit.id } : {}) }));
			}
		}
	}

	/** The reach of an unreviewed loop's diff, recorded on its verify or check entry; a reviewed loop is never measured. */
	function reachField(book: Book, cwd: string): { reach?: ReturnType<typeof reachOf> } {
		return REVIEWLESS.has(currentKind(book.entries) ?? "inline") ? { reach: reachOf(book.entries, cwd) } : {};
	}

	/** The line that asks the loop to re-classify after a verify or check entry whose reach no `kind` answer covers. */
	function reachNotice(book: Book, entry: Entry): string | undefined {
		const reach = entry.reach as ReturnType<typeof reachOf> | undefined;
		return reach && unansweredReach(book.entries, reach).length > 0 ? `anchorloop: ${reachLine(reach, currentKind(book.entries))}.` : undefined;
	}

	/** The repos the loop works in: the repos it changed and the one it runs in. */
	function loopRepos(book: Book, cwd: string): string[] {
		const here = repoRootOf(join(cwd, "_"));
		return [...new Set([...ownBases(book.entries).map((base) => base.repo), ...(here ? [here] : [])])];
	}

	function loopTrees(book: Book, cwd: string): string[] {
		return workingTrees(loopRepos(book, cwd));
	}

	/** A child's anchor run carries the trees it ran on, so the coordinator can tell whether it holds that same state. */
	function treesField(book: Book, cwd: string): { trees?: string[] } {
		const trees = loopTrees(book, cwd);
		return trees.length ? { trees } : {};
	}

	/**
	 * Records a linked child's passing run of the loop anchor as this loop's verify when the loop now holds exactly the state
	 * that run checked (after a merge lands a worker's branch, or when a child that worked in this checkout returns), so the
	 * coordinator does not run the anchor a second time. Any other state, or another command, leaves verify to its own run.
	 */
	function adoptChildRun(book: Book, cwd: string): void {
		const anchor = anchorCommand(book.entries);
		if (!anchor || verifyAfterLastAct(book.entries) || !book.entries.some((entry) => entry.stage === "link")) return;
		const repos = loopRepos(book, cwd);
		const at = treeAtField(repos);
		const trees = Object.values(at.treeAt ?? {});
		const found = adoptableRun(book.entries, anchor, trees, repos, cwd);
		if (!found) return;
		const last = `adopted from ${found.name}${found.run.last ? `: ${String(found.run.last)}` : ""}`.slice(0, 200);
		book.entries.push(appendEntry(book.path, "verify", { command: anchor.slice(0, 200), exit: 0, last, adopted: found.name, child: found.child, trees, ...at, ...reachField(book, cwd) }));
	}

	/**
	 * In a loop of two or more units, records a returned child's passing run of its own unit's anchor as that unit's verify, with the tree
	 * the run recorded (its worktree, or the checkout it ran in): the verify stands while that tree is unchanged, so the coordinator does
	 * not run the unit's anchor again. A run the child's later edit made stale, or one already adopted, is not taken.
	 */
	function adoptUnitRuns(book: Book, ctx: ExtensionContext): void {
		const found = unitsOf(book.entries, todosOf(ctx));
		const repos = loopRepos(book, ctx.cwd);
		for (const unit of found.units) {
			if (!unit.anchor) continue;
			for (const [child, id] of found.bound) {
				if (id !== unit.id || !resultOf(book.entries, child)) continue;
				const run = passingRunOf(book.entries, child, unit.anchor, repos, ctx.cwd);
				if (!run) continue;
				const ran = run.run.ts;
				const stale = findChildBooks(child).some(({ book: own }) => own.entries.some((entry) => entry.stage === "edit" && entry.ts > ran));
				const taken = book.entries.some((entry, index) => entry.stage === "verify" && entry.child === child && taskOfEntry(book.entries, index) === unit.id && entry.ran === ran);
				if (stale || taken) continue;
				const last = `adopted from ${run.name}${run.run.last ? `: ${String(run.run.last)}` : ""}`.slice(0, 200);
				const at = run.run.treeAt && typeof run.run.treeAt === "object" ? { treeAt: run.run.treeAt } : {};
				book.entries.push(appendEntry(book.path, "verify", { command: unit.anchor.slice(0, 200), exit: 0, last, adopted: run.name, child, task: unit.id, ran, ...at }));
			}
		}
	}

	/** Adopts a returned child's passing run: per unit in a loop of two or more units, else as the loop's verify. */
	function adoptRuns(book: Book, ctx: ExtensionContext): void {
		if (unitsOf(book.entries, todosOf(ctx)).units.length >= 2) adoptUnitRuns(book, ctx);
		else adoptChildRun(book, ctx.cwd);
	}

	/**
	 * Records what a finished bash call shows: runs of the loop anchor, of task anchors, and a first commit as the change.
	 * Returns the re-classification line when an anchor run of an unreviewed loop measured a reach no `kind` answer covers.
	 */
	function recordBash(book: Book, event: { input: unknown; isError?: boolean; structuredContent?: unknown; content?: unknown }, cwd: string): string | undefined {
		const structured = event.structuredContent as { output?: unknown } | undefined;
		const output = typeof structured?.output === "string" ? structured.output : textOf(event.content);
		const command = String((event.input as { command?: unknown }).command ?? "");
		const exit = bashExit(event);
		const last = lastLine(output);
		const anchor = anchorCommand(book.entries);
		const notices: string[] = [];
		// A failed run keeps its key line, so a rerun that passes can name what failed without the whole output.
		const keyOf = (code: unknown) => (typeof code === "number" && code !== 0 ? { key: keyLine(output) } : {});
		const inherited = parentAnchorNow();
		// Each run records the working tree of the repo it ran in (a leading `cd` moves it), and stands while that tree is unchanged.
		const trees = new Map<string, { treeAt?: Record<string, string> }>();
		const treeOf = (at: number) => {
			const repo = repoRootOf(join(ranIn(command, at, cwd), "_"));
			if (!repo) return {};
			if (!trees.has(repo)) trees.set(repo, treeAtField([repo]));
			return trees.get(repo) ?? {};
		};
		for (const own of [...new Set([anchor, inherited].filter((item): item is string => item !== undefined))]) {
			const run = anchorRun(command, own);
			if (!run) continue;
			// The parent's anchor, run from another directory, is another check.
			if (own !== anchor && cdsOutside(command.slice(0, run.at), loopRepos(book, cwd), cwd)) continue;
			const child = childId() !== undefined;
			const recorded = child || currentKind(book.entries) === "quick" ? "check" : "verify";
			const code = anchorExit(command, own, exit);
			const entry = appendEntry(book.path, recorded, { command: own.slice(0, 200), exit: code, last, ...keyOf(code), ...reachField(book, cwd), ...(child ? treesField(book, cwd) : {}), ...treeOf(run.at) });
			book.entries.push(entry);
			const reach = reachNotice(book, entry);
			if (reach) notices.push(reach);
		}
		for (const task of latestTasks(book.entries)) {
			const run = typeof task.anchor === "string" ? anchorRun(command, task.anchor) : undefined;
			if (typeof task.anchor !== "string" || !run) continue;
			const code = anchorExit(command, task.anchor, exit);
			book.entries.push(appendEntry(book.path, "taskrun", { id: task.id, command: task.anchor.slice(0, 200), exit: code, last, ...keyOf(code), ...treeOf(run.at) }));
		}
		autoFriction(book);
		const merged = mergeRun(command);
		if (exit === 0 && merged && !/Already up[ -]to[ -]date/i.test(last ?? "")) {
			if (book.entries.at(-1)?.stage !== "edit") {
				const dir = resolve(String(book.header.cwd ?? process.cwd()), merged.dir);
				touchRepoBeforeMerge(book, dir, merged.verb);
				const repo = repoRootOf(join(dir, "_"));
				book.entries.push(appendEntry(book.path, "edit", { via: "merge", ...(repo ? { repo } : {}) }));
			}
			adoptChildRun(book, cwd);
		}
		if (exit === 0 && /\bgit\b[^|;&]*\bcommit\b/.test(command) && !book.entries.some((entry) => entry.stage === "edit")) {
			const cwd = String(book.header.cwd ?? "");
			if (diffAgainstBases(book.entries).paths.some((path) => !outsideWork(path, cwd))) appendEntry(book.path, "edit", { via: "commit" });
		}
		return notices.join("\n") || undefined;
	}

	/**
	 * Records one friction line for each anchor that passed again after it had passed and then failed. A pair is recorded
	 * once, and not at all when the agent recorded a friction entry itself after the failure. The pairs one command
	 * completes in one bash call (it is both the loop and a task anchor) share one entry. No instruction owns such a slip, so
	 * the entry is reflected as `resolved` at once and the agent is told nothing.
	 */
	function autoFriction(book: Book): void {
		const open = new Map<string, string[]>();
		for (const pair of retryPairs(book.entries)) {
			const id = `${pair.key}#${pair.fail}`;
			const recorded = book.entries.some(
				(entry, index) =>
					entry.stage === "friction" && ((Array.isArray(entry.pairs) && entry.pairs.includes(id)) || (index > pair.fail && entry.auto !== true)),
			);
			if (recorded) continue;
			const command = String(book.entries[pair.fail].command ?? pair.key);
			open.set(command, [...(open.get(command) ?? []), id]);
		}
		for (const [command, pairs] of open) {
			// The newest failure speaks for the entry; an older pair it backfills is listed in `pairs`.
			const newest = pairs.at(-1) as string;
			const failed = book.entries[Number(newest.slice(newest.lastIndexOf("#") + 1))];
			const tried = clip(`rerun of ${command}`, 80);
			// A failure recorded before 2.4 has no key line; its last line gets the same filter.
			const found = clip(String(failed.key ?? keyLine(String(failed.last ?? ""))) || "failed with no output");
			const number = frictionOf(book.entries).length + 1;
			book.entries.push(appendEntry(book.path, "friction", { id: number, tried, found, led_by: "none", auto: true, pairs }));
			book.entries.push(appendEntry(book.path, "reflect", { friction: [String(number)], class: "resolved", action: "auto-recorded rerun" }));
		}
	}

	/**
	 * The line below the editor: the loop's kind, its last complete phase, the next one, and the friction still to reflect; cleared when
	 * no loop is open. It builds no working tree (a tree costs a second or more on a large repo): it reads the trees its event already
	 * read, and counts a run as standing where none was read, until `read` or the turn's end compares them.
	 */
	function showStatus(ctx: ExtensionContext): void {
		withTrees(() => statusLine(ctx), { build: false });
	}

	function statusLine(ctx: ExtensionContext): void {
		if (typeof ctx.ui?.setWidget !== "function") return;
		const book = openLoop(ctx);
		if (!book) {
			ctx.ui.setWidget(WIDGET_KEY, undefined);
			return;
		}
		const looped = computeLoop(book, { cwd: ctx.cwd, todos: todosOf(ctx) });
		const { phases } = looped;
		const open = allFriction(book.entries).filter((item) => !item.reflected).length;
		const kind = phases.kind === "undeclared" ? "no kind" : phases.kind;
		const at = `${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}`;
		const units = looped.rows.map(unitWidgetLine);
		ctx.ui.setWidget(WIDGET_KEY, [`⚓ ${kind} · ${at}${open ? ` · ${open} friction` : ""}`, ...units], { placement: "belowEditor" });
	}

	/**
	 * Records what a finished tool call shows; returns the tool result with any line the loop adds. A main session whose book another
	 * session resumed is told so on whatever tool result comes next, and that call records nothing in a loop that is no longer its own.
	 */
	function recordResult(event: ToolResultEvent, ctx: ExtensionContext) {
		const moved = childId() === undefined && !openLoop(ctx) ? movedNotice(ctx) : undefined;
		if (moved) {
			return { content: [...((event.content as unknown[]) ?? []), { type: "text", text: moved }], ...(event.structuredContent !== undefined ? { structuredContent: event.structuredContent } : {}) };
		}
		return recordOwnResult(event, ctx);
	}

	function recordOwnResult(event: ToolResultEvent, ctx: ExtensionContext) {
		if (event.toolName === "bash") {
			const book = openLoop(ctx) ?? (childId() !== undefined ? openChildFromBash(ctx, event) : undefined);
			const notice = book ? recordBash(book, event, ctx.cwd) : undefined;
			const before = tipsBefore.get(event.toolCallId);
			tipsBefore.delete(event.toolCallId);
			const remotes = remotesBefore.get(event.toolCallId);
			remotesBefore.delete(event.toolCallId);
			if (book && remotes) recordPushes(book, remotes, String((event.input as { command?: unknown }).command ?? ""), ctx);
			if (book) checkLandings(book, before);
			// The line only appends text, so the bash call's structured output passes on unchanged.
			return notice ? { content: [...((event.content as unknown[]) ?? []), { type: "text", text: notice }], structuredContent: event.structuredContent } : undefined;
		}
		if (event.isError) return;
		if (event.toolName === "todo") {
			const input = event.input as { action?: unknown; id?: unknown };
			let open = openLoop(ctx);
			let said: string | undefined;
			const resume = input.action === "create" ? (taskDetails(event.details) ?? []).map((task) => task.metadata?.resume).find((id): id is string => typeof id === "string" && id.trim() !== "") : undefined;
			// A todo's `resume` adopts the book whether or not an opening `kind` came first; a refusal is said, never dropped.
			if (resume !== undefined && open?.header.id !== resume) {
				const adopted = resumeBook(ctx, resume);
				if (adopted.refused) said = `anchorloop: resume refused: ${adopted.refused}${open ? "" : "; a new loop was opened instead, and `kind` with `resume` can still adopt the book while it holds no evidence"}.`;
				open = adopted.book ?? open;
			}
			if (!open && input.action === "create") open = openFromTodo(ctx, event.details);
			if (!open) return;
			recordTasks(open, event.details, input, ctx.cwd);
			return said ? { content: [...((event.content as unknown[]) ?? []), { type: "text", text: said }] } : undefined;
		}
		const book = openLoop(ctx);
		if (!book) return;
		if (event.toolName === "subagent") {
			const link = linkFrom(event.toolName, event.input, event.details);
			if (link) recordLink(book, link, ctx);
			return;
		}
		if (event.toolName === "subagent_send" || event.toolName === "subagent_resume") {
			recordSend(book, event.toolName, event.input, event.details, ctx);
			return;
		}
		if (event.toolName !== "write" && event.toolName !== "edit") return;
		const path = (event.input as { path?: unknown }).path;
		if (typeof path !== "string") return;
		if (!artifactKind(path)) {
			const target = resolve(ctx.cwd, path);
			// A file git ignores (a handoff note, a plan) is in no diff, so it is no change to the code.
			if (outsideWork(path, ctx.cwd) || ignoredByGit(target)) return;
			const repo = repoRootOf(target);
			const last = book.entries.at(-1);
			if (last?.stage !== "edit" || last.repo !== repo) appendEntry(book.path, "edit", { path, ...(repo ? { repo } : {}) });
			return;
		}
		let text: string;
		try {
			text = readFileSync(resolve(ctx.cwd, path), "utf-8");
		} catch {
			return;
		}
		const summary = summarizeArtifact(book.entries, path, text);
		if (summary) appendEntry(book.path, summary.stage, summary.fields);
	}

	// One reading of the working state per tool result: the footer after the recording reads the trees the recording built.
	pi.on("tool_result", (event, ctx) =>
		withTrees(() => {
			const out = guarded(recordResult)(event, ctx);
			guarded(showStatus)(ctx);
			return out;
		}),
	);

	/**
	 * Records a reviewer's verdict as a review round. It counts from the reviewer's dispatch (the latest `link` or `send` of that child
	 * before the result), with the trees that dispatch gave it, and for the unit its brief names by ticket, else the unit its child is bound to.
	 */
	async function recordReview(ctx: ExtensionContext, book: Book, result: { name: string; agent: string; task: string; resultContent: unknown; failed: boolean }, link: Entry | undefined): Promise<void> {
		const name = result.name || result.agent;
		const text = textOf(result.resultContent);
		const failed = result.failed;
		const child = link?.child;
		let dispatch: Entry | undefined;
		let sent: number | undefined;
		for (let i = book.entries.length - 1; i >= 0 && !dispatch; i--) {
			const entry = book.entries[i];
			if ((entry.stage === "link" || entry.stage === "send") && entry.child === child && child !== undefined) {
				dispatch = entry;
				// A `send` names the unit it went for, while that todo is still of the current list.
				if (entry.stage === "send") sent = taskOfEntry(book.entries, i);
			}
		}
		const todos = todosOf(ctx);
		const found = unitsOf(book.entries, todos);
		const brief = sent !== undefined ? undefined : result.task;
		const task = sent !== undefined ? sent : found.units.length >= 2 ? unitOfDispatch(found, todos, typeof child === "string" ? child : undefined, brief ?? "") : undefined;
		const trees = dispatch?.treeAt ? { treeAt: dispatch.treeAt } : dispatch ? {} : treeAtField(reviewedRepos(book, ctx.cwd));
		const counts = parseBlocking(text);
		let blocking: boolean | null = null;
		let source = `reviewer ${name}`;
		if (failed || /\bStatus:?\*{0,2}\s*INCOMPLETE\b/i.test(text)) {
			source = "failed";
		} else if (!counts) {
			source = "jev";
			const { answers } = await classify(ctx, { review: text.slice(-3000) }, {
				blocking: {
					type: "bool",
					instructions: "Does `review` report any blocking finding, a P0 or P1 defect that must be fixed before the change is merged?",
					criteria: { true: "the review names at least one defect it says must be fixed before merge", false: "the review finds no blocking defect, or only lower-priority notes" },
				},
			});
			const probability = answers?.blocking?.type === "bool" ? answers.blocking.probability : undefined;
			blocking = probability === undefined ? null : probability >= 0.5;
		} else {
			blocking = counts.p0 + counts.p1 > 0;
		}
		const entry = appendEntry(book.path, "review", {
			round: reviews(book.entries).length + 1,
			...(source === "failed" ? {} : (counts ?? {})),
			blocking,
			source,
			...(typeof child === "string" ? { child } : {}),
			...(dispatch ? { from: dispatch.ts } : {}),
			...(task !== undefined ? { task } : {}),
			...trees,
		});
		book.entries.push(entry);
		if (reviewsStalled(book.entries)) ctx.ui.notify("anchorloop: two consecutive review rounds still raised blocking findings; stop and hand the trend to the user.", "warning");
	}

	const HOST_LINE = /^\s*(Parent action:|Requested model|Session:|Resume:)/i;

/** The text without the lines pi-herdr adds around a subagent brief or result. */
function strip(text: string): string {
	return text
		.split("\n")
		.filter((line) => !HOST_LINE.test(line))
		.join("\n")
		.trim();
}

function headAndTail(text: string): string {
	return text.length <= 2500 ? text : `${text.slice(0, 1000)}\n…\n${text.slice(-1500)}`;
}

/** Jev judges whether a returned subagent was a fresh-context read of the spec; the spec path in its brief is only a pre-filter. */
	async function detectFreshRead(ctx: ExtensionContext, book: Book, details: { name?: unknown; task?: unknown; resultContent?: unknown }): Promise<void> {
		const phases = withTrees(() => phasesOf(book, ctx));
		const read = phases.statuses.find((status) => status.name === "read");
		if (read?.state !== "missing" || !read.note.startsWith("a fresh-context")) return;
		const folder = specFolder(book.entries, todosOf(ctx), ctx.cwd);
		const brief = String(details.task ?? "");
		if (!folder || !(brief.includes(`${folder}/spec.md`) || brief.includes(resolve(ctx.cwd, folder, "spec.md")))) return;
		const { answers } = await classify(ctx, { brief: strip(brief).slice(0, 1500), result: headAndTail(strip(textOf(details.resultContent))) }, {
			fresh_read: {
				type: "bool",
				instructions: "Did this subagent read the spec and report on it: does its `result` restate the spec, or list gaps, guesses, or questions about it? The `brief` only needs to have handed it the spec.",
				criteria: { true: "the result restates the spec or lists gaps, guesses, or questions about it", false: "the subagent did other work and its result does not report on the spec" },
			},
		});
		const probability = answers?.fresh_read?.type === "bool" ? answers.fresh_read.probability : undefined;
		if (probability === undefined) return;
		appendEntry(book.path, "goldfish", { source: "jev", ok: probability >= 0.5, child: String(details.name ?? "") });
	}

	pi.on(
		"message_end",
		guarded(async (event, ctx) => {
			const message = event.message as { role?: string; content?: unknown; customType?: string; details?: unknown };
			const book = openLoop(ctx);
			if (!book) return;
			const stated = statedAnchor(message);
			if (stated && !book.entries.some((entry) => entry.stage === "anchor" && entry.check === stated)) {
				appendEntry(book.path, "anchor", { check: stated, line: true });
				showStatus(ctx);
			}
			const result = resultFrom(message);
			if (!result) return;
			// A subagent session reads only its own reviewers' results: their verdicts are its review rounds; the rest its parent judges.
			if (subagent && !REVIEWERS.has(result.agent)) return;
			const handoff = result.handoff;
			const link = linkOfResult(book.entries, result);
			book.entries.push(appendEntry(book.path, "result", {
				...(link?.child ? { child: link.child } : {}),
				name: result.name,
				failed: result.failed,
				...(result.sessionFile ? { sessionFile: result.sessionFile } : {}),
				...(handoff?.headSha ? { headSha: handoff.headSha } : {}),
				...(handoff?.commitsAhead !== undefined ? { commitsAhead: handoff.commitsAhead } : {}),
				...(handoff?.changedFiles ? { changedFiles: handoff.changedFiles.slice(0, 50) } : {}),
			}));
			if (!subagent) {
				withTrees(() => {
					checkLandings(book);
					adoptRuns(book, ctx);
				});
			}
			if (REVIEWERS.has(result.agent)) await recordReview(ctx, book, result, link);
			else await detectFreshRead(ctx, book, result);
		}),
	);
}
