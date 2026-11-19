"""Every workflow skill is named ckore-<name>, so none clashes with a Claude Code built-in
(/resume and /design are built-in commands; review overlaps code-review) or another plugin.

Checks the skill directories, their frontmatter, and every reference to a skill in a form that
can only mean the skill: `name`, /name, skills/name/, name/ at a path start, "name skill" and
frontmatter `name:`. Plain English ("we design", "a review") is left alone on purpose.

Run: python -I -m unittest discover tests
"""
import os
import re
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "ckore-"
SKILLS_DIR = os.path.join(REPO, "skills")
TEXT_EXT = (".md", ".py", ".sh", ".json", ".txt", "")


def skill_dirs():
    return sorted(d for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d)))


def bare_names():
    return [d[len(PREFIX):] if d.startswith(PREFIX) else d for d in skill_dirs()]


def reference_patterns(name):
    n = re.escape(name)
    return [
        rf"(?<!'s )`{n}`",               # `review`, but not an upstream credit (Matt Pocock's `tdd`)
        rf"(?<![\w./~-])/{n}(?![\w/-])",  # /resume as a command
        rf"\bskills/{n}(?![\w-])",        # skills/review/SKILL.md
        rf"(?<=[\s`(\[]){n}/",           # `retro/LESSONS.md`
        rf"(?<![\w-]){n} skill\b",       # the review skill
        rf"^name: {n}\s*$",              # frontmatter
    ]


def tracked_text_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True)
    for rel in out.stdout.splitlines():
        if rel.startswith("tests/"):  # the tests name the patterns and the built-ins on purpose
            continue
        if os.path.splitext(rel)[1] in TEXT_EXT and os.path.isfile(os.path.join(REPO, rel)):
            yield rel


class SkillNames(unittest.TestCase):
    def test_every_skill_dir_has_the_prefix(self):
        bad = [d for d in skill_dirs() if not d.startswith(PREFIX)]
        self.assertEqual(bad, [], f"skill dirs without {PREFIX}")

    def test_frontmatter_name_matches_the_dir(self):
        for d in skill_dirs():
            path = os.path.join(SKILLS_DIR, d, "SKILL.md")
            if not os.path.exists(path):  # a shared-rules dir has no SKILL.md
                continue
            with open(path, encoding="utf-8") as f:
                m = re.search(r"^name:\s*(\S+)", f.read(), re.M)
            self.assertIsNotNone(m, f"{d}/SKILL.md has no name:")
            self.assertEqual(m.group(1), d)

    def test_no_unprefixed_skill_references(self):
        pats = [(n, re.compile(p, re.M)) for n in bare_names() for p in reference_patterns(n)]
        hits = []
        for rel in tracked_text_files():
            with open(os.path.join(REPO, rel), encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for n, p in pats:
                        if p.search(line):
                            hits.append(f"{rel}:{i}: {n}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "unprefixed skill references:\n" + "\n".join(hits[:40]))


if __name__ == "__main__":
    unittest.main()
