/**
 * The delegation-host seam: how the loop book learns about child sessions. An adapter knows one host's markers, message shapes, and
 * liveness evidence; the book knows only the records here. With no adapter matching, there are no children and nothing is linked.
 */

import { envOnly } from "./hosts/env-only.ts";
import { herdr } from "./hosts/herdr.ts";

/** Where a child worked, as its host reports it. */
export type Worktree = { path?: string; branch?: string; baseRef?: string; baseSha?: string };

/** What a spawn tells the parent about its child. */
/** `acceptSec`: the timeout of the acceptance check the host reruns after the child exits and before it delivers the result. */
export type Link = { child: string; name?: string; agent?: string; task?: string; sessionFile?: string; cwd?: string; worktree?: Worktree; acceptSec?: number };

/** What a child's returned result tells the parent; `handoff` is the worktree state the host recorded at the end. */
export type Result = {
	name: string;
	agent: string;
	task: string;
	resultContent: unknown;
	failed: boolean;
	sessionFile?: string;
	handoff?: { headSha?: string; commitsAhead?: number; changedFiles?: string[] };
};

/** A follow-up task sent to a child already linked (a persistent specialist, a resumed session): the child by id, name, or session file, and its brief. */
export type Dispatch = { id?: string; name?: string; sessionFile?: string; task: string };

export type Liveness = "alive" | "gone" | "unknown";

export interface Host {
	name: "herdr" | "env-only" | "none";
	isChild(env: NodeJS.ProcessEnv): boolean;
	/** The id a parent can find the child's book by; hosts that pass none have no linkable children. */
	childId(env: NodeJS.ProcessEnv): string | undefined;
	childName(env: NodeJS.ProcessEnv): string | undefined;
	childSession(env: NodeJS.ProcessEnv): string | undefined;
	linkFrom(toolName: string, input: unknown, details: unknown): Link | undefined;
	dispatchFrom(toolName: string, input: unknown, details: unknown): Dispatch | undefined;
	resultFrom(message: { role?: string; customType?: string; details?: unknown }): Result | undefined;
	liveness(link: Link): Liveness;
}

const NONE: Host = {
	name: "none",
	isChild: () => false,
	childId: () => undefined,
	childName: () => undefined,
	childSession: () => undefined,
	linkFrom: () => undefined,
	dispatchFrom: () => undefined,
	resultFrom: () => undefined,
	liveness: () => "unknown",
};

const HOSTS: readonly Host[] = [herdr, envOnly];

/** The adapter whose child markers `env` carries, else the no-host adapter. Needs no configuration. */
export function detectHost(env: NodeJS.ProcessEnv = process.env): Host {
	return HOSTS.find((host) => host.isChild(env)) ?? NONE;
}

export const isChild = (env: NodeJS.ProcessEnv = process.env): boolean => detectHost(env).isChild(env);
export const childId = (env: NodeJS.ProcessEnv = process.env): string | undefined => detectHost(env).childId(env);
export const childName = (env: NodeJS.ProcessEnv = process.env): string | undefined => detectHost(env).childName(env);
export const childSession = (env: NodeJS.ProcessEnv = process.env): string | undefined => detectHost(env).childSession(env);

/** The link a tool result describes, from whichever adapter recognizes it: a parent session carries no child markers. */
export function linkFrom(toolName: string, input: unknown, details: unknown): Link | undefined {
	for (const host of HOSTS) {
		const link = host.linkFrom(toolName, input, details);
		if (link) return link;
	}
	return undefined;
}

/** The follow-up dispatch a tool result describes, from whichever adapter recognizes it. */
export function dispatchFrom(toolName: string, input: unknown, details: unknown): Dispatch | undefined {
	for (const host of HOSTS) {
		const dispatch = host.dispatchFrom(toolName, input, details);
		if (dispatch) return dispatch;
	}
	return undefined;
}

export function resultFrom(message: { role?: string; customType?: string; details?: unknown }): Result | undefined {
	for (const host of HOSTS) {
		const result = host.resultFrom(message);
		if (result) return result;
	}
	return undefined;
}

/** The first adapter that can tell decides; no adapter knowing the child is `unknown`, never `gone`. */
export function liveness(link: Link): Liveness {
	for (const host of HOSTS) {
		const found = host.liveness(link);
		if (found !== "unknown") return found;
	}
	return "unknown";
}
