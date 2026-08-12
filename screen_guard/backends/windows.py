from __future__ import annotations

import ctypes
import struct
import sys
from ctypes import wintypes
from typing import Callable

from ..about import APP_NAME
from ..assets import logo_ico
from ..model import WindowInfo
from . import cursor_cloak, focus_shield
from .base import Backend

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Chromium decides a window is "not on screen" by walking the windows stacked on
# top of it, and it throttles timers and animation frames when it concludes it is
# covered. A hidden window sitting over the kept one triggers exactly that, which
# a page can measure even though focus and visibility look clean.
#
# Its occluder test (ui/gfx/win/hwnd_util.cc, IsWindowVisibleAndFullyOpaque) skips
# any window whose layered alpha is below 255. WS_EX_TRANSPARENT would also work
# but makes the window click through, so alpha is the usable lever: 254 is visually
# indistinguishable and keeps the window fully interactive.
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
NO_OCCLUDE_ALPHA = 254

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_CREATE_THREAD = 0x0002
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
INJECT_ACCESS = (PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION |
                 PROCESS_VM_WRITE | PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40
GA_ROOT = 2

OWN_TITLE = APP_NAME

WM_NULL = 0x0000
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
TRAY_CALLBACK = 0x0400 + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
IDI_APPLICATION = 32512
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
ID_RESTORE, ID_QUIT = 1001, 1002
MF_STRING = 0x0000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
WS_OVERLAPPED = 0x00000000
CW_USEDEFAULT = -2147483648

BROWSERS = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox",
    "brave.exe": "Brave", "opera.exe": "Opera", "vivaldi.exe": "Vivaldi", "arc.exe": "Arc",
}

LRESULT = ctypes.c_ssize_t
WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROCTYPE), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


def _bind():
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                  ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.DWORD
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualAllocEx.restype = wintypes.LPVOID
    kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.CreateRemoteThread.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID]
    kernel32.CreateRemoteThread.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE

    shell32.IsUserAnAdmin.restype = wintypes.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL


_bind()
# System DLLs share one session ASLR base, so a local address is valid remotely.
SWDA_ADDR = ctypes.cast(user32.SetWindowDisplayAffinity, ctypes.c_void_p).value
SLWA_ADDR = ctypes.cast(user32.SetLayeredWindowAttributes, ctypes.c_void_p).value
SETWLP_ADDR = ctypes.cast(user32.SetWindowLongPtrW, ctypes.c_void_p).value
IS_64BIT = ctypes.sizeof(ctypes.c_void_p) == 8


def _process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.split("\\")[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _app_label(proc: str) -> str:
    if proc in BROWSERS:
        return BROWSERS[proc]
    if proc.endswith(".exe"):
        return proc[:-4]
    return proc or "?"


def _shellcode(func_addr: int, a1: int, a2: int = 0, a3: int = 0, a4: int = 0) -> bytes:
    """x64: load the four register args, call func_addr, return its result."""
    def q(value: int) -> bytes:
        return struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)

    return (
        b"\x48\xB9" + q(a1) +          # mov rcx, a1
        b"\x48\xBA" + q(a2) +          # mov rdx, a2
        b"\x49\xB8" + q(a3) +          # mov r8,  a3
        b"\x49\xB9" + q(a4) +          # mov r9,  a4
        b"\x48\xB8" + q(func_addr) +   # mov rax, func
        b"\x48\x83\xEC\x28" +          # sub rsp, 0x28
        b"\xFF\xD0" +                  # call rax
        b"\x48\x83\xC4\x28" +          # add rsp, 0x28
        b"\xC3"
    )


