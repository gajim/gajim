# Copyright (C) 2018 Marcin Mielniczuk <marmistrz.dev AT zoho.eu>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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
from typing import Optional
from typing import Union

import logging
import math
import textwrap
from io import BytesIO
from importlib import import_module
from functools import wraps
from functools import lru_cache
from pathlib import Path
from re import Match

try:
    from PIL import Image
except Exception:
    pass

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Pango
from gi.repository import GdkPixbuf
import cairo
import nbxmpp
from nbxmpp import JID
from nbxmpp.structs import LocationData
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _
from gajim.common.helpers import URL_REGEX
from gajim.common.const import LOCATION_DATA
from gajim.common.const import Display
from gajim.common.const import StyleAttr
from gajim.common.ged import EventHelper as CommonEventHelper
from gajim.common.styling import PlainBlock
from gajim.common.structs import VariantMixin

from .const import WINDOW_MODULES


log = logging.getLogger('gajim.gui.util')


MenuValueT = Union[None, str, GLib.Variant, VariantMixin]
MenuItemListT = list[tuple[str, str, MenuValueT]]


class NickCompletionGenerator:
    def __init__(self, self_nick: str) -> None:
        self.nick = self_nick
        self.sender_list: list[str] = []
        self.attention_list: list[str] = []

    def change_nick(self, new_nick: str) -> None:
        self.nick = new_nick

    def record_message(self, contact: str, highlight: bool) -> None:
        if contact == self.nick:
            return

        log.debug('Recorded a message from %s, highlight; %s', contact,
                  highlight)
        if highlight:
            try:
                self.attention_list.remove(contact)
            except ValueError:
                pass
            if len(self.attention_list) > 6:
                self.attention_list.pop(0)  # remove older
            self.attention_list.append(contact)

        # TODO implement it in a more efficient way
        # Currently it's O(n*m + n*s), where n is the number of participants and
        # m is the number of messages processed, s - the number of times the
        # suggestions are requested
        #
        # A better way to do it would be to keep a dict: contact -> timestamp
        # with expected O(1) insert, and sort it by timestamps in O(n log n)
        # for each suggestion (currently generating the suggestions is O(n))
        # this would give the expected complexity of O(m + s * n log n)
        try:
            self.sender_list.remove(contact)
        except ValueError:
            pass
        self.sender_list.append(contact)

    def contact_renamed(self, contact_old: str, contact_new: str) -> None:
        log.debug('Contact %s renamed to %s', contact_old, contact_new)
        for lst in (self.attention_list, self.sender_list):
            for idx, contact in enumerate(lst):
                if contact == contact_old:
                    lst[idx] = contact_new

    def generate_suggestions(self, nicks: list[str],
                             beginning: str) -> list[str]:
        """
        Generate the order of suggested MUC autocompletions

        `nicks` is the list of contacts currently participating in a MUC
        `beginning` is the text already typed by the user
        """
        def nick_matching(nick: str) -> bool:
            return nick != self.nick \
                and nick.lower().startswith(beginning.lower())

        if beginning == '':
            # empty message, so just suggest recent mentions
            potential_matches = self.attention_list
        else:
            # nick partially typed, try completing it
            potential_matches = self.sender_list

        potential_matches_set = set(potential_matches)
        log.debug('Priority matches: %s', potential_matches_set)

        matches = [n for n in potential_matches if nick_matching(n)]
        # the most recent nick is the last one on the list
        matches.reverse()

        # handle people who have not posted/mentioned us
        other_nicks = [
            n for n in nicks
            if nick_matching(n) and n not in potential_matches_set
        ]
        other_nicks.sort(key=str.lower)
        log.debug('Other matches: %s', other_nicks)

        return matches + other_nicks


def set_urgency_hint(window: Gtk.Window, setting: bool) -> None:
    if app.settings.get('use_urgency_hint'):
        window.set_urgency_hint(setting)


