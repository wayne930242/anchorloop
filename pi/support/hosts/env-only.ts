/**
 * Hosts that only mark their children in the environment: pi-subagents (`PI_SUBAGENT_CHILD`) and avtc's pi-subagent
 * (`PI_SUBAGENT_CHILD_AGENT` with `PI_SUBAGENT_PARENT_PID`). They give a child no id a parent could link, so this adapter
 * detects children and nothing else.
 */

import type { Host } from "../host.ts";

export const envOnly: Host = {
	name: "env-only",
	isChild: (env) => env.PI_SUBAGENT_CHILD === "1" || Boolean(env.PI_SUBAGENT_CHILD_AGENT && env.PI_SUBAGENT_PARENT_PID),
	childId: () => undefined,
	childName: () => undefined,
	childSession: () => undefined,
	linkFrom: () => undefined,
	resultFrom: () => undefined,
	liveness: () => "unknown",
};
