"""Provider wrappers for Kiwoom REST data."""

from typing import Any, Dict, List, Optional


class KiwoomProvider:
    def __init__(self, rest_client: Any):
        self.rest_client = rest_client

    def get_quote(self, code: str) -> Optional[Any]:
        if not self.rest_client:
            return None
        return self.rest_client.get_stock_quote(code)

    def get_daily_bars(self, code: str, count: int = 120) -> List[Any]:
        if not self.rest_client:
            return []
        return self.rest_client.get_daily_chart(code, count)

    def get_minute_bars(self, code: str, interval: int = 1, count: int = 240) -> List[Any]:
        if not self.rest_client:
            return []
        return self.rest_client.get_minute_chart(code, interval, count)

    def get_investor_flow(self, code: str) -> Dict[str, Any]:
        if not self.rest_client:
            return {}
        return self.rest_client.get_investor_trading(code)

    def get_program_flow(self, code: str) -> Dict[str, Any]:
        if not self.rest_client:
            return {}
        return self.rest_client.get_program_trading(code)
