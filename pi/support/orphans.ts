/** Children the loop spawned whose result never arrived (a restart dropped the host's watchers): what the host and git can still say about each. */

import { existsSync } from "node:fs";
import { type Entry, findChildBooks, git, isClosed, stagesDone } from "./book.ts";
import { type Link, liveness } from "./host.ts";

/** The links of the book with no `result` entry. A link with no `cwd` (recorded by an older version) comes from a book that kept no results, so its result is unknown, not missing. */
export function pendingLinks(entries: Entry[]): Entry[] {
	const latest = new Map<string, Entry>();
	for (const entry of entries) if (entry.stage === "link" && typeof entry.child === "string") latest.set(entry.child, entry);
	const returned = new Set(entries.filter((entry) => entry.stage === "result" && typeof entry.child === "string").map((entry) => String(entry.child)));
	return [...latest.values()].filter((link) => !returned.has(String(link.child)));
}

function bookState(child: string, env: NodeJS.ProcessEnv): string {
	const books = findChildBooks(child, env);
	const last = books.at(-1)?.book;
	if (!last) return "no child book";
	const check = [...last.entries].reverse().find((entry) => entry.stage === "check" || entry.stage === "verify");
	const closed = isClosed(last) ? `closed (${String(last.entries.at(-1)?.verdict ?? "no verdict")})` : stagesDone(last.entries).length ? "open" : "open, empty";
	return `child book ${closed}${check ? `, check exit ${String(check.exit ?? "unknown")}` : ""}`;
}

function worktreeState(link: Entry): string | undefined {
	const worktree = link.worktree as { path?: string; branch?: string; baseSha?: string } | undefined;
	if (!worktree?.branch) return undefined;
	if (!worktree.path || !existsSync(worktree.path)) return `worktree ${worktree.branch} gone`;
	const ahead = worktree.baseSha ? git(worktree.path, ["rev-list", "--count", `${worktree.baseSha}..HEAD`]) : undefined;
	return `worktree ${worktree.branch}${ahead !== undefined ? ` ahead ${ahead}` : ""}`;
}

/** One line per child without a result: `name: no result; process <alive|gone|unknown>; <child book state>; <worktree state>`. */
export function orphanLines(entries: Entry[], env: NodeJS.ProcessEnv = process.env): string[] {
	return pendingLinks(entries).map((link) => {
		const alive = liveness(link as unknown as Link);
		return [`${String(link.name ?? link.child)}: ${typeof link.cwd === "string" ? "no result" : "result unknown (link has no cwd)"}`, `process ${alive}`, bookState(String(link.child), env), worktreeState(link)].filter(Boolean).join("; ");
	});
}
