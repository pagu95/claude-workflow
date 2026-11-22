"""ckore-retro's TDD metrics: red-first rate and weakened tests, read from transcripts.

Run: python -I -m unittest discover tests
"""
import importlib.util
import json
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("analyze", os.path.join(REPO, "skills/ckore-retro/analyze.py"))
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


class Transcript:
    """Builds a minimal main transcript: one assistant call per tool use, then its result."""

    def __init__(self):
        self.lines, self.n = [], 0

    def tool(self, name, inp, result="ok", is_error=False):
        self.n += 1
        tid = f"t{self.n}"
        self.lines.append({"type": "assistant", "requestId": f"r{self.n}",
                           "timestamp": f"2026-11-20T10:00:{self.n:02d}Z",
                           "message": {"model": "claude-opus-5-5", "usage": {"input_tokens": 1, "output_tokens": 1},
                                       "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        self.lines.append({"type": "user", "timestamp": f"2026-11-20T10:00:{self.n:02d}Z",
                           "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                                    "content": result, "is_error": is_error}]}})
        return self

    def edit(self, path, old="a", new="b"):
        return self.tool("Edit", {"file_path": path, "old_string": old, "new_string": new})

    def test(self, failed):
        return self.tool("Bash", {"command": "python -m pytest tests/test_x.py"},
                         "1 failed" if failed else "1 passed", is_error=failed)

    def save(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x) for x in self.lines) + "\n")
        return path

    def metrics(self):
        threads = analyze.load_session(self.save(), None, True, analyze.new_stats())
        return analyze.tdd_metrics(threads)


class RedFirst(unittest.TestCase):
    def test_source_edited_after_a_failing_new_test_is_red_first(self):
        m = Transcript().edit("tests/test_x.py").test(failed=True).edit("src/x.py").test(failed=False).metrics()
        self.assertEqual((m["red_first"], m["source_files"]), (1, 1))

    def test_source_edited_before_any_test_is_not_red_first(self):
        m = Transcript().edit("src/x.py").edit("tests/test_x.py").test(failed=False).metrics()
        self.assertEqual((m["red_first"], m["source_files"]), (0, 1))

    def test_a_test_file_that_never_ran_red_does_not_count(self):
        m = Transcript().edit("tests/test_x.py").edit("src/x.py").metrics()
        self.assertEqual((m["red_first"], m["source_files"]), (0, 1))

    def test_a_passing_run_ends_the_red_so_the_next_file_needs_a_new_one(self):
        m = (Transcript().edit("tests/test_x.py").test(failed=True).edit("src/x.py").test(failed=False)
             .edit("src/y.py").metrics())
        self.assertEqual((m["red_first"], m["source_files"]), (1, 2))

    def test_docs_and_config_are_not_source_files(self):
        m = Transcript().edit("README.md").edit("package.json").metrics()
        self.assertEqual(m["source_files"], 0)

    def test_node_test_runner_failure_is_red(self):
        m = (Transcript().edit("test/x.test.js")
             .tool("Bash", {"command": "node --test test/x.test.js"}, "✖ adds two\nℹ pass 3\nℹ fail 1")
             .edit("src/x.js").metrics())
        self.assertEqual(m["red_first"], 1)

    def test_angular_test_runner_failure_is_red(self):
        m = (Transcript().edit("src/app/x.component.spec.ts")
             .tool("Bash", {"command": "npx ng test --watch=false"}, "Executed 4 of 4 (1 FAILED)")
             .edit("src/app/x.component.ts").metrics())
        self.assertEqual(m["red_first"], 1)

    def test_node_test_runner_with_zero_failures_is_not_red(self):
        m = (Transcript().edit("test/x.test.js")
             .tool("Bash", {"command": "node --test"}, "✔ adds two\nℹ pass 4\nℹ fail 0")
             .edit("src/x.js").metrics())
        self.assertEqual(m["red_first"], 0)

    def test_a_passing_cargo_run_is_not_red(self):
        m = (Transcript().edit("tests/x_test.rs")
             .tool("Bash", {"command": "cargo test"}, "test result: ok. 5 passed; 0 failed; 0 ignored")
             .edit("src/x.rs").metrics())
        self.assertEqual(m["red_first"], 0)

    def test_a_failing_run_in_powershell_is_red(self):
        m = (Transcript().edit("tests/test_x.py")
             .tool("PowerShell", {"command": "python -m pytest tests"}, "1 failed", is_error=True)
             .edit("src/x.py").metrics())
        self.assertEqual(m["red_first"], 1)

    def test_a_command_that_only_mentions_a_runner_does_not_end_the_red(self):
        m = (Transcript().edit("tests/test_x.py").test(failed=True)
             .tool("Bash", {"command": "pip install pytest"}).edit("src/x.py").metrics())
        self.assertEqual(m["red_first"], 1)

    def test_fixing_the_test_after_it_ran_red_keeps_the_red(self):
        m = Transcript().edit("tests/test_x.py").test(failed=True).edit("tests/test_x.py").edit("src/x.py").metrics()
        self.assertEqual(m["red_first"], 1)

    def test_counts_are_also_split_per_thread(self):
        m = Transcript().edit("tests/test_x.py").test(failed=True).edit("src/x.py").edit("src/y.py").metrics()
        self.assertEqual(m["threads"], {"main": (2, 2)})

    def test_a_failure_without_a_test_edit_first_is_not_red(self):
        m = Transcript().test(failed=True).edit("src/x.py").metrics()
        self.assertEqual(m["red_first"], 0)


class Weakened(unittest.TestCase):
    def test_adding_only_to_a_test_counts(self):
        m = Transcript().edit("src/x.test.ts", "it('a', f)", "it.only('a', f)").metrics()
        self.assertEqual(m["weakened"], 1)

    def test_adding_pytest_skip_counts(self):
        m = Transcript().edit("tests/test_x.py", "def test_a():", "@pytest.mark.skip\ndef test_a():").metrics()
        self.assertEqual(m["weakened"], 1)

    def test_removing_every_assertion_in_an_edit_counts(self):
        m = Transcript().edit("tests/test_x.py", "assert a == 1\nassert b == 2", "pass").metrics()
        self.assertEqual(m["weakened"], 1)

    def test_merging_two_assertions_into_one_does_not_count(self):
        m = Transcript().edit("tests/test_x.py", "assert a == 1\nassert b == 2",
                              "self.assertEqual((a, b), (1, 2))").metrics()
        self.assertEqual(m["weakened"], 0)

    def test_cleanup_commands_that_are_not_test_deletions_do_not_count(self):
        for cmd in ("docker run --rm -v x:/app img pytest tests/test_x.py",
                    "rm -f out.log\npytest tests/test_x.py",
                    "rm -rf tests/__pycache__",
                    "git rm --cached tests/test_x.py"):
            with self.subTest(cmd=cmd):
                self.assertEqual(Transcript().tool("Bash", {"command": cmd}).metrics()["weakened"], 0)

    def test_removing_a_test_written_by_absolute_path_does_not_count(self):
        m = (Transcript().tool("Write", {"file_path": "C:\\work\\app\\test\\x.test.js", "content": "it('a')"})
             .tool("Bash", {"command": "rm test/x.test.js"}).metrics())
        self.assertEqual(m["weakened"], 0)

    def test_deleting_a_test_file_counts(self):
        m = Transcript().tool("Bash", {"command": "git rm tests/test_x.py"}).metrics()
        self.assertEqual(m["weakened"], 1)

    def test_removing_a_test_copied_in_for_a_check_does_not_count(self):
        # A reviewer runs a new test against the old code, then removes the temporary copy.
        m = Transcript().tool("Bash", {"command": "cp /tmp/x.test.js test/x.test.js && node --test test/x.test.js; "
                                                  "rm test/x.test.js"}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_removing_a_test_redirected_into_place_does_not_count(self):
        m = Transcript().tool("Bash", {"command": "git show feat:test/x.test.js > test/x.test.js && node --test; "
                                                  "rm test/x.test.js"}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_removing_a_test_checked_out_from_another_branch_does_not_count(self):
        # The night Hat's fake-green check: the PR's new test on the base branch, removed after the run.
        t = Transcript().tool("Bash", {"command": "git checkout origin/night/x -- tests/unit/x.test.ts"})
        m = t.tool("Bash", {"command": "npx jest tests/unit/x.test.ts; rm tests/unit/x.test.ts"}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_a_checkout_through_a_quoted_worktree_path_is_a_copy_too(self):
        t = Transcript().tool("Bash", {"command": 'git -C "C:/a b/wt" checkout origin/night/x -- tests/unit/x.test.ts'})
        m = t.tool("Bash", {"command": 'rm "C:/a b/wt/tests/unit/x.test.ts"'}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_a_checkout_without_a_ref_discards_changes_so_a_later_removal_counts(self):
        t = Transcript().tool("Bash", {"command": "git checkout -- tests/unit/x.test.ts"})
        m = t.tool("Bash", {"command": "rm tests/unit/x.test.ts"}).metrics()
        self.assertEqual(m["weakened"], 1)

    def test_removing_a_scratch_test_by_a_quoted_path_with_a_space_does_not_count(self):
        t = Transcript().tool("Write", {"file_path": "C:\\a b\\wt\\tests\\unit\\zzScratch.test.ts", "content": "x"})
        m = t.tool("Bash", {"command": 'rm "C:/a b/wt/tests/unit/zzScratch.test.ts"'}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_a_scratch_test_redirected_to_a_quoted_path_with_a_space_is_a_copy(self):
        t = Transcript().tool("Bash", {"command": 'sed -e s/a/b/ src/x.ts > "C:/a b/wt/tests/unit/zzScratch.test.ts"'})
        m = t.tool("Bash", {"command": 'rm "C:/a b/wt/tests/unit/zzScratch.test.ts"'}).metrics()
        self.assertEqual(m["weakened"], 0)

    def test_deleting_a_tracked_test_by_a_quoted_path_with_a_space_counts_once(self):
        m = Transcript().tool("Bash", {"command": 'rm "C:/a b/wt/tests/unit/x.test.ts"'}).metrics()
        self.assertEqual(m["weakened"], 1)

    def test_removing_a_test_copied_into_its_directory_does_not_count(self):
        m = (Transcript().tool("Bash", {"command": 'cp "/tmp/a b/x.test.js" test/'})
             .tool("Bash", {"command": "rm test/x.test.js"}).metrics())
        self.assertEqual(m["weakened"], 0)

    def test_removing_a_test_written_earlier_in_the_thread_does_not_count(self):
        m = (Transcript().tool("Write", {"file_path": "test/x.test.js", "content": "it('a')"})
             .tool("Bash", {"command": "rm test/x.test.js"}).metrics())
        self.assertEqual(m["weakened"], 0)

    def test_adding_an_assertion_does_not_count(self):
        m = Transcript().edit("tests/test_x.py", "assert a == 1", "assert a == 1\nassert b == 2").metrics()
        self.assertEqual(m["weakened"], 0)

    def test_skip_in_source_code_does_not_count(self):
        m = Transcript().edit("src/x.py", "x", "skip(x)").metrics()
        self.assertEqual(m["weakened"], 0)


class TrendRow(unittest.TestCase):
    P, _ = analyze.load_prices(os.path.join(REPO, "skills/ckore-retro/prices.json"))

    def test_session_summary_carries_red_first_and_weakened(self):
        path = (Transcript().edit("tests/test_x.py").test(failed=True).edit("src/x.py")
                .edit("src/y.py", "it('a')", "it.only('a')").save())
        r = analyze.summarize(path, self.P)
        self.assertEqual((r["red_first"], r["source_files"], r["weakened"]), (2, 2, 0))

    def test_red_first_cell_is_a_dash_without_source_edits(self):
        self.assertEqual(analyze.red_cell(dict(red_first=0, source_files=0)), "–")
        self.assertEqual(analyze.red_cell(dict(red_first=1, source_files=4)), "25% (1/4)")

    def test_pattern_rows_fire_on_low_red_first_and_any_weakened(self):
        rules = {label: test for label, test, _ in analyze.TREND_RULES}
        base = dict(sub_share=0, avg_ctx=0, solo=0, total=1, cold=0, bash=0, compacts=0)
        self.assertTrue(rules["red-first < 50%"](dict(base, red_first=1, source_files=3, weakened=0)))
        self.assertFalse(rules["red-first < 50%"](dict(base, red_first=0, source_files=0, weakened=0)))
        self.assertTrue(rules["tests weakened"](dict(base, red_first=0, source_files=0, weakened=1)))


class SmellLog(unittest.TestCase):
    NOW = analyze.ts("2026-11-20T12:00:00Z")

    def log(self, *lines):
        path = os.path.join(tempfile.mkdtemp(), "smells.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(x if isinstance(x, str) else json.dumps(x) for x in lines) + "\n")
        return path

    def row(self, smell, branch, date="2026-11-18", kind="judgement"):
        return dict(date=date, repo="shop-web", branch=branch, smell=smell, kind=kind)

    def test_counts_per_smell_and_flags_two_or_more_branches(self):
        path = self.log(self.row("duplicated-logic", "a"), self.row("duplicated-logic", "b"),
                        self.row("mysterious-name", "a"), self.row("mysterious-name", "a"))
        rows, bad = analyze.smell_summary(path, 30, self.NOW)
        self.assertEqual(rows, [("duplicated-logic", 2, 2, True), ("mysterious-name", 2, 1, False)])
        self.assertEqual(bad, 0)

    def test_skips_old_and_malformed_lines_and_counts_the_bad_ones(self):
        path = self.log(self.row("duplicated-logic", "a", date="2026-09-01"), "{not json",
                        self.row("mysterious-name", "a"))
        rows, bad = analyze.smell_summary(path, 30, self.NOW)
        self.assertEqual(rows, [("mysterious-name", 1, 1, False)])
        self.assertEqual(bad, 1)

    def test_missing_log_is_none(self):
        self.assertIsNone(analyze.smell_summary(os.path.join(tempfile.mkdtemp(), "nope.jsonl"), 30, self.NOW))


if __name__ == "__main__":
    unittest.main()
