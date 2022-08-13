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

from gi.repository import Gtk

import cairo

from nbxmpp.structs import PresenceProperties

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.events import AccountEnabled
from gajim.common.events import BookmarksReceived
from gajim.common.events import MessageReceived
from gajim.common.events import MucDiscoUpdate
from gajim.common.ged import EventHelper
from gajim.common.helpers import get_uf_chatstate
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from .builder import get_builder
from .util import AccountBadge


class ChatBanner(Gtk.Box, EventHelper):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self._client: Optional[types.Client] = None
        self._contact: Optional[types.ChatContactT] = None

        self._ui = get_builder('chat_banner.ui')
        self.add(self._ui.banner_box)
        self._ui.connect_signals(self)

        self._account_badge: Optional[AccountBadge] = None

        hide_roster = app.settings.get('hide_groupchat_occupants_list')
        self._set_toggle_roster_button_icon(hide_roster)
        app.settings.connect_signal(
            'hide_groupchat_occupants_list',
            self._set_toggle_roster_button_icon)

        self.show_all()

    def clear(self) -> None:
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)
            self._contact = None

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)
            self._client = None

        self.unregister_events()

        self._contact = None
        self._client = None

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self._update_account_badge(contact.account)

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)

        self._client = app.get_client(contact.account)
        self._client.connect_signal('state-changed',
                                    self._on_client_state_changed)

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = contact
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
                'state-changed': self._on_muc_state_changed
            })
            self._ui.toggle_roster_button.show()
            hide_banner = app.settings.get('hide_groupchat_banner')
        else:
            self._ui.toggle_roster_button.hide()
            hide_banner = app.settings.get('hide_chat_banner')

        if isinstance(self._contact, GroupchatParticipant):
            self._contact.multi_connect({
                'user-joined': self._on_user_state_changed,
                'user-left': self._on_user_state_changed,
                'user-avatar-update': self._on_user_avatar_update,
            })

        self.register_events([
            ('message-received', ged.GUI1, self._on_message_received),
            ('bookmarks-received', ged.GUI1, self._on_bookmarks_received),
            ('muc-disco-update', ged.GUI1, self._on_muc_disco_update),
            ('account-enabled', ged.GUI2, self._on_account_changed),
            ('account-disabled', ged.GUI2, self._on_account_changed)
        ])

        self._ui.phone_image.set_visible(False)

        if hide_banner:
            self.set_no_show_all(True)
            self.hide()
        else:
            self.set_no_show_all(False)
            self.show_all()

        self._update_avatar()
        self._update_content()

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: SimpleClientState):
        self._update_avatar()
        self._update_content()

    def _on_presence_update(self,
                            _contact: types.BareContact,
                            _signal_name: str
                            ) -> None:
        self._update_avatar()

    def _on_chatstate_update(self,
                             _contact: types.BareContact,
                             _signal_name: str
                             ) -> None:
        self._update_content()

    def _on_nickname_update(self,
                            _contact: types.BareContact,
                            _signal_name: str
                            ) -> None:
        self._update_content()

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

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:
        if contact.is_joined:
            self._update_content()

    def _on_user_role_changed(self,
                              _contact: GroupchatContact,
                              _signal_name: str,
                              user_contact: GroupchatParticipant,
                              properties: PresenceProperties
                              ) -> None:
        self._update_content()

    def _on_user_state_changed(self, *args: Any) -> None:
        self._update_avatar()

    def _on_user_avatar_update(self, *args: Any) -> None:
        self._update_avatar()

    def _on_bookmarks_received(self, _event: BookmarksReceived) -> None:
        self._update_content()

    def _on_muc_disco_update(self, event: MucDiscoUpdate) -> None:
        if self._contact is None or event.jid != self._contact.jid:
            return

        self._update_content()

    def _on_account_changed(self, event: AccountEnabled) -> None:
        if self._contact is None:
            return

        self._update_account_badge(self._contact.account)

    def _on_message_received(self, event: MessageReceived) -> None:
        if (not isinstance(self._contact, BareContact) or
                event.jid != self._contact.jid or
                not event.msgtxt or
                event.properties.is_sent_carbon or
                event.resource is None):
            return

        resource_contact = self._contact.get_resource(event.resource)
        self._ui.phone_image.set_visible(resource_contact.is_phone)

    def _update_avatar(self) -> None:
        scale = app.window.get_scale_factor()
        assert self._contact
        surface = self._contact.get_avatar(AvatarSize.CHAT, scale)
        assert isinstance(surface, cairo.Surface)
        self._ui.avatar_image.set_from_surface(surface)

    def _update_content(self) -> None:
        if self._client is None or self._contact is None:
            return

        name = self._contact.name

        if self._contact.jid.bare_match(self._client.get_own_jid()):
            name = _('Note to myself')

        if self._contact.is_pm_contact:
            gc_contact = self._client.get_module('Contacts').get_contact(
                self._contact.jid.bare)
            name = f'{name} ({gc_contact.name})'

        label_text = f'<span>{name}</span>'
        label_tooltip = name
        show_chatstate = app.settings.get('show_chatstate_in_banner')
        if (show_chatstate and isinstance(
                self._contact, (BareContact, GroupchatParticipant))):
            chatstate = self._contact.chatstate
            if chatstate is not None:
                chatstate = get_uf_chatstate(chatstate.value)
            else:
                chatstate = ''

            label_text = f'<span>{name}</span>' \
                         f'<span size="60%" weight="light">' \
                         f' {chatstate}</span>'
            label_tooltip = f'{name} {chatstate}'

        self._ui.name_label.set_markup(label_text)
        self._ui.name_label.set_tooltip_text(label_tooltip)

        if isinstance(self._contact, GroupchatContact):
            self_contact = self._contact.get_self()
            if self_contact:
                self._ui.visitor_box.set_visible(self_contact.role.is_visitor)

    def _update_account_badge(self, account: str) -> None:
        if self._account_badge is not None:
            self._account_badge.destroy()

        enabled_accounts = app.get_enabled_accounts_with_labels()
        if len(enabled_accounts) > 1:
            self._account_badge = AccountBadge(account)
            self._ui.account_badge_box.add(self._account_badge)

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
