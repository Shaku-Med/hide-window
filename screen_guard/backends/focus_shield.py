"""Focus shield for keep-active.

Chromium/Brave page focus:

  Modern Aura path: WM_ACTIVATE(WA_INACTIVE) on Chrome_WidgetWin_1
    -> HWNDMessageHandler -> HandleActivationChanged(false)
    -> RenderWidgetHost::Blur() -> window.blur + hasFocus()===false

  Legacy HasFocus check: ::GetFocus() == Chrome_RenderWidgetHostHWND

Critical bug we hit: Chrome leaves GWLP_WNDPROC == 0 and uses the class
window procedure (GCLP_WNDPROC). The old shield skipped those HWNDs, so the
top-level never got subclassed and activate/kill-focus still reached Brave.

Fix:
1. Subclass every HWND; if instance wndproc is 0, CallWindowProc the class proc.
2. Inline-hook GetFocus / GetForegroundWindow / GetActiveWindow in-process.
"""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from dataclasses import dataclass, field

from ..logutil import LOG_PATH, log, log_section, win_err

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

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

GWLP_WNDPROC = -4
GCLP_WNDPROC = -24
WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_KILLFOCUS = 0x0008
WM_ACTIVATEAPP = 0x001C
WM_NCACTIVATE = 0x0086
CFG_CALL_TARGET_VALID = 0x00000001

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
LRESULT = ctypes.c_ssize_t


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class CFG_CALL_TARGET_INFO(ctypes.Structure):
    _fields_ = [("Offset", ctypes.c_ulonglong), ("Flags", ctypes.c_ulonglong)]


def _bind():
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                           ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.VirtualProtectEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
                                          wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.VirtualProtectEx.restype = wintypes.BOOL
    kernel32.FlushInstructionCache.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, ctypes.c_size_t]
    kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
                                        wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualAllocEx.restype = wintypes.LPVOID
    kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
                                            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.CreateRemoteThread.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID,
        wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
    ]
    kernel32.CreateRemoteThread.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeThread.restype = wintypes.BOOL
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.FlushInstructionCache.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, ctypes.c_size_t]
    kernel32.FlushInstructionCache.restype = wintypes.BOOL

    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.GetFocus.restype = wintypes.HWND
    user32.GetActiveWindow.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowUnicode.argtypes = [wintypes.HWND]
    user32.IsWindowUnicode.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrA.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrA.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrA.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrA.restype = ctypes.c_ssize_t
    user32.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
    user32.GetClassLongPtrA.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetClassLongPtrA.restype = ctypes.c_ssize_t
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                       wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcA.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                       wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcA.restype = LRESULT
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    try:
        kbase = ctypes.WinDLL("kernelbase", use_last_error=True)
        kbase.SetProcessValidCallTargets.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.ULONG,
            ctypes.POINTER(CFG_CALL_TARGET_INFO),
        ]
        kbase.SetProcessValidCallTargets.restype = wintypes.BOOL
        globals()["_SetProcessValidCallTargets"] = kbase.SetProcessValidCallTargets
    except Exception:
        globals()["_SetProcessValidCallTargets"] = None


_bind()
IS_64BIT = ctypes.sizeof(ctypes.c_void_p) == 8
last_error: str = ""


def _set_error(msg: str) -> None:
    global last_error
    last_error = msg
    if msg:
        log(f"ERROR: {msg}")


def _read_mem(process, addr: int, size: int) -> bytes | None:
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t(0)
    if not kernel32.ReadProcessMemory(process, addr, buf, size, ctypes.byref(got)):
        return None
    return bytes(buf[: got.value])


def _write_mem(process, addr: int, data: bytes) -> bool:
    written = ctypes.c_size_t(0)
    return bool(kernel32.WriteProcessMemory(process, addr, data, len(data), ctypes.byref(written)))


def _whitelist_cfg(process, region: int, offsets: list[int], region_size: int = 0x1000) -> None:
    fn = globals().get("_SetProcessValidCallTargets")
    if not fn or not offsets:
        return
    infos = (CFG_CALL_TARGET_INFO * len(offsets))()
    for i, off in enumerate(offsets):
        infos[i].Offset = off
        infos[i].Flags = CFG_CALL_TARGET_VALID
    fn(process, region, region_size, len(offsets), infos)


def _user32_addr(func) -> int:
    """System DLLs share one session ASLR base — same trick as SetWindowDisplayAffinity inject."""
    return int(ctypes.cast(func, ctypes.c_void_p).value or 0)


@dataclass
class _RemoteSetResult:
    prev: int
    current: int
    last_error: int
    thread_exit: int


