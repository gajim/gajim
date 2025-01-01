# Copyright (C) 2018 Marcin Mielniczuk <marmistrz.dev AT zoho.eu>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload
from typing import TYPE_CHECKING

import datetime
import logging
import math
import textwrap
from collections.abc import Iterator
from functools import lru_cache
from functools import wraps
from importlib import import_module
from re import Match

import cairo
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gsk
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import Pango
from nbxmpp import JID
from nbxmpp import util as nbxmpp_util
from nbxmpp.structs import LocationData
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import LOCATION_DATA
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.regex import URL_REGEX
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import VariantMixin
from gajim.common.styling import PlainBlock
from gajim.common.util.user_strings import format_idle_time

from gajim.gtk.const import GDK_MEMORY_DEFAULT
from gajim.gtk.const import WINDOW_MODULES

if TYPE_CHECKING:
    from gajim.gtk.account_wizard import AccountWizard
    from gajim.gtk.accounts import AccountsWindow
    from gajim.gtk.add_contact import AddContact
    from gajim.gtk.adhoc import AdHocCommands
    from gajim.gtk.advanced_config import AdvancedConfig
    from gajim.gtk.blocking import BlockingList
    from gajim.gtk.call_window import CallWindow
    from gajim.gtk.certificate_dialog import CertificateDialog
    from gajim.gtk.change_password import ChangePassword
    from gajim.gtk.contact_info import ContactInfo
    from gajim.gtk.db_migration import DBMigration
    from gajim.gtk.debug_console import DebugConsoleWindow
    from gajim.gtk.dialogs import QuitDialog
    from gajim.gtk.discovery import ServiceDiscoveryWindow
    from gajim.gtk.features import Features
    from gajim.gtk.groupchat_creation import CreateGroupchatWindow
    from gajim.gtk.groupchat_details import GroupchatDetails
    from gajim.gtk.groupchat_invitation import GroupChatInvitationDialog
    from gajim.gtk.groupchat_join import GroupchatJoin
    from gajim.gtk.history_export import HistoryExport
    from gajim.gtk.history_sync import HistorySyncAssistant
    from gajim.gtk.mam_preferences import MamPreferences
    from gajim.gtk.manage_sounds import ManageSounds
    from gajim.gtk.password_dialog import PasswordDialog
    from gajim.gtk.pep_config import PEPConfig
    from gajim.gtk.plugins import PluginsWindow
    from gajim.gtk.preferences import Preferences
    from gajim.gtk.profile import ProfileWindow
    from gajim.gtk.proxies import ManageProxies
    from gajim.gtk.remove_account import RemoveAccount
    from gajim.gtk.roster_item_exchange import RosterItemExchange
    from gajim.gtk.server_info import ServerInfo
    from gajim.gtk.service_registration import ServiceRegistration
    from gajim.gtk.ssl_error_dialog import SSLErrorDialog
    from gajim.gtk.start_chat import StartChatDialog
    from gajim.gtk.themes import Themes
    from gajim.gtk.workspace_dialog import WorkspaceDialog

    GajimWindowT = (
        AccountsWindow
        | AccountWizard
        | AddContact
        | AdHocCommands
        | AdvancedConfig
        | DBMigration
        | DebugConsoleWindow
        | BlockingList
        | CallWindow
        | CertificateDialog
        | ChangePassword
        | ContactInfo
        | CreateGroupchatWindow
        | Features
        | GroupchatDetails
        | GroupChatInvitationDialog
        | GroupchatJoin
        | HistoryExport
        | HistorySyncAssistant
        | MamPreferences
        | ManageProxies
        | ManageSounds
        | PasswordDialog
        | PEPConfig
        | PluginsWindow
        | Preferences
        | ProfileWindow
        | QuitDialog
        | RemoveAccount
        | RosterItemExchange
        | ServerInfo
        | ServiceDiscoveryWindow
        | ServiceRegistration
        | SSLErrorDialog
        | StartChatDialog
        | Themes
        | WorkspaceDialog
    )
    GajimWindowNameT = (
        Literal["AccountsWindow"]
        | Literal["AccountWizard"]
        | Literal["AddContact"]
        | Literal["AdHocCommands"]
        | Literal["AdvancedConfig"]
        | Literal["DBMigration"]
        | Literal["DebugConsoleWindow"]
        | Literal["BlockingList"]
        | Literal["CallWindow"]
        | Literal["CertificateDialog"]
        | Literal["ChangePassword"]
        | Literal["ContactInfo"]
        | Literal["CreateGroupchatWindow"]
        | Literal["Features"]
        | Literal["GroupchatDetails"]
        | Literal["GroupChatInvitationDialog"]
        | Literal["GroupchatJoin"]
        | Literal["HistoryExport"]
        | Literal["HistorySyncAssistant"]
        | Literal["MamPreferences"]
        | Literal["ManageProxies"]
        | Literal["ManageSounds"]
        | Literal["PasswordDialog"]
        | Literal["PEPConfig"]
        | Literal["PluginsWindow"]
        | Literal["Preferences"]
        | Literal["ProfileWindow"]
        | Literal["QuitDialog"]
        | Literal["RemoveAccount"]
        | Literal["RosterItemExchange"]
        | Literal["ServerInfo"]
        | Literal["ServiceDiscoveryWindow"]
        | Literal["ServiceRegistration"]
        | Literal["SSLErrorDialog"]
        | Literal["StartChatDialog"]
        | Literal["Themes"]
        | Literal["WorkspaceDialog"]
    )

