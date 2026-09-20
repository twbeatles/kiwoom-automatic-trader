"""Market-data reads (SRP: quotes/charts/orderbook/index)."""

from typing import Any, Dict, List, Optional

from ._rest_helpers import _safe_float, _safe_int
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
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkprice", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return StockQuote(
                code=code,
                name=output.get("stk_nm", ""),
                current_price=_safe_int(output.get("cur_prc", 0), absolute=True),
                change=_safe_int(output.get("chg_amt", 0)),
                change_rate=_safe_float(output.get("chg_rt", 0)),
                open_price=_safe_int(output.get("open_prc", 0), absolute=True),
                high_price=_safe_int(output.get("high_prc", 0), absolute=True),
                low_price=_safe_int(output.get("low_prc", 0), absolute=True),
                volume=_safe_int(output.get("acc_vol", 0)),
                prev_close=_safe_int(output.get("yes_prc", 0), absolute=True),
                ask_price=_safe_int(output.get("ask_prc", 0), absolute=True),
                bid_price=_safe_int(output.get("bid_prc", 0), absolute=True),
                timestamp=output.get("stk_tm", ""),
                market_type=self._parse_market_type(output),
                sector=output.get("sect_nm", "기타")  # sect_nm이 없으면 '기타'
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
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkhoga", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            for i in range(1, 11):
                ask_prices.append(_safe_int(output.get(f"ask_prc{i}", 0), absolute=True))
                ask_volumes.append(_safe_int(output.get(f"ask_vol{i}", 0)))
                bid_prices.append(_safe_int(output.get(f"bid_prc{i}", 0), absolute=True))
                bid_volumes.append(_safe_int(output.get(f"bid_vol{i}", 0)))
            
            return OrderBook(
                code=code,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                total_ask_volume=_safe_int(output.get("tot_ask_vol", 0)),
                total_bid_volume=_safe_int(output.get("tot_bid_vol", 0)),
                timestamp=output.get("stk_tm", "")
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
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkdaily", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
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
            "tr_cd": tr_code,
            "stk_cd": code,
            "interval": interval,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkminute", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("datetime", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
                ))
        
        return candles

    def get_weekly_chart(self, code: str, count: int = 52) -> List[DailyOHLC]:
        """주봉 차트 데이터 조회"""
        tr_code = self.TR_CODES["STOCK_WEEKLY"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkweekly", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
                ))
        
        return candles

    def get_tick_chart(self, code: str, count: int = 60) -> List[TickCandle]:
        """
        틱 차트 데이터 조회 (ka10007)
        
        Args:
            code: 종목코드
            count: 조회할 틱 개수 (최대 100)
            
        Returns:
            TickCandle 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_TICK"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stktick", tr_code=tr_code, data=data)
        
        candles: List[TickCandle] = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
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
        """시장 상태 조회 (지원 시). 지원되지 않으면 빈 dict 반환."""
        tr_code = self.TR_CODES["MARKET_STATUS"]
        result = self._request("POST", "/api/dostk/market/status", tr_code=tr_code, data={})
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            if isinstance(output, dict):
                return output
        return {}

    def get_index_quote(self, index_code: str) -> Dict[str, Any]:
        """지수 시세 조회 (지원 시). 지원되지 않으면 빈 dict 반환."""
        if not index_code:
            return {}
        tr_code = self.TR_CODES["INDEX_QUOTE"]
        data = {"idx_cd": index_code}
        result = self._request("POST", "/api/dostk/index/quote", tr_code=tr_code, data=data)
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            if isinstance(output, dict):
                return output
        return {}

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
                        name=res.get("idx_nm", name),
                        current_price=_safe_float(res.get("cur_idx", 0.0)),
                        change=_safe_float(res.get("chg_idx", 0.0)),
                        change_rate=_safe_float(res.get("chg_rt", 0.0)),
                        open_price=_safe_float(res.get("open_idx", 0.0)),
                        high_price=_safe_float(res.get("high_idx", 0.0)),
                        low_price=_safe_float(res.get("low_idx", 0.0)),
                        volume=_safe_int(res.get("acc_vol", 0)),
                        volume_amount=_safe_int(res.get("acc_trd_val", 0)),
                    ))
            except Exception as exc:
                self.logger.warning(f"지수({idx_cd}) 조회 실패: {exc}")
                continue
        return quotes
