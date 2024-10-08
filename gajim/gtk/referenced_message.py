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

from gajim.gtk.util import get_avatar_for_message
from gajim.gtk.util import get_contact_name_for_message
from gajim.gtk.util import get_cursor

log = logging.getLogger('gajim.gtk.referenced_message_widget')


class ReferencedMessageWidget(Gtk.EventBox):
    def __init__(
        self,
        contact: ChatContactT,
        original_message: mod.Message,
        show_reply_icon: bool = True,
    ) -> None:
        Gtk.EventBox.__init__(self)

        self._contact = contact
        self._original_message = original_message
        self._message = original_message
        self._show_reply_icon = show_reply_icon

        if original_message.corrections:
            self._message = original_message.get_last_correction()

        self.connect('realize', self._on_realize)
        self.connect('button-release-event', self._on_button_release)

        self._add_content(self._message)

        self.show_all()

    def _add_content(self, message: mod.Message) -> None:
        main_box = Gtk.Box(
            spacing=12, hexpand=True, tooltip_text=_('Scroll to this message')
        )
        main_box.get_style_context().add_class('referenced-message')
        self.add(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name('quote-bar')
        main_box.add(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START
        )
        main_box.add(content_box)

        avatar_surface = get_avatar_for_message(
            message, self._contact, self.get_scale_factor(), AvatarSize.MESSAGE_REPLY
        )
        avatar_image = Gtk.Image.new_from_surface(avatar_surface)

        name = get_contact_name_for_message(message, self._contact)
        name_label = Gtk.Label(label=name)
        name_label.get_style_context().add_class('dim-label')
        name_label.get_style_context().add_class('small-label')
        name_label.get_style_context().add_class('bold')

        reply_icon = Gtk.Image.new_from_icon_name(
            'lucide-reply-symbolic', Gtk.IconSize.BUTTON
        )

        reply_icon.set_no_show_all(not self._show_reply_icon)

        timestamp = message.timestamp.astimezone()
        format_string = app.settings.get('time_format')
        if timestamp.date() < dt.datetime.today().date():
            format_string = app.settings.get('date_time_format')

        timestamp_label = Gtk.Label(
            label=timestamp.strftime(format_string),
            margin_start=6,
        )
        timestamp_label.get_style_context().add_class('dim-label')
        timestamp_label.get_style_context().add_class('small-label')

        meta_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        meta_box.get_style_context().add_class('small-label')
        meta_box.add(reply_icon)
        meta_box.add(avatar_image)
        meta_box.add(name_label)
        meta_box.add(timestamp_label)
        content_box.add(meta_box)

        message_box = Gtk.Box(spacing=12)
        label_text = ''
        if message.text is not None:
            if app.preview_manager.is_previewable(message.text, message.oob):
                scheme = urlparse(message.text).scheme
                if scheme == 'geo':
                    location = split_geo_uri(message.text)
                    icon = Gio.Icon.new_for_string('mark-location')
                    label_text = format_geo_coords(
                        float(location.lat), float(location.lon)
                    )
                else:
                    file_name = filename_from_uri(message.text)
                    icon, file_type = guess_simple_file_type(message.text)
                    label_text = f'{file_type} ({file_name})'
                image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
                message_box.add(image)
            else:
                label_text = message.text
                lines = message.text.split('\n')
                if len(lines) > 3:
                    label_text = '\n'.join(lines[:3])
                    label_text = f'{label_text} …'

        message_label = Gtk.Label(
            label=label_text,
            halign=Gtk.Align.START,
            max_width_chars=100,
            ellipsize=Pango.EllipsizeMode.END,
        )
        message_label.get_style_context().add_class('dim-label')

        message_box.add(message_label)
        content_box.add(message_box)

    def _on_button_release(
        self, _event_box: ReferencedMessageWidget, _event: Gdk.EventButton
    ) -> bool:

        app.window.activate_action(
            'jump-to-message',
            GLib.Variant(
                'au',
                [
                    self._message.pk,
                    self._message.timestamp.timestamp(),
                ],
            ),
        )
        return False

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        if window is not None:
            window.set_cursor(get_cursor('pointer'))

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


class ReferencedMessageNotFoundWidget(Gtk.EventBox):
    def __init__(self) -> None:
        Gtk.EventBox.__init__(self)

        main_box = Gtk.Box(spacing=12, hexpand=True)
        main_box.get_style_context().add_class('referenced-message')
        self.add(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name('quote-bar')
        main_box.add(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START
        )
        main_box.add(content_box)

        message_box = Gtk.Box(spacing=12)
        message_label = Gtk.Label(
            label=_('The referenced message is not available.'),
            halign=Gtk.Align.START,
            max_width_chars=100,
            ellipsize=Pango.EllipsizeMode.END,
        )
        message_label.get_style_context().add_class('dim-label')

        message_box.add(message_label)
        content_box.add(message_box)

        self.show_all()


class ReplyBox(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, spacing=12, no_show_all=True)

        reply_image = Gtk.Image.new_from_icon_name(
            'lucide-reply-symbolic', Gtk.IconSize.LARGE_TOOLBAR
        )
        reply_image.set_size_request(AvatarSize.CHAT, -1)
        reply_image.get_style_context().add_class('dim-label')
        self.pack_start(reply_image, False, True, 0)

        close_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON
        )
        close_button.set_valign(Gtk.Align.CENTER)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.set_tooltip_text(_('Cancel'))
        close_button.get_style_context().add_class('message-actions-box-button')
        close_button.get_style_context().remove_class('image-button')
        close_button.connect('clicked', self.disable_reply_mode)
        self.pack_end(close_button, False, False, 0)

        self._ref_widget = None

    def enable_reply_mode(
        self, contact: ChatContactT, original_message: mod.Message
    ) -> None:
        if self._ref_widget is not None:
            self.disable_reply_mode()

        self._ref_widget = ReferencedMessageWidget(
            contact, original_message, show_reply_icon=False
        )
        self.add(self._ref_widget)
        self.set_no_show_all(False)
        self.show_all()

    def disable_reply_mode(self, *args: Any) -> None:
        if self._ref_widget is not None:
            self._ref_widget.destroy()
            self._ref_widget = None

        self.set_no_show_all(True)
        self.hide()

    @property
    def is_in_reply_mode(self) -> bool:
        return self._ref_widget is not None

    def get_message_reply(self) -> ReplyData | None:
        if self._ref_widget is None:
            return None

        return self._ref_widget.get_message_reply()
