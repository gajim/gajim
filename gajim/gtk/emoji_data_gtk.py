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

from __future__ import annotations

from typing import Any

import logging
from packaging.version import Version as V

from gi.repository import Gio
from gi.repository import GLib

from .util import get_gtk_version

log = logging.getLogger('gajim.gui.emoji_data_gtk')


def get_emoji_data() -> dict[str, str]:
    return emoji_data


def load_emoji_data() -> dict[str, str]:
    # Location of emoji data resource changed in GTK >= 3.24.30
    if V(get_gtk_version()) >= V('3.24.30'):
        emoji_data_resource = '/org/gtk/libgtk/emoji/en.data'
    else:
        emoji_data_resource = '/org/gtk/libgtk/emoji/emoji.data'

    try:
        bytes_ = Gio.resources_lookup_data(
            emoji_data_resource,
            Gio.ResourceLookupFlags.NONE)
        assert bytes_ is not None
        # We have to store bytes_data in a variable to make sure Python
        # keeps it until it is processed.
        bytes_data = bytes_.get_data()

        def _pass(_user_data: Any) -> None:
            pass

        variant = GLib.Variant.new_from_data(
            GLib.VariantType('a(auss)'),
            bytes_data,
            True,
            _pass)

        emoji_data_dict: dict[str, str] = {}
        index = 0
        for _item in variant:
            emoji = variant.get_child_value(index)
            points = emoji.get_child_value(0)
            codepoint = points.get_child_value(0).get_uint32()
            shortcode = emoji.get_child_value(1).get_string()
            emoji_data_dict[shortcode] = chr(codepoint)
            index += 1

        # Add commonly used shortcodes
        emoji_data_dict['+1'] = '\U0001F44D'
        emoji_data_dict['-1'] = '\U0001F44E'
        return emoji_data_dict

    except GLib.Error:
        return {}


emoji_data = load_emoji_data()
