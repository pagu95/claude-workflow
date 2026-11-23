# claude-workflow

A set of Claude Code skills, hooks and a global `CLAUDE.md` that I use every day to design, build, review and hand off work. Every rule came from a measured session: what it cost, what went wrong, and the change that fixed it. The flow is in [WORKFLOW.md](WORKFLOW.md).

It works in the Claude Code CLI and the desktop app.

| Skill | Use |
|---|---|
| `ckore-guide` | New here? `/ckore-guide <skill>` gives a short usage card for any skill, or picks one from your situation |
| `ckore-design` | Start of any feature. Question rounds, 2–3 approaches, a short spec and a size gate |
| `ckore-build` | Big features in a fresh session. Opus orchestrator, Sonnet workers |
| `ckore-diagnose` | Bugs and incidents. Pin env and ids, build a red loop, then the smallest fix |
| `ckore-explain` | Read-only answers: how it works, why it's built this way, where a change belongs |
| `ckore-prototype` | Settle a design fork by building a throwaway sketch and observing it |
| `ckore-refactor` | Behaviour-preserving reshapes, pinned by a test before and proven after |
| `ckore-tdd` | Test-first rules used by every implementation path |
| `ckore-review` | One pre-PR review: two agents (Standards, Spec), one pass |
| `ckore-blast-radius` | What a change breaks outside the diff, with the safety fact proven |
| `ckore-handoff` | Phase-boundary check, plus a short handoff file when needed |
| `ckore-resume` | Pick up after a break or a handoff: reconcile the trail with live state, one next action |
| `ckore-correct` | Turns repeated corrections into hooks, tests or lints |
| `ckore-retro` | Measures real session cost (subagents included, dated prices) and counts what went wrong (undone work, review-fix commits, hook blocks, failed tool calls), finds patterns across sessions, tracks lessons in `~/.claude/retro/LESSONS.md` |
| `ckore-unslop` | Short, plain text for PRs, commits and proposals |
| `ckore-context-trim` | Measures what a session loads before any work, sorts it by real usage, trims per repo and asks before account-wide changes |
| `ckore-clean-worktrees` | Frees disk: one script removes provably safe leftover worktrees across all repos, then one table and one question for the rest |

Every skill is named `ckore-<name>`, so none clashes with a Claude Code built-in (Claude Code has its own resume and design commands) or with another plugin's skill.

## Requirements

- Claude Code
- Python 3.9+ for the hooks and the cost scripts
- bash. On Windows use Git Bash, with Developer Mode on so it can make real symlinks
- node, only for `ckore-design`'s browser mockups

No plugins are needed.

## Install

```bash
git clone https://github.com/pagu95/claude-workflow.git
claude-workflow/install.sh
```

The installer:
- links each skill into `~/.claude/skills/`, so a `git pull` updates them. Re-run it after a pull that adds, renames or removes a skill: it also removes the links it left for skills that no longer exist.
- adds `@<clone>/CLAUDE.md` to the top of `~/.claude/CLAUDE.md`. Your own rules stay below that line. It never overwrites the file.
- leaves hooks alone. They are opt-in: see [hooks/README.md](hooks/README.md) for each one and the settings snippet that turns it on.

## First run

1. Copy [profiles/TEMPLATE.md](profiles/TEMPLATE.md) to `~/.claude/profiles/<project>.md` and fill in what applies: environments, prod data access, base branch, commit format, sibling repos, risky areas. The skills read project facts from there, never from their own text.
2. In a project, run `/ckore-guide` to see what each skill is for, or describe the task and let `CLAUDE.md`'s routing pick one.
3. Besides the root `CLAUDE.md`, the skills read one `CLAUDE.md` per domain area, in the folder that holds that area's code. It lists the area's gotchas and its name pairs, each pairing the product's word with the word the code uses. You don't need to write these files up front, because `ckore-design` and `ckore-diagnose` add lines as you work. The area files replace a separate glossary file.

## Your private overlay

Profiles for real projects, your lessons ledger and any skills you don't want to share belong in a private repo of your own, not in a fork of this one:

```
my-overlay/
  profiles/<project>.md
  ledger/LESSONS.md       # your ckore-retro ledger
  skills/ckore-<name>/    # private skills
```

`install.sh --overlay ~/my-overlay` links those too. The ledger is linked to `~/.claude/retro/LESSONS.md`. Without an overlay, `ckore-retro` starts a ledger from `skills/ckore-retro/LESSONS.template.md`.

A real file already in `~/.claude/profiles/` or at `~/.claude/retro/LESSONS.md` is replaced by a link only when it is identical to the overlay's copy. To switch existing files over, copy each one into the overlay, commit there, then re-run the install. Any file that still differs is kept and named in the output, so a newer local edit is never lost.

`install.sh --overlay` also records the overlay path in `~/.claude/claude-workflow-overlay`. If the overlay holds a `leak-denylist.txt` (one regex per line) and optionally a `leak-allowlist.txt` (`<file>:<text>` per line), `tests/test_leak_denylist.py` fails when a denied name appears in this repo. Use it before every push of a fork.

## Numbers and `(Ln)` tags

Costs and counts in the skills, `CLAUDE.md` and the hooks README were measured on my own sessions, with the date they were taken. Treat them as an order of magnitude, not a promise. An `(Ln)` tag cites a lesson in my private ledger; the rule next to it is the part that matters.

## Tests

```bash
python -I -m unittest discover tests   # skill names, installer, project-name parsing, leak check, worktree sweep
python -I -m unittest discover hooks
```

## Credits and licence

Adapted from [poteto's pstack](https://github.com/cursor/plugins/tree/main/pstack), [Matt Pocock's skills](https://github.com/mattpocock/skills) and [superpowers](https://github.com/obra/superpowers); each skill names what it is built on. Their MIT notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

MIT, see [LICENSE](LICENSE).
