"""Windows package identity helpers.

Microsoft Store builds run with MSIX package identity. The distinction is
important because Windows owns installation and updates for those builds,
while the traditional Inno Setup build remains self-managed.
"""

from __future__ import annotations

import ctypes
import os
import sys
from functools import lru_cache
from typing import Optional


_APPMODEL_ERROR_NO_PACKAGE = 15700
_ERROR_INSUFFICIENT_BUFFER = 122


def _query_current_package_full_name() -> Optional[str]:
    """Return the package full name from the Windows package identity API."""
    length = ctypes.c_uint32(0)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_name = kernel32.GetCurrentPackageFullName
    get_name.argtypes = [
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_wchar_p,
    ]
    get_name.restype = ctypes.c_long

    result = get_name(ctypes.byref(length), None)
    if result == _APPMODEL_ERROR_NO_PACKAGE:
        return None
    if result not in (0, _ERROR_INSUFFICIENT_BUFFER) or length.value == 0:
        return None

    buffer = ctypes.create_unicode_buffer(length.value)
    result = get_name(ctypes.byref(length), buffer)
    if result != 0:
        return None
    value = buffer.value.strip()
    return value or None


@lru_cache(maxsize=1)
def get_package_full_name() -> Optional[str]:
    """Return the current MSIX package full name, if one is present."""
    # The override is intentionally development-only. A packaged executable
    # must always trust Windows' package identity API so an inherited
    # environment variable cannot disable signature or update enforcement.
    if not getattr(sys, "frozen", False):
        forced = os.getenv("SSMAKER_MSIX_PACKAGE", "").strip().lower()
        if forced in {"1", "true", "yes", "on"}:
            return "SSMaker.TestPackage"
        if forced in {"0", "false", "no", "off"}:
            return None
    if sys.platform != "win32":
        return None

    try:
        return _query_current_package_full_name()
    except (AttributeError, OSError):
        return None


def is_msix_package() -> bool:
    """Return ``True`` when the process is running with MSIX identity."""
    return bool(get_package_full_name())


def reset_package_identity_cache() -> None:
    """Clear cached identity state (primarily useful for tests)."""
    get_package_full_name.cache_clear()
