# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys

import gajim


def get_extended_app_version() -> str:
    if gajim.IS_FLATPAK:
        package = "Flatpak"
    if gajim.IS_FLATPAK_NIGHTLY:
        package = "Flatpak Nightly"
    elif gajim.IS_PORTABLE:
        package = "Windows Portable"
    elif gajim.IS_MS_STORE:
        package = "Windows Store"
    elif sys.platform == "win32":
        package = "Windows"
    elif sys.platform == "darwin":
        package = "MacOS"
    else:
        package = "Unix/Linux"

    return f"{gajim.__version__} ({package})"