def icon_exists(name: str) -> bool:
    return Gtk.IconTheme.get_default().has_icon(name)


def load_icon_info(icon_name: str,
                   size: int,
                   scale: Optional[int],
                   flags: Gtk.IconLookupFlags) -> Optional[Gtk.IconInfo]:

    if scale is None:
        scale = app.window.get_scale_factor()

    if not scale:
        log.warning('Could not determine scale factor')
        scale = 1

    icon_theme = Gtk.IconTheme.get_default()

    try:
        iconinfo = icon_theme.lookup_icon_for_scale(
            icon_name, size, scale, flags)
        if iconinfo is None:
            log.info('No icon found for %s', icon_name)
            return None
        return iconinfo
    except GLib.Error as error:
        log.error('Unable to load icon %s: %s', icon_name, str(error))
    return None


def load_icon_surface(
        icon_name: str,
        size: int = 16,
        scale: Optional[int] = None,
        flags: Gtk.IconLookupFlags = Gtk.IconLookupFlags.FORCE_SIZE,
        ) -> Optional[cairo.Surface]:

    icon_info = load_icon_info(icon_name, size, scale, flags)
    if icon_info is None:
        return None
    return icon_info.load_surface(None)


def load_icon_pixbuf(icon_name: str,
                     size: int = 16,
                     scale: Optional[int] = None,
                     flags: Gtk.IconLookupFlags = Gtk.IconLookupFlags.FORCE_SIZE,
                     ) -> Optional[GdkPixbuf.Pixbuf]:

    icon_info = load_icon_info(icon_name, size, scale, flags)
    if icon_info is None:
        return None
    return icon_info.load_icon()


def get_app_icon_list(scale_widget: Gtk.Widget) -> list[GdkPixbuf.Pixbuf]:
    scale = scale_widget.get_scale_factor()
    pixbufs: list[GdkPixbuf.Pixbuf] = []
    for size in (16, 32, 48, 64, 128):
        pixbuf = load_icon_pixbuf('org.gajim.Gajim', size=size, scale=scale)
        if pixbuf is not None:
            pixbufs.append(pixbuf)
    return pixbufs


def get_icon_name(name: str,
                  iconset: Optional[str] = None,
                  transport: Optional[str] = None) -> str:
    if name == 'not in roster':
        name = 'notinroster'

    if iconset is not None:
        return f'{iconset}-{name}'

    if transport is not None:
        return f'{transport}-{name}'

    iconset = app.settings.get('iconset')
    if not iconset:
        iconset = 'dcraven'
    return f'{iconset}-{name}'


def load_user_iconsets() -> None:
    iconsets_path = configpaths.get('MY_ICONSETS')
    if not iconsets_path.exists():
        return

    icon_theme = Gtk.IconTheme.get_default()

    for path in iconsets_path.iterdir():
        if not path.is_dir():
            continue
        log.info('Found iconset: %s', path.stem)
        icon_theme.append_search_path(str(path))


def get_total_screen_geometry() -> tuple[int, int]:
    total_width = 0
    total_height = 0
    display = Gdk.Display.get_default()
    assert display is not None
    monitors = display.get_n_monitors()
    for num in range(0, monitors):
        monitor = display.get_monitor(num)
        assert monitor is not None
        geometry = monitor.get_geometry()
        total_width += geometry.width
        total_height = max(total_height, geometry.height)
    log.debug('Get screen geometry: %s %s', total_width, total_height)
    return total_width, total_height


def resize_window(window: Gtk.Window, width: int, height: int) -> None:
    """
    Resize window, but also checks if huge window or negative values
    """
    screen_w, screen_h = get_total_screen_geometry()
    if not width or not height:
        return

    width = min(width, screen_w)
    height = min(height, screen_h)
    window.resize(abs(width), abs(height))


