
import sys
import unittest
from unittest.mock import MagicMock
from config import TradingConfig, Config

# Append path to import modules
sys.path.append('d:/google antigravity/키움증권 자동 매매 프로그램')

# Mocking modules that might depend on PyQt if imported directly or not needed
# For StrategyManager, we need it to be importable.
# If StrategyManager imports top level stuff, we might face issues, but let's try.
from strategy_manager import StrategyManager

class MockTrader:
    def __init__(self):
        self.universe = {}
        self.deposit = 10_000_000
    
    def log(self, msg):
        print(f"[LOG] {msg}")

class TestDecoupling(unittest.TestCase):
    def test_config_injection(self):
        """Test that StrategyManager uses values from TradingConfig"""
        trader = MockTrader()
        config = TradingConfig()
        
        # Set specific values in config
        config.k_value = 0.7
        config.use_rsi = True
        config.rsi_period = 14
        config.rsi_upper = 80
        
        # Instantiate StrategyManager with config
        strategy = StrategyManager(trader, config)
        
        # 1. Verify Gap Adjusted K (should use config.k_value if no gap)
        # Mock universe data for '005930'
        trader.universe['005930'] = {
            'open': 10000, 'prev_close': 10000, # 0% gap
            'high': 10200, 'low': 9900, 'current': 10100,
            'price_history': [10000] * 20
        }
        
        k = strategy.get_gap_adjusted_k('005930')
        self.assertEqual(k, 0.7, f"Expected K=0.7 from config, got {k}")
        
        # 2. Update config and verify change reflected immediately
        config.k_value = 0.3
        k_new = strategy.get_gap_adjusted_k('005930')
        self.assertEqual(k_new, 0.3, f"Expected K=0.3 after config update, got {k_new}")
        
        print("✅ StrategyManager correctly reads dynamic updates from TradingConfig")

    def test_ui_independence(self):
        """Ensure no UI widget attributes are accessed"""
        trader = MockTrader()
        config = TradingConfig()
        strategy = StrategyManager(trader, config)
        
        # If strategy tries to access self.trader.spin_k, it will fail because MockTrader doesn't have it.
        try:
            strategy.get_gap_adjusted_k('005930')
            strategy.check_rsi_condition('005930')
            strategy.check_bollinger_condition('005930')
            print("✅ StrategyManager ran without accessing UI widgets")
        except AttributeError as e:
            self.fail(f"StrategyManager tried to access missing attribute (likely UI widget): {e}")

if __name__ == '__main__':
    unittest.main()
