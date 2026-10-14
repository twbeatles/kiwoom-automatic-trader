"""Type-only helpers for dynamically composed Qt mixins."""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    class TraderMixinBase(QMainWindow):
        def __getattr__(self, name: str) -> Any: ...
else:
    class TraderMixinBase:
        pass
