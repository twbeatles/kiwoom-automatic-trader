"""ISSUE-003: ProfileManager atomic save + corrupt backup."""
import json
import tempfile
import unittest
from pathlib import Path

from profile_manager import ProfileManager


class TestProfileCorruptBackup(unittest.TestCase):
    def test_corrupt_file_preserved_as_bak_and_empty_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ProfileManager.PROFILES_FILE
            target.write_bytes(b"{broken json,,,")
            pm = ProfileManager(data_dir=tmp)
            self.assertTrue(pm._load_failed)
            self.assertEqual(pm.get_profile_names(), [])
            bak = Path(tmp) / (ProfileManager.PROFILES_FILE + ".bak")
            self.assertTrue(bak.exists())
            self.assertEqual(bak.read_bytes(), b"{broken json,,,")
            # 손상 후 빈 저장은 거부되고 원본이 유지된다.
            self.assertFalse(pm._save_profiles())
            self.assertEqual(target.read_bytes(), b"{broken json,,,")

    def test_save_after_corrupt_recovers_and_clears_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ProfileManager.PROFILES_FILE
            target.write_bytes(b"not json")
            pm = ProfileManager(data_dir=tmp)
            self.assertTrue(pm.save_profile("day", {"k": 0.5}))
            self.assertFalse(pm._load_failed)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("day", payload["profiles"])
            # tmp 잔여 파일이 남지 않는다.
            self.assertFalse((Path(tmp) / (ProfileManager.PROFILES_FILE + ".tmp")).exists())

    def test_non_dict_json_treated_as_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ProfileManager.PROFILES_FILE
            target.write_text("[1, 2, 3]", encoding="utf-8")
            pm = ProfileManager(data_dir=tmp)
            self.assertTrue(pm._load_failed)
            self.assertEqual(pm.get_profile_names(), [])

    def test_normal_roundtrip_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProfileManager(data_dir=tmp)
            self.assertFalse(pm._load_failed)
            self.assertTrue(pm.save_profile("day", {"k": 0.5}))
            pm2 = ProfileManager(data_dir=tmp)
            self.assertFalse(pm2._load_failed)
            self.assertEqual(pm2.get_profile_names(), ["day"])


if __name__ == "__main__":
    unittest.main()
