---
name: ckore-tdd
description: 'Test-first rules for writing or changing code: a failing test at the right seam, watched failing for the right reason, then the smallest change that turns it green. Used by `ckore-design`''s inline path, every `ckore-build` worker, `ckore-diagnose` phase 5 and `ckore-refactor`. Use when implementing a task, or when the user says "TDD", "test first" or "red-green".'
---

# TDD

Built on superpowers `test-driven-development`, Matt Pocock's `tdd` and poteto's `test-behavior-not-implementation` principle. The test is the proof that the behaviour exists. A test written after the code passes by construction and proves nothing.

**Profile.** "Test and build" gives the per-area test command. Run that area's command, not the whole suite, while iterating.

## The loop, per behaviour

1. **Red.** Write one test for one behaviour, through the public interface a caller uses (the component, the service method, the API handler), not a private helper.
2. **Watch it fail, for the right reason.** Run it and read the failure. "Cannot find module" or a typo is not red. The failure must be the missing behaviour. If it passes at once, the test is wrong or the behaviour already exists. Find out which before going on.
3. **Green.** Write the smallest code that passes. No options, branches or parameters the test doesn't need.
4. **Run the area's tests.** Everything that was green stays green. If an existing test now fails, fix the code, not the test. Loosening an assertion, deleting a test or adding a `skip` needs the user's OK. The one exception is a test whose expected behaviour the spec changes.
5. **Clean up while green**, then re-run. Next behaviour.

Work in vertical slices: one behaviour through all its layers, then the next. Don't write all the tests first, and don't build a layer at a time.

## What makes a test worth keeping

- It fails when the behaviour breaks and keeps passing when only the internals change. Assert what a caller can observe: return values, rendered output, rows written, the HTTP response.
- Expected values are literals from the spec or a real (redacted) record, never recomputed the way the code computes them.
- Mock only at system boundaries: network, time, the Supabase client, third-party APIs. Not your own modules.
- Every stub (`jest.fn()` and the like) the change relies on gets an assertion that it was called, with what. An unasserted stub passes on the old code too (L22).
- One behaviour per test, named after the behaviour ("rejects a booking outside opening hours"), not the method.

## When there is no good seam

Say so instead of writing a shallow test. Options, in order: test one level up where a seam exists; extract the logic into a pure function the real caller uses; or, for UI and integration paths, a smoke check on the real surface (the dev server in the browser pane, or a deployed endpoint per the profile) with the result quoted.

## Done means

The new tests and the area's suite pass, with the command and result quoted in your message. "Should pass" is not a result.
