---
name: ckore-handoff
description: Decide what to do at a phase boundary (continue, /clear, handoff, subagent or /compact), and when a handoff is right, compress the session into a short handoff file so the next phase starts fresh. Use for /ckore-handoff, when the user says "we're done with that", at the end of design or a long investigation, or once the session has compacted.
argument-hint: "What will the next session do?"
disable-model-invocation: true
---

# Handoff

Built on Matt Pocock's `handoff` and the phase-boundary tree in his `ask-matt`, with pstack's `show-me-your-work` and context-window principles. Long sessions compact several times, and every later call re-reads all of it.

## 1. Phase-boundary check (first yes wins)

1. **Continue here** if the next phase needs this one's reasoning as its main source (`ckore-design` → `ckore-build` usually does) **and** the context is under ~250k tokens.
2. **/clear** if nothing from this session is needed later.
3. **Handoff file** if the work moves to another repo, worktree or person, if a side task forks off mid-phase, or if the context is past ~250k tokens. Every session starts near 100k of fixed context, so 250k is about 150k of real work.
4. **Subagent** if the next piece can run unattended and only its conclusion matters, such as `ckore-review` or a prod lookup.
5. **/compact** with an explicit instruction about what to keep, as a last resort. Never compact mid-phase.

Tell the user which one applies in one line. Write the file only for case 3, or when the user asks.

## 2. The file

Write `~/.claude/handoffs/<TICKET-or-topic>-<YYYY-MM-DD>.md`, **≤60 lines**:

```
# <ticket> — <one-line goal>
Next session: <one phase, one concern — from the argument>
Repo / worktree / branch: <absolute path, branch, base>
Profile: <name of the active profile, or none>
Environment + ids pinned: <env, DB, ids with their kind — verified? y/n>
Expected end state / done when: <verbatim from the user>
Decisions (settled): <≤8 bullets, each ending with its evidence: commit, file:line or query>
Rejected (and why): <≤4 bullets — so they aren't re-proposed>
Verified: <command run → result quoted>
Not verified / open: <…>
Next step: <the first concrete action>
Artifacts: <plan/spec paths, PR URLs, commits — link, don't copy>
Suggested skills: <e.g. ckore-build, ckore-tdd, ckore-blast-radius, ckore-review>
```

Rules:
- **One phase, one concern.** If "Next step" touches more than about 8 files or two concerns, write two handoffs.
- **Verified means run.** Only "Verified" may hold claims backed by a command, and each one quotes the result. Everything else goes under "Not verified".
- **Append corrections.** When something changes later, add a line that supersedes the old one instead of rewriting history.
- **Link, don't copy.** Point to plans, PRs and diffs instead of pasting them. Redact tokens and customer PII.
- **End your reply** with the one-line prompt for the next session: `/ckore-resume ~/.claude/handoffs/<file>` (or `/ckore-build <file>` when the size gate said big). `ckore-resume` re-checks the file against live state before continuing.