def _inject_call(hwnd: int, func_addr: int, *args: int) -> int | None:
    """Run a win32 call from inside the window's own process. Returns the low 32
    bits of its result, or None if the call could not be made."""
    if not user32.IsWindow(hwnd) or not IS_64BIT or not func_addr:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None

    handle = kernel32.OpenProcess(INJECT_ACCESS, False, pid.value)
    if not handle:
        return None
    try:
        wow64 = wintypes.BOOL()
        if kernel32.IsWow64Process(handle, ctypes.byref(wow64)) and wow64.value:
            return None

        code = _shellcode(func_addr, *args)
        addr = kernel32.VirtualAllocEx(handle, None, len(code), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
        if not addr:
            return None
        try:
            written = ctypes.c_size_t(0)
            if not kernel32.WriteProcessMemory(handle, addr, code, len(code), ctypes.byref(written)):
                return None
            thread = kernel32.CreateRemoteThread(handle, None, 0, addr, None, 0, None)
            if not thread:
                return None
            try:
                kernel32.WaitForSingleObject(thread, 5000)
                result = wintypes.DWORD()
                kernel32.GetExitCodeThread(thread, ctypes.byref(result))
                return int(result.value)
            finally:
                kernel32.CloseHandle(thread)
        finally:
            kernel32.VirtualFreeEx(handle, addr, 0, MEM_RELEASE)
    finally:
        kernel32.CloseHandle(handle)


def _inject_affinity(hwnd: int, affinity: int) -> bool:
    """Run SetWindowDisplayAffinity from inside the window's own process."""
    return bool(_inject_call(hwnd, SWDA_ADDR, hwnd, affinity))


def _make_non_occluding(hwnd: int) -> int | None:
    """Drop the window just under fully opaque so Chromium stops counting it as
    covering whatever is behind it. Returns the original ex-style to restore, or
    None if nothing was changed."""
    ex = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    if not ex or ex & WS_EX_LAYERED:
        return None  # already layered: it has its own setup, leave it alone
    if _inject_call(hwnd, SETWLP_ADDR, hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED) is None:
        return None
    if not int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE)) & WS_EX_LAYERED:
        return None
    _inject_call(hwnd, SLWA_ADDR, hwnd, 0, NO_OCCLUDE_ALPHA, LWA_ALPHA)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
    return ex


def _restore_occluding(hwnd: int, ex_style: int) -> None:
    if user32.IsWindow(hwnd):
        _inject_call(hwnd, SETWLP_ADDR, hwnd, GWL_EXSTYLE, ex_style)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def _enable_debug_privilege() -> None:
    """Admin tokens often have SeDebugPrivilege disabled until requested."""
    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008
    SE_PRIVILEGE_ENABLED = 0x00000002

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
    advapi32.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES),
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
    ]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)
    ):
        return
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
            return
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None)
    finally:
        kernel32.CloseHandle(token)


