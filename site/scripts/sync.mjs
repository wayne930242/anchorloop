// Generates the site's extension reference from the repository's own Markdown, so docs/ stays the one source:
// docs/how-it-works.md (and its zh-TW twin) split by H2 into one page each.
// Links are rewritten to absolute site paths (the links validator checks them) or to GitHub for files the site does not publish.
// `--check` reports whether docs/how-it-works.zh-TW.md still matches the English file: line for line (same line count, same kind of line,
// every backticked token of an English line on the same zh-TW line; error), heading structure (error), and drift since the source commit (warning),
// whether each hand-written English page has a zh-TW twin with the same headings, folds, and diagrams (error),
// and every `**` that CommonMark would not turn into bold (CJK punctuation beside it), in the site's own zh pages and in docs/*.zh-TW.md (error).
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, normalize, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import GithubSlugger from "github-slugger";

const SITE = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(SITE, "..");
const DOCS = join(REPO, "docs");
const CONTENT = join(SITE, "src/content/docs");
const BASE = "/anchorloop";
const GITHUB = "https://github.com/wayne930242/anchorloop";
const BRANCH = "master";
const LOCALES = { en: { dir: "", suffix: "" }, zh: { dir: "zh-tw", suffix: ".zh-TW" } };
const GENERATED = ["reference/how-it-works"];

// Heading text as GitHub and Astro slug it: the rendered text, without code ticks, link targets, or emphasis marks.
const plain = (text) =>
	text
		.replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
		.replace(/`([^`]*)`/g, "$1")
		.replace(/<[^>]+>/g, "")
		.replace(/(\*\*|__|\*|_)(.+?)\1/g, "$2")
		.trim();

// Headings outside code fences, with their line index, level, text, and slug in the whole document.
function headings(lines) {
	const slugger = new GithubSlugger();
	const out = [];
	let fence = false;
	lines.forEach((line, i) => {
		if (/^\s*```/.test(line)) fence = !fence;
		const m = !fence && /^(#{1,6}) (.*)$/.exec(line);
		if (m) out.push({ i, level: m[1].length, text: m[2], slug: slugger.slug(plain(m[2])) });
	});
	return out;
}

function read(path) {
	return existsSync(path) ? readFileSync(path, "utf8") : undefined;
}

// The how-it-works index of one language: each H2 section becomes a page named by the English heading's slug, so both
// languages share URLs (Starlight's language switch keeps the path). anchors maps a whole-document slug to its page and in-page slug.
function hiwPlan(enText, text) {
	const en = headings(enText.split("\n"));
	const lines = text.split("\n");
	const own = headings(lines);
	if (own.length !== en.length || own.some((h, n) => h.level !== en[n].level))
		throw new Error("docs/how-it-works.zh-TW.md: its headings do not match docs/how-it-works.md (run `npm run check`)");
	const pages = [];
	const anchors = new Map();
	let page;
	own.forEach((h, n) => {
		if (h.level === 2) {
			page = { slug: en[n].slug, title: plain(h.text), start: h.i, slugger: new GithubSlugger() };
			pages.push(page);
			for (const s of [h.slug, en[n].slug]) anchors.set(s, { page: page.slug });
		} else if (page) {
			const local = page.slugger.slug(plain(h.text));
			for (const s of [h.slug, en[n].slug]) if (!anchors.has(s)) anchors.set(s, { page: page.slug, hash: local });
		}
	});
	pages.forEach((p, n) => (p.end = n + 1 < pages.length ? pages[n + 1].start : lines.length));
	const intro = { start: own[0]?.level === 1 ? own[0].i + 1 : 0, end: pages[0]?.start ?? lines.length, title: plain(own[0]?.text ?? "How it works") };
	return { lines, pages, anchors, intro };
}

const prefix = (lang) => `${BASE}/${LOCALES[lang].dir ? `${LOCALES[lang].dir}/` : ""}`;