def move_window(window: Gtk.Window, pos_x: int, pos_y: int) -> None:
    """
    Move the window, but also check if out of screen
    """
    screen_w, screen_h = get_total_screen_geometry()
    pos_x = max(pos_x, 0)
    pos_y = max(pos_y, 0)

    width, height = window.get_size()
    if pos_x + width > screen_w:
        pos_x = screen_w - width
    if pos_y + height > screen_h:
        pos_y = screen_h - height
    window.move(pos_x, pos_y)


def save_main_window_position() -> None:
    if not app.settings.get('save_main_window_position'):
        return
    if app.is_display(Display.WAYLAND):
        return
    x_pos, y_pos = app.window.get_position()
    log.debug('Saving main window position: %s %s', x_pos, y_pos)
    app.settings.set('mainwin_x_position', x_pos)
    app.settings.set('mainwin_y_position', y_pos)


def restore_main_window_position() -> None:
    if not app.settings.get('save_main_window_position'):
        return
    if app.is_display(Display.WAYLAND):
        return
    move_window(app.window,
                app.settings.get('mainwin_x_position'),
                app.settings.get('mainwin_y_position'))


def get_completion_liststore(entry: Gtk.Entry) -> Gtk.ListStore:
    """
    Create a completion model for entry widget completion list consists of
    (Pixbuf, Text) rows
    """
    completion = Gtk.EntryCompletion()
    liststore = Gtk.ListStore(str, str)

    render_pixbuf = Gtk.CellRendererPixbuf()
    completion.pack_start(render_pixbuf, False)
    completion.add_attribute(render_pixbuf, 'icon_name', 0)

    render_text = Gtk.CellRendererText()
    completion.pack_start(render_text, True)
    completion.add_attribute(render_text, 'text', 1)
    completion.set_property('text_column', 1)
    completion.set_model(liststore)
    entry.set_completion(completion)
    return liststore


def get_cursor(name: str) -> Gdk.Cursor:
    display = Gdk.Display.get_default()
    assert display is not None
    cursor = Gdk.Cursor.new_from_name(display, name)
    if cursor is not None:
        return cursor
    return Gdk.Cursor.new_from_name(display, 'default')


def scroll_to_end(widget: Gtk.ScrolledWindow) -> bool:
    """Scrolls to the end of a GtkScrolledWindow.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is False so it can be used with GLib.idle_add.
    """
    adj_v = widget.get_vadjustment()
    if adj_v is None:
        # This can happen when the Widget is already destroyed when called
        # from GLib.idle_add
        return False
    max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    adj_v.set_value(max_scroll_pos)

    adj_h = widget.get_hadjustment()
    adj_h.set_value(0)
    return False


def at_the_end(widget: Gtk.ScrolledWindow) -> bool:
    """Determines if a Scrollbar in a GtkScrolledWindow is at the end.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is True if at the end, False if not.
    """
    adj_v = widget.get_vadjustment()
    max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    return adj_v.get_value() == max_scroll_pos


def get_image_button(icon_name: str, tooltip: str,
                     toggle: bool = False) -> Gtk.Button:
    if toggle:
        button = Gtk.ToggleButton()
        image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        button.set_image(image)
    else:
        button = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    return button


def python_month(month: int) -> int:
    return month + 1


def gtk_month(month: int) -> int:
    return month - 1


def convert_rgba_to_hex(rgba: Gdk.RGBA) -> str:
    red = int(rgba.red * 255)
    green = int(rgba.green * 255)
    blue = int(rgba.blue * 255)
    return '#%02x%02x%02x' % (red, green, blue)


def convert_rgb_to_hex(rgb_string: str) -> str:
    rgba = Gdk.RGBA()
    rgba.parse(rgb_string)
    rgba.to_color()
    return convert_rgba_to_hex(rgba)


@lru_cache(maxsize=1024)
def convert_rgb_string_to_float(rgb_string: str) -> tuple[float, float, float]:
    rgba = Gdk.RGBA()
    rgba.parse(rgb_string)
    return (rgba.red, rgba.green, rgba.blue)


