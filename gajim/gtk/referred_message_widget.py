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

import datetime as dt

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.structs import ReplyData

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.text import quote_text

from gajim.gtk.util import get_cursor


class ReferredMessageWidget(Gtk.EventBox):
    def __init__(self, contact: types.ChatContactT, reply_to_id: str) -> None:

        Gtk.EventBox.__init__(self)
        self.connect('realize', self._on_realize)
        self.connect('button-release-event', self._on_button_release)

        main_box = Gtk.Box(spacing=12, hexpand=True)
        main_box.set_tooltip_text(_('Scroll to this message'))
        main_box.get_style_context().add_class('referred-message')
        self.add(main_box)

        quote_bar = Gtk.Box(width_request=4)
        quote_bar.set_name('quote-bar')
        main_box.add(quote_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.START
        )
        main_box.add(content_box)

        self._contact = contact

        message = app.storage.archive.get_referred_message(contact, reply_to_id)
        assert message is not None
        self._referred_message = message

        if self._contact.is_groupchat:
            name = self._referred_message.occupant.nickname
        else:
            if self._referred_message.direction == ChatDirection.INCOMING:
                name = self._contact.name
            else:
                name = _('You')

        icon = Gtk.Image.new_from_icon_name(
            'lucide-reply-symbolic', Gtk.IconSize.BUTTON
        )
        icon.get_style_context().add_class('dim-label')

        name_label = Gtk.Label(label=name)
        name_label.get_style_context().add_class('dim-label')
        name_label.get_style_context().add_class('small-label')
        name_label.get_style_context().add_class('bold')

        timestamp = self._referred_message.timestamp.astimezone()
        format_string = app.settings.get('time_format')
        if timestamp.date() < dt.datetime.today().date():
            format_string = app.settings.get('date_time_format')

        timestamp_label = Gtk.Label(label=timestamp.strftime(format_string))
        timestamp_label.get_style_context().add_class('dim-label')
        timestamp_label.get_style_context().add_class('small-label')

        meta_box = Gtk.Box(spacing=6)
        meta_box.get_style_context().add_class('small-label')
        meta_box.add(icon)
        meta_box.add(name_label)
        meta_box.add(timestamp_label)
        content_box.add(meta_box)

        label_text = ''
        if self._referred_message.text is not None:
            label_text = self._referred_message.text
            lines = self._referred_message.text.split('\n')
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
        content_box.add(message_label)

        self.show_all()

    def _on_button_release(
        self,
        _event_box: ReferredMessageWidget,
        _event: Gdk.EventButton
    ) -> bool:

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

    def get_reply_data(self) -> ReplyData:
        if isinstance(self._contact, GroupchatContact):
            resource_contact = self._contact.get_resource(
                self._referred_message.occupant.nickname
            )
            jid = str(resource_contact.real_jid or resource_contact.jid)
        else:
            jid = self._contact.jid.bare

        reply_quoted_text = quote_text(self._referred_message.text)
        reply_to_id = self._referred_message.id
        if self._referred_message.type == MessageType.GROUPCHAT:
            reply_to_id = self._referred_message.stanza_id

        fallback_end = len(reply_quoted_text) - len(self._referred_message.text)
        return ReplyData(
            to=jid,
            id=reply_to_id,
            fallback_start=0,
            fallback_end=fallback_end,
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

    def enable_reply_mode(
        self,
        contact: types.ChatContactT,
        reply_to_id: str
    ) -> None:

        if self._ref_widget is not None:
            self.disable_reply_mode()

        self._ref_widget = ReferredMessageWidget(contact, reply_to_id)
        self.add(self._ref_widget)
        self.set_no_show_all(False)
        self.show_all()

    def disable_reply_mode(self, *args: Any) -> None:
        if self._ref_widget is not None:
            self._ref_widget.destroy()
            self._ref_widget = None

        self.set_no_show_all(True)
        self.hide()

    def get_reply_data(self) -> ReplyData | None:
        if self._ref_widget is None:
            return None

        return self._ref_widget.get_reply_data()
