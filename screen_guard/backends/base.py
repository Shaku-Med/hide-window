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

    def is_window(self, window_id: int) -> bool:
        return False

    def get_foreground(self) -> int | None:
        return None

    def ensure_focus_shield(self, window_id: int) -> bool:
        """Make window_id keep believing it is active while another window has real focus."""
        return False

    def clear_focus_shield(self, window_id: int | None = None) -> None:
        """Remove one installed focus shield, or all of them when window_id is None."""
        pass

    supports_cursor_cloak = False

    def start_cursor_cloak(self, active_window_id: int) -> bool:
        """Hide the real cursor from capture and park a decoy in the active window."""
        return False

    def update_cursor_cloak(self) -> bool:
        """Move the follow cursor to the mouse. Returns True while cloaking."""
        return False

    def stop_cursor_cloak(self) -> None:
        """Restore the system cursor and drop the overlays."""
        pass

    def reset_cursor(self) -> None:
        """Force the system cursor back, even with no live cloak (crash recovery)."""
        pass

    supports_tray = False
    supports_keep_active = False

    def setup_tray(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
        pass

    def notify(self, title: str, text: str) -> None:
        pass

    def remove_tray(self) -> None:
        pass
