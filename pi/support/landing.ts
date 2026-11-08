/**
 * Where a worker's change stands against the ref it will land on. Pure git over the repo's refs: no bash command text is read,
 * so how a landing happened (push, merge, fetch, an integrator elsewhere) never matters, only what the ref holds afterwards.
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import {
	type Book,
	type Entry,
	anchorCommand,
	appendEntry,
	findChildBooks,
	git,
	ownBases,
	passingRunOf,
	repoRootOf,
	resultOf,
} from "./book.ts";
import type { Worktree } from "./host.ts";

/** The commit a ref resolves to in `repo`, or undefined when the ref or repo is unknown. */
export function refSha(repo: string, ref: string): string | undefined {
	return git(repo, ["rev-parse", "--verify", "--quiet", `${ref}^{commit}`]) || undefined;
}

/**
 * The ref a link's work lands on, in order: the unit's `lands`; the worktree's base ref when it names a ref other than `HEAD`;
 * the upstream of the source checkout's branch; `origin/HEAD`. Undefined when none exists, so a repo with no remote watches nothing.
 */
export function integrationRef(source: string, link: { worktree?: Worktree }, lands?: string): string | undefined {
	if (lands) return lands;
	const baseRef = link.worktree?.baseRef;
	if (baseRef && baseRef !== "HEAD") return baseRef;
	const upstream = git(source, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]);
	if (upstream) return upstream;
	const origin = git(source, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]);
	return origin || undefined;
}

/** How many commits `ref` holds that `base` does not, or undefined when git cannot say. */
export function behindBy(repo: string, base: string, ref: string): number | undefined {
	const count = git(repo, ["rev-list", "--count", `${base}..${ref}`]);
	return count === undefined || count === "" ? undefined : Number(count);
}

/** One advisory line per linked worker that was based behind the ref it lands on, from the link's base SHA to that ref's tip now. */
export function linkNotes(entries: Entry[]): string[] {
	const notes: string[] = [];
	for (const entry of entries) {
		if (entry.stage !== "link" || typeof entry.ref !== "string") continue;
		const worktree = entry.worktree as Worktree | undefined;
		if (!worktree?.baseSha) continue;
		const dir = worktree.path && existsSync(worktree.path) ? worktree.path : typeof entry.cwd === "string" ? entry.cwd : undefined;
		const behind = dir ? behindBy(dir, worktree.baseSha, entry.ref) : undefined;
		if (behind) notes.push(`${String(entry.name ?? entry.child)} based ${behind} behind ${entry.ref}`);
	}
	return notes;
}

// --- ref state -----------------------------------------------------------------------------------

export type LandRule = "ancestor" | "patch-id" | "content";

/** The result of testing a branch head against a ref: the rule that proves it landed, or how many of its commits are upstream. */
export type Standing = { rule?: LandRule; upstream: number; total: number };

/** Commits to land: `base..head`, 0 when the head adds nothing. */
function aheadOf(repo: string, base: string, head: string): number {
	return Number(git(repo, ["rev-list", "--count", `${base}..${head}`]) ?? 0);
}

/**
 * Whether the change `base..head` is in `ref`, by git's own equivalence in this order: the head is an ancestor of the ref; every commit
 * of `base..head` has its patch upstream (`git cherry`), which survives a rebase; every path the change touches holds the same content
 * at the ref as at the head, which covers a squash. A head that adds nothing over `base` has nothing to land.
 */
export function standing(repo: string, ref: string, head: string, base: string): Standing {
	const total = aheadOf(repo, base, head);
	if (total === 0) return { upstream: 0, total: 0 };
	if (git(repo, ["merge-base", "--is-ancestor", head, ref]) !== undefined) return { rule: "ancestor", upstream: total, total };
	const cherry = (git(repo, ["cherry", ref, head, base]) ?? "").split("\n").filter(Boolean);
	const upstream = cherry.filter((line) => line.startsWith("-")).length;
	if (cherry.length > 0 && upstream === cherry.length) return { rule: "patch-id", upstream, total: cherry.length };
	const paths = (git(repo, ["diff", "--name-only", base, head]) ?? "").split("\n").filter(Boolean);
	if (paths.length > 0 && paths.length <= 2000) {
		let same = true;
		for (let i = 0; i < paths.length && same; i += 200) same = git(repo, ["diff", "--name-only", head, ref, "--", ...paths.slice(i, i + 200)]) === "";
		if (same) return { rule: "content", upstream: total, total };
	}
	return { upstream, total: cherry.length || total };
}

/** What watches one ref: the directory git queries run in, and the ref name there. */
type Watch = { key: string; dir: string; ref: string };

