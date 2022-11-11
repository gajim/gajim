from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common.const import CSSPriority


def get_gajim_dir() -> Path:
    gajim_path = Path(__file__) / '..' / '..' / '..' / 'gajim'
    return gajim_path.resolve()


def load_style(filename: str, priority: CSSPriority) -> None:
    path = get_gajim_dir() / 'data' / 'style' / filename
    try:
        with open(str(path), 'r', encoding='utf8') as file:
            css = file.read()
    except Exception as exc:
        print(exc)
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode('utf-8')))
    screen = Gdk.Screen.get_default()
    assert screen is not None
    Gtk.StyleContext.add_provider_for_screen(screen,
                                             provider,
                                             priority)
