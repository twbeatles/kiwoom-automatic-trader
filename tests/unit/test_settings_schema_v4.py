import unittest

from app.mixins.persistence_settings import PersistenceSettingsMixin


class _Harness(PersistenceSettingsMixin):
    pass


class TestSettingsSchemaV4(unittest.TestCase):
    def test_v4_defaults_are_injected_and_version_upgraded(self):
        trader = _Harness()
        settings = {
            "settings_version": 3,
            "codes": "005930",
            "shock_1m_pct": 2.0,
        }

        trader._apply_settings_schema_migration(settings)

        self.assertEqual(settings["settings_version"], 4)
        self.assertEqual(settings["shock_1m_pct"], 2.0)
        self.assertIn("use_vi_guard", settings)
        self.assertIn("max_slippage_bps", settings)
        self.assertIn("order_health_fail_count", settings)


if __name__ == "__main__":
    unittest.main()
