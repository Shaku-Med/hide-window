from __future__ import annotations

from typing import Callable

from ..model import WindowInfo


class Backend:
    """Platform interface. Every method has a safe default."""

    name = "base"
    can_hide_other_apps = False
    unsupported_reason = "This platform is not supported yet."

    def ensure_privileges(self) -> bool:
        return True

    def list_windows(self) -> list[WindowInfo]:
        return []

    def hide(self, window_id: int) -> bool:
        return False

    def show(self, window_id: int) -> bool:
        return False

    def protect_self(self, tk_root) -> bool:
        return False

    def unprotect_self(self) -> None:
        pass

    supports_tray = False

    def setup_tray(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
        pass

    def notify(self, title: str, text: str) -> None:
        pass

    def remove_tray(self) -> None:
        pass
