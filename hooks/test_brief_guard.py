"""Tests for brief_guard.py. Run: python -I hooks/test_brief_guard.py"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brief_guard.py")
LINE = "Don't re-read CLAUDE.md."


def run(payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, "-I", HOOK], input=raw, capture_output=True,
                          text=True, encoding="utf-8").returncode


def agent(desc, prompt, **extra):
    return {"tool_name": "Agent", "tool_input": dict(description=desc, prompt=prompt,
                                                     model="sonnet", **extra)}


def bare(desc, **extra):
    """An Agent call with no model: inherits the main thread's Opus."""
    return {"tool_name": "Agent", "tool_input": dict(description=desc, prompt="p", **extra)}


class BriefGuard(unittest.TestCase):
    def test_night_roles_without_line_are_blocked(self):
        for desc in ("Hat spec: xlsx import", "Glove F14", "Glove: wifi fit", "Scout 2",
                     "Tester sweep", "Hand critique round 3", "Leg critique round 1"):
            self.assertEqual(run(agent(desc, "Implement the spec below.")), 2, desc)

    def test_night_role_with_line_passes(self):
        self.assertEqual(run(agent("Hat spec: x", f"Gotchas:\n- a\n{LINE}\nSpec...")), 0)

    def test_curly_apostrophe_passes(self):
        self.assertEqual(run(agent("Glove F2", "Don’t re-read CLAUDE.md.")), 0)

    def test_other_agents_pass(self):
        for desc in ("Merge PR 414 behind full gate", "[review-skill] Spec review #409",
                     "Explore the auth module", "Hatch plan", "Gloves off refactor"):
            self.assertEqual(run(agent(desc, "no line")), 0, desc)

    def test_general_purpose_without_model_is_blocked(self):
        self.assertEqual(run(bare("Pre-flip checklist", subagent_type="general-purpose")), 2)
        self.assertEqual(run(bare("Oracle headroom replay")), 2)

    def test_model_set_or_typed_agent_passes(self):
        self.assertEqual(run(bare("Senior review", subagent_type="general-purpose", model="opus")), 0)
        self.assertEqual(run(bare("Prod lookup", subagent_type="prod-investigator")), 0)
        self.assertEqual(run(bare("Explore the auth module", subagent_type="Explore")), 0)

    def test_other_tools_and_bad_input_pass(self):
        self.assertEqual(run({"tool_name": "Bash", "tool_input": {"command": "ls"}}), 0)
        self.assertEqual(run("not json"), 0)


if __name__ == "__main__":
    unittest.main()
