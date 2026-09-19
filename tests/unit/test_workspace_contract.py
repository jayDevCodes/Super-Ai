from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import WorkspaceContract, WorkspaceContractError


class WorkspaceContractTests(unittest.TestCase):
    def test_valid_workspace_requires_output_inside_root(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "runs" / "one"
            source.mkdir()

            contract = WorkspaceContract(
                root=root,
                source_path=source,
                output_path=output,
            )
            contract.ensure_output_directory()

            self.assertTrue(output.is_dir())
            contract.validate(require_output=True)

    def test_output_escape_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            escaped = root.parent / "outside"

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "inside the workspace root",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=source,
                    output_path=escaped,
                ).validate()

    def test_source_must_be_read_only(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            source.mkdir()

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "read-only",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=source,
                    output_path=output,
                    source_read_only=False,
                ).validate()

    def test_output_must_be_writable(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            source.mkdir()

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "writable",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=source,
                    output_path=output,
                    output_read_only=True,
                ).validate()

    def test_overlapping_paths_are_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            output = source / "output"

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "must not overlap",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=source,
                    output_path=output,
                ).validate()

    def test_root_and_source_cannot_be_same_directory(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "must be different",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=root,
                    output_path=root / "output",
                ).validate()

    def test_symlinked_output_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            output_link = root / "output"
            source.mkdir()
            target.mkdir()
            output_link.symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(
                WorkspaceContractError,
                "must not be a symlink",
            ):
                WorkspaceContract(
                    root=root,
                    source_path=source,
                    output_path=output_link,
                ).validate()


if __name__ == "__main__":
    unittest.main()
