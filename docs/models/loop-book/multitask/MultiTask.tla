------------------------------ MODULE MultiTask ------------------------------
(* The loop book of a straw-boss coordinator that runs two units at once: two todos with their own anchors, each worked by
   its own child (pi-herdr-agents subagents in their own worktrees), one persistent reviewer, sb car notices, and the turn
   ends the many wakes of such a session start. The single-loop model beside it (../LoopBook.tla) covers one unit; this one
   covers what one unit's steps do to the other, and what the turn-end notice says while children are out.

   `Design` and `Fixes` pick the code under the model:
   - "today": the code at 04f083a (pi/support/units.ts unitEntries and computeLoop, pi/support/book.ts withChildActs,
     pi/book.ts adoptChildRun and the tool, pi/support/landing.ts declareLanded, pi/second-thought.ts).
   - "decided": today plus the boss's decisions on issues #2 to #8 (2026-11-12), read as the code would build them: a
     verify records the working trees of the loop's repos and counts while they are unchanged, as child checks do today
     (pi/book.ts treesField, loopTrees), and no longer by its order against edit entries; while a child the loop started has
     no result, the notice neither judges nor continues. #3, #4, #5 and #8 change nothing on these paths.
   - `Fixes`: with "decided", the changes design.md proposes on top of it, P1 to P8, each marked where it acts below;
     every one of them is the proposed design, and each run without one shows what that one is for.

   The book's variables hold what the phase machine reads for each unit; the variables under "what really happened" are not
   in the book, and the rules are stated in them. *)
EXTENDS Naturals

CONSTANTS
  Design,      \* "today" or "decided"
  Fixes,       \* a subset of {"P1", ..., "P8"}, with "decided" only
  Turns,       \* the coordinator's turn ends and the turn-end notice may speak
  Wakes,       \* someone else starts a turn: the user or a form, a tower reply, another main's ask, a late monitor wake
  Todos,       \* a todo is added or completed (a checkpoint, a follow-up, another unit), so the open-todo list changes
  Reloads,     \* /reload after an install
  Fails,       \* a child dies (model quota) and its failed result arrives; the coordinator starts it again
  Resumes,     \* the coordinator sends a returned child a follow-up, and it edits again
  CoordEdits,  \* the coordinator changes one unit's code itself (then it carries that unit's car itself)
  Backs,       \* sb returns a unit's car: the coordinator declares back with that unit's task
  Reviews,     \* units are reviewed, by one persistent reviewer sent each unit in turn
  Lands,       \* units land through an sb car: the coordinator declares the landed notice, then the observation
  Handoffs,    \* the session rotates through a scratch handoff to a new session
  Declares,    \* the coordinator declares a unit's passing verify with its `task`
  RunWaits     \* (cause switch) a run that started a subagent ends unjudged, as second-thought.ts does; FALSE only in causes/

U == {"a", "b"}
\* "a" is the first unit: the loop line and today's notice follow the first unit not done, and its anchor is the loop's.
Other(u) == IF u = "a" THEN "b" ELSE "a"
F(p) == p \in Fixes

VARIABLES
  \* what the book holds, per unit, as the phase machine reads it
  acted,      \* a change counts for the unit
  pass,       \* a passing run of the unit's anchor counts after that change
  clear,      \* a review with Blocking P0=0 P1=0 counts after that change
  landed,     \* a landing counts, and the observation after it
  \* the actors
  child,      \* the unit's worker: idle (never started), out (no edit yet), edited, back (returned), failed
  rev,        \* the unit the persistent reviewer reads now, or none
  revOf,      \* the unit the reviewer's link is bound to (the unit of its first dispatch), or none
  \* the turn and the notice
  idle,       \* the coordinator's turn is over
  waits,      \* this run started a subagent
  newEv,      \* the book gained an evidence entry since the notice last judged it (in memory)
  told,       \* the advisory key last sent (in memory): the phase name, for the same open-todo list
  said,       \* the unit the last turn-end notice asked for a step, or none
  forgot,     \* the notice lost its memory of what it asked (a /reload or a new session) and has not judged since
  handed,     \* the session was handed off once
  closed,
  \* what really happened (not in the book)
  done,       \* the unit's code is written, and no returned car undid it
  fresh,      \* the unit's anchor passed on the unit's own code, and that code has not changed since
  toldClear,  \* a reviewer reported Blocking P0=0 P1=0 for the unit after its last change
  inRef,      \* the unit's car landed
  carried,    \* the coordinator did the unit's work itself, so its car is the coordinator's own push
  declared,   \* the tool answered ok to a verify with the unit's task since its last change
  dirty,      \* something about the unit changed since the notice last asked for its step
  asked,      \* the step the notice last asked of the unit
  crossUndo,  \* a step for one unit took a check, a review, or a landing away from the other
  spam,       \* a notice asked a unit for the step it had already asked, with nothing changed for that unit
  waitAsk,    \* a notice asked for the step of a unit whose child (worker or reviewer) was out
  judgedBusy, \* the notice judged the loop while a child the loop started was out
  muted       \* a turn ended with a unit waiting on the coordinator, unasked since its last change, and no notice named one

