import unittest

import tkinter as tk

from screen_guard.app import App
from screen_guard.backends.base import Backend
from screen_guard.model import WindowInfo


class ListBackend(Backend):
    can_hide_other_apps = True
    supports_tray = False

    def __init__(self):
        self.hidden = set()
        self.protected = False

    def list_windows(self):
        return [
            WindowInfo(1, "holiday photos", "Photos"),
            WindowInfo(2, "my password vault", "Vault"),
        ]

    def hide(self, win_id):
        self.hidden.add(win_id)
        return True

    def show(self, win_id):
        self.hidden.discard(win_id)
        return True

    def protect_self(self, tk_root):
        self.protected = True
        return True

    def unprotect_self(self):
        self.protected = False


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display available: {exc}")
        self.backend = ListBackend()
        self.app = App(self.root, self.backend)
        for _ in range(2):
            self.root.update()

    def tearDown(self):
        try:
            self.app.quit()
        except tk.TclError:
            pass

    def test_protects_own_window(self):
        self.assertTrue(self.backend.protected)

    def test_keyword_window_is_hidden_after_refresh(self):
        self.assertEqual(self.app.guard.hidden, {2})

    def test_pinned_window_is_hidden(self):
        self.app.guard.toggle_pin(1)
        self.app.refresh()
        self.assertIn(1, self.app.guard.hidden)

    def test_set_selected_hides_then_shows(self):
        self.app.tree.focus("1")
        self.app._set_selected(True)
        self.assertIn(1, self.app.guard.hidden)
        self.app._set_selected(False)
        self.assertNotIn(1, self.app.guard.hidden)

    def test_self_protection_toggle(self):
        self.app.hide_self.set(False)
        self.app._apply_self_protection()
        self.assertFalse(self.backend.protected)
        self.app.hide_self.set(True)
        self.app._apply_self_protection()
        self.assertTrue(self.backend.protected)

    def test_quit_restores_everything(self):
        self.app.quit()
        self.assertEqual(self.app.guard.hidden, set())
        self.assertEqual(self.backend.hidden, set())


if __name__ == "__main__":
    unittest.main()
