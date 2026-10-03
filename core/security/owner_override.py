from __future__ import annotations

from dataclasses import dataclass
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from threading import RLock
from typing import Any, Mapping


class OwnerAuthorizationError(RuntimeError):
    """Raised when owner break-glass authentication cannot be completed."""


@dataclass(frozen=True, slots=True)
class OwnerOverrideGrant:
    """Opaque, task-scoped authorization issued after successful verification."""

    grant_id: str
    scope_digest: str
    expires_at: str
    proof_id: str


@dataclass(frozen=True, slots=True)
class OwnerAuthRecord:
    """Serializable verifier record; never contains the owner secret."""

    version: int
    algorithm: str
    salt_b64: str
    digest_b64: str
    scrypt_n: int
    scrypt_r: int
    scrypt_p: int
    created_at: str

    def validate(self) -> None:
        if self.version != 1:
            raise OwnerAuthorizationError("unsupported owner-auth record version")
        if self.algorithm != "scrypt":
            raise OwnerAuthorizationError("owner-auth record must use scrypt")
        for value, name in (
            (self.scrypt_n, "scrypt_n"),
            (self.scrypt_r, "scrypt_r"),
            (self.scrypt_p, "scrypt_p"),
        ):
            if value <= 0:
                raise OwnerAuthorizationError(f"{name} must be > 0")
        try:
            salt = base64.b64decode(self.salt_b64, validate=True)
            digest = base64.b64decode(self.digest_b64, validate=True)
        except ValueError as exc:
            raise OwnerAuthorizationError("owner-auth record contains invalid base64") from exc
        if len(salt) < 16:
            raise OwnerAuthorizationError("owner-auth salt is too short")
        if len(digest) != 32:
            raise OwnerAuthorizationError("owner-auth digest has unexpected length")


