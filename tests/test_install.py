"""install.sh links every skill and removes links it left for skills that were renamed or deleted,
without touching anything else in ~/.claude/skills.

Run: python -I -m unittest discover tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASH = shutil.which("bash")


def sh(cmd, env=None):
    return subprocess.run([BASH, "-c", cmd], capture_output=True, text=True, env=env)


@unittest.skipIf(BASH is None, "needs bash")
class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        self.claude = os.path.join(self.tmp, "home", ".claude")
        for d in ("skills/ckore-a", "skills/old-name", "profiles"):
            os.makedirs(os.path.join(self.repo, d))
        with open(os.path.join(self.repo, "skills/ckore-a/SKILL.md"), "w") as f:
            f.write("---\nname: ckore-a\n---\n")
        open(os.path.join(self.repo, "CLAUDE.md"), "w").close()
        shutil.copy(os.path.join(REPO, "install.sh"), self.repo)
        os.makedirs(os.path.join(self.tmp, "elsewhere", "gone"))
        os.makedirs(os.path.join(self.claude, "skills", "own-real-dir"))
        self.env = dict(os.environ, HOME=os.path.join(self.tmp, "home"), CLAUDE_DIR=self.claude,
                        MSYS="winsymlinks:nativestrict")

    def bash_path(self, p):
        return sh(f'cygpath -u "{p}" 2>/dev/null || echo "{p}"').stdout.strip()

    def link(self, target, name):
        r = sh(f'ln -s "{self.bash_path(target)}" "{self.bash_path(os.path.join(self.claude, "skills", name))}"',
               self.env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_prunes_only_dangling_links_into_this_repo(self):
        self.link(os.path.join(self.repo, "skills", "old-name"), "old-name")
        self.link(os.path.join(self.tmp, "elsewhere", "gone"), "foreign")
        shutil.rmtree(os.path.join(self.repo, "skills", "old-name"))  # the skill was renamed
        shutil.rmtree(os.path.join(self.tmp, "elsewhere", "gone"))  # not ours: keep the link

        r = sh(f'bash "{self.bash_path(os.path.join(self.repo, "install.sh"))}"', self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        skills = os.path.join(self.claude, "skills")
        self.assertFalse(os.path.lexists(os.path.join(skills, "old-name")), r.stdout)
        self.assertTrue(os.path.lexists(os.path.join(skills, "foreign")))
        self.assertTrue(os.path.isdir(os.path.join(skills, "own-real-dir")))
        self.assertTrue(os.path.exists(os.path.join(skills, "ckore-a", "SKILL.md")))

    def test_prunes_a_renamed_skill_whose_folder_kept_ignored_files(self):
        # git removes the tracked files of a renamed skill but leaves ignored ones such as __pycache__
        os.makedirs(os.path.join(self.repo, "skills", "old-name", "__pycache__"))
        self.link(os.path.join(self.repo, "skills", "old-name"), "old-name")

        r = sh(f'bash "{self.bash_path(os.path.join(self.repo, "install.sh"))}"', self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        self.assertFalse(os.path.lexists(os.path.join(self.claude, "skills", "old-name")), r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.claude, "skills", "ckore-a", "SKILL.md")))


    def install(self, *args):
        r = sh(" ".join([f'bash "{self.bash_path(os.path.join(self.repo, "install.sh"))}"']
                        + [f'"{self.bash_path(a)}"' if os.sep in a else a for a in args]), self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def make_overlay(self):
        ov = os.path.join(self.tmp, "overlay")
        for d in ("skills/ckore-private", "profiles", "ledger"):
            os.makedirs(os.path.join(ov, d))
        for rel, text in (("skills/ckore-private/SKILL.md", "---\nname: ckore-private\n---\n"),
                          ("profiles/work.md", "# work\n"), ("ledger/LESSONS.md", "# Lessons\n")):
            with open(os.path.join(ov, rel), "w") as f:
                f.write(text)
        return ov

    def test_overlay_links_skills_profiles_and_the_ledger(self):
        ov = self.make_overlay()
        self.install("--overlay", ov)
        self.assertTrue(os.path.exists(os.path.join(self.claude, "skills", "ckore-private", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(self.claude, "skills", "ckore-a", "SKILL.md")))
        with open(os.path.join(self.claude, "profiles", "work.md")) as f:
            self.assertEqual(f.read(), "# work\n")
        lessons = os.path.join(self.claude, "retro", "LESSONS.md")
        self.assertTrue(os.path.islink(lessons))
        with open(lessons) as f:
            self.assertEqual(f.read(), "# Lessons\n")

    def test_rerun_without_overlay_keeps_overlay_links(self):
        ov = self.make_overlay()
        self.install("--overlay", ov)
        self.install()
        self.assertTrue(os.path.exists(os.path.join(self.claude, "skills", "ckore-private", "SKILL.md")))

    def test_overlay_prunes_its_own_renamed_skill(self):
        ov = self.make_overlay()
        os.makedirs(os.path.join(ov, "skills", "old-private"))
        self.link(os.path.join(ov, "skills", "old-private"), "old-private")
        shutil.rmtree(os.path.join(ov, "skills", "old-private"))
        self.install("--overlay", ov)
        self.assertFalse(os.path.lexists(os.path.join(self.claude, "skills", "old-private")))

    def test_overlay_never_replaces_a_real_ledger(self):
        ov = self.make_overlay()
        os.makedirs(os.path.join(self.claude, "retro"))
        with open(os.path.join(self.claude, "retro", "LESSONS.md"), "w") as f:
            f.write("mine\n")
        out = self.install("--overlay", ov)
        with open(os.path.join(self.claude, "retro", "LESSONS.md")) as f:
            self.assertEqual(f.read(), "mine\n", out)

    def test_relative_overlay_path_works(self):
        self.make_overlay()
        r = sh(f'cd "{self.bash_path(self.tmp)}" && bash repo/install.sh --overlay overlay', self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        link = os.path.join(self.claude, "skills", "ckore-private")
        self.assertTrue(os.path.exists(os.path.join(link, "SKILL.md")))
        self.assertTrue(os.path.isabs(os.readlink(link)) or os.readlink(link).startswith("/"))

    def test_missing_overlay_dir_fails(self):
        r = sh(f'bash "{self.bash_path(os.path.join(self.repo, "install.sh"))}" --overlay '
               f'"{self.bash_path(os.path.join(self.tmp, "nowhere"))}"', self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.claude, "skills", "ckore-a")), r.stdout)

    def test_overlay_without_ledger(self):
        ov = self.make_overlay()
        shutil.rmtree(os.path.join(ov, "ledger"))
        self.install("--overlay", ov)
        self.assertTrue(os.path.exists(os.path.join(self.claude, "skills", "ckore-private", "SKILL.md")))
        self.assertFalse(os.path.lexists(os.path.join(self.claude, "retro", "LESSONS.md")))

    def test_identical_real_profile_and_ledger_become_links(self):
        # switch-over: the home copies were moved into the overlay, so the real files hold nothing new
        ov = self.make_overlay()
        os.makedirs(os.path.join(self.claude, "profiles"))
        os.makedirs(os.path.join(self.claude, "retro"))
        for rel, text in (("profiles/work.md", "# work\n"), ("retro/LESSONS.md", "# Lessons\n")):
            with open(os.path.join(self.claude, rel), "w") as f:
                f.write(text)
        self.install("--overlay", ov)
        self.assertTrue(os.path.islink(os.path.join(self.claude, "profiles", "work.md")))
        self.assertTrue(os.path.islink(os.path.join(self.claude, "retro", "LESSONS.md")))

    def test_file_reached_through_a_linked_folder_is_not_deleted(self):
        # ~/.claude/retro links to <overlay>/ledger, so dest and src are the same file: cmp says
        # identical, and removing dest would delete the ledger itself
        ov = self.make_overlay()
        r = sh(f'ln -s "{self.bash_path(os.path.join(ov, "ledger"))}" '
               f'"{self.bash_path(os.path.join(self.claude, "retro"))}"', self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.install("--overlay", ov)
        with open(os.path.join(ov, "ledger", "LESSONS.md")) as f:
            self.assertEqual(f.read(), "# Lessons\n")

    def test_differing_real_profile_is_kept_and_named(self):
        ov = self.make_overlay()
        os.makedirs(os.path.join(self.claude, "profiles"))
        with open(os.path.join(self.claude, "profiles", "work.md"), "w") as f:
            f.write("# newer local edit\n")
        out = self.install("--overlay", ov)
        dest = os.path.join(self.claude, "profiles", "work.md")
        self.assertFalse(os.path.islink(dest))
        with open(dest) as f:
            self.assertEqual(f.read(), "# newer local edit\n")
        self.assertIn("work.md", out)
        self.assertIn("differs", out)

    def test_overlay_path_is_recorded_for_the_leak_check(self):
        ov = self.make_overlay()
        self.install("--overlay", ov)
        with open(os.path.join(self.claude, "claude-workflow-overlay")) as f:
            self.assertEqual(f.read().strip(), self.bash_path(ov))

    def test_unknown_argument_fails(self):
        r = sh(f'bash "{self.bash_path(os.path.join(self.repo, "install.sh"))}" --nope', self.env)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
