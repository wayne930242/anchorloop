/**
 * Port of hooks/validators/*.py and the routing in hooks/validate_tool_use.py:
 * checks an edited file against skill compactness, direct expected behavior, and
 * durable review standards, so the pi extension needs no Python on the machine.
 * Behavior mirrors the Python validators; tests/test_validator_parity.py compares them.
 */

import { existsSync, readdirSync, readFileSync, realpathSync, statSync } from "node:fs";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";

// ---- constants (hooks/validators/constants.py) ----

const SKILL_ALLOWED_FIELDS = new Set(["name", "description"]);
const SKILL_MAX_RECOMMENDED_LINES = 300;

const DEFENSIVE_PATTERNS = [
	"never under any circumstances",
	"under no circumstances",
	"you must never ever",
	"do not under any condition",
	"strict red line",
	"absolute red line",
	"prohibited at all costs",
	"zero tolerance for any",
	"absolutely forbidden to ever",
	"無限多的紅線",
	"千萬不要",
	"嚴禁在任何情況下",
	"絕對不可",
];

// Python's \b treats every letter, digit, and underscore as a word character; JS's \b is ASCII only.
const WORD = "[\\p{L}\\p{N}_]";
const wordAround = (alternatives: string) => `(?<!${WORD})(?:${alternatives})(?!${WORD})`;

const RED_LINE_MARKERS = new RegExp(
	`${wordAround("never|must not|do not|don't|forbidden|barred|prohibited|avoid")}|不要|禁止|不得|不准|嚴禁`,
	"giu",
);
const MAX_ADVISORIES = 3;
const RED_LINE_MIN_BUDGET = 3;
const RED_LINE_DENSITY = 0.1;
const EMPHATIC_WORDS = new RegExp(wordAround("(NEVER|ALWAYS|MUST NOT|MUST|FORBIDDEN|DO NOT)"), "gu");
const REASON_WORDS = new RegExp(`${wordAround("because|otherwise|so that|since")}|否則|因為|以免`, "iu");

const VALID_VERIFICATION_RESULTS = new Set(["pass", "fail", "unknown"]);

// ---- Python-compatible string and file helpers ----

/** Python str.splitlines(): splits on the same line boundaries and drops a trailing empty line. */
function splitlines(text: string): string[] {
	const lines = text.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);
	if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
	return lines;
}

/** Python str.strip(chars): removes any of `chars` from both ends. */
function stripChars(text: string, chars: string): string {
	let start = 0;
	let end = text.length;
	while (start < end && chars.includes(text[start])) start++;
	while (end > start && chars.includes(text[end - 1])) end--;
	return text.slice(start, end);
}

/** Path.read_text(encoding="utf-8"): strict UTF-8, BOM kept, newlines translated to \n. */
function readText(path: string): string {
	const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
	return decoder.decode(readFileSync(path)).replace(/\r\n?/g, "\n");
}

/** Path.resolve(): absolute, symlinks resolved through the nearest existing parent. */
function real(path: string): string {
	const absolute = resolve(path);
	if (existsSync(absolute)) return realpathSync(absolute);
	const parent = dirname(absolute);
	return parent === absolute ? absolute : join(real(parent), basename(absolute));
}

function within(root: string, target: string): boolean {
	const rel = relative(root, target);
	return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

const isDirectory = (path: string) => {
	try {
		return statSync(path).isDirectory();
	} catch {
		return false;
	}
};

const errorMessage = (error: unknown) => (error instanceof Error ? error.message : String(error));

// ---- utils (hooks/validators/utils.py) ----

function parseFrontmatter(text: string): Map<string, string> | undefined {
	if (!text.startsWith("---")) return undefined;
	const end = text.indexOf("\n---", 3);
	if (end === -1) return undefined;
	const block = text.slice(3, end).trim();
	const result = new Map<string, string>();
	let currentKey: string | undefined;
	let currentVal: string[] = [];

	for (const line of splitlines(block)) {
		if (!line.trim() || line.trim().startsWith("#")) continue;
		const match = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
		if (match && !line.startsWith(" ")) {
			if (currentKey !== undefined) result.set(currentKey, stripChars(currentVal.join("\n").trim(), "\"'"));
			currentKey = match[1];
			const rawVal = match[2].trim();
			currentVal = rawVal ? [rawVal] : [];
		} else if (currentKey !== undefined) {
			currentVal.push(line.trim());
		}
	}
	if (currentKey !== undefined) result.set(currentKey, stripChars(currentVal.join("\n").trim(), "\"'"));
	return result;
}

function extractMarkdownLinks(text: string): string[] {
	const stripped = text.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]+`/g, "");
	const links: string[] = [];
	for (const match of stripped.matchAll(/\[(?:[^\]]*)\]\(([^)#\s]+)(?:#[^)]*)?\)/g)) links.push(match[1]);
	return links.filter((link) => !/^[a-zA-Z]+:\/\//.test(link) && !link.startsWith("mailto:"));
}

/** Blank out fenced and inline code while keeping line numbers stable. */
function stripCode(text: string): string {
	const fenced = text.replace(/```[\s\S]*?```/g, (block) => "\n".repeat(block.split("\n").length - 1));
	return fenced.replace(/`[^`\n]+`/g, "");
}

