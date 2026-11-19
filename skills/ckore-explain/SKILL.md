---
name: ckore-explain
description: 'Read-only answers about code: how X works, why it was built this way, where a change should live, or what a library or API really does. Returns a cited answer, never a code change. Use for "how does X work", "why is it like this", "where should this live", "are we sure", "teach me X", "research X", or a walkthrough before changing unfamiliar code. Changes go to `ckore-design` or `ckore-diagnose` afterwards. How to use one of the workflow skills goes to `ckore-guide`.'
argument-hint: "the question"
---

# Explain

Built on poteto's `how`, `why`, `teach` and Investigation playbook, and Matt Pocock's `research`. Answer at the level of a senior engineer onboarding onto the area: enough for a working mental model, not annotated source. The output is an answer with evidence. If the question turns into "so let's change it", stop and hand over to `ckore-design` or `ckore-diagnose`.

**Profile.** Read the active profile in `~/.claude/profiles/`. "Repos and readers" says where the code continues outside this repo, and "Project skills" may name a knowledge-base skill to check first.

## 1. Size the question

State your reading of the question in one line, then pick the path. When in doubt, take the simple one.

- **Simple** (one module, one function, one narrow question): answer it yourself. Grep for the symbol first, then read by line range.
- **Wide** (a subsystem across many files, repos or services): split it into 2 or 3 angles and send each to an **Explore subagent** (`model: sonnet`), all in one message. Each returns findings with `file:line`, ≤200 words, no file dumps. Add to every brief: "Issue independent reads/greps together in one message; serialise only when a call needs the previous result."

## 2. "Why" questions: read the history

The motivation lives in history, not in the code. Build the anchor inline:

- `git log --oneline -15 -- <file>` and `git blame -L <start>,<end> <file>` for the lines in question
- `git log -1 --format=%B <commit>` for PR numbers, then `gh pr view <n> --json title,body,comments,reviews`
- the knowledge-base skill from the profile, and ADRs or docs the repo keeps

Beware recency bias: the newest commit is often a small edit on top of an older decision. Trace back to the commit that introduced the shape.

## 3. External facts (libraries, APIs, platform limits)

Go to primary sources: official docs, the library's source in `node_modules`, the spec. Not blog posts. If the reading is long, run it in a background subagent and have it write a notes file with a source for each claim to `~/.claude/handoffs/notes-<topic>-<YYYY-MM-DD>.md`, so later sessions reuse it instead of fetching again.

## 4. Label every claim

In the same sentence, mark each claim **measured** (you ran something), **read** (`file:line` or a PR link), **inferred**, or **guess**. Never hand the user a check you could run. Never cite a link or PR you didn't open in this session.

## Reply (≤300 words, drop sections that don't apply)

- **Answer:** the direct answer in 1 or 2 sentences.
- **How it works:** the runtime flow as a short call chain or a 5-node diagram.
- **Where things live:** the 3 to 6 files that matter, one line each.
- **Why:** the decision and its evidence, plus competing explanations if the evidence is thin.
- **Gotchas:** what will surprise the next person who changes it.
- **If you change it:** Preserve / Change / Avoid, one line each. Include this only when the question comes before a change. It feeds `ckore-design` step 1.

For an "are we sure?" question, give your real judgment. Say so plainly when the premise is wrong.
