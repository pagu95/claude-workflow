# Hooks

Enforcement for lessons that prose rules can't carry, because the model can't see the fact they depend on. `install.sh` does **not** wire these up; add them to `~/.claude/settings.json` yourself.

## `context_guard.py` (lessons L7, L8, L27, L28)

A `UserPromptSubmit` hook. Before your prompt goes out, it reads the transcript tail and warns, in the terminal and to the model:

- **Idle:** more than 60 minutes since the last reply and a context over 200k. The 1h cache has expired, so the prompt re-writes the whole context (it prints the cost). The cheaper path is `/ckore-handoff`, then `/ckore-resume` in a new session. The first such prompt is held (L28): the prompt doesn't go out and the reason is shown. Sending it again for the same idle reply goes through with the warning.
- **Size:** the context crossed 250k, then every 150k more. It warns once per step.

Apart from that one hold it never blocks, prints nothing when there's nothing to say, and exits 0 on any error. Thresholds are constants at the top of the file.

Every run appends one line to `~/.claude/context-guard/runs.jsonl` (`session`, `ctx`, `idle_min`, `fired`: `idle-block`, `idle`, `size` or null), so `ckore-retro` can count whether it ran and how often it warned (L27). Tests: `python -I hooks/test_context_guard.py`.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
                     "command": "python -I \"<repo>/hooks/context_guard.py\"" } ] }
    ]
  }
}
```

Replace `<repo>` with the absolute path of this clone.

Tested 2026-11-01 on real transcripts: idle 1.6h at 274k warned with ~$2.20; a 377k active session warned once, then stayed quiet at the same step; a 145k idle session, a missing transcript and bad input stayed silent.

## `subagent_guard.py` (lessons L29, L23)

A `PreToolUse` hook on `Bash|PowerShell` with two checks that apply only inside a subagent (the event carries `agent_id`); the main thread always passes.

- **Wait cap (L29).** A subagent's prompt cache lives 5 minutes. A foreground call with a `timeout` over 270,000 ms is blocked, and the message says to wait in steps of at most 4 minutes. Background calls pass.
- **Call cap (L23).** It counts shell calls per agent. Call 60 is blocked once with a checkpoint message (finish, or report back if the work isn't converging); from call 121 on every shell call is blocked and the agent is told to return its report.

Each block appends one line to `~/.claude/subagent-guard/runs.jsonl` (`session`, `agent`, `kind`: `wait`/`nudge`/`stop`), which is the count `ckore-retro` reads. Counts live beside it and are deleted after 7 days. Tests: `python -I hooks/test_subagent_guard.py`.

Replayed 2026-11-15 on an overnight run (44 agents): 15 foreground waits of ~10 minutes re-wrote 3.05M tokens (~$10 of $58.89), all of which the wait cap blocks; 3 agents reach the checkpoint and 1 (220 calls, $12.68, result still failing) reaches the stop. On three other sessions that day (17 agents) the call cap never fires and the wait cap fires 4 times. Not yet run live: that a block reaches a subagent the way it reaches the main thread is documented, not observed.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|PowerShell",
        "hooks": [ { "type": "command",
                     "command": "python -I \"<repo>/hooks/subagent_guard.py\"" } ] }
    ]
  }
}
```

## `review_guard.py` (lesson L11)

A `PreToolUse` hook on `Agent`. It blocks a subagent whose description says "review" and whose brief is about a PR, diff or branch, unless the description starts with `[review-skill]`, the marker the `ckore-review` skill adds. The model gets a message telling it to run `ckore-review` instead. Agents that fix, apply or address findings pass, and so do any other agents and bad input.

Tested 2026-11-03 with the work repo's real agent descriptions: "Review PR … stats job" and "Independent reviewer for #…" were blocked; `[review-skill] …`, "Fix S5 review findings", "Review the design doc", a non-Agent tool and invalid JSON passed.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Agent",
        "hooks": [ { "type": "command",
                     "command": "python -I \"<repo>/hooks/review_guard.py\"" } ] }
    ]
  }
}
```

## `pr_body_guard.py`

A `PreToolUse` hook on `Bash|PowerShell`. It blocks `gh pr create` unless the PR body has `ckore-review`'s `Merge danger:` line. It looks in the command text (inline `--body`, heredocs) and in the file named by `--body-file` / `-F`. `--fill` with no body is blocked on purpose, and `gh pr edit` isn't checked. It matches `gh pr create` only as a command (at the start, or after `;`, `&&`, `|`, `(` or a newline), so a mention inside a commit message passes. Every other command, any other tool and bad input pass. The line was prose-only in `ckore-unslop` before, and only 1 of 15 work-repo PRs carried it (2026-11-05).

Tests: `python -I hooks/test_pr_body_guard.py`.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|PowerShell",
        "hooks": [ { "type": "command",
                     "command": "python -I \"<repo>/hooks/pr_body_guard.py\"" } ] }
    ]
  }
}
```

## `brief_guard.py` (lessons L18, L30)

A `PreToolUse` hook on `Agent`. It blocks a general-purpose agent (or one with no `subagent_type`) that sets no `model`, since it would inherit the main thread's Opus (L30); typed agents such as Explore and prod-investigator pass. Replayed 2026-11-17 over 30 days of transcripts: 106 calls in 16 sessions would have been held for a model choice, none of them `ckore-review` agents (those already set one). It also blocks an agent whose description starts with an overnight-council role (Hat, Glove, Scout, Tester, Hand, Leg) unless its brief contains "Don't re-read CLAUDE.md" (straight or curly apostrophe), the line the council's core rules require (the overnight skills aren't in this release). Any other tool and bad input pass. On a 2026-11-05 overnight run, none of 76 briefs carried the line and subagents read CLAUDE.md files 32 times; 45 of those agents would have been blocked.

Tests: `python -I hooks/test_brief_guard.py`.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Agent",
        "hooks": [ { "type": "command",
                     "command": "python -I \"<repo>/hooks/brief_guard.py\"" } ] }
    ]
  }
}
```

## `git_guard.py` (profile guardrails)

A `PreToolUse` hook on `Bash` for git rules a profile lists under "Guardrails". It reads a machine-local `~/.claude/guards.json` (override with `CLAUDE_GUARDS_CONFIG`) and does nothing without it, so repo names and paths never land in this repo. It splits the command with `shell_segments.py`, which knows about quotes, so a mention inside a commit message or a grep pattern passes.

Per repo glob (subfolders and worktrees included), it blocks `git push` to a protected branch (including `HEAD:<branch>` and a bare push while on it), `git commit` on a protected branch, and, with `commit_needs_no_verify`, `git commit` without `--no-verify` (for husky hooks that run `git add -A`). `shell_segments.py` is shared, so other machine-local guards in a private overlay can import it.

```json
{
  "git": [{ "repos": ["~/code/api", "~/code/shop*"], "protected_branches": ["staging", "main"],
            "commit_needs_no_verify": true }]
}
```

Replayed against 21,801 Bash commands from a work repo's transcripts (2026-11-09): it fired 43 times on commits without `--no-verify` in the husky repo and 6 times on pushes to a protected fork branch, with no false positives once the splitter knew about quotes.

Tests: `python -I hooks/test_git_guard.py`.

```json
{ "matcher": "Bash",
  "hooks": [ { "type": "command", "command": "python -I \"<repo>/hooks/git_guard.py\"" } ] }
```
