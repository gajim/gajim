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

from typing import Optional

from gi.repository import Gtk

try:
    from gi.repository import Gst
except Exception:
    pass


def create_gtk_widget() -> Optional[tuple[Gst.Element,
                                          Gtk.Widget,
                                          str]]:
    gtkglsink = Gst.ElementFactory.make('gtkglsink', None)
    if gtkglsink is not None:
        glsinkbin = Gst.ElementFactory.make('glsinkbin', None)
        if glsinkbin is None:
            return None
        glsinkbin.set_property('sink', gtkglsink)
        sink = glsinkbin
        widget = gtkglsink.get_property('widget')
        name = 'gtkglsink'
    else:
        sink = Gst.ElementFactory.make('gtksink', None)
        if sink is None:
            return None
        widget = sink.get_property('widget')
        name = 'gtksink'
    widget.set_visible(True)
    widget.set_property('expand', True)
    return sink, widget, name
