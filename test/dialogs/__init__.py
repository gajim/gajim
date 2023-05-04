import gi


def require_versions():
    gi.require_versions({'Gdk': '3.0',
                         'Gio': '2.0',
                         'GLib': '2.0',
                         'GObject': '2.0',
                         'Gtk': '3.0',
                         'GtkSource': '4',
                         'Pango': '1.0',
                         'PangoCairo': '1.0'})


require_versions()
