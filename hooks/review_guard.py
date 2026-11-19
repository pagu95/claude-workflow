#!/usr/bin/env python3
"""PreToolUse hook (matcher: Agent): block ad-hoc code-review subagents so reviews go through the
`ckore-review` skill once per PR (L11). One work-repo feature ran four review rounds with improvised
reviewers instead of one `ckore-review` pass.

Blocks (exit 2) an Agent call whose description says review and whose prompt is about a PR, diff
or branch, unless the description starts with the `[review-skill]` marker the skill adds, or with `Hat`
(an overnight-council Hat, from the private overlay, runs `ckore-review` itself).
Anything else, including bad input, exits 0.
"""
import json
import re
import sys

MARKER = "[review-skill]"
REVIEW = re.compile(r"\breview", re.I)
CODE = re.compile(r"\b(PR|pull request|diff|branch)\b|#\d+", re.I)
FIXER = re.compile(r"\b(fix|apply|address)", re.I)  # agents acting on findings, not reviewing


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Agent":
        return 0
    inp = data.get("tool_input") or {}
    desc, prompt = inp.get("description") or "", inp.get("prompt") or ""
    if desc.startswith(MARKER) or desc.startswith("Hat") or FIXER.search(desc) or not REVIEW.search(desc) \
            or not CODE.search(desc + " " + prompt):
        return 0
    print("Blocked an ad-hoc review subagent (L11). Run the `ckore-review` skill once for this PR: it "
          "spawns the two Opus reviewers. If this agent isn't a code review, take 'review' out of "
          "its description.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
