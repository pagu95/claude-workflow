---
name: ckore-retro
description: Measure what Claude Code sessions really cost from their transcripts (main thread and every subagent, priced per call from dated official rates), find the patterns that repeat across sessions, and turn each one into a tracked lesson in LESSONS.md plus the skill edit, CLAUDE.md note or hook it points at. Use for /ckore-retro, "how much did this cost", "why was this so expensive", "make the next session cheaper", or the weekly trend check.
argument-hint: "empty for the trend over recent sessions, or a session id for one session"
---

# Retro

Built on `session-cost-review` (the analyzer and the dated `prices.json`), with Matt Pocock's `retro` and poteto's `reflect` for routing findings to where they change behaviour. Every rule in the global CLAUDE.md came from a measured number. This skill produces the next numbers and keeps track of whether each lesson worked.

The split never changes: **the script counts** (the same transcript always gives the same numbers), **research keeps prices current**, and **you judge** (diagnosis, rework, lessons). Never `cat` a transcript or write an ad-hoc parser instead of the script. Reading transcripts into context is the cost being measured.

```bash
A=~/.claude/skills/ckore-retro/analyze.py
python -I $A --last 10 [--exclude 'regex']   # trend: one line per session + repeating patterns
python -I $A <sessionId>                     # one session in depth (prefix ok); no id = current
python -I $A --list                          # recent sessions
python -I $A --family <id|path> ...          # several sessions as one total, each API call once (forks re-list their parent's calls)
```

Options for one session: `--cutoff <ISO>|none`, `--report <path>` (Markdown, only if the user wants a file), `--prices <file>`, `--main-only` (never quote it as a session total).

## 1. Pick the mode

- **Trend** (the default for `/ckore-retro`): `--last 10`. Use this weekly, or when the user asks "how are we doing". Lessons come from here, because a lesson needs the same pattern in 2+ sessions.
- **One session**: when a session cost more than ~$50, or more than twice the baseline $/call, or a phase felt slow. Run it from a **fresh, small session** (retrospective mode). Running it at the end of a 500k-context session makes every analysis call re-read that context. The script's default cutoff stops it from measuring itself if you do.
- **Skip** sessions under ~$5. They are noise, not lessons.

State which sessions you picked and why. Worktrees have their own project folder, so the newest transcript overall is often from another checkout. A desktop-app session (`local_<id>`) maps to its transcripts through `cliSessionId` plus `priorCliSessionIds` in `~/Library/Application Support/Claude/claude-code-sessions/**/local_<id>.json`. For a session family or sidebar group, pass all of those to `--family`: summing single runs counts a fork's copied history twice.

## 2. Handle failures, never route around them

- **Exit 3, SCHEMA CHECK FAILED:** the transcript format changed and the numbers would be wrong. Don't hand-count. Probe with a small script that prints aggregates only (record types, key sets, counts, never message text), fix `analyze.py`, re-run, and say what changed. The traps already handled: one call split over several lines (dedupe by `requestId`); a partial first record for streamed calls (keep the record with the largest output; subagent files do this on most calls); real numbers in `usage.iterations[]`; subagents in separate files (79% of cost in one session); images in tool results (counted separately, not as text); UTF-8 transcripts on Windows.
- **Exit 2:** nothing to analyse. Pick another session.
- **Prices:** refresh `prices.json` when the header says `STALE` (over 30 days), `no prices file`, or lists `UNPRICED` calls. Fetch https://platform.claude.com/docs/en/about-claude/pricing, grep the saved page for the model table, fast mode, long context and data residency, and update exact model ids, all five rates, `retrieved` and `source`. Never guess or alias a rate. If the lookup fails, give tokens as the hard number and dollars as dated.
- **Warnings** that affect the numbers (an Agent call without a transcript, orphan subagents) go to the user.

## 3. Read the numbers

Lead with the component split. In nearly every long session, cache reads and writes dominate and output is small, so cost tracks how many times the context is re-read, not how much work was produced. Say so plainly; users assume the opposite.

Label correctly: result characters are **measured**; tokens and re-read exposure are **estimates** at ~4 chars per token and are never added to the totals.

Then diagnose. The recurring drivers, in order of size across measured sessions:

