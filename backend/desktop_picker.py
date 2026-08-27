"""Small, explicit native dialogs for the local OBus desktop application.

The browser UI never receives unrestricted filesystem access. A native dialog
opens only after an explicit local click and returns one selected directory to
the existing workspace safety boundary.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


def native_workspace_picker_available() -> bool:
    """Whether this local process can show the Windows folder picker."""
    return os.name == "nt" and os.environ.get("OBUS_DISABLE_NATIVE_WORKSPACE_PICKER") != "1"


def native_workspace_picker_status() -> dict[str, object]:
    available = native_workspace_picker_available()
    return {
        "available": available,
        "platform": "windows" if os.name == "nt" else "unsupported",
        "reason": "Ready for an explicit local folder selection." if available else "The native workspace picker is available only in the Windows desktop application.",
    }


def select_local_workspace_directory(*, title: str = "Choose an OBus workspace folder") -> Path | None:
    """Show Windows' folder picker and return an existing directory or ``None``.

    The picker is user-visible. It neither scans nor remembers a path on its
    own, and a cancelled dialog leaves the configured workspace unchanged.
    """
    if not native_workspace_picker_available():
        raise RuntimeError("Native workspace picker is unavailable")

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", ctypes.c_uint),
            ("lpfn", ctypes.c_void_p),
            ("lParam", ctypes.c_ssize_t),
            ("iImage", ctypes.c_int),
        ]

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFOW)]
    shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
    ole32.CoInitialize.argtypes = [ctypes.c_void_p]
    ole32.CoInitialize.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    # BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_EDITBOX. The dialog is
    # native and visible, and only permits actual filesystem directories.
    flags = 0x0001 | 0x0040 | 0x0010
    initialized = ole32.CoInitialize(None)
    should_uninitialize = initialized in (0, 1)
    try:
        display_name = ctypes.create_unicode_buffer(260)
        browse_info = BROWSEINFOW(None, None, display_name, title, flags, None, 0, 0)
        item_id_list = shell32.SHBrowseForFolderW(ctypes.byref(browse_info))
        if not item_id_list:
            return None
        try:
            selected = ctypes.create_unicode_buffer(32_768)
            if not shell32.SHGetPathFromIDListW(item_id_list, selected):
                raise OSError("Windows did not return a filesystem directory")
            path = Path(selected.value).resolve(strict=True)
            if not path.is_dir():
                raise OSError("The selected location is not a directory")
            return path
        finally:
            ole32.CoTaskMemFree(item_id_list)
    finally:
        if should_uninitialize:
            ole32.CoUninitialize()
