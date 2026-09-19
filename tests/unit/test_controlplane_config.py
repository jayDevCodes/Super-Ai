import os
import unittest

from core.controlplane.config import ConfigError, EngineConfig


class EngineConfigTests(unittest.TestCase):
    def test_defaults_validate(self):
        cfg = EngineConfig()
        cfg.validate()
        self.assertEqual(cfg.host_ram_mb, 8192)
        self.assertEqual(cfg.storage_gb, 256)

    def test_cache_bounds(self):
        with self.assertRaises(ConfigError):
            EngineConfig(cache_soft_limit_gb=10, cache_hard_limit_gb=9).validate()

    def test_env_loader(self):
        original = os.environ.get("SUPER_AI_MAX_CONCURRENT_TASKS")
        os.environ["SUPER_AI_MAX_CONCURRENT_TASKS"] = "3"
        try:
            self.assertEqual(EngineConfig.from_env().max_concurrent_tasks, 3)
        finally:
            if original is None:
                os.environ.pop("SUPER_AI_MAX_CONCURRENT_TASKS", None)
            else:
                os.environ["SUPER_AI_MAX_CONCURRENT_TASKS"] = original
