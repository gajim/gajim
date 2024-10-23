import gi


def require_versions():
    gi.require_versions(
        {
            'Gdk': '4.0',
            'Gio': '2.0',
            'GLib': '2.0',
            'GObject': '2.0',
            'Gst': '1.0',
            'Gtk': '4.0',
            'GtkSource': '5',
            'Pango': '1.0',
            'PangoCairo': '1.0',
        }
    )


require_versions()