vars == << acted, pass, clear, landed, child, rev, revOf, idle, waits, newEv, told, said, forgot, handed, closed,
           done, fresh, toldClear, inRef, carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

Bools == [U -> BOOLEAN]
StepNames == {"none", "act", "verify", "review", "land", "close"}

TypeOK ==
  /\ acted \in Bools /\ pass \in Bools /\ clear \in Bools /\ landed \in Bools
  /\ child \in [U -> {"idle", "out", "edited", "back", "failed"}] /\ rev \in U \cup {"none"} /\ revOf \in U \cup {"none"}
  /\ idle \in BOOLEAN /\ waits \in BOOLEAN /\ newEv \in BOOLEAN /\ told \in StepNames /\ said \in U \cup {"none"} /\ forgot \in BOOLEAN /\ handed \in BOOLEAN /\ closed \in BOOLEAN
  /\ done \in Bools /\ fresh \in Bools /\ toldClear \in Bools /\ inRef \in Bools /\ carried \in Bools /\ declared \in Bools
  /\ dirty \in Bools /\ asked \in [U -> StepNames]
  /\ crossUndo \in BOOLEAN /\ spam \in BOOLEAN /\ waitAsk \in BOOLEAN /\ judgedBusy \in BOOLEAN /\ muted \in BOOLEAN

No == [u \in U |-> FALSE]
All == [u \in U |-> TRUE]

Init ==
  /\ acted = No /\ pass = No /\ clear = No /\ landed = No
  /\ child = [u \in U |-> "idle"] /\ rev = "none" /\ revOf = "none"
  /\ idle = FALSE /\ waits = FALSE /\ newEv = TRUE /\ told = "none" /\ said = "none" /\ forgot = FALSE /\ handed = FALSE /\ closed = FALSE
  /\ done = No /\ fresh = No /\ toldClear = No /\ inRef = No /\ carried = No /\ declared = No
  /\ dirty = No /\ asked = [u \in U |-> "none"]
  /\ crossUndo = FALSE /\ spam = FALSE /\ waitAsk = FALSE /\ judgedBusy = FALSE /\ muted = FALSE

\* ---- the phase machine's reading, per unit ----
Complete(u) == acted[u] /\ pass[u] /\ (~Reviews \/ clear[u]) /\ (~Lands \/ landed[u])
Step(u) ==
  IF ~acted[u] THEN "act"
  ELSE IF ~pass[u] THEN "verify"
  ELSE IF Reviews /\ ~clear[u] THEN "review"
  ELSE IF Lands /\ ~landed[u] THEN "land"
  ELSE "close"
Out(u) == child[u] \in {"out", "edited"} \/ rev = u
AnyOut == \E u \in U : Out(u)
Working == ~closed /\ ~idle

\* The other unit lost a check, a review or a landing that still held for it.
Undid(p2, c2, u) == LET v == Other(u) IN (pass[v] /\ fresh[v] /\ ~p2[v]) \/ (clear[v] /\ toldClear[v] /\ ~c2[v])

\* ---- the coordinator's children ----
Spawn(u) ==            \* subagent with the unit's agent name: linked and bound to the unit
  /\ Working /\ ~done[u] /\ child[u] \in {"idle", "back", "failed"}
  /\ child' = [child EXCEPT ![u] = "out"] /\ waits' = TRUE
  /\ UNCHANGED << acted, pass, clear, landed, rev, revOf, idle, newEv, told, said, forgot, handed, closed, done, fresh, toldClear, inRef,
                  carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