1. **Subagents.** Their share, and the costliest ones. Worth it when they keep bulk out of the main context or run on Sonnet; waste when they re-read whole CLAUDE.md files and plans the brief could have excerpted, or run on Opus for mechanical work.
2. **Context growth.** Early vs late $/call. A 2x rise means late work was charged twice. The fix is a handoff at the phase boundary, not the auto-compact.
3. **Cold-cache rewrites.** A cache-write spike after an idle gap over an hour (past the 1h TTL) re-writes the whole prefix at 12–40x the read price.
4. **Serial tool calls.** Near 1.0 tools per call means every step is a separate round trip over the full context.
5. **Bulky results.** Name the specific results and the narrower alternative (a line range, `head`, `--stat`, `grep -l`, a subagent that returns conclusions).
6. **Rework.** The script can't see it. Read your own history for work that was undone (a wrong approach, a reverted commit, a re-run fan-out) and sum those turns. Report it even when the mistake was yours. Give each piece of rework one cause, because the cause picks the fix:
   - Vague ticket or first prompt → WORKFLOW's first-prompt template, or a `ckore-design` question
   - Weak validation (green but wrong) → `ckore-tdd`, or a check through `ckore-correct`
   - A plan word that isn't the code word → `ckore-design`'s name-pairs step; if this keeps showing up, that step isn't working
   - Missing or unclear instructions → the area `CLAUDE.md`, or `ckore-correct` if the rule already exists
   - The architecture hid the right path → a `ckore-refactor` candidate
   - None of these (a wrong guess that was reasonable at the time) → no lesson

Give each lever in dollars and say the estimates overlap rather than add up.

## 4. Turn patterns into lessons

Read `~/.claude/retro/LESSONS.md` first; if it doesn't exist, create it from `LESSONS.template.md` in this skill's folder. The ledger is yours, so it lives outside the repo (`install.sh --overlay` links a private copy there). For each pattern that appears in 2+ sessions:

- **Already a lesson, status `applied`?** Check its metric in this trend. If it moved, mark it `verified` with the new number. If it didn't move after 2 checks, the written fix didn't work: send it to `ckore-correct` (a hook, lint or test) or mark it `retired` with the reason.
- **New?** Add a row with status `proposed` and pick its destination. Ask first whether a script could detect the pattern; prose is only for what needs judgment:

| The cause is | Destination |
|---|---|
| Visible in a tool call (wrong agent, oversized output, missing brief field, time, context size) | A hook in this repo's `hooks/`, built with `ckore-correct` |
| Visible in the project's code (unasserted mocks, unreachable spots, a banned pattern) | A test or lint rule in that project's repo, built with `ckore-correct`, run before commit as well as in CI. In a work repo, propose it per the profile; don't add it |
| A workflow skill step (a brief, a gate, a missing step) | An edit to that skill, ≤5 lines |
| A general habit (output size, idle handoff, model choice) | A dated line in the repo's `CLAUDE.md`, in the same form as the existing ones (behaviour, number, date) |
| A rule that already exists and isn't followed | `ckore-correct`, which enforces it |
| One project's numbers | That project's memory, as its baseline only |

A coded check needs 2+ sessions and no false positives on the current code. Once it is in, delete the prose line it replaces and make the lesson's metric "times the check fired".

Present the proposed rows and edits as one table and **ask before editing anything**. After approval, make the skill, hook and CLAUDE.md edits on a branch of the workflow repo, set each row to `applied` in `~/.claude/retro/LESSONS.md` with the commit, and put the numbers in the commit message. Prefer replacing or tightening an existing line over adding one. A rule cites its id as `(Ln)` and never retells the evidence; the evidence goes in the LESSONS row and the commit. When a lesson is verified, delete its row; when it is retired, or is a fact that stops a failed fix coming back, move it to the one-line "Don't retry" list, and check that list before proposing a fix. Keep Open at 12 rows or fewer: when over, close rows first (the 2-check rule above) before adding any.

CLAUDE.md is read by every session, so every line there has a cost. Each run, report its line count against the last run. Before a row leaves Open, handle every line anywhere that cites its `(Ln)`: in CLAUDE.md, delete the line if the lesson is retired or a hook or test now enforces it; if verified prose is still needed, keep it with a date instead of the id. The count should go down over time, not up.

Save or update the project's **baseline** in memory: total, main vs subagent split, API calls, avg context per call, $/call, tools per call, and the `prices.json` date. Baselines are personal and project-specific; they never go into this repo. Never write a work project's name into `LESSONS.md`; use "work repo" instead.

## Reply (≤300 words)

1. The trend table, or the one-session component split, with the total.
2. Findings, worst first: the number, the cause, the lesson id.
3. Lessons checked: which `applied` ones moved and which didn't.
4. One question: which proposed edits to apply.

Be direct about waste, including your own. An unflattering number the user can act on is worth more than a flattering one.
