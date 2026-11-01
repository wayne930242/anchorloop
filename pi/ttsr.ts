/**
 * pi extension: Time Traveling Stream Rules (TTSR), ported from oh-my-pi.
 *
 * A rule is a Markdown file whose frontmatter carries a `condition` regex. Rules load from
 * `<agentDir>/rules/*.md` and `<cwd>/.pi/rules/*.md`; a project rule shadows a user rule of
 * the same name. Rules without `condition` are ordinary prose rules and are left alone.
 *
 * - A match in streamed assistant text (or thinking, when scoped) aborts the response, drops
 *   the partial output from context, and retries with the rule injected.
 * - A match in tool arguments blocks the call before it runs, with the rule as the reason.
 * - `interruptMode: never` lets the output stand: tool matches get the rule appended to the
 *   tool result, prose matches get it as a follow-up message.
 *
 * Injected rule names persist in the session, so resume does not repeat them.
 */

import { readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join, matchesGlob } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export type Source = "text" | "thinking" | "tool";
type InterruptMode = "always" | "prose-only" | "tool-only" | "never";
type RepeatMode = "once" | "after-gap";

interface ToolScope {
	toolName?: string;
	pathGlob?: string;
}

interface Scope {
	allowText: boolean;
	allowThinking: boolean;
	allowAnyTool: boolean;
	toolScopes: ToolScope[];
}

export interface Rule {
	name: string;
	path: string;
	content: string;
	conditions: RegExp[];
	scope: Scope;
	globs: string[];
	interruptMode: InterruptMode;
	repeatMode: RepeatMode;
	repeatGap: number;
}

export interface MatchContext {
	source: Source;
	toolName?: string;
	filePaths?: string[];
}

const DEFAULT_INTERRUPT_MODE: InterruptMode = "always";
const DEFAULT_REPEAT_MODE: RepeatMode = "once";
const DEFAULT_REPEAT_GAP = 10;
const UNSUPPORTED_FIELDS = ["astCondition", "question", "agents"];
const INTERRUPT_MODES = new Set(["always", "prose-only", "tool-only", "never"]);
const ENTRY_TYPE = "ttsr_injection";
const MESSAGE_TYPE = "ttsr-injection";

// One wrapper for every injection: the body is the instruction, and the rule's file path is user-facing configuration.
export function render(rule: Rule): string {
	return `<rule name="${rule.name}">\n${rule.content.trim()}\n</rule>`;
}

/** Unquote a YAML scalar written plainly, in single quotes, or in double quotes. */
function parseScalar(raw: string): string {
	const value = raw.trim();
	if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
		return value.slice(1, -1).replaceAll("''", "'");
	}
	if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
		return JSON.parse(value);
	}
	return value;
}

/**
 * Parse the frontmatter subset rule files use: `key: scalar`, `key: [a, b]`, and `key:`
 * followed by `- item` lines. Returns undefined when the file has no frontmatter.
 */
export function parseFrontmatter(source: string): { data: Record<string, string | string[]>; body: string } | undefined {
	const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(source);
	if (!match) return undefined;
	const data: Record<string, string | string[]> = {};
	let listKey: string | undefined;
	for (const line of match[1].split(/\r?\n/)) {
		if (line.trim() === "" || line.trimStart().startsWith("#")) continue;
		const item = /^\s+-\s+(.*)$/.exec(line);
		if (item && listKey) {
			(data[listKey] as string[]).push(parseScalar(item[1]));
			continue;
		}
		const pair = /^([A-Za-z_][\w-]*):\s*(.*)$/.exec(line);
		if (!pair) throw new Error(`unparseable frontmatter line: ${line}`);
		const [, key, rawValue] = pair;
		const value = rawValue.trim();
		listKey = undefined;
		if (value === "") {
			data[key] = [];
			listKey = key;
		} else if (value.startsWith("[") && value.endsWith("]")) {
			data[key] = value.slice(1, -1).split(",").map(parseScalar).filter((v) => v.length > 0);
		} else {
			data[key] = parseScalar(value);
		}
	}
	return { data, body: source.slice(match[0].length) };
}

