from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


class OutputContractError(ValueError):
    """Raised when an output contract is malformed."""


@dataclass(frozen=True, slots=True)
class OutputInspection:
    """Bounded evidence produced by validating a workspace output tree."""

    passed: bool
    file_count: int
    total_bytes: int
    missing_required: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OutputContract:
    """Immutable limits and required artifacts for one execution output."""

    required_files: tuple[str, ...] = ()
    max_files: int = 256
    max_total_bytes: int = 64 * 1024 * 1024
    max_single_file_bytes: int = 16 * 1024 * 1024
    allow_symlinks: bool = False

    def validate(self) -> None:
        if self.max_files <= 0:
            raise OutputContractError("max_files must be > 0")
        if self.max_total_bytes <= 0:
            raise OutputContractError("max_total_bytes must be > 0")
        if self.max_single_file_bytes <= 0:
            raise OutputContractError("max_single_file_bytes must be > 0")
        if self.max_single_file_bytes > self.max_total_bytes:
            raise OutputContractError(
                "max_single_file_bytes must be <= max_total_bytes"
            )
        if self.allow_symlinks:
            raise OutputContractError(
                "output symlinks are not permitted at the runtime boundary"
            )

        normalized: list[str] = []
        for path in self.required_files:
            if not isinstance(path, str) or not path or len(path) > 512:
                raise OutputContractError(
                    "required_files must contain bounded non-empty paths"
                )
            if (
                path.startswith(("/", "\\"))
                or "\x00" in path
                or "\r" in path
                or "\n" in path
            ):
                raise OutputContractError(
                    "required output paths must be relative and free of control characters"
                )
            portable = path.replace("\\", "/")
            parts = portable.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                raise OutputContractError(
                    "required output paths must not contain empty, '.', or '..' segments"
                )
            normalized.append(portable)

        if len(set(normalized)) != len(normalized):
            raise OutputContractError("required_files must not contain duplicates")

    def inspect(self, output_root: Path) -> OutputInspection:
        """Validate a completed output directory without following symlinks."""
        self.validate()
        root = Path(output_root).expanduser()
        if root.exists() and root.is_symlink():
            return OutputInspection(
                False,
                0,
                0,
                tuple(self.required_files),
                ("output root is a symlink",),
            )
        root = root.resolve()
        if not root.exists() or not root.is_dir():
            return OutputInspection(
                False,
                0,
                0,
                tuple(self.required_files),
                ("output root is not a directory",),
            )

        required = {path.replace("\\", "/") for path in self.required_files}
        seen_required: set[str] = set()
        violations: list[str] = []
        file_count = 0
        total_bytes = 0

        for current_root, dirnames, filenames in os.walk(
            root,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_root)

            for dirname in list(dirnames):
                path = current / dirname
                if path.is_symlink():
                    violations.append("symlink directory is not permitted")
                    dirnames.remove(dirname)

            for filename in filenames:
                path = current / filename
                try:
                    relative = path.relative_to(root).as_posix()
                    if path.is_symlink():
                        violations.append(f"symlink file is not permitted: {relative}")
                        continue
                    if not path.is_file():
                        violations.append(f"non-regular output entry: {relative}")
                        continue
                    size = path.stat().st_size
                except OSError:
                    violations.append("output entry could not be inspected safely")
                    continue

                if size > self.max_single_file_bytes:
                    violations.append(
                        f"output file exceeds per-file limit: {relative}"
                    )
                file_count += 1
                total_bytes += size
                if relative in required:
                    seen_required.add(relative)

                if file_count > self.max_files:
                    violations.append("output file count exceeds contract")
                    break
                if total_bytes > self.max_total_bytes:
                    violations.append("output total size exceeds contract")
                    break

            if file_count > self.max_files or total_bytes > self.max_total_bytes:
                break

        missing = tuple(sorted(required - seen_required))
        if missing:
            violations.append("required output files are missing")

        return OutputInspection(
            passed=not violations,
            file_count=file_count,
            total_bytes=total_bytes,
            missing_required=missing,
            violations=tuple(violations),
        )
