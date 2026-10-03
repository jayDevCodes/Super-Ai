from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.security import OwnerAuthorization, OwnerAuthorizationError


class OwnerAuthorizationTests(unittest.TestCase):
    def test_code_is_not_stored_and_valid_code_issues_scoped_grant(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "owner_auth.json"
            auth = OwnerAuthorization(path)
            secret = "a-strong-owner-code-2026!"
            auth.configure(secret)

            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(secret, raw)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

            scope = OwnerAuthorization.scope_for_task("T1", "do the exceptional task")
            grant = auth.authenticate(secret, scope_digest=scope)
            self.assertTrue(grant.proof_id)
            auth.consume(grant, scope_digest=scope)

            with self.assertRaises(OwnerAuthorizationError):
                auth.consume(grant, scope_digest=scope)

    def test_wrong_code_does_not_issue_grant(self) -> None:
        with TemporaryDirectory() as directory:
            auth = OwnerAuthorization(Path(directory) / "owner_auth.json")
            auth.configure("a-strong-owner-code-2026!")
            scope = OwnerAuthorization.scope_for_task("T2", "another exceptional task")
            with self.assertRaises(OwnerAuthorizationError):
                auth.authenticate("incorrect-owner-code", scope_digest=scope)


if __name__ == "__main__":
    unittest.main()
