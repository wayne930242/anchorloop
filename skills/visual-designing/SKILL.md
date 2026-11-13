---
name: visual-designing
description: Use when a person must see and approve how something looks before it is built, such as comparing visual directions for a UI (比稿), mocking up a native app or web screen, flow, or animation, or laying out a purely visual piece such as an icon, poster, slide, or illustration.
---

# Visual Designing

Run the loop in [../anchorloop/SKILL.md](../anchorloop/SKILL.md). The anchor is the person's verdict on rendered frames: state it as the `anchor` of the `kind` call before drawing, and record it with `anchorloop_stage verify`, `pass` once every frame is accepted and `fail` with the comments otherwise; it stays `unknown` until they answer. Frames live outside the repository, so record `skip` for phase `act` with that reason.

Draw every frame as a hand-written SVG file. SVG is text: a frame costs a few kilobytes to write, a revision is an `edit` to the lines that change, and the same file serves as the build reference later. HTML and CSS pull in layout code nobody asked to approve, and generated raster images cannot be revised in place. Motion is animated SVG too ([motion](playbooks/motion.md)); only gesture feel or performance on a real device needs the `coding` prototype playbook.

## Frames

- One file per frame, `NN-<screen>-<state>.svg`, in `/tmp/design-<task>/` unless the project keeps designs elsewhere, so no frame lands in a commit by accident. A flow is a sequence of frames, one per state.
- Size the `viewBox` to the real canvas, from [canvases](references/canvases.md), and draw at that scale, so a frame reads true on a phone as well as a desktop.
- Self-contained: no `<script>`, external `href`, web fonts, or `<foreignObject>`, which break silently in the review sandbox; CSS and SMIL animation play.
- Text uses a system font stack that covers the content's script, such as `-apple-system, "PingFang TC", "Noto Sans TC", "Segoe UI", sans-serif`. SVG does not wrap text: break lines yourself with `<tspan x dy>`, and size every box for its longest real string.
- Use real content (names, numbers, dates, the product's language), because placeholder text hides the line breaks and widths that decide the layout. Content a frame generates (sample data, jitter) comes from a fixed seed, so a revision diff shows only the intended change.
- Define each repeated part once in `<defs>` and place it with `<use>`; set colors and type sizes as a few CSS classes in one `<style>` block, so a direction change is a few edits.

## Self-check

Measure each frame, then look at it. `node <skill dir>/scripts/measure.mjs 01-home.svg 02-detail.svg` loads each frame in a headless browser through `agent-browser`, runs `scripts/measure.js` in the page, and prints, per frame, the defects as numbers; it exits 1 when it finds any. Fix every defect and measure again until it prints `defects 0`.

The frame marks what the measurement needs, as attributes with values (the SVG is XML):

- `data-in="<id>"` on a `<text>`: the id of the shape that holds it. The text box must stay inside that shape; a text without it is checked only against the canvas and against other texts. An id inside a `<defs>` part resolves within each `<use>` instance, through nested `<use>` parts. A `<use>` passes its `id` and `data-*` marks to its placed instance, and a `<use>` of a `<symbol>` measures the symbol's children scaled by its `viewBox` to the `<use>`'s size.
- `data-target="44"` on each tappable shape or group: the minimum side in viewBox units (44 for touch on iOS, 48 on Android, 24 on desktop web); the box must be at least that on both sides.
- `data-states` and `data-state` mark an element state sheet ([refine](playbooks/refine.md)); `data-overlay=""` marks a part drawn outside the layout box, such as a focus ring.

The measurement covers text that exceeds its container or the canvas, text boxes that overlap, targets under the minimum, and state boxes that differ. Then render each frame to PNG at the review width, for example `rsvg-convert -w 780 01-home.svg -o 01-home.png` (or `resvg`, or a headless browser), and look at every PNG for what numbers do not show: misalignment against the grid, balance, and contrast under 4.5:1 for body text. The person's time goes to judgment, not to defects you could measure.

## Hand over

Write `/tmp/design-<task>/review.md` with one `review` block: an item per frame, `image` the SVG's relative path, `label` the direction and state, `body` the intent of the frame in one or two lines; set `pick: true` when the person chooses between directions. Open it with `show_doc` and `view: "page"`, say that a blank box means accepted, and end the turn; the answers arrive as a message. When `show_doc` is not among your tools, attach the PNG renders if the host takes attachments and list each frame with its intent in the reply. An unattended run leaves the folder in place and reports the checkpoint `unknown` with the page path.

A comment on a frame is Detected feedback for `human-feedback`; revise only the frames it touches and open the page again with them.

## Playbooks

- [compare](playbooks/compare.md): two or more directions for the person to choose between.
- [refine](playbooks/refine.md): one direction carried to every screen, state, and size the build needs.
- [motion](playbooks/motion.md): transitions, feedback, and loading states as looping animated SVG.

## References

- [Canvases](references/canvases.md): canvas sizes and platform conventions for native, web, and print frames.
