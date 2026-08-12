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
        self.keep_active: set[int] = set()
        self.keep_active_ok: dict[int, bool] = {}
        # The cursor decoy needs one window to sit in, so the most recent arm wins.
        self.keep_primary: int | None = None

    def toggle_pin(self, win_id: int) -> None:
        self.pinned.discard(win_id) if win_id in self.pinned else self.pinned.add(win_id)

    def set_pinned(self, win_ids: Iterable[int], pinned: bool) -> None:
        for win_id in win_ids:
            self.pinned.add(win_id) if pinned else self.pinned.discard(win_id)

    def toggle_pin_group(self, win_ids: Iterable[int]) -> None:
        ids = list(win_ids)
        self.set_pinned(ids, not all(i in self.pinned for i in ids))

    def is_keep_active(self, win_id: int) -> bool:
        return win_id in self.keep_active

    def keep_active_mark(self, win_id: int) -> str:
        if win_id not in self.keep_active:
            return ""
        return "KEEP" if self.keep_active_ok.get(win_id) else "FAILED"

    def arm_keep_active(self, win_ids: Iterable[int]) -> None:
        for win_id in win_ids:
            self.keep_active.add(win_id)
            self.keep_active_ok[win_id] = self.backend.ensure_focus_shield(win_id)
            self.keep_primary = win_id
        self._sync_cursor()

    def disarm_keep_active(self, win_ids: Iterable[int]) -> None:
        for win_id in list(win_ids):
            self.keep_active.discard(win_id)
            self.keep_active_ok.pop(win_id, None)
            self.backend.clear_focus_shield(win_id)
        if self.keep_primary not in self.keep_active:
            self.keep_primary = next(iter(self.keep_active), None)
        self._sync_cursor()

    def toggle_keep_active(self, win_id: int) -> None:
        self.disarm_keep_active([win_id]) if win_id in self.keep_active else self.arm_keep_active([win_id])

    def toggle_keep_active_group(self, win_ids: Iterable[int]) -> None:
        ids = list(win_ids)
        if ids and all(i in self.keep_active for i in ids):
            self.disarm_keep_active(ids)
        else:
            self.arm_keep_active(i for i in ids if i not in self.keep_active)

    def clear_keep_active(self) -> None:
        self.disarm_keep_active(list(self.keep_active))
        self.keep_active.clear()
        self.keep_active_ok.clear()
        self.keep_primary = None
        self.backend.clear_focus_shield()
        self.backend.stop_cursor_cloak()

    def _sync_cursor(self) -> None:
        if self.keep_primary is None:
            self.backend.stop_cursor_cloak()
        else:
            self.backend.start_cursor_cloak(self.keep_primary)

    def sync(self, live: set[int]) -> None:
        self.pinned &= live
        self.hidden &= live
        self.fail_count = {i: c for i, c in self.fail_count.items() if i in live}
        dead = self.keep_active - live
        if dead:
            self.disarm_keep_active(dead)

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
        """Keep the shields on the chosen windows; do not steal real OS focus."""
        if not self.keep_active:
            return
        for win_id in list(self.keep_active):
            if not self.backend.is_window(win_id):
                self.disarm_keep_active([win_id])
                continue
            self.keep_active_ok[win_id] = self.backend.ensure_focus_shield(win_id)

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
        self.backend.reset_cursor()
        self.pinned.clear()
        for window in windows:
            self.backend.show(window.id)
        self.hidden.clear()
        self.fail_count.clear()
