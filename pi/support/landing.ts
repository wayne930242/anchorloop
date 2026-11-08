/**
 * Where a worker's change stands against the ref it will land on. Pure git over the repo's refs: no bash command text is read,
 * so how a landing happened (push, merge, fetch, an integrator elsewhere) never matters, only what the ref holds afterwards.
 */

import { existsSync } from "node:fs";
import type { Worktree } from "./host.ts";
import { type Entry, git } from "./book.ts";

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
