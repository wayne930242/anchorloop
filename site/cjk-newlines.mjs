// A Sätteri mdast plugin and an Astro integration that drop a source line break between two Chinese (or Japanese) characters.
// Markdown turns the break into a space, and browsers draw that space (Chrome and Safari do not remove it), so a sentence-per-line
// Chinese source reads with a gap after every full stop. The sources keep one sentence per line, which the line-for-line twin rule needs.

// Han, kana, and Hangul letters; full-width forms; CJK punctuation; the dashes and ellipsis Chinese text uses.
const WIDE = /[\u1100-\u11ff\u2014\u2026\u2e80-\u303f\u3040-\u30ff\u3100-\u312f\u3190-\u31ff\u3200-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef]/u;
// Marks that never take a space on their inner side: a space after them, or before a closing one, is a gap, not a word break.
const AFTER_OK = /[\u3001\u3002\u3008-\u3011\u3014-\u301b\uff01\uff08\uff0c\uff0e\uff1a\uff1b\uff1f]/u;
const BEFORE_OK = /[\u3001\u3002\u3009\u300b\u300d\u300f\u3011\u3015\uff01\uff09\uff0c\uff0e\uff1a\uff1b\uff1f]/u;

/** True when a line break between `a` and `b` is no word break: both are wide, or the break touches a full-width mark. */
export function joins(a, b) {
	if (a === undefined || b === undefined) return false;
	if (WIDE.test(a) && WIDE.test(b)) return true;
	return AFTER_OK.test(a) || BEFORE_OK.test(b);
}

/** `text` with each line break (with the spaces around it) removed where `joins(before, after)`; `before` and `after` are the characters beside `text`. */
export function joinLines(text, before, after) {
	if (!text.includes("\n")) return text;
	let out = "";
	let i = 0;
	while (i < text.length) {
		if (text[i] !== "\n") {
			out += text[i++];
			continue;
		}
		let j = i;
		while (j < text.length && /[ \t\n]/.test(text[j])) j++;
		const a = [...out].at(-1) ?? before;
		const b = j < text.length ? [...text.slice(j)][0] : after;
		if (joins(a, b) && !/\s$/.test(out)) i = j;
		else out += text[i++];
	}
	return out;
}

const edge = (node, ctx, last) => {
	const text = ctx.textContent(node, { includeHtml: false });
	return text === "" ? undefined : [...text].at(last ? -1 : 0);
};

/** The mdast plugin: it joins in a text node, and across the node's neighbours when the break sits at its edge. */
export const cjkNewlinesPlugin = {
	name: "cjk-newlines",
	text(node, ctx) {
		if (!node.value.includes("\n")) return;
		const parent = ctx.parent(node);
		const at = ctx.indexOf(node);
		const siblings = parent?.children ?? [];
		const prev = at === undefined || at === 0 ? undefined : siblings[at - 1];
		const next = at === undefined ? undefined : siblings[at + 1];
		const value = joinLines(node.value, prev ? edge(prev, ctx, true) : undefined, next ? edge(next, ctx, false) : undefined);
		if (value !== node.value) return { type: "text", value };
	},
};

/** The Astro integration: adds the plugin to the Sätteri processor Astro 7 uses by default. */
export default function cjkNewlines() {
	return {
		name: "cjk-newlines",
		hooks: {
			"astro:config:setup": async ({ config, updateConfig, logger }) => {
				const { satteri, isSatteriProcessor } = await import("@astrojs/markdown-satteri");
				const processor = config.markdown?.processor;
				if (!isSatteriProcessor(processor)) throw new Error(`cjk-newlines: the markdown processor is ${processor?.name}, not satteri`);
				const options = processor.options ?? {};
				updateConfig({ markdown: { processor: satteri({ ...options, mdastPlugins: [...(options.mdastPlugins ?? []), cjkNewlinesPlugin] }) } });
				logger.info("joining line breaks between Chinese characters");
			},
		},
	};
}