/** A branch whose landing is watched: a linked worker's branch, or the coordinator's own commits. */
type Candidate = { key: string; dir: string; ref: string; label: string; child?: string; head: string; base: string; repo: string };

const watchKey = (dir: string, ref: string): string => `${dir}\0${ref}`;

function linkEntries(entries: Entry[]): Entry[] {
	const latest = new Map<string, Entry>();
	for (const entry of entries) if (entry.stage === "link" && typeof entry.child === "string") latest.set(entry.child, entry);
	return [...latest.values()];
}

function landedKeys(entries: Entry[]): Set<string> {
	return new Set(entries.filter((entry) => entry.stage === "land" && entry.verified !== false).map((entry) => `${String(entry.child ?? "self")}\0${String(entry.head ?? "")}`));
}

// The integration ref of a repo is looked up once per session: it changes only when the user retargets the branch.
const ownRefCache = new Map<string, string | undefined>();
function ownRef(repo: string): string | undefined {
	if (!ownRefCache.has(repo)) ownRefCache.set(repo, integrationRef(repo, {}));
	return ownRefCache.get(repo);
}

/** The ref of each own base's repo, which a push of the coordinator's own commits moves. */
function ownRefs(entries: Entry[]): Watch[] {
	const found: Watch[] = [];
	for (const base of ownBases(entries)) {
		if (!existsSync(base.repo)) continue;
		const ref = ownRef(base.repo);
		if (ref) found.push({ key: watchKey(base.repo, ref), dir: base.repo, ref });
	}
	return found;
}

/** Every ref the book watches: the integration ref of each linked worker that has not landed, and of each own repo; none without a linked worker. */
function watched(entries: Entry[]): Watch[] {
	// A session that spawned no linked child has nothing to land: it is read as a plain session, with no git calls for landings.
	if (linkEntries(entries).length === 0) return [];
	const landedChildren = new Set(entries.filter((entry) => entry.stage === "land" && entry.verified !== false && typeof entry.child === "string").map((entry) => String(entry.child)));
	const found = new Map<string, Watch>();
	for (const link of linkEntries(entries)) {
		if (typeof link.ref !== "string" || typeof link.cwd !== "string" || landedChildren.has(String(link.child))) continue;
		found.set(watchKey(link.cwd, link.ref), { key: watchKey(link.cwd, link.ref), dir: link.cwd, ref: link.ref });
	}
	for (const own of ownRefs(entries)) found.set(own.key, own);
	return [...found.values()];
}

/** The last tip seen for a watch: the latest `watch` entry, else the tip a link recorded when it was spawned. */
function lastSeen(entries: Entry[], watch: Watch): string | undefined {
	const seen = [...entries].reverse().find((entry) => entry.stage === "watch" && entry.key === watch.key);
	if (seen) return String(seen.sha);
	const link = linkEntries(entries).find((entry) => entry.cwd === watch.dir && entry.ref === watch.ref && typeof entry.refSha === "string");
	return link ? String(link.refSha) : undefined;
}

/**
 * True when the last move of a remote-tracking ref was a fetch or pull (the reflog subject is `fetch…` or `pull…`) rather than this
 * checkout's own push (`update by push`): the ref then holds what others landed. Undefined for a ref that is not remote-tracking or has no reflog.
 */
function movedByFetch(dir: string, ref: string): boolean | undefined {
	const full = git(dir, ["rev-parse", "--symbolic-full-name", ref]);
	if (!full?.startsWith("refs/remotes/")) return undefined;
	const subject = git(dir, ["reflog", "-1", "--format=%gs", full]);
	if (!subject) return undefined;
	return !subject.startsWith("update by push");
}

/** The tip of each watch, one `for-each-ref` per directory; a ref that is not a branch name falls back to its own lookup. */
function tipsOf(watches: Watch[]): Map<string, string> {
	const tips = new Map<string, string>();
	const byDir = new Map<string, Watch[]>();
	for (const watch of watches) byDir.set(watch.dir, [...(byDir.get(watch.dir) ?? []), watch]);
	for (const [dir, group] of byDir) {
		const patterns = group.flatMap((watch) => [`refs/remotes/${watch.ref}`, `refs/heads/${watch.ref}`]);
		const listed = new Map<string, string>();
		for (const line of (git(dir, ["for-each-ref", "--format=%(objectname) %(refname:short)", ...patterns]) ?? "").split("\n")) {
			const [sha, name] = line.split(" ");
			if (sha && name) listed.set(name, sha);
		}
		for (const watch of group) {
			const tip = listed.get(watch.ref) ?? refSha(dir, watch.ref);
			if (tip) tips.set(watch.key, tip);
		}
	}
	return tips;
}

