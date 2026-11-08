/** Links between a coordinator's book and its children: which spawns happened before a loop opened, and which link a result belongs to. */

import { type Link, type Result, linkFrom, resultFrom } from "./host.ts";
import type { Entry } from "./book.ts";

type Block = { type?: string; id?: string; name?: string; arguments?: unknown; input?: unknown };
type BranchItem = {
	type?: string;
	customType?: string;
	details?: unknown;
	data?: unknown;
	message?: { role?: string; customType?: string; toolName?: string; toolCallId?: string; details?: unknown; content?: unknown };
};

/** The result a branch item holds, if it is a delivered `subagent_result` in either of pi's two shapes. */
function resultOfItem(item: BranchItem): Result | undefined {
	if (item.type === "custom_message") return resultFrom({ role: "custom", customType: item.customType, details: item.details });
	if (item.type === "message" && item.message?.role === "custom") return resultFrom({ role: "custom", customType: item.message.customType, details: item.message.details });
	return undefined;
}

/** True when `result` is the return of the child `link` started: equal session files when both name one, else equal names. */
export function resultIsOf(result: { sessionFile?: string; name?: string }, link: { sessionFile?: unknown; name?: unknown }): boolean {
	if (result.sessionFile && typeof link.sessionFile === "string") return result.sessionFile === link.sessionFile;
	return Boolean(result.name) && result.name === link.name;
}

/** The latest link of the book that `result` belongs to, or undefined. */
export function linkOfResult(entries: Entry[], result: { sessionFile?: string; name?: string }): Entry | undefined {
	return [...entries].reverse().find((entry) => entry.stage === "link" && resultIsOf(result, entry));
}

/**
 * The children spawned in this session since its last closed loop (`closeType` custom entry) that have not returned: a loop opens
 * at the first todo, and a spawn before it left no link. The spawn's own tool input is read from the assistant message that made the call.
 */
export function priorSpawns(branch: unknown[], closeType: string): Link[] {
	const items = branch as BranchItem[];
	let start = 0;
	items.forEach((item, index) => {
		if (item.type === "custom" && item.customType === closeType) start = index + 1;
	});
	const calls = new Map<string, unknown>();
	const spawns: { link: Link; at: number }[] = [];
	const returned: { result: Result; at: number }[] = [];
	items.slice(start).forEach((item, offset) => {
		const message = item.type === "message" ? item.message : undefined;
		if (message?.role === "assistant" && Array.isArray(message.content)) {
			for (const block of message.content as Block[]) if (block?.type === "toolCall" && block.id) calls.set(block.id, block.arguments ?? block.input);
		}
		if (message?.role === "toolResult" && message.toolName === "subagent") {
			const link = linkFrom("subagent", calls.get(message.toolCallId ?? ""), message.details);
			if (link) spawns.push({ link, at: offset });
		}
		const result = resultOfItem(item);
		if (result) returned.push({ result, at: offset });
	});
	return spawns.filter(({ link, at }) => !returned.some((done) => done.at > at && resultIsOf(done.result, link))).map(({ link }) => link);
}