function findDefensivePhrases(text: string, patterns: string[]): string[] {
	const stripped = stripCode(text);
	return patterns.filter((pattern) => new RegExp(pattern, "iu").test(stripped));
}

// ---- rule files (rule_validator.py) ----

const SIMPLIFIED_CHINESE_CHARS = "为这就从时会过发对门书见长经说样开";

function checkRulesFile(path: string): string[] {
	const warnings: string[] = [];
	let text: string;
	try {
		text = readText(path);
	} catch (error) {
		return [`failed to read rule file: ${errorMessage(error)}`];
	}

	const found = findDefensivePhrases(text, DEFENSIVE_PATTERNS);
	if (found.length) {
		warnings.push(`detected defensive wording: ${found.join(", ")}`);
	}

	const lines = splitlines(text)
		.map((line) => line.trim())
		.filter((line) => line && !line.startsWith("#"));
	if (lines.length > 200) {
		warnings.push(`rule file has ${lines.length} non-empty lines (over 200)`);
	}

	const simplified = [...SIMPLIFIED_CHINESE_CHARS].filter((char) => text.includes(char));
	if (simplified.length) {
		warnings.push(`possible Simplified Chinese detected (${simplified.slice(0, 5).join("")})`);
	}
	return warnings;
}

// ---- SKILL.md (skill_validator.py) ----

function checkSkillMd(path: string): string[] {
	const warnings: string[] = [];
	let text: string;
	try {
		text = readText(path);
	} catch (error) {
		return [`failed to read SKILL.md: ${errorMessage(error)}`];
	}

	const skillDir = dirname(path);
	const lines = splitlines(text);

	const fields = parseFrontmatter(text);
	if (!fields) {
		warnings.push("missing or invalid YAML frontmatter (--- ... ---)");
	} else {
		const extra = [...fields.keys()].filter((key) => !SKILL_ALLOWED_FIELDS.has(key)).sort();
		if (extra.length) warnings.push(`extra frontmatter fields: ${extra.join(", ")}`);

		if (!fields.has("name") || !fields.get("name")!.trim()) warnings.push("missing required frontmatter field: 'name'");

		// The regex parser accepts what pi's YAML parser rejects, and pi then skips the whole skill.
		for (const key of ["name", "description"]) {
			const line = lines.slice(1).find((candidate) => candidate.startsWith(`${key}:`));
			const raw = line === undefined ? "" : line.slice(line.indexOf(":") + 1).trim();
			if (raw && !"\"'|>".includes(raw[0]) && (raw.includes(": ") || raw.includes(" #"))) {
				warnings.push(`quote the ${key}: YAML reads an unquoted ': ' or ' #' as syntax, and pi skips the skill`);
			}
		}

		if (!fields.has("description") || !fields.get("description")!.trim()) {
			warnings.push("missing required frontmatter field: 'description'");
		} else if (!fields.get("description")!.toLowerCase().includes("use when")) {
			warnings.push("description should specify trigger criteria (include 'Use when...')");
		}
	}

	if (lines.length > SKILL_MAX_RECOMMENDED_LINES && !isDirectory(join(skillDir, "references"))) {
		warnings.push(`skill has ${lines.length} lines (over ${SKILL_MAX_RECOMMENDED_LINES}) and no references/`);
	}

	// Broken markdown links, followed through every Markdown file SKILL.md reaches.
	const root = real(skillDir);
	const self = real(path);
	const reached = new Map<string, string>([[self, text]]);
	const linked = new Set<string>();
	const pending = [self];
	while (pending.length) {
		const source = pending.pop()!;
		for (const link of extractMarkdownLinks(reached.get(source)!)) {
			const target = real(join(dirname(source), link));
			if (!existsSync(target)) {
				const where = source === self ? "" : ` (in ${relative(root, source).replaceAll("\\", "/")})`;
				warnings.push(`broken local link: ${link}${where}`);
				continue;
			}
			linked.add(target);
			if (target.endsWith(".md") && within(root, target) && !reached.has(target)) {
				reached.set(target, readText(target));
				pending.push(target);
			}
		}
	}

	// Orphaned files.
	const corpus = [...reached.values()].join("\n");
	const walk = (dir: string): string[] =>
		readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
			const full = join(dir, entry.name);
			return entry.isDirectory() ? walk(full) : [full];
		});
	for (const file of walk(skillDir)) {
		if (file === path || isDirectory(file)) continue;
		const rel = relative(skillDir, file).replaceAll("\\", "/");
		if (!(linked.has(real(file)) || corpus.includes(rel) || corpus.includes(basename(file)))) {
			warnings.push(`orphaned file not referenced in SKILL.md: ${rel}`);
		}
	}

	const defensive = findDefensivePhrases(text, DEFENSIVE_PATTERNS);
	if (defensive.length) {
		warnings.push(`detected defensive anti-pattern(s): ${defensive.join(", ")}`);
	}
	return warnings;
}

