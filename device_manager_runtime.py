"""Resolve the visible portable executable, never trust a bare environment path."""

from functools import lru_cache
import os
from pathlib import Path
import sys


def _parent_image(pid):
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError("Cannot verify the portable launcher.")
    parent = None
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32ProcessID == pid:
                parent = entry.th32ParentProcessID
                break
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    if parent is None:
        raise OSError("The application process was not found.")
    handle = kernel.OpenProcess(0x1000, False, parent)
    if not handle:
        raise OSError("Cannot inspect the portable launcher.")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            raise OSError("Cannot resolve the portable launcher.")
        return parent, Path(buffer.value).resolve()
    finally:
        kernel.CloseHandle(handle)


@lru_cache(maxsize=4)
def _verified_launcher(path, parent_pid, current_pid, core_path):
    launcher = Path(path).resolve(strict=True)
    parent, parent_image = _parent_image(current_pid)
    if (launcher.suffix.lower() != ".exe" or parent != int(parent_pid)
            or parent_image != launcher or launcher == Path(core_path).resolve()):
        raise OSError("Invalid portable launcher context.")
    return launcher, parent


def application_context():
    path = os.environ.get("DEVICE_MANAGER_PORTABLE_EXE", "")
    parent = os.environ.get("DEVICE_MANAGER_PORTABLE_PID", "")
    if getattr(sys, "frozen", False) and path and parent:
        if os.name != "nt":
            raise OSError("The portable launcher is only supported on Windows.")
        return _verified_launcher(path, parent, os.getpid(), sys.executable)
    return Path(sys.executable).resolve(), os.getpid()


def application_executable():
    return application_context()[0]
