# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast

import importlib.resources
import sys
from pathlib import Path

from .config import *  # noqa: F403

__version__ = "2.6.0"


def _is_portable() -> bool:
    if sys.platform == "win32":
        return False
    basedir = cast(Path, importlib.resources.files("gajim"))
    portable_path = basedir / "data" / "is_portable"
    return portable_path.exists()


def _is_ms_store() -> bool:
    # Check for Microsoft app identity by trying to query AppInfo.
    # If there is no AppInfo, it's no MS Store install.
    try:
        from winrt.windows.applicationmodel import AppInfo

        return AppInfo.current is not None
    except Exception:
        pass

    return False


IS_PORTABLE = _is_portable()
IS_MS_STORE = _is_ms_store()
