# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import functools
import sys
import xml.etree.ElementTree as ET

from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import configpaths
from gajim.common import i18n
from gajim.common.i18n import _


class Builder:

    filename = ''

    def __init__(self,
                 filename: str | None = None,
                 widgets: list[str] | None = None,
                 domain: str | None = None,
                 gettext_: Any | None = None) -> None:

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
    @functools.cache
    def _load_string_from_filename(filename: str, gettext_: Any) -> str:
        file_path = str(configpaths.get('GUI') / filename)

        if sys.platform == 'win32':
            # This is a workaround for non working translation on Windows
            tree = ET.parse(file_path)
            for node in tree.findall(".//*[@translatable='yes']"):
                node.text = gettext_(node.text) if node.text else ''
                del node.attrib['translatable']

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


def get_builder(file_name: str, widgets: list[str] | None = None) -> Builder:
    return Builder(file_name, widgets)
