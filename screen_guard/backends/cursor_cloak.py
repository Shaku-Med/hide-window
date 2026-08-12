"""Cursor cloak for keep-active.

Windows has a single global cursor that every screen capturer samples directly,
so the real pointer betrays that you are working in a hidden window: it drifts
into empty space and flips to an I-beam over text. There is no way to give the
capture a different cursor position than your own.

The workaround here has three parts:

1. Replace every system cursor with a fully transparent one, so the true pointer
   renders nowhere. Input still lands where the real (invisible) cursor is.
2. Draw a pointer you can still see as a topmost, click-through overlay that
   follows the mouse and is excluded from capture (WDA_EXCLUDEFROMCAPTURE).
3. Draw a decoy pointer, parked inside the kept window, that IS captured. The
   stream sees a cursor resting in the active window.

The decoy is an ordinary window, so the user sees it too. That is fine while they
are away, but the moment they come back to the kept window there would be two
pointers on screen. So the cloak engages only while the user is actually working
elsewhere, and drops back to the plain system cursor as soon as they return.

Restoring the system cursors uses SPI_SETCURSORS, which reloads the user's own
scheme, so it is non-destructive.
"""

from __future__ import annotations

import ctypes
import math
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# wintypes does not ship these GDI handle aliases.
HCURSOR = wintypes.HANDLE
HPEN = wintypes.HANDLE
HBRUSH = wintypes.HANDLE
HGDIOBJ = wintypes.HANDLE
COLORREF = wintypes.DWORD

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SW_SHOWNA = 8
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
LWA_COLORKEY = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WM_PAINT = 0x000F
PS_SOLID = 0

SPI_SETCURSORS = 0x0057
SPIF_SENDCHANGE = 0x02

COLOR_KEY = 0x00FF00FF  # magenta background -> transparent
ARROW_WHITE = 0x00FFFFFF
ARROW_BLACK = 0x00000000

OVERLAY_W = 18
OVERLAY_H = 30
# Classic pointer outline, tip at (0, 0).
ARROW_POINTS = [(0, 0), (0, 22), (5, 17), (9, 26), (12, 25), (8, 16), (15, 16)]

# A pointer frozen to the pixel for minutes is its own tell, so the decoy wanders
# a few pixels on two slow, mismatched periods. Roughly 8s and 13s at a 15ms tick.
DRIFT_PX = 3
DRIFT_X_PERIOD = 90.0
DRIFT_Y_PERIOD = 140.0

# How fast the decoy glides back to its parking spot. Snapping there would look
# like a teleport on the stream, so it eases instead.
GLIDE = 0.16
SNAP_PX = 1.0

# Every cursor role, so no shape (I-beam, hand, resize) can leak.
OCR_IDS = [32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644,
           32645, 32646, 32648, 32649, 32650, 32651]

LRESULT = ctypes.c_ssize_t
WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROCTYPE), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32),
    ]


def _bind():
    user32.CreateCursor.argtypes = [wintypes.HINSTANCE, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.LPCVOID, wintypes.LPCVOID]
    user32.CreateCursor.restype = HCURSOR
    user32.SetSystemCursor.argtypes = [HCURSOR, wintypes.DWORD]
    user32.SetSystemCursor.restype = wintypes.BOOL
    user32.DestroyCursor.argtypes = [HCURSOR]
    user32.DestroyCursor.restype = wintypes.BOOL
    user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT]
    user32.SystemParametersInfoW.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, COLORREF, wintypes.BYTE, wintypes.DWORD]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.UpdateWindow.argtypes = [wintypes.HWND]
    user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.BeginPaint.restype = wintypes.HDC
    user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), HBRUSH]

    gdi32.CreateSolidBrush.argtypes = [COLORREF]
    gdi32.CreateSolidBrush.restype = HBRUSH
    gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, COLORREF]
    gdi32.CreatePen.restype = HPEN
    gdi32.SelectObject.argtypes = [wintypes.HDC, HGDIOBJ]
    gdi32.SelectObject.restype = HGDIOBJ
    gdi32.DeleteObject.argtypes = [HGDIOBJ]
    gdi32.Polygon.argtypes = [wintypes.HDC, ctypes.c_void_p, ctypes.c_int]

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE


