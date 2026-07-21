from __future__ import annotations

from typing import Iterable

from .backends.base import Backend
from .model import WindowInfo

MAX_RETRIES = 3


def matches_keyword(title: str, keywords: str) -> bool:
    words = [w.strip().lower() for w in keywords.split(",") if w.strip()]
    low = title.lower()
    return any(w in low for w in words)


class Guard:
    def __init__(self, backend: Backend):
        self.backend = backend
        self.pinned: set[int] = set()
        self.hidden: set[int] = set()
        self.fail_count: dict[int, int] = {}
        self.keep_active: int | None = None
        self.keep_active_ok = False

    def toggle_pin(self, win_id: int) -> None:
        self.pinned.discard(win_id) if win_id in self.pinned else self.pinned.add(win_id)

    def toggle_keep_active(self, win_id: int) -> None:
        if self.keep_active == win_id:
            self.clear_keep_active()
            return
        self.backend.clear_focus_shield()
        self.keep_active = win_id
        self.keep_active_ok = self.backend.ensure_focus_shield(win_id)

    def clear_keep_active(self) -> None:
        self.keep_active = None
        self.keep_active_ok = False
        self.backend.clear_focus_shield()

    def sync(self, live: set[int]) -> None:
        self.pinned &= live
        self.hidden &= live
        self.fail_count = {i: c for i, c in self.fail_count.items() if i in live}
        if self.keep_active is not None and self.keep_active not in live:
            self.clear_keep_active()

    def wanted(self, window: WindowInfo, auto: bool, keywords: str) -> bool:
        return window.id in self.pinned or (auto and matches_keyword(window.title, keywords))

    def apply(self, win_id: int, wanted: bool) -> bool:
        already = win_id in self.hidden
        if wanted:
            if already:
                return True
            if self.fail_count.get(win_id, 0) >= MAX_RETRIES:
                return False
            if self.backend.hide(win_id):
                self.hidden.add(win_id)
                self.fail_count.pop(win_id, None)
                return True
            self.fail_count[win_id] = self.fail_count.get(win_id, 0) + 1
            return False
        if already and self.backend.show(win_id):
            self.hidden.discard(win_id)
        self.fail_count.pop(win_id, None)
        return True

    def tick_focus(self) -> None:
        """Keep the shield on the chosen window; do not steal real OS focus."""
        if self.keep_active is None:
            self.keep_active_ok = False
            self.backend.clear_focus_shield()
            return
        if not self.backend.is_window(self.keep_active):
            self.clear_keep_active()
            return
        self.keep_active_ok = self.backend.ensure_focus_shield(self.keep_active)

    def restore_all(self) -> None:
        self.clear_keep_active()
        for win_id in list(self.hidden):
            for _ in range(2):
                if self.backend.show(win_id):
                    break
            self.hidden.discard(win_id)
        self.fail_count.clear()
        self.backend.unprotect_self()

    def unhide_all(self, windows: Iterable[WindowInfo]) -> None:
        self.clear_keep_active()
        self.pinned.clear()
        for window in windows:
            self.backend.show(window.id)
        self.hidden.clear()
        self.fail_count.clear()
