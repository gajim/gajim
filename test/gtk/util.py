from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gtk


def get_gajim_dir():
    gajim_path = Path(__file__) / '..' / '..' / '..' / 'gajim'
    return gajim_path.resolve()

def load_style(filename, priority):
    path = get_gajim_dir() / 'data' / 'style' / filename
    try:
        with open(str(path), 'r', encoding='utf8') as file:
            css = file.read()
    except Exception as exc:
        print(exc)
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode('utf-8')))
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                             provider,
                                             priority)
