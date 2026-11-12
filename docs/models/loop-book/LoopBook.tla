------------------------------ MODULE LoopBook ------------------------------
(* One loop book as the agent meets it: what the book counts as the last change, the check and the review after it,
   post-landing observations, linked subagents, the turn-end notice, and close.

   The code under the model: pi/support/phases.ts (computePhases, evaluate), pi/support/book.ts (lastActIndex,
   withChildActs, isRunEntry), pi/support/units.ts (unitEntries), pi/support/landing.ts (watched, checkLandings,
   declareLanded), pi/book.ts (the tool and the event handlers), pi/second-thought.ts (the notice).

   The book's own variables hold what the phase machine reads. The variables under "what really happened" are not in
   the book: they record the facts each rule is stated in. *)
EXTENDS Naturals

CONSTANTS
  Reviewed,        \* the loop's kind is reviewed (anchor, act, verify, review); otherwise inline
  SubSession,      \* the session is itself a subagent: results of the subagents it starts are not read
  UnitsOwnAnchor,  \* the todo list holds two units, each with its own anchor
  MaxWorkers,      \* workers the loop may start
  OtherRepo,       \* you may write a file in another repository
  Notes,           \* you may write a file git ignores inside the repository
  BashEdits,       \* you may change code through a shell command
  WorkerEdits,     \* a worker may edit in its own worktree
  Observations,    \* you may list an observation to make after landing
  OtherRoles,      \* you may ask a subagent whose role is not reviewer for the review
  Failures,        \* the anchor may fail and a review may block
  Declares,        \* you may declare skip and back
  Turns,           \* your run may end (the turn-end notice is in the model)
  Wakes            \* someone other than your own subagent may start your next run

VARIABLES
  \* what the book holds, as the phase machine reads it
  acted,        \* an edit or a counted landing is in the book
  run,          \* the latest run of the anchor after the last change the book counts: none, pass, fail
  review,       \* the latest review round after that change: none, clear, blocking
  observe,      \* an observation is listed
  landed,       \* a landing the book counts
  seen,         \* the observation was declared seen after the last landing
  linked,       \* the book holds a link to a subagent (only then is a ref watched for landings)
  skipV, skipR, \* skip declared for verify, for review
  pushed,       \* your commits are on the remote
  \* subagents
  busy,         \* workers without a result
  reviewerOut,  \* none, reviewer, other: who is reading the change now
  \* the turn
  idle,         \* your run has ended
  runWaits,     \* this run started a subagent (the notice does not judge it)
  news,         \* the book gained evidence since the notice last judged it
  \* the end
  todo,         \* open, settled (done or given a followup)
  closed,
  \* what really happened (not in the book)
  fresh,        \* a run the book counted passed, and nothing the anchor tests changed since, nor did you take it back
  declared,     \* the tool answered ok to a declared passing verify after the last change the book counts
  changed,      \* code the anchor tests changed after the last pass the book counts
  judgedBusy,   \* the notice judged the loop while a subagent it started had not returned
  clearTold,    \* a subagent reported Blocking P0=0 P1=0 after the last change the book counts
  missed,       \* the code changed while the reviewer was reading
  blind         \* the review in the book did not read the latest code

vars == << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
           news, todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

TypeOK ==
  /\ acted \in BOOLEAN /\ run \in {"none", "pass", "fail"} /\ review \in {"none", "clear", "blocking"}
  /\ observe \in BOOLEAN /\ landed \in BOOLEAN /\ seen \in BOOLEAN /\ linked \in BOOLEAN
  /\ skipV \in BOOLEAN /\ skipR \in BOOLEAN /\ pushed \in BOOLEAN
  /\ busy \in 0..MaxWorkers /\ reviewerOut \in {"none", "reviewer", "other"}
  /\ idle \in BOOLEAN /\ runWaits \in BOOLEAN /\ news \in BOOLEAN
  /\ todo \in {"open", "settled"} /\ closed \in BOOLEAN
  /\ fresh \in BOOLEAN /\ declared \in BOOLEAN /\ changed \in BOOLEAN /\ judgedBusy \in BOOLEAN
  /\ clearTold \in BOOLEAN /\ missed \in BOOLEAN /\ blind \in BOOLEAN