def rgba_to_float(rgba: Gdk.RGBA) -> tuple[float, float, float]:
    return (rgba.red, rgba.green, rgba.blue)


def make_rgba(color_string: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(color_string)
    return rgba


def get_monitor_scale_factor() -> int:
    display = Gdk.Display.get_default()
    assert display is not None
    monitor = display.get_primary_monitor()
    if monitor is None:
        log.warning('Could not determine scale factor')
        return 1
    return monitor.get_scale_factor()


def get_primary_accel_mod() -> Optional[Gdk.ModifierType]:
    """
    Returns the primary Gdk.ModifierType modifier.
    cmd on osx, ctrl everywhere else.
    """
    return Gtk.accelerator_parse("<Primary>")[1]


def get_hardware_key_codes(keyval: int) -> list[int]:
    display = Gdk.Display.get_default()
    assert display is not None
    keymap = Gdk.Keymap.get_for_display(display)

    valid, key_map_keys = keymap.get_entries_for_keyval(keyval)
    if not valid:
        return []
    return [key.keycode for key in key_map_keys]


def ensure_not_destroyed(func: Any) -> Any:
    @wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        if self._destroyed:  # pylint: disable=protected-access
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


def format_tune(data: TuneData) -> str:
    artist = GLib.markup_escape_text(data.artist or _('Unknown Artist'))
    title = GLib.markup_escape_text(data.title or _('Unknown Title'))
    source = GLib.markup_escape_text(data.source or _('Unknown Source'))

    tune_string = _('<b>"%(title)s"</b> by <i>%(artist)s</i>\n'
                    'from <i>%(source)s</i>') % {'title': title,
                                                 'artist': artist,
                                                 'source': source}
    return tune_string


def get_account_tune_icon_name(account: str) -> Optional[str]:
    client = app.get_client(account)
    tune = client.get_module('UserTune').get_current_tune()
    return None if tune is None else 'audio-x-generic'


def format_location(location: LocationData) -> str:
    location_dict = location._asdict()
    location_string = ''
    for attr, value in location_dict.items():
        if value is None:
            continue
        text = GLib.markup_escape_text(value)
        # Translate standard location tag
        tag = LOCATION_DATA.get(attr)
        if tag is None:
            continue
        location_string += '\n<b>%(tag)s</b>: %(text)s' % {
            'tag': tag.capitalize(), 'text': text}

    return location_string.strip()


def get_account_location_icon_name(account: str) -> Optional[str]:
    client = app.get_client(account)
    location = client.get_module('UserLocation').get_current_location()
    return None if location is None else 'applications-internet'


def format_eta(time_: Union[int, float]) -> str:
    times = {'minutes': 0, 'seconds': 0}
    time_ = int(time_)
    times['seconds'] = time_ % 60
    if time_ >= 60:
        time_ = int(time_ / 60)
        times['minutes'] = round(time_ % 60)
        return _('%(minutes)s min %(seconds)s s') % times
    return _('%s s') % times['seconds']


def format_fingerprint(fingerprint: str) -> str:
    fplen = len(fingerprint)
    wordsize = fplen // 8
    buf = ''
    for char in range(0, fplen, wordsize):
        buf += '{0} '.format(fingerprint[char:char + wordsize])
    buf = textwrap.fill(buf, width=36)
    return buf.rstrip().upper()


def find_widget(name: str, container: Gtk.Container) -> Optional[Gtk.Widget]:
    for child in container.get_children():
        if Gtk.Buildable.get_name(child) == name:
            return child
        if isinstance(child, Gtk.Box):
            return find_widget(name, child)
    return None


class MultiLineLabel(Gtk.Label):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.Label.__init__(self, *args, **kwargs)
        self.set_line_wrap(True)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_single_line_mode(False)


class MaxWidthComboBoxText(Gtk.ComboBoxText):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.ComboBoxText.__init__(self, *args, **kwargs)
        self._max_width: int = 100
        text_renderer = self.get_cells()[0]
        text_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)

    def set_max_size(self, size: int) -> None:
        self._max_width = size

    def do_get_preferred_width(self) -> tuple[int, int]:
        minimum_width, natural_width = Gtk.ComboBoxText.do_get_preferred_width(
            self)

        if natural_width > self._max_width:
            natural_width = self._max_width
        if minimum_width > self._max_width:
            minimum_width = self._max_width
        return minimum_width, natural_width


