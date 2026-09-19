from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import OutputContract, OutputContractError


class OutputContractTests(unittest.TestCase):
    def test_valid_output_passes_and_reports_bounded_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "result.txt").write_text("ok", encoding="utf-8")
            contract = OutputContract(
                required_files=("result.txt",),
                max_files=2,
                max_total_bytes=16,
                max_single_file_bytes=8,
            )

            inspection = contract.inspect(root)

            self.assertTrue(inspection.passed)
            self.assertEqual(inspection.file_count, 1)
            self.assertEqual(inspection.total_bytes, 2)
            self.assertEqual(inspection.missing_required, ())
            self.assertEqual(inspection.violations, ())

    def test_missing_required_output_fails_closed(self):
        with TemporaryDirectory() as temp:
            inspection = OutputContract(required_files=("result.txt",)).inspect(
                Path(temp)
            )

        self.assertFalse(inspection.passed)
        self.assertEqual(inspection.missing_required, ("result.txt",))

    def test_size_and_count_limits_fail_closed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.bin").write_bytes(b"123456")
            (root / "b.bin").write_bytes(b"12")
            inspection = OutputContract(
                max_files=1,
                max_total_bytes=7,
                max_single_file_bytes=4,
            ).inspect(root)

        self.assertFalse(inspection.passed)
        self.assertTrue(inspection.violations)

    def test_symlink_output_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.txt"
            target.write_text("secret", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)

            inspection = OutputContract().inspect(root)

        self.assertFalse(inspection.passed)
        self.assertTrue(any("symlink" in item for item in inspection.violations))

    def test_control_characters_in_required_paths_are_rejected(self):
        with self.assertRaises(OutputContractError):
            OutputContract(required_files=("bad\x00name.txt",)).validate()
        with self.assertRaises(OutputContractError):
            OutputContract(required_files=("bad\nname.txt",)).validate()

    def test_output_inspection_limits_violation_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(40):
                (root / f"link-{index}").symlink_to(root, target_is_directory=True)
            inspection = OutputContract(max_files=1).inspect(root)

        self.assertFalse(inspection.passed)
        self.assertLessEqual(len(inspection.violations), 32)

    def test_required_paths_must_be_relative(self):
        with self.assertRaises(OutputContractError):
            OutputContract(required_files=("../escape.txt",)).validate()

    def test_contract_rejects_symlink_policy(self):
        with self.assertRaises(OutputContractError):
            OutputContract(allow_symlinks=True).validate()


if __name__ == "__main__":
    unittest.main()