def _shellcode_set_wndproc(
    hwnd: int, new_proc: int, set_fn: int, get_fn: int, get_last_error: int, out_addr: int
) -> bytes:
    """x64: SetWindowLongPtr; GetLastError; GetWindowLongPtr → out_addr[0/8/16]."""
    # out layout: +0 prev, +8 current, +16 last_error (u64)
    idx = struct.pack("<I", GWLP_WNDPROC & 0xFFFFFFFF)
    return (
        b"\x48\x83\xEC\x28"
        # SetWindowLongPtr(hwnd, GWLP_WNDPROC, new_proc)
        + b"\x48\xB9" + struct.pack("<Q", hwnd & 0xFFFFFFFFFFFFFFFF)
        + b"\xBA" + idx
        + b"\x49\xB8" + struct.pack("<Q", new_proc & 0xFFFFFFFFFFFFFFFF)
        + b"\x48\xB8" + struct.pack("<Q", set_fn & 0xFFFFFFFFFFFFFFFF)
        + b"\xFF\xD0"
        + b"\x48\xB9" + struct.pack("<Q", out_addr & 0xFFFFFFFFFFFFFFFF)
        + b"\x48\x89\x01"  # mov [out+0], rax  (prev)
        # GetLastError() immediately after set
        + b"\x48\xB8" + struct.pack("<Q", get_last_error & 0xFFFFFFFFFFFFFFFF)
        + b"\xFF\xD0"
        + b"\x48\xB9" + struct.pack("<Q", (out_addr + 16) & 0xFFFFFFFFFFFFFFFF)
        + b"\x48\x89\x01"  # mov [out+16], rax
        # GetWindowLongPtr(hwnd, GWLP_WNDPROC) — in-process verify
        + b"\x48\xB9" + struct.pack("<Q", hwnd & 0xFFFFFFFFFFFFFFFF)
        + b"\xBA" + idx
        + b"\x48\xB8" + struct.pack("<Q", get_fn & 0xFFFFFFFFFFFFFFFF)
        + b"\xFF\xD0"
        + b"\x48\xB9" + struct.pack("<Q", (out_addr + 8) & 0xFFFFFFFFFFFFFFFF)
        + b"\x48\x89\x01"  # mov [out+8], rax  (current)
        + b"\x48\x83\xC4\x28"
        + b"\x33\xC0"
        + b"\xC3"
    )


def _remote_set_wndproc(
    process, pid: int, hwnd: int, new_proc: int, unicode: bool
) -> _RemoteSetResult | None:
    """SetWindowLongPtr from inside the target process (cross-process is denied on Chromium)."""
    del pid  # user32 session ASLR — local addr is valid remotely
    set_fn = _user32_addr(user32.SetWindowLongPtrW if unicode else user32.SetWindowLongPtrA)
    get_fn = _user32_addr(user32.GetWindowLongPtrW if unicode else user32.GetWindowLongPtrA)
    gle = _user32_addr(kernel32.GetLastError)
    if not set_fn or not get_fn or not gle:
        log("  remote SetWindowLongPtr: FAIL resolve user32/kernel32 addrs")
        return None
    log(f"  remote addrs set={set_fn:#x} get={get_fn:#x} gle={gle:#x}")

    # [0:24] out struct, [24:] shellcode
    ctypes.set_last_error(0)
    remote = kernel32.VirtualAllocEx(
        process, None, 0x200, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
    )
    if not remote:
        log(f"  remote SetWindowLongPtr: FAIL VirtualAllocEx ({win_err()})")
        return None
    remote = int(remote)
    out_addr = remote
    code_addr = remote + 24
    code = _shellcode_set_wndproc(hwnd, new_proc, set_fn, get_fn, gle, out_addr)
    blob = b"\x00" * 24 + code
    try:
        if not _write_mem(process, remote, blob):
            log(f"  remote SetWindowLongPtr: FAIL WriteProcessMemory ({win_err()})")
            return None
        _whitelist_cfg(process, remote, [24], 0x200)
        kernel32.FlushInstructionCache(process, code_addr, len(code))
        ctypes.set_last_error(0)
        thread = kernel32.CreateRemoteThread(process, None, 0, code_addr, None, 0, None)
        if not thread:
            log(f"  remote SetWindowLongPtr: FAIL CreateRemoteThread ({win_err()})")
            return None
        try:
            wait = kernel32.WaitForSingleObject(thread, 5000)
            exit_code = wintypes.DWORD(0xFFFFFFFF)
            kernel32.GetExitCodeThread(thread, ctypes.byref(exit_code))
            if wait != 0:  # WAIT_OBJECT_0
                log(f"  remote SetWindowLongPtr: FAIL wait={wait} exit={exit_code.value:#x} ({win_err()})")
                return None
            raw = _read_mem(process, out_addr, 24)
            if raw is None:
                log(f"  remote SetWindowLongPtr: FAIL read result ({win_err()})")
                return None
            prev, current, last_err = struct.unpack("<QQQ", raw)
            result = _RemoteSetResult(
                prev=prev, current=current, last_error=last_err, thread_exit=exit_code.value
            )
            log(
                f"  remote SetWindowLongPtr prev={prev:#x} current={current:#x} "
                f"want={new_proc:#x} last_error={last_err} thread_exit={exit_code.value:#x}"
            )
            return result
        finally:
            kernel32.CloseHandle(thread)
    finally:
        kernel32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _list_tree(root: int) -> list[int]:
    found = [int(root)]
    # Keep the ctypes callback alive for the whole enum (classic ctypes pitfall).
    def cb(hwnd, _):
        found.append(int(hwnd))
        return True

    enum_cb = WNDENUMPROC(cb)
    user32.EnumChildWindows(root, enum_cb, 0)
    _list_tree._keep = enum_cb  # noqa: B018 — prevent GC during nested calls
    return found


