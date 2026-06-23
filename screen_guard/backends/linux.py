from __future__ import annotations

import shutil
import subprocess

from ..model import WindowInfo
from .base import Backend


class LinuxBackend(Backend):
    name = "linux"
    can_hide_other_apps = False
    unsupported_reason = (
        "Linux has no general capture exclusion API, so the list is read only. "
        "Window listing uses wmctrl when it is installed."
    )

    def list_windows(self) -> list[WindowInfo]:
        if not shutil.which("wmctrl"):
            return []
        try:
            output = subprocess.check_output(["wmctrl", "-lp"], text=True)
        except Exception:
            return []
        windows: list[WindowInfo] = []
        for line in output.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue
            win_id, _desktop, _pid, _host, title = parts
            title = title.strip()
            if not title:
                continue
            try:
                number = int(win_id, 16)
            except ValueError:
                continue
            windows.append(WindowInfo(id=number, title=title, app="?"))
        return windows
