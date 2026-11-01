/**
 * pi extension: the `anchorloop_decision` tool appends single-line rows to a
 * decision trail TSV. Adapted from pstack's show-me-your-work log.sh
 * (MIT, (c) 2026 Lauren Tan).
 */

import { closeSync, existsSync, mkdirSync, openSync, readFileSync, statSync, writeSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HEADER = ["ts", "decision", "why", "evidence", "result"];
const FORMULA_LEADS = ["=", "+", "-", "@", '"'];
const TRAIL_PATH = /^scratch\/decisions-[^/]+\.tsv$/;

function clean(cell: string): string {
	const flat = cell.replace(/[\t\r\n]/g, " ");
	return FORMULA_LEADS.some((lead) => flat.startsWith(lead)) ? `'${flat}` : flat;
}

function readRows(log: string): string[][] {
	if (!existsSync(log)) return [];
	return readFileSync(log, "utf-8")
		.split("\n")
		.slice(1)
		.filter(Boolean)
		.map((line) => line.split("\t"));
}

export function appendRow(log: string, cells: string[], now = new Date()): string {
	mkdirSync(dirname(log), { recursive: true });
	const ts = now.toISOString().replace(/\.\d{3}Z$/, "Z");
	const row = `${[ts, ...cells.map(clean)].join("\t")}\n`;
	const data = existsSync(log) && statSync(log).size > 0 ? row : `${HEADER.join("\t")}\n${row}`;
	// One O_APPEND write per row, so parallel writers never interleave inside a row.
	const fd = openSync(log, "a");
	try {
		const bytes = Buffer.from(data);
		const written = writeSync(fd, bytes);
		if (written !== bytes.length) throw new Error(`short write: ${written} of ${bytes.length} bytes`);
	} finally {
		closeSync(fd);
	}
	return row;
}

export function startRow(log: string, runId: string): string {
	const rows = readRows(log);
	const span = rows.length > 0 ? `${rows[0][0]}..${rows.at(-1)?.[0]}` : "empty trail";
	return appendRow(log, ["start", `picked up after ${rows.length} earlier rows (${span})`, runId, "open"]);
}

type Params = { log: string; start?: string; decision?: string; why?: string; evidence?: string; result?: string };

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "anchorloop_decision",
		label: "Decision trail",
		description: "Append one row to scratch/decisions-<slug>.tsv for a fork, pivot, or blocker (git log holds completed units). `start` = your run id when picking up a trail.",
		parameters: {
			type: "object",
			properties: {
				log: { type: "string" },
				start: { type: "string" },
				decision: { type: "string" },
				why: { type: "string" },
				evidence: { type: "string", description: "commit, file:line, or path" },
				result: { type: "string" },
			},
			required: ["log"],
			additionalProperties: false,
		},
		async execute(_toolCallId: string, params: Params, _signal: unknown, _onUpdate: unknown, ctx: { cwd: string }) {
			const log = resolve(ctx.cwd, params.log);
			if (!TRAIL_PATH.test(relative(ctx.cwd, log))) throw new Error("log must be scratch/decisions-<task-slug>.tsv");
			let row: string;
			if (params.start) {
				row = startRow(log, params.start);
			} else {
				const cells = [params.decision, params.why, params.evidence, params.result];
				if (cells.some((cell) => !cell)) throw new Error("decision, why, evidence, and result are all required");
				row = appendRow(log, cells as string[]);
			}
			return { content: [{ type: "text", text: `appended to ${params.log}: ${row.trim()}` }], details: undefined };
		},
	});
}
