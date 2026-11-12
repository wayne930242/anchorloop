// The reader's words shared by the views: each unit as the coordinator meets it, and each step as it happens.
// Unit "a" is MP-1001, the first unit (its anchor is the loop's); unit "b" is MP-1002.

export const NAME = { a: "MP-1001", b: "MP-1002" };

const reviews = () => process.env.MULTITASK_REVIEWS === "1";
const lands = () => process.env.MULTITASK_LANDS === "1";

/** What the book asks of the unit next: act, verify, review, land, or close. */
export function next(v, u) {
	if (!v.acted[u]) return "act";
	if (!v.pass[u]) return "verify";
	if (reviews() && !v.clear[u]) return "review";
	if (lands() && !v.landed[u]) return "land";
	return "close";
}

const out = (v, u) => v.child[u] === "out" || v.child[u] === "edited" || v.rev === u;

/** One unit in a few words: who has it, and what the book asks for, with what the book does not show. */
export function unit(v, u) {
	if (v.closed) return "closed";
	if (v.rev === u) return "reviewer reading";
	if (v.child[u] === "out") return "worker started";
	if (v.child[u] === "edited") return v.pass[u] ? "worker editing, book still shows its check" : "worker editing";
	if (v.child[u] === "failed" && !v.done[u]) return "worker died";
	if (v.child[u] === "idle" && !v.done[u]) return "not started";
	if (!v.done[u]) return "car returned, rework";
	const step = next(v, u);
	if (step === "act") return "work done, book shows no change";
	if (step === "verify") return v.fresh[u] ? "checked, book asks for the check" : "changed, check missing";
	if (step === "review") return v.toldClear[u] ? "reviewed clear, book asks for a review" : "checked, review missing";
	if (step === "land") return v.inRef[u] ? "landed, book sees no landing" : "checked, car not landed";
	if (v.pass[u] && !v.fresh[u]) return "book shows a check of older code";
	if (v.clear[u] && !v.toldClear[u]) return "book shows another unit's review";
	return "complete";
}

export const units = (v) => `${NAME.a}: ${unit(v, "a")} | ${NAME.b}: ${unit(v, "b")}`;

const STEPS = {
	Spawn: "you start its worker",
	Resume: "you send its worker a follow-up",
	ChildEdits: "its worker edits in its worktree",
	ChildFails: "its worker dies (model quota)",
	CoordEdit: "you change its code yourself",
	RunAnchor: "you run its anchor: it passes",
	DeclareVerify: "you declare its verify with its task",
	Back: "sb returns its car: you declare back for it",
	SendReview: "you send it to the persistent reviewer",
	Land: "sb's notice: its car landed; you declare it",
	Handoff: "you hand off to a new session",
	Reload: "you /reload after an install",
	Wake: "someone else starts your turn",
	TodoMoves: "a todo is added or completed",
	Close: "you close the loop",
};

/** Which unit a step was for: the one whose worker, book, or flags changed. */
function whose(from, to) {
	for (const u of ["a", "b"]) {
		if (from.child[u] !== to.child[u] || from.done[u] !== to.done[u] || from.fresh[u] !== to.fresh[u] || from.inRef[u] !== to.inRef[u]) return u;
		if (from.declared[u] !== to.declared[u] || from.toldClear[u] !== to.toldClear[u] || (from.rev !== to.rev && (to.rev === u || from.rev === u))) return u;
	}
	for (const u of ["a", "b"]) {
		if (from.pass[u] !== to.pass[u] || from.acted[u] !== to.acted[u] || from.landed[u] !== to.landed[u]) return u;
	}
	return undefined;
}

export function step(action, from, to) {
	if (action === "TurnEnds") {
		return to.said !== "none" ? `your turn ends: the notice asks ${NAME[to.said]} for ${to.asked[to.said]}` : "your turn ends: no notice";
	}
	if (action === "ReviewBack") return `the reviewer comes back clear for ${NAME[from.rev]}`;
	if (action === "ChildReturns") {
		const u = whose(from, to);
		return `${NAME[u]}'s worker returns, its check passed${to.pass[u] ? "" : ": the book does not count it"}`;
	}
	const words = STEPS[action] ?? action;
	const u = whose(from, to);
	return u ? `${NAME[u]}: ${words}` : words;
}
