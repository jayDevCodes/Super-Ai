from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.ci_failure_repair_queue import parse_failures


class CIFailureRepairQueueTests(unittest.TestCase):
    def test_groups_same_root_exception_and_preserves_order(self):
        log = """
2026-09-22T12:45:17.3591047Z Traceback (most recent call last):
2026-09-22T12:45:17.3602384Z   File "x.py", line 1
2026-09-22T12:45:17.3623500Z NameError: name 'forbidden' is not defined
2026-09-22T12:45:17.3624980Z ======================================================================
2026-09-22T12:45:17.3631171Z ERROR: test_second (unit.test_demo.DemoTests.test_second)
2026-09-22T12:45:17.3640000Z NameError: name 'forbidden' is not defined
2026-09-22T12:45:17.3700000Z FAIL: test_third (unit.test_demo.DemoTests.test_third)
2026-09-22T12:45:17.3710000Z AssertionError: expected value
"""
        queue = parse_failures(log.splitlines())
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["issue_id"], "CI-001")
        self.assertEqual(
            queue[0]["root_cause"],
            "NameError: name 'forbidden' is not defined",
        )
        self.assertEqual(
            queue[0]["tests"],
            [
                "unit.test_demo.DemoTests.test_second",
                "unit.test_demo.DemoTests.test_third",
            ],
        )
        self.assertEqual(queue[1]["issue_id"], "CI-002")

    def test_real_github_timestamp_and_bom_are_normalized(self):
        log = """
﻿2026-09-22T12:56:40.1158639Z ERROR: test_case (unit.test_demo.DemoTests.test_case)
2026-09-22T12:56:40.1160000Z TypeError: bad argument
"""
        queue = parse_failures(log.splitlines())
        self.assertEqual(
            queue,
            [{
                "issue_id": "CI-001",
                "status": "unresolved",
                "root_cause": "TypeError: bad argument",
                "tests": ["unit.test_demo.DemoTests.test_case"],
            }],
        )


if __name__ == "__main__":
    unittest.main()
