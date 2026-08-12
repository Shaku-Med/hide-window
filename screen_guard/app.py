from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from . import assets, theme
from .about import APP_NAME
from .backends.base import Backend
from .controller import Guard

REFRESH_MS = 2000
FOCUS_MS = 50
CURSOR_MS = 15
CURSOR_IDLE_MS = 150
GROUP_PREFIX = "g:"
DEFAULT_KEYWORDS = ".env, password, secret, credential, .pem, api key, bitwarden"


class App:
    def __init__(self, root: tk.Tk, backend: Backend):
        self.root = root
        self.backend = backend
        self.guard = Guard(backend)
        self.auto = tk.BooleanVar(value=True)
        self.hide_self = tk.BooleanVar(value=True)
        self._focus_job = None
        self._cursor_job = None
        self._groups: dict[str, list[int]] = {}
        self._collapsed: set[str] = set()

        root.title(APP_NAME)
        root.geometry("720x640")
        root.minsize(600, 520)
        root.maxsize(1000, 1000)
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
        self._tick_focus()
        self._tick_cursor()

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
        options.add_command(label="Keep selected window active", command=self.toggle_keep_active)
        options.add_command(label="Clear keep active", command=self.clear_keep_active)
        options.add_command(label="Unhide all (reset)", command=self.unhide_all)
        options.add_separator()
        options.add_command(label="Open debug log", command=self.open_debug_log)
        options.add_command(label="Minimize to tray", command=self.minimize)
        options.add_command(label="Quit (stop protecting)", command=self.quit)
        menubar.add_cascade(label="Options", menu=options)
        self.root.config(menu=menubar)

    def _build_header(self):
        head = ttk.Frame(self.root, padding=10)
        head.pack(fill="x")
        ttk.Label(head, text="Select a window, then use the Hide or show button. Double click and right click work too.").pack(anchor="w")
        ttk.Label(
            head,
            text="Keep active: click the window that must stay 'present' so it is focused, then press Keep selected active, then switch to your hidden window and type normally. Works on any app; browsers are the strictest about this order.",
            foreground=self.palette["muted"],
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
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
        self.tree = ttk.Treeview(self.root, columns=("app", "state", "active"), selectmode="browse")
        self.tree.heading("#0", text="Window")
        self.tree.heading("app", text="App")
        self.tree.heading("state", text="Hidden")
        self.tree.heading("active", text="Active")
        self.tree.column("#0", width=360)
        self.tree.column("app", width=100, anchor="center")
        self.tree.column("state", width=80, anchor="center")
        self.tree.column("active", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._show_context)

        self.context = self._menu(self.tree)
        self.context.add_command(label="Hide this window", command=lambda: self._set_selected(True))
        self.context.add_command(label="Show this window", command=lambda: self._set_selected(False))
        self.context.add_separator()
        self.context.add_command(label="Keep this window active", command=self.toggle_keep_active)
        self.context.add_command(label="Clear keep active", command=self.clear_keep_active)

        self.group_context = self._menu(self.tree)
        self.group_context.add_command(label="Hide every window in this group",
                                       command=lambda: self._set_selected(True))
        self.group_context.add_command(label="Show every window in this group",
                                       command=lambda: self._set_selected(False))
        self.group_context.add_separator()
        self.group_context.add_command(label="Keep every window in this group active",
                                       command=lambda: self._set_group_keep_active(True))
        self.group_context.add_command(label="Clear keep active for this group",
                                       command=lambda: self._set_group_keep_active(False))

    def _build_buttons(self):
        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="Hide / show selected", command=self.toggle_selected).pack(side="left")
        ttk.Button(bar, text="Keep selected active", command=self.toggle_keep_active).pack(side="left", padx=6)
        ttk.Button(bar, text="Unhide ALL (reset)", command=self.unhide_all).pack(side="left")
        ttk.Button(bar, text="Minimize to tray", command=self.minimize).pack(side="left", padx=6)
        ttk.Button(bar, text="Quit (stop protecting)", command=self.quit).pack(side="left")
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="right")

    def _target_ids(self) -> list[int]:
        """Windows the current row stands for: one, or every window in a group."""
        iid = self.tree.focus()
        if not iid:
            return []
        if iid.startswith(GROUP_PREFIX):
            return list(self._groups.get(iid, []))
        return [int(iid)]

    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row or row.startswith(GROUP_PREFIX):
            return  # let the group expand or collapse instead
        self.toggle_selected()

    def toggle_selected(self, _event=None):
        ids = self._target_ids()
        if ids:
            self.guard.toggle_pin_group(ids)
            self.refresh()

    def toggle_keep_active(self, _event=None):
        ids = self._target_ids()
        if ids:
            self.guard.toggle_keep_active_group(ids)
            self.refresh()

    def _set_group_keep_active(self, on: bool):
        ids = self._target_ids()
        if not ids:
            return
        self.guard.arm_keep_active(ids) if on else self.guard.disarm_keep_active(ids)
        self.refresh()

    def clear_keep_active(self):
        self.guard.clear_keep_active()
        self.refresh()

    def open_debug_log(self):
        from .logutil import LOG_PATH
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not LOG_PATH.exists():
                LOG_PATH.write_text("No keep-active attempts logged yet.\n", encoding="utf-8")
            os.startfile(str(LOG_PATH))
        except Exception as exc:
            self.status.config(text=f"could not open log: {exc}")

    def _set_selected(self, hide: bool):
        ids = self._target_ids()
        if ids:
            self.guard.set_pinned(ids, hide)
            self.refresh()

    def _show_context(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.focus(row)
        self.tree.selection_set(row)
        menu = self.group_context if row.startswith(GROUP_PREFIX) else self.context
        menu.tk_popup(event.x_root, event.y_root)

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
        for job in ("_focus_job", "_cursor_job"):
            handle = getattr(self, job)
            if handle is not None:
                try:
                    self.root.after_cancel(handle)
                except Exception:
                    pass
                setattr(self, job, None)
        self.restore_all()
        if self.backend.supports_tray:
            self.backend.remove_tray()
        self.root.destroy()

    def _tick_focus(self):
        try:
            self.guard.tick_focus()
        except Exception:
            pass
        try:
            self._focus_job = self.root.after(FOCUS_MS, self._tick_focus)
        except tk.TclError:
            self._focus_job = None

    def _tick_cursor(self):
        active = False
        try:
            active = self.backend.update_cursor_cloak()
        except Exception:
            active = False
        try:
            delay = CURSOR_MS if active else CURSOR_IDLE_MS
            self._cursor_job = self.root.after(delay, self._tick_cursor)
        except tk.TclError:
            self._cursor_job = None

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
            rows.append((window, mark, self.guard.keep_active_mark(window.id)))

        self._render(rows)
        self.status.config(text=f"{hidden_count} hidden  .  {self._shield_status()}")
        self.root.after(REFRESH_MS, self.refresh)

    def _remember_collapsed(self):
        for iid in self.tree.get_children(""):
            if not iid.startswith(GROUP_PREFIX):
                continue
            self._collapsed.discard(iid) if self.tree.item(iid, "open") else self._collapsed.add(iid)

    def _render(self, rows):
        """One row per window, but apps with several windows fold into a group."""
        selected = self.tree.focus()
        self._remember_collapsed()
        self.tree.delete(*self.tree.get_children())
        self._groups = {}

        by_app: dict[str, list] = {}
        for row in rows:
            by_app.setdefault(row[0].app, []).append(row)

        for app in sorted(by_app, key=str.lower):
            items = by_app[app]
            if len(items) < 2:
                for window, mark, active in items:
                    self.tree.insert("", "end", iid=str(window.id), text=window.title,
                                     values=(window.app, mark, active))
                continue
            key = GROUP_PREFIX + app
            self._groups[key] = [w.id for w, _, _ in items]
            hidden = sum(1 for _, mark, _ in items if mark == "hidden")
            kept = sum(1 for _, _, active in items if active == "KEEP")
            total = len(items)
            self.tree.insert("", "end", iid=key, text=f"{app}  ({total})",
                             open=key not in self._collapsed,
                             values=("", f"{hidden}/{total}" if hidden else "",
                                     f"{kept}/{total}" if kept else ""))
            for window, mark, active in items:
                self.tree.insert(key, "end", iid=str(window.id), text=window.title,
                                 values=(window.app, mark, active))

        if selected and self.tree.exists(selected):
            self.tree.focus(selected)
            self.tree.selection_set(selected)

    def _shield_status(self) -> str:
        if not self.guard.keep_active:
            return "guard running"
        failed = [i for i in self.guard.keep_active if not self.guard.keep_active_ok.get(i)]
        if not failed:
            count = len(self.guard.keep_active)
            return "shield ok" if count == 1 else f"shield ok on {count} windows"
        from .backends import focus_shield
        from .logutil import LOG_PATH
        why = focus_shield.last_error or "unknown"
        return f"shield FAILED on {len(failed)}: {why}  (see Options → Open debug log: {LOG_PATH.name})"