Init ==
  /\ acted = FALSE /\ run = "none" /\ review = "none" /\ observe = FALSE /\ landed = FALSE /\ seen = FALSE
  /\ linked = FALSE /\ skipV = FALSE /\ skipR = FALSE /\ pushed = FALSE /\ busy = 0 /\ reviewerOut = "none"
  /\ idle = FALSE /\ runWaits = FALSE /\ news = FALSE /\ todo = "open" /\ closed = FALSE
  /\ fresh = FALSE /\ declared = FALSE /\ changed = FALSE /\ judgedBusy = FALSE /\ clearTold = FALSE
  /\ missed = FALSE /\ blind = FALSE

\* ---- the phase machine's reading (phases.ts evaluate) ----
ObsOpen    == observe /\ ~(landed /\ seen)
VerifyDone == skipV \/ (run = "pass" /\ ~ObsOpen)
ReviewDone == ~Reviewed \/ skipR \/ review = "clear"
Complete   == acted /\ VerifyDone /\ ReviewDone
Phase ==
  IF ~acted THEN "act"
  ELSE IF ~VerifyDone THEN (IF run = "fail" THEN "fix" ELSE "verify")
  ELSE IF ~ReviewDone THEN (IF review = "blocking" THEN "fix" ELSE "review")
  ELSE "close"

Working == ~closed /\ ~idle

\* What every change the book counts does to it: an edit entry moves the last change past the run and the review.
BookAct ==
  /\ acted' = TRUE /\ run' = "none" /\ review' = "none" /\ news' = TRUE
  /\ declared' = FALSE /\ clearTold' = FALSE /\ blind' = FALSE