class WindowsBackend(Backend):
    name = "windows"
    can_hide_other_apps = True
    supports_keep_active = True
    supports_anti_occlusion = True

    def __init__(self):
        self.anti_occlusion = True
        self._unoccluded: dict[int, int] = {}
        self._own_hwnd = None
        self._tray = None
        self._shields: dict[int, focus_shield.ShieldState] = {}
        self._shield_background: dict[int, bool] = {}
        self._cursor = None

    def ensure_privileges(self) -> bool:
        try:
            is_admin = bool(shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False
        if is_admin:
            try:
                _enable_debug_privilege()
            except Exception:
                pass
            return True
        shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return False

    def list_windows(self) -> list[WindowInfo]:
        found: list[WindowInfo] = []

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if not title or title == OWN_TITLE:
                return True
            proc = _process_name(hwnd)
            found.append(WindowInfo(id=int(hwnd), title=title, app=_app_label(proc)))
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return found

    def hide(self, window_id: int) -> bool:
        ok = _inject_affinity(window_id, WDA_EXCLUDEFROMCAPTURE)
        if ok and self.anti_occlusion and window_id not in self._unoccluded:
            ex = _make_non_occluding(window_id)
            if ex is not None:
                self._unoccluded[window_id] = ex
        return ok

    def show(self, window_id: int) -> bool:
        self._revert_occlusion(window_id)
        return _inject_affinity(window_id, WDA_NONE)

    def _revert_occlusion(self, window_id: int) -> None:
        ex = self._unoccluded.pop(window_id, None)
        if ex is not None:
            _restore_occluding(window_id, ex)

    def set_anti_occlusion(self, enabled: bool, window_ids=()) -> None:
        self.anti_occlusion = enabled
        if enabled:
            for win_id in window_ids:
                if win_id not in self._unoccluded:
                    ex = _make_non_occluding(win_id)
                    if ex is not None:
                        self._unoccluded[win_id] = ex
            return
        for win_id in list(self._unoccluded):
            self._revert_occlusion(win_id)

    def is_window(self, window_id: int) -> bool:
        return bool(user32.IsWindow(window_id))

    def get_foreground(self) -> int | None:
        hwnd = user32.GetForegroundWindow()
        return int(hwnd) if hwnd else None

    def ensure_focus_shield(self, window_id: int) -> bool:
        shield = self._shields.get(window_id)
        if shield and focus_shield.is_alive(shield):
            focus_shield.sync_children(shield)
            fg = self.get_foreground()
            in_foreground = fg is not None and (fg == window_id or fg == self._own_hwnd)
            if in_foreground:
                # User came back — pulse real focus so the page is not stuck AWAY.
                if self._shield_background.get(window_id):
                    focus_shield.resync_real_focus(shield)
                self._shield_background[window_id] = False
            else:
                # Still elsewhere — keep the page believing it is focused.
                focus_shield.reinforce(shield)
                self._shield_background[window_id] = True
            return True
        if shield:
            focus_shield.remove(shield)
            self._shields.pop(window_id, None)
        state = focus_shield.install(window_id)
        if not state:
            return False
        self._shields[window_id] = state
        self._shield_background[window_id] = False
        return True

    def clear_focus_shield(self, window_id: int | None = None) -> None:
        targets = [window_id] if window_id is not None else list(self._shields)
        for target in targets:
            shield = self._shields.pop(target, None)
            if shield:
                focus_shield.remove(shield)
            self._shield_background.pop(target, None)

    supports_cursor_cloak = True

    def start_cursor_cloak(self, active_window_id: int) -> bool:
        if self._cursor:
            if self._cursor.active_hwnd == active_window_id and cursor_cloak.is_alive(self._cursor):
                return True
            cursor_cloak.stop(self._cursor)
            self._cursor = None
        self._cursor = cursor_cloak.start(active_window_id)
        return self._cursor is not None

    def update_cursor_cloak(self) -> bool:
        if not self._cursor:
            return False
        if not cursor_cloak.is_alive(self._cursor):
            self.stop_cursor_cloak()
            return False
        cursor_cloak.update(self._cursor)
        return True

    def stop_cursor_cloak(self) -> None:
        if self._cursor:
            cursor_cloak.stop(self._cursor)
            self._cursor = None

    def reset_cursor(self) -> None:
        self.stop_cursor_cloak()
        cursor_cloak.force_restore()

    def protect_self(self, tk_root) -> bool:
        try:
            tk_root.update_idletasks()
            child = tk_root.winfo_id()
            self._own_hwnd = user32.GetAncestor(child, GA_ROOT) or child
            return bool(user32.SetWindowDisplayAffinity(self._own_hwnd, WDA_EXCLUDEFROMCAPTURE))
        except Exception:
            self._own_hwnd = None
            return False

    def unprotect_self(self) -> None:
        self.stop_cursor_cloak()
        self.clear_focus_shield()
        if self._own_hwnd:
            try:
                user32.SetWindowDisplayAffinity(self._own_hwnd, WDA_NONE)
            except Exception:
                pass

    supports_tray = True

    def setup_tray(self, on_restore: Callable[[], None], on_quit: Callable[[], None]) -> None:
        self._tray = _Tray(on_restore, on_quit)

    def notify(self, title: str, text: str) -> None:
        if self._tray:
            self._tray.notify(title, text)

    def remove_tray(self) -> None:
        if self._tray:
            self._tray.remove()
            self._tray = None


class _Tray:
    def __init__(self, on_restore: Callable[[], None], on_quit: Callable[[], None]):
        self._on_restore = on_restore
        self._on_quit = on_quit
        self.hinst = kernel32.GetModuleHandleW(None)
        self.wndproc = WNDPROCTYPE(self._wndproc)
        classname = "ScreenShareGuardTray"
        self.wc = WNDCLASS()
        self.wc.lpfnWndProc = self.wndproc
        self.wc.hInstance = self.hinst
        self.wc.lpszClassName = classname
        user32.RegisterClassW(ctypes.byref(self.wc))
        self.hwnd = user32.CreateWindowExW(0, classname, "guard", WS_OVERLAPPED,
                                           CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
                                           None, None, self.hinst, None)
        self.hicon = self._load_icon()
        self.nid = NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self.nid.uCallbackMessage = TRAY_CALLBACK
        self.nid.hIcon = self.hicon
        self.nid.szTip = f"{APP_NAME} (running)"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid))

    def _load_icon(self):
        ico = logo_ico()
        if ico:
            handle = user32.LoadImageW(None, ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if handle:
                return handle
        return user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == TRAY_CALLBACK:
            if lparam == WM_LBUTTONDBLCLK:
                self._on_restore()
            elif lparam == WM_RBUTTONUP:
                self._menu()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_RESTORE, "Show window")
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Quit (stop protecting)")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if cmd == ID_RESTORE:
            self._on_restore()
        elif cmd == ID_QUIT:
            self._on_quit()

    def notify(self, title: str, text: str) -> None:
        self.nid.uFlags = NIF_INFO
        self.nid.szInfoTitle = title
        self.nid.szInfo = text
        self.nid.dwInfoFlags = 0
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP

    def remove(self) -> None:
        try:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
        except Exception:
            pass
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