// Rewrites one Markdown link target found in `from` (a path under docs/) for the page in `lang`.
function target(url, from, lang, ctx) {
	if (/^(https?:|mailto:)/.test(url)) return url;
	const [path, hash] = url.split("#");
	const hiw = (h) => {
		const a = h ? ctx.anchors[lang].get(h) ?? ctx.anchors.en.get(h) : undefined;
		if (h && !a) throw new Error(`${relative(REPO, from)}: no heading for #${h}`);
		return a ? `${prefix(lang)}reference/how-it-works/${a.page}/${a.hash ? `#${a.hash}` : ""}` : `${prefix(lang)}reference/how-it-works/`;
	};
	if (!path) return from.endsWith("how-it-works.md") || from.endsWith("how-it-works.zh-TW.md") ? hiw(hash) : url;
	const file = normalize(join(dirname(from), path));
	const rel = relative(REPO, file).replaceAll("\\", "/");
	if (/^docs\/how-it-works(\.zh-TW)?\.md$/.test(rel)) return hiw(hash);
	if (/^README(\.zh-TW)?\.md$/.test(rel)) return prefix(rel.includes("zh-TW") ? "zh" : lang);
	if (rel.startsWith("..")) return url;
	const kind = existsSync(file) && statSync(file).isDirectory() ? "tree" : "blob";
	return `${GITHUB}/${kind}/${BRANCH}/${rel}${hash ? `#${hash}` : ""}`;
}

