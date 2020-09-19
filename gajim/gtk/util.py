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

from typing import Any
from typing import List
from typing import Tuple
from typing import Optional

import sys
import weakref
import logging
import math
import textwrap
import functools
from importlib import import_module
import xml.etree.ElementTree as ET
from pathlib import Path
from functools import wraps
from functools import lru_cache

try:
    from PIL import Image
except Exception:
    pass

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Pango
from gi.repository import GdkPixbuf
import nbxmpp
import cairo

from gajim.common import app
from gajim.common import configpaths
from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common.helpers import URL_REGEX
from gajim.common.const import MOODS
from gajim.common.const import ACTIVITIES
from gajim.common.const import LOCATION_DATA
from gajim.common.const import Display
from gajim.common.const import StyleAttr
from gajim.common.nec import EventHelper as CommonEventHelper

from gajim.gtk.const import GajimIconSet
from gajim.gtk.const import WINDOW_MODULES

_icon_theme = Gtk.IconTheme.get_default()
if _icon_theme is not None:
    _icon_theme.append_search_path(str(configpaths.get('ICONS')))

log = logging.getLogger('gajim.gtk.util')


class NickCompletionGenerator:
    def __init__(self, self_nick: str) -> None:
        self.nick = self_nick
        self.sender_list = []  # type: List[str]
        self.attention_list = []  # type: List[str]

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


    def generate_suggestions(self, nicks: List[str],
                             beginning: str) -> List[str]:
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


class Builder:
    def __init__(self,
                 filename: str,
                 widgets: List[str] = None,
                 domain: str = None,
                 gettext_: Any = None) -> None:
        self._builder = Gtk.Builder()

        if domain is None:
            domain = i18n.DOMAIN
        self._builder.set_translation_domain(domain)

        if gettext_ is None:
            gettext_ = _

        xml_text = self._load_string_from_filename(filename, gettext_)

        if widgets is not None:
            self._builder.add_objects_from_string(xml_text, widgets)
        else:
            self._builder.add_from_string(xml_text)

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _load_string_from_filename(filename, gettext_):
        file_path = str(Path(configpaths.get('GUI')) / filename)

        if sys.platform == "win32":
            # This is a workaround for non working translation on Windows
            tree = ET.parse(file_path)
            for node in tree.iter():
                if 'translatable' in node.attrib and node.text is not None:
                    node.text = gettext_(node.text)

            return ET.tostring(tree.getroot(),
                               encoding='unicode',
                               method='xml')


        file = Gio.File.new_for_path(file_path)
        content = file.load_contents(None)
        return content[1].decode()

    def __getattr__(self, name):
        try:
            return getattr(self._builder, name)
        except AttributeError:
            return self._builder.get_object(name)


def get_builder(file_name: str, widgets: List[str] = None) -> Builder:
    return Builder(file_name, widgets)


def set_urgency_hint(window: Any, setting: bool) -> None:
    if app.settings.get('use_urgency_hint'):
        window.set_urgency_hint(setting)


def icon_exists(name: str) -> bool:
    return _icon_theme.has_icon(name)


def load_icon(icon_name, widget=None, size=16, pixbuf=False,
              scale=None, flags=Gtk.IconLookupFlags.FORCE_SIZE):

    if widget is not None:
        scale = widget.get_scale_factor()

    if not scale:
        log.warning('Could not determine scale factor')
        scale = 1

    try:
        iconinfo = _icon_theme.lookup_icon_for_scale(
            icon_name, size, scale, flags)
        if iconinfo is None:
            log.info('No icon found for %s', icon_name)
            return
        if pixbuf:
            return iconinfo.load_icon()
        return iconinfo.load_surface(None)
    except GLib.GError as error:
        log.error('Unable to load icon %s: %s', icon_name, str(error))


def get_app_icon_list(scale_widget):
    pixbufs = []
    for size in (16, 32, 48, 64, 128):
        pixbuf = load_icon('org.gajim.Gajim', scale_widget, size, pixbuf=True)
        if pixbuf is not None:
            pixbufs.append(pixbuf)
    return pixbufs


