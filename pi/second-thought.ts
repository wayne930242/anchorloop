/**
 * pi extension: inside an open loop, asks Jev to check the phase machine's reading of the loop book. The
 * program computes the next phase from the book's evidence; Jev sees the kind, intent, anchor, diff
 * summary, phase (current, next, missing), verify state, open todos, tasks, and friction, and judges only
 * whether the current phase's completion condition truly holds and whether to advance, go back, or ask
 * the user. It runs when a run settles and the book gained an entry since the last judgment, and at a
 * `close` declaration. The advisory is one line leading with `next → <phase>`; it continues the run once
 * when Jev agrees to advance and the next phase is a verify, review, or fix, or when todos are still open
 * without a followup (unless Jev says to ask the user). Away from close the advisory names those todos and
 * asks the agent to continue, complete, or settle each with `metadata.followup`. A run that arranged a wake
 * (a monitor, a loop, a subagent) is waiting, not finished, and is not judged. Outside a loop nothing
 * runs, nor in a `quick` loop, whose only prompt is the close reminder; a subagent session registers
 * nothing, since the agent that spawned it judges its result.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { currentKind, guarded, openLoop } from "./support/book.ts";
import { type Answers, classify } from "./support/jev.ts";
import { type Snapshot, listTodos, snapshot } from "./support/snapshot.ts";
import { isSubagent } from "./support/subagent.ts";

export { isSubagent, snapshot };
export type { Snapshot };

export const ENTRY_TYPE = "anchorloop-second-thought";
const WAIT_TOOLS = new Set(["MonitorCreate", "LoopCreate", "goal_wait", "subagent", "subagent_resume", "subagent_send"]);

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

export function assess(verdict: Verdict, snap: Snapshot): { found: string[]; notes: string[] } {
	const found: string[] = [];
	const notes: string[] = [];
	if (verdict.done < THRESHOLDS.doneBelow) found.push("evidence not shown to cover the intent");
	if (verdict.review === THRESHOLDS.reviewTier) {
		if (snap.reviewClear) notes.push("review rated full, but a review recorded after the last change found no blocking finding");
		else found.push("needs full independent review");
	}
	if (verdict.quality < THRESHOLDS.qualityBelow) found.push("result below the intent");
	return { found, notes };
}

/** True when Jev agrees to advance and the next phase is one the agent can act on now, or open todos wait and the user is not needed. */
export function continues(verdict: Verdict, snap: Snapshot): boolean {
	if (snap.unsettled.length && verdict.move !== "ask-user") return true;
	return verdict.move === "advance" && ACTIONABLE.has(snap.next);
}

/** The open todos the agent must answer, or the call to put them to the user. */
function todoCall(verdict: Verdict, snap: Snapshot): string {
	const list = `Open todos: ${listTodos(snap.unsettled)}.`;
	return verdict.move === "ask-user"
		? ` ${list} Ask the user about them with ask_user_question before ending the turn.`
		: ` ${list} Continue each, complete it, or set metadata.followup (a ticket id, \`memory\`, or \`drop — <reason>\`).`;
}

/** One line: the program's next phase and its gap, Jev's move and scores, and, away from close, the call to act. */
export function message(verdict: Verdict, snap: Snapshot, found: string[], notes: string[], atClose = false): string {
	const extra = [...found, ...notes];
	return (
		`Second thought (Jev, advisory): next → ${snap.next}${snap.missing ? ` (missing: ${snap.missing})` : ""}; ` +
		`${verdict.move}; done ${verdict.done.toFixed(2)}, review ${verdict.review}, quality ${verdict.quality.toFixed(2)}/3` +
		`${extra.length ? `; ${extra.join("; ")}` : ""}.` +
		(!atClose && verdict.move === "advance" && ACTIONABLE.has(snap.next) ? ` Do ${snap.next} now, or say why it does not apply.` : "") +
		(!atClose && snap.unsettled.length ? todoCall(verdict, snap) : "")
	);
}

export default function (pi: ExtensionAPI) {
	if (isSubagent()) return;
	let waiting = false;
	let continued = false;
	// Entries each open book held when it was last judged, and the advisory it last received.
	const judged = new Map<string, number>();
	const told = new Map<string, string>();
	// A close deletes its book, so what Jev needs is read when the call starts.
	const closing = new Map<string, Snapshot>();

	pi.on("session_start", () => {
		judged.clear();
		told.clear();
		closing.clear();
	});

	pi.on("agent_settled", () => {
		waiting = false;
		continued = false;
	});

	pi.on(
		"tool_call",
		guarded((event, ctx) => {
			if (WAIT_TOOLS.has(event.toolName)) waiting = true;
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
			const called = closing.get(event.toolCallId);
			if (called) closing.delete(event.toolCallId);
			if (event.isError) return;
			// The close tool reports the loop as it stood when it closed, after any reflect that ran beside it.
			const snap = (event.details as { snapshot?: Snapshot } | undefined)?.snapshot ?? called;
			if (!snap) return;
			const judgment = await judge(ctx, snap);
			if (!judgment?.verdict) return;
			const { found, notes } = assess(judgment.verdict, snap);
			pi.appendEntry(ENTRY_TYPE, { ...judgment.verdict, at: "close", concerns: found });
			return { content: [...event.content, { type: "text" as const, text: `\n${message(judgment.verdict, snap, found, notes, true)}` }] };
		}),
	);

	pi.on(
		"agent_before_settle",
		guarded(async (event, ctx) => {
			if (waiting || event.outcome !== "completed") return;
			const book = openLoop(ctx);
			// A quick loop has no prompts but the close reminder.
			if (!book || currentKind(book.entries) === "quick") return;
			const id = String(book.header.id);
			if (book.entries.length <= (judged.get(id) ?? 0)) return;
			judged.set(id, book.entries.length);
			const snap = snapshot(book, ctx);
			const judgment = await judge(ctx, snap);
			if (!judgment) return;
			const record = (data: Record<string, unknown>) => ({ type: "custom" as const, customType: ENTRY_TYPE, data });
			// A later handler's boundary result replaces the entries an earlier one returned, so carry them along.
			const earlier = event.entries ?? [];
			if (!judgment.verdict) return { entries: [...earlier, record({ verdict: "unknown", reason: judgment.reason })] };
			const { found, notes } = assess(judgment.verdict, snap);
			const text = message(judgment.verdict, snap, found, notes);
			if (told.get(id) === text) return;
			told.set(id, text);
			const proceed = !continued && continues(judgment.verdict, snap);
			if (proceed) continued = true;
			return {
				entries: [...earlier, record({ ...judgment.verdict, concerns: found }), { type: "custom_message" as const, customType: ENTRY_TYPE, content: text, display: true }],
				...(proceed ? { continue: true } : {}),
			};
		}),
	);
}