class OwnerAuthorization:
    """Local owner-only break-glass verifier.

    The secret is accepted only for verification and is never logged, returned,
    placed in task context, sent to the model, or written to disk. Successful
    verification yields a short-lived one-use grant scoped to one task.
    """

    MIN_SECRET_LENGTH = 15
    DEFAULT_SCRYPT_N = 2**17
    DEFAULT_SCRYPT_R = 8
    DEFAULT_SCRYPT_P = 1
    DEFAULT_MAX_ATTEMPTS = 5
    DEFAULT_GRANT_TTL_SECONDS = 300

    def __init__(
        self,
        path: Path = Path(".super-ai/security/owner_auth.json"),
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        grant_ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        if grant_ttl_seconds <= 0:
            raise ValueError("grant_ttl_seconds must be > 0")
        self.path = Path(path)
        self.max_attempts = max_attempts
        self.grant_ttl_seconds = grant_ttl_seconds
        self._failed_attempts = 0
        self._lock = RLock()
        self._used_grants: set[str] = set()
        self._issued_grants: dict[str, str] = {}

    @property
    def configured(self) -> bool:
        return self.path.is_file()

    def configure(self, secret: str) -> None:
        self._validate_secret(secret)
        salt = secrets.token_bytes(32)
        digest = _derive(secret, salt, self.DEFAULT_SCRYPT_N, self.DEFAULT_SCRYPT_R, self.DEFAULT_SCRYPT_P)
        record = OwnerAuthRecord(
            version=1,
            algorithm="scrypt",
            salt_b64=base64.b64encode(salt).decode("ascii"),
            digest_b64=base64.b64encode(digest).decode("ascii"),
            scrypt_n=self.DEFAULT_SCRYPT_N,
            scrypt_r=self.DEFAULT_SCRYPT_R,
            scrypt_p=self.DEFAULT_SCRYPT_P,
            created_at=_now_iso(),
        )
        self._write_record(record)
        with self._lock:
            self._failed_attempts = 0
            self._used_grants.clear()

    def authenticate(self, secret: str, *, scope_digest: str) -> OwnerOverrideGrant:
        self._validate_secret(secret)
        if not _is_digest(scope_digest):
            raise OwnerAuthorizationError("invalid owner-override scope digest")

        record = self._read_record()
        with self._lock:
            if self._failed_attempts >= self.max_attempts:
                raise OwnerAuthorizationError(
                    "owner break-glass authentication is temporarily locked after failed attempts"
                )

            candidate = _derive(
                secret,
                base64.b64decode(record.salt_b64),
                record.scrypt_n,
                record.scrypt_r,
                record.scrypt_p,
            )
            expected = base64.b64decode(record.digest_b64)
            if not hmac.compare_digest(candidate, expected):
                self._failed_attempts += 1
                raise OwnerAuthorizationError("owner authentication failed")

            self._failed_attempts = 0
            grant_id = secrets.token_urlsafe(24)
            expires = datetime.now(timezone.utc) + timedelta(seconds=self.grant_ttl_seconds)
            proof_material = f"{grant_id}:{scope_digest}:{expires.isoformat()}".encode("utf-8")
            proof_id = hashlib.sha256(proof_material).hexdigest()
            return OwnerOverrideGrant(
                grant_id=grant_id,
                scope_digest=scope_digest,
                expires_at=expires.isoformat(),
                proof_id=proof_id,
            )

    def consume(self, grant: OwnerOverrideGrant, *, scope_digest: str) -> None:
        if not isinstance(grant, OwnerOverrideGrant):
            raise OwnerAuthorizationError("invalid owner override grant")
        if not hmac.compare_digest(grant.scope_digest, scope_digest):
            raise OwnerAuthorizationError("owner override grant is scoped to a different task")
        try:
            expires = datetime.fromisoformat(grant.expires_at)
        except ValueError as exc:
            raise OwnerAuthorizationError("owner override grant has invalid expiry") from exc
        if datetime.now(timezone.utc) >= expires:
            raise OwnerAuthorizationError("owner override grant has expired")

        with self._lock:
            if grant.grant_id in self._used_grants:
                raise OwnerAuthorizationError("owner override grant has already been consumed")
            self._used_grants.add(grant.grant_id)

    def _read_record(self) -> OwnerAuthRecord:
        if not self.path.is_file():
            raise OwnerAuthorizationError(
                f"owner authentication is not configured: {self.path}"
            )
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OwnerAuthorizationError("owner authentication record could not be read") from exc
        if not isinstance(raw, Mapping):
            raise OwnerAuthorizationError("owner authentication record must be an object")
        try:
            record = OwnerAuthRecord(
                version=int(raw["version"]),
                algorithm=str(raw["algorithm"]),
                salt_b64=str(raw["salt_b64"]),
                digest_b64=str(raw["digest_b64"]),
                scrypt_n=int(raw["scrypt_n"]),
                scrypt_r=int(raw["scrypt_r"]),
                scrypt_p=int(raw["scrypt_p"]),
                created_at=str(raw["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OwnerAuthorizationError("owner authentication record is malformed") from exc
        record.validate()
        return record

    def _write_record(self, record: OwnerAuthRecord) -> None:
        record.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": record.version,
            "algorithm": record.algorithm,
            "salt_b64": record.salt_b64,
            "digest_b64": record.digest_b64,
            "scrypt_n": record.scrypt_n,
            "scrypt_r": record.scrypt_r,
            "scrypt_p": record.scrypt_p,
            "created_at": record.created_at,
        }
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "
", encoding="utf-8")
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        temp.replace(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @classmethod
    def scope_for_task(cls, task_id: str, goal: str) -> str:
        if not task_id or not goal or not task_id.strip() or not goal.strip():
            raise ValueError("task scope requires non-empty task_id and goal")
        material = json.dumps(
            {"task_id": task_id, "goal": goal},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @classmethod
    def _validate_secret(cls, secret: str) -> None:
        if not isinstance(secret, str):
            raise TypeError("owner authentication secret must be text")
        if len(secret) < cls.MIN_SECRET_LENGTH:
            raise ValueError(
                f"owner authentication secret must be at least {cls.MIN_SECRET_LENGTH} characters"
            )
        if " " in secret or "" in secret or "
" in secret:
            raise ValueError("owner authentication secret contains forbidden control characters")


def _derive(secret: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    try:
        return hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=256 * 1024 * 1024,
        )
    except (ValueError, MemoryError) as exc:
        raise OwnerAuthorizationError("owner secret derivation failed") from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_digest(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
