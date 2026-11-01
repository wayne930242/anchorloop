/**
 * pi extension: validates the file after each write and edit tool result and
 * appends the suggestions to the model-visible result content. The checks run
 * in-process (pi/support/validators.ts), so no Python is needed on any platform.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { validateFile } from "./support/validators.ts";

function validate(filePath: string, cwd: string): string | undefined {
	try {
		return validateFile(filePath, cwd);
	} catch (error) {
		return `validator did not run: ${error instanceof Error ? error.message : String(error)}`;
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_result", async (event, ctx) => {
		if (event.isError || (event.toolName !== "write" && event.toolName !== "edit")) return;
		const filePath = event.input.path;
		if (typeof filePath !== "string") return;
		const advice = validate(filePath, ctx.cwd);
		if (!advice) return;
		return { content: [...event.content, { type: "text", text: advice }] };
	});
}
