# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk

from gajim.gtk.util.misc import get_ui_string


@Gtk.Template.from_string(string=get_ui_string("preview/loading_box.ui"))
class LoadingBox(Gtk.Box):
    __gtype_name__ = "LoadingBox"
