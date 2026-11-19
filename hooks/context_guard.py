#!/usr/bin/env python3
"""UserPromptSubmit hook: warn before a prompt re-caches a huge idle context (L7) or keeps
growing one past the handoff point (L8). The model can't see either; the transcript can.

- Idle: more than IDLE_MIN since the last reply and context over IDLE_CTX. The cache TTL is
  1h, so this prompt re-writes the whole context at the cache-write price. The first prompt
  after such a gap is held once (L28: six warnings in one work-repo feature were all read past); sending it
  again goes through, so continuing stays one keystroke away.
- Size: context crossed SIZE_CTX (then every SIZE_STEP more). Warns once per step.

Always exits 0. Prints nothing when there is nothing to say.
"""
import datetime
import json
import os
import re
import sys

IDLE_MIN = 60
IDLE_CTX = 200_000
SIZE_CTX = 250_000
SIZE_STEP = 150_000
WRITE_PER_MTOK = 8.0      # Opus 5.5, 1h cache write (ckore-retro/prices.json, 2026-11-17)
STATE = os.environ.get("CLAUDE_CONTEXT_GUARD_STATE") or os.path.join(
    os.path.expanduser("~"), ".claude", "context-guard")


def last_reply(path):
    """(timestamp, context tokens) of the newest assistant record with usage."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - 400_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"assistant"' not in line or '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        u = (d.get("message") or {}).get("usage") or {}
        its = u.get("iterations") or [u]
        ctx = sum((i.get(k) or 0) for i in its for k in
                  ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        when = d.get("timestamp")
        if ctx and when:
            return datetime.datetime.fromisoformat(when.replace("Z", "+00:00")), ctx
    return None, 0


def warned_step(session):
    try:
        with open(os.path.join(STATE, session), encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def remember_step(session, step):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, session), "w", encoding="utf-8") as f:
            f.write(str(step))
    except OSError:
        pass


def idle_seen(session, when):
    """True the second time an idle prompt arrives for the same last reply (the resend)."""
    mark = os.path.join(STATE, session + ".idle")
    try:
        with open(mark, encoding="utf-8") as f:
            if f.read().strip() == when.isoformat():
                return True
    except OSError:
        pass
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(mark, "w", encoding="utf-8") as f:
            f.write(when.isoformat())
    except OSError:
        return True       # can't remember the block, so never block
    return False


def log_run(session, ctx, idle, fired):
    """One line per run, so 'did it run' and 'how often it warned' are countable (L27)."""
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.datetime.now(datetime.timezone.utc).isoformat()[:19],
                                "session": session, "ctx": ctx, "idle_min": round(idle),
                                "fired": fired}) + "\n")
    except OSError:
        pass


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    path = event.get("transcript_path") or ""
    session = re.sub(r"[^A-Za-z0-9-]", "", event.get("session_id") or "unknown")
    if not os.path.isfile(path):
        return
    when, ctx = last_reply(path)
    if not when:
        return
    idle = (datetime.datetime.now(datetime.timezone.utc) - when).total_seconds() / 60
    msg = fired = None
    block = False
    if idle > IDLE_MIN and ctx > IDLE_CTX:
        cost = ctx / 1e6 * WRITE_PER_MTOK
        block = not idle_seen(session, when)
        fired = "idle-block" if block else "idle"
        msg = (f"Idle {idle / 60:.1f}h with a {ctx // 1000}k-token context: the cache has expired, so "
               f"this prompt re-writes it (~${cost:.2f}). Cheaper: /ckore-handoff, then /ckore-resume in a new "
               f"session (starts near 100k). Measured: idle rewrites were ~12% of spend (L7).")
        if block:
            msg += " Held once (L28): send the prompt again to continue here anyway."
    elif ctx > SIZE_CTX:
        step = 1 + (ctx - SIZE_CTX) // SIZE_STEP
        if step > warned_step(session):
            remember_step(session, step)
            fired = "size"
            msg = (f"Context is {ctx // 1000}k tokens; every call re-reads all of it. At a phase "
                   f"boundary, /ckore-handoff and continue in a new session (L8).")
    log_run(session, ctx, idle, fired)
    if block:
        print(json.dumps({"decision": "block", "reason": msg}))
    elif msg:
        print(json.dumps({"systemMessage": msg,
                          "hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": msg}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass          # a guard must never break the prompt
    sys.exit(0)
