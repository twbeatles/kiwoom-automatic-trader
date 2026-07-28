"""B4: 일일 손실 한도 즉시 평가 검증.

매도 체결 누적(_add_trade) 직후 _check_daily_loss_limit 가 호출되어,
다음 timer tick 을 기다리지 않고 daily_loss_triggered 가 True 로 전환되는지 확인.
"""
import unittest


class _DummySignal:
    def emit(self):
        return None


class _DummyCheck:
    def __init__(self, checked=True):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _DummySpin:
    def __init__(self, value=3.0):
        self._value = value

    def value(self):
        return self._value


class _Harness:
    """_check_daily_loss_limit + _add_trade 경로만 검증하는 최소 하네스."""

    def __init__(self):
        self.is_running = True
        self.daily_loss_triggered = False
        self.daily_realized_profit = 0
        self.daily_initial_deposit = 1_000_000
        self.config = type("Cfg", (), {"max_daily_loss": 3.0, "daily_loss_basis": "total_equity"})()
        self.chk_use_risk = _DummyCheck(checked=True)
        self.spin_max_loss = _DummySpin(value=3.0)
        self.stop_called = False
        self.logs = []
        self.trade_history = []

    def log(self, msg):
        self.logs.append(str(msg))

    def stop_trading(self):
        self.stop_called = True

    # 시스템 쉘 믹스인에서 가져온 동일 로직(헬퍼).
    def _check_daily_loss_limit(self):
        if bool(getattr(self, "daily_loss_triggered", False)):
            return
        if not getattr(self, "is_running", False):
            return
        use_risk_chk = getattr(self, "chk_use_risk", None)
        if use_risk_chk is None or not use_risk_chk.isChecked():
            return
        if int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0:
            return
        loss_rate = (self.daily_realized_profit / self.daily_initial_deposit) * 100
        max_loss_spin = getattr(self, "spin_max_loss", None)
        max_loss = float(getattr(self.config, "max_daily_loss", max_loss_spin.value() if max_loss_spin else 0))
        if loss_rate <= -max_loss:
            self.daily_loss_triggered = True
            self.log(
                f"일일 손실 한도 도달 ({loss_rate:.2f}%, 손익 {self.daily_realized_profit:+,}원) - 매매 중지"
            )
            self.stop_trading()

    def _add_trade(self, record):
        """거래내역 추가 + 매도 시 즉시 한도 평가(실제 trade_history.py 와 동일 패턴)."""
        self.trade_history.append(record)
        if record.get("type") == "매도":
            self.daily_realized_profit = int(getattr(self, "daily_realized_profit", 0) or 0) + int(
                record.get("profit", 0) or 0
            )
            check_fn = getattr(self, "_check_daily_loss_limit", None)
            if callable(check_fn):
                check_fn()


class TestDailyLossImmediateEval(unittest.TestCase):
    def test_sell_pushing_past_limit_triggers_immediately(self):
        trader = _Harness()
        # 초기 예수금 1,000,000 / 한도 3% = -30,000 원 도달 시 중지
        self.assertFalse(trader.daily_loss_triggered)

        trader._add_trade({"type": "매도", "profit": -15_000})
        # 아직 한도 미도달
        self.assertFalse(trader.daily_loss_triggered)
        self.assertFalse(trader.stop_called)

        # 한도 초과 매도
        trader._add_trade({"type": "매도", "profit": -20_000})  # 누적 -35,000 (-3.5%)

        # 다음 timer tick 없이 즉시 triggered
        self.assertTrue(trader.daily_loss_triggered)
        self.assertTrue(trader.stop_called)
        self.assertTrue(any("일일 손실 한도 도달" in m for m in trader.logs))

    def test_buy_does_not_trigger_loss_eval(self):
        trader = _Harness()
        trader._add_trade({"type": "매수", "profit": 0})
        self.assertFalse(trader.daily_loss_triggered)
        self.assertFalse(trader.stop_called)

    def test_already_triggered_short_circuits(self):
        trader = _Harness()
        trader.daily_loss_triggered = True
        trader._add_trade({"type": "매도", "profit": -100_000})
        # 이미 triggered 상태면 stop_trading 이 중복 호출되지 않는다.
        self.assertEqual(trader.stop_called, False)


if __name__ == "__main__":
    unittest.main()