_bind()
IS_64BIT = ctypes.sizeof(ctypes.c_void_p) == 8
_class_atom = 0
_wndproc_ref = None  # keep the callback alive for the process lifetime


def _paint(hwnd: int) -> None:
    ps = PAINTSTRUCT()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    if not hdc:
        return
    key = gdi32.CreateSolidBrush(COLOR_KEY)
    white = gdi32.CreateSolidBrush(ARROW_WHITE)
    pen = gdi32.CreatePen(PS_SOLID, 1, ARROW_BLACK)
    try:
        rc = wintypes.RECT(0, 0, OVERLAY_W, OVERLAY_H)
        user32.FillRect(hdc, ctypes.byref(rc), key)
        old_pen = gdi32.SelectObject(hdc, pen)
        old_brush = gdi32.SelectObject(hdc, white)
        pts = (wintypes.POINT * len(ARROW_POINTS))(*[wintypes.POINT(x, y) for x, y in ARROW_POINTS])
        gdi32.Polygon(hdc, ctypes.cast(pts, ctypes.c_void_p), len(ARROW_POINTS))
        gdi32.SelectObject(hdc, old_pen)
        gdi32.SelectObject(hdc, old_brush)
    finally:
        gdi32.DeleteObject(key)
        gdi32.DeleteObject(white)
        gdi32.DeleteObject(pen)
        user32.EndPaint(hwnd, ctypes.byref(ps))


def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_PAINT:
        _paint(hwnd)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _ensure_class() -> bool:
    global _class_atom, _wndproc_ref
    if _class_atom:
        return True
    _wndproc_ref = WNDPROCTYPE(_wndproc)
    wc = WNDCLASS()
    wc.lpfnWndProc = _wndproc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = "ScreenGuardCursorOverlay"
    _class_atom = user32.RegisterClassW(ctypes.byref(wc))
    return bool(_class_atom)


def _make_overlay(exclude_from_capture: bool) -> int | None:
    if not _ensure_class():
        return None
    ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    hwnd = user32.CreateWindowExW(ex, "ScreenGuardCursorOverlay", None, WS_POPUP,
                                  0, 0, OVERLAY_W, OVERLAY_H, None, None,
                                  kernel32.GetModuleHandleW(None), None)
    if not hwnd:
        return None
    user32.SetLayeredWindowAttributes(hwnd, COLOR_KEY, 0, LWA_COLORKEY)
    if exclude_from_capture:
        if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            user32.DestroyWindow(hwnd)
            return None
    return int(hwnd)


def _transparent_cursor() -> int | None:
    size = 32
    plane = size * size // 8
    and_plane = b"\xFF" * plane
    xor_plane = b"\x00" * plane
    cur = user32.CreateCursor(None, 0, 0, size, size, and_plane, xor_plane)
    return int(cur) if cur else None


def _hide_system_cursor() -> bool:
    ok_primary = False
    for ocr in OCR_IDS:
        cur = _transparent_cursor()
        if not cur:
            continue
        # On success SetSystemCursor owns and frees the handle; free it ourselves if not.
        if user32.SetSystemCursor(cur, ocr):
            if ocr == 32512:
                ok_primary = True
        else:
            user32.DestroyCursor(cur)
    return ok_primary


def _restore_system_cursor() -> None:
    user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_SENDCHANGE)


def force_restore() -> None:
    """Reload the user's cursor scheme with no live cloak, for crash recovery."""
    _restore_system_cursor()


def _destroy(hwnd: int) -> None:
    try:
        if hwnd and user32.IsWindow(hwnd):
            user32.DestroyWindow(hwnd)
    except Exception:
        pass


@dataclass
class Cloak:
    active_hwnd: int
    real: int
    decoy: int
    engaged: bool = False
    phase: int = 0
    decoy_x: float = 0.0
    decoy_y: float = 0.0
    parked: bool = False       # decoy has a known position to glide from
    real_shown: bool = False
    decoy_shown: bool = False


def start(active_hwnd: int) -> Cloak | None:
    if not IS_64BIT or not user32.IsWindow(active_hwnd):
        return None
    real = _make_overlay(exclude_from_capture=True)
    if not real:
        return None
    decoy = _make_overlay(exclude_from_capture=False)
    if not decoy:
        _destroy(real)
        return None
    # Overlays stay hidden until the user actually leaves the kept window.
    state = Cloak(active_hwnd=int(active_hwnd), real=real, decoy=decoy)
    update(state)
    return state


