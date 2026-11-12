/**
 * pi extension: inside an open loop, asks Jev to check the phase machine's reading of the loop book. The
 * program computes the next phase from the book's evidence; Jev sees the kind, intent, anchor, diff
 * summary, phase (current, next, missing), verify state, open todos, tasks, and friction, and judges only
 * whether the current phase's completion condition truly holds and whether to advance, go back, or ask
 * the user. It runs when a run settles and the book gained an evidence entry (not a task, link, or watch record) since the last judgment, and at a
 * `close` declaration. The advisory is `next: <phase> (<missing>)` plus Jev's concerns, and is sent only when it
 * changes the agent's next action: Jev has a concern, todos are still open without a followup, or the run
 * continues. It continues the run once when Jev agrees to advance and the next phase is a verify, review, or
 * fix, or when todos are still open without a followup (unless Jev says to ask the user). Away from close the
 * advisory names up to three of those todos and asks the agent to continue, complete, or settle each with
 * `metadata.followup`. An advisory with the same next phase, assessment findings, and open todo ids, and Jev's move is sent once. At
 * close only concerns are sent. A run that arranged a wake (a monitor, a loop, a goal wait, or a subagent call whose child the book has
 * not linked yet) is waiting, not finished, and is not judged. A loop whose child has no result is quiet; in a loop of two or more units
 * the quiet is per unit: the notice judges, speaks, and continues for the first unit that waits on the coordinator (started, not done,
 * nothing of its own out) whose step it has not asked since that unit's last evidence, and names every other such unit on its own line.
 * What the notice asked is kept in the book (`notice` entries), so a `/reload` or a new session that adopts the book does not ask again.
 * Outside a loop nothing runs, nor in a `quick` loop, whose only prompt is the close reminder; a subagent session registers nothing,
 * since the agent that spawned it judges its result.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { type Book, type Entry, appendEntry, currentKind, guarded, isOpenTask, openLoop, replayTodos, validFollowup, withChildActs } from "./support/book.ts";
import { checkLandings } from "./support/landing.ts";
import { type UnitRow, type Units, computeLoop, outDispatches, unitEntries } from "./support/units.ts";
import { type Answers, classify } from "./support/jev.ts";
import { type Snapshot, listTodos, snapshot } from "./support/snapshot.ts";
import { isSubagent } from "./support/subagent.ts";

export { isSubagent, snapshot };
export type { Snapshot };

export const ENTRY_TYPE = "anchorloop-second-thought";
const WAIT_TOOLS = new Set(["MonitorCreate", "LoopCreate", "goal_wait"]);
// A subagent call waits until its result tells the book which child went out; from then on the book's links say which unit waits.
const SUBAGENT_TOOLS = new Set(["subagent", "subagent_resume", "subagent_send"]);

export const THRESHOLDS = { doneBelow: 0.25, qualityBelow: 1.5, reviewTier: "full" };

export const MOVES = ["advance", "back", "ask-user"] as const;
export type Move = (typeof MOVES)[number];

/** The phases whose missing evidence the agent can supply by acting, so Jev's agreement continues the run. */
const ACTIONABLE = new Set(["verify", "check", "review", "fix"]);

export const QUESTIONS = {
	move: {
		type: "choice" as const,
		instructions:
			"The program computed `phase` from the loop book: the last complete phase, the next one, and what the next lacks. Given `kind`, `intent`, `anchor`, `diff`, `verify` (check evidence and reviews), `todos`, `tasks`, and `friction`, should the agent move on to the next phase, go back because the evidence of an earlier phase does not hold, or ask the user?",
		criteria: {
			advance: "the recorded evidence supports the last complete phase and the next phase can proceed",
			back: "evidence recorded for an earlier phase is wrong, stale, or contradicted by a later result",
			"ask-user": "a decision or judgment that belongs to the user blocks progress",
		},
	},
	done: {
		type: "bool" as const,
		instructions: "Does the `verify` evidence show, with observed results, that `intent` is fully met?",
		criteria: {
			true: "every part of the intent has observed evidence: command output, a test result, a review verdict, or an artifact",
			false: "some part failed, was skipped, is left for later, or rests only on a claim",
		},
	},
	review: {
		type: "choice" as const,
		instructions: "What review should the `diff` still get before it is merged or released, given the reviews recorded in `verify`?",
		criteria: {
			none: "trivial, fully covered by a passing check, or already reviewed with no blocking finding",
			focused: "one independent reviewer on the changed lines",
			full: "independent review plus an adversarial pass: security, data, permissions, migration, or a shared contract",
		},
	},
	quality: {
		type: "score" as const,
		instructions: "How acceptable is the work recorded in the loop against its `intent`?",
		criteria: [
			"unacceptable: wrong or broken",
			"weak: works but misses requirements",
			"acceptable: meets the intent",
			"strong: meets it with direct evidence and no excess",
		],
	},
};

