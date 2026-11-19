#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): per-repo git rules that were prose in a profile's "Guardrails".

Config: `~/.claude/guards.json` (machine-local, never in this repo), or the path in CLAUDE_GUARDS_CONFIG:
  {"git": [{"repos": ["~/code/api", "~/code/insta*"],          # globs; subfolders and worktrees included
            "protected_branches": ["staging"],
            "commit_needs_no_verify": true}]}                  # husky repos whose pre-commit runs `git add -A`

Blocks (exit 2), in a matching repo (the cwd, or `git -C <path>`):
- `git push` whose destination is a protected branch, or a bare `git push` while on one
- `git commit` while on a protected branch
- `git commit` without `--no-verify` / `-n` when commit_needs_no_verify is set
Only `git` as a command counts (shell_segments.py, quote-aware), so a mention inside a commit message
passes. No config, no matching repo, any other tool, bad input or any error: exit 0.
"""
import fnmatch
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir
from shell_segments import segments  # noqa: E402


def load_rules():
    path = os.path.expanduser(os.environ.get("CLAUDE_GUARDS_CONFIG", "~/.claude/guards.json"))
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("git") or []
    except (OSError, ValueError):
        return []


def rule_for(repo, rules):
    real = os.path.realpath(repo)
    for rule in rules:
        for pat in rule.get("repos") or []:
            pat = os.path.realpath(os.path.expanduser(pat))
            if fnmatch.fnmatch(real, pat) or fnmatch.fnmatch(real, pat + "/*"):
                return rule
    return None


def current_branch(repo):
    out = subprocess.run(["git", "-C", repo, "symbolic-ref", "--short", "-q", "HEAD"],
                         capture_output=True, text=True, timeout=5)
    return out.stdout.strip()


def parse(tokens, cwd):
    """-> (repo, subcommand, args) for a token list starting with git."""
    tokens, repo = tokens[1:], cwd
    while tokens and tokens[0].startswith("-"):
        opt = tokens.pop(0)
        if opt in ("-C", "-c") and tokens:
            val = tokens.pop(0)
            if opt == "-C":
                repo = os.path.join(repo, os.path.expanduser(val))
    if not tokens:
        return repo, "", []
    return repo, tokens[0], tokens[1:]


def push_dests(args):
    positional = [a for a in args if not a.startswith("-")]
    dests = []
    for spec in positional[1:]:
        dest = spec.split(":")[-1].lstrip("+")
        dests.append(dest[len("refs/heads/"):] if dest.startswith("refs/heads/") else dest)
    return dests


def check(tokens, cwd, rules):
    if os.path.basename(tokens[0]) != "git":
        return None
    repo, sub, args = parse(tokens, cwd)
    if sub not in ("push", "commit"):
        return None
    rule = rule_for(repo, rules)
    if not rule:
        return None
    protected = set(rule.get("protected_branches") or [])
    if sub == "push":
        dests = push_dests(args)
        if not dests and "--all" not in args and "--mirror" not in args:
            dests = [current_branch(repo)]
        hit = sorted(protected.intersection(dests))
        if hit:
            return f"Blocked `git push` to protected branch {hit[0]}. Push a feature branch and open a PR."
        return None
    branch = current_branch(repo)
    if branch in protected:
        return f"Blocked `git commit` on protected branch {branch}. Create a feature branch first."
    if rule.get("commit_needs_no_verify") and "--no-verify" not in args and "-n" not in args:
        return ("Blocked `git commit` without --no-verify: this repo's pre-commit hook runs `git add -A` "
                "and sweeps unrelated files into the commit. Lint the touched area yourself, then commit "
                "with --no-verify.")
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    rules = load_rules()
    if not rules:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()
    for tokens in segments(command):
        reason = check(tokens, cwd, rules)
        if reason:
            print(reason, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
