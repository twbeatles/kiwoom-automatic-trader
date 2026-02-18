import unittest

from app.support.execution_policy import ExecutionPolicy


class _DummyClient:
    def buy_market(self, *args):
        return ("buy_market", args)

    def buy_limit(self, *args):
        return ("buy_limit", args)

    def sell_market(self, *args):
        return ("sell_market", args)

    def sell_limit(self, *args):
        return ("sell_limit", args)


class TestExecutionPolicy(unittest.TestCase):
    def test_select_buy_limit(self):
        client = _DummyClient()
        fn, args = ExecutionPolicy.select_buy(client, "limit", "acc", "005930", 1, 70000)
        self.assertEqual(fn.__name__, "buy_limit")
        self.assertEqual(args, ("acc", "005930", 1, 70000))

    def test_select_sell_market_fallback(self):
        client = _DummyClient()
        fn, args = ExecutionPolicy.select_sell(client, "market", "acc", "005930", 2, 0)
        self.assertEqual(fn.__name__, "sell_market")
        self.assertEqual(args, ("acc", "005930", 2))


if __name__ == "__main__":
    unittest.main()