export type Verdict = { move: Move; done: number; review: string; reviewProbability: number; quality: number };

export function readVerdict(answers: Answers): Verdict | undefined {
	const { move, done, review, quality } = answers;
	if (move?.type !== "choice" || done?.type !== "bool" || review?.type !== "choice" || quality?.type !== "score") return undefined;
	if (!(MOVES as readonly string[]).includes(move.choice ?? "")) return undefined;
	const choice = review.choice ?? "";
	return {
		move: move.choice as Move,
		done: done.probability ?? 0,
		review: choice,
		reviewProbability: review.probabilities?.[choice] ?? 0,
		quality: quality.score ?? 0,
	};
}

export function assess(verdict: Verdict, snap: Snapshot): { found: string[] } {
	const found: string[] = [];
	if (verdict.done < THRESHOLDS.doneBelow) found.push("evidence not shown to cover the intent");
	// A review recorded after the last change with no blocking finding already covers the full-review rating.
	if (verdict.review === THRESHOLDS.reviewTier && !snap.reviewClear) found.push("needs full independent review");
	if (verdict.quality < THRESHOLDS.qualityBelow) found.push("result below the intent");
	return { found };
}

/** True when Jev agrees to advance and the next phase is one the agent can act on now, or open todos wait and the user is not needed. */
export function continues(verdict: Verdict, snap: Snapshot): boolean {
	if (snap.unsettled.length && verdict.move !== "ask-user") return true;
	return verdict.move === "advance" && ACTIONABLE.has(snap.next);
}

/** What Jev's move adds to the program's reading when it is not "advance". */
const MOVE_CONCERN: Record<Move, string | undefined> = { advance: undefined, back: "earlier evidence does not hold", "ask-user": "needs the user's decision" };

/** Jev's concerns: a move against the program's reading, then the assessment findings. */
export function concerns(verdict: Verdict, found: string[]): string[] {
	const move = MOVE_CONCERN[verdict.move];
	return move ? [move, ...found] : found;
}

/** The open todos the agent must answer, or the call to put them to the user. */
function todoCall(verdict: Verdict, snap: Snapshot): string {
	const list = `open: ${listTodos(snap.unsettled)}`;
	return verdict.move === "ask-user"
		? `${list} — ask the user about them with ask_user_question before ending the turn`
		: `${list} — continue each, complete it, or set metadata.followup (a ticket id, \`memory\`, or \`drop — <reason>\`)`;
}

/** The advisory: the program's next phase and its gap, Jev's concerns, and, away from close, the open todos. Empty at close without concerns. */
export function message(verdict: Verdict, snap: Snapshot, found: string[], atClose = false, others: string[] = []): string {
	const list = concerns(verdict, found);
	if (atClose) return list.length ? `Jev: ${list.join("; ")}.` : "";
	return [
		`next: ${snap.unit ? `${snap.unit.label} ` : ""}${snap.next}${snap.missing ? ` (${snap.missing})` : ""}`,
		...others.map((line) => `next: ${line}`),
		...(list.length ? [`concerns: ${list.join("; ")}`] : []),
		...(snap.unsettled.length ? [todoCall(verdict, snap)] : []),
	].join("\n");
}

/**
 * What makes two advisories the same: Jev's move, the next phase, the assessment findings, and the open todo ids; the wording of the gap
 * may change. The move stays in, so a turn to `back` or `ask-user` on new evidence is never taken for the advisory already sent. A book
 * is judged again only when it holds new evidence, which keeps an unchanged state from flapping between moves.
 */
function adviceKey(verdict: Verdict, snap: Snapshot, found: string[]): string {
	return JSON.stringify([verdict.move, snap.next, found, snap.unsettled.map((task) => task.id)]);
}