log = logging.getLogger("gajim.gtk.util")


MenuValueT = None | str | GLib.Variant | VariantMixin
MenuItemListT = list[tuple[str, str, MenuValueT]]


def icon_exists(name: str) -> bool:
    return get_icon_theme().has_icon(name)


def get_icon_theme() -> Gtk.IconTheme:
    display = Gdk.Display.get_default()
    assert display is not None
    return Gtk.IconTheme.get_for_display(display)


def load_icon_surface(
    icon_name: str,
    size: int = 16,
    scale: int | None = None,
) -> cairo.ImageSurface | None:

    if scale is None:
        scale = app.window.get_scale_factor()

    if not scale:
        log.warning("Could not determine scale factor")
        scale = 1

    icon_theme = get_icon_theme()
    icon = icon_theme.lookup_icon(
        icon_name, None, size, scale, Gtk.TextDirection.NONE, 0  # pyright: ignore
    )

    snapshot = Gtk.Snapshot()
    icon.snapshot(snapshot, size, size)
    node = cast(Gsk.TextureNode, snapshot.to_node())
    assert node is not None

    texture = node.get_texture()
    return convert_texture_to_surface(texture)


def get_status_icon_name(name: str) -> str:
    prefix = "gajim"
    if app.is_flatpak():
        prefix = app.get_default_app_id()
    return f"{prefix}-status-{name}"


def get_total_screen_geometry() -> tuple[int, int]:
    total_width = 0
    total_height = 0
    display = Gdk.Display.get_default()
    assert display is not None
    monitors = display.get_monitors()
    for num in range(monitors.get_n_items()):
        monitor = monitors.get_item(num)
        assert isinstance(monitor, Gdk.Monitor)
        geometry = monitor.get_geometry()
        total_width += geometry.width
        total_height = max(total_height, geometry.height)
    log.debug("Get screen geometry: %s %s", total_width, total_height)
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
    window.set_default_size(abs(width), abs(height))


def get_source_view_style_scheme() -> GtkSource.StyleScheme | None:
    style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
    if app.css_config.prefer_dark:
        return style_scheme_manager.get_scheme("solarized-dark")
    return style_scheme_manager.get_scheme("solarized-light")


def scroll_to_end(widget: Gtk.ScrolledWindow) -> bool:
    """Scrolls to the end of a GtkScrolledWindow.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is False so it can be used with GLib.idle_add.
    """
    adj_v = widget.get_vadjustment()
    if adj_v is None:  # pyright: ignore
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


def convert_rgba_to_hex(rgba: Gdk.RGBA) -> str:
    red = int(rgba.red * 255)
    green = int(rgba.green * 255)
    blue = int(rgba.blue * 255)
    return f"#{red:02x}{green:02x}{blue:02x}"


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


def ensure_not_destroyed(func: Any) -> Any:
    @wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        if self._destroyed:  # pylint: disable=protected-access
            return None
        return func(self, *args, **kwargs)

    return func_wrapper


def format_tune(data: TuneData) -> str:
    artist = GLib.markup_escape_text(data.artist or _("Unknown Artist"))
    title = GLib.markup_escape_text(data.title or _("Unknown Title"))
    source = GLib.markup_escape_text(data.source or _("Unknown Source"))

    return _('<b>"%(title)s"</b> by <i>%(artist)s</i>\n' "from <i>%(source)s</i>") % {
        "title": title,
        "artist": artist,
        "source": source,
    }


