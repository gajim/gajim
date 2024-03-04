# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from pathlib import Path

from gajim.common import configpaths

from gajim.gtk.builder import Builder

from .plugins_i18n import _
from .plugins_i18n import DOMAIN


class GajimPluginActivateException(Exception):
    '''
    Raised when activation failed
    '''


def get_builder(file_name: str, widgets: list[str] | None = None) -> Builder:
    return Builder(file_name,
                   widgets,  # pyright: ignore
                   domain=DOMAIN,
                   gettext_=_)


def is_shipped_plugin(path: Path) -> bool:
    base = configpaths.get('PLUGINS_BASE')
    if not base.exists():
        return False
    plugin_parent = path.parent
    return base.samefile(plugin_parent)
