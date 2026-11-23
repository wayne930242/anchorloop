# Apply friction notes

**You own one action per note.** A note pairs what an instruction said (`Led by`) with what the run found (`Found`).

1. A note with no before/after contrast (the failed attempt and what revealed the cause) gets no placement; record it as unsupported.
2. **Misdirection**, when `Led by` states or implies something `Found` contradicts: rewrite that line to state what `Found` established, or delete it.
3. **Gap**, when no instruction in use states the `Found` fact: search the agent system for it. When it exists, sharpen the pointer or description that should have led there; when it does not, write it as one direct sentence where **Placement** puts it. A fact that names a SHA, tool version, or run-specific path becomes the durable rule or a check, because the detail drifts. A tool slip no instruction owns needs no placement.
4. Choose the **Mechanism** before writing prose, then **Hold the Size**. An action that stays prose says why no higher level held it.

**Reply:** one pair per note:

```text
Friction: <Found> (misdirection | gap)
Action: <corrected line | sharpened pointer | placed at <location> | enforced by <check> | unsupported>
```