def text_to_color(text: str) -> tuple[float, float, float]:
    if app.css_config.prefer_dark:
        background = (0, 0, 0)  # RGB (0, 0, 0) black
    else:
        background = (1, 1, 1)  # RGB (255, 255, 255) white
    return nbxmpp.util.text_to_color(text, background)  # type: ignore


def get_color_for_account(account: str) -> str:
    col_r, col_g, col_b = text_to_color(account)
    rgba = Gdk.RGBA(red=col_r, green=col_g, blue=col_b)
    return rgba.to_string()


@lru_cache(maxsize=16)
def get_css_show_class(show: str) -> str:
    if show in ('online', 'chat'):
        return '.gajim-status-online'
    if show == 'away':
        return '.gajim-status-away'
    if show in ('dnd', 'xa'):
        return '.gajim-status-dnd'
    if show == 'connecting':
        return '.gajim-status-connecting'
    return '.gajim-status-offline'


def add_css_to_widget(widget: Any, css: str) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode()))
    context = widget.get_style_context()
    context.add_provider(provider,
                         Gtk.STYLE_PROVIDER_PRIORITY_USER)


def get_pixbuf_from_data(file_data: bytes) -> Optional[GdkPixbuf.Pixbuf]:
    # TODO: This already exists in preview_helpery pixbuf_from_data
    """
    Get image data and returns GdkPixbuf.Pixbuf
    """
    pixbufloader = GdkPixbuf.PixbufLoader()
    try:
        pixbufloader.write(file_data)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.Error:
        pixbufloader.close()

        log.warning('loading avatar using pixbufloader failed, trying to '
                    'convert avatar image using pillow')
        try:
            avatar = Image.open(BytesIO(file_data)).convert("RGBA")
            array = GLib.Bytes.new(avatar.tobytes())  # type: ignore
            width, height = avatar.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                array, GdkPixbuf.Colorspace.RGB,
                True, 8, width, height, width * 4)
        except Exception:
            log.warning('Could not use pillow to convert avatar image, '
                        'image cannot be displayed', exc_info=True)
            return None

    return pixbuf


def scale_with_ratio(size: int, width: int, height: int) -> tuple[int, int]:
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size

    ratio = width / float(height)
    return size, int(size / ratio)


def scale_pixbuf(pixbuf: GdkPixbuf.Pixbuf,
                 size: int) -> Optional[GdkPixbuf.Pixbuf]:
    width, height = scale_with_ratio(size,
                                     pixbuf.get_width(),
                                     pixbuf.get_height())
    return pixbuf.scale_simple(width, height,
                               GdkPixbuf.InterpType.BILINEAR)


def scale_pixbuf_from_data(data: bytes,
                           size: int
                           ) -> Optional[GdkPixbuf.Pixbuf]:
    pixbuf = get_pixbuf_from_data(data)
    assert pixbuf is not None
    return scale_pixbuf(pixbuf, size)


