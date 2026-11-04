# Test behavior, not implementation

**When:** Writing or keeping a test.

Assert what users of the code observe, so the test fails when behavior breaks and survives internal change. Imagine breaking the behavior: a test that still passes proves nothing. Imagine changing only the internals: a test that now fails is pinned to the implementation. Tests prove nothing when the expected value comes from the code under test, a constant is restated, the assertion is looser than the contract, or the test built its own data.