function rewrite(text, from, lang, ctx) {
	let fence = false;
	return text
		.split("\n")
		.map((line) => {
			if (/^\s*```/.test(line)) fence = !fence;
			if (fence || /^\s*```/.test(line)) return line;
			return line
				.replace(/(\]\()([^)\s]+)((?:\s+"[^"]*")?\))/g, (_, a, url, b) => a + target(url, from, lang, ctx) + b)
				.replace(/(<img [^>]*src=")([^"]+)(")/g, (_, a, url, b) => a + target(url, from, lang, ctx) + b)
				.replace(/(<a [^>]*href=")([^"]+)(")/g, (_, a, url, b) => a + target(url, from, lang, ctx) + b);
		})
		.join("\n");
}

// Every heading one level up (### becomes ##), for a section that becomes a page whose title is its H2.
const demote = (body) => {
	let fence = false;
	return body
		.split("\n")
		.map((line) => {
			if (/^\s*```/.test(line)) fence = !fence;
			return !fence && /^#{3,6} /.test(line) ? line.slice(1) : line;
		})
		.join("\n");
};

const yaml = (s) => JSON.stringify(s);

function page(path, front, body) {
	mkdirSync(dirname(path), { recursive: true });
	const lines = Object.entries(front).map(([k, v]) => (typeof v === "object" ? `${k}:\n${Object.entries(v).map(([a, b]) => `  ${a}: ${yaml(b)}`).join("\n")}` : `${k}: ${yaml(v)}`));
	writeFileSync(path, `---\n${lines.join("\n")}\n---\n\n${body.trim()}\n`);
}

function sourceOf(zhText) {
	return /<!-- source: docs\/how-it-works\.md @ ([0-9a-f]{7,40}) -->/.exec(zhText)?.[1];
}

const PUNCT = /[\p{P}\p{S}]/u;
const SPACE = /\s/u;

// The 1-based lines of `text` holding a `**` that is not bold under CommonMark's flanking rule. A delimiter that opens needs a
// non-space after it, and a punctuation mark after it only when a space or punctuation lies before it; a delimiter that closes
// is the mirror. Code fences are skipped, and inline code counts as its backticks (punctuation). `**` pairs are taken in order, as the parser pairs a line's runs.
export function brokenBold(text) {
	const out = [];
	let fence = false;
	text.split("\n").forEach((line, i) => {
		if (/^\s*```/.test(line)) fence = !fence;
		if (fence || !line.includes("**")) return;
		const plainLine = line.replace(/`[^`]*`/g, (m) => "`".repeat(m.length));
		const runs = [...plainLine.matchAll(/\*\*+/g)].filter((m) => m[0].length === 2);
		let bad = false;
		runs.forEach((m, n) => {
			const before = m.index > 0 ? plainLine[m.index - 1] : " ";
			const after = m.index + 2 < plainLine.length ? plainLine[m.index + 2] : " ";
			const left = !SPACE.test(after) && (!PUNCT.test(after) || SPACE.test(before) || PUNCT.test(before));
			const right = !SPACE.test(before) && (!PUNCT.test(before) || SPACE.test(after) || PUNCT.test(after));
			if (n % 2 === 0 ? !left : !right) bad = true;
		});
		if (bad) out.push(i + 1);
	});
	return out;
}

function checkBold() {
	let bad = 0;
	const files = [];
	const walk = (dir) => {
		for (const f of readdirSync(dir)) {
			const path = join(dir, f);
			if (statSync(path).isDirectory()) walk(path);
			else if (/\.mdx?$/.test(f)) files.push(path);
		}
	};
	walk(join(CONTENT, "zh-tw"));
	for (const path of files) {
		if (GENERATED.some((g) => relative(join(CONTENT, "zh-tw"), path).startsWith(g))) continue;
		const lines = brokenBold(read(path));
		if (lines.length) console.log(`${relative(REPO, path)}: bold the page cannot show, at lines ${lines.join(", ")}`), (bad = 1);
	}
	for (const f of readdirSync(DOCS).filter((f) => /\.zh-TW\.md$/.test(f))) {
		const lines = brokenBold(read(join(DOCS, f)));
		if (lines.length) console.log(`docs/${f}: bold the page cannot show (move the punctuation outside the ** or put a space after it), at lines ${lines.join(", ")}`), (bad = 1);
	}
	return bad;
}

// The kind of one line, by what Markdown makes of it; lines inside a code fence are all "code".
function lineKinds(lines) {
	let fence = false;
	return lines.map((line) => {
		if (/^\s*```/.test(line)) return (fence = !fence), "fence";
		if (fence) return "code";
		if (!line.trim()) return "blank";
		const h = /^(#{1,6}) /.exec(line);
		if (h) return `h${h[1].length}`;
		if (line.startsWith("|")) return "row";
		if (/^\s*[-*] /.test(line)) return "bullet";
		if (/^\s*\d+\. /.test(line)) return "number";
		return "text";
	});
}

// The line-for-line check: the 1-based lines where the twin's line differs from the English line in kind, or lacks a backticked token the
// English line has (the twin may add tokens, such as the zh-TW form of a message). Returns a message when the line counts differ.
export function twinDrift(enLines, zhLines) {
	if (enLines.length !== zhLines.length) return { message: `${enLines.length} lines in English, ${zhLines.length} in zh-TW` };
	const [ke, kz] = [lineKinds(enLines), lineKinds(zhLines)];
	const bad = [];
	enLines.forEach((line, i) => {
		if (ke[i] !== kz[i]) return bad.push(i + 1);
		if (ke[i] === "code" || ke[i] === "fence") return;
		const have = new Map();
		for (const t of zhLines[i].match(/`[^`]+`/g) ?? []) have.set(t, (have.get(t) ?? 0) + 1);
		for (const t of line.match(/`[^`]+`/g) ?? []) {
			if (!have.get(t)) return bad.push(i + 1);
			have.set(t, have.get(t) - 1);
		}
	});
	return { bad };
}

// Each hand-written English page needs a zh-TW twin of the same shape: the same heading levels in order, and as many folds, diagrams, and
// tables. (The generated reference pages are held to the stricter line-for-line rule above.)
export function pageShape(text) {
	const lines = text.split("\n");
	const heads = headings(lines).map((h) => h.level).join("");
	let fence = false;
	let diagrams = 0;
	let folds = 0;
	let rows = 0;
	for (const line of lines) {
		if (/^\s*```/.test(line)) {
			if (!fence && /^\s*```mermaid/.test(line)) diagrams++;
			fence = !fence;
		} else if (!fence) {
			if (/^<details>/.test(line)) folds++;
			if (line.startsWith("|")) rows++;
		}
	}
	return { heads, diagrams, folds, rows };
}

function checkPairs() {
	let bad = 0;
	const walk = (dir, out = []) => {
		for (const f of readdirSync(dir)) {
			const path = join(dir, f);
			if (statSync(path).isDirectory()) walk(path, out);
			else if (/\.mdx?$/.test(f)) out.push(path);
		}
		return out;
	};
	for (const path of walk(CONTENT)) {
		const rel = relative(CONTENT, path);
		if (rel.startsWith("zh-tw") || GENERATED.some((g) => rel.startsWith(g))) continue;
		const twin = join(CONTENT, "zh-tw", rel);
		if (!existsSync(twin)) {
			console.log(`site/src/content/docs/${rel}: no zh-TW twin at zh-tw/${rel}`);
			bad = 1;
			continue;
		}
		const [a, b] = [pageShape(read(path)), pageShape(read(twin))];
		for (const key of Object.keys(a)) {
			if (a[key] !== b[key]) {
				console.log(`site/src/content/docs/${rel}: zh-TW twin differs in ${key} (English ${JSON.stringify(a[key])}, zh-TW ${JSON.stringify(b[key])})`);
				bad = 1;
			}
		}
	}
	return bad;
}

function check() {
	const en = read(join(DOCS, "how-it-works.md"));
	const zh = read(join(DOCS, "how-it-works.zh-TW.md"));
	if (!zh) return console.log("docs/how-it-works.zh-TW.md: missing"), 1;
	const a = headings(en.split("\n"));
	const b = headings(zh.split("\n"));
	let bad = 0;
	if (a.length !== b.length) console.log(`headings: ${a.length} in English, ${b.length} in zh-TW`), (bad = 1);
	a.forEach((h, n) => {
		if (b[n] && b[n].level !== h.level) console.log(`heading ${n + 1} ("${h.text}"): level ${h.level} in English, ${b[n].level} in zh-TW`), (bad = 1);
	});
	const drift = twinDrift(en.split("\n"), zh.split("\n"));
	if (drift.message) console.log(`line for line: ${drift.message}`), (bad = 1);
	else if (drift.bad.length) {
		console.log(`line for line: ${drift.bad.length} lines of docs/how-it-works.zh-TW.md differ from the English line of the same number in kind or backticked tokens (a paragraph split elsewhere than in English?), first at ${drift.bad.slice(0, 12).join(", ")}`);
		bad = 1;
	}
	const sha = sourceOf(zh);
	if (!sha) console.log("docs/how-it-works.zh-TW.md: no `<!-- source: docs/how-it-works.md @ <commit> -->` line"), (bad = 1);
	else {
		const log = execFileSync("git", ["log", "--oneline", `${sha}..HEAD`, "--", "docs/how-it-works.md"], { cwd: REPO, encoding: "utf8" }).trim();
		if (log) console.log(`docs/how-it-works.md changed since the translation (${sha}); bring these into docs/how-it-works.zh-TW.md:\n${log}`);
		else console.log(`docs/how-it-works.zh-TW.md matches docs/how-it-works.md at ${sha}`);
	}
	return bad | checkBold() | checkPairs();
}

function sync() {
	for (const lang of Object.keys(LOCALES)) for (const g of GENERATED) rmSync(join(CONTENT, LOCALES[lang].dir, g), { recursive: true, force: true });
	const enText = read(join(DOCS, "how-it-works.md"));
	const zhText = read(join(DOCS, "how-it-works.zh-TW.md"));
	const plans = { en: hiwPlan(enText, enText) };
	if (zhText) plans.zh = hiwPlan(enText, zhText);
	const ctx = { anchors: { en: plans.en.anchors, zh: plans.zh?.anchors ?? plans.en.anchors } };

	for (const [lang, plan] of Object.entries(plans)) {
		const src = join(DOCS, `how-it-works${LOCALES[lang].suffix}.md`);
		const dir = join(CONTENT, LOCALES[lang].dir, "reference/how-it-works");
		const edit = `${GITHUB}/edit/${BRANCH}/docs/how-it-works${LOCALES[lang].suffix}.md`;
		const intro = plan.lines.slice(plan.intro.start, plan.intro.end).join("\n").replace(/<!-- source:[^>]*-->/, "");
		page(join(dir, "index.md"), { title: plan.intro.title, editUrl: edit, sidebar: { order: 0, label: lang === "zh" ? "總覽" : "Overview" } }, rewrite(intro, src, lang, ctx));
		plan.pages.forEach((p, n) => {
			const body = demote(plan.lines.slice(p.start + 1, p.end).join("\n"));
			page(join(dir, `${p.slug}.md`), { title: p.title, editUrl: edit, sidebar: { order: n + 1 } }, rewrite(body, src, lang, ctx));
		});
	}

	console.log(`synced: how-it-works ${Object.keys(plans).join("+")} (${plans.en.pages.length + 1} pages each)`);
}

process.exit(process.argv.includes("--check") ? check() : (sync(), 0));
