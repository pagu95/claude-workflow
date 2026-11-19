"""Tests for subagent_guard.py. Run: python -I hooks/test_subagent_guard.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subagent_guard.py")


class SubagentGuard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_hook(self, payload):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        env = dict(os.environ, CLAUDE_SUBAGENT_GUARD_STATE=self.dir.name)
        done = subprocess.run([sys.executable, "-I", HOOK], input=raw, capture_output=True,
                              text=True, encoding="utf-8", env=env)
        return done.returncode, done.stderr

    def shell(self, agent="a1", tool="Bash", **tool_input):
        tool_input.setdefault("command", "npm test")
        event = {"session_id": "s1", "tool_name": tool, "tool_input": tool_input}
        if agent:
            event["agent_id"] = agent
        return event

    def fired(self):
        try:
            with open(os.path.join(self.dir.name, "runs.jsonl"), encoding="utf-8") as f:
                return [json.loads(line)["kind"] for line in f]
        except OSError:
            return []

    # wait cap
    def test_long_foreground_wait_in_a_subagent_is_blocked(self):
        code, err = self.run_hook(self.shell(timeout=590000))
        self.assertEqual(code, 2)
        self.assertIn("270000", err)
        self.assertEqual(self.fired(), ["wait"])

    def test_wait_at_the_cap_passes(self):
        self.assertEqual(self.run_hook(self.shell(timeout=270000))[0], 0)

    def test_no_timeout_passes(self):
        self.assertEqual(self.run_hook(self.shell())[0], 0)

    def test_long_background_call_passes(self):
        self.assertEqual(self.run_hook(self.shell(timeout=590000, run_in_background=True))[0], 0)

    def test_long_wait_on_the_main_thread_passes(self):
        self.assertEqual(self.run_hook(self.shell(agent=None, timeout=590000))[0], 0)

    def test_long_powershell_wait_is_blocked(self):
        self.assertEqual(self.run_hook(self.shell(tool="PowerShell", timeout=600000))[0], 2)

    # call cap
    def test_nudge_blocks_one_call_then_lets_the_repeat_through(self):
        codes = [self.run_hook(self.shell())[0] for _ in range(61)]
        self.assertEqual(codes[:59], [0] * 59)
        self.assertEqual(codes[59], 2)
        self.assertEqual(codes[60], 0)
        self.assertEqual(self.fired(), ["nudge"])

    def test_every_call_over_the_cap_is_blocked(self):
        codes = [self.run_hook(self.shell())[0] for _ in range(123)]
        self.assertEqual(codes[119], 0)
        self.assertEqual(codes[120:], [2, 2, 2])
        self.assertIn("report", self.run_hook(self.shell())[1])

    def test_agents_are_counted_apart(self):
        for _ in range(59):
            self.run_hook(self.shell(agent="a1"))
        self.assertEqual(self.run_hook(self.shell(agent="a2"))[0], 0)
        self.assertEqual(self.run_hook(self.shell(agent="a1"))[0], 2)

    def test_main_thread_is_never_counted(self):
        codes = [self.run_hook(self.shell(agent=None))[0] for _ in range(125)]
        self.assertEqual(set(codes), {0})

    # never break a tool call
    def test_other_tools_and_bad_input_pass(self):
        self.assertEqual(self.run_hook({"agent_id": "a1", "tool_name": "Read",
                                        "tool_input": {"timeout": 590000}})[0], 0)
        self.assertEqual(self.run_hook("not json")[0], 0)
        self.assertEqual(self.run_hook({"agent_id": "a1", "tool_name": "Bash",
                                        "tool_input": {"timeout": "soon"}})[0], 0)


if __name__ == "__main__":
    unittest.main()
