import gi

from gajim.common import configpaths

configpaths.init()


def require_versions():
    gi.require_versions(
        {
            'Gdk': '4.0',
            'GLib': '2.0',
            'Gio': '2.0',
            'Gtk': '4.0',
            'GtkSource': '5',
            'GObject': '2.0',
            'Pango': '1.0',
        }
    )


require_versions()