def get_account_tune_icon_name(account: str) -> str | None:
    client = app.get_client(account)
    tune = client.get_module("UserTune").get_current_tune()
    return None if tune is None else "audio-x-generic"


def format_location(location: LocationData) -> str:
    location_dict = location._asdict()
    location_string = ""
    for attr, value in location_dict.items():
        if value is None:
            continue
        text = GLib.markup_escape_text(value)
        # Translate standard location tag
        tag = LOCATION_DATA.get(attr)
        if tag is None:
            continue
        location_string += f"\n<b>{tag.capitalize()}</b>: {text}"

    return location_string.strip()


def get_account_location_icon_name(account: str) -> str | None:
    client = app.get_client(account)
    location = client.get_module("UserLocation").get_current_location()
    return None if location is None else "applications-internet"


def format_eta(time_: int | float) -> str:
    times = {"minutes": 0, "seconds": 0}
    time_ = int(time_)
    times["seconds"] = time_ % 60
    if time_ >= 60:
        time_ = int(time_ / 60)
        times["minutes"] = round(time_ % 60)
        return _("%(minutes)s min %(seconds)s s") % times
    return _("%s s") % times["seconds"]


def format_fingerprint(fingerprint: str) -> str:
    fplen = len(fingerprint)
    wordsize = fplen // 8
    buf = ""
    for char in range(0, fplen, wordsize):
        buf += f"{fingerprint[char:char + wordsize]} "
    buf = textwrap.fill(buf, width=36)
    return buf.rstrip().upper()


class MultiLineLabel(Gtk.Label):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.Label.__init__(self, *args, **kwargs)
        self.set_wrap(True)
        self.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_single_line_mode(False)
        self.set_selectable(True)


class MaxWidthComboBoxText(Gtk.ComboBoxText):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.ComboBoxText.__init__(self, *args, **kwargs)
        text_renderer = self.get_cells()[0]
        text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)

    def do_unroot(self) -> None:
        Gtk.ComboBoxText.do_unroot(self)
        app.check_finalize(self)

    def set_max_width_chars(self, count: int) -> None:
        text_renderer = self.get_cells()[0]
        text_renderer.set_property("max-width-chars", count)


def text_to_color(text: str) -> tuple[float, float, float]:
    if app.css_config.prefer_dark:
        lightness = 60
    else:
        lightness = 40
    return nbxmpp_util.text_to_color(text, 100, lightness)


def get_contact_color(contact: types.ChatContactT) -> tuple[float, float, float]:

    if isinstance(contact, GroupchatParticipant):
        if contact.room.muc_context in (None, "public"):
            return text_to_color(contact.name)

        if contact.real_jid is not None:
            return text_to_color(str(contact.real_jid))

    return text_to_color(str(contact.jid))


def get_color_for_account(account: str) -> str:
    col_r, col_g, col_b = text_to_color(account)
    rgba = Gdk.RGBA()
    rgba.red = col_r
    rgba.green = col_g
    rgba.blue = col_b
    rgba.alpha = 1
    return rgba.to_string()


@lru_cache(maxsize=16)
def get_css_show_class(show: str) -> str:
    if show in ("online", "chat"):
        return ".gajim-status-online"
    if show == "away":
        return ".gajim-status-away"
    if show in ("dnd", "xa"):
        return ".gajim-status-dnd"
    if show == "connecting":
        return ".gajim-status-connecting"
    return ".gajim-status-offline"


def add_css_to_widget(widget: Gtk.Widget, css: str) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)


def get_contact_name_for_message(
    db_row: mod.Message, contact: types.ChatContactT
) -> str:

    if isinstance(contact, BareContact) and contact.is_self:
        return _("Me")

    if db_row.type == MessageType.CHAT:
        if db_row.direction == ChatDirection.INCOMING:
            return contact.name
        return app.nicks[contact.account]

    elif db_row.type == MessageType.GROUPCHAT:
        resource = db_row.resource
        if resource is None:
            # Fall back to MUC name if contact name is None
            # (may be the case for service messages from the MUC)
            return contact.name
        return resource

    elif db_row.type == MessageType.PM:
        resource = db_row.resource
        assert resource is not None
        return resource

    else:
        raise ValueError


