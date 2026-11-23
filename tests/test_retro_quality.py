"""ckore-retro's quality counts: undone work, review-fix commits, hook blocks, denials, interruptions
and failed tool calls, read from transcripts. Nothing a user or a tool wrote may reach the output.

Run: python -I -m unittest discover tests
"""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("quality", os.path.join(REPO, "skills/ckore-retro/quality.py"))
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)

SECRET = "zebra-quartz"   # stands for anything a user or a tool wrote
HOOK_BLOCK = "PreToolUse:Bash hook error: [command hook 4]: Blocked: " + SECRET
DENIED = "Permission for this action was denied by the Claude Code auto mode classifier. " + SECRET


class Transcript:
    """Builds a minimal transcript: one assistant call per tool use, then its result."""

    def __init__(self, day=20, start=0):
        self.lines, self.n, self.day = [], start, day

    def _stamp(self):
        return f"2026-11-{self.day:02d}T10:{self.n // 60:02d}:{self.n % 60:02d}Z"

    def tool(self, name, inp, result="ok", is_error=False):
        self.n += 1
        tid = f"t{self.n}"
        self.lines.append({"type": "assistant", "requestId": f"r{self.n}", "timestamp": self._stamp(),
                           "message": {"model": "claude-opus-5-5", "usage": {"input_tokens": 1, "output_tokens": 1},
                                       "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        self.lines.append({"type": "user", "timestamp": self._stamp(),
                           "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                                    "content": result, "is_error": is_error}]}})
        return self

    def bash(self, cmd, result="ok", is_error=False):
        return self.tool("Bash", {"command": cmd}, result, is_error)

    def edit(self, path):
        return self.tool("Edit", {"file_path": path, "old_string": "a", "new_string": "b"})

    def prompt(self, text):
        self.n += 1
        self.lines.append({"type": "user", "timestamp": self._stamp(),
                           "message": {"content": [{"type": "text", "text": text}]}})
        return self

    def repeat_last_call(self):
        """A streamed call is logged twice: the same tool use and result appear again."""
        self.lines += self.lines[-2:]
        return self

    def save(self, root=None, name="s", project="proj"):
        d = os.path.join(root or tempfile.mkdtemp(), project)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name + ".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x, separators=(",", ":")) for x in self.lines) + "\n")
        return path

    def save_as_subagent_of(self, main_path, agent_id="a1"):
        d = os.path.join(main_path[:-len(".jsonl")], "subagents")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"agent-{agent_id}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x, separators=(",", ":")) for x in self.lines) + "\n")
        with open(path[:-len(".jsonl")] + ".meta.json", "w", encoding="utf-8") as f:
            json.dump({"agentType": "general-purpose", "description": "worker"}, f)
        return path

    def counts(self):
        return quality.session_counts(self.save())


class UndoneWork(unittest.TestCase):
    def test_a_git_revert_is_undone_work(self):
        self.assertEqual(Transcript().bash("git revert --no-edit abc123").counts()["undone"], 1)

    def test_a_hard_reset_after_another_command_is_undone_work(self):
        self.assertEqual(Transcript().bash("cd repo && git reset --hard HEAD~1").counts()["undone"], 1)

    def test_discarding_working_tree_changes_is_undone_work(self):
        c = (Transcript().bash("git checkout -- src/x.py").bash("git restore src/y.py")
             .bash('git -C "my repo" checkout .').counts())
        self.assertEqual(c["undone"], 3)

    def test_taking_a_file_from_another_ref_or_unstaging_is_not_undone_work(self):
        c = (Transcript().bash("git checkout main -- tests/test_x.py").bash("git restore --staged src/x.py")
             .bash("git checkout -b feature").counts())
        self.assertEqual(c["undone"], 0)

    def test_a_revert_only_mentioned_in_text_is_not_undone_work(self):
        c = (Transcript().bash('echo "then run git revert abc"')
             .bash("cat > notes.md <<'EOF'\ngit revert abc123\ngit reset --hard\nEOF")
             .bash("grep -rn 'git reset --hard' docs").counts())
        self.assertEqual(c["undone"], 0)

    def test_powershell_commands_count_too(self):
        self.assertEqual(Transcript().tool("PowerShell", {"command": "git revert HEAD"}).counts()["undone"], 1)


class ReviewFixCommits(unittest.TestCase):
    def test_a_commit_that_says_review_fixes_is_counted(self):
        c = Transcript().bash('git commit -m "Review fixes: guard sees edited files"').counts()
        self.assertEqual(c["fix_commits"], 1)

    def test_a_review_fix_message_in_a_heredoc_is_counted(self):
        c = Transcript().bash("git add -A && git commit -F - <<'EOF'\nretro: address review: restore L11\nEOF").counts()
        self.assertEqual(c["fix_commits"], 1)

    def test_a_fixup_commit_is_counted(self):
        self.assertEqual(Transcript().bash("git commit --fixup abc123").counts()["fix_commits"], 1)

    def test_an_ordinary_commit_is_not_counted(self):
        c = Transcript().bash('git commit -m "Add the review skill"').bash("git log --grep 'Review fixes'").counts()
        self.assertEqual(c["fix_commits"], 0)


class BlocksAndDenials(unittest.TestCase):
    def test_a_hook_block_is_grouped_by_tool_and_hook_and_is_not_a_failed_call(self):
        c = (Transcript().bash("sleep 600", HOOK_BLOCK, is_error=True).bash("sleep 900", HOOK_BLOCK, is_error=True)
             .tool("Agent", {"prompt": "x"}, "PreToolUse:Agent hook error: [command hook 2]: Blocked", is_error=True)
             .counts())
        self.assertEqual(dict(c["hook_blocks"]), {"Bash hook 4": 2, "Agent hook 2": 1})
        self.assertEqual(sum(c["failed"].values()), 0)

    def test_a_permission_denial_is_counted_as_denied_not_failed(self):
        c = (Transcript().bash("rm -rf build", DENIED, is_error=True)
             .tool("Edit", {"file_path": "a.py"}, "The user doesn't want to proceed with this tool use.", is_error=True)
             .counts())
        self.assertEqual((c["denied"], sum(c["failed"].values())), (2, 0))

    def test_a_user_interruption_is_counted(self):
        c = Transcript().bash("ls").prompt("[Request interrupted by user for tool use]").counts()
        self.assertEqual(c["interrupted"], 1)


class FailedToolCalls(unittest.TestCase):
    def test_failed_calls_are_grouped_by_tool_out_of_all_tool_calls(self):
        c = (Transcript().bash("ls nope", "No such file", is_error=True).bash("ls")
             .tool("Edit", {"file_path": "a.py"}, "String to replace not found", is_error=True)
             .tool("mcp__1234abcd__execute_sql", {"query": "x"}, "syntax error", is_error=True).counts())
        self.assertEqual(dict(c["failed"]), {"Bash": 1, "Edit": 1, "execute_sql": 1})
        self.assertEqual(c["tool_calls"], 4)

    def test_a_failing_test_run_is_not_a_failed_call(self):
        c = Transcript().bash("python -m pytest tests", "1 failed", is_error=True).counts()
        self.assertEqual(sum(c["failed"].values()), 0)

    def test_a_call_logged_twice_is_counted_once(self):
        c = (Transcript().bash("git revert abc").repeat_last_call()
             .bash("ls nope", "No such file", is_error=True).repeat_last_call().counts())
        self.assertEqual((c["undone"], dict(c["failed"]), c["tool_calls"]), (1, {"Bash": 1}, 2))

    def test_subagent_transcripts_are_included(self):
        main = Transcript().bash("git revert abc").save()
        Transcript(start=100).bash("git reset --hard").bash("x", HOOK_BLOCK, is_error=True).save_as_subagent_of(main)
        c = quality.session_counts(main)
        self.assertEqual((c["undone"], dict(c["hook_blocks"])), (2, {"Bash hook 4": 1}))

    def test_red_first_and_weakened_come_from_the_cost_analyzer(self):
        c = (Transcript().edit("tests/test_x.py").bash("python -m pytest tests", "1 failed", is_error=True)
             .edit("src/x.py").counts())
        self.assertEqual((c["red_first"], c["source_files"], c["weakened"]), (1, 1, 0))

    def test_a_transcript_with_no_assistant_calls_gives_nothing(self):
        self.assertIsNone(Transcript().prompt("hello").counts())


def run(*argv, root):
    """Output of the command line, with transcripts looked up under `root`."""
    old = quality.analyze.PROJECTS, quality.analyze.SMELL_LOG
    quality.analyze.PROJECTS, quality.analyze.SMELL_LOG = root, os.path.join(root, "no-smells.jsonl")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            quality.main(list(argv))
    finally:
        quality.analyze.PROJECTS, quality.analyze.SMELL_LOG = old
    return buf.getvalue()


def row(out, start):
    return next(line for line in out.splitlines() if line.startswith(start))


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        (Transcript(day=20).prompt("please " + SECRET).bash(f"git revert abc # {SECRET}")
         .bash("sleep 600", HOOK_BLOCK, is_error=True).bash("ls " + SECRET, SECRET, is_error=True)
         .bash(f'git commit -m "Review fixes: {SECRET}"').save(self.root, "aaaa1111", "alpha"))
        (Transcript(day=21).bash("git reset --hard").bash("ls").save(self.root, "bbbb2222", "beta"))
        (Transcript(day=22).bash("ls").save(self.root, "cccc3333", "gamma"))

    def test_trend_prints_one_row_per_session_newest_first(self):
        out = run("--last", "10", root=self.root)
        rows = [line for line in out.splitlines() if line.startswith("| 2026-")]
        self.assertEqual([r.split("|")[2].strip() for r in rows], ["gamma", "beta", "alpha"])
        self.assertEqual([c.strip() for c in rows[2].split("|")[3:9]], ["1", "1", "1", "0", "0", "1/4"])

    def test_trend_counts_the_sessions_each_signal_shows_up_in(self):
        out = run("--last", "10", root=self.root)
        self.assertIn("| 2/3 |", row(out, "| undone work"))
        self.assertIn("| 1/3 |", row(out, "| review-fix commits"))

    def test_trend_takes_only_the_newest_n_and_skips_excluded_projects(self):
        out = run("--last", "1", "--exclude", "gamma", root=self.root)
        rows = [line for line in out.splitlines() if line.startswith("| 2026-")]
        self.assertEqual([r.split("|")[2].strip() for r in rows], ["beta"])

    def test_trend_names_the_hooks_and_tools_behind_the_counts(self):
        out = run("--last", "10", root=self.root)
        self.assertIn("Bash hook 4: 1", out)
        self.assertIn("Bash: 1", out)

    def test_one_session_prints_its_counts(self):
        out = run("aaaa", root=self.root)
        self.assertIn("| undone work | 1 |", out)
        self.assertIn("| failed tool calls | 1 of 4 |", out)

    def test_nothing_a_user_or_tool_wrote_reaches_the_output(self):
        for argv in (["--last", "10"], ["aaaa"], ["--family", "aaaa", "bbbb"]):
            self.assertNotIn(SECRET, run(*argv, root=self.root))

    def test_family_counts_a_call_a_fork_copied_from_its_parent_once(self):
        parent = Transcript(day=20).bash("git revert abc")
        fork = Transcript(day=20).bash("git revert abc").bash("git reset --hard")   # t1 is the parent's call again
        parent.save(self.root, "dddd4444", "delta")
        fork.save(self.root, "eeee5555", "delta")
        out = run("--family", "dddd", "eeee", root=self.root)
        self.assertIn("| total | | 2 |", out.replace("**", ""))

    def test_an_unknown_session_exits_2(self):
        with self.assertRaises(SystemExit) as e:
            run("nope", root=self.root)
        self.assertEqual(e.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