Resume(u) ==           \* subagent_send to a returned child: a follow-up after its check
  /\ Resumes /\ Working /\ child[u] = "back" /\ done[u] /\ fresh[u]
  /\ child' = [child EXCEPT ![u] = "out"] /\ waits' = TRUE
  /\ UNCHANGED << acted, pass, clear, landed, rev, revOf, idle, newEv, told, said, forgot, handed, closed, done, fresh, toldClear, inRef,
                  carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

ChildEdits(u) ==       \* withChildActs: the child's edit entries count for its own unit; not an entry of the coordinator's book
  /\ ~closed /\ child[u] = "out"
  /\ child' = [child EXCEPT ![u] = "edited"]
  /\ acted' = [acted EXCEPT ![u] = TRUE]
     \* decided: the verify recorded the loop's trees, which a worktree edit does not change, and edits no longer order it.
     \* P1: a unit's verify records the tree its run was in, here the worker's worktree.
  /\ pass' = IF Design = "decided" /\ ~F("P1") THEN pass ELSE [pass EXCEPT ![u] = FALSE]
  /\ clear' = [clear EXCEPT ![u] = FALSE]
  /\ fresh' = [fresh EXCEPT ![u] = FALSE] /\ toldClear' = [toldClear EXCEPT ![u] = FALSE] /\ declared' = [declared EXCEPT ![u] = FALSE]
  /\ dirty' = [dirty EXCEPT ![u] = TRUE]
  /\ UNCHANGED << landed, rev, revOf, idle, waits, newEv, told, said, forgot, handed, closed, done, inRef, carried, asked, crossUndo, spam,
                  waitAsk, judgedBusy, muted >>

ChildReturns(u) ==     \* its result arrives as a steer message; it ran its unit's anchor in its worktree, and it passed
  /\ ~closed /\ child[u] = "edited"
  /\ child' = [child EXCEPT ![u] = "back"] /\ idle' = FALSE
  /\ done' = [done EXCEPT ![u] = TRUE] /\ fresh' = [fresh EXCEPT ![u] = TRUE] /\ dirty' = [dirty EXCEPT ![u] = TRUE]
     \* adoptChildRun adopts only a run of the loop's anchor, the first unit's; a child inherits that anchor too.
     \* P2: a child bound to a unit inherits the unit's anchor, and its passing run is adopted for that unit.
  /\ IF u = "a" \/ F("P2")
       THEN pass' = [pass EXCEPT ![u] = TRUE] /\ newEv' = TRUE
       ELSE UNCHANGED << pass, newEv >>
  /\ UNCHANGED << acted, clear, landed, rev, revOf, waits, told, said, forgot, handed, closed, toldClear, inRef, carried, declared, asked,
                  crossUndo, spam, waitAsk, judgedBusy, muted >>

ChildFails(u) ==       \* model quota or a crash: a failed result arrives, with no check
  /\ Fails /\ ~closed /\ child[u] \in {"out", "edited"}
  /\ child' = [child EXCEPT ![u] = "failed"] /\ idle' = FALSE /\ dirty' = [dirty EXCEPT ![u] = TRUE]
  /\ UNCHANGED << acted, pass, clear, landed, rev, revOf, waits, newEv, told, said, forgot, handed, closed, done, fresh, toldClear, inRef,
                  carried, declared, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

\* ---- the coordinator itself ----
CoordEdit(u) ==        \* a write in the coordinator's own checkout of the unit's repository: an edit entry
  /\ CoordEdits /\ Working /\ ~Out(u) /\ (pass[u] \/ ~done[u])
     \* today: the edit entry is every unit's last change. decided: it changed a tree every unit's verify recorded.
  /\ LET p2 == IF F("P1") THEN [pass EXCEPT ![u] = FALSE] ELSE No    \* P1: a unit's verify records the tree its run was in
         c2 == IF F("P3") THEN [clear EXCEPT ![u] = FALSE] ELSE No   \* P3: an edit entry is the change of the unit whose tree it touches
         a2 == IF F("P3") THEN [acted EXCEPT ![u] = TRUE] ELSE All
     IN /\ pass' = p2 /\ clear' = c2 /\ acted' = a2
        /\ crossUndo' = (crossUndo \/ Undid(p2, c2, u))
        /\ dirty' = [v \in U |-> dirty[v] \/ v = u \/ a2[v] # acted[v] \/ p2[v] # pass[v] \/ c2[v] # clear[v]]
  /\ done' = [done EXCEPT ![u] = TRUE] /\ carried' = [carried EXCEPT ![u] = carried[u] \/ child[u] = "idle"]
  /\ fresh' = [fresh EXCEPT ![u] = FALSE] /\ toldClear' = [toldClear EXCEPT ![u] = FALSE] /\ declared' = [declared EXCEPT ![u] = FALSE]
  /\ newEv' = TRUE
  /\ UNCHANGED << landed, child, rev, revOf, idle, waits, told, said, forgot, handed, closed, inRef, asked, spam, waitAsk, judgedBusy, muted >>

