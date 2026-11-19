---
name: ckore-context-trim
description: Cut what a Claude Code session loads before any work in a repo (plugins, skill listings, connector tool names, SessionStart hooks, CLAUDE.md) by measuring the startup size from transcripts, sorting each item into needed / ad-hoc / never from real usage, trimming what the repo controls and asking before anything account-wide. Use for "trim startup context", "why does a session start at 100k", "what loads that we don't need", or when a repo's first call is over ~60k tokens.
argument-hint: "empty for the current repo, or a repo path"
---

# Context trim

Every token loaded at startup is re-read on every later call, so the startup size is a tax on the whole session. This skill measures it, proves which parts are used, trims per repo, and leaves account-wide switches to the user. First run, 2026-11-02: one web app went from 106k to 90k on connector toggles alone, before its own trim.

**The script counts, you judge.** Never `cat` a transcript; it costs what you are trying to save.

```bash
A="$HOME/.claude/skills/ckore-context-trim/audit.py"
python -I "$A" startup [repo] --n 5   # first-call size, attachment split, the floor the repo can't touch
python -I "$A" usage [repo]           # real tool_use calls per skill/agent/MCP family: here vs elsewhere
```

## 1. Measure

Run `startup` on the repo. `start` is the first call's input (the true size); `attachments` are the parts you can trace; `floor` is the app prompt and full tool schemas (~55k on 2026-11-02), which nothing here changes. Compare the newest session with older ones: a drop you didn't make is usually an account-wide toggle made from another repo.

| attachment | what it is | lever |
|---|---|---|
| `deferred_tools_delta` | names of every connector tool (one connector can be 150+) | connector toggle, **account-wide** |
| `skill_listing` | every skill of every enabled plugin, plus desktop-app and account skills | `enabledPlugins` per repo; desktop plugins in the app |
| `hook_success` | SessionStart hook output (e.g. the Vercel plugin's knowledge update) | disable the plugin that owns the hook |
| `mcp_instructions_delta` | per-connector instructions | connector toggle |
| `instructions` | CLAUDE.md files + memory index | edit CLAUDE.md (step 4) |
| `prompt_snapshot`, `agent_listing_delta` | the app's own | none |

## 2. Inventory and sort

List what loads, with its source: `~/.claude/settings.json` and `.claude/settings.json` (`enabledPlugins`, hooks), `~/.claude/plugins/installed_plugins.json`, `.mcp.json`, and `mcp__ccd_connectors__session_connectors_status` (connectors, plugin MCP servers, `needs_auth` and `failed` ones). Skills and connectors seen in your own context but in none of those files come from the desktop app or the claude.ai account.

Run `usage` and put each item in one bucket:

- **Needed**: called in this repo recently. Keep.
- **Ad-hoc**: called here, but rarely, or only for one kind of task (a DB connector, a deploy connector). Off at startup; switch on per session from the composer's + → Connectors, or say so in the repo's CLAUDE.md.
- **Never**: zero calls here, or only in other repos. Off for this repo.
- Also **broken**: a plugin MCP that is `failed` or has been `needs_auth` for weeks loads its noise and gives nothing. Treat it as never.

A skill family with 0 calls in every repo is the strongest signal. One with calls only in other repos is per-repo off, never account-wide off.

## 3. Trim

1. **Plugins, per repo, safe.** In `.claude/settings.json` set `"<plugin>@<marketplace>": false` under `enabledPlugins`. This overrides a global enable. The file is committed, so it applies to teammates too; say so in the PR.
2. **Connectors, ACCOUNT-WIDE, ask first.** `set_session_connector_enabled` changes this session AND the default for every new session in every repo. Show the user the `usage` row (which repos use it) and get a yes per connector. Never re-enable one another repo turned off.
3. **Desktop-app plugins and account skills** (e.g. `ckore-design`, `cowork-plugin-management`, anthropic-skills) can't be changed from here. Tell the user where: the desktop app's plugin settings, or claude.ai.
4. **CLAUDE.md, needs the user's eyes.** Look at it whatever the `instructions` size (a game repo's was 13k, a web app's 3k):
   - History and status sections → move verbatim to a history doc, leave a 1–2 line pointer.
   - Long gotchas → move verbatim to `docs/gotchas.md` (or the repo's equivalent), keep one line per rule plus its key symbol, grouped by area. Never drop a rule.
   - Leave commands, architecture, protocol and conventions unless clearly bloated.
   - Link the new doc from the repo's docs index if there is one.
   - Prove the move: `git show main:CLAUDE.md | sed -n 'A,Bp'` against the new file with `diff --strip-trailing-cr` (Windows CRLF makes plain `diff` flag every line).

## 4. Record and ship

- Write down why each item was turned off, with the usage numbers, where the repo keeps lessons (a platform card, a CLAUDE.md line). A `false` in settings with no reason gets flipped back.
- Branch, commit in the repo's format, PR, and the repo's review rule. Account-wide changes go in the PR body too, since they aren't in the diff.

## 5. Done when

The PR is merged, and the user has the before figure, what changed (per repo / account-wide / left for them), and the expected after. The after can't be measured in the session that made the changes: open a fresh session, say "hi", then run `startup --n 1` from another. Until then call the saving an estimate.

## Traps

- A connector toggle takes effect when the current turn ends.
- `enabledPlugins` entries for plugins that aren't installed do nothing for you but do for a teammate who has them; leave them unless the user asks.
- Worktrees have their own transcript folders (`<repo>--claude-worktrees-*`); both modes count them as this repo, a hand-rolled grep won't.
- The deferred tool list appears in every transcript, so grepping for a tool name counts sessions that loaded it, not ones that used it. Count `tool_use` blocks only (the script does).
- `cat > file` with no heredoc waits on stdin and hangs the Bash tool.
- Doing several sibling repos from one session: no-commit-to-main guard hooks resolve the branch from a leading literal `cd "<worktree>" &&`, not from a variable or `git -C "$W"`, so commit with one Bash call per repo.
