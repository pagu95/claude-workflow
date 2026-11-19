"""Tests for context_guard.py. Run: python -I hooks/test_context_guard.py"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "context_guard.py")


def transcript(folder, ctx, minutes_ago):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    rec = {"type": "assistant", "timestamp": when.isoformat().replace("+00:00", "Z"),
           "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": ctx - 10,
                                 "cache_creation_input_tokens": 0}}}
    path = os.path.join(folder, "t.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return path


class ContextGuard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = dict(os.environ, CLAUDE_CONTEXT_GUARD_STATE=os.path.join(self.dir, "state"))

    def run_hook(self, payload):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        p = subprocess.run([sys.executable, "-I", HOOK], input=raw, capture_output=True,
                           text=True, encoding="utf-8", env=self.env)
        return p.returncode, p.stdout

    def runs(self):
        try:
            with open(os.path.join(self.dir, "state", "runs.jsonl"), encoding="utf-8") as f:
                return [json.loads(l) for l in f]
        except OSError:
            return []

    def event(self, ctx, minutes_ago, session="s1"):
        return {"session_id": session, "transcript_path": transcript(self.dir, ctx, minutes_ago)}

    def test_quiet_run_is_logged(self):
        code, out = self.run_hook(self.event(100_000, 1))
        self.assertEqual((code, out), (0, ""))
        [r] = self.runs()
        self.assertEqual((r["session"], r["ctx"], r["fired"]), ("s1", 100_000, None))

    def test_size_warning_once_per_step_and_logged(self):
        _, first = self.run_hook(self.event(300_000, 1))
        _, second = self.run_hook(self.event(310_000, 1))
        self.assertIn("(L8)", first)
        self.assertEqual(second, "")
        self.assertEqual([r["fired"] for r in self.runs()], ["size", None])

    def test_idle_blocks_once_then_lets_the_resend_through(self):
        ev = self.event(300_000, 90)
        _, first = self.run_hook(ev)
        _, second = self.run_hook(ev)
        self.assertEqual(json.loads(first)["decision"], "block")
        self.assertIn("cache has expired", json.loads(first)["reason"])
        self.assertNotIn("decision", json.loads(second))
        self.assertEqual([r["fired"] for r in self.runs()], ["idle-block", "idle"])

    def test_idle_blocks_again_after_a_new_reply_goes_idle(self):
        ev = self.event(300_000, 90)
        self.run_hook(ev)
        self.run_hook(ev)
        _, out = self.run_hook(self.event(300_000, 95))
        self.assertEqual(json.loads(out)["decision"], "block")

    def test_idle_under_the_context_line_passes_quietly(self):
        self.assertEqual(self.run_hook(self.event(150_000, 90)), (0, ""))

    def test_bad_input_and_missing_transcript_exit_zero(self):
        self.assertEqual(self.run_hook("not json"), (0, ""))
        self.assertEqual(self.run_hook({"session_id": "x", "transcript_path": "/nope"}), (0, ""))
        self.assertEqual(self.runs(), [])


if __name__ == "__main__":
    unittest.main()
