import unittest

from config import TradingConfig
from strategy_manager import StrategyManager


class _Trader:
    def __init__(self):
        self.deposit = 1_000_000
        self.universe = {"005930": {"market_type": "KOSPI", "sector": "IT"}}

    def log(self, _msg):
        return None


class TestInvestmentCostBasisLedger(unittest.TestCase):
    def test_market_and_sector_ledger_returns_to_zero_after_profit_sell(self):
        trader = _Trader()
        manager = StrategyManager(trader, TradingConfig())
        manager.update_market_investment("005930", 100_000, is_buy=True)
        manager.update_sector_investment("005930", 100_000, is_buy=True)

        manager.update_market_investment("005930", 120_000, is_buy=False, cost_amount=100_000)
        manager.update_sector_investment("005930", 120_000, is_buy=False, cost_amount=100_000)

        self.assertEqual(manager.market_investments.get("kospi", 0), 0)
        self.assertEqual(manager.sector_investments.get("IT", 0), 0)

    def test_market_and_sector_ledger_returns_to_zero_after_loss_sell(self):
        trader = _Trader()
        manager = StrategyManager(trader, TradingConfig())
        manager.update_market_investment("005930", 100_000, is_buy=True)
        manager.update_sector_investment("005930", 100_000, is_buy=True)

        manager.update_market_investment("005930", 80_000, is_buy=False, cost_amount=100_000)
        manager.update_sector_investment("005930", 80_000, is_buy=False, cost_amount=100_000)

        self.assertEqual(manager.market_investments.get("kospi", 0), 0)
        self.assertEqual(manager.sector_investments.get("IT", 0), 0)


if __name__ == "__main__":
    unittest.main()
