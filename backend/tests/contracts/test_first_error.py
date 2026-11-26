"""contracts.first_error.run_first_error: the run-list rule on its own."""

import unittest

from agent_debugger_api.contracts import run_first_error

A, B, C, D = "a" * 16, "b" * 16, "c" * 16, "d" * 16


def err(span_id, started_at, name="op", error_type=""):
    return (span_id, started_at, name, "tool", error_type)


class RunFirstErrorTests(unittest.TestCase):
    def test_only_a_failed_root_has_a_first_error(self):
        spans, links = [err(B, 5)], [(A, None), (B, A)]
        for status in ("OK", "UNSET", None):
            self.assertIsNone(run_first_error(status, spans, links))
        self.assertEqual(run_first_error("ERROR", spans + [err(A, 0)], links).span_id, B)

    def test_a_conflicted_span_counts_once_at_its_earliest_version(self):
        found = run_first_error("ERROR", [err(A, 0), err(B, 9, "late"), err(B, 3, "early")], [(A, None), (B, A)])
        self.assertEqual((found.span_name, found.originating_error_span_count), ("early", 1))

    def test_every_recorded_parent_of_a_conflicted_span_carries_its_error(self):
        # B's two versions name different parents; both carry B's error.
        found = run_first_error("ERROR", [err(A, 0), err(C, 1), err(B, 5)], [(A, None), (C, A), (B, A), (B, C)])
        self.assertEqual((found.span_id, found.originating_error_span_count), (B, 1))

    def test_a_parent_cycle_ends_the_walk(self):
        found = run_first_error("ERROR", [err(A, 0), err(D, 7)], [(A, None), (B, C), (C, B), (D, B)])
        self.assertEqual(found.span_id, A)  # D's chain never reaches A; both are leaves, A is earlier
        self.assertEqual(found.originating_error_span_count, 2)

    def test_empty_error_type_is_none(self):
        self.assertIsNone(run_first_error("ERROR", [err(A, 0)], [(A, None)]).error_type)
        self.assertEqual(run_first_error("ERROR", [err(A, 0, error_type="E")], [(A, None)]).error_type, "E")


if __name__ == "__main__":
    unittest.main()
