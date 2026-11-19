"""Tests for pr_body_guard.py. Run: python -I hooks/test_pr_body_guard.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pr_body_guard.py")
LINE = "Merge danger: two-way / local / skim"


def run(payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, "-I", HOOK], input=raw, capture_output=True,
                          text=True, encoding="utf-8").returncode


def shell(command, tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}}


class PrBodyGuard(unittest.TestCase):
    def test_body_without_line_is_blocked(self):
        self.assertEqual(run(shell('gh pr create --title "x" --body "Summary only"')), 2)

    def test_body_with_line_passes(self):
        self.assertEqual(run(shell(f'gh pr create --title "x" --body "{LINE}\n\nSummary"')), 0)

    def test_heredoc_body_with_line_passes(self):
        cmd = f"gh pr create --title x --body \"$(cat <<'EOF'\n{LINE}\nSummary\nEOF\n)\""
        self.assertEqual(run(shell(cmd)), 0)

    def test_powershell_without_line_is_blocked(self):
        self.assertEqual(run(shell('gh pr create --title x --body "nope"', "PowerShell")), 2)

    def test_body_file_with_and_without_line(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, "good.md"), os.path.join(d, "bad.md")
            with open(good, "w", encoding="utf-8") as f:
                f.write(LINE + "\n\nSummary\n")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("Summary\n")
            self.assertEqual(run(shell(f'gh pr create --title x --body-file "{good}"')), 0)
            self.assertEqual(run(shell(f'gh pr create --title x -F "{bad}"')), 2)

    def test_fill_without_body_is_blocked(self):
        self.assertEqual(run(shell("gh pr create --fill")), 2)

    def test_other_gh_commands_pass(self):
        self.assertEqual(run(shell("gh pr list --state all")), 0)

    def test_mention_in_another_command_passes(self):
        self.assertEqual(run(shell('git commit -m "hook blocks gh pr create without the line"')), 0)

    def test_chained_create_is_blocked(self):
        self.assertEqual(run(shell("git push -u origin x && gh pr create --fill")), 2)

    def test_non_shell_tool_passes(self):
        self.assertEqual(run({"tool_name": "Edit", "tool_input": {"command": "gh pr create"}}), 0)

    def test_bad_json_passes(self):
        self.assertEqual(run("not json"), 0)


if __name__ == "__main__":
    unittest.main()
