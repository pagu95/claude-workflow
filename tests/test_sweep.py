"""ckore-clean-worktrees/sweep.py sorts every leftover worktree into remove / ask / keep, removes
only the safe tier by itself, and never forces, deletes a branch or touches recent work.

Each test builds real git repos under a root whose name has a space in it (the owner's home
folder does, and that broke the hand-written commands this script replaces).

Run: python -I -m unittest discover tests
"""
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "skills", "ckore-clean-worktrees"))
import sweep  # noqa: E402

HOUR = 3600
DAY = 24 * HOUR


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
         "-C", cwd, *args], capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(f"git {' '.join(args)}: {out.stderr}")
    return out.stdout.strip()


def _rm_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


class SweepCase(unittest.TestCase):
    def setUp(self):
        base = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base, onexc=_rm_readonly)
        self.root = os.path.join(base, "my projects")
        os.mkdir(self.root)
        self.repo = self.make_repo("game")
        # Everything in a test is seconds old; look at it from three hours later.
        self.later = time.time() + 3 * HOUR
        self.prs = {}

    def make_repo(self, name):
        repo = os.path.join(self.root, name)
        os.mkdir(repo)
        git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "a.txt"), "w") as f:
            f.write("a\n")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-q", "-m", "first")
        return repo

    def add_worktree(self, name, branch=None, repo=None, path=None):
        repo = repo or self.repo
        path = path or os.path.join(repo, ".claude", "worktrees", name)
        if branch:
            git(repo, "worktree", "add", "-q", "-b", branch, path)
        else:
            git(repo, "worktree", "add", "-q", "--detach", path)
        return path

    def commit_in(self, path, name="b.txt"):
        with open(os.path.join(path, name), "w") as f:
            f.write("b\n")
        git(path, "add", name)
        git(path, "commit", "-q", "-m", "work")
        return git(path, "rev-parse", "HEAD")

    def lookup(self, repo):
        return self.prs

    def rows(self, **kw):
        kw.setdefault("now", self.later)
        kw.setdefault("pr_lookup", self.lookup)
        return sweep.inventory(self.root, **kw)

    def row(self, path, **kw):
        found = [r for r in self.rows(**kw) if os.path.normcase(r["path"]) == os.path.normcase(path)]
        self.assertEqual(len(found), 1, f"expected one row for {path}")
        return found[0]

    def apply(self, **kw):
        kw.setdefault("now", self.later)
        kw.setdefault("pr_lookup", self.lookup)
        return sweep.apply(self.root, **kw)

    def registered(self, repo=None):
        return git(repo or self.repo, "worktree", "list", "--porcelain")


