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
        func = 0xAABBCCDDEEFF0011
        code = _shellcode(func, hwnd, 0x11)
        self.assertTrue(code.startswith(b"\x48\xB9"))
        self.assertTrue(code.endswith(b"\xC3"))
        self.assertEqual(code[2:10], struct.pack("<Q", hwnd))       # rcx = hwnd
        self.assertEqual(code[12:20], struct.pack("<Q", 0x11))      # rdx = second arg
        self.assertIn(struct.pack("<Q", func), code)
        self.assertIn(b"\xFF\xD0", code)                            # call rax

    def test_shellcode_carries_all_four_args(self):
        from screen_guard.backends.windows import _shellcode
        code = _shellcode(0xDEAD, 1, 2, 3, 4)
        for reg, value in ((b"\x48\xB9", 1), (b"\x48\xBA", 2), (b"\x49\xB8", 3), (b"\x49\xB9", 4)):
            self.assertIn(reg + struct.pack("<Q", value), code)

    def test_getmessage_hook_builds(self):
        from screen_guard.backends.focus_shield import build_subclass_wndproc
        code = build_subclass_wndproc(0x10000, 0xAABBCCDDEEFF0011)
        self.assertGreater(len(code), 40)
        self.assertTrue(code.endswith(b"\xC3"))
        self.assertIn(struct.pack("<Q", 0xAABBCCDDEEFF0011), code)

    def test_resolve_wndproc_uses_class_proc_when_instance_zero(self):
        """Chrome_WidgetWin_1 has GWLP_WNDPROC==0; shield must use GCLP_WNDPROC."""
        import ctypes
        from ctypes import wintypes
        from screen_guard.backends import focus_shield

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            self.skipTest("no foreground window")
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value != "Chrome_WidgetWin_1":
            self.skipTest("focus a Chrome/Brave window to run this check")
        instance, call_target = focus_shield.resolve_wndproc(int(hwnd), True)
        self.assertEqual(instance, 0)
        self.assertNotEqual(call_target, 0)


if __name__ == "__main__":
    unittest.main()