def get_avatar_for_message(
    db_row: mod.Message, contact: types.ChatContactT, scale: int, size: AvatarSize
) -> Gdk.Texture | None:

    if isinstance(contact, GroupchatContact):
        name = get_contact_name_for_message(db_row, contact)
        resource_contact = contact.get_resource(name)
        return resource_contact.get_avatar(size, scale, add_show=False)

    if db_row.direction == ChatDirection.OUTGOING:
        client = app.get_client(contact.account)
        self_contact = client.get_module("Contacts").get_contact(
            client.get_own_jid().bare
        )
        assert isinstance(self_contact, BareContact)
        return self_contact.get_avatar(size, scale, add_show=False)

    return contact.get_avatar(size, scale, add_show=False)


def get_thumbnail_size(pixbuf: GdkPixbuf.Pixbuf, size: int) -> tuple[int, int]:
    # Calculates the new thumbnail size while preserving the aspect ratio
    image_width = pixbuf.get_width()
    image_height = pixbuf.get_height()

    if image_width > image_height:
        if image_width > size:
            image_height = math.ceil(size / float(image_width) * image_height)
            image_width = int(size)
    else:
        if image_height > size:
            image_width = math.ceil(size / float(image_height) * image_width)
            image_height = int(size)

    return image_width, image_height


def make_href_markup(string: str | None) -> str:
    if not string:
        return ""

    string = GLib.markup_escape_text(string)

    def _to_href(match: Match[str]) -> str:
        url = match.group()
        if "://" not in url:
            url = f"https://{url}"
        return f'<a href="{url}">{match.group()}</a>'

    return URL_REGEX.sub(_to_href, string)


def get_app_windows(account: str) -> list[Gtk.Window]:
    windows: list[Gtk.Window] = []
    for win in app.app.get_windows():
        if hasattr(win, "account"):
            if win.account == account:  # pyright: ignore
                windows.append(win)
    return windows


