#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash|PowerShell): two spend checks that apply only inside a subagent
(the event carries `agent_id`). The main thread always passes.

1. Wait cap (L29). A subagent's prompt cache lives 5 minutes. A foreground shell call that runs
   longer than that makes the next call re-write the agent's whole context instead of reading it
   (12x the price). The model can't see that; the `timeout` it asks for can be checked. A
   foreground call with a timeout over WAIT_MS is blocked, and the message says to wait in
   shorter steps.
2. Call cap (L23). An agent that isn't converging keeps going: one made 220 calls for a result
   that still failed. The hook counts shell calls per agent. Call number NUDGE is blocked once
   with a message to report back if the work isn't nearly done; from STOP on, every shell call is
   blocked and the agent is told to return its report.

Blocks with exit 2 and a message on stderr. Bad input or any error exits 0.
"""
import datetime
import json
import os
import re
import sys
import time

WAIT_MS = 270_000        # 4.5 minutes: under the 5-minute cache lifetime, with room for the call itself
NUDGE = 60               # shell calls; 40 of 44 agents in the measured night stayed under this
STOP = 120               # shell calls; only the non-converging agent passed this
STATE = os.environ.get("CLAUDE_SUBAGENT_GUARD_STATE") or os.path.join(
    os.path.expanduser("~"), ".claude", "subagent-guard")
KEEP_DAYS = 7

WAIT_MSG = (
    "Blocked: a foreground call with a timeout of {mins:.0f} min inside a subagent. Your prompt cache "
    "lasts 5 minutes; a longer wait makes the next call re-write your whole context instead of "
    "reading it (12x the price). Use a timeout of 270000 ms or less. For work that runs longer, "
    "start it with run_in_background and wait in steps of at most 4 minutes (the same wait loop "
    "with a shorter deadline), repeating until it is done (L29).")
NUDGE_MSG = (
    "Checkpoint: this is shell call {n} in this agent. If the task is nearly done, repeat the call "
    "and finish. If it is not converging, stop now and return a report to whoever started you: "
    "what works, what doesn't, what you tried, and what you would try next. A fresh agent with a "
    "narrower brief is cheaper than continuing here (L23).")
STOP_MSG = (
    "Blocked: this agent has made {n} shell calls, over the cap of {cap}. Do not run more commands. "
    "Return your report now: what works, what doesn't, what you tried, the branch and its state, "
    "and what you would try next (L23).")


def clean(value):
    return re.sub(r"[^A-Za-z0-9-]", "", value or "") or "unknown"


def bump(session, agent):
    """Add one to this agent's shell-call count and return the new count."""
    os.makedirs(STATE, exist_ok=True)
    path = os.path.join(STATE, f"{session}.{agent}.count")
    try:
        with open(path, encoding="utf-8") as f:
            count = int(f.read().strip() or 0)
    except (OSError, ValueError):
        count = 0
    count += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(count))
    return count


def log_fired(session, agent, kind, value):
    """One line per block, so retro can count how often each check fired."""
    try:
        with open(os.path.join(STATE, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.datetime.now(datetime.timezone.utc).isoformat()[:19],
                                "session": session, "agent": agent, "kind": kind,
                                "value": value}) + "\n")
        cutoff = time.time() - KEEP_DAYS * 86400
        for name in os.listdir(STATE):
            path = os.path.join(STATE, name)
            if name.endswith(".count") and os.path.getmtime(path) < cutoff:
                os.remove(path)
    except OSError:
        pass


def block(session, agent, kind, value, message):
    log_fired(session, agent, kind, value)
    print(message, file=sys.stderr)
    return 2


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if event.get("tool_name") not in ("Bash", "PowerShell") or not event.get("agent_id"):
        return 0
    session, agent = clean(event.get("session_id")), clean(event.get("agent_id"))
    tool_input = event.get("tool_input") or {}

    count = bump(session, agent)
    if count > STOP:
        return block(session, agent, "stop", count, STOP_MSG.format(n=count, cap=STOP))

    timeout = tool_input.get("timeout")
    if isinstance(timeout, (int, float)) and timeout > WAIT_MS \
            and not tool_input.get("run_in_background"):
        return block(session, agent, "wait", int(timeout),
                     WAIT_MSG.format(mins=timeout / 60000))

    if count == NUDGE:
        return block(session, agent, "nudge", count, NUDGE_MSG.format(n=count))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)       # a guard must never break a tool call