\* ---- you change things ----
EditHome ==            \* write or edit of a file in the checkout the anchor runs in
  /\ Working /\ BookAct
  /\ pushed' = FALSE /\ fresh' = FALSE /\ changed' = TRUE /\ missed' = (missed \/ reviewerOut # "none")
  /\ UNCHANGED << observe, landed, seen, linked, skipV, skipR, busy, reviewerOut, idle, runWaits, todo, closed, judgedBusy >>

EditOther ==           \* a file in another git repository: outsideWork() is false for it, so it is an edit entry
  /\ OtherRepo /\ Working /\ BookAct
  /\ UNCHANGED << observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits, todo, closed,
                  fresh, changed, judgedBusy, missed >>

WriteNote ==           \* a file git ignores, or a note, inside the repository: also an edit entry
  /\ Notes /\ Working /\ BookAct
  /\ UNCHANGED << observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits, todo, closed,
                  fresh, changed, judgedBusy, missed >>

BashEdit ==            \* sed, a formatter, a generator, git checkout: the book records nothing
  /\ BashEdits /\ Working /\ ~changed
  /\ fresh' = FALSE /\ changed' = TRUE /\ missed' = (missed \/ reviewerOut # "none")
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle,
                  runWaits, news, todo, closed, declared, judgedBusy, clearTold, blind >>

\* ---- you check ----
RunPasses ==
  /\ Working /\ run' = "pass" /\ fresh' = TRUE /\ changed' = FALSE /\ news' = TRUE
  /\ UNCHANGED << acted, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, declared, judgedBusy, clearTold, missed, blind >>

RunFails ==
  /\ Failures /\ Working /\ run' = "fail" /\ fresh' = FALSE /\ declared' = FALSE /\ news' = TRUE
  /\ UNCHANGED << acted, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, changed, judgedBusy, clearTold, missed, blind >>

DeclareVerify ==       \* anchorloop_stage verify with a note and no task: the tool answers ok
  /\ Working /\ ~declared /\ declared' = TRUE /\ news' = TRUE
  /\ IF UnitsOwnAnchor
       THEN UNCHANGED << run, fresh, changed >>     \* units.ts: a unit with its own anchor does not keep the entry
       ELSE run' = "pass" /\ fresh' = TRUE /\ changed' = FALSE
  /\ UNCHANGED << acted, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, judgedBusy, clearTold, missed, blind >>

DeclareVerifyTask ==   \* the same with task: counts for that unit
  /\ UnitsOwnAnchor /\ Working /\ run # "pass"
  /\ run' = "pass" /\ fresh' = TRUE /\ changed' = FALSE /\ declared' = TRUE /\ news' = TRUE
  /\ UNCHANGED << acted, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, judgedBusy, clearTold, missed, blind >>

\* ---- observations and landing ----
AddObserve ==          \* kind with observe
  /\ Observations /\ Working /\ ~observe /\ observe' = TRUE /\ news' = TRUE
  /\ UNCHANGED << acted, run, review, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

Push ==                \* landing.ts: a ref is watched only when the book holds a link
  /\ Observations /\ Working /\ acted /\ ~pushed /\ pushed' = TRUE
  /\ IF linked THEN landed' = TRUE /\ seen' = FALSE /\ news' = TRUE ELSE UNCHANGED << landed, seen, news >>
  /\ UNCHANGED << acted, run, review, observe, linked, skipV, skipR, busy, reviewerOut, idle, runWaits, todo, closed,
                  fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

DeclareSeen ==         \* verify with checkpoint, after the landing
  /\ Working /\ observe /\ landed /\ ~seen /\ seen' = TRUE /\ news' = TRUE
  /\ UNCHANGED << acted, run, review, observe, landed, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

\* ---- subagents ----
StartWorker ==
  /\ Working /\ busy < MaxWorkers /\ busy' = busy + 1 /\ linked' = TRUE /\ runWaits' = TRUE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, skipV, skipR, pushed, reviewerOut, idle, news, todo, closed,
                  fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

WorkerEditsItsTree ==  \* withChildActs: a linked child's edit entry is the coordinator's last change
  /\ WorkerEdits /\ ~closed /\ busy > 0 /\ BookAct
  /\ UNCHANGED << observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle, runWaits, todo, closed,
                  fresh, changed, judgedBusy, missed >>

WorkerReturns ==
  /\ ~closed /\ busy > 0 /\ busy' = busy - 1 /\ idle' = FALSE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, reviewerOut, runWaits, news,
                  todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

AskReview(role) ==
  /\ Reviewed /\ Working /\ acted /\ reviewerOut = "none"
  /\ reviewerOut' = role /\ linked' = TRUE /\ runWaits' = TRUE /\ missed' = FALSE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, skipV, skipR, pushed, busy, idle, news, todo, closed,
                  fresh, declared, changed, judgedBusy, clearTold, blind >>

AskReviewer == AskReview("reviewer")
AskOtherRole == OtherRoles /\ AskReview("other")

ReviewReturns(verdict) ==   \* book.ts: only a result of role reviewer, in a session that is not a subagent, is a review entry
  /\ ~closed /\ reviewerOut # "none" /\ reviewerOut' = "none" /\ idle' = FALSE /\ missed' = FALSE
  /\ clearTold' = (verdict = "clear")
  /\ IF reviewerOut = "reviewer" /\ ~SubSession
       THEN review' = verdict /\ news' = TRUE /\ blind' = (verdict = "clear" /\ missed)
       ELSE UNCHANGED << review, news, blind >>
  /\ UNCHANGED << acted, run, observe, landed, seen, linked, skipV, skipR, pushed, busy, runWaits, todo, closed,
                  fresh, declared, changed, judgedBusy >>

ReviewClear == ReviewReturns("clear")
ReviewBlocks == Failures /\ ReviewReturns("blocking")

\* ---- declarations ----
SkipVerify ==
  /\ Declares /\ Working /\ ~skipV /\ skipV' = TRUE /\ news' = TRUE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipR, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

SkipReview ==
  /\ Declares /\ Reviewed /\ Working /\ ~skipR /\ skipR' = TRUE /\ news' = TRUE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, pushed, busy, reviewerOut, idle, runWaits,
                  todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

BackToVerify ==        \* phases.ts floor(): nothing before the back counts for verify or a later phase
  /\ Declares /\ Working /\ (run # "none" \/ review # "none" \/ skipV \/ skipR \/ seen)
  /\ run' = "none" /\ review' = "none" /\ skipV' = FALSE /\ skipR' = FALSE /\ seen' = FALSE /\ news' = TRUE
  /\ fresh' = FALSE /\ declared' = FALSE /\ clearTold' = FALSE /\ blind' = FALSE
  /\ UNCHANGED << acted, observe, landed, linked, pushed, busy, reviewerOut, idle, runWaits, todo, closed, changed,
                  judgedBusy, missed >>

\* ---- the turn ----
TurnEnds ==            \* second-thought.ts: judged when this run started no subagent and the book has new evidence
  /\ Turns /\ Working /\ idle' = TRUE /\ runWaits' = FALSE
  /\ IF ~runWaits /\ news
       THEN news' = FALSE /\ judgedBusy' = (judgedBusy \/ busy > 0 \/ reviewerOut # "none")
       ELSE UNCHANGED << news, judgedBusy >>
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, todo,
                  closed, fresh, declared, changed, clearTold, missed, blind >>

Wake ==                \* the user, another session, a monitor
  /\ Wakes /\ ~closed /\ idle /\ idle' = FALSE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, runWaits,
                  news, todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

\* ---- the end ----
SettleTodo ==
  /\ Working /\ todo = "open" /\ todo' = "settled"
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle,
                  runWaits, news, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

Close ==               \* book.ts close(): refuses only while an open todo has no followup
  /\ Working /\ todo = "settled" /\ closed' = TRUE
  /\ UNCHANGED << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle,
                  runWaits, news, todo, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

Next ==
  \/ EditHome \/ EditOther \/ WriteNote \/ BashEdit
  \/ RunPasses \/ RunFails \/ DeclareVerify \/ DeclareVerifyTask
  \/ AddObserve \/ Push \/ DeclareSeen
  \/ StartWorker \/ WorkerEditsItsTree \/ WorkerReturns
  \/ AskReviewer \/ AskOtherRole \/ ReviewClear \/ ReviewBlocks
  \/ SkipVerify \/ SkipReview \/ BackToVerify
  \/ TurnEnds \/ Wake \/ SettleTodo \/ Close

Spec == Init /\ [][Next]_vars

\* What small.cfg tells TLC to compare states by: with no turn end in the config, these two flags decide nothing.
NoTurnView == << acted, run, review, observe, landed, seen, linked, skipV, skipR, pushed, busy, reviewerOut, idle,
                 todo, closed, fresh, declared, changed, judgedBusy, clearTold, missed, blind >>

\* ---- the rules (all proposed; the reader confirms them) ----

\* 1. A check that passed stays passed until something the anchor tests changes, or you take it back.
KeptDone == fresh => run = "pass"

\* 2. A verify the tool answered ok to counts: the book does not ask for it again before the next change.
AcceptedCounts == declared => run = "pass"

\* 3. A review that came back Blocking P0=0 P1=0 after the last change counts as the review.
ReportedReviewCounts == clearTold => review = "clear"

\* 4. A loop can always be finished complete with evidence: while a phase is missing, somebody has a step that supplies it.
\*    SomebodyHasAStep lists what each actor is taken to do: you edit, run or declare the anchor, declare an observation
\*    once the work landed; a push or the integrator's merge is recorded as the landing when a ref is watched; a reviewer
\*    you start returns and its result is read. `skip` is not evidence, and starting a subagent only to get a ref watched
\*    is not a step anybody would think of.
SomebodyHasAStep ==
  \/ ~acted
  \/ (~skipV /\ run # "pass")
  \/ (run = "pass" /\ ObsOpen /\ landed)
  \/ (run = "pass" /\ ObsOpen /\ ~landed /\ linked)
  \/ (VerifyDone /\ ~ReviewDone /\ ~SubSession)
CanFinish == (~closed /\ ~Complete) => SomebodyHasAStep

\* 5. While a subagent the loop started has not returned, the turn-end notice does not judge the loop.
QuietWhileWaiting == ~judgedBusy

\* 6. The book never shows the check as passed for code that changed after it ran.
NoStalePass == run = "pass" => ~changed

\* 7. The book never shows a review as clear when the code changed while the reviewer was reading.
ReviewReadTheChange == review = "clear" => ~blind

\* 8. Close never needs phase evidence: once every todo is done or has a followup, close is accepted.
CloseNeedsOnlyTodos == (Working /\ todo = "settled") => ENABLED Close

=============================================================================
