/**
 * The pi-herdr-agents adapter. A child carries `PI_SUBAGENT_ID`, `PI_SUBAGENT_NAME` and `PI_SUBAGENT_SESSION`; the `subagent` tool's
 * result holds the started metadata (`id`, `name`, `agent`, `sessionFile`, `worktree`); a finished child arrives as a
 * `subagent_result` message. Each child records its process identity beside its session in `<session>.process.json`.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import type { Host, Link, Liveness, Result, Worktree } from "../host.ts";

const text = (value: unknown): string | undefined => (typeof value === "string" && value !== "" ? value : undefined);
const record = (value: unknown): Record<string, unknown> | undefined => (value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined);

function worktreeOf(value: unknown): Worktree | undefined {
	const found = record(value);
	if (!found) return undefined;
	const worktree: Worktree = { path: text(found.path), branch: text(found.branch), baseRef: text(found.baseRef), baseSha: text(found.baseSha) };
	return Object.values(worktree).some((item) => item !== undefined) ? (Object.fromEntries(Object.entries(worktree).filter(([, item]) => item !== undefined)) as Worktree) : undefined;
}

function handoffOf(value: unknown): Result["handoff"] {
	const found = record(value);
	if (!found) return undefined;
	return {
		...(text(found.headSha) ? { headSha: text(found.headSha) } : {}),
		...(typeof found.commitsAhead === "number" ? { commitsAhead: found.commitsAhead } : {}),
		...(Array.isArray(found.changedFiles) ? { changedFiles: found.changedFiles.map(String) } : {}),
	};
}

/** The start time of `pid` in epoch seconds where the platform shows one: macOS through `ps`, Linux through `/proc`; else undefined. */
function startedAt(pid: number): string | undefined {
	try {
		if (process.platform === "darwin") {
			const shown = execFileSync("ps", ["-o", "lstart=", "-p", String(pid)], { encoding: "utf-8", env: { ...process.env, LC_ALL: "C", TZ: "UTC" }, stdio: ["ignore", "pipe", "ignore"], timeout: 2000 }).trim();
			const parsed = Date.parse(`${shown} UTC`);
			return Number.isNaN(parsed) ? undefined : String(Math.floor(parsed / 1000));
		}
		if (process.platform === "linux") {
			const stat = readFileSync(`/proc/${pid}/stat`, "utf-8");
			return stat.slice(stat.lastIndexOf(")") + 2).split(" ")[19];
		}
	} catch {
		return undefined;
	}
	return undefined;
}

export const herdr: Host = {
	name: "herdr",
	isChild: (env) => Boolean(env.PI_SUBAGENT_ID),
	childId: (env) => env.PI_SUBAGENT_ID || undefined,
	childName: (env) => env.PI_SUBAGENT_NAME || undefined,
	childSession: (env) => env.PI_SUBAGENT_SESSION || undefined,
	linkFrom(toolName, input, details): Link | undefined {
		if (toolName !== "subagent") return undefined;
		const started = record(details);
		const id = text(started?.id);
		if (!started || !id) return undefined;
		const worktree = worktreeOf(started.worktree);
		return {
			child: id,
			...(text(started.name) ? { name: text(started.name) } : {}),
			...(text(started.agent) ? { agent: text(started.agent) } : {}),
			...(text(started.sessionFile) ? { sessionFile: text(started.sessionFile) } : {}),
			...(text(record(input)?.cwd) ? { cwd: text(record(input)?.cwd) } : {}),
			...(worktree ? { worktree } : {}),
		};
	},
	resultFrom(message): Result | undefined {
		if (message.role !== "custom" || message.customType !== "subagent_result") return undefined;
		const details = record(message.details) ?? {};
		const handoff = handoffOf(details.worktree);
		return {
			name: String(details.name ?? ""),
			agent: String(details.agent ?? ""),
			task: String(details.task ?? ""),
			resultContent: details.resultContent,
			failed: Boolean(details.error) || Boolean(details.errorMessage) || (typeof details.exitCode === "number" && details.exitCode !== 0),
			...(text(details.sessionFile) ? { sessionFile: text(details.sessionFile) } : {}),
			...(handoff ? { handoff } : {}),
		};
	},
	liveness(link): Liveness {
		if (!link.sessionFile) return "unknown";
		let identity: Record<string, unknown> | undefined;
		try {
			identity = record(JSON.parse(readFileSync(`${link.sessionFile}.process.json`, "utf-8")));
		} catch {
			return "unknown";
		}
		const pid = identity?.pid;
		if (typeof pid !== "number" || !Number.isInteger(pid) || pid <= 0) return "unknown";
		try {
			process.kill(pid, 0);
		} catch (error) {
			return (error as NodeJS.ErrnoException).code === "EPERM" ? "alive" : "gone";
		}
		// A recycled PID has another start time; the record's time is compared only where this host can read one.
		const recorded = text(identity?.startTime);
		const now = recorded ? startedAt(pid) : undefined;
		return recorded && now && recorded !== now ? "gone" : "alive";
	},
};