RunAnchor(u) ==        \* the coordinator runs the unit's anchor (a task run) on the unit's code: it passes
  /\ Working /\ acted[u] /\ ~pass[u] /\ done[u] /\ ~Out(u)
  /\ pass' = [pass EXCEPT ![u] = TRUE] /\ fresh' = [fresh EXCEPT ![u] = TRUE] /\ dirty' = [dirty EXCEPT ![u] = TRUE] /\ newEv' = TRUE
  /\ UNCHANGED << acted, clear, landed, child, rev, revOf, idle, waits, told, said, forgot, handed, closed, done, toldClear, inRef, carried,
                  declared, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

DeclareVerify(u) ==    \* verify with a note and the unit's task: answered ok; it counts only after a change in this book
  /\ Declares /\ Working /\ fresh[u] /\ ~pass[u] /\ ~declared[u]
  /\ declared' = [declared EXCEPT ![u] = TRUE] /\ pass' = [pass EXCEPT ![u] = acted[u]]
  /\ dirty' = [dirty EXCEPT ![u] = TRUE] /\ newEv' = TRUE
  /\ UNCHANGED << acted, clear, landed, child, rev, revOf, idle, waits, told, said, forgot, handed, closed, done, fresh, toldClear, inRef,
                  carried, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

Back(u) ==             \* sb's notice: the unit's car was returned; back with its task (phases.ts floor)
  /\ Backs /\ Working /\ done[u] /\ fresh[u] /\ ~inRef[u] /\ ~Out(u)
  /\ LET p2 == IF F("P3") THEN [pass EXCEPT ![u] = FALSE] ELSE No    \* P3: back and skip with a task floor that unit only
         c2 == IF F("P3") THEN [clear EXCEPT ![u] = FALSE] ELSE No
     IN /\ pass' = p2 /\ clear' = c2
        /\ crossUndo' = (crossUndo \/ Undid(p2, c2, u))
        /\ dirty' = [v \in U |-> dirty[v] \/ v = u \/ p2[v] # pass[v] \/ c2[v] # clear[v]]
  /\ done' = [done EXCEPT ![u] = FALSE] /\ fresh' = [fresh EXCEPT ![u] = FALSE]
  /\ toldClear' = [toldClear EXCEPT ![u] = FALSE] /\ declared' = [declared EXCEPT ![u] = FALSE] /\ newEv' = TRUE
  /\ UNCHANGED << acted, landed, child, rev, revOf, idle, waits, told, said, forgot, handed, closed, inRef, carried, asked, spam, waitAsk,
                  judgedBusy, muted >>

\* ---- the persistent reviewer ----
SendReview(u) ==       \* the first dispatch links the reviewer to that unit; later ones are subagent_send to the same child
  /\ Reviews /\ Working /\ rev = "none" /\ acted[u] /\ fresh[u] /\ ~toldClear[u] /\ ~Out(u)
  /\ rev' = u /\ revOf' = (IF revOf = "none" THEN u ELSE revOf) /\ waits' = TRUE
  /\ UNCHANGED << acted, pass, clear, landed, child, idle, newEv, told, said, forgot, handed, closed, done, fresh, toldClear, inRef, carried,
                  declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

ReviewBack ==          \* Blocking P0=0 P1=0 for the unit it read; the book records it for the unit the reviewer is bound to
  /\ Reviews /\ ~closed /\ rev # "none"
  /\ LET r == rev
         c == IF F("P4") THEN rev ELSE revOf                      \* P4: a review binds to the unit its dispatch names
     IN /\ toldClear' = [toldClear EXCEPT ![r] = TRUE] /\ clear' = [clear EXCEPT ![c] = TRUE]
        /\ dirty' = [dirty EXCEPT ![r] = TRUE, ![c] = TRUE]
  /\ rev' = "none" /\ idle' = FALSE /\ newEv' = TRUE
  /\ UNCHANGED << acted, pass, landed, child, revOf, waits, told, said, forgot, handed, closed, done, fresh, inRef, carried, declared, asked,
                  crossUndo, spam, waitAsk, judgedBusy, muted >>

