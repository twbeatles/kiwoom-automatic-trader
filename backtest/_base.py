"""Backtest engine base (SRP: config ownership; mixin chain root)."""

from __future__ import annotations

from typing import Optional

from .models import BacktestConfig


class BacktestEngineBase:
    """Config holder. Domain mixins extend this in a linear chain."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
