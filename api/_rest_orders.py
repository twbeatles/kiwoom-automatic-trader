"""Order writes (SRP: send/modify/cancel + market/limit conveniences)."""

from ._rest_transport import RestTransport
from .models import OrderResult, OrderType, PriceType


class RestOrderMixin(RestTransport):
    """Order writes (SRP: send/modify/cancel + market/limit conveniences)."""

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
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "stk_cd": code,
            "ord_tp": order_type.value,
            "ord_qty": quantity,
            "ord_prc": price if price_type == PriceType.LIMIT else 0,
            "prc_tp": price_type.value
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
        if result:
            return_code = result.get("return_code", -1)
            
            if return_code == 0:
                output = result.get("output", {})
                return OrderResult(
                    success=True,
                    order_no=output.get("ord_no", ""),
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
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "org_ord_no": order_no,
            "stk_cd": code,
            "ord_qty": quantity
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
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
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "org_ord_no": order_no,
            "stk_cd": code,
            "ord_qty": quantity,
            "ord_prc": price,
            "prc_tp": price_type.value
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
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