def get_icon_name(name: str,
                  iconset: Optional[str] = None,
                  transport: Optional[str] = None) -> str:
    if name == 'not in roster':
        name = 'notinroster'

    if iconset is not None:
        return '%s-%s' % (iconset, name)

    if transport is not None:
        return '%s-%s' % (transport, name)

    iconset = app.settings.get('iconset')
    if not iconset:
        iconset = 'dcraven'
    return '%s-%s' % (iconset, name)


def load_user_iconsets():
    iconsets_path = Path(configpaths.get('MY_ICONSETS'))
    if not iconsets_path.exists():
        return

    for path in iconsets_path.iterdir():
        if not path.is_dir():
            continue
        log.info('Found iconset: %s', path.stem)
        _icon_theme.append_search_path(str(path))


def get_available_iconsets():
    iconsets = []
    for iconset in GajimIconSet:
        iconsets.append(iconset.value)

    iconsets_path = Path(configpaths.get('MY_ICONSETS'))
    if not iconsets_path.exists():
        return iconsets

    for path in iconsets_path.iterdir():
        if not path.is_dir():
            continue
        iconsets.append(path.stem)
    return iconsets


def get_total_screen_geometry() -> Tuple[int, int]:
    total_width = 0
    total_height = 0
    display = Gdk.Display.get_default()
    monitors = display.get_n_monitors()
    for num in range(0, monitors):
        monitor = display.get_monitor(num)
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
    if width > screen_w:
        width = screen_w
    if height > screen_h:
        height = screen_h
    window.resize(abs(width), abs(height))


def move_window(window: Gtk.Window, pos_x: int, pos_y: int) -> None:
    """
    Move the window, but also check if out of screen
    """
    screen_w, screen_h = get_total_screen_geometry()
    if pos_x < 0:
        pos_x = 0
    if pos_y < 0:
        pos_y = 0
    width, height = window.get_size()
    if pos_x + width > screen_w:
        pos_x = screen_w - width
    if pos_y + height > screen_h:
        pos_y = screen_h - height
    window.move(pos_x, pos_y)


def restore_roster_position(window):
    if not app.settings.get('save-roster-position'):
        return
    if app.is_display(Display.WAYLAND):
        return
    move_window(window,
                app.settings.get('roster_x-position'),
                app.settings.get('roster_y-position'))


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


def get_image_button(icon_name, tooltip, toggle=False):
    if toggle:
        button = Gtk.ToggleButton()
        image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        button.set_image(image)
    else:
        button = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    return button


def get_image_from_icon_name(icon_name: str, scale: int) -> Any:
    icon = get_icon_name(icon_name)
    surface = _icon_theme.load_surface(icon, 16, scale, None, 0)
    return Gtk.Image.new_from_surface(surface)


def python_month(month: int) -> int:
    return month + 1


def gtk_month(month: int) -> int:
    return month - 1


def convert_rgb_to_hex(rgb_string: str) -> str:
    rgb = Gdk.RGBA()
    rgb.parse(rgb_string)
    rgb.to_color()

    red = int(rgb.red * 255)
    green = int(rgb.green * 255)
    blue = int(rgb.blue * 255)
    return '#%02x%02x%02x' % (red, green, blue)


@lru_cache(maxsize=1024)
def convert_rgb_string_to_float(rgb_string: str) -> Tuple[float, float, float]:
    rgba = Gdk.RGBA()
    rgba.parse(rgb_string)
    return (rgba.red, rgba.green, rgba.blue)


def get_monitor_scale_factor() -> int:
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor()
    if monitor is None:
        log.warning('Could not determine scale factor')
        return 1
    return monitor.get_scale_factor()


def get_metacontact_surface(icon_name, expanded, scale):
    icon_size = 16
    state_surface = _icon_theme.load_surface(
        icon_name, icon_size, scale, None, 0)
    if 'event' in icon_name:
        return state_surface

    if expanded:
        icon = get_icon_name('opened')
        expanded_surface = _icon_theme.load_surface(
            icon, icon_size, scale, None, 0)
    else:
        icon = get_icon_name('closed')
        expanded_surface = _icon_theme.load_surface(
            icon, icon_size, scale, None, 0)
    ctx = cairo.Context(state_surface)
    ctx.rectangle(0, 0, icon_size, icon_size)
    ctx.set_source_surface(expanded_surface)
    ctx.fill()
    return state_surface


