import struct
import sys
import unittest


@unittest.skipUnless(sys.platform.startswith("win"), "Windows only")
class WindowsBackendTests(unittest.TestCase):
    def test_app_label_maps_browsers_and_strips_exe(self):
        from screen_guard.backends.windows import _app_label
        self.assertEqual(_app_label("chrome.exe"), "Chrome")
        self.assertEqual(_app_label("python.exe"), "python")
        self.assertEqual(_app_label(""), "?")

    def test_shellcode_layout(self):
        from screen_guard.backends.windows import _shellcode
        hwnd = 0x1122334455667788
        code = _shellcode(hwnd, 0x11, 0xAABBCCDDEEFF0011)
        self.assertEqual(len(code), 36)
        self.assertTrue(code.startswith(b"\x48\xB9"))
        self.assertTrue(code.endswith(b"\xC3"))
        self.assertEqual(code[2:10], struct.pack("<Q", hwnd))


if __name__ == "__main__":
    unittest.main()
