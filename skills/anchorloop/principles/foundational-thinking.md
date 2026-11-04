# Foundational thinking

**When:** Before writing logic or integrating a new requirement.

Choose the data shape and its organizing structure first, as if the requirement had been there from day one, so the code that follows is obvious. Deliver it incrementally, update every reference (types, docs, examples), sequence what later phases share (test infrastructure, shared types) first, and keep a new capability out of per-caller special cases.
