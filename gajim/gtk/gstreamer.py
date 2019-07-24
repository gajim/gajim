from typing import Tuple, Optional

from gi.repository import Gst
from gi.repository import Gtk

def create_gtk_widget() -> Tuple[Optional[Gst.Element], Optional[Gtk.Widget], Optional[str]]:
    gtkglsink = Gst.ElementFactory.make('gtkglsink', None)
    if gtkglsink is not None:
        glsinkbin = Gst.ElementFactory.make('glsinkbin', None)
        if glsinkbin is None:
            return None, None, None
        glsinkbin.set_property('sink', gtkglsink)
        sink = glsinkbin
        widget = gtkglsink.get_property('widget')
        name = 'gtkglsink'
    else:
        sink = Gst.ElementFactory.make('gtksink', None)
        if sink is None:
            return None, None, None
        widget = sink.get_property('widget')
        name = 'gtksink'
    widget.set_visible(True)
    widget.set_property('expand', True)
    return sink, widget, name
