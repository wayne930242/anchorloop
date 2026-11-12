// The documentation site, served on GitHub Pages at https://wayne930242.github.io/anchorloop/.
// Pages under reference/how-it-works are generated from docs/ by scripts/sync.mjs.
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import mermaid from "astro-mermaid";
import starlightLinksValidator from "starlight-links-validator";
import cjkNewlines from "./cjk-newlines.mjs";

export default defineConfig({
	site: "https://wayne930242.github.io",
	base: "/anchorloop",
	trailingSlash: "always",
	integrations: [
		// Both before starlight(): they add Sätteri plugins to the processor Starlight then extends.
		// Diagrams keep their natural size and scroll sideways when wider than the column, so their text stays readable on a phone;
		// sequence messages wrap inside the gap between two participants instead of widening it.
		mermaid({
			autoTheme: true,
			enableLog: false,
			mermaidConfig: {
				sequence: { wrap: true, width: 140, actorMargin: 24, messageMargin: 34, useMaxWidth: false },
				flowchart: { useMaxWidth: false, wrappingWidth: 320 },
				state: { useMaxWidth: false },
			},
		}),
		cjkNewlines(),
		starlight({
			title: "anchorloop",
			description: "Agent workflow skills and loop extensions for pi: one entry skill per task type over a shared Align → Anchor → Act → Verify loop.",
			defaultLocale: "root",
			locales: {
				root: { label: "English", lang: "en" },
				"zh-tw": { label: "繁體中文", lang: "zh-TW" },
			},
			social: [{ icon: "github", label: "GitHub", href: "https://github.com/wayne930242/anchorloop" }],
			editLink: { baseUrl: "https://github.com/wayne930242/anchorloop/edit/master/site/" },
			lastUpdated: false,
			customCss: ["./src/styles/custom.css"],
			// The reference pages fold each section's details into <details>: open the ones a link or a search hit points into.
			head: [
				{
					tag: "script",
					content:
						"(()=>{const up=(el)=>{for(let d=el&&el.closest&&el.closest('details');d;d=d.parentElement&&d.parentElement.closest('details'))d.open=true};" +
						"const go=()=>{if(!location.hash)return;let t;try{t=document.getElementById(decodeURIComponent(location.hash.slice(1)))}catch{}if(t&&t.closest('details')){up(t);t.scrollIntoView()}};" +
						"addEventListener('hashchange',go);addEventListener('DOMContentLoaded',go);" +
						"addEventListener('load',()=>setTimeout(()=>{document.querySelectorAll('mark[data-pagefind-highlight]').forEach(up)},400))})();",
				},
			],
			tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 4 },
			sidebar: [
				{
					label: "Start here",
					translations: { "zh-TW": "開始" },
					items: ["guide/install", "guide/quick-start", "guide/concepts"],
				},
				{
					label: "Guides",
					translations: { "zh-TW": "指南" },
					items: ["guide/skills", "guide/merge-train", "guide/with-straw-boss"],
				},
				{
					label: "Extensions",
					translations: { "zh-TW": "擴充功能" },
					collapsed: true,
					items: [{ autogenerate: { directory: "reference/how-it-works" } }],
				},
				{
					label: "Project",
					translations: { "zh-TW": "專案" },
					items: ["guide/develop", "guide/acknowledgments"],
				},
			],
			plugins: [starlightLinksValidator({ errorOnFallbackPages: false })],
		}),
	],
});
