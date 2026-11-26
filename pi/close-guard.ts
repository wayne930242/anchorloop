/**
 * The close guard: when a run settles after a file change with no passing run of its anchor since, it adds one line to the
 * session. The line is shown and reaches the model with the next prompt; it never starts a turn.
 *
 * The anchor is the last labelled check line (`Anchor:`, `Gates:`, `Checks:`, `Verify:`, `Done when:`, `驗證：`) in the brief (the
 * first user message) or the agent's text, or the last anchor or sb check spec on a todo call or batch item. Each backticked command
 * in it (a todo's bare value is one command) must have its latest run, in bash or a monitor (by its exit code), after the last change,
 * and that run passed; passing todo evidence recorded after the last change counts as a passing run of each. An anchor with no
 * command (a review, a person's verdict) is not judged. A change is a successful `write` or `edit`; prose (.md, .txt) written after
 * a code change does not move the last change.
 * Everything is read from the session branch, so a resumed or reloaded session reads the same state.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const NOTICE_TYPE = "anchorloop-close-guard";

type Part = { type?: string; text?: string; id?: string; name?: string; arguments?: Record<string, unknown> };
type Message = { role?: string; content?: unknown; toolCallId?: string; isError?: boolean; structuredContent?: { exit_code?: unknown } };
interface LedgerTask { id: number; subject: string; status: string; anchor?: string; metadata?: { anchor?: string } }
type Outcome = { monitorId?: unknown; exitCode?: unknown };
type Entry = { type?: string; id?: string; customType?: string; details?: { change?: unknown; evidenceKey?: string; monitorOutcome?: Outcome; notifications?: { monitorOutcome?: Outcome }[] }; data?: { v?: number; tasks?: LedgerTask[] }; message?: Message };

/** Runs of spaces and tabs collapsed, so `pytest  -q` matches `pytest -q`. */
const squeeze = (text: string) => text.replace(/[ \t]+/g, " ").trim();

