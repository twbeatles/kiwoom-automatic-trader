"""Market-data reads (SRP: quotes/charts/orderbook/index)."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ._rest_helpers import _pick, _payload_dict, _payload_records, _safe_float, _safe_int
from ._rest_transport import RestTransport
from .models import DailyOHLC, OrderBook, SectorQuote, StockQuote, TickCandle


class RestMarketMixin(RestTransport):
    """Market-data reads (SRP: quotes/charts/orderbook/index)."""

    def get_stock_quote(self, code: str) -> Optional[StockQuote]:
        """
        주식 현재가 조회
        
        Args:
            code: 종목코드 (예: "005930")
            
        Returns:
            StockQuote 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["STOCK_CURRENT"]
        result = self._request("POST", self.PATHS["stkinfo"], tr_code=tr_code, data={"stk_cd": code})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            
            return StockQuote(
                code=code,
                name=str(_pick(output, "stk_nm", default="")),
                current_price=_safe_int(_pick(output, "cur_prc"), absolute=True),
                change=_safe_int(_pick(output, "pred_pre", "chg_amt")),
                change_rate=_safe_float(_pick(output, "flu_rt", "chg_rt")),
                open_price=_safe_int(_pick(output, "open_pric", "open_prc"), absolute=True),
                high_price=_safe_int(_pick(output, "high_pric", "high_prc"), absolute=True),
                low_price=_safe_int(_pick(output, "low_pric", "low_prc"), absolute=True),
                volume=_safe_int(_pick(output, "trde_qty", "acc_vol")),
                prev_close=_safe_int(_pick(output, "base_pric", "yes_prc"), absolute=True),
                ask_price=_safe_int(_pick(output, "ask_prc", "sel_fpr_bid"), absolute=True),
                bid_price=_safe_int(_pick(output, "bid_prc", "buy_fpr_bid"), absolute=True),
                timestamp=str(_pick(output, "stk_tm", default="")),
                market_type=self._parse_market_type(output),
                sector=str(_pick(output, "sect_nm", default="기타") or "기타"),
            )
        
        return None

    def get_order_book(self, code: str) -> Optional[OrderBook]:
        """
        호가 정보 조회
        
        Args:
            code: 종목코드
            
        Returns:
            OrderBook 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["STOCK_HOGA"]
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data={"stk_cd": code})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            ordinals = ("1th", "2th", "3th", "4th", "5th", "6th", "7th", "8th", "9th", "10th")
            
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            for i, ordinal in enumerate(ordinals, start=1):
                if i == 1:
                    ask_prices.append(_safe_int(_pick(output, "sel_fpr_bid", f"ask_prc{i}"), absolute=True))
                    ask_volumes.append(_safe_int(_pick(output, "sel_fpr_req", f"ask_vol{i}")))
                    bid_prices.append(_safe_int(_pick(output, "buy_fpr_bid", f"bid_prc{i}"), absolute=True))
                    bid_volumes.append(_safe_int(_pick(output, "buy_fpr_req", f"bid_vol{i}")))
                    continue
                ask_prices.append(_safe_int(_pick(output, f"sel_{ordinal}_pre_bid", f"ask_prc{i}"), absolute=True))
                ask_volumes.append(_safe_int(_pick(output, f"sel_{ordinal}_pre_req", f"ask_vol{i}")))
                bid_prices.append(_safe_int(_pick(output, f"buy_{ordinal}_pre_bid", f"bid_prc{i}"), absolute=True))
                bid_volumes.append(_safe_int(_pick(output, f"buy_{ordinal}_pre_req", f"bid_vol{i}")))
            
            return OrderBook(
                code=code,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                total_ask_volume=_safe_int(_pick(output, "tot_sel_req", "tot_ask_vol")),
                total_bid_volume=_safe_int(_pick(output, "tot_buy_req", "tot_bid_vol")),
                timestamp=str(_pick(output, "bid_req_base_tm", "stk_tm", default="")),
            )
        
        return None

    def get_daily_chart(self, code: str, count: int = 60) -> List[DailyOHLC]:
        """
        일봉 차트 데이터 조회
        
        Args:
            code: 종목코드
            count: 조회할 봉 개수 (최대 100)
            
        Returns:
            DailyOHLC 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_DAILY"]
        data = {
            "stk_cd": code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_dt_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "dt", "date", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
                ))
        
        return candles

    def get_minute_chart(self, code: str, interval: int = 1, count: int = 60) -> List[DailyOHLC]:
        """
        분봉 차트 데이터 조회
        
        Args:
            code: 종목코드
            interval: 분봉 간격 (1, 3, 5, 10, 15, 30, 60)
            count: 조회할 봉 개수 (최대 100)
            
        Returns:
            DailyOHLC 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_MINUTE"]
        data = {
            "stk_cd": code,
            "tic_scope": str(interval),
            "upd_stkpc_tp": "1",
            "base_dt": datetime.now().strftime("%Y%m%d"),
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_min_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "cntr_tm", "datetime", "dt", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
                ))
        
        return candles

    def get_weekly_chart(self, code: str, count: int = 52) -> List[DailyOHLC]:
        """주봉 차트 데이터 조회"""
        tr_code = self.TR_CODES["STOCK_WEEKLY"]
        data = {
            "stk_cd": code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_wk_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "dt", "date", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
                ))
        
        return candles

    def get_tick_chart(self, code: str, count: int = 60) -> List[TickCandle]:
        """
        틱 차트 데이터 조회 (ka10079)
        
        Args:
            code: 종목코드
            count: 조회할 틱 개수 (최대 100)
            
        Returns:
            TickCandle 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_TICK"]
        data = {
            "stk_cd": code,
            "tic_scope": "1",
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles: List[TickCandle] = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_tic_chart_qry", "output")[: max(1, min(count, 100))]
            for item in output_list:
                candles.append(TickCandle(
                    time=str(item.get("time") or item.get("stk_tm") or "").strip(),
                    price=_safe_int(item.get("cur_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", item.get("cntr_qty", 0))),
                    change=_safe_int(item.get("chg_amt", 0)),
                    change_rate=_safe_float(item.get("chg_rt", 0.0)),
                    side=str(item.get("cntr_tp") or "").strip(),
                    cum_volume=_safe_int(item.get("acc_vol", 0)),
                ))
        return candles

    def get_stock_name(self, code: str) -> str:
        """종목명 조회"""
        quote = self.get_stock_quote(code)
        return quote.name if quote else ""

    def get_market_status(self) -> Dict[str, Any]:
        """장 상태는 공식 REST TR이 없고 WebSocket REAL `0s`(장시작시간)만 존재한다."""
        return {}

    def get_index_quote(self, index_code: str) -> Dict[str, Any]:
        """업종현재가 조회 (ka20001 /api/dostk/sect)."""
        if not index_code:
            return {}
        tr_code = self.TR_CODES["INDEX_QUOTE"]
        data = {
            "mrkt_tp": self._index_market_tp(index_code),
            "inds_cd": str(index_code),
        }
        result = self._request("POST", self.PATHS["sect"], tr_code=tr_code, data=data)
        if not result:
            return {}
        output = _payload_dict(result, "output")
        current = _safe_float(_pick(output, "cur_prc", "cur_idx"))
        change = _safe_float(_pick(output, "pred_pre", "chg_idx"))
        change_rate = _safe_float(_pick(output, "flu_rt", "chg_rt"))
        if current == 0.0 and change == 0.0 and change_rate == 0.0 and not _pick(output, "cur_prc", "cur_idx"):
            return {}
        return {
            "idx_cd": str(index_code),
            "idx_nm": str(_pick(output, "idx_nm", "inds_nm", default="") or ""),
            "cur_idx": current,
            "chg_idx": change,
            "chg_rt": change_rate,
            "open_idx": _safe_float(_pick(output, "open_pric", "open_idx")),
            "high_idx": _safe_float(_pick(output, "high_pric", "high_idx")),
            "low_idx": _safe_float(_pick(output, "low_pric", "low_idx")),
            "acc_vol": _safe_int(_pick(output, "trde_qty", "acc_vol")),
            "acc_trd_val": _safe_int(_pick(output, "trde_prica", "acc_trd_val")),
            "cur_prc": current,
            "flu_rt": change_rate,
        }

    def get_market_indexes(self) -> List[SectorQuote]:
        """
        주요 시장 지수 시세 조회 (코스피: 001, 코스닥: 101, 코스피200: 201)
        
        Returns:
            SectorQuote 리스트
        """
        major_indexes = [
            ("001", "코스피"),
            ("101", "코스닥"),
            ("201", "코스피200"),
        ]
        quotes: List[SectorQuote] = []
        for idx_cd, name in major_indexes:
            try:
                res = self.get_index_quote(idx_cd)
                if res:
                    quotes.append(SectorQuote(
                        code=idx_cd,
                        name=str(_pick(res, "idx_nm", default="") or name),
                        current_price=_safe_float(_pick(res, "cur_idx", "cur_prc")),
                        change=_safe_float(_pick(res, "chg_idx", "pred_pre")),
                        change_rate=_safe_float(_pick(res, "chg_rt", "flu_rt")),
                        open_price=_safe_float(_pick(res, "open_idx", "open_pric")),
                        high_price=_safe_float(_pick(res, "high_idx", "high_pric")),
                        low_price=_safe_float(_pick(res, "low_idx", "low_pric")),
                        volume=_safe_int(_pick(res, "acc_vol", "trde_qty")),
                        volume_amount=_safe_int(_pick(res, "acc_trd_val", "trde_prica")),
                    ))
            except Exception as exc:
                self.logger.warning(f"지수({idx_cd}) 조회 실패: {exc}")
                continue
        return quotes
