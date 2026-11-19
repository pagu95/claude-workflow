---
name: ckore-refactor
description: Behaviour-preserving changes to structure (rename, extract, inline, dedupe, move, replace an internal API) with the behaviour pinned by a test before anything moves and proven unchanged after. Also finds where a refactor would pay off when no target is given. Use for "refactor", "clean up", "simplify", "dedupe", "move X to Y", "replace the old API", or when `ckore-review` flagged smells worth fixing in their own PR. New behaviour goes to `ckore-design`, a wrong behaviour to `ckore-diagnose`.
argument-hint: "the code to reshape, or empty to look for candidates"
---

# Refactor

Built on poteto's Refactoring playbook with his `laziness-protocol`, `subtract-before-you-add`, `migrate-callers-then-delete-legacy-apis` and `minimize-reader-load` principles, and Matt Pocock's `improve-codebase-architecture` (the hot-spot scan, the explorer brief and the deletion test). The structure changes and the behaviour does not. A refactor that finds a bug or a missing feature splits it out: ship the structural change first against the pinned behaviour, then send the rest to `ckore-diagnose` or `ckore-design`.

**Profile.** "Repos and readers" lists callers outside this repo, "Risky areas" marks code that gets `ckore-blast-radius` after, and "Test and build" gives the commands.

## 1. Pick the target (only if none was given)

An occasional sweep, not a per-PR step: one explorer run cost ~180k tokens on a mid-size web app (2026-11-02).

Look where change keeps happening: `git log --since=3.months --name-only --format= | sort | uniq -c | sort -rn | head -15`. Give those files to one fresh-context Explore subagent (`model: sonnet`), with no hypothesis of yours and CLAUDE.md's batching line, asking for:

- logic duplicated across modules (two formatters, two copies of one patch builder), which is where copies drift into bugs;
- shallow modules: an interface as complex as its body, wrappers with one caller, one concept spread over many small files;
- the **deletion test** on each: if this module vanished, would complexity disappear or just move to its callers? Only "disappear" is a candidate.

Every candidate comes back with `file:line` evidence for each site and a concrete failure scenario (input → wrong output). Open the cited lines and confirm each one yourself before reporting it; drop what doesn't hold. Show at most 3 verified candidates, one line each with the gain, and ask which one. A candidate that turns out to be a live bug goes to `ckore-diagnose` first; 4 of the 5 PRs the sweep led to across 4 repos were bug fixes (2026-11-02).

## 2. Pin the behaviour

Before any structure moves, have a check that captures what the code does today: existing tests that reach it, or a new characterization test or snapshot written against the current code and run green. Type checks and lint are not a pin. If the area has no seam to test through, say so and stop; a refactor without a pin is a rewrite.

## 3. Name the target shape, smallest first

In ≤5 lines: the module layout, types and call graph as you would build them today, and what gets deleted. The reshape must remove branches, layers or invalid states, not add indirection. Prefer the smallest change that reaches the shape. If the target crosses repos or more than ~10 files, run `ckore-design`'s size gate.

## 4. Subtract, then move in green steps

1. **Delete first:** dead code, one-caller wrappers, redundant validators, unused exports. Commit.
2. **Move in small steps**, running the pin after each.
3. **Replacing an internal API:** migrate every caller and delete the old API in the same PR. No compatibility shims and no parallel old and new paths, unless a caller is in another repo the profile lists. Then ship the new API first and leave a dated removal note.
4. **Renames:** grep for the old name afterwards, including strings, templates, config, docs and the profile's sibling repos. Renames miss usages in strings.

## 5. Prove it, then decide whether to keep it

- Run the pin and the area's full test and build commands, and quote the results.
- Count the reader-load change: files, layers, branches or lines a reader must hold to follow the flow, before and after. If nothing went down, revert the reshape and keep only the deletions.
- If a shared lib, payload or schema moved, run `ckore-blast-radius`. Then `ckore-review`, whose Spec axis checks "no behaviour change".

## Reply (≤200 words)

The structure that changed, the pin it was held against and its quoted result, the reader-load delta, what was deleted, and anything split out as a bug or feature.