\* ---- the car ----
Land(u) ==             \* the integrator merged the car; sb's landed notice is declared with the unit's task, then the observation
  /\ Lands /\ Working /\ done[u] /\ fresh[u] /\ ~inRef[u] /\ ~Out(u)
  /\ inRef' = [inRef EXCEPT ![u] = TRUE]
     \* declareLanded finds no candidate for a branch the coordinator pushed itself and records rule "declared", which does
     \* not count. P8: the session's own pushed head counts when it is in the landed ref.
  /\ landed' = [landed EXCEPT ![u] = ~carried[u] \/ F("P8")]
  /\ dirty' = [dirty EXCEPT ![u] = TRUE] /\ newEv' = TRUE
  /\ UNCHANGED << acted, pass, clear, child, rev, revOf, idle, waits, told, said, forgot, handed, closed, done, fresh, toldClear, carried,
                  declared, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

\* ---- sessions ----
Handoff ==             \* scratch/handoff-<name>.md, then a new session; the book is <session id>.yml
  /\ Handoffs /\ ~closed /\ ~handed /\ ~AnyOut
  /\ handed' = TRUE /\ idle' = FALSE /\ waits' = FALSE
     \* P7: the new session adopts the open book the handoff names. P6: the notice's memory is read back from that book.
  /\ IF F("P7")
       THEN UNCHANGED << acted, pass, clear, landed, declared >>
       ELSE acted' = No /\ pass' = No /\ clear' = No /\ landed' = No /\ declared' = No
  /\ IF F("P7") /\ F("P6")
       THEN UNCHANGED << newEv, told, forgot >>
       ELSE newEv' = TRUE /\ told' = "none" /\ forgot' = TRUE
  /\ UNCHANGED << child, rev, revOf, said, closed, done, fresh, toldClear, inRef, carried, dirty, asked, crossUndo, spam, waitAsk,
                  judgedBusy, muted >>