/**
 * The tip of every watched ref now, recording a baseline for a ref seen the first time. Taken before a bash call, so the call's own
 * moves of a ref can be told from moves made elsewhere.
 */
export function watchTips(book: Book): Record<string, string> {
	const tips: Record<string, string> = {};
	const watches = watched(book.entries);
	const now = tipsOf(watches);
	for (const watch of watches) {
		const tip = now.get(watch.key);
		if (!tip) continue;
		tips[watch.key] = tip;
		if (lastSeen(book.entries, watch) === undefined) book.entries.push(appendEntry(book.path, "watch", { key: watch.key, ref: watch.ref, sha: tip }));
	}
	return tips;
}

// Reflog subjects of the operations that create commits: a commit, cherry-pick, revert, am, a rebase that replays commits, a merge that is not a fast-forward.
const MAKES_COMMITS = /^(commit|cherry-pick|revert|am)\b|\((pick|squash|fixup|reword|edit|merge)\)|^merge .*: (?!Fast-forward)/;

/**
 * Whether the branch ever held a commit made on it, read from its reflog: false for a branch that only started from a base and moved
 * forward to what a ref already held (a fetch and fast-forward), which has nothing of its own to land. Undefined when no reflog says.
 */
function hasOwnCommits(repo: string, ref: string): boolean | undefined {
	const log = git(repo, ["reflog", "show", "--format=%gs", ref]);
	if (!log) return undefined;
	return log.split("\n").some((subject) => MAKES_COMMITS.test(subject));
}

/**
 * The branches that can land on `watch`: each linked worker's. With `ownBase`, the tip the ref had before a bash call that moved it,
 * also the coordinator's own commits that call may have pushed: the commits of `HEAD` the ref did not hold before.
 */
function candidatesOn(entries: Entry[], watch: Watch, ownBase?: string): Candidate[] {
	const found: Candidate[] = [];
	for (const link of linkEntries(entries)) {
		if (link.cwd !== watch.dir || link.ref !== watch.ref) continue;
		const worktree = link.worktree as Worktree | undefined;
		const tree = worktree?.path && existsSync(worktree.path) ? worktree.path : undefined;
		const repo = tree ?? watch.dir;
		const result = resultOf(entries, String(link.child));
		const head =
			(tree ? git(tree, ["rev-parse", "HEAD"]) : undefined) ??
			(typeof result?.headSha === "string" ? result.headSha : undefined) ??
			(worktree?.branch ? refSha(repo, `refs/heads/${worktree.branch}`) : undefined);
		const base = worktree?.baseSha ?? (typeof link.refSha === "string" ? link.refSha : undefined);
		if (!head || !base) continue;
		// A worker that never made a commit of its own (it only updated its branch from the ref) has nothing to land, whichever tip the ref took.
		if (hasOwnCommits(repo, worktree?.branch ? `refs/heads/${worktree.branch}` : "HEAD") === false) continue;
		found.push({ key: watch.key, dir: watch.dir, ref: watch.ref, label: String(link.name ?? link.child), child: String(link.child), head, base, repo });
	}
	if (ownBase !== undefined && existsSync(watch.dir) && ownBases(entries).some((base) => base.repo === watch.dir)) {
		const head = git(watch.dir, ["rev-parse", "HEAD"]);
		if (head) found.push({ key: watch.key, dir: watch.dir, ref: watch.ref, label: "this session", head, base: ownBase, repo: watch.dir });
	}
	return found;
}

/** The latest passing check of the child's run of the coordinator's anchor, or any passing check when the coordinator has no command anchor. */
function childPassingRun(book: Book, child: string): { name: string; run: Entry } | undefined {
	const cwd = String(book.header.cwd ?? "");
	const here = cwd ? repoRootOf(join(cwd, "_")) : undefined;
	const roots = [...ownBases(book.entries).map((base) => base.repo), ...(here ? [here] : [])];
	return passingRunOf(book.entries, child, anchorCommand(book.entries), roots, cwd);
}

/** The landings recorded so far, newest last, for `read`. */
export function landLines(entries: Entry[]): string[] {
	return entries
		.filter((entry) => entry.stage === "land" && entry.verified !== false)
		.map((entry) => `landed ${String(entry.label ?? entry.child ?? "this session")} in ${String(entry.ref)} (${String(entry.rule)}; ${entry.exact === true ? "the tree its check ran on" : "not the tree its check ran on"}; ${entry.self === true ? "landed by this session" : "landed elsewhere"})`);
}