def get_show_in_roster(event, session=None):
    """
    Return True if this event must be shown in roster, else False
    """
    if event == 'gc_message_received':
        return True
    if event == 'message_received':
        if session and session.control:
            return False
    return True


def get_show_in_systray(type_, account, jid):
    """
    Return True if this event must be shown in systray, else False
    """
    if type_ == 'printed_gc_msg':
        contact = app.contacts.get_groupchat_contact(account, jid)
        if contact is not None:
            return contact.can_notify()
        # it's not an highlighted message, don't show in systray
        return False
    return app.settings.get('trayicon_notification_on_events')


def get_primary_accel_mod():
    """
    Returns the primary Gdk.ModifierType modifier.
    cmd on osx, ctrl everywhere else.
    """
    return Gtk.accelerator_parse("<Primary>")[1]


def get_hardware_key_codes(keyval):
    keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())

    valid, key_map_keys = keymap.get_entries_for_keyval(keyval)
    if not valid:
        return []
    return [key.keycode for key in key_map_keys]


def ensure_not_destroyed(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if self._destroyed:  # pylint: disable=protected-access
            return None
        return func(self, *args, **kwargs)
    return func_wrapper


def format_mood(mood, text):
    if mood is None:
        return ''
    mood = MOODS[mood]
    markuptext = '<b>%s</b>' % GLib.markup_escape_text(mood)
    if text is not None:
        markuptext += ' (%s)' % GLib.markup_escape_text(text)
    return markuptext


def get_account_mood_icon_name(account):
    client = app.get_client(account)
    mood = client.get_module('UserMood').get_current_mood()
    return f'mood-{mood.mood}' if mood is not None else mood


def format_activity(activity, subactivity, text):
    if activity is None:
        return None

    if subactivity in ACTIVITIES[activity]:
        subactivity = ACTIVITIES[activity][subactivity]
    activity = ACTIVITIES[activity]['category']

    markuptext = '<b>' + GLib.markup_escape_text(activity)
    if subactivity:
        markuptext += ': ' + GLib.markup_escape_text(subactivity)
    markuptext += '</b>'
    if text:
        markuptext += ' (%s)' % GLib.markup_escape_text(text)
    return markuptext


def get_activity_icon_name(activity, subactivity=None):
    icon_name = 'activity-%s' % activity.replace('_', '-')
    if subactivity is not None:
        icon_name += '-%s' % subactivity.replace('_', '-')
    return icon_name


def get_account_activity_icon_name(account):
    client = app.get_client(account)
    activity = client.get_module('UserActivity').get_current_activity()
    if activity is None:
        return None
    return get_activity_icon_name(activity.activity, activity.subactivity)


def format_tune(artist, _length, _rating, source, title, _track, _uri):
    if artist is None and title is None and source is None:
        return None
    artist = GLib.markup_escape_text(artist or _('Unknown Artist'))
    title = GLib.markup_escape_text(title or _('Unknown Title'))
    source = GLib.markup_escape_text(source or _('Unknown Source'))

    tune_string = _('<b>"%(title)s"</b> by <i>%(artist)s</i>\n'
                    'from <i>%(source)s</i>') % {'title': title,
                                                 'artist': artist,
                                                 'source': source}
    return tune_string


def get_account_tune_icon_name(account):
    client = app.get_client(account)
    tune = client.get_module('UserTune').get_current_tune()
    return None if tune is None else 'audio-x-generic'


def format_location(location):
    location = location._asdict()
    location_string = ''
    for attr, value in location.items():
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


def get_account_location_icon_name(account):
    client = app.get_client(account)
    location = client.get_module('UserLocation').get_current_location()
    return None if location is None else 'applications-internet'


def format_fingerprint(fingerprint):
    fplen = len(fingerprint)
    wordsize = fplen // 8
    buf = ''
    for char in range(0, fplen, wordsize):
        buf += '{0} '.format(fingerprint[char:char + wordsize])
    buf = textwrap.fill(buf, width=36)
    return buf.rstrip().upper()


def find_widget(name, container):
    for child in container.get_children():
        if Gtk.Buildable.get_name(child) == name:
            return child
        if isinstance(child, Gtk.Box):
            return find_widget(name, child)
    return None


class MultiLineLabel(Gtk.Label):
    def __init__(self, *args, **kwargs):
        Gtk.Label.__init__(self, *args, **kwargs)
        self.set_line_wrap(True)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_single_line_mode(False)


class MaxWidthComboBoxText(Gtk.ComboBoxText):
    def __init__(self, *args, **kwargs):
        Gtk.ComboBoxText.__init__(self, *args, **kwargs)
        self._max_width = 100
        text_renderer = self.get_cells()[0]
        text_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)

    def set_max_size(self, size):
        self._max_width = size

    def do_get_preferred_width(self):
        minimum_width, natural_width = Gtk.ComboBoxText.do_get_preferred_width(
            self)

        if natural_width > self._max_width:
            natural_width = self._max_width
        if minimum_width > self._max_width:
            minimum_width = self._max_width
        return minimum_width, natural_width


