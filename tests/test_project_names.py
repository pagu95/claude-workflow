"""Transcript folders are named after the project path (every non-alphanumeric char becomes '-').
context-trim's audit and retro's analyzer shorten them for display. They must work for any home
folder and workspace layout, not one machine's.

Run: python -I -m unittest discover tests
"""
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MODULES = [load("skills/ckore-context-trim/audit.py", "audit"), load("skills/ckore-retro/analyze.py", "analyze")]

CASES = [
    ("C--Users-Ana-PC-IdeaProjects-shop-web", r"C:\Users\Ana PC", "shop-web"),
    ("-Users-bo-Projects-api", "/Users/bo", "api"),
    ("-home-ana-projects-api", "/home/ana", "api"),
    # Only a *Projects folder is a workspace: "dev", "code" or "src" may be part of the project name.
    ("-home-ana-dev-tools", "/home/ana", "dev-tools"),
    ("-home-ana-code-api", "/home/ana", "code-api"),
    ("-Users-bo-src-tools-x", "/Users/bo", "src-tools-x"),
    ("C--Users-Ana-PC-IdeaProjects-shop--claude-worktrees-fix-x", r"C:\Users\Ana PC",
     "shop--claude-worktrees-fix-x"),
    ("-Users-bo-my-app", "/Users/bo", "my-app"),  # no workspace folder: only home is stripped
    ("-opt-build-app", "/home/ana", "-opt-build-app"),  # outside home: left alone
]


class ShortProject(unittest.TestCase):
    def test_strips_home_and_one_workspace_folder(self):
        for mod in MODULES:
            for slug, home, want in CASES:
                with self.subTest(mod=mod.__name__, slug=slug):
                    self.assertEqual(mod.short_project(slug, home), want)


if __name__ == "__main__":
    unittest.main()
