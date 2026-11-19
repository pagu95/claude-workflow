# Profiles

Project-specific facts (environments, prod data access, base branch, commit format, sibling repos, risky
areas, repo skills) live in `~/.claude/profiles/<name>.md`, not in skills. Before running a workflow skill,
pick the profile whose "Applies to" matches the current repo's path or git remote. If none matches, use the
project's CLAUDE.md and ask for anything missing. Never copy a work profile into this repo.

# Skill routing

The workflow skills in this repo replace the superpowers plugin; don't load superpowers skills even if the
plugin is still installed. Route by task: a feature or behaviour change → `ckore-design`; a bug → `ckore-diagnose`; a
read-only question → `ckore-explain`; "how do I use skill X" or "which skill" → `ckore-guide`; a behaviour-preserving change → `ckore-refactor`; picking up earlier work →
`ckore-resume`. Implementation follows `ckore-tdd`. For pre-PR review use `ckore-review` once, not code-review +
security-review. The flow: `ckore-design` → (size gate) → inline with `ckore-tdd`, or `/ckore-build` in a new Opus session →
`ckore-blast-radius` if shared data → `ckore-review` → the profile's finish step.

# Claude Code configuration

For a simple settings change (a permission rule, an env var), edit the settings file directly; load
`update-config` only for hooks or keys you don't know (it adds ~89K tokens; 2026-10-08, L1).

# Tool output size

Fetch tickets and docs once and work from notes; send bulk exploration whose raw output isn't needed later
to a subagent that returns conclusions. Context size is the lever that works: hand off at ~250k (2026-11-05).

# Child sessions

When you start sessions and one has an open PR and has been idle over an hour, send its follow-ups
(conflicts, review fixes, side questions) to a fresh session or a Sonnet subagent in its worktree with a
short brief, not back to the child: four resumed 200–350k children cost ~$18 of one $113 feature (2026-11-03,
L10). Once a child's PR merges, offer to archive it; wake-up turns after days idle cost ~$1–1.5 each (L12).
