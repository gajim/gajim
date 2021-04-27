# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import Dict  # pylint: disable=unused-import
from typing import Tuple

from functools import partial

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import PresenceShowExt
from gajim.common.structs import UNKNOWN_PRESENCE
from gajim.common.structs import UNKNOWN_MUC_PRESENCE
from gajim.common.helpers import Observable
from gajim.common.types import ConnectionT
from gajim.common.modules.base import BaseModule
from gajim.common.helpers import get_groupchat_name


class ContactSettings:
    def __init__(self, account, jid):
        self.get = partial(app.settings.get_contact_setting, account, jid)
        self.set = partial(app.settings.set_contact_setting, account, jid)


class GroupChatSettings:
    def __init__(self, account, jid):
        self.get = partial(app.settings.get_group_chat_setting, account, jid)
        self.set = partial(app.settings.set_group_chat_setting, account, jid)


class Contacts(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self._contacts = {}
        self._con.connect_signal('state-changed', self._on_client_state_changed)
        self._con.connect_signal('resume-failed', self._on_client_resume_failed)

    def _on_client_resume_failed(self, _client, _signal_name):
        self._reset_presence()

    def _on_client_state_changed(self, _client, _signal_name, state):
        if state.is_disconnected:
            self._reset_presence()

    def add_contact(self, jid, groupchat=False):
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        contact = self._contacts.get(jid)
        if contact is not None:
            return contact

        if groupchat:
            contact = GroupchatContact(self._log, jid, self._account)
        else:
            contact = BareContact(self._log, jid, self._account)

        self._contacts[jid] = contact
        return contact

    def get_contact(self, jid, groupchat=False):
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        resource = jid.resource
        jid = jid.new_as_bare()

        contact = self._contacts.get(jid)
        if contact is None:
            contact = self.add_contact(jid, groupchat=groupchat)

        if resource is None:
            return contact

        contact = contact.get_resource(resource)
        return contact

    def get_group_chat_contact(self, jid):
        return self.get_contact(jid, groupchat=True)

    def get_contacts_with_domain(self, domain):
        contacts = []
        for contact in self._contacts.values():
            if contact.jid.domain == domain:
                contacts.append(contact)
        return contacts

    def _reset_presence(self):
        for contact in self._contacts.values():
            if contact.is_groupchat or contact.is_pm_contact:
                continue
            contact.update_presence(UNKNOWN_PRESENCE)

    def force_chatstate_update(self):
        for contact in self._contacts.values():
            contact.force_chatstate_update()


class CommonContact(Observable):
    def __init__(self, logger, jid, account):
        Observable.__init__(self, logger)
        self._jid = jid
        self._account = account

        self._resources = {}

    def _module(self, name):
        return app.get_client(self._account).get_module(name)

    @property
    def jid(self):
        return self._jid

    @property
    def account(self):
        return self._account

    def _on_signal(self, _contact, signal_name, *args, **kwargs):
        self.notify(signal_name, *args, **kwargs)

    def supports(self, requested_feature):
        if not self.is_available:
            return False

        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        if disco_info is None:
            return False

        return disco_info.supports(requested_feature)

    @property
    def is_groupchat(self):
        return False

    @property
    def is_pm_contact(self):
        return False

    def force_chatstate_update(self):
        for contact in self._resources.values():
            contact.notify('chatstate-update')

    def __repr__(self):
        return f'{self.jid} ({self._account})'


class BareContact(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self.settings = ContactSettings(account, str(jid))

        self._avatar_sha = app.storage.cache.get_contact(jid, 'avatar')

    def add_resource(self, resource):
        jid = self._jid.new_with(resource=resource)
        contact = ResourceContact(self._log, jid, self._account)
        self._resources[resource] = contact
        contact.connect('presence-update', self._on_signal)
        contact.connect('chatstate-update', self._on_signal)
        contact.connect('nickname-update', self._on_signal)
        return contact

    def get_resource(self, resource):
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    def get_resources(self):
        resources = []
        for contact in self._resources.values():
            if contact.show != PresenceShowExt.OFFLINE:
                resources.append(contact)
        return resources

    def iter_resources(self):
        for contact in self._resources.values():
            if contact.show != PresenceShowExt.OFFLINE:
                yield contact

    @property
    def is_available(self):
        return any([contact.is_available for contact
                    in self._resources.values()])

    @property
    def show(self):
        show_values = [contact.show for contact in self._resources.values()]
        if not show_values:
            return PresenceShowExt.OFFLINE
        return max(show_values)

    @property
    def chatstate(self):
        chatstates = {contact.chatstate for contact in self._resources.values()}
        chatstates.discard(None)
        if not chatstates:
            return None
        return min(chatstates)

    @property
    def name(self):
        roster_name = self._get_roster_attr('name')
        if roster_name:
            return roster_name
        nickname = app.storage.cache.get_contact(self._jid, 'nickname')
        if nickname:
            return nickname
        return self._jid.localpart

    @property
    def avatar_sha(self):
        return app.storage.cache.get_contact(self._jid, 'avatar')

    def get_avatar(self,
                   size,
                   scale,
                   add_show=True,
                   pixbuf=False,
                   default=False,
                   style='circle'):

        show = self.show if add_show else None

        if pixbuf:
            return app.interface.avatar_storage.get_pixbuf(
                self, size, scale, show, default=default, style=style)
        return app.interface.avatar_storage.get_surface(
            self, size, scale, show, default=default, style=style)

    def update_presence(self, presence_data):
        for contact in self._resources.values():
            contact.update_presence(presence_data, notify=False)
        self.notify('presence-update')

    def update_avatar(self, sha):
        if self._avatar_sha == sha:
            return

        self._avatar_sha = sha

        app.storage.cache.set_contact(self._jid, 'avatar', sha)
        app.interface.avatar_storage.invalidate_cache(self._jid)
        self.notify('avatar-update')

    def _get_roster_attr(self, attr):
        item = self._module('Roster').get_item(self._jid)
        if item is None:
            return None
        return getattr(item, attr)

    @property
    def is_in_roster(self):
        item = self._module('Roster').get_item(self._jid)
        return item is not None

    @property
    def ask(self):
        return self._get_roster_attr('ask')

    @property
    def subscription(self):
        return self._get_roster_attr('subscription')

    @property
    def groups(self):
        return self._get_roster_attr('groups')

    @property
    def is_subscribed(self):
        return self.subscription in ('from', 'both')

    @property
    def is_blocked(self):
        return self._module('Blocking').is_blocked(self._jid)

    def set_blocked(self):
        self.update_presence(UNKNOWN_PRESENCE)
        self.notify('blocking-update')

    def set_unblocked(self):
        self.notify('blocking-update')


class ResourceContact(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self._presence = UNKNOWN_PRESENCE

    @property
    def is_available(self):
        return self._presence.available

    @property
    def show(self):
        if not self._presence.available:
            return PresenceShowExt.OFFLINE
        return self._presence.show

    @property
    def status(self):
        return self._presence.status

    @property
    def priority(self):
        return self._presence.priority

    @property
    def idle_time(self):
        return self._presence.idle_time

    @property
    def chatstate(self):
        return self._module('Chatstate').get_remote_chatstate(self._jid)

    def update_presence(self, presence_data, notify=True):
        self._presence = presence_data
        if notify:
            self.notify('presence-update')


class GroupchatContact(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self.settings = GroupChatSettings(account, str(jid))

    @property
    def is_groupchat(self):
        return True

    def add_resource(self, resource):
        jid = self._jid.new_with(resource=resource)
        contact = GroupchatParticipant(self._log, jid, self._account)
        self._resources[resource] = contact
        contact.connect('user-joined', self._on_user_signal)
        contact.connect('user-left', self._on_user_signal)
        contact.connect('user-affiliation-changed', self._on_user_signal)
        contact.connect('user-role-changed', self._on_user_signal)
        contact.connect('user-status-show-changed', self._on_user_signal)
        contact.connect('user-avatar-update', self._on_user_signal)
        return contact

    def get_resource(self, resource):
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    @property
    def name(self):
        client = app.get_client(self._account)
        return get_groupchat_name(client, self._jid)

    @property
    def avatar_sha(self):
        return app.storage.cache.get_muc(self._jid, 'avatar')

    def get_avatar(self, size, scale):
        return app.interface.avatar_storage.get_muc_surface(
            self._account,
            self._jid,
            size,
            scale)

    def _on_user_signal(self, contact, signal_name, *args):
        self.notify(signal_name, contact, *args)

    def update_avatar(self, *args):
        app.interface.avatar_storage.invalidate_cache(self._jid)
        self.notify('avatar-update')

    def get_self(self):
        nick = self.nickname
        if nick is None:
            return None
        return self.get_resource(nick)

    @property
    def nickname(self):
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.nick

    @property
    def occupant_jid(self):
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.occupant_jid

    @property
    def is_joined(self):
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joined

    @property
    def is_joining(self):
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joining

    @property
    def is_not_joined(self):
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return True
        return muc_data.state.is_not_joined

    def set_not_joined(self):
        for contact in self._resources.values():
            contact.update_presence(UNKNOWN_MUC_PRESENCE, notify=False)

    def get_user_nicknames(self):
        client = app.get_client(self._account)
        return client.get_module('MUC').get_joined_users(self._jid)


class GroupchatParticipant(CommonContact):
    def __init__(self, logger, jid, account):
        CommonContact.__init__(self, logger, jid, account)

        self.settings = ContactSettings(account, str(jid))

        self._client = app.get_client(self._account)

        self._presence = UNKNOWN_MUC_PRESENCE

    @property
    def is_pm_contact(self):
        return True

    @property
    def is_in_roster(self):
        return False

    @property
    def presence(self):
        return self._presence

    def set_presence(self, presence):
        self._presence = presence

    @property
    def is_available(self):
        return self._presence.available

    @property
    def show(self):
        if not self._presence.available:
            return PresenceShowExt.OFFLINE
        return self._presence.show

    @property
    def status(self):
        return self._presence.status

    @property
    def idle_time(self):
        return self._presence.idle_time

    @property
    def name(self):
        return self._jid.resource

    @property
    def real_jid(self):
        return self._presence.real_jid

    @property
    def affiliation(self):
        return self._presence.affiliation

    @property
    def role(self):
        return self._presence.role

    @property
    def chatstate(self):
        return self._module('Chatstate').get_remote_chatstate(self._jid)

    @property
    def avatar_sha(self):
        return self._client.get_module('VCardAvatars').get_avatar_sha(self._jid)

    def get_avatar(self,
                   size,
                   scale,
                   add_show=True,
                   style='circle'):

        show = self.show if add_show else None
        return app.interface.avatar_storage.get_surface(
            self, size, scale, show, style=style)

    def update_presence(self, presence, *args, notify=True):
        if not notify:
            self._presence = presence
            return

        if not self._presence.available and presence.available:
            self._presence = presence
            self.notify('user-joined', *args)
            return

        if not presence.available:
            self._presence = presence
            self.notify('user-left', *args)
            return

        signals = []
        if self._presence.affiliation != presence.affiliation:
            signals.append('user-affiliation-changed')

        if self._presence.role != presence.role:
            signals.append('user-role-changed')

        if (self._presence.status != presence.status or
                self._presence.show != presence.show):
            signals.append('user-status-show-changed')

        self._presence = presence
        for signal in signals:
            self.notify(signal, *args)

    def set_state(self, state, presence):
        self._presence = presence
        self.notify(state)

    def update_avatar(self, *args):
        app.interface.avatar_storage.invalidate_cache(self._jid)
        self.notify('user-avatar-update')


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Contacts, str]:
    return Contacts(*args, **kwargs), 'Contacts'
