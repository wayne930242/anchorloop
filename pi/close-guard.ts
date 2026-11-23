/**
 * The close guard: when a run settles after a file change with no passing run of its anchor since, it adds one line to the
 * session. The line is shown and reaches the model with the next prompt; it never starts a turn.
 *
 * The anchor is the last `Anchor: <check>` line the agent wrote, or the last `metadata.anchor` on a todo call. Each backticked
 * command in it (a todo's bare value is one command) must have its latest bash run after the last change, and that run passed.
 * An anchor with no command (a review, a person's verdict) is not judged. A change is a successful `write` or `edit`.
 * Everything is read from the session branch, so a resumed or reloaded session reads the same state.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const NOTICE_TYPE = "anchorloop-close-guard";

type Part = { type?: string; text?: string; id?: string; name?: string; arguments?: Record<string, unknown> };
type Message = { role?: string; content?: unknown; toolCallId?: string; isError?: boolean; structuredContent?: { exit_code?: unknown } };
type Entry = { type?: string; id?: string; customType?: string; details?: { change?: unknown }; message?: Message };

/** Runs of spaces and tabs collapsed, so `pytest  -q` matches `pytest -q`. */
const squeeze = (text: string) => text.replace(/[ \t]+/g, " ").trim();

/** The backticked commands of an anchor, or `bare` itself when it has none and is taken as one command. */
function commandsOf(text: string, bare: boolean): string[] {
	const ticked = [...text.matchAll(/`([^`\n]+)`/g)].map((m) => squeeze(m[1])).filter(Boolean);
	return ticked.length || !bare ? ticked : [squeeze(text)].filter(Boolean);
}

/** The anchor stated in one assistant text, if any: the last `Anchor:` line (`Reality anchor:` and bold markers allowed). */
function anchorLine(text: string): string | undefined {
	const lines = [...text.matchAll(/^[ \t>*_-]*(?:reality )?anchor[*_]*:[*_]*\s*(.+)$/gim)];
	return lines.at(-1)?.[1];
}

const partsOf = (message: Message): Part[] => (Array.isArray(message.content) ? (message.content as Part[]) : []);

export interface Reading {
	/** The anchor's commands, `[]` for an anchor with no command, `undefined` when none was stated. */
	anchor?: string[];
	/** The id of the entry that recorded the last change. */
	change?: string;
	/** Per anchor command, whether its latest run came after the last change and passed. */
	green: Map<string, boolean>;
	/** The change ids a notice was already added for. */
	noticed: Set<string>;
}

/** Reads the branch in order: anchor statements, tool calls and their results, and earlier notices. */
export function read(branch: readonly Entry[]): Reading {
	const calls = new Map<string, Part>();
	const runs: { seq: number; command: string; ok: boolean }[] = [];
	const noticed = new Set<string>();
	let anchor: string[] | undefined;
	let change: string | undefined;
	let changeSeq = -1;
	branch.forEach((entry, seq) => {
		if (entry.type === "custom_message" && entry.customType === NOTICE_TYPE && typeof entry.details?.change === "string") noticed.add(entry.details.change);
		const message = entry.message;
		if (entry.type !== "message" || !message) return;
		if (message.role === "assistant") {
			for (const part of partsOf(message)) {
				if (part.type === "text" && part.text) {
					const line = anchorLine(part.text);
					if (line !== undefined) anchor = commandsOf(line, false);
				} else if (part.type === "toolCall" && part.id) {
					calls.set(part.id, part);
					const meta = part.name === "todo" ? (part.arguments?.metadata as { anchor?: unknown } | undefined) : undefined;
					if (typeof meta?.anchor === "string" && meta.anchor.trim()) anchor = commandsOf(meta.anchor, true);
				}
			}
		} else if (message.role === "toolResult" && message.toolCallId) {
			const part = calls.get(message.toolCallId);
			if (!part) return;
			const code = message.structuredContent?.exit_code;
			const ok = typeof code === "number" ? code === 0 : message.isError !== true;
			if ((part.name === "write" || part.name === "edit") && ok) {
				change = entry.id ?? `#${seq}`;
				changeSeq = seq;
			} else if (part.name === "bash" && typeof part.arguments?.command === "string") {
				runs.push({ seq, command: squeeze(part.arguments.command), ok });
			}
		}
	});
	const green = new Map<string, boolean>();
	for (const command of anchor ?? []) {
		const last = runs.filter((run) => run.command.includes(command)).at(-1);
		green.set(command, !!last && last.seq > changeSeq && last.ok);
	}
	return { anchor, change, green, noticed };
}

/** The one-line notice for a reading, or `undefined` when the run may close as it stands. */
export function notice(reading: Reading): string | undefined {
	if (!reading.change || reading.noticed.has(reading.change)) return undefined;
	if (!reading.anchor) return "anchorloop: files changed, but no `Anchor: <check>` line was stated; state the check and show it passing.";
	const missing = [...reading.green].filter(([, ok]) => !ok).map(([command]) => `\`${command}\``);
	if (!missing.length) return undefined;
	const named = missing.join(", ");
	return `anchorloop: no passing run of ${named.length > 120 ? `${named.slice(0, 117)}...` : named} after the last change.`;
}

export default function closeGuard(pi: ExtensionAPI) {
	pi.on("agent_before_settle", (event, ctx) => {
		const reading = read(ctx.sessionManager.getBranch() as Entry[]);
		const line = notice(reading);
		if (!line) return undefined;
		const entry = { type: "custom_message" as const, customType: NOTICE_TYPE, content: line, display: true, details: { change: reading.change } };
		return { entries: [...event.entries, entry] };
	});
}
