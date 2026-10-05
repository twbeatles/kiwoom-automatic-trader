"""REST discovery reads and compatibility facades for WebSocket conditions."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from ._rest_helpers import _as_records, _pick, _payload_dict, _payload_records, _safe_float, _safe_int
from ._rest_transport import RestTransport
from .models import VIEvent


class RestDiscoveryMixin(RestTransport):
    """REST discovery reads and compatibility facades for WebSocket conditions."""

    def get_condition_list(self) -> List[Dict[str, Any]]:
        """Compatibility facade; condition search belongs to WebSocket."""
        ws = self._condition_ws()
        return ws.get_condition_list() if ws is not None else []

    def search_by_condition(self, condition_index: int, condition_name: str = "") -> List[Dict[str, Any]]:
        """Preserve existing UI/caller signature while delegating to WebSocket."""
        ws = self._condition_ws()
        return ws.search_by_condition(condition_index, condition_name) if ws is not None else []

    def get_volume_ranking(self, market: str = "0", count: int = 30) -> List[Dict[str, Any]]:
        """
        거래량 상위 종목 조회
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            count: 조회 개수
            
        Returns:
            거래량 순위 리스트
        """
        tr_code = self.TR_CODES["RANK_VOLUME"]
        data = {
            "mrkt_tp": self._rank_market_tp(market),
            "sort_tp": "1",
            "mang_stk_incls": "0",
            "crd_tp": "0",
            "trde_qty_tp": "0",
            "pric_tp": "0",
            "trde_prica_tp": "0",
            "mrkt_open_tp": "0",
            "stex_tp": "3",
        }
        result = self._request("POST", self.PATHS["rkinfo"], tr_code=tr_code, data=data)
        records = _payload_records(result, "tdy_trde_qty_upper", "output")
        rankings = []
        for i, item in enumerate(records[: max(1, min(int(count or 30), 100))]):
            rankings.append({
                "rank": i + 1,
                "code": self._stk_cd(_pick(item, "stk_cd")),
                "name": str(_pick(item, "stk_nm", default="") or ""),
                "current_price": _safe_int(_pick(item, "cur_prc"), absolute=True),
                "change_rate": _safe_float(_pick(item, "flu_rt", "chg_rt")),
                "volume": _safe_int(_pick(item, "trde_qty", "vol")),
                "volume_rate": _safe_float(_pick(item, "trde_tern_rt", "vol_rt")),
            })
        return rankings

    def get_fluctuation_ranking(self, market: str = "0", sort_type: str = "1", count: int = 30) -> List[Dict[str, Any]]:
        """
        등락률 상위 종목 조회
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            sort_type: "1"=상승률, "2"=하락률
            count: 조회 개수
            
        Returns:
            등락률 순위 리스트
        """
        tr_code = self.TR_CODES["RANK_FLUCTUATION"]
        official_sort = {"1": "1", "2": "3", "3": "3", "4": "4"}.get(str(sort_type), "1")
        data = {
            "mrkt_tp": self._rank_market_tp(market),
            "sort_tp": official_sort,
            "trde_qty_cnd": "0000",
            "stk_cnd": "0",
            "crd_cnd": "0",
            "updown_incls": "1",
            "pric_cnd": "0",
            "trde_prica_cnd": "0",
            "stex_tp": "3",
        }
        result = self._request("POST", self.PATHS["rkinfo"], tr_code=tr_code, data=data)
        records = _payload_records(result, "pred_pre_flu_rt_upper", "output")
        rankings = []
        for i, item in enumerate(records[: max(1, min(int(count or 30), 100))]):
            rankings.append({
                "rank": i + 1,
                "code": self._stk_cd(_pick(item, "stk_cd")),
                "name": str(_pick(item, "stk_nm", default="") or ""),
                "current_price": _safe_int(_pick(item, "cur_prc"), absolute=True),
                "change": _safe_int(_pick(item, "pred_pre", "chg_amt")),
                "change_rate": _safe_float(_pick(item, "flu_rt", "chg_rt")),
                "volume": _safe_int(_pick(item, "now_trde_qty", "trde_qty", "vol")),
            })
        return rankings

    def get_investor_trading(self, code: str) -> Dict[str, Any]:
        """
        투자자별 매매 동향 조회
        
        Args:
            code: 종목코드
            
        Returns:
            투자자별 순매수량/금액
        """
        tr_code = self.TR_CODES["INVESTOR_TRADING"]
        end_dt = datetime.now().strftime("%Y%m%d")
        strt_dt = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        data = {
            "stk_cd": code,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "orgn_prsm_unp_tp": "1",
            "for_prsm_unp_tp": "1",
        }
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data=data)
        records = _payload_records(result, "stk_orgn_trde_trnsn", "output")
        if not records:
            return {}
        row = records[0]
        institution_net = _safe_int(_pick(row, "orgn_daly_nettrde_qty", "inst_net"))
        foreign_net = _safe_int(_pick(row, "for_daly_nettrde_qty", "frgn_net"))
        individual_net = _safe_int(_pick(row, "indv_net"))
        return {
            "code": code,
            "individual_buy": _safe_int(_pick(row, "indv_buy")),
            "individual_sell": _safe_int(_pick(row, "indv_sell")),
            "foreign_buy": _safe_int(_pick(row, "frgn_buy")),
            "foreign_sell": _safe_int(_pick(row, "frgn_sell")),
            "institution_buy": _safe_int(_pick(row, "inst_buy")),
            "institution_sell": _safe_int(_pick(row, "inst_sell")),
            "individual_net": individual_net,
            "foreign_net": foreign_net,
            "institution_net": institution_net,
        }

    def get_program_trading(self, code: str) -> Dict[str, Any]:
        """
        프로그램 매매 동향 조회
        
        Args:
            code: 종목코드
            
        Returns:
            프로그램 순매수량/금액
        """
        tr_code = self.TR_CODES["PROGRAM_TRADING"]
        data = {
            "stk_cd": code,
            "amt_qty_tp": "2",
            "date": "",
        }
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data=data)
        records = _payload_records(result, "stk_daly_prm_trde_trnsn", "output")
        if not records:
            return {}
        row = records[0]
        buy_qty = _safe_int(_pick(row, "prm_buy_qty", "tot_buy"))
        sell_qty = _safe_int(_pick(row, "prm_sell_qty", "tot_sell"))
        net = _safe_int(_pick(row, "prm_netprps_qty", "net"), default=buy_qty - sell_qty)
        return {
            "code": code,
            "arb_buy": _safe_int(_pick(row, "arb_buy")),
            "arb_sell": _safe_int(_pick(row, "arb_sell")),
            "nonarb_buy": _safe_int(_pick(row, "nonarb_buy")),
            "nonarb_sell": _safe_int(_pick(row, "nonarb_sell")),
            "total_buy": buy_qty,
            "total_sell": sell_qty,
            "net": net,
        }

    def get_vi_status(self, market: str = "0") -> List[VIEvent]:
        """
        변동성완화장치(VI) 발동 현황 조회 (ka10054)
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            
        Returns:
            VIEvent 리스트
        """
        tr_code = self.TR_CODES["VI_STATUS"]
        market_map = {"0": "000", "1": "001", "2": "101"}
        data = {
            "mrkt_tp": market_map.get(str(market), "000"),
            "bf_mkrt_tp": "0",
            "motn_tp": "0",
            "skip_stk": "000000000",
            "trde_qty_tp": "0",
            "min_trde_qty": "0",
            "max_trde_qty": "0",
            "trde_prica_tp": "0",
            "min_trde_prica": "0",
            "max_trde_prica": "0",
            "motn_drc": "0",
            "stex_tp": "3",
            "stk_cd": "",
        }
        result = self._request("POST", self.PATHS["stkinfo"], tr_code=tr_code, data=data)
        
        events: List[VIEvent] = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "motn_stk", "output")
            for item in output_list:
                events.append(VIEvent(
                    code=str(item.get("stk_cd") or "").strip(),
                    name=str(item.get("stk_nm") or "").strip(),
                    vi_type=str(item.get("viaplc_tp") or item.get("vi_tp") or "").strip(),
                    vi_status=str(item.get("vi_st") or "발동").strip(),
                    trigger_time=str(item.get("trde_cntr_proc_time") or item.get("trg_tm") or "").strip(),
                    release_time=str(item.get("virelis_time") or item.get("rls_tm") or "").strip(),
                    trigger_price=_safe_int(_pick(item, "motn_pric", "trg_prc"), absolute=True),
                    base_price=_safe_int(_pick(item, "static_stdpc", "dynm_stdpc", "base_prc"), absolute=True),
                    deviance_rate=_safe_float(_pick(item, "static_dispty_rt", "dynm_dispty_rt", "dev_rt")),
                ))
        return events

    def get_broker_stock_trend(
        self, code: str, member_code: str = "", start_date: str = "", end_date: str = ""
    ) -> List[Dict[str, Any]]:
        """증권사별 종목 매매동향 조회 (ka10078 /api/dostk/mrkcond).

        member_code는 ka10102 회원사 리스트의 코드 (빈 값이면 전체).
        """
        if not str(code or "").strip():
            return []
        today = datetime.now().strftime("%Y%m%d")
        data = {
            "mbrm_cd": str(member_code or ""),
            "stk_cd": str(code),
            "strt_dt": str(start_date or today),
            "end_dt": str(end_date or start_date or today),
        }
        try:
            result = self._request("POST", self.PATHS["mrkcond"], tr_code=self.TR_CODES["BROKER_STOCK_TREND"], data=data)
        except Exception as exc:
            self.logger.warning(f"증권사 매매동향 조회 예외: {exc}")
            return []
        if not result or result.get("return_code") != 0:
            return []
        rows = _payload_records(result, "sec_stk_trde_trend", "output")
        trend: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            buy_qty = _safe_int(_pick(item, "buy_qty"))
            sell_qty = _safe_int(_pick(item, "sell_qty"))
            trend.append({
                "date": str(_pick(item, "dt", "date", default="") or ""),
                "current_price": _safe_int(_pick(item, "cur_prc"), absolute=True),
                "change": _safe_int(_pick(item, "pred_pre", "chg_amt")),
                "change_rate": _safe_float(_pick(item, "flu_rt", "chg_rt")),
                "acc_volume": _safe_int(_pick(item, "acc_trde_qty", "acc_vol")),
                "net_buy_qty": _safe_int(_pick(item, "netprps_qty", "net"), default=buy_qty - sell_qty),
                "buy_qty": buy_qty,
                "sell_qty": sell_qty,
            })
        return trend

    def request_condition_realtime(self, condition_index: int) -> List[Dict[str, Any]]:
        """Compatibility facade for the initial realtime condition snapshot."""
        ws = self._condition_ws()
        return ws.request_condition_realtime(condition_index) if ws is not None else []

    def stop_condition_realtime(self, condition_index: int) -> bool:
        """Compatibility facade for the one-shot condition cancellation."""
        ws = self._condition_ws()
        return ws.stop_condition_realtime(condition_index) if ws is not None else False

    def _parse_condition_stock_rows(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Keep the legacy parser entry point; implementation lives with WS."""
        from .websocket_client import KiwoomWebSocketClient
        return KiwoomWebSocketClient._parse_condition_stock_rows(result)
