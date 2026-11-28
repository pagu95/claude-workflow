# Quality pass

Read this only when the quality pass runs (`/ckore-retro quality`, or `/ckore-retro` with no pass named). The cost pass finds what was expensive. This one finds what went wrong, including in sessions too cheap for the cost pass to look at.

```bash
Q=~/.claude/skills/ckore-retro/quality.py
python -I $Q --last 10 [--exclude 'regex']   # one line per session, the signals that repeat, review smells
python -I $Q <sessionId>                     # one session (prefix ok); no id = current
python -I $Q --family <id|path> ...          # several sessions as one total, each tool call once
```

The script prints counts, project names, tool names and hook positions. It never prints prompt, command or result text, and neither do you: the rule against reading transcripts holds here too.

## What each count is

| Count | What is counted | What it is not |
|---|---|---|
| undone | `git revert`, `git reset --hard`, and `git checkout -- <path>`, `git checkout .` or `git restore <path>` that throw edits away | A file taken from another ref (`git checkout main -- x`), an unstage, a command only echoed, grepped for or written to a file, a discard in a subagent that never commits (a reviewer cleaning up a scratch check) |
| review-fix | A commit whose message says it answers a review ("Review fixes", "address review"), or a fixup/squash commit | Every commit after a review: a fix with an ordinary message is missed |
| hook blocks | Tool calls a PreToolUse hook refused, grouped as `<tool> hook <n>` | The idle hold on a prompt, which is not a tool call (`~/.claude/context-guard/runs.jsonl` has it) |
| denied | Tool calls the user or the permission system refused | An operating-system "Permission denied", which is a failed call |
| interrupted | Times the user stopped a turn | Stopping at a tool prompt, which is already one denial |
| failed calls | Every other tool call that returned an error, out of all tool calls | A failing test run, which is what a red test looks like. A probe that exits non-zero (`grep` with no match) is counted, so read the share and the tool, not the raw number |
| red-first, weakened, smells | Defined in SKILL.md §3 | |

`hook <n>` is the hook's position among the PreToolUse hooks in `~/.claude/settings.json`, counted from 1 in file order. That mapping was checked on one machine (2026-11-23: 3 was `pr_body_guard`, 4 was `subagent_guard`), so read your settings before naming a hook.

## From counts to traps

1. **A count says where to look, not why.** Two sessions with undone work are a candidate. They are a trap only if the cause is the same. Find the cause in what the session left behind: the branch's commits, the PR and its review comments, the hook's own log. For the session you are in, use your own history.
2. **Give each one cause**, from the rework list in SKILL.md §3.6. The cause picks the destination in §4. No shared cause, no trap. A trap is about how we work: flow, prompts, briefs, review and test gates. A quirk of one project's code gets no row; it goes to that project's area `CLAUDE.md` or a test.
3. **A hook that blocks often** is either working (the rule is missing from the brief or skill that keeps triggering it: fix that text) or noisy (it blocks correct work: fix the hook). Say which.
4. **One session, severe** (a wrong fix merged, a bug that passed review): no row yet. Add a watch line to the trend log and give it a row on the second sighting.
5. **One-session mode only: user corrections.** The script can't count these. List the turns where the user redirected the work (a "no", a restated request, an interruption), give each one cause as in step 2, and report them even when the mistake was yours.

Traps go in the ledger's Traps table by the rules in SKILL.md §4. Add the quality counts to the project's baseline in memory.
