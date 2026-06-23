from __future__ import annotations

import atexit
import tkinter as tk

from .app import App
from .backends import load_backend


def run() -> None:
    backend = load_backend()
    if not backend.ensure_privileges():
        return

    root = tk.Tk()
    app = App(root, backend)
    atexit.register(app.restore_all)
    try:
        root.mainloop()
    finally:
        app.restore_all()