/** Red-line advisories for the author; they never count as validation failures. */
function checkSkillAdvisories(path: string): string[] {
	let text: string;
	try {
		text = readText(path);
	} catch {
		return [];
	}

	const body = stripCode(text);
	const lines = splitlines(body);
	const advisories: string[] = [];

	const markers = (body.match(RED_LINE_MARKERS) ?? []).length;
	const budget = Math.max(RED_LINE_MIN_BUDGET, Math.floor(lines.filter((line) => line.trim()).length * RED_LINE_DENSITY));
	if (markers > budget) {
		advisories.push(`${markers} red-line markers exceed the budget of ${budget}`);
	}

	const seen = new Map<string, number>();
	lines.forEach((line, index) => {
		for (const match of line.matchAll(EMPHATIC_WORDS)) {
			const word = match[1];
			seen.set(word, (seen.get(word) ?? 0) + 1);
			const window = lines.slice(index, index + 2).join(" ");
			if (!REASON_WORDS.test(window)) {
				advisories.push(`line ${index + 1}: emphatic '${word}' has no reason beside it`);
			}
		}
	});
	for (const [word, count] of seen) {
		if (count > 1) {
			advisories.push(`emphatic '${word}' appears ${count} times`);
		}
	}
	return advisories.slice(0, MAX_ADVISORIES);
}

// ---- durable specs (durable_validator.py) ----

function checkDecisionMd(path: string): string[] {
	const warnings: string[] = [];
	const text = readText(path);
	if (!/\|\s*Question\s*\|\s*Answer\s*\|\s*Basis\s*\|\s*Status\s*\|/i.test(text)) {
		warnings.push("decision.md should include a Question | Answer | Basis | Status table (Status: grounded, confirmed, or open).");
	}
	return warnings;
}

function checkSpecMd(path: string): string[] {
	const warnings: string[] = [];
	const text = readText(path);
	if (!/Status:\s*(proposed|approved)/i.test(text)) {
		warnings.push("spec.md must declare 'Status: proposed' or 'Status: approved' at the top.");
	}
	return warnings;
}

function checkVerificationMd(path: string): string[] {
	const warnings: string[] = [];
	const text = readText(path);

	if (!/\|\s*Requirement\s*\|\s*Evidence\s*\|\s*Result\s*\|/i.test(text)) {
		warnings.push("verification.md must include a 'Requirement | Evidence | Result' table.");
	} else {
		const results = [...text.matchAll(/\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*([a-zA-Z]+)\s*\|/g)].map((match) => match[1].toLowerCase());
		const invalid = [...new Set(results.filter((result) => !VALID_VERIFICATION_RESULTS.has(result) && result !== "result"))];
		if (invalid.length) {
			warnings.push(`invalid verification Result values found: ${invalid.join(", ")} (use pass, fail, unknown)`);
		}
	}

	const defensive = findDefensivePhrases(text, DEFENSIVE_PATTERNS);
	if (defensive.length) {
		warnings.push(`detected defensive wording in verification/review: ${defensive.join(", ")}`);
	}
	return warnings;
}

function checkDurableSpec(path: string): string[] {
	const name = basename(path).toLowerCase();
	if (name === "decision.md" || name === "requirements.md") return checkDecisionMd(path);
	if (name === "spec.md") return checkSpecMd(path);
	if (name === "verification.md") return checkVerificationMd(path);
	return [];
}

// ---- routing (validate_tool_use.py) ----

/** Route a file to the validator its name and location call for. */
export function runValidation(path: string): string[] {
	const name = basename(path).toLowerCase();
	const pathStr = path.replaceAll("\\", "/");

	if (name === "skill.md") return [...checkSkillMd(path), ...checkSkillAdvisories(path)];
	if (["agents.md", "claude.md", "gemini.md"].includes(name) || pathStr.includes("/rules/")) return checkRulesFile(path);
	if (pathStr.includes("/docs/specs/") && name.endsWith(".md")) return checkDurableSpec(path);
	return [];
}

/** Validation suggestions for the edited file, or undefined when it is clean, missing, or not validated. */
export function validateFile(filePath: string, cwd: string): string | undefined {
	const base = cwd || process.cwd();
	const target = isAbsolute(filePath) ? filePath : resolve(base, filePath);
	if (!existsSync(target)) return undefined;

	const warnings = runValidation(target);
	if (!warnings.length) return undefined;

	const rel = relative(base, target);
	const shown = rel.startsWith("..") || isAbsolute(rel) ? target : rel;
	return `validator ${shown}:\n${warnings.map((warning) => `  - ${warning}`).join("\n")}`;
}
