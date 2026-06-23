from __future__ import annotations

import ctypes
import struct
import sys
from ctypes import wintypes
from typing import Callable

from ..about import APP_NAME
from ..assets import logo_ico
from ..model import WindowInfo
from .base import Backend

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

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
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
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
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]

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

    shell32.IsUserAnAdmin.restype = wintypes.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL


_bind()
SWDA_ADDR = ctypes.cast(user32.SetWindowDisplayAffinity, ctypes.c_void_p).value
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


def _shellcode(hwnd: int, affinity: int, func_addr: int) -> bytes:
    # mov rcx,hwnd  mov edx,affinity  mov rax,func  sub rsp,0x28  call rax  add rsp,0x28  ret
    return (
        b"\x48\xB9" + struct.pack("<Q", hwnd & 0xFFFFFFFFFFFFFFFF) +
        b"\xBA" + struct.pack("<I", affinity & 0xFFFFFFFF) +
        b"\x48\xB8" + struct.pack("<Q", func_addr) +
        b"\x48\x83\xEC\x28" +
        b"\xFF\xD0" +
        b"\x48\x83\xC4\x28" +
        b"\xC3"
    )


def _inject_affinity(hwnd: int, affinity: int) -> bool:
    """Run SetWindowDisplayAffinity from inside the window's own process."""
    if not user32.IsWindow(hwnd) or not IS_64BIT or not SWDA_ADDR:
        return False

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False

    handle = kernel32.OpenProcess(INJECT_ACCESS, False, pid.value)
    if not handle:
        return False
    try:
        wow64 = wintypes.BOOL()
        if kernel32.IsWow64Process(handle, ctypes.byref(wow64)) and wow64.value:
            return False

        code = _shellcode(hwnd, affinity, SWDA_ADDR)
        addr = kernel32.VirtualAllocEx(handle, None, len(code), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
        if not addr:
            return False
        try:
            written = ctypes.c_size_t(0)
            if not kernel32.WriteProcessMemory(handle, addr, code, len(code), ctypes.byref(written)):
                return False
            thread = kernel32.CreateRemoteThread(handle, None, 0, addr, None, 0, None)
            if not thread:
                return False
            try:
                kernel32.WaitForSingleObject(thread, 5000)
                result = wintypes.DWORD()
                kernel32.GetExitCodeThread(thread, ctypes.byref(result))
                return bool(result.value)
            finally:
                kernel32.CloseHandle(thread)
        finally:
            kernel32.VirtualFreeEx(handle, addr, 0, MEM_RELEASE)
    finally:
        kernel32.CloseHandle(handle)


class WindowsBackend(Backend):
    name = "windows"
    can_hide_other_apps = True

    def __init__(self):
        self._own_hwnd = None
        self._tray = None

    def ensure_privileges(self) -> bool:
        try:
            is_admin = bool(shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False
        if is_admin:
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
        return _inject_affinity(window_id, WDA_EXCLUDEFROMCAPTURE)

    def show(self, window_id: int) -> bool:
        return _inject_affinity(window_id, WDA_NONE)

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