def load_pixbuf(path: Union[str, Path],
                size: Optional[int] = None
                ) -> Optional[GdkPixbuf.Pixbuf]:
    try:
        if size is None:
            return GdkPixbuf.Pixbuf.new_from_file(str(path))
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path), size, size, True)

    except GLib.Error:
        try:
            with open(path, 'rb') as im_handle:
                img = Image.open(im_handle)
                avatar = img.convert("RGBA")
        except (NameError, OSError):
            log.warning('Pillow convert failed: %s', path)
            log.debug('Error', exc_info=True)
            return None

        array = GLib.Bytes.new(avatar.tobytes())  # type: ignore
        width, height = avatar.size
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            array, GdkPixbuf.Colorspace.RGB, True,
            8, width, height, width * 4)
        if size is not None:
            width, height = scale_with_ratio(size, width, height)
            return pixbuf.scale_simple(width,
                                       height,
                                       GdkPixbuf.InterpType.BILINEAR)
        return pixbuf

    except RuntimeError as error:
        log.warning('Loading pixbuf failed: %s', error)
        return None


def get_thumbnail_size(pixbuf: GdkPixbuf.Pixbuf, size: int) -> tuple[int, int]:
    # Calculates the new thumbnail size while preserving the aspect ratio
    image_width = pixbuf.get_width()
    image_height = pixbuf.get_height()

    if image_width > image_height:
        if image_width > size:
            image_height = math.ceil(
                (size / float(image_width) * image_height))
            image_width = int(size)
    else:
        if image_height > size:
            image_width = math.ceil(
                (size / float(image_height) * image_width))
            image_height = int(size)

    return image_width, image_height


def make_href_markup(string: str) -> str:
    url_color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
    assert isinstance(url_color, str)
    color = convert_rgb_to_hex(url_color)

    def _to_href(match: Match[str]) -> str:
        url = match.group()
        if '://' not in url:
            url = 'https://' + url
        return '<a href="%s"><span foreground="%s">%s</span></a>' % (
            url, color, match.group())

    return URL_REGEX.sub(_to_href, string)


def get_app_windows(account: str) -> list[Gtk.Window]:
    windows: list[Gtk.Window] = []
    for win in app.app.get_windows():
        if hasattr(win, 'account'):
            if win.account == account:  # type: ignore
                windows.append(win)
    return windows


def get_app_window(name: str,
                   account: Optional[str] = None,
                   jid: Optional[Union[str, JID]] = None
                   ) -> Optional[Gtk.Window]:
    for win in app.app.get_windows():
        if type(win).__name__ != name:
            continue

        if account is not None:
            if account != win.account:  # type: ignore
                continue

        if jid is not None:
            if jid != win.jid:  # type: ignore
                continue
        return win
    return None


def open_window(name: str, **kwargs: Any) -> Any:
    window = get_app_window(name,
                            kwargs.get('account'),
                            kwargs.get('jid'))
    if window is None:
        module = import_module(WINDOW_MODULES[name])
        window_cls = getattr(module, name)
        window = window_cls(**kwargs)
    else:
        window.present()
    return window


class EventHelper(CommonEventHelper):
    def __init__(self):
        CommonEventHelper.__init__(self)
        self.connect('destroy', self.__on_destroy)  # type: ignore

    def __on_destroy(self, *args: Any) -> None:
        self.unregister_events()


def check_destroy(widget: Gtk.Widget) -> None:
    def _destroy(*args: Any) -> None:
        print('DESTROYED', args)
    widget.connect('destroy', _destroy)


def _connect_destroy(sender: Any,
                     func: Any,
                     detailed_signal: str,
                     handler: Any,
                     *args: Any,
                     **kwargs: Any) -> int:
    """Connect a bound method to a foreign object signal and disconnect
    if the object the method is bound to emits destroy (Gtk.Widget subclass).
    Also works if the handler is a nested function in a method and
    references the method's bound object.
    This solves the problem that the sender holds a strong reference
    to the bound method and the bound to object doesn't get GCed.
    """

    if hasattr(handler, "__self__"):
        obj = handler.__self__
    else:
        # XXX: get the "self" var of the enclosing scope.
        # Used for nested functions which ref the object but aren't methods.
        # In case they don't ref "self" normal connect() should be used anyway.
        index = handler.__code__.co_freevars.index("self")
        obj = handler.__closure__[index].cell_contents

    assert obj is not sender

    handler_id = func(detailed_signal, handler, *args, **kwargs)

    def disconnect_cb(*args: Any) -> None:
        sender.disconnect(handler_id)

    obj.connect('destroy', disconnect_cb)
    return handler_id


