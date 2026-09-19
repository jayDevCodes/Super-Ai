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
        "initProcess": {"user": {"id": {"uid": 65532, "gid": 65532}}},
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