function toList(value: string | string[] | undefined): string[] {
	if (value === undefined) return [];
	return (Array.isArray(value) ? value : [value]).map((v) => v.trim()).filter((v) => v.length > 0);
}

/** Split comma-separated scope tokens, keeping commas inside (), [] and {} intact. */
function splitScopeTokens(value: string): string[] {
	const tokens: string[] = [];
	let depth = 0;
	let current = "";
	for (const char of value) {
		if ("([{".includes(char)) depth++;
		if (")]}".includes(char)) depth = Math.max(0, depth - 1);
		if (char === "," && depth === 0) {
			if (current.trim()) tokens.push(current.trim());
			current = "";
			continue;
		}
		current += char;
	}
	if (current.trim()) tokens.push(current.trim());
	return tokens.map((token) => parseScalar(token));
}

/** Compile a condition, translating a leading PCRE inline flag group such as `(?i)`. */
export function compileCondition(pattern: string): RegExp {
	const inline = /^\(\?([ims]+)\)/.exec(pattern);
	if (inline) return new RegExp(pattern.slice(inline[0].length), Array.from(new Set(inline[1])).join(""));
	return new RegExp(pattern);
}

function buildScope(tokens: string[], warnings: string[], name: string): Scope {
	if (tokens.length === 0) return { allowText: true, allowThinking: false, allowAnyTool: true, toolScopes: [] };
	const scope: Scope = { allowText: false, allowThinking: false, allowAnyTool: false, toolScopes: [] };
	for (const token of tokens) {
		const normalized = token.toLowerCase();
		if (normalized === "text") scope.allowText = true;
		else if (normalized === "thinking") scope.allowThinking = true;
		else if (normalized === "tool" || normalized === "toolcall") scope.allowAnyTool = true;
		else {
			const match = /^(?:(?<prefix>tool)(?::(?<tool>[a-z0-9_-]+))?|(?<bare>[a-z0-9_-]+))(?:\((?<path>[^)]+)\))?$/i.exec(token);
			if (!match?.groups) {
				warnings.push(`${name}: invalid scope token "${token}" skipped`);
				continue;
			}
			const { prefix, tool, bare, path } = match.groups;
			const toolName = (tool ?? (prefix ? undefined : bare))?.toLowerCase();
			const pathGlob = path?.trim();
			if (!toolName && !pathGlob) scope.allowAnyTool = true;
			else scope.toolScopes.push({ toolName, pathGlob });
		}
	}
	return scope;
}

/** Build a TTSR rule from a Markdown file, or return undefined for a non-TTSR file. */
export function buildRule(path: string, source: string, warnings: string[]): Rule | undefined {
	const name = basename(path).replace(/\.mdc?$/, "");
	let parsed: ReturnType<typeof parseFrontmatter>;
	try {
		parsed = parseFrontmatter(source);
	} catch (error) {
		warnings.push(`${name}: ${(error as Error).message}`);
		return undefined;
	}
	if (!parsed) return undefined;
	const { data, body } = parsed;
	if (data.enabled === "false") return undefined;
	const rawConditions = toList(data.condition ?? data.ttsr_trigger ?? data.ttsrTrigger);
	const unsupported = UNSUPPORTED_FIELDS.filter((field) => data[field] !== undefined);
	if (rawConditions.length === 0) {
		if (unsupported.length > 0) warnings.push(`${name}: ${unsupported.join(", ")} not supported; rule skipped`);
		return undefined;
	}
	if (unsupported.length > 0) {
		warnings.push(`${name}: ${unsupported.join(", ")} not supported; rule skipped`);
		return undefined;
	}
	const conditions: RegExp[] = [];
	for (const pattern of rawConditions) {
		try {
			conditions.push(compileCondition(pattern));
		} catch (error) {
			warnings.push(`${name}: invalid condition /${pattern}/ skipped (${(error as Error).message})`);
		}
	}
	if (conditions.length === 0) return undefined;
	const scope = buildScope(toList(data.scope).flatMap(splitScopeTokens), warnings, name);
	if (!scope.allowText && !scope.allowThinking && !scope.allowAnyTool && scope.toolScopes.length === 0) {
		warnings.push(`${name}: scope excludes every stream; rule skipped`);
		return undefined;
	}
	const interruptMode = typeof data.interruptMode === "string" ? data.interruptMode : DEFAULT_INTERRUPT_MODE;
	if (!INTERRUPT_MODES.has(interruptMode)) {
		warnings.push(`${name}: invalid interruptMode "${interruptMode}"; rule skipped`);
		return undefined;
	}
	const repeatMode = data.repeatMode === "after-gap" ? "after-gap" : DEFAULT_REPEAT_MODE;
	const repeatGap = typeof data.repeatGap === "string" ? Number.parseInt(data.repeatGap, 10) : DEFAULT_REPEAT_GAP;
	return {
		name,
		path,
		content: body,
		conditions,
		scope,
		globs: toList(data.globs).flatMap(splitScopeTokens),
		interruptMode: interruptMode as InterruptMode,
		repeatMode,
		repeatGap: Number.isFinite(repeatGap) && repeatGap > 0 ? repeatGap : DEFAULT_REPEAT_GAP,
	};
}

