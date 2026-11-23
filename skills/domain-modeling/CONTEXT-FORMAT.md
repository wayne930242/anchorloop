# CONTEXT.md Format

```md
# {Context Name}

{One or two sentences: what this context is and why it exists.}

## Language

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request
```

- Pick one word per concept and list the others under `_Avoid_`.
- Define what a term is, in one or two sentences, not what it does.
- Include only terms specific to this context; general programming concepts stay out.
- Group terms under subheadings when natural clusters emerge.

One context: a root `CONTEXT.md`, created when the first term is resolved. Several: a root `CONTEXT-MAP.md` lists each context's `CONTEXT.md` with one line on what it owns, then the relationships (`**Ordering → Fulfillment**: Ordering emits OrderPlaced; Fulfillment consumes it`). Infer which context the topic belongs to; ask when unclear.
