from __future__ import annotations

import unittest

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

    def test_rejects_unsafe_command_token(self):
        with self.assertRaises(RuntimeSpecError):
            RuntimeSpec(
                image="alpine:3.22",
                command=("/bin/sh
malicious",),
            ).validate()


if __name__ == "__main__":
    unittest.main()
