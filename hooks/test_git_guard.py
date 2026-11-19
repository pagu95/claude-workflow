"""Tests for git_guard.py. Run: python -I hooks/test_git_guard.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_guard.py")


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


class GitGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.tmp.name
        cls.repo = os.path.join(root, "work", "api")
        cls.other = os.path.join(root, "personal")
        for r in (cls.repo, cls.other):
            os.makedirs(r)
            git(r, "init", "-q", "-b", "feature")
        cls.config = os.path.join(root, "guards.json")
        with open(cls.config, "w", encoding="utf-8") as f:
            json.dump({"git": [{"repos": [os.path.join(root, "work", "*")],
                                "protected_branches": ["staging", "saas-staging"],
                                "commit_needs_no_verify": True}]}, f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_hook(self, command, cwd=None, tool="Bash", raw=None):
        payload = raw if raw is not None else json.dumps(
            {"tool_name": tool, "cwd": cwd or self.repo, "tool_input": {"command": command}})
        env = dict(os.environ, CLAUDE_GUARDS_CONFIG=self.config)
        return subprocess.run([sys.executable, "-I", HOOK], input=payload, capture_output=True,
                              text=True, env=env).returncode

    def on_branch(self, branch):
        git(self.repo, "checkout", "-q", "-B", branch)

    # push
    def test_push_to_protected_branch_is_blocked(self):
        self.assertEqual(self.run_hook("git push origin staging"), 2)

    def test_push_refspec_to_protected_branch_is_blocked(self):
        self.assertEqual(self.run_hook("git push origin HEAD:refs/heads/saas-staging"), 2)

    def test_push_feature_branch_passes(self):
        self.on_branch("feature")
        self.assertEqual(self.run_hook("git push -u origin feature"), 0)

    def test_bare_push_on_protected_branch_is_blocked(self):
        self.on_branch("staging")
        try:
            self.assertEqual(self.run_hook("git push"), 2)
        finally:
            self.on_branch("feature")

    def test_chained_push_is_blocked(self):
        self.assertEqual(self.run_hook("npm test && git push origin staging"), 2)

    # commit
    def test_commit_without_no_verify_is_blocked(self):
        self.on_branch("feature")
        self.assertEqual(self.run_hook('git commit -m "PROJ-1: x"'), 2)

    def test_commit_with_no_verify_passes(self):
        self.on_branch("feature")
        self.assertEqual(self.run_hook('git commit --no-verify -m "PROJ-1: x"'), 0)

    def test_commit_on_protected_branch_is_blocked(self):
        self.on_branch("staging")
        try:
            self.assertEqual(self.run_hook('git commit --no-verify -m "x"'), 2)
        finally:
            self.on_branch("feature")

    def test_git_dash_c_uses_that_repo(self):
        self.assertEqual(self.run_hook(f'git -C "{self.repo}" commit -m x', cwd=self.other), 2)

    def test_worktree_subdir_is_covered(self):
        sub = os.path.join(self.repo, ".claude", "worktrees", "w1")
        os.makedirs(sub, exist_ok=True)
        self.assertEqual(self.run_hook("git push origin staging", cwd=sub), 2)

    # out of scope
    def test_other_repo_passes(self):
        self.assertEqual(self.run_hook("git push origin staging", cwd=self.other), 0)
        self.assertEqual(self.run_hook('git commit -m x', cwd=self.other), 0)

    def test_mention_in_message_passes(self):
        self.assertEqual(self.run_hook('git commit --no-verify -m "never git push origin staging"'), 0)

    def test_non_bash_tool_passes(self):
        self.assertEqual(self.run_hook("git push origin staging", tool="Edit"), 0)

    def test_bad_json_passes(self):
        self.assertEqual(self.run_hook("", raw="not json"), 0)

    def test_missing_config_passes(self):
        payload = json.dumps({"tool_name": "Bash", "cwd": self.repo,
                              "tool_input": {"command": "git push origin staging"}})
        env = dict(os.environ, CLAUDE_GUARDS_CONFIG=os.path.join(self.tmp.name, "none.json"))
        rc = subprocess.run([sys.executable, "-I", HOOK], input=payload, capture_output=True,
                            text=True, env=env).returncode
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
