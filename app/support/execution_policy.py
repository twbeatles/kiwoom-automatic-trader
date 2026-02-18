"""Execution policy abstraction for order routing."""

from typing import Any, Callable, Tuple


class ExecutionPolicy:
    MARKET = "market"
    LIMIT = "limit"

    @staticmethod
    def select_buy(rest_client: Any, policy: str, account: str, code: str, quantity: int, price: int) -> Tuple[Callable, tuple]:
        policy = (policy or ExecutionPolicy.MARKET).lower()
        if policy == ExecutionPolicy.LIMIT and hasattr(rest_client, "buy_limit") and price > 0:
            return rest_client.buy_limit, (account, code, quantity, int(price))
        return rest_client.buy_market, (account, code, quantity)

    @staticmethod
    def select_sell(rest_client: Any, policy: str, account: str, code: str, quantity: int, price: int) -> Tuple[Callable, tuple]:
        policy = (policy or ExecutionPolicy.MARKET).lower()
        if policy == ExecutionPolicy.LIMIT and hasattr(rest_client, "sell_limit") and price > 0:
            return rest_client.sell_limit, (account, code, quantity, int(price))
        return rest_client.sell_market, (account, code, quantity)
