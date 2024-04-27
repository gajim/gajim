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
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import format_geo_coords
from gajim.common.preview_helpers import guess_simple_file_type
from gajim.common.preview_helpers import split_geo_uri
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import ReplyData
from gajim.common.types import ChatContactT
from gajim.common.util.text import quote_text

from gajim.gtk.util import get_avatar_for_message
from gajim.gtk.util import get_contact_name_for_message
from gajim.gtk.util import get_cursor

log = logging.getLogger('gajim.gtk.referred_message_widget')


class ReferredMessageWidget(Gtk.EventBox):
    def __init__(
        self, contact: ChatContactT, pk: int, reply_mode: bool = False
    ) -> None:
        Gtk.EventBox.__init__(self)

        self._contact = contact

        self._message = app.storage.archive.get_message_with_pk(pk)
        if self._message is None:
            log.warning('Could not find message with pk %s in database', pk)
            return

        if reply_mode:
            # In reply mode the ReferredMessage widget shows
            # the original message, which is about to be replied to.
            self._referred_message = self._message
        else:
            assert self._message.reply is not None
            if self._message.type == MessageType.GROUPCHAT:
                self._referred_message = \
                    app.storage.archive.get_message_with_stanza_id(
                        self._contact.account,
                        self._contact.jid,
                        self._message.reply.id
                )
            else:
                self._referred_message = \
                    app.storage.archive.get_message_with_id(
                        self._contact.account,
                        self._contact.jid,
                        self._message.reply.id
                )

            if self._referred_message is None:
                log.warning(
                    'Could not find referred message in with id %s database',
                    self._message.reply.id,
                )
                return

        self.connect('realize', self._on_realize)
        self.connect('button-release-event', self._on_button_release)

        self._add_content(self._referred_message)

        self.show_all()

    def _add_content(self, message: mod.Message) -> None:
        main_box = Gtk.Box(
            spacing=12, hexpand=True, tooltip_text=_('Scroll to this message')
        )
        main_box.get_style_context().add_class('referred-message')
        self.add(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name('quote-bar')
        main_box.add(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START
        )
        main_box.add(content_box)

        name_box = Gtk.Box(spacing=6)
        avatar_surface = get_avatar_for_message(
            message,
            self._contact,
            self.get_scale_factor(),
            AvatarSize.MESSAGE_REPLY
        )
        avatar_image = Gtk.Image.new_from_surface(avatar_surface)
        name_box.add(avatar_image)

        name = get_contact_name_for_message(message, self._contact)
        name_label = Gtk.Label(label=name, valign=Gtk.Align.START)
        name_label.get_style_context().add_class('dim-label')
        name_label.get_style_context().add_class('small-label')
        name_label.get_style_context().add_class('bold')
        name_box.add(name_label)

        reply_icon = Gtk.Image.new_from_icon_name(
            'lucide-reply-symbolic', Gtk.IconSize.BUTTON
        )
        reply_icon.set_valign(Gtk.Align.CENTER)
        reply_icon.get_style_context().add_class('dim-label')

        timestamp = message.timestamp.astimezone()
        format_string = app.settings.get('time_format')
        if timestamp.date() < dt.datetime.today().date():
            format_string = app.settings.get('date_time_format')

        timestamp_label = Gtk.Label(
            label=timestamp.strftime(format_string), valign=Gtk.Align.CENTER
        )
        timestamp_label.get_style_context().add_class('dim-label')
        timestamp_label.get_style_context().add_class('small-label')

        meta_box = Gtk.Box(spacing=6)
        meta_box.get_style_context().add_class('small-label')
        meta_box.add(reply_icon)
        meta_box.add(name_box)
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
            max_width_chars=52,
            ellipsize=Pango.EllipsizeMode.END,
        )
        message_label.get_style_context().add_class('dim-label')

        message_box.add(message_label)
        content_box.add(message_box)

    def _on_button_release(
        self, _event_box: ReferredMessageWidget, _event: Gdk.EventButton
    ) -> bool:

        # Widget can only be clicked once a message was found
        assert self._referred_message is not None
        app.window.activate_action(
            'jump-to-message',
            GLib.Variant(
                'au',
                [
                    self._referred_message.pk,
                    self._referred_message.timestamp.timestamp(),
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
        if self._message is None:
            return None

        # We only show the reply menu if there is text
        assert self._message.text

        jid = self._message.remote.jid
        reply_to_id = self._message.id

        if self._message.type == MessageType.GROUPCHAT:
            jid = self._message.remote.jid
            jid = jid.new_with(resource=self._message.resource)
            reply_to_id = self._message.stanza_id

        if reply_to_id is None:
            return None

        quoted_text = quote_text(self._message.text)
        return ReplyData(
            to=jid,
            id=reply_to_id,
            fallback_start=0,
            fallback_end=len(quoted_text),
            fallback_text=quoted_text
        )


class ReplyBox(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, spacing=14, no_show_all=True)

        close_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON
        )
        close_button.set_valign(Gtk.Align.CENTER)
        close_button.set_tooltip_text(_('Cancel'))
        close_button.connect('clicked', self.disable_reply_mode)
        self.pack_end(close_button, False, False, 0)

        self._ref_widget = None

    def enable_reply_mode(self, contact: ChatContactT, pk: int) -> None:
        if self._ref_widget is not None:
            self.disable_reply_mode()

        self._ref_widget = ReferredMessageWidget(contact, pk, reply_mode=True)
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
