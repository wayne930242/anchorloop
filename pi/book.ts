/**
 * pi extension: the loop book. The first `todo` create opens a loop and its book as `inline`, its intent the first todo's subject
 * and its anchor a stated `Reality anchor:` line or the todo's `metadata.anchor`; a `kind` declaration opens one too. The agent declares only
 * what the program cannot observe (`kind` to choose `reviewed` or `durable`, a non-command `verify`,
 * `fresh-read`, `friction`, `reflect`, `skip`, `back`, `close`); the extension derives the rest from
 * evidence: production edits, the exit code of the anchor command, reviewer results, durable artifacts,
 * and the fresh-reader subagent. A phase machine over that evidence warns once per jump and never blocks;
 * only `close` refuses, while a todo is neither done nor disposed of.
 */

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
	type Book,
	type Entry,
	KINDS,
	allFriction,
	anchorCommand,
	appendEntry,
	artifactKind,
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
	guarded,
	isOpenTask,
	latestTasks,
	openLoop,
	replayTodos,
	refsOf,
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
	sweep,
	touchRepo,
	touchRepoBeforeMerge,
	validFollowup,
	verifyAfterLastAct,
} from "./support/book.ts";
import { classify } from "./support/jev.ts";
import { REVIEWLESS, SEQUENCES, computePhases, describe, incompleteBefore, outsideWork, reachLine, reachOf, unansweredReach } from "./support/phases.ts";
import { type Snapshot, snapshot } from "./support/snapshot.ts";
import { isSubagent } from "./support/subagent.ts";

export const SESSION_ENTRY = "anchorloop-loop";
const STAGES = ["kind", "verify", "fresh-read", "friction", "reflect", "skip", "back", "close", "read"] as const;
const REVIEWERS = new Set(["reviewer", "adversarial-reviewer"]);
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
};

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

/** The text a `Reality anchor:` line states in an assistant message, if any. */
function statedAnchor(message: { role?: string; content?: unknown } | undefined): string | undefined {
	if (message?.role !== "assistant") return undefined;
	const found = ANCHOR_LINE.exec(textOf(message.content));
	return found ? found[1].trim().slice(0, 300) || "(stated on the next line)" : undefined;
}

const WIDGET_KEY = "anchorloop";

const reply = (text: string) => ({ content: [{ type: "text" as const, text }], details: undefined });

