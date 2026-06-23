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

    def toggle_pin(self, win_id: int) -> None:
        self.pinned.discard(win_id) if win_id in self.pinned else self.pinned.add(win_id)

    def sync(self, live: set[int]) -> None:
        self.pinned &= live
        self.hidden &= live
        self.fail_count = {i: c for i, c in self.fail_count.items() if i in live}

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

    def restore_all(self) -> None:
        for win_id in list(self.hidden):
            for _ in range(2):
                if self.backend.show(win_id):
                    break
            self.hidden.discard(win_id)
        self.fail_count.clear()
        self.backend.unprotect_self()

    def unhide_all(self, windows: Iterable[WindowInfo]) -> None:
        self.pinned.clear()
        for window in windows:
            self.backend.show(window.id)
        self.hidden.clear()
        self.fail_count.clear()