function listRuleFiles(dir: string): string[] {
	try {
		return readdirSync(dir)
			.filter((file) => /\.mdc?$/.test(file))
			.sort()
			.map((file) => join(dir, file));
	} catch {
		return [];
	}
}

export function agentDir(): string {
	const envDir = process.env.PI_CODING_AGENT_DIR;
	if (envDir) return envDir.replace(/^~(?=$|\/)/, homedir());
	return join(homedir(), ".pi", "agent");
}

/** Discover rules: project rules first so they shadow user rules of the same name. */
export function discoverRules(cwd: string, userDir: string): { rules: Rule[]; warnings: string[] } {
	const warnings: string[] = [];
	const rules: Rule[] = [];
	const seen = new Set<string>();
	for (const file of [...listRuleFiles(join(cwd, ".pi", "rules")), ...listRuleFiles(join(userDir, "rules"))]) {
		const rule = buildRule(file, readFileSync(file, "utf-8"), warnings);
		if (!rule || seen.has(rule.name)) continue;
		seen.add(rule.name);
		rules.push(rule);
	}
	return { rules, warnings };
}

function matchesPathGlob(glob: string, filePaths: string[] | undefined): boolean {
	for (const filePath of filePaths ?? []) {
		const normalized = filePath.replaceAll("\\", "/");
		if (matchesGlob(normalized, glob) || matchesGlob(basename(normalized), glob)) return true;
	}
	return false;
}

/** Tracks rules, scope matching, and the repeat policy for one session. */
export class TtsrManager {
	readonly rules: Rule[];
	#turnCount = 0;
	#injectedAt = new Map<string, number>();

	constructor(rules: Rule[]) {
		this.rules = rules;
	}

	turnEnded(): void {
		this.#turnCount++;
	}

	restore(names: string[]): void {
		for (const name of names) this.#injectedAt.set(name, 0);
	}

	markInjected(names: string[]): void {
		for (const name of names) this.#injectedAt.set(name, this.#turnCount);
	}

	#eligible(rule: Rule): boolean {
		const last = this.#injectedAt.get(rule.name);
		if (last === undefined) return true;
		return rule.repeatMode === "after-gap" && this.#turnCount - last >= rule.repeatGap;
	}

	#inScope(rule: Rule, context: MatchContext): boolean {
		if (rule.globs.length > 0 && !rule.globs.some((glob) => matchesPathGlob(glob, context.filePaths))) return false;
		if (context.source === "text") return rule.scope.allowText;
		if (context.source === "thinking") return rule.scope.allowThinking;
		if (rule.scope.allowAnyTool) return true;
		const toolName = context.toolName?.toLowerCase();
		return rule.scope.toolScopes.some(
			(scope) =>
				(!scope.toolName || scope.toolName === toolName) &&
				(!scope.pathGlob || matchesPathGlob(scope.pathGlob, context.filePaths)),
		);
	}

	/**
	 * Rules whose scope, path globs, condition, and repeat policy all admit `content`. A match that blocks a tool call
	 * ignores the repeat policy: the call must never run, however often the rule has fired.
	 */
	check(content: string, context: MatchContext): Rule[] {
		return this.rules.filter(
			(rule) =>
				((context.source === "tool" && interrupts(rule, "tool")) || this.#eligible(rule)) &&
				this.#inScope(rule, context) &&
				rule.conditions.some((condition) => {
					condition.lastIndex = 0;
					return condition.test(content);
				}),
		);
	}
}

