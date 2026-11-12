// The full check: the phase line, then what the book does not show the reader on that line.
import { phase, step as words } from "./words.mjs";

export const title = "one loop book: what it asks for, and what really happened";

// The kind is a constant of the config and not in the state; every config that uses this view is a reviewed loop
// except inline.cfg, which sets the environment variable.
const reviewed = process.env.LOOPBOOK_KIND !== "inline";

export function state(v) {
	const parts = [phase(v, reviewed)];
	if (v.closed) return parts[0];
	if (v.fresh && v.run !== "pass") parts.push("a check passed and nothing it tests changed since");
	if (v.declared && v.run !== "pass") parts.push("the tool answered ok to a verify");
	if (v.clearTold && v.review !== "clear") parts.push("a review came back with no blocking finding");
	if (v.run === "pass" && v.changed) parts.push("the code changed after the check");
	if (v.review === "clear" && v.blind) parts.push("the code changed while the reviewer read");
	if (v.observe && !v.landed && v.pushed) parts.push("pushed");
	if (v.observe && !v.linked) parts.push("no ref watched");
	if (v.busy > 0) parts.push("worker out");
	if (v.reviewerOut !== "none") parts.push(v.reviewerOut === "reviewer" ? "reviewer reading" : "another role reviewing");
	if (v.judgedBusy) parts.push("judged while waiting");
	if (v.idle) parts.push("turn over");
	return parts.join("; ");
}

export const step = words;