/** One `partial k/n` line for each linked worker whose change is in the ref only in part, read from git now. */
export function partialLines(entries: Entry[]): string[] {
	const done = landedKeys(entries);
	const lines: string[] = [];
	for (const watch of watched(entries)) {
		for (const candidate of candidatesOn(entries, watch)) {
			if (done.has(`${candidate.child ?? "self"}\0${candidate.head}`) || candidate.child === undefined) continue;
			const now = standing(candidate.repo, candidate.ref, candidate.head, candidate.base);
			if (!now.rule && now.upstream > 0) lines.push(`${candidate.label}: partial ${now.upstream}/${now.total} in ${candidate.ref}`);
		}
	}
	return lines;
}

/**
 * Compares every watched ref with what the book last saw. A ref that moved is tested against each branch not yet landed on it, and a
 * proven landing is recorded as a `land` entry. `before` holds the tips taken before the bash call that just ran: a ref that moved
 * inside that call was moved by this session (`self`), any other move was made elsewhere. Returns the landings recorded.
 */
export function checkLandings(book: Book, before: Record<string, string> = {}): Entry[] {
	const recorded: Entry[] = [];
	const watches = watched(book.entries);
	const now = tipsOf(watches);
	for (const watch of watches) {
		const tip = now.get(watch.key);
		const last = lastSeen(book.entries, watch);
		if (!tip || tip === last) continue;
		book.entries.push(appendEntry(book.path, "watch", { key: watch.key, ref: watch.ref, sha: tip }));
		const self = before[watch.key] !== undefined && before[watch.key] !== tip && movedByFetch(watch.dir, watch.ref) !== true;
		const done = landedKeys(book.entries);
		const tipTree = git(watch.dir, ["rev-parse", `${tip}^{tree}`]);
		// The coordinator's own commits count only for a push this session made, and not when a worker's landing already explains the move.
		let explained = false;
		// Only a remote-tracking ref whose last move was `update by push` is proof of a push: a pull on a local branch, or a ref with no reflog, proves nothing.
		const own = self && movedByFetch(watch.dir, watch.ref) === false ? before[watch.key] : undefined;
		for (const candidate of candidatesOn(book.entries, watch, own)) {
			if (done.has(`${candidate.child ?? "self"}\0${candidate.head}`)) continue;
			if (candidate.child === undefined && explained) continue;
			// A worker whose head the ref already held before this move brought nothing to it (it only updated its branch from the ref).
			if (candidate.child !== undefined && last !== undefined && aheadOf(candidate.repo, last, candidate.head) === 0) continue;
			const found = standing(candidate.repo, candidate.ref, candidate.head, candidate.base);
			if (!found.rule) continue;
			if (candidate.child !== undefined) explained = true;
			const run = candidate.child ? childPassingRun(book, candidate.child) : undefined;
			const checked = new Set(Array.isArray(run?.run.trees) ? (run?.run.trees as unknown[]).map(String) : []);
			const exact = candidate.child ? tipTree !== undefined && checked.has(tipTree) : tipTree !== undefined && git(candidate.repo, ["rev-parse", "HEAD^{tree}"]) === tipTree;
			const land = appendEntry(book.path, "land", {
				...(candidate.child ? { child: candidate.child } : {}),
				label: candidate.label,
				ref: candidate.ref,
				sha: tip,
				head: candidate.head,
				rule: found.rule,
				exact,
				self,
				verified: true,
			});
			book.entries.push(land);
			recorded.push(land);
			adoptLanded(book, candidate, run, exact, self);
		}
	}
	return recorded;
}

/**
 * Records the landed child's passing run of the anchor as the coordinator's verify (the worker's run stands, since the integrator's
 * own gates ran on the integrated head), unless the coordinator pushed it itself and the ref differs from what the run checked, or the
 * coordinator changed code of its own since it spawned the child.
 */
function adoptLanded(book: Book, candidate: Candidate, run: { name: string; run: Entry } | undefined, exact: boolean, self: boolean): void {
	if (!run || (self && !exact)) return;
	const linkAt = book.entries.findIndex((entry) => entry.stage === "link" && entry.child === candidate.child);
	if (book.entries.slice(linkAt + 1).some((entry) => entry.stage === "edit")) return;
	const last = `adopted from ${run.name}${run.run.last ? `: ${String(run.run.last)}` : ""}`.slice(0, 200);
	book.entries.push(appendEntry(book.path, "verify", { command: String(run.run.command ?? "").slice(0, 200), exit: 0, last, adopted: run.name, landed: true, ...(candidate.child ? { child: candidate.child } : {}) }));
}

export type Declared = { ok: boolean; text: string };