def _find_render_widget(root: int) -> int | None:
    for hwnd in _list_tree(root):
        if "RenderWidgetHost" in _class_name(hwnd):
            return hwnd
    return None


def _capture_focus_target(root: int, thread_id: int) -> int:
    rwhv = _find_render_widget(root)
    if rwhv:
        return rwhv
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)) and info.hwndFocus:
        focus = int(info.hwndFocus)
        for hwnd in _list_tree(root):
            if hwnd == focus:
                return focus
    return int(root)


def resolve_wndproc(hwnd: int, unicode: bool) -> tuple[int, int]:
    """
    Return (instance_proc, call_target).

    Chrome_WidgetWin_1 normally has instance_proc == 0 and uses the class proc.
    We must CallWindowProc(call_target) and restore instance_proc on remove.
    """
    get_long = user32.GetWindowLongPtrW if unicode else user32.GetWindowLongPtrA
    get_class = user32.GetClassLongPtrW if unicode else user32.GetClassLongPtrA
    instance = int(get_long(hwnd, GWLP_WNDPROC))
    if instance:
        return instance, instance
    class_proc = int(get_class(hwnd, GCLP_WNDPROC))
    return 0, class_proc


def build_subclass_wndproc(data_base: int, call_window_proc: int) -> bytes:
    """data_base+0 = original/call-target WndProc. Drops deactivate messages."""
    code = bytearray()
    fixups: list[tuple[int, str]] = []
    labels: dict[str, int] = {}

    def emit(b: bytes):
        code.extend(b)

    def mark(label: str):
        labels[label] = len(code)

    def rel8(label: str):
        fixups.append((len(code), label))
        emit(b"\x00")

    emit(b"\x81\xFA" + struct.pack("<I", WM_KILLFOCUS))
    emit(b"\x74")
    rel8("swallow")

    emit(b"\x81\xFA" + struct.pack("<I", WM_ACTIVATEAPP))
    emit(b"\x75")
    rel8("check_act")
    emit(b"\x4D\x85\xC0")
    emit(b"\x74")
    rel8("swallow")
    emit(b"\xEB")
    rel8("forward")

    mark("check_act")
    emit(b"\x81\xFA" + struct.pack("<I", WM_ACTIVATE))
    emit(b"\x75")
    rel8("check_nc")
    emit(b"\x44\x89\xC0")
    emit(b"\x25\xFF\xFF\x00\x00")
    emit(b"\x85\xC0")
    emit(b"\x74")
    rel8("swallow")
    emit(b"\xEB")
    rel8("forward")

    mark("check_nc")
    emit(b"\x81\xFA" + struct.pack("<I", WM_NCACTIVATE))
    emit(b"\x75")
    rel8("forward")
    emit(b"\x4D\x85\xC0")
    emit(b"\x75")
    rel8("forward")
    emit(b"\xB8\x01\x00\x00\x00")
    emit(b"\xC3")

    mark("swallow")
    emit(b"\x31\xC0")
    emit(b"\xC3")

    mark("forward")
    emit(b"\x48\x83\xEC\x28")
    emit(b"\x4C\x89\x4C\x24\x20")
    emit(b"\x49\x89\xCA")
    emit(b"\x49\x89\xD3")
    emit(b"\x48\xB8" + struct.pack("<Q", data_base & 0xFFFFFFFFFFFFFFFF))
    emit(b"\x48\x8B\x00")
    emit(b"\x48\x89\xC1")
    emit(b"\x4C\x89\xD2")
    emit(b"\x4D\x89\xC1")
    emit(b"\x4D\x89\xD8")
    emit(b"\x48\xB8" + struct.pack("<Q", call_window_proc & 0xFFFFFFFFFFFFFFFF))
    emit(b"\xFF\xD0")
    emit(b"\x48\x83\xC4\x28")
    emit(b"\xC3")

    for pos, label in fixups:
        rel = labels[label] - (pos + 1)
        if rel < -128 or rel > 127:
            raise ValueError(f"rel8 out of range for {label}: {rel}")
        code[pos] = rel & 0xFF
    return bytes(code)


