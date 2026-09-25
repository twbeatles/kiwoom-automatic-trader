"""Manual-order dialogs (SRP: validation + submit + result only)."""

from typing import Any, Dict

from PyQt6.QtWidgets import QDialog, QMessageBox

from app.support.worker import Worker
from app.mixins._typing import TraderMixinBase
from config import Config


class ManualOrdersMixin(TraderMixinBase):
    """Manual-order dialogs (SRP: validation + submit + result only)."""

    def _manual_order_live_guard_required(self) -> bool:
        if not bool(getattr(Config, "LIVE_GUARD_ENABLED", True)):
            return False
        chk_mock = getattr(self, "chk_mock", None)
        if chk_mock is None:
            return False
        return not bool(chk_mock.isChecked())

    def _estimate_manual_order_price(self, order: dict) -> int:
        if not isinstance(order, dict):
            return 0
        order_type = str(order.get("type", "") or "")
        if order_type != "매수":
            return max(0, int(order.get("price", 0) or 0))

        price_type = str(order.get("price_type", "시장가") or "시장가")
        if price_type == "지정가":
            return max(1, int(order.get("price", 0) or 0))

        code = str(order.get("code", "") or "").strip()
        info = getattr(self, "universe", {}).get(code, {}) if code else {}
        current = max(0, int(info.get("current", 0) or 0))
        if current > 0:
            return current

        client = getattr(self, "rest_client", None)
        fetch_quote = getattr(client, "get_stock_quote", None)
        if callable(fetch_quote) and code:
            try:
                quote = fetch_quote(code)
                current = max(0, int(getattr(quote, "current_price", 0) or 0))
            except Exception as exc:
                self.log(f"⚠️ 수동 주문 현재가 조회 실패: {exc}")
                current = 0
        return current

    def _resolve_manual_sell_available_qty(self, code: str):
        code = str(code or "").strip()
        if not code:
            return None

        latest_available = None
        if getattr(self, "is_connected", False) and getattr(self, "rest_client", None) and getattr(self, "current_account", ""):
            getter = getattr(self.rest_client, "get_positions", None)
            if callable(getter):
                try:
                    positions = getter(self.current_account)
                except Exception as exc:
                    self.log(f"Manual sell position refresh failed [{code}]: {exc}")
                    positions = None
                if isinstance(positions, list):
                    latest_available = 0
                    for position in positions:
                        if str(getattr(position, "code", "") or "").strip() != code:
                            continue
                        latest_available = max(
                            0,
                            int(getattr(position, "available_qty", getattr(position, "quantity", 0)) or 0),
                        )
                        break
        if latest_available is not None:
            return latest_available

        tracked_getter = getattr(self, "_get_tracked_position_info", None)
        raw_info = tracked_getter(code) if callable(tracked_getter) else {}
        info: Dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
        if not info:
            universe = getattr(self, "universe", {})
            if isinstance(universe, dict):
                raw_info = universe.get(code, {})
                info = raw_info if isinstance(raw_info, dict) else {}
        if not info:
            external_positions = getattr(self, "external_positions", {})
            if isinstance(external_positions, dict):
                raw_info = external_positions.get(code, {})
                info = raw_info if isinstance(raw_info, dict) else {}
        if not info:
            return None
        return max(0, int(info.get("available_qty", info.get("held", 0)) or 0))

    def _validate_manual_order_request(self, order: dict) -> bool:
        if not isinstance(order, dict):
            QMessageBox.warning(self, "경고", "주문 요청 데이터가 올바르지 않습니다.")
            return False

        code = str(order.get("code", "") or "").strip()
        qty = max(0, int(order.get("qty", 0) or 0))
        price_type = str(order.get("price_type", "시장가") or "시장가")
        price = max(0, int(order.get("price", 0) or 0))
        order_type = str(order.get("type", "") or "")

        if len(code) != 6 or not code.isdigit():
            QMessageBox.warning(self, "경고", "종목코드는 6자리 숫자여야 합니다.")
            return False
        if qty <= 0:
            QMessageBox.warning(self, "경고", "주문수량은 1주 이상이어야 합니다.")
            return False
        if price_type == "지정가" and price <= 0:
            QMessageBox.warning(self, "경고", "지정가 주문은 1원 이상의 가격이 필요합니다.")
            return False

        universe = getattr(self, "universe", {})
        external_positions = getattr(self, "external_positions", {})
        has_external_position = isinstance(external_positions, dict) and code in external_positions
        if code not in universe and not has_external_position:
            QMessageBox.warning(
                self,
                "경고",
                "감시 유니버스 또는 동기화된 보유 포지션에 없는 종목은 수동 주문할 수 없습니다.",
            )
            return False

        estimated_price = self._estimate_manual_order_price(order)
        order["expected_price"] = estimated_price
        if order_type == "매수":
            if code not in universe:
                QMessageBox.warning(
                    self,
                    "경고",
                    "감시 유니버스 밖 종목은 수동 매수할 수 없습니다.",
                )
                return False
            if estimated_price <= 0:
                QMessageBox.warning(
                    self,
                    "경고",
                    "현재가를 확인할 수 없어 예상 주문금액을 계산하지 못했습니다.\n"
                    "지정가 주문을 사용하거나 감시 유니버스에 종목을 먼저 추가해주세요.",
                )
                return False
            required_cash = qty * estimated_price
            available_cash = int(getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0)) or 0)
            if required_cash > available_cash:
                QMessageBox.warning(
                    self,
                    "경고",
                    f"예상 필요금액 {required_cash:,}원이 주문가능금액 {available_cash:,}원을 초과합니다.",
                )
                return False
        elif order_type == "매도":
            available_qty = self._resolve_manual_sell_available_qty(code)
            if available_qty is None:
                QMessageBox.warning(
                    self,
                    "경고",
                    "최신 보유 가능수량을 확인할 수 없어 매도 주문을 진행하지 않습니다.",
                )
                return False
            if qty > available_qty:
                QMessageBox.warning(
                    self,
                    "경고",
                    f"매도 가능수량 {available_qty}주를 초과한 주문입니다.",
                )
                return False

        return True

    def _open_manual_order(self):
        """수동 주문 다이얼로그 열기"""
        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API에 연결하세요.")
            return
        if not getattr(self, "current_account", ""):
            QMessageBox.warning(self, "경고", "주문 가능한 계좌를 먼저 선택하세요.")
            return
        
        # NOTE(compat-seam): 기존 테스트가 "app.mixins.dialogs_profiles.ManualOrderDialog"를
        # patch하므로, 호출 시점에 shim 모듈 속성으로 조회한다. (import 시점 바인딩 금지)
        from app.mixins import dialogs_profiles as _dialogs_seam
        dialog = _dialogs_seam.ManualOrderDialog(self, self.rest_client, self.current_account)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.order_result:
            order = dialog.order_result
            # 검증은 이 지점(단일 choke point)에서만 통과한다.
            # 통과한 주문만 실행될 수 있도록 플래그로 표시하고, 아래 실제 주문 실행 직전에 다시 확인한다.
            if not self._validate_manual_order_request(order):
                return
            order["validated"] = True
            self._dispatch_manual_order(order)
            return

    def _dispatch_manual_order(self, order):
        """검증 통과 주문의 실행 단계(signal_only/live 가드 + Worker 전송).

        주문 티켓과 수동 주문 다이얼로그가 공유하는 단일 실행 경로다.
        호출자는 반드시 _validate_manual_order_request 통과 후
        order["validated"] = True 를 세팅해야 한다.
        """
        signal_only = getattr(self, "_is_signal_only_mode", None)
        if callable(signal_only) and bool(signal_only()):
            recorder = getattr(self, "_record_signal_only_order", None)
            if callable(recorder):
                recorder(
                    side="buy" if order.get("type") == "매수" else "sell",
                    code=str(order.get("code", "")),
                    quantity=int(order.get("qty", 0) or 0),
                    price=int(order.get("expected_price", order.get("price", 0)) or 0),
                    reason="MANUAL_ORDER",
                    payload=dict(order),
                )
            return
        if self._manual_order_live_guard_required():
            confirm_guard = getattr(self, "_confirm_live_trading_guard", None)
            if callable(confirm_guard) and not bool(confirm_guard()):
                return
        self.log(f"📝 수동 주문 요청: {order['type']} {order['code']} {order['qty']}주")

        # 방어막: 검증 통과 플래그가 없으면 절대 주문을 실행하지 않는다.
        # (choke point 회귀로 인한 우회를 원천 차단)
        if not bool(order.get("validated", False)):
            self.log("❌ 수동 주문 차단: 검증을 통과하지 않은 요청입니다.")
            return

        # 실제 주문 실행 (Worker 사용)
        code = order['code']
        qty = order['qty']
        price = order.get('price', 0)
        order_type = order['type']
        price_type = order.get('price_type', '시장가')
        
        # API 호출 함수 선택
        if order_type == '매수':
            if price_type == '시장가':
                func = self.rest_client.buy_market
                args = (self.current_account, code, qty)
            else:
                func = self.rest_client.buy_limit
                args = (self.current_account, code, qty, price)
        else:  # 매도
            if price_type == '시장가':
                func = self.rest_client.sell_market
                args = (self.current_account, code, qty)
            else:
                func = self.rest_client.sell_limit
                args = (self.current_account, code, qty, price)

        worker = Worker(func, *args)
        worker.signals.result.connect(
            lambda res, submitted_order=order: self._on_manual_order_result(res, submitted_order, order_type, code)
        )
        worker.signals.error.connect(lambda e: self.log(f"❌ 수동 주문 오류: {e}"))
        self.threadpool.start(worker)

    def _on_manual_order_result(self, result, order, order_type, code):
        """수동 주문 결과 처리"""
        if result.success:
            self.log(f"✅ 수동 주문 성공: {order_type} {code} (주문번호 {result.order_no})")
            side = "buy" if order_type == "매수" else "sell"
            submitted_qty = int(order.get("qty", 0) or 0) if isinstance(order, dict) else 0
            expected_price = int(order.get("expected_price", order.get("price", 0) if isinstance(order, dict) else 0) or 0)
            reserve_amount = submitted_qty * expected_price if side == "buy" and expected_price > 0 else 0
            reserve_cash = getattr(self, "_reserve_cash_for_buy", None)
            if callable(reserve_cash) and reserve_amount > 0:
                reserve_cash(code, reserve_amount)
            if code in getattr(self, "universe", {}):
                if side == "buy":
                    self.universe[code]["status"] = "buy_submitted"
                elif side == "sell":
                    self.universe[code]["status"] = "sell_submitted"
                self._set_pending_order(
                    code,
                    side,
                    "수동주문",
                    expected_price=expected_price,
                    submitted_qty=submitted_qty,
                    order_no=str(getattr(result, "order_no", "") or ""),
                )
                recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
                if callable(recompute_count):
                    recompute_count()
                self._sync_position_from_account(code)
            else:
                set_manual_pending = getattr(self, "_set_manual_pending_order", None)
                if callable(set_manual_pending):
                    set_manual_pending(
                        code,
                        side,
                        "수동주문",
                        expected_price=expected_price,
                        submitted_qty=submitted_qty,
                        order_no=str(getattr(result, "order_no", "") or ""),
                        reserved_cash=reserve_amount,
                    )
                    recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
                    if callable(recompute_count):
                        recompute_count()
                    self._sync_position_from_account(code)
                else:
                    self._set_pending_order(
                        code,
                        side,
                        "수동주문",
                        expected_price=expected_price,
                        submitted_qty=submitted_qty,
                        order_no=str(getattr(result, "order_no", "") or ""),
                    )
                    recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
                    if callable(recompute_count):
                        recompute_count()
                    self._sync_position_from_account(code)
        else:
            self.log(f"❌ 수동 주문 실패: {result.message}")
            if code in getattr(self, "universe", {}):
                self._clear_pending_order(code)
            else:
                clear_manual_pending = getattr(self, "_clear_manual_pending_order", None)
                if callable(clear_manual_pending):
                    clear_manual_pending(code)
                else:
                    self._clear_pending_order(code)
            recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
            if callable(recompute_count):
                recompute_count()
