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

import cairo
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.const import XmppUriQuery
from gajim.common.events import AccountEnabled
from gajim.common.events import BookmarksReceived
from gajim.common.events import MessageReceived
from gajim.common.ged import EventHelper
from gajim.common.helpers import generate_qr_code
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.builder import get_builder
from gajim.gtk.groupchat_voice_requests_button import VoiceRequestsButton
from gajim.gtk.menus import get_groupchat_menu
from gajim.gtk.menus import get_private_chat_menu
from gajim.gtk.menus import get_self_contact_menu
from gajim.gtk.menus import get_singlechat_menu
from gajim.gtk.tooltips import ContactTooltip
from gajim.gtk.util import AccountBadge


class ChatBanner(Gtk.Box, EventHelper):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self._client: types.Client | None = None
        self._contact: types.ChatContactT | None = None

        self._last_message_from_phone: set[BareContact] = set()

        self._ui = get_builder('chat_banner.ui')
        self.add(self._ui.banner_box)
        self._ui.connect_signals(self)

        self._account_badge = AccountBadge()
        self._voice_requests_button = VoiceRequestsButton()

        self._ui.additional_items_box.pack_start(
            self._voice_requests_button, False, True, 0)
        self._ui.additional_items_box.pack_end(
            self._account_badge, False, True, 0)

        hide_roster = app.settings.get('hide_groupchat_occupants_list')
        self._set_toggle_roster_button_icon(hide_roster)

        app.settings.connect_signal(
            'hide_groupchat_occupants_list',
            self._set_toggle_roster_button_icon)

        self.show_all()

    def clear(self) -> None:
        self._disconnect_signals()
        self.unregister_events()

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self._disconnect_signals()
        self._client = app.get_client(contact.account)
        self._contact = contact
        self._connect_signals()

        if not self.has_events_registered():
            self.register_events([
                ('message-received', ged.GUI2, self._on_message_received),
                ('bookmarks-received', ged.GUI2, self._on_bookmarks_received),
                ('account-enabled', ged.GUI2, self._on_account_changed),
                ('account-disabled', ged.GUI2, self._on_account_changed)
            ])

        self._voice_requests_button.switch_contact(self._contact)

        self._set_chat_menu(contact)
        self._update_phone_image()
        self._update_robot_image()
        self._update_roster_button()
        self._update_avatar()
        self._update_visitor_button()
        self._update_name_label()
        self._update_description_label()
        self._update_account_badge()
        self._update_share_box()

    def _connect_signals(self) -> None:
        assert self._contact is not None
        assert self._client is not None

        self._contact.multi_connect({
            'chatstate-update': self._on_chatstate_update,
            'nickname-update': self._on_nickname_update,
            'avatar-update': self._on_avatar_update,
            'presence-update': self._on_presence_update,
            'caps-update': self._on_caps_update
        })

        if isinstance(self._contact, GroupchatContact):
            self._contact.multi_connect({
                'user-role-changed': self._on_user_role_changed,
                'state-changed': self._on_muc_state_changed,
                'room-voice-request': self._on_room_voice_request,
                'disco-info-update': self._on_disco_info_update,
            })

        elif isinstance(self._contact, GroupchatParticipant):
            self._contact.multi_connect({
                'user-joined': self._on_user_state_changed,
                'user-left': self._on_user_state_changed,
                'user-avatar-update': self._on_user_avatar_update,
            })

        self._client.connect_signal('state-changed',
                                    self._on_client_state_changed)

    def _disconnect_signals(self) -> None:
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)
            self._contact = None

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)
            self._client = None

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: SimpleClientState):

        self._update_avatar()

    def _on_presence_update(self,
                            _contact: types.BareContact,
                            _signal_name: str
                            ) -> None:

        self._update_avatar()
        self._update_description_label()

    def _on_chatstate_update(self,
                             _contact: types.BareContact,
                             _signal_name: str
                             ) -> None:

        self._update_name_label()

    def _on_nickname_update(self,
                            _contact: types.BareContact,
                            _signal_name: str
                            ) -> None:

        self._update_name_label()

    def _on_avatar_update(self,
                          _contact: types.BareContact,
                          _signal_name: str
                          ) -> None:

        self._update_avatar()

    def _on_caps_update(self,
                        _contact: types.BareContact,
                        _signal_name: str
                        ) -> None:
        self._update_avatar()
        self._update_robot_image()

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:

        self._update_visitor_button()

    def _on_room_voice_request(self, *args: Any) -> None:
        self._voice_requests_button.set_no_show_all(False)
        self._voice_requests_button.show_all()

    def _on_user_role_changed(self, *args: Any) -> None:
        self._update_visitor_button()

    def _on_user_state_changed(self, *args: Any) -> None:
        self._update_avatar()

    def _on_user_avatar_update(self, *args: Any) -> None:
        self._update_avatar()

    def _on_bookmarks_received(self, _event: BookmarksReceived) -> None:
        if not isinstance(self._contact, GroupchatContact):
            return

        self._update_name_label()

    def _on_disco_info_update(self,
                              _contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:

        self._update_name_label()
        self._update_description_label()

    def _on_account_changed(self, event: AccountEnabled) -> None:
        self._update_account_badge()

    def _on_message_received(self, event: MessageReceived) -> None:
        if (not isinstance(self._contact, BareContact) or
                event.jid != self._contact.jid or
                not event.msgtxt or
                event.properties.is_sent_carbon or
                event.resource is None):
            return

        resource_contact = self._contact.get_resource(event.resource)
        if resource_contact.is_phone:
            self._last_message_from_phone.add(self._contact)
        else:
            self._last_message_from_phone.discard(self._contact)

        self._update_phone_image()

    def _set_chat_menu(self, contact: types.ChatContactT) -> None:
        if isinstance(contact, GroupchatContact):
            menu = get_groupchat_menu(contact)
        elif isinstance(contact, GroupchatParticipant):
            menu = get_private_chat_menu(contact)
        elif contact.is_self:
            menu = get_self_contact_menu(contact)
        else:
            menu = get_singlechat_menu(contact)
        self._ui.chat_menu_button.set_menu_model(menu)

    def _update_phone_image(self) -> None:
        self._ui.phone_image.set_visible(
            self._contact in self._last_message_from_phone)

    def _update_robot_image(self) -> None:
        if isinstance(self._contact, BareContact):
            self._ui.robot_image.set_visible(self._contact.is_gateway
                                             or self._contact.is_bot)
        else:
            self._ui.robot_image.set_visible(False)

    def _update_roster_button(self) -> None:
        self._ui.toggle_roster_button.set_visible(
            isinstance(self._contact, GroupchatContact))

    def _update_avatar(self) -> None:
        scale = app.window.get_scale_factor()
        assert self._contact
        surface = self._contact.get_avatar(AvatarSize.CHAT, scale)
        assert isinstance(surface, cairo.ImageSurface)
        self._ui.avatar_image.set_from_surface(surface)

        self._avatar_image_tooltip = ContactTooltip()

    def _on_query_tooltip(self,
                          _img: Gtk.Image,
                          _x_coord: int,
                          _y_coord: int,
                          _keyboard_mode: bool,
                          tooltip: Gtk.Tooltip) -> bool:
        if not isinstance(self._contact, BareContact):
            return False
        res, widget = self._avatar_image_tooltip.get_tooltip(self._contact)
        tooltip.set_custom(widget)
        return res

    def _update_visitor_button(self) -> None:
        if not isinstance(self._contact, GroupchatContact):
            self._ui.visitor_box.set_visible(False)
            return

        if self._contact.is_not_joined:
            self._ui.visitor_box.set_visible(False)
            return

        self_contact = self._contact.get_self()
        assert self_contact is not None
        self._ui.visitor_box.set_visible(self_contact.role.is_visitor)

    def _update_name_label(self) -> None:
        assert self._contact is not None

        name = self._get_name_from_contact(self._contact)

        chatstate = ''
        if app.settings.get('show_chatstate_in_banner'):
            chatstate = self._contact.chatstate_string

        label_text = f'<span>{GLib.markup_escape_text(name)}</span>'
        if chatstate:
            escaped_chatstate = GLib.markup_escape_text(chatstate)
            label_markup = '<span size="60%" weight="light"> {}</span>'
            label_text += label_markup.format(escaped_chatstate)

        self._ui.name_label.set_markup(label_text)

        tooltip_text = name
        if chatstate:
            tooltip_text = f'{name} {chatstate}'

        self._ui.name_label.set_tooltip_text(tooltip_text)

    def _update_description_label(self) -> None:
        contact = self._contact
        assert contact is not None

        if contact.is_groupchat:
            disco_info = app.storage.cache.get_last_disco_info(contact.jid)
            if disco_info is None:
                text = ''
            else:
                text = disco_info.muc_description or ''
        else:
            assert not isinstance(contact, GroupchatContact)
            text = contact.status or ''
        self._ui.description_label.set_text(text)
        self._ui.description_label.set_visible(bool(text))

    def _update_account_badge(self) -> None:
        if self._contact is None:
            self._account_badge.set_visible(False)
            return

        visible = len(app.settings.get_active_accounts()) > 1
        if visible:
            self._account_badge.set_account(self._contact.account)

        self._account_badge.set_visible(visible)

    def _update_share_box(self) -> None:
        assert self._contact is not None
        self._ui.share_menu_button.set_sensitive(
            not self._contact.is_pm_contact)
        self._ui.jid_label.set_text(str(self._contact.jid))

    def _get_share_uri(self) -> str:
        assert self._client is not None
        assert self._contact is not None
        jid = self._contact.get_address()
        if self._contact.is_groupchat:
            return jid.to_iri(XmppUriQuery.JOIN.value)
        else:
            return self._client.get_module('OMEMO').compose_trust_uri(jid)

    def _on_share_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        if self._contact.is_groupchat:
            share_text = _('Scan this QR code to join %s.')
        else:
            share_text = _('Scan this QR code to start a chat with %s.')
        self._ui.share_instructions.set_text(share_text % self._contact.name)

        # Generate QR code on demand (i.e. not when switching chats)
        self._ui.qr_code_image.set_from_pixbuf(
            generate_qr_code(self._get_share_uri()))

    def _on_copy_jid_clicked(self, _button: Gtk.Button) -> None:
        text = self._get_share_uri()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        self._ui.share_popover.popdown()

    def _on_request_voice_clicked(self, _button: Gtk.Button) -> None:
        self._ui.visitor_popover.popdown()
        app.window.activate_action('muc-request-voice', None)

    def _on_toggle_roster_clicked(self, _button: Gtk.Button) -> None:
        state = app.settings.get('hide_groupchat_occupants_list')
        app.settings.set('hide_groupchat_occupants_list', not state)

    def _set_toggle_roster_button_icon(self,
                                       hide_roster: bool,
                                       *args: Any) -> None:

        icon = 'go-next-symbolic' if not hide_roster else 'go-previous-symbolic'
        self._ui.toggle_roster_image.set_from_icon_name(
            icon, Gtk.IconSize.BUTTON)

    @staticmethod
    def _get_name_from_contact(contact: types.ChatContactT) -> str:
        name = contact.name

        if isinstance(contact, BareContact):
            if contact.is_self:
                return _('Note to myself')
            return name

        if isinstance(contact, GroupchatParticipant):
            return f'{name} ({contact.room.name})'

        return name
