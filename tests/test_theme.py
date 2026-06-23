import unittest

import tkinter as tk

from screen_guard import theme


class ThemeTests(unittest.TestCase):
    def test_is_dark_returns_bool(self):
        self.assertIsInstance(theme.is_dark(), bool)

    def test_apply_returns_palette(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display available: {exc}")
        try:
            palette = theme.apply(root)
            for key in ("bg", "fg", "field", "select", "muted", "alert"):
                self.assertIn(key, palette)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
