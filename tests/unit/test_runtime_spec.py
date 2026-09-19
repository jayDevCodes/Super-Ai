from __future__ import annotations

import unittest

from core.contracts import OutputContract
from registry.runtime import RuntimeSpec, RuntimeSpecError


class RuntimeSpecTests(unittest.TestCase):
    def test_valid_runtime_spec(self):
        RuntimeSpec(
            image="alpine:3.22",
            command=("/bin/sh", "-c", "echo ok"),
            expected_image_digest="sha256:" + "a" * 64,
        ).validate()

    def test_rejects_url_image_reference(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(
                image="https://example.com/image:latest",
                command=("/bin/sh",),
            ).validate()

    def test_rejects_empty_command(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(image="alpine:3.22", command=()).validate()

    def test_rejects_invalid_digest(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(
                image="alpine:3.22",
                command=("/bin/sh",),
                expected_image_digest="alpine:latest",
            ).validate()

    def test_output_contract_is_part_of_runtime_identity(self):
        spec = RuntimeSpec(
            image="alpine:3.22",
            command=("/bin/sh",),
            output_contract=OutputContract(
                required_files=("result.txt",),
                max_files=8,
                max_total_bytes=1024,
                max_single_file_bytes=512,
            ),
        )
        spec.validate()
        self.assertEqual(spec.output_contract.required_files, ("result.txt",))

    def test_rejects_invalid_output_contract(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(
                image="alpine:3.22",
                command=("/bin/sh",),
                output_contract=OutputContract(allow_symlinks=True),
            ).validate()

    def test_rejects_unsafe_command_token(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(
                image="alpine:3.22",
                command=("/bin/sh" + "\n" + "malicious",),
            ).validate()


if __name__ == "__main__":
    unittest.main()
