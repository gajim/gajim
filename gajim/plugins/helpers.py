# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from pathlib import Path

from gajim.common import configpaths

from gajim.gtk.builder import GajimBuilder

from .plugins_i18n import _
from .plugins_i18n import DOMAIN


class GajimPluginActivateException(Exception):
    """
    Raised when activation failed
    """


def get_builder(
    file_name: str, instance: Any = None, widgets: list[str] | None = None
) -> GajimBuilder:
    return GajimBuilder(file_name, instance, widgets, domain=DOMAIN, gettext_=_)


def is_shipped_plugin(path: Path) -> bool:
    base = configpaths.get("PLUGINS_BASE")
    if not base.exists():
        return False
    plugin_parent = path.parent
    return base.samefile(plugin_parent)