@overload
def get_app_window(
    name: Literal["AccountsWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AccountsWindow | None: ...


@overload
def get_app_window(
    name: Literal["AccountWizard"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AccountWizard | None: ...


@overload
def get_app_window(
    name: Literal["AddContact"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AddContact | None: ...


@overload
def get_app_window(
    name: Literal["AdHocCommands"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AdHocCommands | None: ...


@overload
def get_app_window(
    name: Literal["AdvancedConfig"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AdvancedConfig | None: ...


@overload
def get_app_window(
    name: Literal["DBMigration"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> DBMigration | None: ...


@overload
def get_app_window(
    name: Literal["DebugConsoleWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> DebugConsoleWindow | None: ...


@overload
def get_app_window(
    name: Literal["BlockingList"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> BlockingList | None: ...


@overload
def get_app_window(
    name: Literal["CallWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CallWindow | None: ...


@overload
def get_app_window(
    name: Literal["CertificateDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CertificateDialog | None: ...


@overload
def get_app_window(
    name: Literal["ChangePassword"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ChangePassword | None: ...


@overload
def get_app_window(
    name: Literal["ContactInfo"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ContactInfo | None: ...


@overload
def get_app_window(
    name: Literal["CreateGroupchatWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CreateGroupchatWindow | None: ...


@overload
def get_app_window(
    name: Literal["Features"], account: str | None = None, jid: str | JID | None = None
) -> Features | None: ...


@overload
def get_app_window(
    name: Literal["GroupchatDetails"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> GroupchatDetails | None: ...


@overload
def get_app_window(
    name: Literal["GroupChatInvitationDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> GroupChatInvitationDialog | None: ...


@overload
def get_app_window(
    name: Literal["GroupchatJoin"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> GroupchatJoin | None: ...


@overload
def get_app_window(
    name: Literal["HistoryExport"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> HistoryExport | None: ...


@overload
def get_app_window(
    name: Literal["HistorySyncAssistant"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> HistorySyncAssistant | None: ...


@overload
def get_app_window(
    name: Literal["MamPreferences"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> MamPreferences | None: ...


@overload
def get_app_window(
    name: Literal["ManageProxies"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ManageProxies | None: ...


@overload
def get_app_window(
    name: Literal["ManageSounds"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ManageSounds | None: ...


@overload
def get_app_window(
    name: Literal["PasswordDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> PasswordDialog | None: ...


@overload
def get_app_window(
    name: Literal["PEPConfig"], account: str | None = None, jid: str | JID | None = None
) -> PEPConfig | None: ...


@overload
def get_app_window(
    name: Literal["PluginsWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> PluginsWindow | None: ...


@overload
def get_app_window(
    name: Literal["Preferences"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> Preferences | None: ...


@overload
def get_app_window(
    name: Literal["ProfileWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ProfileWindow | None: ...


@overload
def get_app_window(
    name: Literal["QuitDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> QuitDialog | None: ...


@overload
def get_app_window(
    name: Literal["RemoveAccount"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> RemoveAccount | None: ...


@overload
def get_app_window(
    name: Literal["RosterItemExchange"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> RosterItemExchange | None: ...


@overload
def get_app_window(
    name: Literal["ServerInfo"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ServerInfo | None: ...


@overload
def get_app_window(
    name: Literal["ServiceDiscoveryWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ServiceDiscoveryWindow | None: ...


@overload
def get_app_window(
    name: Literal["ServiceRegistration"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ServiceRegistration | None: ...


@overload
def get_app_window(
    name: Literal["SSLErrorDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> SSLErrorDialog | None: ...


@overload
def get_app_window(
    name: Literal["StartChatDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> StartChatDialog | None: ...


@overload
def get_app_window(
    name: Literal["Themes"], account: str | None = None, jid: str | JID | None = None
) -> Themes | None: ...


@overload
def get_app_window(
    name: Literal["WorkspaceDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> WorkspaceDialog | None: ...


def get_app_window(
    name: str, account: str | None = None, jid: str | JID | None = None
) -> GajimWindowT | None:
    for win in app.app.get_windows():
        if win.get_name() != name:
            continue

        if account is not None:
            if account != win.wrapper.account:  # pyright: ignore
                continue

        if jid is not None:
            if jid != win.wrapper.jid:  # pyright: ignore
                continue
        return win.wrapper  # pyright: ignore
    return None


@overload
def open_window(name: Literal["AccountsWindow"], **kwargs: Any) -> AccountsWindow: ...
@overload
def open_window(name: Literal["AccountWizard"], **kwargs: Any) -> AccountWizard: ...
@overload
def open_window(name: Literal["AddContact"], **kwargs: Any) -> AddContact: ...
@overload
def open_window(name: Literal["AdHocCommands"], **kwargs: Any) -> AdHocCommands: ...
@overload
def open_window(name: Literal["AdvancedConfig"], **kwargs: Any) -> AdvancedConfig: ...
@overload
def open_window(name: Literal["DBMigration"], **kwargs: Any) -> DBMigration: ...
@overload
def open_window(
    name: Literal["DebugConsoleWindow"], **kwargs: Any
) -> DebugConsoleWindow: ...
@overload
def open_window(name: Literal["BlockingList"], **kwargs: Any) -> BlockingList: ...
@overload
def open_window(name: Literal["CallWindow"], **kwargs: Any) -> CallWindow: ...
@overload
def open_window(
    name: Literal["CertificateDialog"], **kwargs: Any
) -> CertificateDialog: ...
@overload
def open_window(name: Literal["ChangePassword"], **kwargs: Any) -> ChangePassword: ...
@overload
def open_window(name: Literal["ContactInfo"], **kwargs: Any) -> ContactInfo: ...
@overload
def open_window(
    name: Literal["CreateGroupchatWindow"], **kwargs: Any
) -> CreateGroupchatWindow: ...
@overload
def open_window(name: Literal["Features"], **kwargs: Any) -> Features: ...
@overload
def open_window(
    name: Literal["GroupchatDetails"], **kwargs: Any
) -> GroupchatDetails: ...
@overload
def open_window(
    name: Literal["GroupChatInvitationDialog"], **kwargs: Any
) -> GroupChatInvitationDialog: ...
@overload
def open_window(name: Literal["GroupchatJoin"], **kwargs: Any) -> GroupchatJoin: ...
@overload
def open_window(name: Literal["HistoryExport"], **kwargs: Any) -> HistoryExport: ...
@overload
def open_window(
    name: Literal["HistorySyncAssistant"], **kwargs: Any
) -> HistorySyncAssistant: ...
@overload
def open_window(name: Literal["MamPreferences"], **kwargs: Any) -> MamPreferences: ...
@overload
def open_window(name: Literal["ManageProxies"], **kwargs: Any) -> ManageProxies: ...
@overload
def open_window(name: Literal["ManageSounds"], **kwargs: Any) -> ManageSounds: ...
@overload
def open_window(name: Literal["PasswordDialog"], **kwargs: Any) -> PasswordDialog: ...
@overload
def open_window(name: Literal["PEPConfig"], **kwargs: Any) -> PEPConfig: ...
@overload
def open_window(name: Literal["PluginsWindow"], **kwargs: Any) -> PluginsWindow: ...
@overload
def open_window(name: Literal["Preferences"], **kwargs: Any) -> Preferences: ...
@overload
def open_window(name: Literal["ProfileWindow"], **kwargs: Any) -> ProfileWindow: ...
@overload
def open_window(name: Literal["QuitDialog"], **kwargs: Any) -> QuitDialog: ...
@overload
def open_window(name: Literal["RemoveAccount"], **kwargs: Any) -> RemoveAccount: ...
@overload
def open_window(
    name: Literal["RosterItemExchange"], **kwargs: Any
) -> RosterItemExchange: ...
@overload
def open_window(name: Literal["ServerInfo"], **kwargs: Any) -> ServerInfo: ...
@overload
def open_window(
    name: Literal["ServiceDiscoveryWindow"], **kwargs: Any
) -> ServiceDiscoveryWindow: ...
@overload
def open_window(
    name: Literal["ServiceRegistration"], **kwargs: Any
) -> ServiceRegistration: ...
@overload
def open_window(name: Literal["SSLErrorDialog"], **kwargs: Any) -> SSLErrorDialog: ...
@overload
def open_window(name: Literal["StartChatDialog"], **kwargs: Any) -> StartChatDialog: ...
@overload
def open_window(name: Literal["Themes"], **kwargs: Any) -> Themes: ...
@overload
def open_window(name: Literal["WorkspaceDialog"], **kwargs: Any) -> WorkspaceDialog: ...


def open_window(name: GajimWindowNameT, **kwargs: Any) -> GajimWindowT:
    window = get_app_window(name, kwargs.get("account"), kwargs.get("jid"))
    if window is None:
        module = import_module(WINDOW_MODULES[name])
        window_cls = getattr(module, name)
        window = window_cls(**kwargs)

    window.present()
    return window


def get_gtk_version() -> str:
    return "%i.%i.%i" % (
        Gtk.get_major_version(),
        Gtk.get_minor_version(),
        Gtk.get_micro_version(),
    )


def _connect_destroy(
    sender: Any,
    func: Any,
    detailed_signal: str,
    handler: Any,
    *args: Any,
    **kwargs: Any,
) -> int:
    """Connect a bound method to a foreign object signal and disconnect
    if the object the method is bound to emits destroy (Gtk.Widget subclass).
    Also works if the handler is a nested function in a method and
    references the method's bound object.
    This solves the problem that the sender holds a strong reference
    to the bound method and the bound to object doesn't get GCed.
    """
    # TODO GTK4: keep and adapt?

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

    obj.connect("destroy", disconnect_cb)
    return handler_id


def connect_destroy(sender: Any, *args: Any, **kwargs: Any) -> int:
    return _connect_destroy(sender, sender.connect, *args, **kwargs)


class GroupBadge(Gtk.Label):
    def __init__(self, group: str) -> None:
        Gtk.Label.__init__(
            self,
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.END,
            hexpand=True,
            label=group,
            valign=Gtk.Align.CENTER,
            max_width_chars=20,
        )

        self.add_css_class("group")


class GroupBadgeBox(Gtk.Box):
    __gtype_name__ = "GroupBadgeBox"

    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        self._groups: list[str] = []

    @GObject.Property(type=object)
    def groups(self) -> list[str]:  # pyright: ignore
        return self._groups

    @groups.setter
    def groups(self, groups: list[str] | None) -> None:
        if groups is None:
            groups = []

        self._groups = groups[:3]
        container_remove_all(self)
        visible = bool(groups)
        self.set_visible(visible)
        if not visible:
            return

        for group in self._groups:
            self.append(GroupBadge(group))


class IdleBadge(Gtk.Label):
    __gtype_name__ = "IdleBadge"

    def __init__(self, idle: datetime.datetime | None = None) -> None:
        Gtk.Label.__init__(
            self,
            halign=Gtk.Align.START,
            hexpand=True,
            ellipsize=Pango.EllipsizeMode.NONE,
            visible=False,
        )
        self.set_size_request(50, -1)
        self.add_css_class("dim-label")
        self.add_css_class("small-label")

    @GObject.Property(type=object)
    def idle(self) -> str:  # pyright: ignore
        return self.get_text()

    @idle.setter
    def idle(self, value: datetime.datetime | None) -> None:
        return self._set_idle(value)

    def _set_idle(self, value: datetime.datetime | None) -> None:
        self.set_visible(bool(value))
        if value is None:
            return

        self.set_text(_("Last seen: %s") % format_idle_time(value))
        format_string = app.settings.get("date_time_format")
        self.set_tooltip_text(value.strftime(format_string))


class AccountBadge(Gtk.Label):
    __gtype_name__ = "AccountBadge"

    def __init__(self, account: str | None = None, bind_setting: bool = False) -> None:
        Gtk.Label.__init__(self)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(12)
        self.set_size_request(50, -1)
        self.add_css_class("badge")
        self.set_visible(False)

        self._bind_setting = bind_setting

        if account is not None:
            self.set_account(account)
            self.show()

    def do_unroot(self) -> None:
        app.settings.disconnect_signals(self)
        Gtk.Label.do_unroot(self)
        app.check_finalize(self)

    @GObject.Property(type=str)
    def account(self) -> str:  # pyright: ignore
        return self.get_text()

    @account.setter
    def account(self, value: str) -> None:
        self.set_account(value)

    def set_account(self, account: str) -> None:
        label = app.get_account_label(account)
        self.set_text(label)

        for style_class in self.get_css_classes():
            if style_class.startswith("gajim_class"):
                self.remove_css_class(style_class)

        account_class = app.css_config.get_dynamic_class(account)
        self.add_css_class(account_class)

        self.set_tooltip_text(_("Account: %s") % label)
        if self._bind_setting:
            app.settings.disconnect_signals(self)
            app.settings.connect_signal(
                "account_label", self._on_account_label_changed, account
            )

    def _on_account_label_changed(
        self, _value: str, _setting: str, account: str | None, *args: Any
    ) -> None:

        assert account is not None
        self.set_account(account)


def make_pango_attributes(block: PlainBlock) -> Pango.AttrList:
    attrlist = Pango.AttrList()
    for span in block.spans:
        attr = get_style_attribute_with_name(span.name)
        attr.start_index = span.start_byte
        attr.end_index = span.end_byte
        attrlist.insert(attr)
    return attrlist


_grapheme_buffer = Gtk.TextBuffer()


def get_first_graphemes(text: str, n: int) -> str:
    # This should be possible with lower-level APIs like Pango.break_* or
    # Pango.get_log_attrs, but their Python bindings seem totally broken.
    # The reuse of one global buffer is to mitigate very probable memory leaks.
    _grapheme_buffer.set_text(text)
    cursor = _grapheme_buffer.get_start_iter()
    cursor.forward_cursor_positions(n)
    return _grapheme_buffer.get_slice(_grapheme_buffer.get_start_iter(), cursor, False)


def get_first_grapheme(text: str) -> str:
    return get_first_graphemes(text, 1)


def get_style_attribute_with_name(name: str) -> Pango.Attribute:
    if name == "strong":
        return Pango.attr_weight_new(Pango.Weight.BOLD)

    if name == "strike":
        return Pango.attr_strikethrough_new(True)

    if name == "emphasis":
        return Pango.attr_style_new(Pango.Style.ITALIC)

    if name == "pre":
        return Pango.attr_family_new("monospace")

    raise ValueError("unknown attribute %s" % name)


def get_key_theme() -> str | None:
    settings = Gtk.Settings.get_default()
    if settings is None:
        return None
    return settings.get_property("gtk-key-theme-name")


def make_menu_item(
    label: str, action: str | None = None, value: MenuValueT = None
) -> Gio.MenuItem:

    item = Gio.MenuItem.new(label)

    if value is None:
        item.set_action_and_target_value(action, None)
        return item

    item = Gio.MenuItem.new(label)
    if isinstance(value, str):
        item.set_action_and_target_value(action, GLib.Variant("s", value))
    elif isinstance(value, VariantMixin):
        item.set_action_and_target_value(action, value.to_variant())
    else:
        item.set_action_and_target_value(action, value)
    return item


def allow_send_message(has_text: bool, contact: types.ChatContactT) -> bool:
    if isinstance(contact, GroupchatContact):
        joined = contact.is_joined

        is_visitor = False
        if joined:
            self_contact = contact.get_self()
            assert self_contact
            is_visitor = self_contact.role.is_visitor

        return bool(has_text and joined and not is_visitor)

    if isinstance(contact, GroupchatParticipant):
        groupchat_contact = contact.room
        joined = groupchat_contact.is_joined

        is_visitor = False
        if joined:
            self_contact = groupchat_contact.get_self()
            assert self_contact
            is_visitor = self_contact.role.is_visitor

        return bool(has_text and joined and not is_visitor)

    # BareContact
    online = app.account_is_connected(contact.account)
    return bool(online and has_text)


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

    def add_item(
        self, label: str, action: str, value: MenuValueT | None = None
    ) -> None:
        item = make_menu_item(label, action, value)
        self.append_item(item)

    def add_submenu(self, label: str) -> GajimMenu:
        menu = GajimMenu()
        self.append_submenu(label, menu)
        return menu


class GdkRectangle(Gdk.Rectangle):
    def __init__(self, x: int, y: int, height: int = 1, width: int = 1) -> None:

        Gdk.Rectangle.__init__(self)
        self.x = x
        self.y = y
        self.height = height
        self.width = width


class GajimPopover(Gtk.PopoverMenu):
    __gtype_name__ = "GajimPopover"

    def __init__(
        self,
        menu: Gio.MenuModel | None = None,
        position: Gtk.PositionType = Gtk.PositionType.RIGHT,
        event: Any | None = None,
    ) -> None:

        Gtk.PopoverMenu.__init__(self, autohide=True)

        if menu is not None:
            self.set_menu_model(menu)

        self.set_position(position)
        if event is not None:
            self.set_pointing_from_event(event)

    def set_pointing_from_event(self, event: Any) -> None:
        self.set_pointing_to_coord(event.x, event.y)

    def set_pointing_to_coord(self, x: float, y: float) -> None:
        rectangle = GdkRectangle(x=int(x), y=int(y))
        self.set_pointing_to(rectangle)


def iterate_listbox_children(listbox: Gtk.ListBox) -> Iterator[Gtk.Widget]:
    index = 0
    while child := listbox.get_row_at_index(index):
        yield child
        index += 1


def container_remove_all(container: Any) -> None:
    while child := container.get_first_child():
        container.remove(child)


def clear_listbox(listbox: Gtk.ListBox) -> None:
    """Gtk.ListBox.remove_all() does not work if backed by a model."""
    for row in iterate_listbox_children(listbox):
        listbox.remove(row)


def get_listbox_row_count(listbox: Gtk.ListBox) -> int:
    return len(list(iterate_listbox_children(listbox)))


def iterate_children(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    child = widget.get_first_child()
    if child is None:
        return
    yield child

    while child := child.get_next_sibling():
        yield child


def convert_surface_to_texture(surface: cairo.ImageSurface) -> Gdk.Texture:
    memoryv = surface.get_data()
    assert memoryv is not None
    return Gdk.MemoryTexture.new(
        width=surface.get_width(),
        height=surface.get_height(),
        format=GDK_MEMORY_DEFAULT,
        bytes=GLib.Bytes.new(memoryv.tobytes()),
        stride=surface.get_stride(),
    )


def convert_texture_to_surface(texture: Gdk.Texture) -> cairo.ImageSurface:
    downloader = Gdk.TextureDownloader.new(texture)
    gbytes, stride = downloader.download_bytes()
    bytes_ = gbytes.get_data()
    assert bytes_ is not None
    array = bytearray(bytes_)

    surface = cairo.ImageSurface.create_for_data(
        array,  # pyright: ignore
        cairo.Format.ARGB32,
        texture.get_width(),
        texture.get_height(),
        stride,
    )
    return surface


def convert_py_to_glib_datetime(dt: datetime.datetime | datetime.date) -> GLib.DateTime:
    if type(dt) is datetime.date:
        dt = datetime.datetime(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=datetime.timezone.utc,
        )

    g_dt = GLib.DateTime.new_from_iso8601(dt.isoformat())
    assert g_dt is not None
    return g_dt


class SignalManager:
    def __init__(self) -> None:
        self._signal_data: list[tuple[GObject.Object | Gio.Action, int]] = []

    def _connect(
        self,
        obj: GObject.Object | Gio.Action,
        signal_name: str,
        callback: Any,
        *args: Any,
    ) -> int:

        signal_id = obj.connect(signal_name, callback, *args)
        self._signal_data.append((obj, signal_id))
        return signal_id

    def _connect_after(
        self, obj: GObject.Object, signal_name: str, callback: Any, *args: Any
    ) -> int:

        signal_id = obj.connect_after(signal_name, callback, *args)
        self._signal_data.append((obj, signal_id))
        return signal_id

    def _disconnect_all(self):
        for obj, signal_id in self._signal_data:
            obj.disconnect(signal_id)
        self._signal_data.clear()
