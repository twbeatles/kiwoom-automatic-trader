"""Discovery reads (SRP: conditions/rankings/flows/VI)."""

from typing import Any, Dict, List

from ._rest_helpers import _safe_float, _safe_int
from ._rest_transport import RestTransport
from .models import VIEvent


class RestDiscoveryMixin(RestTransport):
    """Discovery reads (SRP: conditions/rankings/flows/VI)."""

    def get_condition_list(self) -> List[Dict[str, Any]]:
        """
        조건검색식 목록 조회
        
        Returns:
            [{"index": 0, "name": "조건식명"}, ...]
        """
        tr_code = self.TR_CODES["CONDITION_LIST"]
        result = self._request("POST", "/api/dostk/condition/list", tr_code=tr_code, data={})
        
        conditions = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                conditions.append({
                    "index": _safe_int(item.get("cond_idx", 0)),
                    "name": item.get("cond_nm", "")
                })
        
        return conditions

    def search_by_condition(self, condition_index: int, condition_name: str = "") -> List[Dict[str, Any]]:
        """
        조건검색 실행
        
        Args:
            condition_index: 조건식 인덱스
            condition_name: 조건식 이름 (옵션)
            
        Returns:
            [{"code": "종목코드", "name": "종목명"}, ...]
        """
        tr_code = self.TR_CODES["CONDITION_SEARCH"]
        data = {
            "cond_idx": condition_index,
            "cond_nm": condition_name
        }
        
        result = self._request("POST", "/api/dostk/condition/search", tr_code=tr_code, data=data)
        
        stocks = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                stocks.append({
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0))
                })
        
        return stocks

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
            "tr_cd": tr_code,
            "mkt_tp": market,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/volume", tr_code=tr_code, data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0)),
                    "volume_rate": _safe_float(item.get("vol_rt", 0))
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
        data = {
            "tr_cd": tr_code,
            "mkt_tp": market,
            "sort_tp": sort_type,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/fluctuation", tr_code=tr_code, data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change": _safe_int(item.get("chg_amt", 0)),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0))
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
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/investor", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "individual_buy": _safe_int(output.get("indv_buy", 0)),
                "individual_sell": _safe_int(output.get("indv_sell", 0)),
                "foreign_buy": _safe_int(output.get("frgn_buy", 0)),
                "foreign_sell": _safe_int(output.get("frgn_sell", 0)),
                "institution_buy": _safe_int(output.get("inst_buy", 0)),
                "institution_sell": _safe_int(output.get("inst_sell", 0)),
                "individual_net": _safe_int(output.get("indv_net", 0)),
                "foreign_net": _safe_int(output.get("frgn_net", 0)),
                "institution_net": _safe_int(output.get("inst_net", 0))
            }
        
        return {}

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
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/program", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "arb_buy": _safe_int(output.get("arb_buy", 0)),
                "arb_sell": _safe_int(output.get("arb_sell", 0)),
                "nonarb_buy": _safe_int(output.get("nonarb_buy", 0)),
                "nonarb_sell": _safe_int(output.get("nonarb_sell", 0)),
                "total_buy": _safe_int(output.get("tot_buy", 0)),
                "total_sell": _safe_int(output.get("tot_sell", 0)),
                "net": _safe_int(output.get("net", 0))
            }
        
        return {}

    def get_vi_status(self, market: str = "0") -> List[VIEvent]:
        """
        변동성완화장치(VI) 발동 현황 조회 (ka20009)
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            
        Returns:
            VIEvent 리스트
        """
        tr_code = self.TR_CODES["VI_STATUS"]
        data = {
            "tr_cd": tr_code,
            "mkt_tp": market,
        }
        
        result = self._request("POST", "/api/dostk/vi/status", tr_code=tr_code, data=data)
        
        events: List[VIEvent] = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                events.append(VIEvent(
                    code=str(item.get("stk_cd") or "").strip(),
                    name=str(item.get("stk_nm") or "").strip(),
                    vi_type=str(item.get("vi_tp") or "").strip(),
                    vi_status=str(item.get("vi_st") or "발동").strip(),
                    trigger_time=str(item.get("trg_tm") or "").strip(),
                    release_time=str(item.get("rls_tm") or "").strip(),
                    trigger_price=_safe_int(item.get("trg_prc", 0), absolute=True),
                    base_price=_safe_int(item.get("base_prc", 0), absolute=True),
                    deviance_rate=_safe_float(item.get("dev_rt", 0.0)),
                ))
        return events
