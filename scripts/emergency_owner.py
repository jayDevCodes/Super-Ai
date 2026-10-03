#!/usr/bin/env python3
from __future__ import annotations

import argparse
from getpass import getpass
import shlex
from pathlib import Path

from core.audit import HashChainAuditStore
from core.security import (
    EmergencyAuthority,
    EmergencyCommand,
    EmergencyRequest,
    OwnerAuthorization,
)


def parse_command(line: str) -> EmergencyRequest:
    parts = shlex.split(line)
    if not parts:
        raise ValueError("command is empty")
    command = parts[0].lower()

    if command == "stop-task" and len(parts) == 2:
        return EmergencyRequest(EmergencyCommand.STOP_TASK, task_id=parts[1])
    if command == "resume-task" and len(parts) == 2:
        return EmergencyRequest(EmergencyCommand.RESUME_TASK, task_id=parts[1])
    if command == "disable-autonomy" and len(parts) == 1:
        return EmergencyRequest(EmergencyCommand.DISABLE_AUTONOMY)
    if command == "enable-autonomy" and len(parts) == 1:
        return EmergencyRequest(EmergencyCommand.ENABLE_AUTONOMY)
    if command == "shutdown" and len(parts) == 1:
        return EmergencyRequest(EmergencyCommand.SHUTDOWN)
    if command == "owner-directive" and len(parts) >= 2:
        return EmergencyRequest(
            EmergencyCommand.OWNER_DIRECTIVE,
            directive=" ".join(parts[1:]),
        )
    raise ValueError(
        "commands: stop-task <id> | resume-task <id> | disable-autonomy | "
        "enable-autonomy | shutdown | owner-directive <instruction>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authenticated Super-Ai emergency owner console."
    )
    parser.add_argument(
        "--auth",
        type=Path,
        default=Path(".super-ai/security/owner_auth.json"),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(".super-ai/security/emergency_state.json"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path(".super-ai/security/emergency_audit.jsonl"),
    )
    args = parser.parse_args()

    code = getpass("Emergency owner code: ")
    auth = OwnerAuthorization(args.auth)
    audit = HashChainAuditStore(args.audit)
    authority = EmergencyAuthority(
        auth,
        state_path=args.state,
        audit_store=audit,
    )

    line = input("Emergency command: ").strip()
    request = parse_command(line)
    grant = authority.execute(request, owner_code=code)

    print(f"Emergency command accepted: {request.command.value}")
    print(f"Proof: {grant.proof_id}")
    print(f"State: {authority.state().owner_decision_mode}")
    if request.command is EmergencyCommand.SHUTDOWN:
        print("Shutdown requested. The active Super-Ai supervisor should terminate cleanly at its next control boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
