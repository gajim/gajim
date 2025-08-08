# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from __future__ import annotations

from typing import Any
from typing import Literal

import datetime
import logging
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from functools import wraps

import cairo
from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import types
from gajim.common.configpaths import get_ui_path
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.styling import PlainBlock

from gajim.gtk.const import GDK_MEMORY_DEFAULT

log = logging.getLogger("gajim.gtk.util")


def get_gtk_version() -> str:
    return "%i.%i.%i" % (
        Gtk.get_major_version(),
        Gtk.get_minor_version(),
        Gtk.get_micro_version(),
    )


def get_adw_version() -> str:
    return "%i.%i.%i" % (
        Adw.get_major_version(),
        Adw.get_minor_version(),
        Adw.get_micro_version(),
    )


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


def scroll_to(widget: Gtk.ScrolledWindow, pos: Literal["top", "bottom"]) -> bool:
    """Scrolls to `pos` of a GtkScrolledWindow.

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

    scroll_pos = 0
    if pos == "bottom":
        scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    adj_v.set_value(scroll_pos)

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


def ensure_not_destroyed(func: Any) -> Any:
    @wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        if self._destroyed:  # pylint: disable=protected-access
            return None
        return func(self, *args, **kwargs)

    return func_wrapper


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
        if not contact.is_available:
            return False

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
            tzinfo=datetime.UTC,
        )

    g_dt = GLib.DateTime.new_from_iso8601(dt.isoformat())
    assert g_dt is not None
    return g_dt


def get_ui_string(filename: str) -> bytes:
    path = get_ui_path(filename)

    if sys.platform != "win32":
        return path.read_bytes()

    tree = ET.parse(path)
    for node in tree.findall(".//*[@translatable='yes']"):
        node.text = _(node.text) if node.text else ""
        del node.attrib["translatable"]
    return ET.tostring(tree.getroot(), method="xml")
