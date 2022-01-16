# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import Optional

import sys
import functools
import xml.etree.ElementTree as ET

from gi.repository import Gtk
from gi.repository import Gio

from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common import configpaths


class Builder:

    filename = ''

    def __init__(self,
                 filename: Optional[str] = None,
                 widgets: Optional[list[str]] = None,
                 domain: Optional[str] = None,
                 gettext_: Optional[Any] = None) -> None:

        if filename is None:
            filename = self.filename

        self._builder = Gtk.Builder()

        if domain is None:
            domain = i18n.DOMAIN
        self._builder.set_translation_domain(domain)

        if gettext_ is None:
            gettext_ = _

        xml_text = self._load_string_from_filename(filename, gettext_)

        if widgets is not None:
            self._builder.add_objects_from_string(xml_text, widgets)
        else:
            self._builder.add_from_string(xml_text)

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _load_string_from_filename(filename: str, gettext_: Any) -> str:
        file_path = str(configpaths.get('GUI') / filename)

        if sys.platform == "win32":
            # This is a workaround for non working translation on Windows
            tree = ET.parse(file_path)
            for node in tree.iter():
                if 'translatable' in node.attrib and node.text is not None:
                    node.text = gettext_(node.text)

            return ET.tostring(tree.getroot(),
                               encoding='unicode',
                               method='xml')

        file = Gio.File.new_for_path(file_path)
        content = file.load_contents(None)
        return content[1].decode()

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self._builder, name)
        except AttributeError:
            return self._builder.get_object(name)

    def get(self, name: str) -> Any:
        return self._builder.get_object(name)


def get_builder(file_name: str, widgets: Optional[list[str]] = None) -> Builder:
    return Builder(file_name, widgets)
