import sys
import unittest

from screen_guard.backends import load_backend


class BackendFactoryTests(unittest.TestCase):
    def test_returns_backend_for_current_platform(self):
        backend = load_backend()
        if sys.platform.startswith("win"):
            self.assertEqual(backend.name, "windows")
            self.assertTrue(backend.can_hide_other_apps)
        elif sys.platform == "darwin":
            self.assertEqual(backend.name, "macos")
        else:
            self.assertEqual(backend.name, "linux")

    def test_list_windows_returns_a_list(self):
        self.assertIsInstance(load_backend().list_windows(), list)


if __name__ == "__main__":
    unittest.main()
