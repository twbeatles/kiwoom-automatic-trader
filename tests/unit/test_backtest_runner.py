import tempfile
import unittest
from pathlib import Path

from app.support.backtest_runner import backtest_result_to_dict, load_backtest_bars_csv, run_backtest_from_files


class TestBacktestRunner(unittest.TestCase):
    def test_csv_loader_and_runner_return_serializable_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "bars.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "symbol,ts,open,high,low,close,volume",
                        "AAA,2026-01-01,100,101,99,100,1000",
                        "AAA,2026-01-02,101,103,100,102,1000",
                        "AAA,2026-01-03,102,104,101,103,1000",
                        "AAA,2026-01-04,103,105,102,104,1000",
                        "AAA,2026-01-05,104,106,103,105,1000",
                        "AAA,2026-01-06,105,108,104,107,1000",
                        "AAA,2026-01-07,107,108,101,102,1000",
                    ]
                ),
                encoding="utf-8",
            )

            bars = load_backtest_bars_csv(csv_path)
            result = run_backtest_from_files(csv_path, config_values={"commission_bps": 0, "slippage_bps": 0})
            serialized = backtest_result_to_dict(result)

        self.assertEqual(len(bars), 7)
        self.assertIn("metrics", serialized)
        self.assertIn("trades", serialized)
        self.assertIn("equity_curve", serialized)


if __name__ == "__main__":
    unittest.main()