export default function (pi: ExtensionAPI) {
	const subagent = isSubagent();
	function todosOf(ctx: ExtensionContext) {
		return replayTodos(ctx.sessionManager.getBranch());
	}

	function phasesOf(book: Book, ctx: ExtensionContext) {
		return computePhases(book, { cwd: ctx.cwd, todos: todosOf(ctx) });
	}

	/** The line that tells the agent Jev did not accept a returned subagent as the fresh read, while the read is still open. */
	function freshReadLine(book: Book, phases: ReturnType<typeof phasesOf>): string[] {
		const last = [...book.entries].reverse().find((entry) => entry.stage === "goldfish");
		const open = phases.statuses.find((status) => status.name === "read")?.state === "missing";
		return open && last?.source === "jev" && last.ok === false ? [`fresh read by ${String(last.child || "a subagent")} judged not fresh — declare \`fresh-read\` if it was`] : [];
	}

	function summaryLines(book: Book, ctx: ExtensionContext): string[] {
		const phases = phasesOf(book, ctx);
		const verify = [...book.entries].reverse().find((entry) => entry.stage === "verify" || entry.stage === "check");
		const open = todosOf(ctx).filter(isOpenTask).length;
		const friction = allFriction(book.entries);
		return [
			describe(phases),
			`intent: ${currentIntent(book.entries) ?? "not declared"}`,
			`last ${verify?.stage ?? "verify"}: ${verify ? `${verify.declared ? `declared ${verify.result}` : `exit ${verify.exit ?? "unknown"}`}${verify.last ? ` — ${verify.last}` : ""}${verifyAfterLastAct(book.entries) ? "" : " (before the last change)"}` : "none"}`,
			`reviews: ${reviewTrend(book.entries)}; open todos: ${open}; friction: ${friction.length} (${friction.filter((item) => !item.reflected).length} unreflected)`,
			...childLines(book.entries).map((line) => `child ${line}`),
			...friction.filter((item) => item.owner !== "main").map((item) => `friction ${item.ref}: ${item.tried} → ${item.found}${item.reflected ? ` [${item.class}]` : ""}`),
			...freshReadLine(book, phases),
		];
	}

	function recordTasks(book: Book, details: unknown, input: { action?: unknown; id?: unknown }, cwd: string): void {
		const tasks = taskDetails(details) ?? [];
		const known = new Set(latestTasks(book.entries).map((entry) => entry.id));
		const touched = input.action === "create" ? tasks.filter((task) => !known.has(task.id)) : tasks.filter((task) => task.id === Number(input.id));
		for (const task of touched) {
			const refs = refsOf(task.metadata).map((ref) => ({ ref, range: resolveRef(ref, cwd, book.entries) }));
			const { anchor, followup } = task.metadata ?? {};
			book.entries.push(
				appendEntry(book.path, "task", {
					id: task.id,
					subject: task.subject,
					status: task.status,
					...(typeof anchor === "string" ? { anchor } : {}),
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

	/** True while no `kind` call has chosen the kind: the loop still holds the `inline` a todo create opened it with. */
	function kindIsDefault(entries: Entry[]): boolean {
		return !entries.some((entry) => entry.stage === "kind" && typeof entry.kind === "string" && entry.auto !== true);
	}

	/** Opens the loop at the first todo create as `inline`: the first todo's subject is the intent, a stated `Reality anchor:` line or its `metadata.anchor` the anchor. */
	function openFromTodo(ctx: ExtensionContext, details: unknown): Book {
		const book = createBook(ctx);
		touchRepo(book, join(ctx.cwd, "_"));
		const first = (taskDetails(details) ?? [])[0];
		book.entries.push(appendEntry(book.path, "kind", { kind: "inline", auto: true, ...(first?.subject ? { intent: clip(first.subject.replace(/\s+/g, " ").trim(), 200) } : {}) }));
		recordPriorAnchor(book, ctx);
		const anchor = first?.metadata?.anchor;
		if (typeof anchor === "string" && anchor.trim() && !anchorCommand(book.entries)) book.entries.push(appendEntry(book.path, "anchor", { check: anchor.trim() }));
		return book;
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
		const phases = phasesOf(book, ctx);
		const missing = incompleteBefore(phases, "close");
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
		for (const id of childIds(book.entries)) {
			for (const { book: child } of findChildBooks(id)) deleteBook(child.path);
		}
		deleteBook(book.path);
		return { text: `${text} Clear the todo list.`, snapshot: snap };
	}

	pi.registerTool({
		name: "anchorloop_stage",
		label: "Loop stage",
		description:
			"Loop book; the first `todo` create opens a loop as inline. stage: kind (kind, intent, anchor; reason to change the kind or answer a reach notice), verify (note; only for a check not run in bash), fresh-read, friction (tried, found, led_by), reflect (friction ids, class, action), skip/back (phase, reason), close (verdict; refuses while an open todo lacks metadata.followup), read. Edits, anchor runs, reviews, and specs are read from evidence.",
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
				led_by: { type: "string", description: "the instruction that misled the attempt, or `none`" },
				friction: { type: "array", items: { type: ["string", "number"] }, description: "ids: `3`, `worker#2`" },
				class: { type: "string", enum: ["misdirection", "gap", "resolved"] },
				action: { type: "string" },
				phase: { type: "string" },
				reason: { type: "string" },
				verdict: { type: "string", enum: ["landed", "blocked", "abandoned"] },
				view: { type: "string", enum: ["summary", "all"] },
			},
			required: ["stage"],
			additionalProperties: false,
		},
		async execute(toolCallId: string, raw: unknown, signal: unknown, onUpdate: unknown, ctx: ExtensionContext) {
			try {
				return await stageTool(toolCallId, raw, signal, onUpdate, ctx);
			} finally {
				guarded(showStatus)(ctx);
			}
		},
	});

	async function stageTool(_toolCallId: string, raw: unknown, _signal: unknown, _onUpdate: unknown, ctx: ExtensionContext) {
		const params = raw as Params;
		const { stage } = params;
		if (!(STAGES as readonly string[]).includes(stage)) throw new Error(`unknown stage \`${String(stage)}\`; declare one of ${STAGES.join(", ")}`);
		let book = openLoop(ctx);
		if (!book && stage === "kind") {
			// A todo create in the same batch may not have landed yet; whichever comes first opens the loop.
			if (!params.kind || !params.intent) throw new Error("the first kind declaration needs `kind` and a one-line `intent`");
			book = createBook(ctx);
			recordPriorAnchor(book, ctx);
		}
		if (!book) return reply("No loop is open, so nothing was recorded. A loop opens with the first `todo` create or `kind`.");
		const had = currentKind(book.entries);
		const sequence = SEQUENCES[had ?? "inline"];
		if (stage === "read") {
			const lines = [...summaryLines(book, ctx), ...taskLines(book.entries, todosOf(ctx), ctx.cwd)];
			if (params.view === "all") lines.push("entries:", ...book.entries.map((entry) => JSON.stringify(entry).slice(0, 300)));
			return reply(lines.join("\n"));
		}
		if (stage === "close") {
			if (!params.verdict) throw new Error("close needs a verdict: landed, blocked, or abandoned");
			const closed = close(book, ctx, params.verdict);
			return { content: [{ type: "text" as const, text: closed.text }], details: closed.snapshot ? { snapshot: closed.snapshot } : undefined };
		}
		if (stage === "kind") {
			if (!params.kind && !params.intent && !params.anchor && !params.reason) throw new Error("kind needs `kind`, `intent`, `anchor`, or `reason`");
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
			return reply("ok");
		}
		if (stage === "verify") {
			if (!params.note) throw new Error("verify needs a `note` saying what was observed");
			const result = params.result ?? "pass";
			const recorded = childId() !== undefined || had === "quick" ? "check" : "verify";
			const entry = appendEntry(book.path, recorded, { declared: true, note: params.note, result, exit: result === "pass" ? 0 : 1, ...reachField(book, ctx.cwd) });
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
		// skip and back
		const phase = params.phase;
		const known = sequence.filter((name) => name !== "close");
		if (!phase || !known.includes(phase)) throw new Error(`${stage} needs \`phase\`, one of ${known.join(", ")} for a ${had ?? "undeclared"} loop`);
		if (!params.reason) throw new Error(`${stage} needs a \`reason\``);
		appendEntry(book.path, stage, { phase, reason: params.reason });
		return reply("ok");
	}

	pi.on(
		"session_start",
		guarded((_event, ctx) => {
			const swept = sweep(process.env, ctx.cwd);
			const lines = [
				...swept.deleted.map((path) => `deleted stale loop book: ${path}`),
				...swept.open.map((path) => `open loop book: ${path}`),
			];
			if (lines.length > 0) ctx.ui.notify(`anchorloop books\n${lines.join("\n")}`, "info");
			showStatus(ctx);
		}),
	);

	pi.on(
		"tool_call",
		guarded((event, ctx) => {
			if (event.toolName !== "write" && event.toolName !== "edit") return;
			const path = (event.input as { path?: unknown }).path;
			const book = typeof path === "string" ? openLoop(ctx) : undefined;
			if (book && typeof path === "string") touchRepo(book, resolve(ctx.cwd, path));
		}),
	);

	/** The reach of an unreviewed loop's diff, recorded on its verify or check entry; a reviewed loop is never measured. */
	function reachField(book: Book, cwd: string): { reach?: ReturnType<typeof reachOf> } {
		return REVIEWLESS.has(currentKind(book.entries) ?? "inline") ? { reach: reachOf(book.entries, cwd) } : {};
	}

	/** The line that asks the loop to re-classify after a verify or check entry whose reach no `kind` answer covers. */
	function reachNotice(book: Book, entry: Entry): string | undefined {
		const reach = entry.reach as ReturnType<typeof reachOf> | undefined;
		return reach && unansweredReach(book.entries, reach).length > 0 ? `anchorloop: ${reachLine(reach, currentKind(book.entries))}.` : undefined;
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
		if (anchor && anchorRun(command, anchor)) {
			const recorded = childId() !== undefined || currentKind(book.entries) === "quick" ? "check" : "verify";
			const code = anchorExit(command, anchor, exit);
			const entry = appendEntry(book.path, recorded, { command: anchor.slice(0, 200), exit: code, last, ...keyOf(code), ...reachField(book, cwd) });
			book.entries.push(entry);
			const reach = reachNotice(book, entry);
			if (reach) notices.push(reach);
		}
		for (const task of latestTasks(book.entries)) {
			if (typeof task.anchor !== "string" || !anchorRun(command, task.anchor)) continue;
			const code = anchorExit(command, task.anchor, exit);
			book.entries.push(appendEntry(book.path, "taskrun", { id: task.id, command: task.anchor.slice(0, 200), exit: code, last, ...keyOf(code) }));
		}
		autoFriction(book);
		const merged = mergeRun(command);
		if (exit === 0 && merged && !/Already up[ -]to[ -]date/i.test(last ?? "") && book.entries.at(-1)?.stage !== "edit") {
			touchRepoBeforeMerge(book, resolve(String(book.header.cwd ?? process.cwd()), merged.dir), merged.verb);
			book.entries.push(appendEntry(book.path, "edit", { via: "merge" }));
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

	/** The line below the editor: the loop's kind, its last complete phase, the next one, and the friction still to reflect; cleared when no loop is open. */
	function showStatus(ctx: ExtensionContext): void {
		if (typeof ctx.ui?.setWidget !== "function") return;
		const book = openLoop(ctx);
		if (!book) {
			ctx.ui.setWidget(WIDGET_KEY, undefined);
			return;
		}
		const phases = phasesOf(book, ctx);
		const open = allFriction(book.entries).filter((item) => !item.reflected).length;
		const kind = phases.kind === "undeclared" ? "no kind" : phases.kind;
		const at = `${phases.current}${phases.current === "start" ? "" : " ✓"} → ${phases.next}`;
		ctx.ui.setWidget(WIDGET_KEY, [`⚓ ${kind} · ${at}${open ? ` · ${open} friction` : ""}`], { placement: "belowEditor" });
	}

	pi.on(
		"tool_result",
		guarded((event, ctx) => {
			if (event.toolName === "bash") {
				const book = openLoop(ctx);
				const notice = book ? recordBash(book, event, ctx.cwd) : undefined;
				// The line only appends text, so the bash call's structured output passes on unchanged.
				return notice ? { content: [...((event.content as unknown[]) ?? []), { type: "text", text: notice }], structuredContent: event.structuredContent } : undefined;
			}
			if (event.isError) return;
			if (event.toolName === "todo") {
				const input = event.input as { action?: unknown; id?: unknown };
				let open = openLoop(ctx);
				if (!open && input.action === "create") open = openFromTodo(ctx, event.details);
				if (!open) return;
				recordTasks(open, event.details, input, ctx.cwd);
				return;
			}
			const book = openLoop(ctx);
			if (!book) return;
			if (event.toolName === "subagent") {
				const id = (event.details as { id?: unknown } | undefined)?.id;
				if (typeof id === "string") {
					const details = event.details as { name?: unknown; agent?: unknown };
					appendEntry(book.path, "link", { child: id, name: details.name, agent: details.agent });
				}
				return;
			}
			if (event.toolName !== "write" && event.toolName !== "edit") return;
			const path = (event.input as { path?: unknown }).path;
			if (typeof path !== "string") return;
			if (!artifactKind(path)) {
				if (!outsideWork(path, ctx.cwd) && book.entries.at(-1)?.stage !== "edit") appendEntry(book.path, "edit", { path });
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
		}),
	);

	// Registered after the recording handler, so the footer reads what that tool call just recorded.
	pi.on(
		"tool_result",
		guarded((_event, ctx) => {
			showStatus(ctx);
		}),
	);

	async function recordReview(ctx: ExtensionContext, book: Book, name: string, text: string, failed: boolean): Promise<void> {
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
		const entry = appendEntry(book.path, "review", { round: reviews(book.entries).length + 1, ...(source === "failed" ? {} : (counts ?? {})), blocking, source });
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
		const phases = phasesOf(book, ctx);
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
			const message = event.message as { role?: string; content?: unknown; customType?: string; details?: { agent?: unknown; name?: unknown; task?: unknown; resultContent?: unknown; error?: unknown; errorMessage?: unknown; exitCode?: unknown } };
			const book = openLoop(ctx);
			if (!book) return;
			const stated = statedAnchor(message);
			if (stated && !book.entries.some((entry) => entry.stage === "anchor" && entry.check === stated)) {
				appendEntry(book.path, "anchor", { check: stated, line: true });
				showStatus(ctx);
			}
			if (message.role !== "custom" || message.customType !== "subagent_result" || subagent) return;
			const agent = String(message.details?.agent ?? "");
			if (REVIEWERS.has(agent)) {
				const d = message.details ?? {};
				const failed = Boolean(d.error) || Boolean(d.errorMessage) || (typeof d.exitCode === "number" && d.exitCode !== 0);
				await recordReview(ctx, book, String(d.name ?? agent), textOf(d.resultContent), failed);
			}
			else await detectFreshRead(ctx, book, message.details ?? {});
		}),
	);
}
