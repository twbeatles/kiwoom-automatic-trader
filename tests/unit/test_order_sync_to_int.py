import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("keyring", MagicMock())

from app.mixins.order_sync import OrderSyncMixin


class TestOrderSyncToInt(unittest.TestCase):
    def test_to_int_handles_common_inputs(self):
        self.assertEqual(OrderSyncMixin._to_int("1,234"), 1234)
        self.assertEqual(OrderSyncMixin._to_int("123.0"), 123)
        self.assertEqual(OrderSyncMixin._to_int(None), 0)
        self.assertEqual(OrderSyncMixin._to_int(""), 0)
        self.assertEqual(OrderSyncMixin._to_int("abc", default=7), 7)


if __name__ == "__main__":
    unittest.main()
