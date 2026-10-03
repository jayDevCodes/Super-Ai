from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.audit import HashChainAuditStore
from core.security import (
    EmergencyAuthority,
    EmergencyCommand,
    EmergencyRequest,
    OwnerAuthorization,
)


class EmergencyAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        self.auth = OwnerAuthorization(root / "owner_auth.json")
        self.secret = "strong-emergency-owner-code!"
        self.auth.configure(self.secret)
        self.audit = HashChainAuditStore(root / "audit.jsonl")
        self.authority = EmergencyAuthority(
            self.auth,
            state_path=root / "emergency_state.json",
            audit_store=self.audit,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_shutdown_is_authenticated_and_persisted(self):
        grant = self.authority.execute(
            EmergencyRequest(EmergencyCommand.SHUTDOWN),
            owner_code=self.secret,
        )
        state = self.authority.state()
        self.assertTrue(state.shutdown_requested)
        self.assertFalse(state.autonomy_enabled)
        self.assertEqual(state.owner_decision_mode, "owner")
        self.assertEqual(state.last_proof_id, grant.proof_id)
        self.assertTrue(self.audit.verify())
        self.assertEqual(
            self.audit.read_all()[-1].event_name,
            "owner.emergency_command",
        )

    def test_disable_autonomy_blocks_tasks(self):
        self.authority.execute(
            EmergencyRequest(EmergencyCommand.DISABLE_AUTONOMY),
            owner_code=self.secret,
        )
        self.assertFalse(self.authority.task_allowed("task-1"))

    def test_stop_and_resume_specific_task(self):
        self.authority.execute(
            EmergencyRequest(EmergencyCommand.STOP_TASK, task_id="task-1"),
            owner_code=self.secret,
        )
        self.assertFalse(self.authority.task_allowed("task-1"))

        self.authority.execute(
            EmergencyRequest(EmergencyCommand.RESUME_TASK, task_id="task-1"),
            owner_code=self.secret,
        )
        state = self.authority.state()
        self.assertNotIn("task-1", state.stopped_tasks)

    def test_owner_directive_disables_ai_decision_mode(self):
        self.authority.execute(
            EmergencyRequest(
                EmergencyCommand.OWNER_DIRECTIVE,
                directive="Owner will decide the next action",
            ),
            owner_code=self.secret,
        )
        state = self.authority.state()
        self.assertEqual(state.owner_decision_mode, "owner")
        self.assertFalse(state.autonomy_enabled)
        self.assertEqual(
            state.owner_directive,
            "Owner will decide the next action",
        )

    def test_wrong_code_is_rejected(self):
        with self.assertRaises(Exception):
            self.authority.execute(
                EmergencyRequest(EmergencyCommand.SHUTDOWN),
                owner_code="not-the-owner-code",
            )


if __name__ == "__main__":
    unittest.main()