@dataclass
class _Subclass:
    hwnd: int
    remote: int
    restore_proc: int  # instance value to put back (often 0 for Chrome)
    unicode: bool


@dataclass
class ShieldState:
    hwnd: int
    process: int
    subclasses: list[_Subclass] = field(default_factory=list)
    spoof_focus: int = 0


def _subclass_one(process, pid: int, hwnd: int) -> _Subclass | None:
    cls = _class_name(hwnd)
    unicode = bool(user32.IsWindowUnicode(hwnd))
    restore_proc, call_target = resolve_wndproc(hwnd, unicode)
    log(f"subclass hwnd={hwnd:#x} class={cls!r} unicode={unicode} "
        f"instance={restore_proc:#x} call_target={call_target:#x}")
    if not call_target:
        log(f"  FAIL: no call_target ({win_err()})")
        return None

    # Same session-ASLR trick as hide-window affinity inject.
    call_proc = _user32_addr(user32.CallWindowProcW if unicode else user32.CallWindowProcA)
    if not call_proc:
        log("  FAIL: CallWindowProc addr")
        return None

    code = build_subclass_wndproc(0, call_proc)
    total = max(0x1000, 8 + len(code))
    ctypes.set_last_error(0)
    remote = kernel32.VirtualAllocEx(process, None, total, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
    if not remote:
        log(f"  FAIL: VirtualAllocEx size={total} ({win_err()})")
        return None
    remote = int(remote)
    code = build_subclass_wndproc(remote, call_proc)
    blob = struct.pack("<Q", call_target & 0xFFFFFFFFFFFFFFFF) + code
    if not _write_mem(process, remote, blob):
        log(f"  FAIL: WriteProcessMemory trampoline ({win_err()})")
        kernel32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)
        return None
    _whitelist_cfg(process, remote, [8], total)
    kernel32.FlushInstructionCache(process, remote + 8, len(code))

    want = remote + 8
    # Cross-process Set/GetWindowLongPtr(GWLP_WNDPROC) is denied / always 0 on Chromium.
    # Always set + verify from inside the target process.
    log(f"  in-process SetWindowLongPtr want={want:#x}")
    remote_result = _remote_set_wndproc(process, pid, hwnd, want, unicode)
    if not remote_result:
        kernel32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)
        return None
    if remote_result.thread_exit not in (0,):
        log(f"  FAIL: remote thread crashed exit={remote_result.thread_exit:#x}")
        kernel32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)
        return None
    if remote_result.current != want:
        log(
            f"  FAIL: in-process verify mismatch current={remote_result.current:#x} "
            f"want={want:#x} last_error={remote_result.last_error}"
        )
        kernel32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)
        return None
    # prev==want means a prior attempt already installed the same VA (still success).
    restore_proc = remote_result.prev if remote_result.prev != want else 0
    log("  OK (in-process verified)")
    return _Subclass(hwnd=hwnd, remote=remote, restore_proc=restore_proc, unicode=unicode)


def _remove_subclass(process, sub: _Subclass) -> None:
    try:
        if not user32.IsWindow(sub.hwnd):
            return
        # Cross-process GetWindowLongPtr cannot see the subclass; always restore remotely.
        pid_dw = wintypes.DWORD()
        user32.GetWindowThreadProcessId(sub.hwnd, ctypes.byref(pid_dw))
        if pid_dw.value:
            _remote_set_wndproc(process, pid_dw.value, sub.hwnd, sub.restore_proc, sub.unicode)
    except Exception:
        pass


