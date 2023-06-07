# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.


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
                   widgets,
                   domain=DOMAIN,
                   gettext_=_)


def is_shipped_plugin(path: Path) -> bool:
    base = configpaths.get('PLUGINS_BASE')
    if not base.exists():
        return False
    plugin_parent = path.parent
    return base.samefile(plugin_parent)
