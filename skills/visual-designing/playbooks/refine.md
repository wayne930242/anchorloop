# Refine

**You own a frame set the build can follow without guessing.**

1. List the frames: every screen in the flow, and for each the states a person meets (empty, loading, filled, longest real content, error, confirm), at every size the product ships and in dark mode when it has one.
2. Start from the approved frame. Copy its `<style>` and `<defs>` into every frame unchanged, so a later direction change is one replacement across the folder.
3. For each component with states (default, hover, pressed, focus, disabled), draw an element state sheet: one `<g data-states="Button">` holding one `<g data-state="…">` layer per state, with the layers switching only `visibility="hidden"`, and the first one visible. The self-check confirms every state's outer box matches the first state's, so a state change never shifts layout; a border that grows draws inside the box, and a focus ring or shadow sits in a `data-overlay=""` part.
4. Draw the frames, self-check, and hand over without `pick`.
5. Revise only the frames that got comments and hand over those again, until every frame is accepted.
6. On acceptance the frames become the build reference: copy them with `cp` where the project keeps design references, else to a gitignored folder in the project, because `/tmp` does not survive a reboot, and name that path in the `coding` feature work that builds them. Delete the copies the user does not keep once the build has landed.

**Reply:** each frame with its verdict (accepted, commented, or `unknown`), the revisions made, and where the approved frames live.