def install(hwnd: int) -> ShieldState | None:
    _set_error("")
    log_section(f"focus shield install hwnd={int(hwnd):#x}")
    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        admin = False
    log(f"admin={admin} 64bit={IS_64BIT}")
    log(f"log file: {LOG_PATH}")

    if not IS_64BIT or not user32.IsWindow(hwnd):
        _set_error("need 64-bit Python and a live window")
        return None

    pid_dw = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_dw))
    pid = pid_dw.value
    log(f"pid={pid} tid={thread_id} class={_class_name(hwnd)!r}")
    if not pid or not thread_id:
        _set_error("could not read window pid")
        return None

    ctypes.set_last_error(0)
    process = kernel32.OpenProcess(INJECT_ACCESS, False, pid)
    if not process:
        _set_error(f"OpenProcess failed ({win_err()}) — run Cloak as admin")
        return None
    log(f"OpenProcess OK handle={int(process)}")

    wow64 = wintypes.BOOL()
    if kernel32.IsWow64Process(process, ctypes.byref(wow64)) and wow64.value:
        kernel32.CloseHandle(process)
        _set_error("target is 32-bit; shield needs 64-bit")
        return None

    spoof_focus = _capture_focus_target(hwnd, thread_id)
    log(f"spoof_focus={spoof_focus:#x} focus_class={_class_name(spoof_focus)!r}")

    # Only the top-level Chrome_WidgetWin_1 needs subclassing for WM_ACTIVATE.
    # Subclassing children caused remote-thread AVs and is unnecessary.
    log(f"window tree count={len(_list_tree(hwnd))} (subclassing root only)")
    subclasses: list[_Subclass] = []
    sub = _subclass_one(process, pid, int(hwnd))
    if not sub:
        restore, call = resolve_wndproc(hwnd, bool(user32.IsWindowUnicode(hwnd)))
        kernel32.CloseHandle(process)
        _set_error(f"root subclass failed (instance={restore:#x} class={call:#x} {win_err()})")
        return None
    subclasses.append(sub)
    log(f"subclasses installed={len(subclasses)} root_ok=True")

    # The subclass alone keeps the page present by swallowing its own deactivation.
    # We deliberately do not patch GetFocus/GetForegroundWindow: those live in the
    # shared browser process, so spoofing them freezes every other window the user
    # is trying to work in. The one-shot pulse below only nudges the kept window,
    # which is the focused one at arm time.
    user32.PostMessageW(hwnd, WM_NCACTIVATE, 1, 0)
    user32.PostMessageW(hwnd, WM_ACTIVATE, 1, 0)
    if spoof_focus != hwnd:
        user32.PostMessageW(spoof_focus, WM_SETFOCUS, 0, 0)

    _set_error("")
    log(f"INSTALL SUCCESS subclasses={len(subclasses)}")
    log(f"full log file: {LOG_PATH}")
    return ShieldState(
        hwnd=hwnd,
        process=int(process),
        subclasses=subclasses,
        spoof_focus=spoof_focus,
    )


def reinforce(state: ShieldState) -> None:
    """Kept window is in the background. Keep its frame painted active, but never
    push activation or focus while the user works elsewhere. The subclass already
    keeps the page present, and re-asserting focus here would steal it back from
    the window the user is actually typing in. Posted, so it never blocks the UI."""
    if not user32.IsWindow(state.hwnd):
        return
    user32.PostMessageW(state.hwnd, WM_NCACTIVATE, 1, 0)


def resync_real_focus(state: ShieldState) -> None:
    """When the shielded window is OS-foreground again, re-pulse focus so the page
    is not stuck on a leaked blur / stale JS focus flag."""
    if not user32.IsWindow(state.hwnd):
        return
    user32.PostMessageW(state.hwnd, WM_NCACTIVATE, 1, 0)
    user32.PostMessageW(state.hwnd, WM_ACTIVATE, 1, 0)
    target = state.spoof_focus if state.spoof_focus and user32.IsWindow(state.spoof_focus) else state.hwnd
    user32.PostMessageW(target, WM_SETFOCUS, 0, 0)


def remove(state: ShieldState) -> None:
    for sub in state.subclasses:
        _remove_subclass(state.process, sub)
        try:
            kernel32.VirtualFreeEx(state.process, sub.remote, 0, MEM_RELEASE)
        except Exception:
            pass
    try:
        kernel32.CloseHandle(state.process)
    except Exception:
        pass


def is_alive(state: ShieldState) -> bool:
    if not user32.IsWindow(state.hwnd):
        return False
    # Cross-process GetWindowLongPtr(GWLP_WNDPROC) always reads 0 on Chromium,
    # so we only check that the root window and our recorded subclass still exist.
    for sub in state.subclasses:
        if sub.hwnd == state.hwnd and user32.IsWindow(sub.hwnd):
            return True
    return False


def sync_children(state: ShieldState) -> None:
    # Root-only shield — child HWNDs are not subclassed.
    return