// Entries that say something new about the work; a child's result (a failed one too) is news of its unit. Task, link, base, and watch
// entries change with every todo or spawn.
const EVIDENCE = new Set(["edit", "land", "verify", "check", "review", "result", "decision", "spec", "design", "verification", "friction", "reflect", "skip", "back", "anchor", "observe", "kind", "goldfish", "taskrun"]);
const evidenceCount = (entries: { stage: string }[]): number => entries.filter((entry) => EVIDENCE.has(entry.stage)).length;

/** The memory key of the loop as one unit; a unit of a loop of two or more is keyed by its todo id. */
const LOOP = "loop";

/** What the notice last recorded for `unit` in the book: the latest `notice` entry, and the latest one that carried the advisory sent. */
function memory(book: Book, unit: string | number): { judged?: Entry; told?: string } {
	const own = book.entries.filter((entry) => entry.stage === "notice" && entry.unit === unit);
	const told = [...own].reverse().find((entry) => typeof entry.told === "string");
	return { judged: own.at(-1), ...(told ? { told: String(told.told) } : {}) };
}

function remember(book: Book, fields: Record<string, unknown>): void {
	book.entries.push(appendEntry(book.path, "notice", fields));
}

/** A unit's own evidence: the entries that belong to it (its children's edits and results included) that say something new. */
function unitEvidence(book: Book, row: UnitRow, found: Units): number {
	return evidenceCount(withChildActs(unitEntries(book.entries, row.unit, found)));
}

/** True when the coordinator has taken the unit up: a child works or worked for it, or a change of its own is in the book. */
function started(book: Book, row: UnitRow, found: Units): boolean {
	return [...found.bound.values()].includes(row.unit.id) || unitEntries(book.entries, row.unit, found).some((entry) => entry.stage === "edit" || entry.stage === "land");
}