/** The backticked commands of an anchor, or `bare` itself when it has none and is taken as one command. */
function commandsOf(text: string, bare: boolean): string[] {
	const ticked = [...text.matchAll(/`([^`\n]+)`/g)].map((m) => squeeze(m[1])).filter(Boolean);
	return ticked.length || !bare ? ticked : [squeeze(text)].filter(Boolean);
}

const LABEL = String.raw`(?:reality anchor|anchor|checks?|gates?|verify|verification|done when|驗證|檢查|驗收)`;
/** The anchor stated in one text, if any: its last labelled check line (bold, list, quote, and heading markers allowed). */
const anchorLine = (text: string) => [...text.matchAll(new RegExp(String.raw`^[ \t>*_#-]*${LABEL}[*_]*\s*[:：][*_]*\s*(.+)$`, "gim"))].at(-1)?.[1];

const partsOf = (message: Message): Part[] => (Array.isArray(message.content) ? (message.content as Part[]) : []);
const textOf = (message: Message) => typeof message.content === "string" ? message.content : partsOf(message).map(p => p.type === "text" ? p.text ?? "" : "").join("\n");
const PROSE = /\.(?:md|markdown|txt|rst)$/i;

export interface Reading {
	/** The anchor's commands, `[]` for an anchor with no command, `undefined` when none was stated. */
	anchor?: string[];
	/** The id of the entry that recorded the last change. */
	change?: string;
	/** Per anchor command, whether its latest run came after the last change and passed. */
	green: Map<string, boolean>;
	evidenced?: boolean; // passing todo evidence was recorded after the last change
	/** The change ids a notice was already added for. */
	noticed: Set<string>;
	handoff?: { task: number; key: string };
}

/** Reads the branch in order: anchor statements, tool calls and their results, and earlier notices. */
export function read(branch: readonly Entry[]): Reading {
	const calls = new Map<string, Part>();
	const runs: { seq: number; command: string; ok: boolean }[] = [];
	const noticed = new Set<string>();
	let anchor: string[] | undefined;
	const monitors = new Map<string, string>();
	let change: { id: string; seq: number } | undefined, codeChange: typeof change, evidenceSeq = -1, briefed = false;
	let source: { call: string; value: string; subject?: unknown; id?: unknown } | undefined;
	let tasks: LedgerTask[] = [];
	let task: number | undefined;
	const reminded = new Set<string>();
	branch.forEach((entry, seq) => {
		if (entry.type === "custom_message" && entry.customType === NOTICE_TYPE && typeof entry.details?.change === "string") noticed.add(entry.details.change);
		if (entry.customType === NOTICE_TYPE && entry.details?.evidenceKey) reminded.add(entry.details.evidenceKey);
		if (entry.type === "custom_message" && entry.customType === "pi-loop-monitor") for (const out of [entry.details?.monitorOutcome, ...(entry.details?.notifications ?? []).map(n => n?.monitorOutcome)]) {
			const command = monitors.get(String(out?.monitorId));
			if (command && typeof out?.exitCode === "number") runs.push({ seq, command, ok: out.exitCode === 0 });
		}
		if (entry.type === "custom" && entry.customType === "todo/v1" && entry.data?.v === 1 && Array.isArray(entry.data.tasks)) {
			tasks = entry.data.tasks;
			if (!tasks.some(t => t?.id === task && t.status !== "deleted")) task = undefined;
		}
		const message = entry.message;
		if (entry.type !== "message" || !message) return;
		if (message.role === "user" && !briefed) {
			const line = anchorLine(textOf(message)); // the brief's anchor is the worker's anchor until the agent states one
			if (line !== undefined) anchor = commandsOf(line, false);
			briefed = true;
		} else if (message.role === "assistant") {
			for (const part of partsOf(message)) {
				if (part.type === "text" && part.text) {
					const line = anchorLine(part.text);
					if (line !== undefined) { anchor = commandsOf(line, false); source = undefined; task = undefined; }
				} else if (part.type === "toolCall" && part.id) {
					calls.set(part.id, part);
					if (part.name === "todo" && part.arguments) {
						const tasks = part.arguments.tasks;
						for (const item of [part.arguments, ...(Array.isArray(tasks) ? tasks : [])]) {
							const value = [item?.anchor, item?.metadata?.anchor].find(v => typeof v === "string" && v.trim());
							const spec = item?.metadata?.sb?.spec?.check;
							if (value || spec) {
								anchor = value ? commandsOf(value, true) : commandsOf(typeof spec.run === "string" ? spec.run : "", true);
								source = value ? { call: part.id, value, subject: item.subject, id: item.id } : undefined;
								task = undefined;
							}
						}
					}
				}
			}
		} else if (message.role === "toolResult" && message.toolCallId) {
			const part = calls.get(message.toolCallId);
			if (!part) return;
			const code = message.structuredContent?.exit_code;
			const ok = typeof code === "number" ? code === 0 : message.isError !== true;
			if (source && source.call === message.toolCallId && ok) {
				const { id, subject, value } = source;
				task = tasks.findLast(t => t && t.status !== "deleted" && (id !== undefined ? t.id === id : t.subject === subject)
					&& (t.anchor ?? t.metadata?.anchor) === value)?.id;
			}
			const args = part.arguments;
			if ((part.name === "write" || part.name === "edit") && ok) {
				change = { id: entry.id ?? `#${seq}`, seq };
				if (!PROSE.test(String(args?.path ?? ""))) codeChange = change;
			} else if (part.name === "bash" && typeof args?.command === "string") {
				runs.push({ seq, command: squeeze(args.command), ok });
			} else if (part.name === "MonitorCreate" && typeof args?.command === "string" && ok) {
				const id = /Monitor #(\w+) started/.exec(textOf(message))?.[1];
				if (id) monitors.set(id, squeeze(args.command));
			} else if (part.name === "todo" && ok && [args, ...(Array.isArray(args?.tasks) ? args.tasks : [])]
				.some(item => Array.isArray(item?.evidence) && item.evidence.some((e: { result?: unknown }) => e?.result === "pass"))) {
				evidenceSeq = seq;
			}
		}
	});
	const last = codeChange ?? change;
	const changeSeq = last?.seq ?? -1;
	const green = new Map<string, boolean>();
	const runIds: number[] = [];
	for (const command of anchor ?? []) {
		const latest = runs.filter((run) => run.command.includes(command)).at(-1);
		// A containing shell command can quote the check or swallow its failure; only hand off identifiable invocations.
		const invocation = latest?.command.replace(/^cd [\w./-]+ && /, "");
		if (latest && [latest.command, invocation, invocation?.replace(/^uv run /, "")].includes(command)) runIds.push(latest.seq);
		// Passing evidence is a passing run at the point it was recorded; a later run of the command overrides it.
		const run = latest && latest.seq > evidenceSeq ? latest : evidenceSeq >= 0 ? { seq: evidenceSeq, ok: true } : undefined;
		green.set(command, !!run && run.seq > changeSeq && run.ok);
	}
	const key = JSON.stringify([source?.call, last?.id, runIds]);
	const handoff = task && last && green.size && runIds.length === anchor?.length && Math.min(...runIds) > evidenceSeq
		&& [...green.values()].every(Boolean) && !reminded.has(key) ? { task, key } : undefined;
	return { anchor, change: last?.id, green, evidenced: evidenceSeq > changeSeq && changeSeq >= 0, noticed, handoff };
}

/** The one-line notice for a reading, or `undefined` when the run may close as it stands. */
export function notice(reading: Reading): string | undefined {
	if (!reading.change || reading.noticed.has(reading.change)) return undefined;
	if (!reading.anchor) return reading.evidenced ? undefined : "anchorloop: files changed, but no `Anchor: <check>` line was stated; state the check and show it passing.";
	const missing = [...reading.green].filter(([, ok]) => !ok).map(([command]) => `\`${command}\``);
	if (!missing.length) return undefined;
	const named = missing.join(", ");
	return `anchorloop: no passing run of ${named.length > 120 ? `${named.slice(0, 117)}...` : named} after the last change.`;
}

export default function closeGuard(pi: ExtensionAPI) {
	pi.on("agent_before_settle", (event, ctx) => {
		const reading = read(ctx.sessionManager.getBranch() as Entry[]);
		const handoff = reading.handoff && pi.getAllTools().some(t => t.name === "todo" && t.parameters.properties?.evidence) ? reading.handoff : undefined;
		const line = handoff ? `anchorloop: use todo update on #${handoff.task} to append each unrecorded passing run to evidence: {command, result:"pass"} and include sha when known.` : notice(reading);
		if (!line) return undefined;
		const entry = { type: "custom_message" as const, customType: NOTICE_TYPE, content: line, display: true, details: handoff ? { evidenceKey: handoff.key } : { change: reading.change } };
		return { entries: [...event.entries, entry] };
	});
}
