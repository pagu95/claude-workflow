---
name: ckore-design
description: Turn a ticket, feature idea or UI change into agreed decisions and a short spec before any code. Short numbered question rounds with recommended answers, a scope check, 2–3 approaches, a design of 15 lines or fewer, browser mockups on demand for visual questions, and a size gate that sends big features to a fresh `/ckore-build` session. Use at the start of any feature or behaviour change, backend or UI, or when the user says "design", "grill me" or "brainstorm". Replaces grill and brainstorming. Bugs go to `ckore-diagnose`.
---

# Design

Merges Matt Pocock's `grilling` and superpowers `brainstorming` (its visual companion is vendored in `companion/`). Aim for a shared understanding in as few words and turns as possible, so the user never has to ask "what is the question?".

**Gate:** no code, scaffolding or implementation skill until the user has approved the decisions (step 5). This applies to small changes too, but a small change gets a 3-line design.

## 1. Context and scope (no questions yet)

- Read the CLAUDE.md files for the area. Send code questions to an Explore subagent (`model: sonnet`); before the design rests on its claim that something is the only path, grep for the others yourself (L32). Send prod-data questions to the active profile's prod data access (`~/.claude/profiles/`; ids plus a time window). If the profile's "Project skills" names a knowledge-base or "does this exist?" skill, run it first.
- Finding facts is your job, never the user's. Before asking anything, check whether running something would answer it: a query, a test, or reading the code. If it would, run it and ask nothing. Ask the user only about intent and product choices.
- Unfamiliar area? Run `ckore-explain` first and use its Preserve / Change / Avoid lines as constraints.
- A fork whose answer you could **observe** (which layout fits, whether a state model holds, whether it's fast enough) goes to `ckore-prototype`, not to a question round. Ask only taste and product calls.
- **Scope check:** if the request is several independent pieces (for example, a new API plus a dashboard page plus a cron job), say so in 3 lines or fewer, propose the order, and design only the first piece.
- **Visual?** If later questions will be about layouts, screens or flows the user would understand better by seeing than by reading, offer the visual companion once, in its own short message (see "Visual companion" below).

## 2. Question rounds

Treat the open decisions as a tree. The **frontier** is every decision whose prerequisites are already settled. Each round, ask the frontier, **at most 4 questions**:

```
**Q1 – <title>**: <question, ≤2 lines; options inline if any>
→ <recommended answer, 1 line>
```

- Word each question so that "yes" accepts your recommendation. The user replies "1 yes, 2 no: X, 3 yes".
- Round 1 always covers **expected end state** and **done when**, unless the user already gave them.
- Add nothing between the questions: no preamble, no recap.
- A question that depends on an unanswered one, or on a running lookup, waits for a later round. Ask the rest now.
- The rounds are done only when the frontier is empty and nothing is silently assumed.
- For a visual question with the companion running, put the options in the browser and keep the terminal question to one line ("Which layout, A, B or C? → B").

## 3. Approaches

Once the frontier is mostly settled, show **2–3 approaches**, recommended one first:

```
**A (recommended)** — <1 line>. + <gain>. − <cost>.
**B** — …
```

Always include the **smallest change that meets "done when"** as one of the options. Ask before any approach that adds queues, locks, jobs, tables, collections or new services. Follow existing patterns in the repo. Fix existing problems only where they block this work, with no unrelated refactors.

## 4. Design (≤15 lines)

Present the chosen approach once, not section by section. Cover only what applies:
- **Units**: what each new or changed module does, how it's called and what it depends on. Each unit should end in a checkable state, built as a failing test first with the change on top.
- **Data**: collections, fields, statuses and payloads touched, and who else reads them (flag them for `ckore-blast-radius`)
- **Failure**: errors, retries, idempotency, old documents without the new field
- **Tests**: the seam each behaviour is tested at

For a reversible choice inside the approved scope, decide it yourself, state it in one line and move on. Pause only for irreversible things: prod writes, force-pushes, deploys, messages to customers.

## 5. Approve, write the spec, pick the next step

1. Ask once: "Agreed?" If the user changes anything, update and ask again.
2. Write the agreed design in the `ckore-handoff` format at `~/.claude/handoffs/<TICKET>-<YYYY-MM-DD>.md`. The decisions, rejected approaches, design and "done when" go there. This file is the spec, and it survives compaction. Don't write or commit a spec into the repo unless the user asks.
3. Self-review the file before showing it: no TBDs, no contradictions, no requirement that reads two ways, and small enough for one implementation plan.
4. **Name pairs.** If the design calls something by a word the code doesn't use (e.g. the product says "store", the table is `shops`, the code says "tenant"), add a "done when" item: one line pairing the words in the touched area's `CLAUDE.md`, unless it's already there. If the area (the deepest folder holding the files that use the word) has no `CLAUDE.md`, create one with a `## Gotchas` heading and just that line under it, so `ckore-build` reads it. Don't fall back to the root file. Put the pair where the word is used, not in a glossary. A separate glossary file was rejected because a second definition drifts from the first (2026-11-05).
5. If the work is more than a few hours, write the plan by [PLAN.md](PLAN.md) (read it only then). Then run the size gate.

## 6. Size gate (always the last step)

Count from the plan, or from the design if there's no plan:
- **Tasks**
- **Files touched**
- **Repos touched**

**Big** means any of: **6 or more tasks**, **about 10 or more files**, or **more than one repo**.

- **Small:** say "Small (N tasks, M files). Building here." Then implement inline in this session with `ckore-tdd`, committing per task in the profile's format. If the context is already past ~250k tokens, treat it as big.
- **Big:** don't start building. Reply with exactly this block, then stop:

```
⚠️ Big feature — N tasks, M files, R repos. Build in a NEW session.
Handoff: ~/.claude/handoffs/<file>   Plan: <plan path>
Start it with (Opus):  /ckore-build ~/.claude/handoffs/<file>
```

The handoff file from step 2 must already contain the plan path, the pinned env and ids, and the base branch.

## Visual companion

A local browser page for mockups, layout comparisons and diagrams, where the user clicks the option they want. The scripts live in this skill's `companion/` folder. Offer it once, in its own short message: "Some of this is easier to show than describe. I can open mockups in a local browser page. It costs more tokens. Want it?" Only if the user says yes, read [companion/GUIDE.md](companion/GUIDE.md) and follow it. Use the browser only for genuinely visual questions, and stop the server at step 5.