export function interrupts(rule: Rule, source: Source): boolean {
	if (rule.interruptMode === "always") return true;
	if (rule.interruptMode === "prose-only") return source !== "tool";
	if (rule.interruptMode === "tool-only") return source === "tool";
	return false;
}

/**
 * The text a tool call contributes to matching: the new source for write/edit, the command
 * for bash, and the raw JSON arguments for every other tool.
 */
export function toolDigest(toolName: string, input: Record<string, unknown>): { digest: string; filePaths: string[] } {
	const filePaths = [input.path, input.file_path, ...(Array.isArray(input.paths) ? input.paths : [])].filter(
		(value): value is string => typeof value === "string",
	);
	if (toolName === "write" && typeof input.content === "string") return { digest: input.content, filePaths };
	if (toolName === "edit" && Array.isArray(input.edits)) {
		const added = input.edits.map((edit) => (edit as { newText?: unknown }).newText).filter((t) => typeof t === "string");
		return { digest: added.join("\n"), filePaths };
	}
	if (toolName === "bash" && typeof input.command === "string") return { digest: input.command, filePaths };
	return { digest: JSON.stringify(input), filePaths };
}

export default function (pi: ExtensionAPI) {
	let manager = new TtsrManager([]);
	let warnings: string[] = [];
	const buffers = new Map<string, string>();
	const pendingInterrupt = new Map<string, Rule>();
	const pendingProse = new Map<string, Rule>();
	const toolReminders = new Map<string, Rule[]>();
	const discardedTimestamps = new Set<number>();

	function load(ctx: { cwd: string; ui: { notify(message: string, level?: "info" | "warning" | "error"): void } }) {
		const discovered = discoverRules(ctx.cwd, agentDir());
		manager = new TtsrManager(discovered.rules);
		warnings = discovered.warnings;
		if (warnings.length > 0) ctx.ui.notify(`TTSR rule problems:\n${warnings.join("\n")}`, "warning");
	}

	function injectedNames(entries: Array<{ type: string; customType?: string; data?: unknown }>): string[] {
		return entries.flatMap((entry) =>
			entry.type === "custom" && entry.customType === ENTRY_TYPE ? ((entry.data as { rules?: string[] })?.rules ?? []) : [],
		);
	}

	pi.on("session_start", (_event, ctx) => {
		load(ctx);
		manager.restore(injectedNames(ctx.sessionManager.getBranch() as never));
	});

	pi.on("turn_start", () => {
		buffers.clear();
	});

	pi.on("turn_end", () => {
		manager.turnEnded();
	});

	pi.on("message_start", () => {
		buffers.clear();
	});

	pi.on("message_update", (event, ctx) => {
		if (manager.rules.length === 0 || pendingInterrupt.size > 0) return;
		const update = event.assistantMessageEvent;
		if (update.type !== "text_delta" && update.type !== "thinking_delta") return;
		const source: Source = update.type === "text_delta" ? "text" : "thinking";
		const key = `${source}:${update.contentIndex}`;
		const buffer = (buffers.get(key) ?? "") + update.delta;
		buffers.set(key, buffer);
		const matched = manager.check(buffer, { source });
		if (matched.length === 0) return;
		manager.markInjected(matched.map((rule) => rule.name));
		const interrupting = matched.some((rule) => interrupts(rule, source));
		for (const rule of matched) (interrupting ? pendingInterrupt : pendingProse).set(rule.name, rule);
		if (interrupting) {
			ctx.ui.notify(`TTSR: injecting rule ${[...pendingInterrupt.keys()].join(", ")}`, "warning");
			ctx.abort();
		}
	});

	pi.on("message_end", (event) => {
		const message = event.message as { role?: string; stopReason?: string; timestamp?: number };
		if (message.role !== "assistant") return;
		if (message.stopReason === "aborted" || message.stopReason === "error") {
			toolReminders.clear();
			if (pendingInterrupt.size > 0 && message.timestamp !== undefined) discardedTimestamps.add(message.timestamp);
			pendingProse.clear();
			return;
		}
		if (pendingProse.size === 0) return;
		const rules = [...pendingProse.values()];
		pendingProse.clear();
		pi.sendMessage(
			{
				customType: MESSAGE_TYPE,
				content: rules.map((rule) => render(rule)).join("\n\n"),
				display: true,
				details: { rules: rules.map((rule) => rule.name) },
			},
			{ deliverAs: "followUp", triggerTurn: true },
		);
		pi.appendEntry(ENTRY_TYPE, { rules: rules.map((rule) => rule.name) });
	});

	pi.on("agent_settled", () => {
		if (pendingInterrupt.size === 0) return;
		const rules = [...pendingInterrupt.values()];
		pendingInterrupt.clear();
		pi.appendEntry(ENTRY_TYPE, { rules: rules.map((rule) => rule.name) });
		pi.sendMessage(
			{
				customType: MESSAGE_TYPE,
				content: rules.map((rule) => render(rule)).join("\n\n"),
				display: true,
				details: { rules: rules.map((rule) => rule.name) },
			},
			{ triggerTurn: true },
		);
	});

	// contextMode "discard": the interrupted partial response never reaches the model again.
	pi.on("context", (event) => {
		if (discardedTimestamps.size === 0) return;
		const messages = event.messages.filter(
			(message) =>
				!(message.role === "assistant" && discardedTimestamps.has((message as { timestamp?: number }).timestamp ?? -1)),
		);
		return { messages };
	});

	pi.on("tool_call", (event, ctx) => {
		if (manager.rules.length === 0) return;
		const { digest, filePaths } = toolDigest(event.toolName, event.input as Record<string, unknown>);
		const matched = manager.check(digest, { source: "tool", toolName: event.toolName, filePaths });
		if (matched.length === 0) return;
		manager.markInjected(matched.map((rule) => rule.name));
		const blocking = matched.filter((rule) => interrupts(rule, "tool"));
		const passive = matched.filter((rule) => !interrupts(rule, "tool"));
		if (blocking.length > 0) {
			pi.appendEntry(ENTRY_TYPE, { rules: matched.map((rule) => rule.name) });
			ctx.ui.notify(`TTSR: blocked ${event.toolName} by rule ${blocking.map((rule) => rule.name).join(", ")}`, "warning");
			return {
				block: true,
				reason: [...blocking.map((rule) => render(rule)), ...passive.map((rule) => render(rule))].join("\n\n"),
			};
		}
		toolReminders.set(event.toolCallId, passive);
	});

	pi.on("tool_result", (event) => {
		const rules = toolReminders.get(event.toolCallId);
		if (!rules) return;
		toolReminders.delete(event.toolCallId);
		pi.appendEntry(ENTRY_TYPE, { rules: rules.map((rule) => rule.name) });
		return {
			content: [...event.content, { type: "text", text: rules.map((rule) => render(rule)).join("\n\n") }],
		};
	});

	pi.registerCommand("ttsr", {
		description: "List loaded TTSR rules and rule-file problems",
		handler: async (_args, ctx) => {
			const lines = manager.rules.map(
				(rule) => `${rule.name} [${rule.interruptMode}, ${rule.repeatMode}] ${rule.conditions.map(String).join(" | ")}  ${rule.path}`,
			);
			ctx.ui.notify(
				[`TTSR rules: ${manager.rules.length}`, ...lines, ...(warnings.length > 0 ? ["Problems:", ...warnings] : [])].join("\n"),
				"info",
			);
		},
	});
}
