from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceContractError(ValueError):
    """Raised when a workspace violates the runtime filesystem boundary."""


@dataclass(frozen=True, slots=True)
class WorkspaceContract:
    """Immutable filesystem boundary for one disposable capability execution.

    root is the only host directory the task may write through the runtime
    workspace mount. source_path is an untrusted staged capability and is
    always read-only. output_path must be a strict child of root and is the
    only writable task path.
    """

    root: Path
    source_path: Path
    output_path: Path
    source_read_only: bool = True
    output_read_only: bool = False

    def validate(self, *, require_output: bool = False) -> None:
        root = _resolved_existing_directory(self.root, "workspace root")
        source = _resolved_existing_directory(self.source_path, "source path")

        if root == source:
            raise WorkspaceContractError(
                "workspace root and source path must be different"
            )

        if not self.source_read_only:
            raise WorkspaceContractError(
                "untrusted capability source must be read-only"
            )
        if self.output_read_only:
            raise WorkspaceContractError(
                "capability workspace output must be writable"
            )

        raw_output = Path(self.output_path).expanduser()
        if raw_output.exists() and raw_output.is_symlink():
            raise WorkspaceContractError("workspace output must not be a symlink")
        output = raw_output.resolve()

        if output == root:
            raise WorkspaceContractError(
                "workspace output must be a child of the workspace root"
            )
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise WorkspaceContractError(
                "workspace output must remain inside the workspace root"
            ) from exc

        if output.exists():
            if not output.is_dir():
                raise WorkspaceContractError("workspace output must be a directory")
        elif require_output:
            raise WorkspaceContractError("workspace output directory does not exist")
        else:
            # Missing descendant directories are safe to create because the
            # resolved output path has already been proven to stay inside root.
            pass

        if _is_ancestor(source, output) or _is_ancestor(output, source):
            raise WorkspaceContractError(
                "source and workspace output must not overlap"
            )

    def ensure_output_directory(self) -> Path:
        """Create the declared output directory without escaping the root."""
        self.validate(require_output=False)
        output = Path(self.output_path).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        self.validate(require_output=True)
        return output

    @property
    def source_mount_read_only(self) -> bool:
        return self.source_read_only


def _resolved_existing_directory(path: Path, label: str) -> Path:
    raw = Path(path).expanduser()
    if raw.exists() and raw.is_symlink():
        raise WorkspaceContractError(f"{label} must not be a symlink")
    resolved = raw.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise WorkspaceContractError(f"{label} must be an existing directory")
    return resolved


def _is_ancestor(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
