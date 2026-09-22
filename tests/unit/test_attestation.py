from __future__ import annotations

import json
import unittest

from core.runtime.attestation import (
    AttestationError,
    AttestationPolicy,
    attest_container,
)


DIGEST = "sha256:" + ("a" * 64)


def payload(**overrides):
    configuration = {
        "id": "super-ai-test",
        "image": {
            "reference": "alpine:latest",
            "descriptor": {"digest": DIGEST},
        },
        "mounts": [
            {"source": "/cap", "destination": "/capability", "options": ["ro"]},
            {"source": "/out", "destination": "/workspace", "options": []},
        ],
        "resources": {"cpus": 1, "memoryInBytes": 512 * 1024 * 1024},
        "readOnly": True,
        "capDrop": ["ALL"],
        "initProcess": {
            "user": {"id": {"uid": 65532, "gid": 65532}},
            "rlimits": [
                {"limit": "RLIMIT_NPROC", "soft": 64, "hard": 64},
                {"limit": "RLIMIT_NOFILE", "soft": 1024, "hard": 1024},
            ],
        },
    }
    status = {"state": "created", "networks": []}
    configuration.update(overrides.get("configuration", {}))
    status.update(overrides.get("status", {}))
    return json.dumps([{"configuration": configuration, "status": status}])


class AttestationTests(unittest.TestCase):
    def _policy(self, **kwargs):
        values = dict(
            expected_memory_bytes=512 * 1024 * 1024,
            expected_cpus=1,
            expected_image_digest=DIGEST,
        )
        values.update(kwargs)
        return AttestationPolicy(**values)

    def test_process_limit_contract_bounds_are_validated(self):
        with self.assertRaises(ValueError):
            self._policy(expected_max_processes=0).validate()
        with self.assertRaises(ValueError):
            self._policy(expected_max_processes=4097).validate()
        with self.assertRaises(ValueError):
            self._policy(expected_max_open_files=15).validate()
        with self.assertRaises(ValueError):
            self._policy(expected_max_open_files=65537).validate()

    def test_valid_configuration_passes(self):
        result = attest_container(
            payload(),
            container_id="super-ai-test",
            image_reference="alpine:latest",
            policy=self._policy(),
            network_disabled=True,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.image_digest, DIGEST)
        self.assertEqual(result.mount_destinations, ("/capability", "/workspace"))


    def test_process_limits_are_attested(self):
        result = attest_container(
            payload(),
            container_id="super-ai-test",
            image_reference="alpine:latest",
            policy=self._policy(
                expected_max_processes=64,
                expected_max_open_files=1024,
            ),
            network_disabled=True,
        )
        self.assertEqual(result.max_processes, 64)
        self.assertEqual(result.max_open_files, 1024)
        self.assertEqual(result.as_dict()["max_processes"], 64)
        self.assertEqual(result.as_dict()["max_open_files"], 1024)

    def test_process_limit_mismatch_fails_closed(self):
        with self.assertRaisesRegex(AttestationError, "RLIMIT_NPROC mismatch"):
            attest_container(
                payload(configuration={
                    "initProcess": {
                        "user": {"id": {"uid": 65532, "gid": 65532}},
                        "rlimits": [
                            {"limit": "RLIMIT_NPROC", "soft": 32, "hard": 32},
                            {"limit": "RLIMIT_NOFILE", "soft": 1024, "hard": 1024},
                        ],
                    }
                }),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(
                    expected_max_processes=64,
                    expected_max_open_files=1024,
                ),
                network_disabled=True,
            )

    def test_open_file_limit_mismatch_fails_closed(self):
        with self.assertRaisesRegex(AttestationError, "RLIMIT_NOFILE mismatch"):
            attest_container(
                payload(configuration={
                    "initProcess": {
                        "user": {"id": {"uid": 65532, "gid": 65532}},
                        "rlimits": [
                            {"limit": "RLIMIT_NPROC", "soft": 64, "hard": 64},
                            {"limit": "RLIMIT_NOFILE", "soft": 2048, "hard": 2048},
                        ],
                    }
                }),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(
                    expected_max_processes=64,
                    expected_max_open_files=1024,
                ),
                network_disabled=True,
            )

    def test_missing_process_limits_fail_closed_when_required(self):
        with self.assertRaisesRegex(AttestationError, "missing RLIMIT_NPROC"):
            attest_container(
                payload(configuration={
                    "initProcess": {
                        "user": {"id": {"uid": 65532, "gid": 65532}},
                        "rlimits": [],
                    }
                }),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(expected_max_processes=64),
                network_disabled=True,
            )

    def test_network_attachment_fails_closed(self):
        with self.assertRaisesRegex(AttestationError, "network attachments"):
            attest_container(
                payload(status={"networks": [{"network": "default"}]}),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(),
                network_disabled=True,
            )

    def test_memory_mismatch_fails_closed(self):
        with self.assertRaisesRegex(AttestationError, "memory allocation mismatch"):
            attest_container(
                payload(configuration={
                    "resources": {
                        "cpus": 1,
                        "memoryInBytes": 256 * 1024 * 1024,
                    }
                }),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(),
                network_disabled=True,
            )

    def test_image_digest_mismatch_fails_closed(self):
        wrong = "sha256:" + ("b" * 64)
        with self.assertRaisesRegex(AttestationError, "digest"):
            attest_container(
                payload(),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(expected_image_digest=wrong),
                network_disabled=True,
            )

    def test_mounts_must_be_exact(self):
        with self.assertRaisesRegex(AttestationError, "mount destinations mismatch"):
            attest_container(
                payload(configuration={
                    "mounts": [
                        {"source": "/cap", "destination": "/capability", "options": ["ro"]},
                    ]
                }),
                container_id="super-ai-test",
                image_reference="alpine:latest",
                policy=self._policy(),
                network_disabled=True,
            )


if __name__ == "__main__":
    unittest.main()
