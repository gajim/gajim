# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime as dt
import logging
from urllib.parse import urlparse

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import ReplyData
from gajim.common.types import ChatContactT
from gajim.common.util.preview import filename_from_uri
from gajim.common.util.preview import format_geo_coords
from gajim.common.util.preview import guess_simple_file_type
from gajim.common.util.preview import split_geo_uri
from gajim.common.util.text import quote_text

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_avatar_for_message
from gajim.gtk.util.misc import get_contact_name_for_message

log = logging.getLogger("gajim.gtk.referenced_message_widget")


class ReferencedMessageWidget(Gtk.Box, SignalManager):
    def __init__(
        self,
        contact: ChatContactT,
        original_message: mod.Message,
        show_reply_icon: bool = True,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact
        self._original_message = original_message
        self._message = original_message.get_last_correction() or original_message
        self._show_reply_icon = show_reply_icon

        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_primary_click, "pressed", self._on_clicked)
        self.add_controller(gesture_primary_click)

        self._add_content(self._message)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _add_content(self, message: mod.Message) -> None:
        main_box = Gtk.Box(
            spacing=12, hexpand=True, tooltip_text=_("Scroll to this message")
        )
        main_box.add_css_class("referenced-message")
        self.append(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name("quote-bar")
        main_box.append(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START
        )
        main_box.append(content_box)

        avatar_surface = get_avatar_for_message(
            message, self._contact, self.get_scale_factor(), AvatarSize.MESSAGE_REPLY
        )
        avatar_image = Gtk.Image.new_from_paintable(avatar_surface)
        avatar_image.set_pixel_size(AvatarSize.MESSAGE_REPLY)

        name = get_contact_name_for_message(message, self._contact)
        name_label = Gtk.Label(label=name)
        name_label.add_css_class("dimmed")
        name_label.add_css_class("small-label")
        name_label.add_css_class("bold")

        reply_icon = Gtk.Image.new_from_icon_name("lucide-reply-symbolic")

        timestamp = message.timestamp.astimezone()
        format_string = app.settings.get("time_format")
        if timestamp.date() < dt.datetime.today().date():
            format_string = app.settings.get("date_time_format")

        timestamp_label = Gtk.Label(
            label=timestamp.strftime(format_string),
            margin_start=6,
        )
        timestamp_label.add_css_class("dimmed")
        timestamp_label.add_css_class("small-label")

        meta_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        meta_box.add_css_class("small-label")
        meta_box.append(reply_icon)
        meta_box.append(avatar_image)
        meta_box.append(name_label)
        meta_box.append(timestamp_label)
        content_box.append(meta_box)

        message_box = Gtk.Box(spacing=12)
        label_text = ""
        if message.text is not None:
            if app.preview_manager.is_previewable(message.text, message.oob):
                scheme = urlparse(message.text).scheme
                if scheme == "geo":
                    location = split_geo_uri(message.text)
                    icon = Gio.Icon.new_for_string("mark-location")
                    label_text = format_geo_coords(
                        float(location.lat), float(location.lon)
                    )
                else:
                    file_name = filename_from_uri(message.text)
                    icon, file_type = guess_simple_file_type(message.text)
                    label_text = f"{file_type} ({file_name})"
                image = Gtk.Image.new_from_gicon(icon)
                message_box.append(image)
            else:
                label_text = message.text
                lines = message.text.split("\n")
                if len(lines) > 3:
                    label_text = "\n".join(lines[:3])
                    label_text = f"{label_text} …"

        message_label = Gtk.Label(
            label=label_text,
            halign=Gtk.Align.START,
            max_width_chars=100,
            ellipsize=Pango.EllipsizeMode.END,
        )
        message_label.add_css_class("dimmed")

        message_box.append(message_label)
        content_box.append(message_box)

    def _on_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        app.window.activate_action(
            "win.jump-to-message",
            GLib.Variant(
                "au",
                [
                    self._message.pk,
                    self._message.timestamp.timestamp(),
                ],
            ),
        )
        return Gdk.EVENT_STOP

    def get_message_reply(self) -> ReplyData | None:
        # We only show the reply menu if there is text
        assert self._message.text

        jid = self._message.remote.jid
        reply_to_id = self._original_message.id

        if self._message.type == MessageType.GROUPCHAT:
            jid = self._message.remote.jid
            jid = jid.new_with(resource=self._message.resource)
            reply_to_id = self._original_message.stanza_id

        if reply_to_id is None:
            return None

        quoted_text = quote_text(self._message.text)
        return ReplyData(
            pk=self._original_message.pk,
            to=jid,
            id=reply_to_id,
            fallback_start=0,
            fallback_end=len(quoted_text),
            fallback_text=quoted_text,
        )


class ReferencedMessageNotFoundWidget(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        main_box = Gtk.Box(spacing=12, hexpand=True)
        main_box.add_css_class("referenced-message")
        self.append(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name("quote-bar")
        main_box.append(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START
        )
        main_box.append(content_box)

        message_box = Gtk.Box(spacing=12)
        message_label = Gtk.Label(
            label=_("The referenced message is not available."),
            halign=Gtk.Align.START,
            max_width_chars=100,
            ellipsize=Pango.EllipsizeMode.END,
        )
        message_label.add_css_class("dimmed")

        message_box.append(message_label)
        content_box.append(message_box)


class ReplyBox(Gtk.Box, SignalManager):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, spacing=6, visible=False)
        SignalManager.__init__(self)

        reply_image = Gtk.Image.new_from_icon_name("lucide-reply-symbolic")
        reply_image.set_size_request(AvatarSize.CHAT, -1)
        reply_image.set_pixel_size(24)
        reply_image.add_css_class("dimmed")
        self.append(reply_image)

        self._close_button = Gtk.Button.new_from_icon_name("lucide-x-symbolic")
        self._close_button.set_valign(Gtk.Align.CENTER)
        self._close_button.set_tooltip_text(_("Cancel"))
        self._connect(self._close_button, "clicked", self.disable_reply_mode)
        self.append(self._close_button)

        self._ref_widget = None

    def do_unroot(self) -> None:
        self.disable_reply_mode()
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def enable_reply_mode(
        self, contact: ChatContactT, original_message: mod.Message
    ) -> None:
        if self._ref_widget is not None:
            self.disable_reply_mode()

        self._ref_widget = ReferencedMessageWidget(
            contact, original_message, show_reply_icon=False
        )
        self.append(self._ref_widget)
        self.reorder_child_after(self._close_button, self._ref_widget)
        self.set_visible(True)

    def disable_reply_mode(self, *args: Any) -> None:
        if self._ref_widget is not None:
            self.remove(self._ref_widget)
            self._ref_widget = None

        self.set_visible(False)

    @property
    def is_in_reply_mode(self) -> bool:
        return self._ref_widget is not None

    def get_message_reply(self) -> ReplyData | None:
        if self._ref_widget is None:
            return None

        return self._ref_widget.get_message_reply()
