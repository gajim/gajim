# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast

import functools
import importlib.metadata
import os
import platform
import sys

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Soup
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

CURRENT_PYTHON_VERSION = platform.python_version()


def python_version(specifier_set: str) -> bool:
    spec = SpecifierSet(specifier_set)
    return CURRENT_PYTHON_VERSION in spec


def package_version(requirement: str) -> bool:
    req = Requirement(requirement)

    try:
        installed_version = importlib.metadata.version(req.name)
    except importlib.metadata.PackageNotFoundError:
        return False

    return installed_version in req.specifier


@functools.lru_cache(maxsize=1)
def get_os_info() -> str:
    info = "N/A"
    if sys.platform in ("win32", "darwin"):
        info = f"{platform.system()} {platform.release()}"

    elif sys.platform == "linux":
        try:
            import distro  # type: ignore

            info = cast(str, distro.name(pretty=True))  # type: ignore
        except ImportError:
            info = platform.system()
    return info


def get_os_name() -> str:
    if sys.platform in ("win32", "darwin"):
        return platform.system()
    if os.name == "posix":
        try:
            import distro  # type: ignore

            return distro.name(pretty=True)  # type: ignore
        except ImportError:
            return platform.system()
    return ""


def get_os_version() -> str:
    if sys.platform in ("win32", "darwin"):
        return platform.version()
    if os.name == "posix":
        try:
            import distro  # type: ignore

            return distro.version(pretty=True)  # type: ignore
        except ImportError:
            return platform.release()
    return ""


def get_gobject_version() -> str:
    return ".".join(map(str, GObject.pygobject_version))


def get_glib_version() -> str:
    return ".".join(
        map(str, [GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION])
    )


def get_soup_version() -> str:
    return ".".join(
        map(
            str,
            [
                Soup.get_major_version(),
                Soup.get_minor_version(),
                Soup.get_micro_version(),
            ],
        )
    )
