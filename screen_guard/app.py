from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import assets, theme
from .about import APP_NAME
from .backends.base import Backend
from .controller import Guard

REFRESH_MS = 2000
DEFAULT_KEYWORDS = ".env, password, secret, credential, .pem, api key, bitwarden"


class App:
    def __init__(self, root: tk.Tk, backend: Backend):
        self.root = root
        self.backend = backend
        self.guard = Guard(backend)
        self.auto = tk.BooleanVar(value=True)
        self.hide_self = tk.BooleanVar(value=True)

        root.title(APP_NAME)
        root.geometry("640x640")
        root.minsize(560, 520)
        root.maxsize(900, 1000)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.minimize)

        self.palette = theme.apply(root)
        self._set_window_icon()

        self._build_menu()
        self._build_header()
        self._build_keywords()
        self._build_list()
        self._build_buttons()

        if self.backend.supports_tray:
            self.backend.setup_tray(on_restore=self._tray_restore, on_quit=self._tray_quit)
        self._apply_self_protection()
        self.refresh()

    def _set_window_icon(self):
        png = assets.logo_png()
        if not png:
            return
        try:
            self._icon = tk.PhotoImage(file=png)
            self.root.iconphoto(True, self._icon)
        except Exception:
            pass

    def _menu(self, parent):
        p = self.palette
        return tk.Menu(parent, tearoff=0, bg=p["field"], fg=p["fg"],
                       activebackground=p["select"], activeforeground="#ffffff", bd=0)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        options = self._menu(menubar)
        options.add_checkbutton(label="Auto hide by keyword", variable=self.auto, command=self.refresh)
        options.add_checkbutton(label="Hide this app from capture", variable=self.hide_self,
                                command=self._apply_self_protection)
        options.add_separator()
        options.add_command(label="Hide or show selected window", command=self.toggle_selected)
        options.add_command(label="Unhide all (reset)", command=self.unhide_all)
        options.add_separator()
        options.add_command(label="Minimize to tray", command=self.minimize)
        options.add_command(label="Quit (stop protecting)", command=self.quit)
        menubar.add_cascade(label="Options", menu=options)
        self.root.config(menu=menubar)

    def _build_header(self):
        head = ttk.Frame(self.root, padding=10)
        head.pack(fill="x")
        ttk.Label(head, text="Select a window, then use the Hide or show button. Double click and right click work too.").pack(anchor="w")
        ttk.Label(head, text="Quitting or closing the app puts every window it hid back to normal.",
                  foreground=self.palette["muted"]).pack(anchor="w")
        if not self.backend.can_hide_other_apps:
            ttk.Label(head, text=self.backend.unsupported_reason,
                      foreground=self.palette["alert"], wraplength=600, justify="left").pack(anchor="w", pady=(6, 0))

    def _build_keywords(self):
        frame = ttk.Frame(self.root, padding=(10, 0))
        frame.pack(fill="x")
        ttk.Label(frame, text="Auto hide any window whose title contains:").pack(anchor="w")
        self.keywords = tk.StringVar(value=DEFAULT_KEYWORDS)
        ttk.Entry(frame, textvariable=self.keywords).pack(fill="x", pady=4)
        ttk.Checkbutton(frame, text="Auto hide enabled", variable=self.auto).pack(anchor="w")
        ttk.Checkbutton(frame, text="Hide this app from capture", variable=self.hide_self,
                        command=self._apply_self_protection).pack(anchor="w")

    def _build_list(self):
        self.tree = ttk.Treeview(self.root, columns=("app", "state"), selectmode="browse")
        self.tree.heading("#0", text="Window")
        self.tree.heading("app", text="App")
        self.tree.heading("state", text="Hidden")
        self.tree.column("#0", width=400)
        self.tree.column("app", width=110, anchor="center")
        self.tree.column("state", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", self.toggle_selected)
        self.tree.bind("<Button-3>", self._show_context)

        self.context = self._menu(self.tree)
        self.context.add_command(label="Hide this window", command=lambda: self._set_selected(True))
        self.context.add_command(label="Show this window", command=lambda: self._set_selected(False))

    def _build_buttons(self):
        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="Hide / show selected", command=self.toggle_selected).pack(side="left")
        ttk.Button(bar, text="Unhide ALL (reset)", command=self.unhide_all).pack(side="left", padx=6)
        ttk.Button(bar, text="Minimize to tray", command=self.minimize).pack(side="left")
        ttk.Button(bar, text="Quit (stop protecting)", command=self.quit).pack(side="left", padx=6)
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="right")

    def toggle_selected(self, _event=None):
        iid = self.tree.focus()
        if not iid:
            return
        self.guard.toggle_pin(int(iid))
        self.refresh()

    def _set_selected(self, hide: bool):
        iid = self.tree.focus()
        if not iid:
            return
        win_id = int(iid)
        self.guard.pinned.add(win_id) if hide else self.guard.pinned.discard(win_id)
        self.refresh()

    def _show_context(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.focus(row)
        self.tree.selection_set(row)
        self.context.tk_popup(event.x_root, event.y_root)

    def _apply_self_protection(self):
        if self.hide_self.get():
            self.backend.protect_self(self.root)
        else:
            self.backend.unprotect_self()

    def minimize(self):
        self.root.withdraw()
        if self.backend.supports_tray:
            self.backend.notify("Still protecting your screen",
                                "Running in the tray. Double click the icon to reopen, right click to quit.")
        else:
            self.root.after(400, self.root.deiconify)
            self.root.iconify()

    def restore(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

    def _tray_restore(self):
        self.root.after(0, self.restore)

    def _tray_quit(self):
        self.root.after(0, self.quit)

    def restore_all(self):
        self.guard.restore_all()

    def unhide_all(self):
        self.auto.set(False)
        self.guard.unhide_all(self.backend.list_windows())
        self.refresh()

    def quit(self):
        self.restore_all()
        if self.backend.supports_tray:
            self.backend.remove_tray()
        self.root.destroy()

    def refresh(self):
        windows = self.backend.list_windows()
        self.guard.sync({w.id for w in windows})
        auto_on = self.auto.get()
        keywords = self.keywords.get()

        rows = []
        hidden_count = 0
        for window in windows:
            wanted = self.guard.wanted(window, auto_on, keywords)
            ok = self.guard.apply(window.id, wanted)
            if wanted:
                hidden_count += 1
            mark = ("hidden" if ok else "FAILED") if wanted else ""
            rows.append((window, mark))

        keep = self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        for window, mark in rows:
            self.tree.insert("", "end", iid=str(window.id), text=window.title,
                             values=(window.app, mark))
        if keep and self.tree.exists(keep):
            self.tree.focus(keep)
            self.tree.selection_set(keep)

        self.status.config(text=f"{hidden_count} window(s) hidden  .  guard running")
        self.root.after(REFRESH_MS, self.refresh)