class Tiers(SweepCase):
    def test_a_detached_clean_worktree_is_removed_without_asking(self):
        path = self.add_worktree("wf_1")
        self.assertEqual(self.row(path)["tier"], "auto")
        self.apply()
        self.assertFalse(os.path.exists(path))
        self.assertNotIn("wf_1", self.registered())

    def test_untracked_files_send_a_worktree_to_the_ask_tier(self):
        path = self.add_worktree("wf_dirty")
        with open(os.path.join(path, "out.log"), "w") as f:
            f.write("x")
        row = self.row(path)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("out.log", row["why"])
        self.apply()
        self.assertTrue(os.path.exists(os.path.join(path, "out.log")))

    def test_a_detached_commit_on_no_branch_is_asked_about(self):
        path = self.add_worktree("wf_orphan")
        self.commit_in(path)
        row = self.row(path)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("no branch", row["why"])

    def test_a_branch_whose_tip_is_a_merged_pr_head_is_removed_and_the_branch_stays(self):
        path = self.add_worktree("agent-1", branch="feat/arrows")
        tip = self.commit_in(path)
        self.prs = {"feat/arrows": [{"number": 7, "state": "MERGED", "oid": tip}]}
        self.assertEqual(self.row(path)["tier"], "auto")
        self.apply()
        self.assertFalse(os.path.exists(path))
        self.assertEqual(git(self.repo, "rev-parse", "feat/arrows"), tip)

    def test_commits_added_after_the_merge_keep_the_branch_in_the_ask_tier(self):
        path = self.add_worktree("agent-2", branch="feat/more")
        merged = self.commit_in(path)
        self.commit_in(path, "c.txt")
        self.prs = {"feat/more": [{"number": 8, "state": "MERGED", "oid": merged}]}
        row = self.row(path)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("#8", row["why"])

    def test_a_branch_with_no_pr_is_asked_about(self):
        path = self.add_worktree("desktop", branch="desktop-app")
        self.commit_in(path)
        row = self.row(path)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("no PR", row["why"])
        self.assertEqual(row["branch"], "desktop-app")

    def test_a_repo_where_pr_state_is_unknown_asks_instead_of_guessing(self):
        path = self.add_worktree("agent-3", branch="feat/x")
        row = self.row(path, pr_lookup=lambda repo: None)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("unknown", row["why"])

    def test_anything_changed_in_the_last_two_hours_is_kept(self):
        path = self.add_worktree("wf_live")
        row = self.row(path, now=time.time() + HOUR)
        self.assertEqual(row["tier"], "keep")
        self.apply(now=time.time() + HOUR)
        self.assertTrue(os.path.exists(path))

    def test_a_worktree_outside_the_worktrees_folder_is_always_asked_about(self):
        path = self.add_worktree("x", path=os.path.join(self.root, "game-bal"))
        row = self.row(path)
        self.assertEqual(row["tier"], "ask")
        self.assertIn("outside", row["why"])
        self.assertEqual(row["repo"], "game")

    def test_a_locked_worktree_is_asked_about(self):
        path = self.add_worktree("wf_locked")
        git(self.repo, "worktree", "lock", path)
        self.assertEqual(self.row(path)["tier"], "ask")
        self.apply()
        self.assertTrue(os.path.exists(path))

    def test_looking_does_not_make_a_worktree_look_recently_used(self):
        path = self.add_worktree("agent-4", branch="feat/y")
        self.commit_in(path)
        before = sweep.newest_change(path)
        time.sleep(1.1)
        self.rows()
        self.assertEqual(sweep.newest_change(path), before)

    def test_a_file_edited_in_the_last_two_hours_keeps_an_old_worktree(self):
        path = self.add_worktree("wf_edit")
        target = os.path.join(path, "a.txt")
        with open(target, "a") as f:
            f.write("more\n")
        os.utime(target, (self.later - 20 * 60, self.later - 20 * 60))
        self.assertEqual(self.row(path)["tier"], "keep")
        result = sweep.remove(self.root, [], force=[path], now=self.later, pr_lookup=self.lookup)
        self.assertEqual(result["removed"], [])
        self.assertTrue(os.path.exists(target))

    def test_the_first_changed_file_is_named_in_full(self):
        path = self.add_worktree("wf_mod")
        with open(os.path.join(path, "a.txt"), "a") as f:
            f.write("more\n")
        self.assertEqual(self.row(path)["why"], "uncommitted or untracked: a.txt")

    def test_each_row_says_which_flag_removes_it(self):
        clean = self.add_worktree("desktop", branch="desktop-app")
        dirty = self.add_worktree("x", path=os.path.join(self.root, "game-bal"))
        with open(os.path.join(dirty, "out.log"), "w") as f:
            f.write("x")
        self.assertEqual(self.row(clean)["flag"], "--remove")
        self.assertEqual(self.row(dirty)["flag"], "--force")

    def test_the_main_checkout_is_never_a_row(self):
        self.add_worktree("wf_1")
        paths = [os.path.normcase(r["path"]) for r in self.rows()]
        self.assertNotIn(os.path.normcase(self.repo), paths)


class Leftovers(SweepCase):
    def wt_dir(self):
        d = os.path.join(self.repo, ".claude", "worktrees")
        os.makedirs(d, exist_ok=True)
        return d

    def test_an_empty_leftover_folder_is_removed(self):
        path = os.path.join(self.wt_dir(), "wf_gone")
        os.mkdir(path)
        self.assertEqual(self.row(path)["tier"], "auto")
        self.apply()
        self.assertFalse(os.path.exists(path))

    def test_a_leftover_folder_with_content_is_asked_about(self):
        path = os.path.join(self.wt_dir(), "merge-1")
        os.mkdir(path)
        with open(os.path.join(path, "notes.md"), "w") as f:
            f.write("x")
        self.assertEqual(self.row(path)["tier"], "ask")
        self.apply()
        self.assertTrue(os.path.exists(os.path.join(path, "notes.md")))

    def test_a_file_written_in_the_last_two_hours_keeps_a_leftover_folder(self):
        path = os.path.join(self.wt_dir(), "merge-2")
        os.mkdir(path)
        target = os.path.join(path, "notes.md")
        with open(target, "w") as f:
            f.write("x")
        os.utime(path, (self.later - 5 * HOUR, self.later - 5 * HOUR))
        os.utime(target, (self.later - 20 * 60, self.later - 20 * 60))
        self.assertEqual(self.row(path)["tier"], "keep")

    def test_another_repos_worktree_in_this_folder_is_not_a_leftover(self):
        other = self.make_repo("site")
        path = self.add_worktree("x", repo=other, path=os.path.join(self.wt_dir(), "borrowed"))
        row = self.row(path)
        self.assertEqual((row["repo"], row["kind"]), ("site", "worktree"))

    def test_loose_files_go_after_seven_days_and_stay_before(self):
        old = os.path.join(self.wt_dir(), "batch.log")
        new = os.path.join(self.wt_dir(), "pr-body.txt")
        for p in (old, new):
            with open(p, "w") as f:
                f.write("x")
        os.utime(old, (self.later - 8 * DAY, self.later - 8 * DAY))
        os.utime(new, (self.later - 6 * DAY, self.later - 6 * DAY))
        self.assertEqual(self.row(old)["tier"], "auto")
        self.assertEqual(self.row(new)["tier"], "keep")
        self.apply()
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))


