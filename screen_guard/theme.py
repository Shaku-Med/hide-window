from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import ttk

DARK = {
    "bg": "#1e1e1e", "fg": "#e6e6e6", "field": "#2b2b2b",
    "select": "#0a84ff", "muted": "#9a9a9a", "alert": "#ff6b6b",
}
LIGHT = {
    "bg": "#f3f3f3", "fg": "#1a1a1a", "field": "#ffffff",
    "select": "#0a84ff", "muted": "#5a5a5a", "alert": "#b00000",
}


def is_dark() -> bool:
    if sys.platform.startswith("win"):
        try:
            import winreg
            path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except Exception:
            return False
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                 capture_output=True, text=True)
            return "Dark" in out.stdout
        except Exception:
            return False
    return False


def apply(root: tk.Tk) -> dict:
    palette = DARK if is_dark() else LIGHT
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=palette["bg"])
    style.configure(".", background=palette["bg"], foreground=palette["fg"],
                    fieldbackground=palette["field"], bordercolor=palette["field"])
    style.configure("TFrame", background=palette["bg"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
    style.configure("TCheckbutton", background=palette["bg"], foreground=palette["fg"])
    style.map("TCheckbutton", background=[("active", palette["bg"])])
    style.configure("TButton", background=palette["field"], foreground=palette["fg"])
    style.map("TButton", background=[("active", palette["select"])],
              foreground=[("active", "#ffffff")])
    style.configure("TEntry", fieldbackground=palette["field"], foreground=palette["fg"],
                    insertcolor=palette["fg"])
    style.configure("Treeview", background=palette["field"], fieldbackground=palette["field"],
                    foreground=palette["fg"])
    style.configure("Treeview.Heading", background=palette["bg"], foreground=palette["fg"])
    style.map("Treeview", background=[("selected", palette["select"])],
              foreground=[("selected", "#ffffff")])

    if palette is DARK and sys.platform.startswith("win"):
        _dark_titlebar(root)
    return palette


def _dark_titlebar(root: tk.Tk) -> None:
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        flag = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(flag), ctypes.sizeof(flag))
    except Exception:
        pass
