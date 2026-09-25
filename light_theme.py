"""Light theme stylesheet (compatibility re-export).

Canonical implementation: :mod:`app.support.theme` (tokenized palette,
4.5:1 contrast pairs, focus rings, font scaling). This module preserves the
``light_theme.LIGHT_STYLESHEET`` import path used across the codebase and
``KiwoomTrader.spec`` hiddenimports.
"""

from app.support.theme import LIGHT_STYLESHEET

__all__ = ["LIGHT_STYLESHEET"]
