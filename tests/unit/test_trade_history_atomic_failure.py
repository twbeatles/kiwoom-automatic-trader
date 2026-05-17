import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.mixins.persistence_settings import PersistenceSettingsMixin


class _Harness(PersistenceSettingsMixin):
    pass


class TestTradeHistoryAtomicFailure(unittest.TestCase):
    def test_worker_raises_when_atomic_replace_fails(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_directory = Path(tmpdir) / "history_as_directory"
            target_directory.mkdir()
            with patch("app.mixins.persistence_settings.Config.TRADE_HISTORY_FILE", str(target_directory)):
                with self.assertRaises(OSError):
                    trader._save_trade_history_worker([{"seq": 1}])


if __name__ == "__main__":
    unittest.main()