/**
 * An owner's landed notice. It counts only when git agrees: `sha`, when given, is in `ref`, and each branch not yet landed is proven
 * landed by the rules. A notice git cannot confirm is recorded `verified: false` and says to fetch the ref and declare again.
 */
export function declareLanded(book: Book, params: { sha?: string; ref?: string; note?: string; children?: string[] }): Declared {
	const watches = watched(book.entries);
	const wanted = params.ref ? watches.filter((watch) => watch.ref === params.ref) : watches;
	const ref = params.ref ?? wanted[0]?.ref;
	const dir = wanted[0]?.dir;
	const base = { ...(params.sha ? { declaredSha: params.sha } : {}), ...(params.note ? { note: params.note } : {}), declared: true, ...(ref ? { ref } : {}) };
	const unconfirmed = (why: string): Declared => {
		book.entries.push(appendEntry(book.path, "land", { ...base, self: false, exact: false, verified: false }));
		return { ok: false, text: `not confirmed: ${why}; it does not count as a landing. Fetch ${ref ?? "the integration ref"} (git fetch), then declare it again.` };
	};
	if (!ref || !dir) return unconfirmed("no integration ref is watched for this loop (give `ref`)");
	const tip = refSha(dir, ref);
	if (!tip) return unconfirmed(`${ref} does not resolve here`);
	// With no `ref` given, the sha must be in every watched ref, since it is not said which one it landed in.
	for (const watch of params.sha ? (params.ref ? [{ dir, ref }] : wanted) : []) {
		const at = refSha(watch.dir, watch.ref);
		if (!at || refSha(watch.dir, params.sha as string) === undefined || git(watch.dir, ["merge-base", "--is-ancestor", params.sha as string, at]) === undefined) return unconfirmed(`${(params.sha as string).slice(0, 12)} is not in ${watch.ref} here`);
	}
	const done = landedKeys(book.entries);
	const lines: string[] = [];
	for (const watch of wanted) {
		const watchTip = refSha(watch.dir, watch.ref) ?? tip;
		const watchTree = git(watch.dir, ["rev-parse", `${watchTip}^{tree}`]);
		for (const candidate of candidatesOn(book.entries, watch)) {
			if (done.has(`${candidate.child ?? "self"}\0${candidate.head}`)) continue;
			if (params.children && candidate.child !== undefined && !params.children.includes(candidate.child)) continue;
			const found = standing(candidate.repo, candidate.ref, candidate.head, candidate.base);
			if (!found.rule) {
				lines.push(`${candidate.label}: ${found.total > 0 ? `${found.upstream}/${found.total} of its commits are in ${candidate.ref}` : "nothing to land"}`);
				continue;
			}
			const run = candidate.child ? childPassingRun(book, candidate.child) : undefined;
			const checked = new Set(Array.isArray(run?.run.trees) ? (run?.run.trees as unknown[]).map(String) : []);
			const exact = candidate.child ? watchTree !== undefined && checked.has(watchTree) : false;
			book.entries.push(
				appendEntry(book.path, "land", {
					...base,
					...(candidate.child ? { child: candidate.child } : {}),
					label: candidate.label,
					ref: candidate.ref,
					sha: watchTip,
					head: candidate.head,
					rule: found.rule,
					exact,
					self: false,
					verified: true,
				}),
			);
			adoptLanded(book, candidate, run, exact, false);
			lines.push(`${candidate.label}: landed in ${candidate.ref} (${found.rule})`);
		}
	}
	const prior = book.entries.filter((entry) => entry.stage === "land" && entry.verified !== false && entry.ref === ref);
	if (lines.length === 0 && prior.length > 0 && (!params.sha || prior.some((entry) => entry.sha === tip || entry.declaredSha === params.sha || entry.sha === params.sha))) {
		return { ok: true, text: `already recorded: ${prior.map((entry) => `${String(entry.label ?? "landing")} (${String(entry.rule)})`).join("; ")} in ${ref}` };
	}
	if (lines.length === 0 || !lines.some((line) => line.includes("landed in"))) {
		if (params.sha) {
			// The notice names a commit that is in the ref, but no watched branch is proven to be part of it.
			book.entries.push(appendEntry(book.path, "land", { ...base, rule: "declared", sha: tip, self: false, exact: false, verified: true }));
			return { ok: true, text: `recorded: ${params.sha.slice(0, 12)} is in ${ref}${lines.length ? `; ${lines.join("; ")}` : ""}` };
		}
		return unconfirmed(lines.length ? lines.join("; ") : `no branch waits to land on ${ref}`);
	}
	return { ok: true, text: `recorded: ${lines.join("; ")}` };
}