Reload ==              \* session_start clears the notice's memory; P6 reads it back from the book's own verdict entries
  /\ Reloads /\ ~closed /\ ~F("P6") /\ (told # "none" \/ ~newEv \/ ~forgot)
  /\ told' = "none" /\ newEv' = TRUE /\ forgot' = TRUE
  /\ UNCHANGED << acted, pass, clear, landed, child, rev, revOf, idle, waits, said, handed, closed, done, fresh, toldClear, inRef,
                  carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

TodoMoves ==           \* the advisory key holds the open todo ids: the next advisory is not the one already sent
  /\ Todos /\ ~closed /\ told # "none" /\ told' = "none"
  /\ UNCHANGED << acted, pass, clear, landed, child, rev, revOf, idle, waits, newEv, said, forgot, handed, closed, done, fresh,
                  toldClear, inRef, carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

Wake ==                \* the user, a form, a tower reply, another main's ask, a monitor wake (maybe late): nothing in the book
  /\ Wakes /\ ~closed /\ idle /\ idle' = FALSE
  /\ UNCHANGED << acted, pass, clear, landed, child, rev, revOf, waits, newEv, told, said, forgot, handed, closed, done, fresh, toldClear,
                  inRef, carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

\* ---- the turn end (second-thought.ts agent_before_settle) ----
Repeat(u) == asked[u] = Step(u) /\ ~dirty[u]
\* A unit waits on the coordinator: started (or worked by it), not complete, and nothing of its own is out.
Owed(u) == ~Complete(u) /\ ~Out(u) /\ (child[u] # "idle" \/ done[u])
LoopUnit == IF ~Complete("a") THEN "a" ELSE IF ~Complete("b") THEN "b" ELSE "none"
\* P5: the notice names the first unit with no child out whose step it has not asked since that unit last changed; a
\* notice that lost its memory takes every such unit as unasked.
Fresh(u) == Owed(u) /\ (forgot \/ ~Repeat(u))
OwedUnit == IF Fresh("a") THEN "a" ELSE IF Fresh("b") THEN "b" ELSE "none"

TurnEnds ==
  /\ Turns /\ Working
  \* "P5u" (causes/ only): P5's choice of unit and key, with the decided quiet while any child is out.
  /\ LET n == IF F("P5") \/ F("P5u") THEN OwedUnit ELSE LoopUnit
         s == IF n = "none" THEN "close" ELSE Step(n)
         wait == RunWaits /\ waits
         judge == CASE F("P5") -> n # "none"
                    [] F("P5u") -> n # "none" /\ ~AnyOut
                    [] Design = "decided" -> ~wait /\ newEv /\ ~AnyOut
                    [] OTHER -> ~wait /\ newEv
         speak == judge /\ (F("P5") \/ F("P5u") \/ s # told)
         named == speak /\ n # "none"
     IN /\ newEv' = (newEv /\ ~judge) /\ forgot' = (forgot /\ ~judge)
        /\ told' = IF speak THEN s ELSE told
        /\ asked' = IF named THEN [asked EXCEPT ![n] = s] ELSE asked
        /\ said' = IF named THEN n ELSE "none"
        /\ dirty' = IF named THEN [dirty EXCEPT ![n] = FALSE] ELSE dirty
        /\ spam' = (spam \/ (named /\ Repeat(n)))
        /\ waitAsk' = (waitAsk \/ (named /\ Out(n)))
        /\ judgedBusy' = (judgedBusy \/ (judge /\ AnyOut))
        /\ muted' = (muted \/ ((\E u \in U : Owed(u) /\ ~Repeat(u)) /\ ~(named /\ Owed(n))))
  /\ idle' = TRUE /\ waits' = FALSE
  /\ UNCHANGED << acted, pass, clear, landed, child, rev, revOf, handed, closed, done, fresh, toldClear, inRef, carried,
                  declared, crossUndo >>

Close ==
  /\ Working /\ \A u \in U : Complete(u) /\ closed' = TRUE
  /\ UNCHANGED << acted, pass, clear, landed, child, rev, revOf, idle, waits, newEv, told, said, forgot, handed, done, fresh, toldClear,
                  inRef, carried, declared, dirty, asked, crossUndo, spam, waitAsk, judgedBusy, muted >>

Next ==
  \/ \E u \in U : Spawn(u) \/ Resume(u) \/ ChildEdits(u) \/ ChildReturns(u) \/ ChildFails(u)
  \/ \E u \in U : CoordEdit(u) \/ RunAnchor(u) \/ DeclareVerify(u) \/ Back(u) \/ SendReview(u) \/ Land(u)
  \/ ReviewBack \/ Handoff \/ Reload \/ TodoMoves \/ Wake \/ TurnEnds \/ Close

Spec == Init /\ [][Next]_vars

\* ---- the rules (all proposed; the reader confirms them) ----

\* M1. What passed, came back clear, or landed for a unit counts for that unit.
Counted == \A u \in U : (fresh[u] => pass[u]) /\ (toldClear[u] => clear[u]) /\ (inRef[u] => landed[u])

\* M2. A unit's book shows a check or a review only of that unit's current code.
NotLent == \A u \in U : (pass[u] => fresh[u]) /\ (clear[u] => toldClear[u])

\* M3. One unit's change, or its returned car, never takes another unit's check or review away.
Isolation == ~crossUndo

\* M4. At most one notice per unit and missing step per real change: a wake that changed nothing for a unit, a late
\*     monitor wake, or a /reload does not ask that unit again.
OnePerChange == ~spam

\* M5. A notice never asks for a step that only a child still out can supply.
AskOnlyOwed == ~waitAsk

\* M6. (decided, #6) While a child the loop started has no result, the notice does not judge the loop.
QuietWhileWaiting == ~judgedBusy

\* M7. When a turn ends with a unit that waits on the coordinator and was not asked since its last change, the notice asks
\*     for the step of a unit that waits on the coordinator, whatever the other units' children are doing.
OwedIsNamed == ~muted

\* M8. The coordinator can always reach close with evidence: while a unit lacks a phase, somebody has a step that
\*     supplies it. Assumed of the coordinator: it starts a unit's worker again after a failure or a returned car, runs a
\*     unit's anchor, sends a checked unit to the reviewer, and sends a car; `skip` is not evidence.
HasStep(u) ==
  \/ Out(u)
  \/ ~done[u]
  \/ (acted[u] /\ ~pass[u])
  \/ (acted[u] /\ pass[u] /\ Reviews /\ ~clear[u])
  \/ (acted[u] /\ pass[u] /\ (~Reviews \/ clear[u]) /\ Lands /\ ~landed[u] /\ ~inRef[u])
CanClose == ~closed => \A u \in U : Complete(u) \/ HasStep(u)

\* M9. A verify the tool answered ok to, with the unit's task, counts for that unit.
AcceptedCounts == \A u \in U : declared[u] => pass[u]

=============================================================================
