/**
 * Sweeps the project dirs of removed checkouts from the books root. Every checkout (each worktree of each repo) has its own project
 * dir, and a worktree that is removed leaves its dir behind while a living main session still links the child books in it, so the
 * root grows with the worktrees ever used and every scan of it grows too. The sweep runs at session start, at most once a day.
 */

import { appendFileSync, existsSync, lstatSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join } from "node:path";
import { STALE_BOOK_MS, booksRoot, childBooksChanged, isClosed, parseBook } from "./book.ts";
import { outDispatches } from "./units.ts";

/** How often the sweep may run: one day, tracked by the mtime of a stamp file beside the books root. */
export const PROJECT_SWEEP_INTERVAL_MS = 24 * 60 * 60 * 1000;

/**
 * How long nothing under a project dir may have been written before the dir can go: the age at which the book sweep already
 * treats a book as stale. A shorter idle time would remove a dir the book sweep still counts as live; a longer one only keeps
 * the clutter of a removed checkout longer.
 */
export const PROJECT_IDLE_MS = STALE_BOOK_MS;

export type RemovedProject = { project: string; cwds: string[]; idleDays: number; books: number };
export type ProjectSweep = { ran: boolean; removed: RemovedProject[]; log: string };

/** The stamp and the log sit beside the books root, never in it, so no scan of the root meets them. */
const stampPath = (root: string): string => join(dirname(root), "books-sweep.stamp");
const logPath = (root: string): string => join(dirname(root), "books-sweep.log");

/** True only when the path is known to be absent: any other failure (permissions, an unreadable mount) leaves it standing. */
function pathGone(path: string): boolean {
	if (!isAbsolute(path)) return false;
	try {
		statSync(path);
		return false;
	} catch (error) {
		const code = (error as NodeJS.ErrnoException).code;
		return code === "ENOENT" || code === "ENOTDIR";
	}
}

/** Every regular file under `dir` with its mtime, not following symlinks. */
function filesUnder(dir: string): { path: string; mtimeMs: number }[] {
	const found: { path: string; mtimeMs: number }[] = [];
	for (const name of readdirSync(dir)) {
		const path = join(dir, name);
		const info = lstatSync(path);
		if (info.isDirectory()) found.push(...filesUnder(path));
		else if (info.isFile()) found.push({ path, mtimeMs: info.mtimeMs });
	}
	return found;
}

/** What removing `dir` would remove, or undefined when any condition for removing it fails. */
function removable(dir: string, now: number): Omit<RemovedProject, "project"> | undefined {
	if (!lstatSync(dir).isDirectory()) return undefined;
	const files = filesUnder(dir);
	if (files.length === 0) return undefined;
	const newest = Math.max(...files.map((file) => file.mtimeMs));
	// A write later than now (a clock set back) counts as recent.
	if (now - newest < PROJECT_IDLE_MS) return undefined;
	const books = files.filter((file) => file.path.endsWith(".yml")).map((file) => parseBook(file.path));
	// A book that cannot be read says nothing about its loop or its path, so the dir stays.
	if (books.length === 0 || books.some((book) => book === undefined)) return undefined;
	const parsed = books.filter((book) => book !== undefined);
	const cwds = [...new Set(parsed.map((book) => book.header.cwd).filter((cwd): cwd is string => typeof cwd === "string" && cwd !== ""))];
	// A book that records no path gives no proof the checkout is gone; one that does decides, and every path it records must be gone.
	if (cwds.length === 0 || !cwds.every(pathGone)) return undefined;
	if (parsed.some((book) => !isClosed(book))) return undefined;
	if (parsed.some((book) => outDispatches(book.entries).length > 0)) return undefined;
	return { cwds, idleDays: Math.floor((now - newest) / (24 * 60 * 60 * 1000)), books: parsed.length };
}

/**
 * Removes the project dirs of removed checkouts under the books root, at most once a day. A dir goes only when every path its books
 * record as their cwd is gone, no book under it is an open loop (one that is not closed) or has a dispatch still out, nothing under
 * it was written for `PROJECT_IDLE_MS`, and it is not `current`, the calling session's own project. Each removal is logged to
 * `books-sweep.log` beside the root before the dir is removed. The day's run is claimed by touching the stamp first, so sessions
 * starting together sweep once; a stamp that cannot be written is an error, not a sweep with no throttle.
 */
export function sweepProjectDirs(env: NodeJS.ProcessEnv = process.env, current?: string, now = Date.now()): ProjectSweep {
	const root = booksRoot(env);
	const result: ProjectSweep = { ran: false, removed: [], log: logPath(root) };
	if (!existsSync(root)) return result;
	const stamp = stampPath(root);
	try {
		const age = now - statSync(stamp).mtimeMs;
		if (age >= 0 && age < PROJECT_SWEEP_INTERVAL_MS) return result;
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
	}
	writeFileSync(stamp, `${new Date(now).toISOString()}\n`);
	result.ran = true;
	for (const project of readdirSync(root)) {
		if (project === current) continue;
		const dir = join(root, project);
		let found: Omit<RemovedProject, "project"> | undefined;
		try {
			found = removable(dir, now);
		} catch {
			// The dir vanished or cannot be read (another session tidied it, or permissions): it stays, and the rest of the root still counts.
			continue;
		}
		if (!found) continue;
		// A log that cannot be written, or a dir that cannot be removed, stops the sweep with the error.
		appendFileSync(result.log, `${new Date(now).toISOString()} swept ${project} (cwd ${found.cwds.join(", ")}; ${found.books} book${found.books === 1 ? "" : "s"}; idle ${found.idleDays} days)\n`);
		rmSync(dir, { recursive: true, force: true });
		childBooksChanged();
		result.removed.push({ project, ...found });
	}
	return result;
}