class Roots(SweepCase):
    def test_every_repo_under_the_root_is_swept_and_other_folders_are_ignored(self):
        other = self.make_repo("site")
        os.mkdir(os.path.join(self.root, "not-a-repo"))
        a = self.add_worktree("wf_1")
        b = self.add_worktree("wf_2", repo=other)
        outside = self.add_worktree("x", path=os.path.join(self.root, "game-bal"))
        rows = self.rows()
        self.assertEqual(sorted(r["repo"] for r in rows), ["game", "game", "site"])
        self.assertEqual({os.path.normcase(r["path"]) for r in rows},
                         {os.path.normcase(p) for p in (a, b, outside)})


class Apply(SweepCase):
    def test_apply_reports_what_it_removed_and_what_is_left(self):
        gone = self.add_worktree("wf_1")
        kept = self.add_worktree("desktop", branch="desktop-app")
        result = self.apply()
        self.assertEqual([os.path.normcase(r["path"]) for r in result["removed"]], [os.path.normcase(gone)])
        self.assertEqual([os.path.normcase(r["path"]) for r in result["ask"]], [os.path.normcase(kept)])
        self.assertEqual(result["failed"], [])

    def test_a_removal_that_fails_is_reported_and_the_rest_still_runs(self):
        a = self.add_worktree("wf_1")
        b = self.add_worktree("wf_2")
        real = sweep.remove_row

        def flaky(row, force=False):
            if os.path.normcase(row["path"]) == os.path.normcase(a):
                return "Device or resource busy"
            return real(row, force)

        sweep.remove_row = flaky
        self.addCleanup(setattr, sweep, "remove_row", real)
        result = self.apply()
        self.assertEqual(len(result["failed"]), 1)
        self.assertIn("busy", result["failed"][0]["error"])
        self.assertTrue(os.path.exists(a))
        self.assertFalse(os.path.exists(b))


class Remove(SweepCase):
    def remove(self, paths, force=()):
        return sweep.remove(self.root, paths, force=force, now=self.later, pr_lookup=self.lookup)

    def test_an_approved_row_is_removed_and_its_branch_stays(self):
        path = self.add_worktree("desktop", branch="desktop-app")
        tip = self.commit_in(path)
        result = self.remove([path])
        self.assertEqual(len(result["removed"]), 1)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(git(self.repo, "rev-parse", "desktop-app"), tip)

    def test_a_dirty_worktree_is_refused_without_force_and_removed_with_it(self):
        path = self.add_worktree("wf_dirty")
        with open(os.path.join(path, "out.log"), "w") as f:
            f.write("x")
        result = self.remove([path])
        self.assertEqual(len(result["failed"]), 1)
        self.assertTrue(os.path.exists(path))
        result = self.remove([], force=[path])
        self.assertEqual(len(result["removed"]), 1)
        self.assertFalse(os.path.exists(path))

    def test_a_path_the_inventory_does_not_list_is_refused(self):
        self.add_worktree("wf_1")
        for path in (self.repo, os.path.join(self.root, "nope")):
            result = self.remove([], force=[path])
            self.assertEqual(result["removed"], [])
            self.assertIn("not in the inventory", result["failed"][0]["error"])
        self.assertTrue(os.path.exists(os.path.join(self.repo, "a.txt")))

    def test_recent_work_is_refused_even_with_force(self):
        path = self.add_worktree("wf_live")
        result = sweep.remove(self.root, [], force=[path], now=time.time() + HOUR, pr_lookup=self.lookup)
        self.assertEqual(result["removed"], [])
        self.assertTrue(os.path.exists(path))

    def test_a_leftover_folder_with_content_needs_force(self):
        d = os.path.join(self.repo, ".claude", "worktrees", "merge-1")
        os.makedirs(d)
        with open(os.path.join(d, "notes.md"), "w") as f:
            f.write("x")
        self.assertEqual(len(self.remove([d])["failed"]), 1)
        self.assertEqual(len(self.remove([], force=[d])["removed"]), 1)
        self.assertFalse(os.path.exists(d))


class CommandLine(SweepCase):
    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = sweep.main([self.root, *args], now=self.later, pr_lookup=self.lookup)
        return code, out.getvalue()

    def test_without_apply_nothing_is_removed_and_the_plan_is_printed(self):
        auto = self.add_worktree("wf_1")
        self.add_worktree("desktop", branch="desktop-app")
        code, text = self.run_main()
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(auto))
        self.assertIn("would remove 1", text)
        self.assertIn("desktop-app", text)
        self.assertIn("| game |", text)

    def test_apply_prints_the_count_and_the_rows_that_need_a_call(self):
        self.add_worktree("wf_1")
        self.add_worktree("desktop", branch="desktop-app")
        code, text = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertIn("removed 1", text)
        self.assertIn("desktop-app", text)
        self.assertIn("| --remove |", text)
        self.assertNotIn("wf_1 |", text)


if __name__ == "__main__":
    unittest.main()
