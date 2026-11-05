# UAT

**You own the person's verdict on each screen, and the cleanup after it.**

1. **List the checkpoints.** From the acceptance criteria, the spec, or the change, list each flow and every screen a person meets in it: the happy path plus confirm and cancel prompts, errors and refusals, empty and loading states, the end state, and the narrow (phone) layout when the UI has one, because a pass that shoots only the happy path misses the screens that break.
2. **Run the flow and capture.** Drive the real interface through the user's path with the tool that reaches it: the project's e2e runner or a browser automation tool for a web app, computer use for a desktop app, a terminal capture for a TUI. Save one screenshot per checkpoint as `/tmp/uat-<task>/NN-<flow>-<state>.png`, outside the repository, so no capture lands in a commit.
3. **Read every screenshot yourself.** Open each PNG; fix a defect you can see and recapture before the person looks, so their time goes to judgment.
4. **Hand over.** Write `/tmp/uat-<task>/uat.md` with one `review` block: an item per screenshot, `label` the flow and state, `body` the steps that reached it and the result the criterion expects. Open it with `show_doc` and `view: "page"`, say that a blank box means accepted, and end the turn; the submission arrives as a message. When `show_doc` is not among your tools or opens nothing, list each screenshot path with its expected result in the reply instead. An unattended run leaves the page and captures in place and reports the checkpoint `unknown` with the page path.
5. **Record the verdict** with `anchorloop_stage verify` as a human checkpoint. A comment on an item enters **Diagnose** as Detected feedback; after the fix, recapture only the affected checkpoints and open the page again with them.
6. **Clean up after acceptance.** Once every item is accepted, delete `/tmp/uat-<task>/` and stop the servers, browser sessions, and test data the run started, confirming each by PID or port.

**Reply:** each checkpoint with its verdict (accepted, commented, or `unknown`), the fixes made after comments, and the cleanup done.
