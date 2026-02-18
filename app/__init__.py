"""Application package exports."""

__all__ = ["KiwoomProTrader"]


def __getattr__(name):
    if name == "KiwoomProTrader":
        from .main_window import KiwoomProTrader

        return KiwoomProTrader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
