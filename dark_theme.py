"""Dark theme stylesheet (compatibility re-export).

Canonical implementation: :mod:`app.support.theme` (tokenized palette,
4.5:1 contrast pairs, focus rings, font scaling). This module preserves the
``dark_theme.DARK_STYLESHEET`` import path used across the codebase and
``KiwoomTrader.spec`` hiddenimports.
"""

from app.support.theme import DARK_STYLESHEET

__all__ = ["DARK_STYLESHEET"]
