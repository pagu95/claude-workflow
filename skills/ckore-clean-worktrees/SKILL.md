---
name: ckore-clean-worktrees
description: Free disk by removing leftover git worktrees (night-batch `wf_*`, subagent `agent-*`, finished session worktrees) across every repo in the projects folder. One script inventories all repos and removes what is provably safe; the session then shows one table of the rest and asks one question. Use for /ckore-clean-worktrees, "clean up worktrees", "the disk is full", "free some space", or when a batch or a worktree creation failed for lack of disk.
argument-hint: "empty for the folder that holds the current repo, or a path to another projects folder"
---

# Clean worktrees

One session, one script, one question. On 2026-11-22 the same job took a parent session and eight per-project sessions, with five of them waiting for an answer and three hand-written commands failing on the space in the home folder's name. The script replaces all of that: **the script decides and removes, you only show its table and pass the answer back.**

```bash
S=~/.claude/skills/ckore-clean-worktrees/sweep.py
python "$S" [ROOT] --apply          # remove the safe tier, print what needs a call
python "$S" [ROOT] --remove P...    # approved rows, the plain way
python "$S" [ROOT] --force P...     # approved rows that hold uncommitted files
python "$S" [ROOT]                  # dry run, removes nothing
```

`ROOT` is the folder that holds the repos. Left out, it is the parent of the repo you are in.

## 1. Run it

Run `--apply` in the background (a few dozen removals take minutes). Don't inventory by hand first, don't start a session or subagent per project, and don't run `du`.

What it removes without asking:
- a detached, clean worktree whose commit is on some branch
- a clean worktree on a branch whose tip is the head of a merged PR (the branch itself stays)
- an empty leftover folder under `.claude/worktrees`
- a loose file directly in `.claude/worktrees` that is older than 7 days

Ignored files (`node_modules`, build output, a local `.env` copy) go with a removed worktree. That is where the space is, and git does not count them as changes.

What it never does: delete a branch, push, commit, force, or touch a worktree whose git state or changed files moved in the last 2 hours (another session may be working there).

## 2. Show the result and ask once

Give the user, in this order:
1. Free space before and after, and how many it removed per repo.
2. Anything under `failed`, with the reason. "Busy" on Windows means a program still holds the folder: say a reboot releases it, and that the next run will pick it up.
3. The "Needs your call" table as printed, all repos together.

Then ask one question: which rows to remove. Recommend from the `suggested` column: rows that say `remove` go, rows that say `keep` stay. If the table is empty, ask nothing and stop at the report.

## 3. Remove what was approved

Use the full paths printed under the table, quoted.

- The table's last column says which flag removes each row. Pass approved `--remove` rows and approved `--force` rows in one command.
- `--force` rows lose their uncommitted files or the folder's contents. Name what will be lost in your one question, so the answer covers it, and force only the rows the user named.
- A row marked `unlock first`, or anything changed in the last 2 hours, is refused by the script. Report that; don't work around it.

Finish with free space now, what is still there and why. Don't offer to delete branches.

## When the script is wrong

If it errors or puts something in the wrong tier, fix `sweep.py` and its tests (`tests/test_sweep.py` in the workflow repo, `python -I -m unittest discover tests`) instead of running `git worktree remove` or `rm -rf` by hand. A repo where `gh` cannot answer puts all its named branches in the table; that is the safe side, not a bug.

Worktrees the desktop app made for sessions idle 30 days or more can also be cleared from the app's Settings › Storage. That is separate from this skill and does not cover `wf_*` or `agent-*` folders.
