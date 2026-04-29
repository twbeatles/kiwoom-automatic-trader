"""Type-only helpers for dynamically composed strategy manager mixins."""

from typing import Any


class StrategyManagerMixinBase:
    def __getattr__(self, name: str) -> Any: ...
