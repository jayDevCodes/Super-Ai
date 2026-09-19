from __future__ import annotations

import json
import unittest

from core.runtime.ownership import (
    OwnershipError,
    OwnershipClaim,
    new_ownership_claim,
    verify_container_ownership,
)


class OwnershipTests(unittest.TestCase):
    def test_new_claim_has_unique_id_and_safe_container_id(self):
        first = new_ownership_claim()
        second = new_ownership_claim()

        self.assertNotEqual(first.execution_id, second.execution_id)
        self.assertTrue(first.container_id.startswith("super-ai-"))
        self.assertEqual(first.labels["com.super-ai.execution"], first.execution_id)

    def test_matching_inspect_payload_is_accepted(self):
        claim = OwnershipClaim(
            execution_id="a" * 32,
            container_id="super-ai-" + ("a" * 24),
        )
        payload = [
            {
                "configuration": {
                    "id": claim.container_id,
                    "labels": dict(claim.labels),
                }
            }
        ]

        verify_container_ownership(json.dumps(payload), claim)

    def test_missing_or_mismatched_label_fails_closed(self):
        claim = OwnershipClaim(
            execution_id="a" * 32,
            container_id="super-ai-" + ("a" * 24),
        )
        payload = [
            {
                "configuration": {
                    "id": claim.container_id,
                    "labels": {
                        "com.super-ai.owner": "super-ai",
                        "com.super-ai.execution": "b" * 32,
                    },
                }
            }
        ]

        with self.assertRaises(OwnershipError):
            verify_container_ownership(payload, claim)


if __name__ == "__main__":
    unittest.main()
