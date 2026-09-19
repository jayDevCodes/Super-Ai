from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.security import (
    EnvironmentPolicyError,
    build_sandbox_environment,
)


class EnvironmentPolicyTests(unittest.TestCase):
    def test_only_allowlisted_host_variables_are_inherited(self):
        with patch.dict(os.environ, {
            "PATH": "/safe/bin",
            "HOME": "/private",
            "SUPER_AI_TOKEN": "secret",
        }, clear=False):
            env = build_sandbox_environment()
        self.assertEqual(env["PATH"], "/safe/bin")
        self.assertNotIn("HOME", env)
        self.assertNotIn("SUPER_AI_TOKEN", env)

    def test_sensitive_explicit_variable_is_rejected(self):
        with self.assertRaises(EnvironmentPolicyError):
            build_sandbox_environment({"API_KEY": "secret"})

    def test_control_characters_are_rejected(self):
        with self.assertRaises(EnvironmentPolicyError):
            build_sandbox_environment({"SAFE": "bad\nvalue"})

    def test_explicit_non_sensitive_variable_is_allowed(self):
        env = build_sandbox_environment({"MODE": "smoke"})
        self.assertEqual(env["MODE"], "smoke")


if __name__ == "__main__":
    unittest.main()