def _window_rect(hwnd: int) -> wintypes.RECT | None:
    rc = wintypes.RECT()
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return None
    if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
        return None
    return rc if rc.right > rc.left and rc.bottom > rc.top else None


def _cursor_pos() -> wintypes.POINT | None:
    pt = wintypes.POINT()
    return pt if user32.GetCursorPos(ctypes.byref(pt)) else None


def _inside(rc: wintypes.RECT, pt: wintypes.POINT) -> bool:
    return rc.left <= pt.x < rc.right and rc.top <= pt.y < rc.bottom


def _set_shown(state: Cloak, hwnd: int, shown: bool, is_real: bool) -> None:
    current = state.real_shown if is_real else state.decoy_shown
    if current == shown:
        return
    user32.ShowWindow(hwnd, SW_SHOWNA if shown else SW_HIDE)
    if shown:
        user32.UpdateWindow(hwnd)
    if is_real:
        state.real_shown = shown
    else:
        state.decoy_shown = shown


def _move(hwnd: int, x: float, y: float) -> None:
    user32.SetWindowPos(hwnd, HWND_TOPMOST, int(round(x)), int(round(y)), 0, 0,
                        SWP_NOSIZE | SWP_NOACTIVATE)


def _engage(state: Cloak) -> bool:
    if state.engaged:
        return True
    if not _hide_system_cursor():
        _restore_system_cursor()
        return False
    state.engaged = True
    state.parked = False
    return True


def _disengage(state: Cloak) -> None:
    if not state.engaged:
        return
    _set_shown(state, state.real, False, True)
    _set_shown(state, state.decoy, False, False)
    _restore_system_cursor()
    state.engaged = False
    state.parked = False


def update(state: Cloak) -> None:
    rc = _window_rect(state.active_hwnd)
    pt = _cursor_pos()
    if rc is None or pt is None:
        _disengage(state)
        return

    over_window = _inside(rc, pt)
    focused = int(user32.GetForegroundWindow() or 0) == state.active_hwnd
    if over_window and focused:
        # Genuinely back: hand the real cursor over, shapes and all.
        _disengage(state)
        return

    if not _engage(state):
        return

    if over_window:
        # Pointer is hovering the kept window while the user works elsewhere.
        # Its real position is already natural for the stream, so both sides
        # share the decoy and the follow overlay steps aside. One pointer, no
        # lag, and nothing jumps when you cross the window edge.
        _set_shown(state, state.real, False, True)
        _set_shown(state, state.decoy, True, False)
        state.decoy_x, state.decoy_y = float(pt.x), float(pt.y)
        state.parked = True
        _move(state.decoy, state.decoy_x, state.decoy_y)
        return

    _set_shown(state, state.real, True, True)
    _set_shown(state, state.decoy, True, False)
    _move(state.real, pt.x, pt.y)

    state.phase += 1
    target_x = rc.left + (rc.right - rc.left) / 2 + DRIFT_PX * math.sin(state.phase / DRIFT_X_PERIOD)
    target_y = rc.top + (rc.bottom - rc.top) / 2 + DRIFT_PX * math.sin(state.phase / DRIFT_Y_PERIOD)
    if not state.parked:
        state.decoy_x, state.decoy_y = target_x, target_y
        state.parked = True
    else:
        state.decoy_x += (target_x - state.decoy_x) * GLIDE
        state.decoy_y += (target_y - state.decoy_y) * GLIDE
        if abs(target_x - state.decoy_x) < SNAP_PX and abs(target_y - state.decoy_y) < SNAP_PX:
            state.decoy_x, state.decoy_y = target_x, target_y
    _move(state.decoy, state.decoy_x, state.decoy_y)


def is_alive(state: Cloak) -> bool:
    return bool(user32.IsWindow(state.real) and user32.IsWindow(state.decoy))


def stop(state: Cloak) -> None:
    _disengage(state)
    _restore_system_cursor()  # unconditional, in case engage failed part way
    _destroy(state.real)
    _destroy(state.decoy)
