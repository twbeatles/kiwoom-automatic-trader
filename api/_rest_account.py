"""Account reads (SRP: balances/positions/deposits/orders history)."""

from datetime import datetime
from typing import List, Optional

from ._rest_helpers import _safe_float, _safe_int
from ._rest_transport import RestTransport
from .models import AccountInfo, DepositDetail, ExecutedOrder, OpenOrder, Position


class RestAccountMixin(RestTransport):
    """Account reads (SRP: balances/positions/deposits/orders history)."""

    def get_account_info(self, account_no: str) -> Optional[AccountInfo]:
        """
        계좌 평가 정보 조회
        
        Args:
            account_no: 계좌번호
            
        Returns:
            AccountInfo 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_BALANCE"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return AccountInfo(
                account_no=account_no,
                deposit=_safe_int(output.get("deposit", 0)),
                available_amount=_safe_int(output.get("ord_psbl_amt", 0)),
                total_buy_amount=_safe_int(output.get("tot_buy_amt", 0)),
                total_eval_amount=_safe_int(output.get("tot_eval_amt", 0)),
                total_profit=_safe_int(output.get("tot_eval_pl", 0)),
                total_profit_rate=_safe_float(output.get("tot_eval_pl_rt", 0))
            )
        
        return None

    def get_positions(self, account_no: str) -> Optional[List[Position]]:
        """
        보유 종목 조회
        
        Args:
            account_no: 계좌번호
            
        Returns:
            Position 리스트
        """
        tr_code = self.TR_CODES["ACCOUNT_BALANCE"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", tr_code=tr_code, data=data)
        
        if not result:
            return None
        if result.get("return_code") != 0:
            return None

        positions = []
        stocks = result.get("stocks", [])

        for item in stocks:
            positions.append(Position(
                code=item.get("stk_cd", ""),
                name=item.get("stk_nm", ""),
                quantity=_safe_int(item.get("hold_qty", 0)),
                available_qty=_safe_int(item.get("sell_psbl_qty", 0)),
                buy_price=_safe_int(item.get("buy_prc", 0)),
                current_price=_safe_int(item.get("cur_prc", 0), absolute=True),
                buy_amount=_safe_int(item.get("buy_amt", 0)),
                eval_amount=_safe_int(item.get("eval_amt", 0)),
                profit=_safe_int(item.get("eval_pl", 0)),
                profit_rate=_safe_float(item.get("eval_pl_rt", 0))
            ))

        return positions

    @property
    def supports_open_orders(self) -> bool:
        return True

    def get_open_orders(self, account_no: str) -> List[OpenOrder]:
        """미체결 주문 조회.

        키움 REST TR `ka10075`(미체결요청) 기반.
        여러 필드명 후보를 허용하고 실패 시 빈 리스트를 반환하여 안전하게 동작하도록 한다.
        """
        tr_code = self.TR_CODES["ORDER_OPEN"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
        }

        try:
            result = self._request("POST", "/api/dostk/ordunfilled", tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"미체결 주문 조회 예외: {exc}")
            return []

        if not result or result.get("return_code") != 0:
            return []

        rows = result.get("output", [])
        if not isinstance(rows, list):
            # 단건 응답인 경우 단일 dict를 리스트로 정규화
            if isinstance(rows, dict):
                rows = [rows]
            else:
                return []

        orders: List[OpenOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                order_no = str(item.get("ord_no") or item.get("org_ord_no") or "").strip()
                code = str(item.get("stk_cd") or "").strip()
                if not order_no or not code:
                    continue
                raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
                side = "buy" if raw_side == "1" else ("sell" if raw_side == "2" else raw_side)
                orders.append(
                    OpenOrder(
                        order_no=order_no,
                        code=code,
                        side=side,
                        quantity=_safe_int(item.get("ord_qty", 0)),
                        remaining_qty=_safe_int(
                            item.get("unexec_qty", item.get("not_cncl_qty", item.get("rmn_qty", 0)))
                        ),
                        price=_safe_int(item.get("ord_prc", 0), absolute=True),
                        status=str(item.get("ord_st") or item.get("cnf_tp") or "").strip(),
                    )
                )
            except Exception as exc:
                self.logger.warning(f"미체결 주문 파싱 실패(건 건너뜀): {exc}")
                continue

        return orders

    def get_account_list(self) -> List[str]:
        """
        계좌 목록 조회
        
        Returns:
            계좌번호 리스트
        """
        tr_code = self.TR_CODES["ACCOUNT_LIST"]
        result = self._request("POST", "/api/dostk/acntlist", tr_code=tr_code, data={})
        
        if result and result.get("return_code") == 0:
            return result.get("accounts", [])
        
        return []

    def get_deposit_detail(self, account_no: str) -> Optional[DepositDetail]:
        """
        예수금 상세 정보 조회 (ka30002)
        
        Args:
            account_no: 계좌번호
            
        Returns:
            DepositDetail 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_DEPOSIT"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntdeposit", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return DepositDetail(
                account_no=account_no,
                deposit=_safe_int(output.get("deposit", 0)),
                d1_deposit=_safe_int(output.get("d1_deposit", output.get("d1_estm_dps", 0))),
                d2_deposit=_safe_int(output.get("d2_deposit", output.get("d2_estm_dps", 0))),
                withdrawable_amount=_safe_int(output.get("draw_psbl_amt", output.get("wdrw_psbl_amt", 0))),
                order_available_amount=_safe_int(output.get("ord_psbl_amt", output.get("ord_psbl_cash", 0))),
                receivable_amount=_safe_int(output.get("rcvbl_amt", 0)),
                collateral_amount=_safe_int(output.get("subst_amt", 0)),
                stock_eval_amount=_safe_int(output.get("tot_eval_amt", output.get("stk_eval_amt", 0))),
                total_assets=_safe_int(output.get("tot_asst_amt", 0)),
            )
        return None

    def get_executed_orders(self, account_no: str, date: str = "") -> List[ExecutedOrder]:
        """
        당일 체결 주문 목록 조회 (ka10076)
        
        Args:
            account_no: 계좌번호
            date: 조회일자 (YYYYMMDD, 기본값: 당일)
            
        Returns:
            ExecutedOrder 리스트
        """
        tr_code = self.TR_CODES["ORDER_EXECUTED"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "inqr_dt": date or datetime.now().strftime("%Y%m%d"),
        }
        
        try:
            result = self._request("POST", "/api/dostk/ordexecuted", tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"체결 주문 조회 예외: {exc}")
            return []
            
        if not result or result.get("return_code") != 0:
            return []
            
        rows = result.get("output", [])
        if not isinstance(rows, list):
            if isinstance(rows, dict):
                rows = [rows]
            else:
                return []
                
        orders: List[ExecutedOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
            side = "buy" if raw_side == "1" else ("sell" if raw_side == "2" else raw_side)
            orders.append(ExecutedOrder(
                exec_no=str(item.get("exec_no") or item.get("cntr_no") or "").strip(),
                order_no=str(item.get("ord_no") or "").strip(),
                code=str(item.get("stk_cd") or "").strip(),
                name=str(item.get("stk_nm") or "").strip(),
                side=side,
                order_type=str(item.get("prc_tp") or "").strip(),
                quantity=_safe_int(item.get("ord_qty", 0)),
                exec_quantity=_safe_int(item.get("exec_qty", item.get("cntr_qty", 0))),
                exec_price=_safe_int(item.get("exec_prc", item.get("cntr_prc", 0)), absolute=True),
                exec_amount=_safe_int(item.get("exec_amt", item.get("cntr_amt", 0))),
                exec_time=str(item.get("exec_tm") or item.get("cntr_tm") or "").strip(),
                fee=_safe_int(item.get("fee", 0)),
                tax=_safe_int(item.get("tax", 0)),
            ))
        return orders