def text_to_color(text):
    if app.css_config.prefer_dark:
        background = (0, 0, 0)  # RGB (0, 0, 0) black
    else:
        background = (1, 1, 1)  # RGB (255, 255, 255) white
    return nbxmpp.util.text_to_color(text, background)


def get_color_for_account(account: str) -> str:
    col_r, col_g, col_b = text_to_color(account)
    rgba = Gdk.RGBA(red=col_r, green=col_g, blue=col_b)
    return rgba.to_string()


def generate_account_badge(account):
    account_label = app.get_account_label(account)
    badge = Gtk.Label(label=account_label)
    badge.set_ellipsize(Pango.EllipsizeMode.END)
    badge.set_max_width_chars(12)
    badge.set_size_request(50, -1)
    account_class = app.css_config.get_dynamic_class(account)
    badge_context = badge.get_style_context()
    badge_context.add_class(account_class)
    badge_context.add_class('badge')
    return badge


@lru_cache(maxsize=16)
def get_css_show_class(show):
    if show in ('online', 'chat'):
        return '.gajim-status-online'
    if show == 'away':
        return '.gajim-status-away'
    if show in ('dnd', 'xa'):
        return '.gajim-status-dnd'
    # 'offline', 'not in roster', 'requested'
    return '.gajim-status-offline'


def scale_with_ratio(size, width, height):
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size

    ratio = width / float(height)
    return size, int(size / ratio)


def load_pixbuf(path, size=None):
    try:
        if size is None:
            return GdkPixbuf.Pixbuf.new_from_file(path)
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)

    except GLib.GError:
        try:
            with open(path, 'rb') as im_handle:
                img = Image.open(im_handle)
                avatar = img.convert("RGBA")
        except (NameError, OSError):
            log.warning('Pillow convert failed: %s', path)
            log.debug('Error', exc_info=True)
            return None

        array = GLib.Bytes.new(avatar.tobytes())
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


def get_thumbnail_size(pixbuf, size):
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


def make_href_markup(string):
    url_color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
    color = convert_rgb_to_hex(url_color)

    def _to_href(match):
        url = match.group()
        if '://' not in url:
            url = 'https://' + url
        return '<a href="%s"><span foreground="%s">%s</span></a>' % (
            url, color, match.group())

    return URL_REGEX.sub(_to_href, string)


def get_app_windows(account):
    windows = []
    for win in app.app.get_windows():
        if hasattr(win, 'account'):
            if win.account == account:
                windows.append(win)
    return windows


def get_app_window(name, account=None, jid=None):
    for win in app.app.get_windows():
        if type(win).__name__ != name:
            continue

        if account is not None:
            if account != win.account:
                continue

        if jid is not None:
            if jid != win.jid:
                continue
        return win
    return None


def open_window(name, **kwargs):
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
        self.connect('destroy', self.__on_destroy)  # pylint: disable=no-member

    def __on_destroy(self, *args):
        self.unregister_events()


def check_destroy(widget):
    def _destroy(*args):
        print('DESTROYED', args)
    widget.connect('destroy', _destroy)


def check_finalize(obj, name):
    weakref.finalize(obj, print, f'{name} has been finalized')
