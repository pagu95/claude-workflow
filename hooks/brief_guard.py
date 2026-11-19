#!/usr/bin/env python3
"""PreToolUse hook (matcher: Agent): block overnight-council role agents whose brief doesn't tell them
to skip CLAUDE.md (L18). The council's rules (in the private overlay) already required the line, yet
none of 76 agents in one overnight run carried it, and Hats and Gloves read CLAUDE.md files 23 times.

Blocks (exit 2) an Agent call whose description starts with Lead, Hat, Glove, Scout, Tester, Hand or Leg
when the prompt lacks "Don't re-read CLAUDE.md".

Also blocks (L30) a general-purpose Agent call (or one with no subagent_type) that sets no `model`:
it silently inherits the main thread's Opus, which ran mechanical checklists and replays at about
twice the Sonnet price. Typed agents (Explore, prod-investigator) carry their own model and pass.
Anything else, including bad input, exits 0.
"""
import json
import re
import sys

ROLE = re.compile(r"^(Lead|Hat|Glove|Scout|Tester|Hand|Leg)\b")
LINE = re.compile(r"don['’]t re-read claude\.md", re.I)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Agent":
        return 0
    inp = data.get("tool_input") or {}
    desc, prompt = inp.get("description") or "", inp.get("prompt") or ""
    if inp.get("subagent_type") in (None, "", "general-purpose") and not inp.get("model"):
        print("Blocked a general-purpose agent with no `model`: it would inherit Opus (L30). Set "
              "model: \"sonnet\" for lookups, checklists, replays and mechanical edits, or "
              "model: \"opus\" when the agent must judge (review, design, diagnosis).",
              file=sys.stderr)
        return 2
    if not ROLE.match(desc) or LINE.search(prompt):
        return 0
    print("Blocked an overnight-council brief without the \"skip CLAUDE.md\" line (L18). Paste the area gotchas "
          "(<=30 lines) and add the sentence \"Don't re-read CLAUDE.md.\" to the brief.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
