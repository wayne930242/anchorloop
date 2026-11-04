# Migrate callers, then delete

**When:** Replacing an API no caller outside the change depends on (other repos, deployed versions, and clients count as outside).

Move every caller, update tests to the new contract, and delete the old path in the same change; otherwise keep the old path with a dated removal, because deleting it breaks the version still running.
