#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash|PowerShell): block `gh pr create` unless the PR body has a
`Merge danger:` line, which `ckore-review` writes and `ckore-unslop` puts first in the PR body. The rule was
prose only, and only 1 of 15 work-repo PRs carried the line (2026-11-05).

Looks for the line in the command text (inline --body, heredocs), then in the file named by
--body-file / -F. Blocks with exit 2 if neither has it, so `--fill` with no body is blocked too.
Anything else, including bad input or any error, exits 0.
"""
import json
import os
import re
import sys

CREATE = re.compile(r"(?:^|[;&|(\n])\s*gh\s+pr\s+create\b")  # a command, not a mention
LINE = re.compile(r"merge danger:", re.I)
BODY_FILE = re.compile(r"(?:--body-file|-F)[\s=]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")


def body_file_has_line(command, cwd):
    m = BODY_FILE.search(command)
    if not m:
        return False
    path = next(g for g in m.groups() if g)
    if path == "-":
        return False
    try:
        with open(os.path.join(cwd, path), encoding="utf-8") as f:
            return bool(LINE.search(f.read()))
    except OSError:
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if not CREATE.search(command) or LINE.search(command) \
            or body_file_has_line(command, data.get("cwd") or ""):
        return 0
    print("Blocked `gh pr create`: the PR body has no `Merge danger:` line. Run `ckore-review` and put "
          "its last line first in the body, e.g. `Merge danger: two-way / local / skim`.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
