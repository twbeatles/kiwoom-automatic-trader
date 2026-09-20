"""Account reads (SRP: balances/positions/deposits/orders history)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ._rest_helpers import (
    _as_records, _order_no_from_result, _parse_order_side,
    _pick, _payload_dict, _payload_records, _safe_float, _safe_int,
)
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
            "qry_tp": "1",
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
        }
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            return AccountInfo(
                account_no=account_no,
                deposit=_safe_int(_pick(output, "prsm_dpst_aset_amt", "deposit")),
                available_amount=_safe_int(_pick(output, "ord_alow_amt", "ord_psbl_amt")),
                total_buy_amount=_safe_int(_pick(output, "tot_pur_amt", "tot_buy_amt")),
                total_eval_amount=_safe_int(_pick(output, "tot_evlt_amt", "tot_eval_amt")),
                total_profit=_safe_int(_pick(output, "tot_evlt_pl", "tot_eval_pl")),
                total_profit_rate=_safe_float(_pick(output, "tot_prft_rt", "tot_eval_pl_rt")),
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
            "qry_tp": "1",
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
        }
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        
        if not result:
            return None
        if result.get("return_code") != 0:
            return None

        positions = []
        stocks = _payload_records(result, "acnt_evlt_remn_indv_tot", "stocks", "output")

        for item in stocks:
            positions.append(Position(
                code=str(_pick(item, "stk_cd", default="")),
                name=str(_pick(item, "stk_nm", default="")),
                quantity=_safe_int(_pick(item, "rmnd_qty", "hold_qty")),
                available_qty=_safe_int(_pick(item, "trde_able_qty", "sell_psbl_qty")),
                buy_price=_safe_int(_pick(item, "pur_pric", "buy_prc")),
                current_price=_safe_int(_pick(item, "cur_prc"), absolute=True),
                buy_amount=_safe_int(_pick(item, "pur_amt", "buy_amt")),
                eval_amount=_safe_int(_pick(item, "evlt_amt", "eval_amt")),
                profit=_safe_int(_pick(item, "evltv_prft", "eval_pl")),
                profit_rate=_safe_float(_pick(item, "prft_rt", "eval_pl_rt")),
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
            "all_stk_tp": "0",
            "trde_tp": "0",
            "stex_tp": "0",
        }

        try:
            result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"미체결 주문 조회 예외: {exc}")
            return []

        if not result or result.get("return_code") != 0:
            return []

        rows = _payload_records(result, "oso", "output")

        orders: List[OpenOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                order_no = str(item.get("ord_no") or item.get("org_ord_no") or "").strip()
                code = str(item.get("stk_cd") or "").strip()
                if not order_no or not code:
                    continue
                orders.append(
                    OpenOrder(
                        order_no=order_no,
                        code=code,
                        side=_parse_order_side(item),
                        quantity=_safe_int(item.get("ord_qty", 0)),
                        remaining_qty=_safe_int(
                            _pick(item, "oso_qty", "unexec_qty", "not_cncl_qty", "rmn_qty", default=0)
                        ),
                        price=_safe_int(_pick(item, "ord_pric", "ord_prc", default=0), absolute=True),
                        status=str(item.get("ord_stt") or item.get("ord_st") or item.get("cnf_tp") or "").strip(),
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
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data={})
        
        if result and result.get("return_code") == 0:
            accounts: List[str] = []
            for key in ("acctNo", "accounts", "output", "acnt_no"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    accounts.append(value.strip())
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            accounts.append(item.strip())
                        elif isinstance(item, dict):
                            text = str(item.get("acctNo") or item.get("acnt_no") or item.get("account") or "").strip()
                            if text:
                                accounts.append(text)
                if accounts:
                    break
            return accounts
        
        return []

    def get_deposit_detail(self, account_no: str) -> Optional[DepositDetail]:
        """
        예수금 상세 정보 조회 (kt00001)
        
        Args:
            account_no: 계좌번호
            
        Returns:
            DepositDetail 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_DEPOSIT"]
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data={"qry_tp": "3"})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            return DepositDetail(
                account_no=account_no,
                deposit=_safe_int(_pick(output, "entr", "deposit")),
                d1_deposit=_safe_int(_pick(output, "d1_entra", "d1_deposit", "d1_estm_dps")),
                d2_deposit=_safe_int(_pick(output, "d2_entra", "d2_deposit", "d2_estm_dps")),
                withdrawable_amount=_safe_int(_pick(output, "pymn_alow_amt", "draw_psbl_amt", "wdrw_psbl_amt")),
                order_available_amount=_safe_int(_pick(output, "ord_alow_amt", "ord_psbl_amt", "ord_psbl_cash")),
                receivable_amount=_safe_int(_pick(output, "ch_uncla", "rcvbl_amt")),
                collateral_amount=_safe_int(_pick(output, "repl_amt", "subst_amt")),
                stock_eval_amount=_safe_int(_pick(output, "tot_eval_amt", "stk_eval_amt")),
                total_assets=_safe_int(_pick(output, "tot_asst_amt", "prsm_dpst_aset_amt")),
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
            "qry_tp": "0",
            "sell_tp": "0",
            "stex_tp": "0",
        }
        
        try:
            result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"체결 주문 조회 예외: {exc}")
            return []
            
        if not result or result.get("return_code") != 0:
            return []
            
        rows = _payload_records(result, "cntr", "output")
                
        orders: List[ExecutedOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            orders.append(ExecutedOrder(
                exec_no=str(item.get("exec_no") or item.get("cntr_no") or "").strip(),
                order_no=str(item.get("ord_no") or "").strip(),
                code=str(item.get("stk_cd") or "").strip(),
                name=str(item.get("stk_nm") or "").strip(),
                side=_parse_order_side(item),
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
