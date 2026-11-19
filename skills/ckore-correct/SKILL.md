---
name: ckore-correct
description: Turn mistakes the user keeps correcting into something that enforces itself (a hook, test, lint or code structure) instead of another line in memory or CLAUDE.md, and prune rules that do nothing. Use for /ckore-correct, or when the user corrects the same kind of mistake a second time.
disable-model-invocation: true
---

# Correct

Built on poteto's `correct`, with Matt Pocock's `retro`, `writing-for-agents` and `git-guardrails`. Feedback memories and CLAUDE.md rules can be skipped without anything failing. This skill moves the important ones to a place where skipping them does fail, and deletes the rest.

**Profile.** The active profile's "Guardrails" section lists the known candidates for this project.

## 1. Find the repeat classes

Read, in this order, and keep output small:

- The feedback entries in the project's `memory/MEMORY.md` and the files it points to
- The rules in `~/.claude/CLAUDE.md`, the repo's CLAUDE.md files and the profile's "Guardrails"
- The repo's existing check commands (lint, test and CI scripts, git hooks) and `~/.claude/settings.json` hooks. A check that exists but isn't wired up is the finding; don't build a new one.
- Recent corrections in session transcripts: user messages with "no", "wrong", "I said", "not what", "why did you". Send this sweep to a subagent that returns only grouped classes with one quote each.

A class counts once it has happened **twice**. Mark each class as one of two kinds:

- **Mechanical:** a fixed pattern, a banned call, the wrong env or id, a wrong git command. These get enforcement and no prose rule.
- **Judgement:** these stay as written rules.

## 2. Fix each class at the highest level that works

1. **Architecture**: one supported way of doing it. For example, a single helper that resolves the environment and DB, so code can't pick the wrong one.
2. **Claude Code hook**: a PreToolUse hook that exits 2 with a message naming the right action. A generic starting set, adapted from Matt's `git-guardrails`:
   - a push to the base branch
   - `reset --hard`, `clean -f`, `branch -D`, `checkout .` and `restore .`

   Add the profile's "Guardrails" items to it. Match these inside `&&` chains and `sh -c` too, not only at the start of the command.
3. **Lint, type or CI check**: the error message names the file or function to use instead.
4. **Test**: it fails when the behaviour breaks, and not when only the internals change.
5. **Docs or memory**: last, and only for judgement calls.

## 3. Prune

In the same sweep, delete:

- **No-op rules**, ones the model already follows by default. To test one, remove the line and see whether the behaviour changes.
- **Duplicates**, so that each meaning has one source.

For rules that stay, state the target behaviour ("write X") rather than the ban, because a negation pulls the banned thing into context. Keep a prohibition only as a hard guardrail, paired with its positive target.

## 4. Prove it, then ask

For each enforcement, show it **failing on the real past mistake**. Present one table and ask before editing any repo, hook or settings file:

| Class | Kind | Evidence (quote, session) | Level | Enforcer | Proof it fails |
|---|---|---|---|---|---|

When the user approves, apply one change per class and **delete the memory or CLAUDE.md line it replaces**, so the context shrinks.
