---
name: ckore-review
description: The one pre-PR review for a branch, covering Standards (repo rules, smells, security and data safety) and Spec (does it do what the ticket asked, and nothing more), in exactly two parallel subagents, plus how to act on review findings. Use when the user asks to review a branch, the diff or a PR, before opening a PR, or when responding to review comments. Replaces code-review, security-review and requesting-code-review run back to back.
---

# Review

Built on Matt Pocock's two-axis `code-review`, with parts of superpowers `requesting-code-review`, `receiving-code-review` and `verification-before-completion`, the built-in `security-review` and pstack's principles. It has a fixed budget: **two subagents, one pass, a short report.** Don't spawn more agents, and don't re-run the review unless code changed since the last one.

**Profile.** Read the active profile in `~/.claude/profiles/`. Its sections "Branches and commits" and "Data store risks" fill in the specifics below. If no profile matches, use the project's CLAUDE.md.

## 1. Pin the diff

- Base: the profile's base branch, or else `git symbolic-ref refs/remotes/origin/HEAD`. Never assume `main`. If the user named a different base, use it.
- Before spawning anything, confirm the base resolves (`git rev-parse <base>`) and that `git diff --stat <base>...HEAD` isn't empty.

## 2. Gather the inputs (no agents yet)

- **Spec**: the ticket text or the agreed decisions from this conversation, the handoff file, or the ticket id in the branch or commits. If there's none, the Spec axis reports "no spec".
- **Standards**: the root `CLAUDE.md` and every area `CLAUDE.md` on a path the diff touches, including their gotchas sections, plus the profile's "Data store risks".

## 3. Two subagents in parallel (one message, model: opus)

Opus, because this is the last check before merge; one Opus pass per PR cost ~$1–1.20 (2026-11-03, L11). Start both descriptions with `[review-skill]` so `hooks/review_guard.py` lets them through. Fixes that come out of the review are mechanical: apply them inline or with a Sonnet agent. An overnight-council Hat (private overlay skills) that wrote or holds the spec does the Spec pass itself and spawns only the Standards agent (L21).

Add this to both prompts:

> Issue independent reads/greps/git commands together in one message; serialise only when a call needs the previous result. Under 300 words. Findings only, no praise, no summary of the diff. Report only findings you are over 80% sure are real; skip theoretical races, hardening ideas and style. Give each finding `file:line` and the exact scenario that breaks.

**Standards agent.** Give it the diff command, the list of standards files, and this checklist. Repo rules always win over the heuristics.

- **Repo rules** (`repo-rule`). Any breach of a documented repo rule, with the file and the rule quoted (hard).
- **Security and data safety** (`security`, hard if real):
  - Injection: user-controlled input reaching queries or filters, in the forms the profile lists.
  - Missing auth, ownership or admin checks.
  - Secrets or PII in logs or in client code.
  - State writes without the expected status guard.
  - Unbounded queries or missing indexes, flagged only on hot tables or collections.
  - Non-idempotent job or webhook handlers, flagged only where the handler really retries.
  - Everything else listed in the profile's "Data store risks".
- **Tests** (`tautological-test`). Tautological tests, where the expected value is computed the same way the code computes it.
- **Smells.** Always label these "possible X", never as hard violations:
  - duplicated logic (`duplicated-logic`)
  - speculative generality, plus validators, guards or parsers beyond what the spec needs (`speculative-generality`)
  - validation repeated deep inside the code when it belongs at the API or job boundary (`deep-validation`)
  - wrappers with one caller, and pass-through layers that repeat the same arguments (`pass-through`)
  - the same status if-cascade at several sites (`status-cascade`)
  - the same fields always travelling together (`data-clump`)
  - mysterious names (`mysterious-name`)
  - shotgun surgery (`shotgun-surgery`)
  - raw strings standing in for ids and statuses (`raw-string-id`)
  - comments that narrate what the code does, or claim a constraint ("do not change") with no test or type behind it; keep only a non-obvious why (from poteto's `no-comments`) (`narrating-comment`)

**Spec agent.** Give it the diff command and the spec. It reports:
- missing or partial requirements
- behaviour that wasn't asked for (scope creep, which flags larger-than-needed fixes)
- requirements implemented wrongly

It quotes the spec line for each. It also flags, in a separate line, any place the spec itself looks wrong or misses a case.

## 4. Verify, then report in chat (≤250 words total)

A subagent's report is a claim. Open each `file:line` it cites and confirm it before it goes into your report. Drop any finding you can't confirm.

```
## Standards — N findings (worst: …)
- [hard] file:line — rule — scenario — fix
- [judgement] possible <smell> — file:line
## Spec — N findings (worst: …)
- …
Merge danger: <two-way|one-way> / <local|shared: readers> / <skim|read it all>
```

Then log each confirmed Standards finding for `ckore-retro --smells`: append one line per finding to `~/.claude/retro/smells.jsonl` (create the folder if needed), `{"date": "<YYYY-MM-DD>", "repo": "<repo folder name>", "branch": "<branch>", "smell": "<id from the checklist>", "kind": "hard|judgement"}`. The file is machine-local; never copy it into a repo. Skip the log when re-reviewing the same unchanged diff.

Keep the two axes separate and don't rerank across them. Leave out empty sections and anything a linter already enforces. Don't post the review on the PR.

**Merge danger** is the last line of every report, decided by you, not a subagent. Take the door and readers from `ckore-blast-radius` if it ran. Otherwise read them off the diff: a migration, a deleted field, a message sent, or a status the old code can't read is one-way. Write "read it all" for one-way or shared, otherwise "skim". The line goes first in the PR body, and `hooks/pr_body_guard.py` blocks `gh pr create` without it.

## 5. Acting on findings (ours or a human reviewer's)

- **Clear up first.** If any finding is unclear, ask about it before fixing any of them.
- **Check real usage.** Before building something a finding asks for, grep for how the code is actually used. If nothing calls it, the answer is "remove it" or "skip", not "build it properly".
- **Push back with evidence** when a finding is wrong.
- **Fix one at a time:** blocking first, simple next, complex last. Test after each one.
- **Keep replies short.** No "You're right!" and no thanks; state the fix in one line. On GitHub, reply inside the comment thread, not as a new top-level comment.
