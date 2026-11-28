#!/usr/bin/env python3
"""Count the quality signals in Claude Code transcripts: what was undone, what review sent back,
what a hook or the user stopped, and which tool calls failed. The cost side is analyze.py.

Usage:
  python3 quality.py                    # current session ($CLAUDE_CODE_SESSION_ID), else newest
  python3 quality.py <sessionId>        # a specific session (prefix match ok), or a transcript path
  python3 quality.py --last N [--exclude REGEX]
                                        # one line per session, the signals that repeat, review smells
  python3 quality.py --family ID ...    # several sessions as one total, each tool call once

Counts only. No prompt, command or result text is printed: project names, tool names and the
hook's position in the settings file ("hook 4") are the only strings taken from a transcript.

Exit codes: 0 ok, 2 not found / bad args, 3 SCHEMA CHECK FAILED (see analyze.py).
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402

HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2\b", re.S)
QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"|(?<!\w)'[^']*'")   # the apostrophe in "don't" opens nothing
SEPARATOR = re.compile(r"&&|\|\||;|\|")
GIT = analyze.CMD_START + r"git\s+(?:-C\s+\S+\s+)?"
UNDONE = re.compile(GIT + r"(?:revert\b(?!\s+--(?:abort|quit|continue))"   # a commit taken back
                          r"|reset\b[^;&|\n]*--hard\b"                      # commits or edits thrown away
                          r"|checkout\s+(?:HEAD\s+)?(?:--\s+\S|\.(?:\s|$))"  # edits thrown away (no other ref)
                          r"|restore\b(?![^;&|\n]*--staged)\s+\S)")
COMMIT = re.compile(GIT + r"commit\b")
DISCARD = re.compile(r"\b(?:checkout|restore)\b")
FIX_MESSAGE = re.compile(r"--fixup\b|--squash\b|fixup!|\breview[ -]fix|\baddress(?:es|ed|ing)?\s+(?:the\s+)?review"
                         r"|\breview\s+(?:comments|feedback|findings)\b", re.I)
HOOK_BLOCK = re.compile(r"\s*(?:Error:\s*)?\w+:(\w+) hook error: \[([^\]]*)\]")
HOOK_POSITION = re.compile(r"hook \d+$")
# The permission system's own wording, at the start of the result: an OS "Permission denied" is a failed call.
DENIED = re.compile(r"\s*(?:Error:\s*)?Permission for this .{0,40}denied by\b")
USER_REFUSED = re.compile(r"doesn't want to proceed|tool use was rejected")
INTERRUPTED = "[Request interrupted by user"
AT_A_TOOL_PROMPT = INTERRUPTED + " for tool use"   # logged next to the refused call, which already counts as denied
MANY_BLOCKS = 3          # the same hook blocking this often in one session is a pattern, not a slip
FAILED_SHARE = 0.10


def strip_text(cmd):
    """The command with heredoc bodies and quoted strings blanked out, at the same length, so a
    `git revert` that is only written into a file, echoed or searched for is not read as one that ran."""
    return QUOTED.sub(lambda m: "Q" * len(m.group(0)), HEREDOC.sub(lambda m: " " * len(m.group(0)), cmd))


def is_fix_commit(cmd):
    """A commit whose message says it answers a review, or a fixup/squash commit. Only the commit's
    own segment is read, so review words in a later `gh pr comment` do not count."""
    masked = strip_text(cmd)
    commit = COMMIT.search(masked)
    if not commit:
        return False
    end = SEPARATOR.search(masked, commit.end())
    return bool(FIX_MESSAGE.search(cmd[commit.start():end.start() if end else None][:400]))


def tool_name(name):
    return name.split("__")[-1] if name.startswith("mcp__") else name


def scan(path, c, seen, subagent=False):
    """Add one transcript file's signals to `c`. `seen` holds the tool-use, result and record ids
    already counted: a streamed call is logged more than once, and a fork re-lists its parent.
    In a subagent that never commits (a reviewer), a discarded edit is a scratch check it cleaned
    up, such as a fix taken out to watch its test fail, so it is not undone work."""
    uses = {}                    # tool_use id -> (name, command)
    discards, committed = 0, False
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        content = (d.get("message") or {}).get("content")
        blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
        if d.get("type") == "assistant":
            for b in blocks:
                if b.get("type") != "tool_use":
                    continue
                name, cmd = b.get("name") or "?", str((b.get("input") or {}).get("command") or "")
                uses[b.get("id")] = (name, cmd)
                if ("use", b.get("id")) in seen:
                    continue
                seen.add(("use", b.get("id")))
                c["tool_calls"] += 1
                if name in analyze.SHELL_TOOLS:
                    plain = strip_text(cmd)
                    for m in UNDONE.finditer(plain):
                        if DISCARD.search(m.group(0)):
                            discards += 1
                        else:
                            c["undone"] += 1
                    committed = committed or bool(COMMIT.search(plain))
                    c["fix_commits"] += is_fix_commit(cmd)
        elif d.get("type") == "user":
            text = content if isinstance(content, str) else " ".join(
                b.get("text") or "" for b in blocks if b.get("type") == "text")
            key = ("record", d.get("uuid"))
            if INTERRUPTED in text and AT_A_TOOL_PROMPT not in text and key not in seen:
                c["interrupted"] += 1
                if d.get("uuid"):
                    seen.add(key)
            for b in blocks:
                rid = ("result", b.get("tool_use_id"))
                if b.get("type") != "tool_result" or not b.get("is_error") or rid in seen:
                    continue
                seen.add(rid)
                name, cmd = uses.get(b.get("tool_use_id"), ("?", ""))
                out = analyze.result_text(b.get("content"))
                hook = HOOK_BLOCK.match(out)
                if hook:
                    position = HOOK_POSITION.search(hook.group(2))
                    c["hook_blocks"][f"{hook.group(1)} {position.group(0) if position else 'hook ?'}"] += 1
                elif DENIED.match(out) or USER_REFUSED.search(out[:300]):
                    c["denied"] += 1
                elif not analyze.TEST_CMD.search(cmd):      # a red test run is the job, not a failure
                    c["failed"][tool_name(name)] += 1
    if committed or not subagent:
        c["undone"] += discards


def session_counts(path, seen=None):
    """The signals of one session, main thread and subagents. None when it has no assistant calls;
    dict(fatal=[...]) when the transcript no longer matches what analyze.py expects."""
    stats = analyze.new_stats()
    threads = analyze.load_session(path, None, False, stats)
    if not stats["assistant_lines"]:
        return None
    fatal, _ = analyze.schema_check(threads, stats, path)
    if fatal:
        return dict(path=path, fatal=fatal)
    c = dict(undone=0, fix_commits=0, hook_blocks=collections.Counter(), denied=0, interrupted=0,
             failed=collections.Counter(), tool_calls=0)
    seen = set() if seen is None else seen
    scan(path, c, seen)
    for p in analyze.subagent_files(path):
        scan(p, c, seen, subagent=True)
    tdd = analyze.tdd_metrics(threads)
    project = analyze.short_project(os.path.basename(os.path.dirname(path))).replace("--claude-worktrees-", "/")
    return dict(c, path=path, project=project[:42], when=analyze.last_activity(path),
                red_first=tdd["red_first"], source_files=tdd["source_files"], weakened=tdd["weakened"])


# ---------------------------------------------------------------- output

def n_failed(r):
    return sum(r["failed"].values())


def n_blocks(r):
    return sum(r["hook_blocks"].values())


RULES = [   # (signal, test, where the lesson usually goes)
    ("undone work", lambda r: r["undone"] > 0, "rework: give it one cause (SKILL §3.6)"),
    ("review-fix commits", lambda r: r["fix_commits"] > 0, "what review caught late: ckore-tdd, ckore-design"),
    (f"one hook blocked {MANY_BLOCKS}+ times", lambda r: max(r["hook_blocks"].values(), default=0) >= MANY_BLOCKS,
     "the rule is missing from the brief or skill, or the hook is noisy"),
    ("denied or interrupted", lambda r: r["denied"] + r["interrupted"] > 0,
     "permission rules, or an approach the user stopped"),
    (f"failed tool calls > {FAILED_SHARE:.0%}",
     lambda r: bool(r["tool_calls"]) and n_failed(r) / r["tool_calls"] > FAILED_SHARE,
     "environment notes (shell, paths), the brief"),
] + [rule for rule in analyze.TREND_RULES if rule[0].startswith(("red-first", "tests weakened"))]

HEAD = "undone | review-fix | hook blocks | denied | interrupted | failed calls | red-first | weakened |"


def cells(r):
    return (f"{r['undone']} | {r['fix_commits']} | {n_blocks(r)} | {r['denied']} | {r['interrupted']} "
            f"| {n_failed(r)}/{r['tool_calls']} | {analyze.red_cell(r)} | {r['weakened']} |")


def breakdown(rows):
    for label, key in (("hook blocks by hook", "hook_blocks"), ("failed calls by tool", "failed")):
        total = sum((r[key] for r in rows), collections.Counter())
        if total:
            print(f"- {label}: " + ", ".join(f"{k}: {v}" for k, v in total.most_common(8)))


def trend(n, exclude):
    cur = os.environ.get("CLAUDE_CODE_SESSION_ID") or "\0"
    cands = [t for t in analyze.main_transcripts()
             if not os.path.basename(t).startswith(cur) and not (exclude and re.search(exclude, t, re.I))]
    oldest = analyze.ts("0001-01-01T00:00:00Z")
    cands.sort(key=lambda t: analyze.last_activity(t) or oldest, reverse=True)
    rows = []
    for t in cands:
        if len(rows) >= n:
            break
        r = session_counts(t)
        if r:
            rows.append(r)
    print(f"# Quality trend: last {len(rows)} sessions")
    print()
    print("- excluded: the current session" + (f", paths matching /{exclude}/" if exclude else ""))
    print()
    print("| last active | project | " + HEAD)
    print("|---|---|" + "---:|" * 8)
    ok = [r for r in rows if "fatal" not in r]
    for r in rows:
        if "fatal" in r:
            print(f"| | {os.path.basename(r['path'])} | SCHEMA CHECK FAILED, run it alone |" + " |" * 7)
            continue
        when = r["when"].strftime("%Y-%m-%d") if r["when"] else "?"
        print(f"| {when} | {r['project']} | {cells(r)}")
    print()
    print("## Signals (a trap needs the same signal in 2+ sessions)")
    print()
    print("| signal | sessions | usually points at |")
    print("|---|---:|---|")
    for label, test, hint in RULES:
        print(f"| {label} | {sum(1 for r in ok if test(r))}/{len(ok)} | {hint} |")
    print()
    breakdown(ok)
    print()
    analyze.smells(30)


def family(ids):
    """Several sessions as one total, oldest first. A fork re-lists its parent's calls, so each
    tool call counts once; red-first and weakened are per transcript and are not summed."""
    paths = list(dict.fromkeys(analyze.resolve(i) for i in ids))
    paths.sort(key=analyze.first_call)
    seen = set()
    rows = [r for r in (session_counts(p, seen) for p in paths) if r]
    print(f"# Quality, family: {len(rows)} transcripts, each tool call counted once")
    print()
    print("| transcript | project | " + HEAD)
    print("|---|---|" + "---:|" * 8)
    ok = [r for r in rows if "fatal" not in r]
    for r in rows:
        name = os.path.basename(r["path"])[:8]
        if "fatal" in r:
            print(f"| {name} | SCHEMA CHECK FAILED, run it alone |" + " |" * 8)
            continue
        print(f"| {name} | {r['project']} | {cells(r)}")
    print(f"| **total** | | {sum(r['undone'] for r in ok)} | {sum(r['fix_commits'] for r in ok)} "
          f"| {sum(map(n_blocks, ok))} | {sum(r['denied'] for r in ok)} | {sum(r['interrupted'] for r in ok)} "
          f"| {sum(map(n_failed, ok))}/{sum(r['tool_calls'] for r in ok)} | | |")
    print()
    breakdown(ok)


def one(arg):
    path = analyze.resolve(arg)
    r = session_counts(path)
    if r is None:
        analyze.die(2, f"{path}: no assistant messages -- nothing to analyse; pick another session")
    if "fatal" in r:
        print("SCHEMA CHECK FAILED — run analyze.py on this session and fix what it reports.", file=sys.stderr)
        for f in r["fatal"]:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(3)
    print(f"# Quality: {os.path.basename(path)[:8]} ({r['project']})")
    print()
    print("| signal | count |")
    print("|---|---:|")
    for label, value in (("undone work", r["undone"]), ("review-fix commits", r["fix_commits"]),
                         ("hook blocks", n_blocks(r)), ("denied", r["denied"]), ("interrupted", r["interrupted"]),
                         ("failed tool calls", f"{n_failed(r)} of {r['tool_calls']}"),
                         ("red-first", analyze.red_cell(r)), ("tests weakened", r["weakened"])):
        print(f"| {label} | {value} |")
    print()
    breakdown([r])


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    opt = lambda k: args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    if "--family" in args:
        ids = [a for a in args[args.index("--family") + 1:] if not a.startswith("-")]
        if not ids:
            analyze.die(2, "--family needs session ids or transcript paths")
        return family(ids)
    if "--last" in args:
        try:
            n = int(opt("--last"))
        except (TypeError, ValueError):
            analyze.die(2, "--last needs a number of sessions")
        return trend(n, opt("--exclude"))
    pos = [a for a in args if not a.startswith("-")]
    one(pos[0] if pos else None)


if __name__ == "__main__":
    main()
