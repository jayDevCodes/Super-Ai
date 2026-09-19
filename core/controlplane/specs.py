from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from registry.runtime import RuntimeSpec


class RuntimeSpecIssue(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeSpecReview:
    status: str
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    fingerprint: str
    normalized: dict[str, object]

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


_IMAGE_DIGEST_RE = re.compile(r"@sha256:[0-9a-fA-F]{64}$")
_SAFE_PATH_RE = re.compile(r"^/[^\x00\r\n]*$")


class RuntimeSpecGuardian:
    """Fail-closed review layer kept additive to the existing RuntimeSpec contract."""

    def __init__(
        self,
        *,
        require_image_digest: bool = True,
        max_argv: int = 32,
        max_token_bytes: int = 1024,
        allowed_workdirs: tuple[str, ...] = ("/workspace", "/tmp"),
        max_timeout_seconds: float = 3600.0,
    ) -> None:
        self.require_image_digest = require_image_digest
        self.max_argv = max_argv
        self.max_token_bytes = max_token_bytes
        self.allowed_workdirs = allowed_workdirs
        self.max_timeout_seconds = max_timeout_seconds

    def review(self, spec: RuntimeSpec) -> RuntimeSpecReview:
        issues: list[str] = []
        warnings: list[str] = []
        try:
            spec.validate()
        except ValueError as exc:
            issues.append(str(exc))

        image = spec.image
        if self.require_image_digest:
            if spec.expected_image_digest is None:
                issues.append("immutable image digest is required")
            elif not _IMAGE_DIGEST_RE.search(image) and spec.expected_image_digest:
                warnings.append("image tag/name is paired with an explicit expected digest")

        if len(spec.command) > self.max_argv:
            issues.append("command exceeds argv limit")
        for index, token in enumerate(spec.command):
            if len(token.encode("utf-8")) > self.max_token_bytes:
                issues.append(f"command[{index}] exceeds token byte limit")

        if not _SAFE_PATH_RE.fullmatch(spec.working_directory):
            issues.append("working_directory contains unsafe control characters")
        elif not any(
            spec.working_directory == root or spec.working_directory.startswith(root + "/")
            for root in self.allowed_workdirs
        ):
            issues.append("working_directory is outside allowed roots")

        if spec.timeout_seconds > self.max_timeout_seconds:
            issues.append("timeout exceeds guardian ceiling")

        normalized = self._normalized(spec)
        fingerprint = self.fingerprint(normalized)
        return RuntimeSpecReview(
            status="rejected" if issues else "accepted",
            issues=tuple(sorted(set(issues))),
            warnings=tuple(sorted(set(warnings))),
            fingerprint=fingerprint,
            normalized=normalized,
        )

    @staticmethod
    def _normalized(spec: RuntimeSpec) -> dict[str, object]:
        contract = spec.output_contract
        return {
            "image": spec.image.strip(),
            "command": list(spec.command),
            "timeout_seconds": float(spec.timeout_seconds),
            "expected_image_digest": spec.expected_image_digest,
            "working_directory": spec.working_directory,
            "output_contract": {
                "required": list(getattr(contract, "required", ())),
                "max_files": getattr(contract, "max_files", None),
                "max_total_bytes": getattr(contract, "max_total_bytes", None),
            },
        }

    @staticmethod
    def fingerprint(normalized: dict[str, object]) -> str:
        payload = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def explain(self, spec: RuntimeSpec) -> tuple[str, ...]:
        review = self.review(spec)
        if review.accepted:
            return ("runtime spec accepted", *review.warnings)
        return review.issues

    def review_many(self, specs: Iterable[RuntimeSpec]) -> tuple[RuntimeSpecReview, ...]:
        return tuple(self.review(spec) for spec in specs)
