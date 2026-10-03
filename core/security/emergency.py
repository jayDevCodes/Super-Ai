from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from threading import RLock
from typing import Mapping

from .owner_override import OwnerAuthorization, OwnerAuthorizationError, OwnerOverrideGrant
from core.audit import HashChainAuditStore


class EmergencyCommand(str, Enum):
    STOP_TASK = "stop_task"
    DISABLE_AUTONOMY = "disable_autonomy"
    ENABLE_AUTONOMY = "enable_autonomy"
    SHUTDOWN = "shutdown"
    OWNER_DIRECTIVE = "owner_directive"
    RESUME_TASK = "resume_task"


@dataclass(frozen=True, slots=True)
class EmergencyRequest:
    command: EmergencyCommand
    task_id: str | None = None
    directive: str | None = None

    def validate(self) -> None:
        if self.command in {EmergencyCommand.STOP_TASK, EmergencyCommand.RESUME_TASK}:
            if not self.task_id or not self.task_id.strip():
                raise ValueError(f"{self.command.value} requires task_id")
            if self.directive is not None:
                raise ValueError(f"{self.command.value} does not accept directive")
        elif self.command is EmergencyCommand.OWNER_DIRECTIVE:
            if self.task_id is not None:
                raise ValueError("owner_directive does not accept task_id")
            if not self.directive or not self.directive.strip():
                raise ValueError("owner_directive requires directive")
            if len(self.directive) > 4096:
                raise ValueError("owner directive is too long")
        elif self.task_id is not None or self.directive is not None:
            raise ValueError(f"{self.command.value} does not accept task_id/directive")


@dataclass(frozen=True, slots=True)
class EmergencyState:
    autonomy_enabled: bool = True
    shutdown_requested: bool = False
    stopped_tasks: tuple[str, ...] = ()
    owner_directive: str = ""
    owner_decision_mode: str = "ai"
    last_proof_id: str = ""

    def validate(self) -> None:
        if any(not task_id or not task_id.strip() for task_id in self.stopped_tasks):
            raise ValueError("stopped task ids must be non-empty")
        if len(self.owner_directive) > 4096:
            raise ValueError("owner directive is too long")
        if self.owner_decision_mode not in {"ai", "owner"}:
            raise ValueError("owner_decision_mode must be ai or owner")
        if len(self.last_proof_id) > 128:
            raise ValueError("proof id is too long")


class EmergencyAuthorityError(RuntimeError):
    """Raised when an authenticated emergency command cannot be applied."""


