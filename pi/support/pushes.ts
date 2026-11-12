/**
 * Reading a bash command for the `git push` it runs. Only a push the command names is a candidate for a car: git still decides
 * what moved (`pushedSince`), the command only says which refs of another branch the call asked to push. This is no anchor recognition.
 */

// A value that follows an option: quoted (`-c 'credential.helper=!glab auth git-credential'`, `-C "a b"`) or one word.
const VALUE = String.raw`(?:'[^']*'|"[^"]*"|\S+)`;
// Only global options stand between `git` and `push` (a stash push is none): `-c`/`-C` and the long options that take a separate value
// each carry one value, the rest are flags or `--name=value`.
const GLOBALS = String.raw`(?:\s+(?:-[Cc]\s+${VALUE}|--(?:git-dir|work-tree|namespace|super-prefix|exec-path|config-env)\s+${VALUE}|--?[A-Za-z][\w-]*(?:=\S*)?))*`;
// A bash call that may push: `git`, or a path ending in `/git`, then the global options, then `push`; a `--dry-run` or `-n` push moves no ref.
const HEAD = String.raw`(?<![\w./-])(?:\S*/)?git${GLOBALS}\s+push\b`;
const DRY = String.raw`(?![^|;&\n]*\s(?:--dry-run|-n)(?![\w-]))`;

export const PUSH = new RegExp(HEAD + DRY);
const PUSH_ARGS = new RegExp(`${HEAD}${DRY}([^|;&\\n]*)`, "g");

/** The options of `git push` that take their value as the next word. */
const TAKES_VALUE = new Set(["-o", "--push-option", "--repo", "--receive-pack", "--exec"]);

/** A branch a push command names as the destination of a refspec, on the remote it names when it names one. */
export type NamedRef = { remote?: string; branch: string };

/** The destinations of the refspecs after the remote in each push of `command` (`origin agent/x`, `HEAD:refs/heads/x`, `src:dst` → `dst`). */
export function pushRefspecs(command: string): NamedRef[] {
	const named: NamedRef[] = [];
	for (const found of command.matchAll(PUSH_ARGS)) {
		const words = (found[1].match(/'[^']*'|"[^"]*"|\S+/g) ?? []).map((word) => word.replace(/^(['"])(.*)\1$/, "$2"));
		const positional: string[] = [];
		for (let i = 0; i < words.length; i++) {
			if (words[i].startsWith("-")) {
				if (TAKES_VALUE.has(words[i])) i++;
			} else positional.push(words[i]);
		}
		const [remote, ...specs] = positional;
		for (const spec of specs) {
			const destination = spec.replace(/^\+/, "").split(":").at(-1) ?? "";
			const branch = destination.replace(/^refs\/heads\//, "");
			if (branch && branch !== "HEAD") named.push({ remote, branch });
		}
	}
	return named;
}
