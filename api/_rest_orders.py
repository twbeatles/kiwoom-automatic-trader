"""Order writes (SRP: send/modify/cancel + market/limit conveniences)."""

from typing import Any, Dict, List, Optional

from ._rest_helpers import (
    _order_no_from_result, _parse_order_side,
    _pick, _payload_dict, _safe_int, _trde_tp,
)
from ._rest_transport import RestTransport
from .models import OrderResult, OrderType, PriceType


class RestOrderMixin(RestTransport):
    """Order writes (SRP: send/modify/cancel + market/limit conveniences)."""

    @staticmethod
    def _parse_order_side(item: Dict[str, Any]) -> str:
        """Backward-compat alias (canonical: `_rest_helpers._parse_order_side`)."""
        return _parse_order_side(item)

    @staticmethod
    def _order_no_from_result(result: Optional[Dict[str, Any]]) -> str:
        """Backward-compat alias (canonical: `_rest_helpers._order_no_from_result`)."""
        return _order_no_from_result(result)

    def send_order(self, 
                   account_no: str,
                   code: str,
                   order_type: OrderType,
                   quantity: int,
                   price: int = 0,
                   price_type: PriceType = PriceType.LIMIT) -> OrderResult:
        """
        주식 주문 전송 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)
        
        Args:
            account_no: 계좌번호
            code: 종목코드
            order_type: 주문유형 (매수/매도)
            quantity: 주문수량
            price: 주문가격 (시장가 주문 시 0)
            price_type: 호가유형 (지정가/시장가 등)
            
        Returns:
            OrderResult 객체
        """
        tr_code = self.TR_CODES["ORDER_BUY"] if order_type == OrderType.BUY else self.TR_CODES["ORDER_SELL"]
        trde_tp = _trde_tp(price_type)
        data = {
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "stk_cd": code,
            "ord_qty": str(int(quantity)),
            "trde_tp": trde_tp,
            "ord_uv": "" if trde_tp == "3" else str(int(price or 0)),
            "cond_uv": "",
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
        if result:
            return_code = result.get("return_code", -1)
            
            if return_code == 0:
                return OrderResult(
                    success=True,
                    order_no=_order_no_from_result(result),
                    code=code,
                    order_type=order_type.value,
                    quantity=quantity,
                    price=price,
                    message="주문 전송 성공"
                )
            else:
                return OrderResult(
                    success=False,
                    code=code,
                    order_type=order_type.value,
                    quantity=quantity,
                    price=price,
                    message=result.get("return_msg", "주문 실패"),
                    error_code=return_code
                )
        
        return OrderResult(
            success=False,
            code=code,
            message="네트워크 오류",
            error_code=-1
        )

    def buy_market(self, account_no: str, code: str, quantity: int) -> OrderResult:
        """시장가 매수"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=0,
            price_type=PriceType.MARKET
        )

    def sell_market(self, account_no: str, code: str, quantity: int) -> OrderResult:
        """시장가 매도"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=0,
            price_type=PriceType.MARKET
        )

    def buy_limit(self, account_no: str, code: str, quantity: int, price: int) -> OrderResult:
        """지정가 매수"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=price,
            price_type=PriceType.LIMIT
        )

    def sell_limit(self, account_no: str, code: str, quantity: int, price: int) -> OrderResult:
        """지정가 매도"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=price,
            price_type=PriceType.LIMIT
        )

    def cancel_order(self, account_no: str, order_no: str, code: str, quantity: int) -> OrderResult:
        """주문 취소 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)"""
        tr_code = self.TR_CODES["ORDER_CANCEL"]
        data = {
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "orig_ord_no": str(order_no),
            "stk_cd": code,
            "cncl_qty": str(int(quantity)),
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            return OrderResult(
                success=True,
                order_no=order_no,
                code=code,
                message="주문 취소 성공"
            )
        
        return OrderResult(
            success=False,
            order_no=order_no,
            code=code,
            message=result.get("return_msg", "취소 실패") if result else "네트워크 오류"
        )

    def modify_order(self, account_no: str, order_no: str, code: str, quantity: int, price: int, price_type: PriceType = PriceType.LIMIT) -> OrderResult:
        """주문 정정 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)"""
        tr_code = self.TR_CODES["ORDER_MODIFY"]
        data = {
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "orig_ord_no": str(order_no),
            "stk_cd": code,
            "mdfy_qty": str(int(quantity)),
            "mdfy_uv": str(int(price or 0)),
            "mdfy_cond_uv": "",
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            return OrderResult(
                success=True,
                order_no=order_no,
                code=code,
                quantity=quantity,
                price=price,
                message="주문 정정 성공"
            )
        
        return OrderResult(
            success=False,
            order_no=order_no,
            code=code,
            quantity=quantity,
            price=price,
            message=result.get("return_msg", "정정 실패") if result else "네트워크 오류"
        )