export default function (pi: ExtensionAPI) {
	if (isSubagent()) return;
	let waiting = false;
	let continued = false;
	// Subagent calls of this run whose result has not come yet, by call id.
	const unlinked = new Set<string>();
	// A close deletes its book, so what Jev needs is read when the call starts.
	const closing = new Map<string, Snapshot>();

	// What the notice judged and said lives in the book, so a session start has nothing in memory to rebuild or lose.
	pi.on("session_start", () => {
		closing.clear();
		unlinked.clear();
	});

	pi.on("agent_settled", () => {
		waiting = false;
		continued = false;
		unlinked.clear();
	});

	pi.on(
		"tool_call",
		guarded((event, ctx) => {
			if (WAIT_TOOLS.has(event.toolName)) waiting = true;
			if (SUBAGENT_TOOLS.has(event.toolName)) unlinked.add(event.toolCallId);
			if (event.toolName !== "anchorloop_stage" || (event.input as { stage?: unknown }).stage !== "close") return;
			const book = openLoop(ctx);
			if (book && currentKind(book.entries) !== "quick") closing.set(event.toolCallId, snapshot(book, ctx));
		}),
	);

	async function judge(ctx: Parameters<typeof classify>[0], snap: Snapshot) {
		const { answers, reason } = await classify(ctx, snap.state, QUESTIONS);
		if (reason === "no-auth") return undefined;
		return { verdict: answers ? readVerdict(answers) : undefined, reason };
	}

	pi.on(
		"tool_result",
		guarded(async (event, ctx) => {
			unlinked.delete(event.toolCallId);
			const called = closing.get(event.toolCallId);
			if (called) closing.delete(event.toolCallId);
			if (event.isError) return;
			// The close tool reports the loop as it stood when it closed, after any reflect that ran beside it.
			const snap = (event.details as { snapshot?: Snapshot } | undefined)?.snapshot ?? called;
			if (!snap) return;
			const judgment = await judge(ctx, snap);
			if (!judgment?.verdict) return;
			const { found } = assess(judgment.verdict, snap);
			pi.appendEntry(ENTRY_TYPE, { ...judgment.verdict, at: "close", concerns: found });
			const text = message(judgment.verdict, snap, found, true);
			return text ? { content: [...event.content, { type: "text" as const, text: `\n${text}` }] } : undefined;
		}),
	);

	type Judgment = NonNullable<Awaited<ReturnType<typeof judge>>>;

	/** The settle result for a judgment: the verdict entry, and the advisory when it changes the agent's next action and was not sent already. */
	function settleWith(earlier: unknown[], judgment: Judgment, snap: Snapshot, sent: { told?: string; others?: string[]; onSpeak?: (key: string) => void }) {
		const record = (data: Record<string, unknown>) => ({ type: "custom" as const, customType: ENTRY_TYPE, data });
		if (!judgment.verdict) return { entries: [...earlier, record({ verdict: "unknown", reason: judgment.reason })] };
		const { found } = assess(judgment.verdict, snap);
		const verdictEntry = record({ ...judgment.verdict, concerns: found, ...(snap.unit ? { unit: snap.unit.label } : {}) });
		const proceed = !continued && continues(judgment.verdict, snap);
		// Jev agrees and nothing needs the agent: the verdict is recorded and nothing is said.
		const speaks = proceed || snap.unsettled.length > 0 || concerns(judgment.verdict, found).length > 0;
		const key = adviceKey(judgment.verdict, snap, found);
		if (!speaks || sent.told === key) return { entries: [...earlier, verdictEntry] };
		sent.onSpeak?.(key);
		if (proceed) continued = true;
		return {
			entries: [...earlier, verdictEntry, { type: "custom_message" as const, customType: ENTRY_TYPE, content: message(judgment.verdict, snap, found, false, sent.others), display: true }],
			...(proceed ? { continue: true } : {}),
		};
	}

	pi.on(
		"agent_before_settle",
		guarded(async (event, ctx) => {
			if (waiting || unlinked.size > 0 || event.outcome !== "completed") return;
			const book = openLoop(ctx);
			// A quick loop has no prompts but the close reminder.
			if (!book || currentKind(book.entries) === "quick") return;
			// A ref may have moved since the last tool call; record that landing before the entries are counted.
			checkLandings(book);
			// A later handler's boundary result replaces the entries an earlier one returned, so carry them along.
			const earlier = event.entries ?? [];
			const todos = replayTodos(ctx.sessionManager.getBranch());
			const looped = computeLoop(book, { cwd: ctx.cwd, todos });
			const out = outDispatches(book.entries, looped.found);
			// A child out for the whole loop (bound to no unit) keeps every unit quiet; one out for a unit keeps only that unit quiet.
			if (out.some((dispatch) => dispatch.task === undefined)) return;
			if (looped.rows.length > 0) {
				const busy = new Set(out.map((dispatch) => dispatch.task));
				const owed = looped.rows.filter((row) => row.unit.open && row.phases.next !== "close" && !busy.has(row.unit.id) && started(book, row, looped.found));
				const fresh = owed
					.map((row) => ({ row, step: row.phases.next, evidence: unitEvidence(book, row, looped.found) }))
					.filter(({ row, step, evidence }) => {
						const last = memory(book, row.unit.id).judged;
						return last === undefined || last.step !== step || last.evidence !== evidence;
					});
				if (fresh.length > 0) {
					const [first, ...rest] = fresh;
					remember(book, { unit: first.row.unit.id, step: first.step, evidence: first.evidence });
					const snap = snapshot(book, ctx, first.row.unit.id);
					const judgment = await judge(ctx, snap);
					if (!judgment) return;
					const others = rest.map(({ row }) => `${row.unit.label} ${row.phases.next}${row.phases.missing ? ` (${row.phases.missing})` : ""}`);
					// The other units the advisory names on their own lines are asked too.
					return settleWith(earlier, judgment, snap, { others, onSpeak: () => rest.forEach(({ row, step, evidence }) => remember(book, { unit: row.unit.id, step, evidence })) });
				}
				// Nothing waits on the coordinator: the units wait on their children or were not started. Once every unit is done, the loop is judged whole.
				if (looped.rows.some((row) => row.unit.open && row.phases.next !== "close")) return;
			}
			// A book is judged again on new evidence or on an open todo that needs an answer and was not there last time; a status flip alone is neither.
			const evidence = evidenceCount(book.entries);
			const open = todos.filter((task) => isOpenTask(task) && !validFollowup(task.metadata?.followup)).map((task) => task.id);
			const { judged, told } = memory(book, LOOP);
			const before = { evidence: Number(judged?.evidence ?? 0), open: Array.isArray(judged?.open) ? (judged.open as number[]) : [] };
			if (evidence <= before.evidence && open.every((todo) => before.open.includes(todo))) return;
			remember(book, { unit: LOOP, evidence, open });
			const snap = snapshot(book, ctx);
			const judgment = await judge(ctx, snap);
			if (!judgment) return;
			return settleWith(earlier, judgment, snap, { told, onSpeak: (key) => remember(book, { unit: LOOP, evidence, open, told: key }) });
		}),
	);
}