def connect_destroy(sender: Any, *args: Any, **kwargs: Any) -> int:
    return _connect_destroy(sender, sender.connect, *args, **kwargs)


def wrap_with_event_box(klass: Any) -> Any:
    @wraps(klass)
    def klass_wrapper(*args: Any, **kwargs: Any) -> Gtk.EventBox:
        widget = klass(*args, **kwargs)
        event_box = Gtk.EventBox()

        def _on_realize(*args: Any) -> None:
            window = event_box.get_window()
            assert window is not None
            window.set_cursor(get_cursor('pointer'))

        event_box.connect_after('realize', _on_realize)
        event_box.add(widget)
        return event_box
    return klass_wrapper


class AccountBadge(Gtk.Label):
    def __init__(self, account: str) -> None:
        Gtk.Label.__init__(self)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(12)
        self.set_size_request(50, -1)
        self.get_style_context().add_class('badge')
        self._account = account

        self.refresh()
        self.show()

    def refresh(self) -> None:
        label = app.get_account_label(self._account)
        self.set_text(label)
        account_class = app.css_config.get_dynamic_class(self._account)
        self.get_style_context().add_class(account_class)
        self.set_tooltip_text(_('Account: %s') % label)


def make_pango_attributes(block: PlainBlock) -> Pango.AttrList:
    attrlist = Pango.AttrList()
    for span in block.spans:
        attr = get_style_attribute_with_name(span.name)
        attr.start_index = span.start_byte
        attr.end_index = span.end_byte
        attrlist.insert(attr)
    return attrlist


def get_style_attribute_with_name(name: str) -> Pango.Attribute:
    if name == 'strong':
        return Pango.attr_weight_new(Pango.Weight.BOLD)

    if name == 'strike':
        return Pango.attr_strikethrough_new(True)

    if name == 'emphasis':
        return Pango.attr_style_new(Pango.Style.ITALIC)

    if name == 'pre':
        return Pango.attr_family_new('monospace')

    raise ValueError('unknown attribute %s' % name)


def get_key_theme() -> Optional[str]:
    settings = Gtk.Settings.get_default()
    if settings is None:
        return None
    return settings.get_property('gtk-key-theme-name')


def make_menu_item(label: str,
                   action: Optional[str] = None,
                   value: MenuValueT = None) -> Gio.MenuItem:

    if value is None:
        return Gio.MenuItem.new(label, action)

    item = Gio.MenuItem.new(label)
    if isinstance(value, str):
        item.set_detailed_action(f'{action}({value})')
    elif isinstance(value, VariantMixin):
        item.set_action_and_target_value(action, value.to_variant())
    else:
        item.set_action_and_target_value(action, value)
    return item


def make_menu(menuitems: MenuItemListT) -> Gio.Menu:
    menu = Gio.Menu()
    for item in menuitems:
        menuitem = make_menu_item(*item)
        menu.append_item(menuitem)
    return menu


class GajimMenu(Gio.Menu):
    def __init__(self):
        Gio.Menu.__init__(self)

    @classmethod
    def from_list(cls, menulist: MenuItemListT) -> GajimMenu:
        menu = cls()
        for item in menulist:
            menuitem = make_menu_item(*item)
            menu.append_item(menuitem)
        return menu

    def add_item(self, label: str, action: str, value: MenuValueT) -> None:
        item = make_menu_item(label, action, value)
        self.append_item(item)

    def add_submenu(self, label: str) -> GajimMenu:
        menu = GajimMenu()
        self.append_submenu(label, menu)
        return menu
