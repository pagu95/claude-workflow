---
name: ckore-guide
description: 'Explain one of this repo''s workflow skills to someone who hasn''t read it: what it does, when to use it and when not, how to start it, what it will ask you, what you get at the end, and what comes next. Picks the right skill first when you describe a situation instead of naming one. Read-only. Use for /ckore-guide, "which skill should I use", "how does design work", "how do I use build", or a new teammate''s first look at the repo. Questions about application code go to `ckore-explain`.'
argument-hint: "a skill name, a situation (\"I have a bug in prod\"), or empty for the menu"
---

# Guide

For people who share this repo and want to use a skill without reading all of it. The answer is a short usage card built from the skill's current `SKILL.md`, so it never drifts from the real text. Never change files and never start the skill being explained; the user starts it once they understand it.

## 0. Find the repo

`/ckore-guide` runs from any repo, so don't use paths relative to the working directory. The installer symlinks each skill folder into `~/.claude/skills/`; the repo root is two levels above this skill's real path: `dirname "$(dirname "$(readlink -f ~/.claude/skills/ckore-guide)")"`. Call it `<repo>`. If it doesn't resolve (a copied install, not a symlink), use `~/.claude/skills/` for the skills and skip `WORKFLOW.md`.

## 1. Pick the skill

- **A skill name** (`ckore-design`, `/ckore-build`, "the night one"): use it. Fuzzy names map to the closest skill; say which one you picked.
- **A situation** ("prod is throwing", "I'm back after a weekend", "this PR is huge"): match it against the "Which skill when" table in `<repo>/WORKFLOW.md` and the frontmatter descriptions in `<repo>/skills/*/SKILL.md`. Name the one skill that fits and, in one line, why it beats the runner-up. If two fit in sequence (`ckore-design` then `ckore-build`), say so and explain the first.
- **Empty**: list every `ckore-*` folder in `~/.claude/skills/` that has a `SKILL.md` (this repo's skills plus any private overlay's), one line each from its description, grouped as *Start of work* (ckore-resume, ckore-explain, ckore-design, ckore-diagnose, ckore-refactor, ckore-prototype), *Building* (ckore-tdd, ckore-build), *Before the PR* (ckore-blast-radius, ckore-review, ckore-unslop), *Session hygiene* (ckore-handoff, ckore-correct, ckore-retro, ckore-context-trim), *Overnight* (ckore-nightwatch, ckore-night-jam, when a private overlay installed them) and *Other* for any skill not named here (this one, and skills added later). Then ask which one to explain, with `AskUserQuestion` offering the 4 most common (ckore-design, ckore-diagnose, ckore-review, ckore-resume).

A folder without a `SKILL.md` (shared rules such as a `CORE.md`) is shared material, not a skill: explain it only as part of the skills that read it.

## 2. Read the skill

Read `~/.claude/skills/<name>/SKILL.md` in full; skills run 35–120 lines. Also read any file it says to follow (a shared `CORE.md` it points to, `ckore-design/PLAN.md` when the question is about plans). Don't open scripts (`analyze.py`, `audit.py`) unless the user asks how they work. Grep `<repo>/WORKFLOW.md` for the skill's name to see where it sits in the flow.

Note from the frontmatter: `argument-hint` (what to pass) and `disable-model-invocation: true` (Claude never starts it by itself; the user must type `/<name>`).

## 3. The card (≤300 words, drop sections that don't apply)

```
## /<name>: <one-line purpose in plain words>

**Use it when:** 2–3 concrete situations.
**Don't use it for:** the nearest wrong case, and which skill to use instead.

**Start it:** `/<name> <argument>`, plus one realistic example prompt.
Auto-starts: yes (Claude picks it from what you say) / no (type the command).

**What happens:** 3–6 numbered steps as the user experiences them, not the
skill's internal rules. Mark the moments where it stops and waits for you.

**What it asks you:** the questions or approvals to expect, and the reply shape
it wants (e.g. "1 yes, 2 no: X").

**What you get:** the end product (spec, handoff file, PR, cited answer, LESSONS entry)
and where it lands on disk.

**Next:** the skill that usually follows, from the WORKFLOW.md flow.

**Gotchas:** 1–3 things that surprise first-time users (cost, needs a fresh
session, needs a profile, never touches X).
```

- Write for someone who knows Claude Code but not this repo. Explain repo terms (profile, size gate, handoff file, council) the first time they appear, in a few words.
- Keep the skill's measured numbers only when they change what the user does ("start /ckore-build in a new session; inline is ~$35 vs ~$89").
- If the skill needs a profile (`~/.claude/profiles/<name>.md`) and none matches the current repo, say so under Gotchas.

## 4. After the card

Offer one follow-up in a single line: explain the next skill in the flow, or start this one. Start it only if the user says yes. A skill with `disable-model-invocation: true` can't be started by Claude, and `ckore-build` needs a fresh session; for those, give the exact `/<name> <argument>` line to type instead.
