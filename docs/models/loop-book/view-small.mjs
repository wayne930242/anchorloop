// The chart the reader confirms (small.cfg): a reviewed loop as its phase line reads, one reviewer, no other actor.
import { phase, step as words } from "./words.mjs";

export const title = "a reviewed loop, as the phase line reads it";

export const state = (v) => phase(v, true);

// Not drawn: finishing the todo and starting the reviewer (neither moves the phase line), and close from a loop that is
// not complete. Close is accepted from every state once each todo is done or has a followup (rule 8); the chart draws
// it from the complete loop only.
export function step(action, from, to) {
	if (action === "SettleTodo") return null;
	if (action === "Close") return phase(from, true).startsWith("Complete") ? "you close the loop [every todo done or given a followup]" : null;
	if (action.startsWith("Review")) return `the reviewer you started comes back: ${to.clearTold ? "Blocking P0=0 P1=0" : "blocking findings"}`;
	return words(action, from, to);
}

export const group = (v) => (v.closed ? "closed" : phase(v, true).startsWith("Complete") ? "done" : "open");
export const colors = { open: "blue", done: "teal", closed: "tan" };
