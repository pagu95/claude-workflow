---
name: ckore-resume
description: Pick up work after a break, a crashed or compacted session, or another session's handoff. Rebuilds where things stand from the handoff files, worktrees, branches and PRs, checks the inherited claims against live state, and returns a short brief with the one next action. Use for /ckore-resume, "where did I leave off", "catch me up", "pick up X", or the first prompt of a session that starts from a handoff file. The counterpart of `ckore-handoff`.
argument-hint: "handoff file, branch, ticket or topic (optional)"
disable-model-invocation: true
---

# Resume

Built on poteto's `session-pickup` playbook and `recall`, with the catch-up rules of his `ketchup`. `ckore-handoff` writes the trail and this skill reads it. The trail is authoritative input: resume from it, and don't redo work it marks as verified.

**Profile.** Read the active profile in `~/.claude/profiles/`. "Branches and commits" gives the base branch, "Environments and ids" and "Prod data access" say how to re-check pinned ids.

## 1. Find the trail (one message, all reads together)

- **Handoff files:** `ls -t ~/.claude/handoffs/ | head`. If the argument names one, use it. Otherwise pick the files whose ticket, topic or repo matches, newest first.
- **Git state** for each repo and worktree the handoffs name, or the current one: `git worktree list`, `git status -sb`, `git log --oneline <base>..HEAD`, and `git stash list`.
- **PRs:** `gh pr list --author @me --state open --json number,title,headRefName,isDraft,reviewDecision,statusCheckRollup` and, for each branch, merged PRs since the handoff date.
- **No handoff file?** Read the newest session transcript for this folder (`~/.claude/projects/<folder slug>/*.jsonl`, newest by mtime) in a **Sonnet subagent**. It returns only: the goal, decisions, last verified result, open threads and corrections. The raw transcript stays in the subagent.

Lock the scope before reading more. Default to the topic in the argument, or else the last 7 days of this repo. State the scope in one line. Never read another project's transcripts unless the user asks.

## 2. Reconcile the trail with live state

For each claim in the handoff's "Verified", "Decisions" and "Next step":

- **Still true?** A branch that moved, a PR that merged or was closed, a base branch with new commits that touch the same files. Run `git log --oneline HEAD..<base> -- <files>` to check.
- **Stale facts.** Pinned env and ids older than the break get re-checked once through the profile's prod data access. A cheap re-run of the last red/green command is fine. A full re-investigation is not.
- **Uncommitted work** in a worktree is either the resume point or junk. Say which, and don't delete it.

Put every mismatch under "Changed since the handoff" and append a superseding line to the handoff file (the `ckore-handoff` rule: append, don't rewrite).

## 3. Route

Name the resume point and send the remaining work to the matching skill: `ckore-build` with the handoff for a big plan, `ckore-diagnose` from its phase for a bug, `ckore-design` from the open question, `ckore-review` if the code is done, or the profile's finish step if only the PR is left. This skill ends there.

## Reply (≤200 words)

- **Capsule:** at most 3 bullets on what the work is and where it stands.
- **Threads:** one line each, with exactly one tag: `[merged #N]`, `[open PR #N]`, `[in flight <branch>]`, `[uncommitted]`, `[planned]`, or `[stale]`.
- **Changed since the handoff:** what moved while you were away, or "nothing".
- **Waiting on you:** the calls only the user can make, each with your pick.
- **Next move:** the one concrete action, and the skill that owns it.
