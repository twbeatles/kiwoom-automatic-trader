import datetime
import unittest

from app.support.portfolio_summary import compute_portfolio_summary, position_eval


class _DummyLabel:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)


class TestPortfolioSummary(unittest.TestCase):
    def _universe(self):
        return {
            "005930": {
                "name": "삼성전자", "held": 10, "buy_price": 70000, "current": 75000,
                "invest_amount": 700000, "market_type": "KOSPI", "sector": "전기전자",
                "status": "holding",
            },
            "000660": {
                "name": "SK하이닉스", "held": 5, "buy_price": 200000, "current": 190000,
                "invest_amount": 1000000, "market_type": "KOSPI", "sector": "전기전자",
                "status": "sync_failed", "sync_failed_reason": "조회 실패",
            },
        }

    def _external(self):
        return {
            "035420": {
                "name": "NAVER", "held": 3, "buy_price": 200000, "current": 210000,
                "invest_amount": 600000, "market_type": "KOSPI", "sector": "서비스업",
                "status": "external_holding", "read_only": True,
            },
        }

    def test_position_eval_math(self):
        snap = position_eval({"held": 10, "buy_price": 70000, "current": 75000, "invest_amount": 700000})
        self.assertEqual(snap["eval_amount"], 750000.0)
        self.assertEqual(snap["unrealized_pnl"], 50000.0)

    def test_summary_pnl_weights_exposure(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        history = [
            {"timestamp": f"{today}T10:00:00", "type": "매도", "profit": 50000},
            {"timestamp": f"{today}T11:00:00", "type": "매도", "profit": -10000},
            {"timestamp": f"{today}T09:00:00", "type": "매수", "profit": 0},
        ]
        summary = compute_portfolio_summary(self._universe(), self._external(), history, today=today)
        self.assertEqual(summary["realized_pnl"], 40000.0)
        # unrealized: 50000 (005930) - 50000 (000660) + 30000 (035420)
        self.assertEqual(summary["unrealized_pnl"], 30000.0)
        self.assertEqual(summary["total_pnl"], 70000.0)
        self.assertAlmostEqual(sum(summary["weights"].values()), 1.0)
        self.assertEqual(summary["top_weights"][0][0], "000660")
        self.assertEqual(summary["exposures"]["sector"]["전기전자"], 750000.0 + 950000.0)
        self.assertEqual(summary["exposures"]["sector"]["서비스업"], 630000.0)
        self.assertEqual(summary["counts"]["external"], 1)
        self.assertEqual(summary["counts"]["read_only"], 1)
        self.assertEqual(summary["counts"]["sync_failed"], 1)
        self.assertEqual(summary["sync_failed_codes"], ["000660"])
        self.assertEqual(summary["external_codes"], ["035420"])
        self.assertEqual(summary["read_only_codes"], ["035420"])

    def test_summary_empty_safe(self):
        summary = compute_portfolio_summary(None, None, None)
        self.assertEqual(summary["realized_pnl"], 0.0)
        self.assertEqual(summary["weights"], {})
        self.assertEqual(summary["counts"]["tracked"], 0)

    def test_refresh_portfolio_cards_wiring(self):
        from app.features.ui_build.data_tabs import UIBuildDataTabsMixin

        class Harness:
            _refresh_portfolio_cards = UIBuildDataTabsMixin._refresh_portfolio_cards

            def __init__(self, universe, external, history):
                self.universe = universe
                self.external_positions = external
                self.trade_history = history
                self.portfolio_labels = {key: _DummyLabel() for key in ("pnl", "weight", "exposure", "health")}

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        harness = Harness(
            self._universe(),
            self._external(),
            [{"timestamp": f"{today}T10:00:00", "type": "매도", "profit": 1000}],
        )
        harness._refresh_portfolio_cards()
        self.assertIn("1,000", harness.portfolio_labels["pnl"].text)
        self.assertIn("외부 1", harness.portfolio_labels["health"].text)
        self.assertIn("동기화실패 1", harness.portfolio_labels["health"].text)


if __name__ == "__main__":
    unittest.main()
