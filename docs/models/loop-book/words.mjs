// The reader's words shared by both views: what the phase line says, and each step as the agent lives it.

const obsOpen = (v) => v.observe && !(v.landed && v.seen);
const verifyDone = (v) => v.skipV || (v.run === "pass" && !obsOpen(v));

/** What the book's phase line asks for next. `reviewed` is the loop's kind; the model's constant is not in the state. */
export function next(v, reviewed) {
	if (!v.acted) return "act";
	if (!verifyDone(v)) return v.run === "fail" ? "fix" : "verify";
	if (reviewed && !v.skipR && v.review !== "clear") return v.review === "blocking" ? "fix" : "review";
	return "close";
}

export function phase(v, reviewed) {
	if (v.closed) return "Closed";
	const to = next(v, reviewed);
	if (to === "act") return "No change yet";
	if (to === "fix") return v.run === "fail" ? "Check failed: fix" : "Review found blocking defects: fix";
	if (to === "verify") {
		if (v.run === "pass") return v.landed ? "Check passed, observation still open" : "Check passed, observation waits for a landing";
		return "Changed, check missing";
	}
	if (to === "review") return "Checked, review missing";
	return "Complete: close";
}

const STEPS = {
	EditHome: "you change the code",
	EditOther: "you write a file in another repository",
	WriteNote: "you write a note git ignores",
	BashEdit: "you change the code through a shell command",
	RunPasses: "you run the anchor: it passes",
	RunFails: "you run the anchor: it fails",
	DeclareVerifyTask: "you declare a passing verify for one unit",
	AddObserve: "you list an observation to make after landing",
	DeclareSeen: "you declare the observation seen",
	StartWorker: "you start a worker and wait",
	WorkerEditsItsTree: "the worker edits in its own worktree",
	WorkerReturns: "the worker returns",
	SkipVerify: "you declare skip verify",
	SkipReview: "you declare skip review",
	BackToVerify: "you declare back to verify",
	Wake: "someone speaks to you",
	SettleTodo: "you finish the todo",
	Close: "you close the loop",
};

export function step(action, from, to) {
	if (action === "DeclareVerify") return to.run === "pass" ? "you declare a passing verify" : "you declare a passing verify with no task: the tool answers ok";
	if (action === "Push") return to.landed && !to.seen && to.news ? "you push: the book records the landing" : "you push: the book records no landing";
	if (action === "AskReview" || action === "AskReviewer" || action === "AskOtherRole") return to.reviewerOut === "reviewer" ? "you start a reviewer and wait" : "you ask a subagent of another role to review, and wait";
	if (action === "ReviewReturns" || action === "ReviewClear" || action === "ReviewBlocks") {
		if (!to.clearTold) return "the review comes back with blocking findings";
		return to.review === "clear" && to.news ? "the review comes back: Blocking P0=0 P1=0" : "the review comes back: Blocking P0=0 P1=0, and the book records no review";
	}
	if (action === "TurnEnds") return !from.runWaits && from.news ? "your turn ends: the notice judges the loop" : "your turn ends: no notice";
	return STEPS[action] ?? action;
}
