"""
키움증권 REST API 클라이언트

시세 조회, 계좌 조회, 주문 등 REST API 호출을 담당합니다.

SOLID 분할 구조의 facade: 전송(`_rest_transport`), 시세(`_rest_market`),
계좌(`_rest_account`), 주문(`_rest_orders`), 탐색(`_rest_discovery`) 믹스인을
조합한다. 공개 API·import 경로는 그대로 유지된다.
"""

from typing import Any, Dict, List, Optional  # noqa: F401 (re-export surface)
from datetime import datetime  # noqa: F401

from ._rest_account import RestAccountMixin
from ._rest_discovery import RestDiscoveryMixin
from ._rest_helpers import _safe_float, _safe_int  # noqa: F401 (backward-compat re-export)
from ._rest_market import RestMarketMixin
from ._rest_orders import RestOrderMixin
from .models import (  # noqa: F401
    AccountInfo, DailyOHLC, DepositDetail, ExecutedOrder, OpenOrder, OrderBook,
    OrderResult, OrderType, Position, PriceType, SectorQuote, StockQuote,
    TickCandle, VIEvent,
)


class KiwoomRESTClient(
    RestMarketMixin, RestAccountMixin, RestOrderMixin, RestDiscoveryMixin
):
    """키움증권 REST API 클라이언트 (facade: behavior unchanged)."""
