from __future__ import annotations

from ..model import WindowInfo
from .base import Backend

try:
    import Quartz
    _HAS_QUARTZ = True
except Exception:
    _HAS_QUARTZ = False


class MacBackend(Backend):
    name = "macos"
    can_hide_other_apps = False
    unsupported_reason = (
        "macOS has no public way to hide another app's window from capture. "
        "The list is read only here. Install the Quartz bindings for listing."
    )

    def list_windows(self) -> list[WindowInfo]:
        if not _HAS_QUARTZ:
            return []
        options = (Quartz.kCGWindowListOptionOnScreenOnly |
                   Quartz.kCGWindowListExcludeDesktopElements)
        entries = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
        windows: list[WindowInfo] = []
        for entry in entries:
            title = entry.get("kCGWindowName") or ""
            app = entry.get("kCGWindowOwnerName") or "?"
            number = entry.get("kCGWindowNumber")
            if not title or number is None:
                continue
            windows.append(WindowInfo(id=int(number), title=str(title), app=str(app)))
        return windows

    def protect_self(self, tk_root) -> bool:
        try:
            from AppKit import NSApp, NSWindowSharingNone
            for window in NSApp().windows():
                window.setSharingType_(NSWindowSharingNone)
            return True
        except Exception:
            return False
