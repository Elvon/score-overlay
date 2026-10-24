# SPDX-License-Identifier: GPL-3.0-or-later
"""Prevents a second overlay via a named Windows mutex."""
import ctypes

ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def acquire(name: str) -> int | None:
    """Returns a handle to keep while running, or None if another instance holds it."""
    handle = _kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def release(handle: int) -> None:
    _kernel32.CloseHandle(handle)
