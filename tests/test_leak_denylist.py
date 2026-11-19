"""No private name may reach this public repo. The deny list lives in the private overlay
(leak-denylist.txt, one extended regex per line), so this check runs only where the overlay is known:
$CLAUDE_WORKFLOW_OVERLAY, or the path install.sh --overlay recorded in ~/.claude/claude-workflow-overlay.
Intended hits are listed in the overlay's leak-allowlist.txt as `<file>:<whole line, trimmed>`.

Run: python -I -m unittest discover tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def native(path):
    """~/.claude/claude-workflow-overlay is written by Git Bash, so it may hold /c/Users/..."""
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == "/":
        return path[1].upper() + ":" + path[2:]
    return path


def overlay_dir():
    env = os.environ.get("CLAUDE_WORKFLOW_OVERLAY")
    if env:
        return native(env)
    marker = os.path.join(os.path.expanduser("~"), ".claude", "claude-workflow-overlay")
    if os.path.isfile(marker):
        with open(marker, encoding="utf-8") as f:
            return native(f.read().strip())
    return None


def patterns(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.rstrip("\r\n") for ln in f if ln.strip() and not ln.startswith("#")]


def leaks(repo, deny, allow):
    """Tracked lines matching any deny pattern, minus allowed `<file>:<text>` entries."""
    if not deny:
        return []
    args = ["git", "-C", repo, "grep", "-nIiE"]
    for p in deny:
        args += ["-e", p]
    out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr)
    hits = []
    for line in out.stdout.splitlines():
        file, _, rest = line.partition(":")
        text = rest.partition(":")[2]
        if not any(file == a.partition(":")[0] and a.partition(":")[2] == text.strip() for a in allow):
            hits.append(line)
    return hits


class LeakScan(unittest.TestCase):
    def test_scan_finds_a_denied_word_and_honours_the_allow_list(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        with open(os.path.join(tmp, "a.md"), "w") as f:
            f.write("ok\nSecretProject here\nclone secretproject.git\n")
        subprocess.run(["git", "-C", tmp, "add", "a.md"], check=True)
        self.assertEqual(leaks(tmp, ["secretproject"], []), ["a.md:2:SecretProject here", "a.md:3:clone secretproject.git"])
        self.assertEqual(leaks(tmp, ["secretproject"], ["a.md:clone secretproject.git"]), ["a.md:2:SecretProject here"])
        # an allowed line only covers itself: more text on it (another private name) is still a leak
        self.assertEqual(leaks(tmp, ["secretproject"], ["a.md:clone secretproject", "a.md:SecretProject here"]),
                         ["a.md:3:clone secretproject.git"])

    def test_public_repo_has_no_private_names(self):
        ov = overlay_dir()
        if not ov or not os.path.isfile(os.path.join(ov, "leak-denylist.txt")):
            self.skipTest("no overlay deny list on this machine")
        hits = leaks(REPO, patterns(os.path.join(ov, "leak-denylist.txt")),
                     patterns(os.path.join(ov, "leak-allowlist.txt")))
        self.assertEqual(hits, [], "private names in the public repo:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
