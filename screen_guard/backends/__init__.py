import sys

from .base import Backend


def load_backend() -> Backend:
    """Return the best backend for the current platform."""
    if sys.platform.startswith("win"):
        from .windows import WindowsBackend
        return WindowsBackend()
    if sys.platform == "darwin":
        from .macos import MacBackend
        return MacBackend()
    from .linux import LinuxBackend
    return LinuxBackend()
