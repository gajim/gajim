# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.gtk.util.misc import get_ui_string


@Gtk.Template.from_string(string=get_ui_string("preference/placeholder_box.ui"))
class PlaceholderBox(Gtk.Box):
    __gtype_name__ = "PlaceholderBox"


@Gtk.Template.from_string(string=get_ui_string("preference/copy_button.ui"))
class CopyButton(Gtk.Button):
    __gtype_name__ = "CopyButton"