class EmergencyAuthority:
    """Authenticated owner emergency control plane.

    Owner commands are deliberately explicit. The emergency channel can stop,
    disable, enable, or request shutdown, and can store an owner directive for
    the Brain to surface to a decision boundary. It does not expose arbitrary
    shell/code execution.
    """

    def __init__(
        self,
        owner_authorization: OwnerAuthorization,
        state_path: Path = Path(".super-ai/security/emergency_state.json"),
        audit_store: HashChainAuditStore | None = None,
    ) -> None:
        if not isinstance(owner_authorization, OwnerAuthorization):
            raise TypeError("owner_authorization must be an OwnerAuthorization")
        self._auth = owner_authorization
        self._state_path = Path(state_path)
        self._audit = audit_store
        self._lock = RLock()

    @property
    def state_path(self) -> Path:
        return self._state_path

    def state(self) -> EmergencyState:
        with self._lock:
            if not self._state_path.is_file():
                return EmergencyState()
            try:
                raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EmergencyAuthorityError("emergency state could not be read") from exc
            if not isinstance(raw, Mapping):
                raise EmergencyAuthorityError("emergency state must be an object")
            state = EmergencyState(
                autonomy_enabled=bool(raw.get("autonomy_enabled", True)),
                shutdown_requested=bool(raw.get("shutdown_requested", False)),
                stopped_tasks=tuple(
                    str(item) for item in raw.get("stopped_tasks", [])
                ),
                owner_directive=str(raw.get("owner_directive", "")),
                owner_decision_mode=str(raw.get("owner_decision_mode", "ai")),
                last_proof_id=str(raw.get("last_proof_id", "")),
            )
            try:
                state.validate()
            except ValueError as exc:
                raise EmergencyAuthorityError("emergency state is invalid") from exc
            return state

    def execute(
        self,
        request: EmergencyRequest,
        *,
        owner_code: str,
    ) -> OwnerOverrideGrant:
        request.validate()
        scope = self.scope_for_request(request)
        try:
            grant = self._auth.authenticate(owner_code, scope_digest=scope)
            self._auth.consume(grant, scope_digest=scope)
        except (OwnerAuthorizationError, ValueError, TypeError) as exc:
            raise EmergencyAuthorityError("owner emergency authentication failed") from exc

        with self._lock:
            current = self.state()
            if request.command is EmergencyCommand.STOP_TASK:
                tasks = tuple(sorted(set((*current.stopped_tasks, request.task_id or ""))))
                next_state = EmergencyState(
                    autonomy_enabled=current.autonomy_enabled,
                    shutdown_requested=current.shutdown_requested,
                    stopped_tasks=tasks,
                    owner_directive=current.owner_directive,
                    owner_decision_mode=current.owner_decision_mode,
                    last_proof_id=grant.proof_id,
                )
            elif request.command is EmergencyCommand.DISABLE_AUTONOMY:
                next_state = EmergencyState(
                    autonomy_enabled=False,
                    shutdown_requested=current.shutdown_requested,
                    stopped_tasks=current.stopped_tasks,
                    owner_directive=current.owner_directive,
                    owner_decision_mode="owner",
                    last_proof_id=grant.proof_id,
                )
            elif request.command is EmergencyCommand.ENABLE_AUTONOMY:
                next_state = EmergencyState(
                    autonomy_enabled=True,
                    shutdown_requested=False,
                    stopped_tasks=current.stopped_tasks,
                    owner_directive="",
                    owner_decision_mode="ai",
                    last_proof_id=grant.proof_id,
                )
            elif request.command is EmergencyCommand.SHUTDOWN:
                next_state = EmergencyState(
                    autonomy_enabled=False,
                    shutdown_requested=True,
                    stopped_tasks=current.stopped_tasks,
                    owner_directive="",
                    owner_decision_mode="owner",
                    last_proof_id=grant.proof_id,
                )
            elif request.command is EmergencyCommand.OWNER_DIRECTIVE:
                next_state = EmergencyState(
                    autonomy_enabled=False,
                    shutdown_requested=current.shutdown_requested,
                    stopped_tasks=current.stopped_tasks,
                    owner_directive=request.directive or "",
                    owner_decision_mode="owner",
                    last_proof_id=grant.proof_id,
                )
            elif request.command is EmergencyCommand.RESUME_TASK:
                stopped = tuple(
                    value for value in current.stopped_tasks
                    if value != (request.task_id or "")
                )
                next_state = EmergencyState(
                    autonomy_enabled=current.autonomy_enabled,
                    shutdown_requested=current.shutdown_requested,
                    stopped_tasks=stopped,
                    owner_directive=current.owner_directive,
                    owner_decision_mode=current.owner_decision_mode,
                    last_proof_id=grant.proof_id,
                )
            else:
                raise EmergencyAuthorityError("unsupported emergency command")

            self._write_state(next_state)
            if self._audit is not None:
                import hashlib
                directive_digest = hashlib.sha256(
                    (request.directive or "").encode("utf-8")
                ).hexdigest()
                self._audit.append(
                    "owner.emergency_command",
                    {
                        "command": request.command.value,
                        "task_id": request.task_id or "",
                        "directive_sha256": directive_digest,
                        "scope_digest": scope,
                        "proof_id": grant.proof_id,
                    },
                )
        return grant

    def task_allowed(self, task_id: str) -> bool:
        state = self.state()
        return (
            state.autonomy_enabled
            and not state.shutdown_requested
            and state.owner_decision_mode == "ai"
            and task_id not in set(state.stopped_tasks)
        )

    def assert_task_allowed(self, task_id: str) -> None:
        if not self.task_allowed(task_id):
            raise EmergencyAuthorityError(
                f"task {task_id!r} is blocked by owner emergency state"
            )

    def request_shutdown(self) -> bool:
        return self.state().shutdown_requested

    def clear_stopped_task(self, task_id: str, *, owner_code: str) -> OwnerOverrideGrant:
        if not task_id or not task_id.strip():
            raise ValueError("task_id must be non-empty")
        current = self.state()
        if task_id not in current.stopped_tasks:
            raise EmergencyAuthorityError("task is not currently stopped")
        request = EmergencyRequest(
            command=EmergencyCommand.RESUME_TASK,
            task_id=task_id,
        )
        grant = self.execute(request, owner_code=owner_code)
        next_state = EmergencyState(
            autonomy_enabled=current.autonomy_enabled,
            shutdown_requested=current.shutdown_requested,
            stopped_tasks=tuple(
                value for value in current.stopped_tasks if value != task_id
            ),
            owner_directive="",
            last_proof_id=grant.proof_id,
        )
        with self._lock:
            self._write_state(next_state)
        return grant

    @staticmethod
    def scope_for_request(request: EmergencyRequest) -> str:
        request.validate()
        material = json.dumps(
            {
                "command": request.command.value,
                "task_id": request.task_id,
                "directive": request.directive,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        import hashlib
        return hashlib.sha256(material).hexdigest()

    def _write_state(self, state: EmergencyState) -> None:
        state.validate()
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "autonomy_enabled": state.autonomy_enabled,
            "shutdown_requested": state.shutdown_requested,
            "stopped_tasks": list(state.stopped_tasks),
            "owner_directive": state.owner_directive,
            "owner_decision_mode": state.owner_decision_mode,
            "last_proof_id": state.last_proof_id,
        }
        temp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        temp.replace(self._state_path)
