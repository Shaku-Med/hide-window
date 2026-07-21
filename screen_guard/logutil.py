"""Simple file logger for Cloak diagnostics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Repo root (next to safe.py) so it's easy to find.
LOG_PATH = Path(__file__).resolve().parent.parent / "cloak_debug.log"


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}  {msg}"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def log_section(title: str) -> None:
    log("=" * 60)
    log(title)
    log("=" * 60)


def clear_log() -> None:
    try:
        LOG_PATH.write_text("", encoding="utf-8")
    except Exception:
        pass


def win_err() -> str:
    import ctypes
    err = ctypes.get_last_error()
    if not err:
        return "err=0"
    try:
        buf = ctypes.create_unicode_buffer(512)
        n = ctypes.windll.kernel32.FormatMessageW(
            0x00001000, None, err, 0, buf, len(buf), None
        )
        text = buf.value.strip() if n else ""
        return f"err={err} ({text})" if text else f"err={err}"
    except Exception:
        return f"err={err}"
