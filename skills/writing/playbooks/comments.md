# Comments

**You own the comments, not the code.** No behavior changes.

1. Keep a comment only for a non-obvious why the code cannot show and whose cause lies outside this codebase (vendor, platform, protocol): a constraint, a workaround with its cause. Also keep license headers, doc comments that define a public API contract, tool directives, and links to the issue or RFC behind a constraint.
2. Delete comments that narrate what the code does, mark phases, or restate names; a test or script documents its step through its assertion text.
3. A comment that asserts a constraint ("IMPORTANT", "do not remove") stays only after you check on the named symbol that it holds today; delete one you cannot verify and report it, because an unchecked claim protects dead code.
4. A surprise in our own code, or a constraint the code could enforce (a type, an assertion, a check), is a reshape target: report it as a follow-up with the comment's text and the exact symbol, and drop the comment.
5. List each lint or type suppression (`eslint-disable`, `@ts-ignore`, `noqa`) with the rule it silences; where that rule guards correctness or safety, report the suppressed symbol as a follow-up. The directive stays in this pass.
6. Verify that the diff touches only comments and that the project's tests still pass.

**Reply:** comments removed and rewritten by count, the follow-ups, the suppressions listed, and the test result.
