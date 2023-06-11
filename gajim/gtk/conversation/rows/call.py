# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GdkPixbuf
from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.events import JingleRequestReceived
from gajim.common.i18n import _
from gajim.common.jingle_session import JingleSession
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.models import Message
from gajim.common.util.datetime import utc_now

from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import NicknameLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel


class CallRow(BaseRow):
    def __init__(self,
                 account: str,
                 contact: types.BareContact,
                 event: JingleRequestReceived | None = None,
                 db_row: Message | None = None
                 ) -> None:
        BaseRow.__init__(self, account)

        self.type = 'call'

        self._client = app.get_client(account)

        if db_row is not None:
            timestamp = db_row.timestamp
        else:
            timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        self._contact = contact
        self._event = event
        self._db_row = db_row

        self._session: JingleSession | None = None

        if db_row is not None and db_row.call is not None:
            module = self._client.get_module('Jingle')
            self._session = module.get_jingle_session(
                str(self._contact.jid), db_row.call.sid)
            self.pk = db_row.pk

        self._avatar_placeholder = Gtk.Box()
        self._avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(self._avatar_placeholder, 0, 0, 1, 1)

        if event is None and self._session is None:
            self._add_history_call_widget()
        else:
            self._add_incoming_call_widget()

        self.show_all()

    def update(self) -> None:
        if self._event is None and self._session is None:
            return

        self._call_box.destroy()
        self._add_history_call_widget()

        self._event = None
        self._session = None

    def _on_accept(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        self._decline_button.set_sensitive(False)
        if self._event is not None:
            session = self._client.get_module('Jingle').get_jingle_session(
                self._event.fjid, self._event.sid)
            if session is not None:
                app.call_manager.accept_call(session)
        else:
            assert self._session is not None
            app.call_manager.accept_call(self._session)

    def _on_decline(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        self._accept_button.set_sensitive(False)
        if self._event is not None:
            session = self._client.get_module('Jingle').get_jingle_session(
                self._event.fjid, self._event.sid)
            if session is not None:
                app.call_manager.decline_call(session)
        else:
            assert self._session is not None
            app.call_manager.decline_call(self._session)
        self._session = None

    def _add_history_call_widget(self) -> None:
        contact = self._client.get_module('Contacts').get_contact(
            self._client.get_own_jid().bare)
        assert isinstance(contact, BareContact)

        is_self = True
        if self._db_row is not None:
            if self._db_row.direction == ChatDirection.INCOMING:
                contact = self._contact
                is_self = True
            else:
                is_self = False

        if self._event is not None:
            is_self = False
        else:
            contact = self._contact
            is_self = True

        scale = self.get_scale_factor()
        avatar = contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
        assert not isinstance(avatar, GdkPixbuf.Pixbuf)
        avatar_image = Gtk.Image.new_from_surface(avatar)
        self._avatar_placeholder.add(avatar_image)

        name_widget = NicknameLabel(contact.name, is_self)
        name_widget.set_halign(Gtk.Align.START)
        name_widget.set_valign(Gtk.Align.START)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.START)

        meta_box = Gtk.Box()
        meta_box.set_spacing(6)
        meta_box.add(name_widget)
        meta_box.add(timestamp_widget)
        self.grid.attach(meta_box, 1, 0, 1, 1)

        icon = Gtk.Image.new_from_icon_name('call-start-symbolic',
                                            Gtk.IconSize.MENU)

        label = SimpleLabel()
        label.get_style_context().add_class('dim-label')
        label.set_text(_('Call'))

        content_box = Gtk.Box(spacing=12)
        content_box.add(icon)
        content_box.add(label)
        self.grid.attach(content_box, 1, 1, 1, 1)
        self.show_all()

    def _add_incoming_call_widget(self) -> None:
        self._call_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._call_box.set_size_request(350, -1)
        self._call_box.get_style_context().add_class('conversation-call-box')
        self._call_box.get_style_context().add_class('gajim-call-message')

        scale = self.get_scale_factor()
        avatar = self._contact.get_avatar(
            AvatarSize.CALL,
            scale,
            add_show=False)
        assert not isinstance(avatar, GdkPixbuf.Pixbuf)
        avatar_image = Gtk.Image.new_from_surface(avatar)
        self._call_box.add(avatar_image)

        content_types: list[str] = []
        if self._event is not None:
            for item in self._event.contents:
                content_types.append(item.media)
        if self._session is not None:
            if self._session.get_content('audio') is not None:
                content_types.append('audio')
            if self._session.get_content('video') is not None:
                content_types.append('video')

        text = _('%s is calling') % self._contact.name
        if 'video' in content_types:
            text += _(' (Video Call)')
        else:
            text += _(' (Voice Call)')
        label = Gtk.Label(label=text)
        label.get_style_context().add_class('bold')
        label.set_max_width_chars(40)
        label.set_line_wrap(True)
        self._call_box.add(label)

        self._decline_button = Gtk.Button()
        if self._session is not None:
            self._decline_button.set_sensitive(not self._session.accepted)
        self._decline_button.get_style_context().add_class(
            'destructive-action')
        self._decline_button.connect('clicked', self._on_decline)
        decline_icon = Gtk.Image.new_from_icon_name(
            'call-stop-symbolic', Gtk.IconSize.DND)
        self._decline_button.add(decline_icon)
        decline_label = Gtk.Label(label=_('Decline'))
        decline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        decline_box.add(self._decline_button)
        decline_box.add(decline_label)

        self._accept_button = Gtk.Button()
        if self._session is not None:
            self._accept_button.set_sensitive(not self._session.accepted)
        self._accept_button.get_style_context().add_class(
            'suggested-action')
        self._accept_button.connect('clicked', self._on_accept)
        accept_icon = Gtk.Image.new_from_icon_name(
            'call-start-symbolic', Gtk.IconSize.DND)
        self._accept_button.add(accept_icon)
        accept_label = Gtk.Label(label=_('Accept'))
        accept_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        accept_box.add(self._accept_button)
        accept_box.add(accept_label)

        button_box = Gtk.Box(spacing=50)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.add(decline_box)
        button_box.add(accept_box)
        self._call_box.add(button_box)

        self.grid.attach(self._call_box, 1, 0, 1, 1)
