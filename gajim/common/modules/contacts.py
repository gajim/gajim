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

from __future__ import annotations

from typing import Any
from typing import Iterator
from typing import Optional
from typing import Union
from typing import overload

import cairo
from nbxmpp.const import Affiliation
from nbxmpp.const import Chatstate
from nbxmpp.const import Role
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import LocationData
from nbxmpp.structs import TuneData
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common import types
from gajim.common.const import PresenceShowExt
from gajim.common.const import SimpleClientState
from gajim.common.setting_values import BoolContactSettings
from gajim.common.setting_values import StringContactSettings
from gajim.common.setting_values import BoolGroupChatSettings
from gajim.common.setting_values import IntGroupChatSettings
from gajim.common.setting_values import StringGroupChatSettings
from gajim.common.structs import UNKNOWN_PRESENCE
from gajim.common.structs import PresenceData
from gajim.common.structs import UNKNOWN_MUC_PRESENCE
from gajim.common.structs import MUCPresenceData
from gajim.common.helpers import Observable
from gajim.common.helpers import chatstate_to_string
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import LogAdapter
from gajim.common.helpers import get_groupchat_name


class ContactSettings:
    def __init__(self, account: str, jid: JID) -> None:
        self._account = account
        self._jid = jid

    @overload
    def get(self, setting: StringContactSettings) -> str: ...  # noqa: E704
    @overload
    def get(self, setting: BoolContactSettings) -> bool: ...  # noqa: E704

    def get(self, setting: Any) -> Any:
        return app.settings.get_contact_setting(
            self._account, self._jid, setting)

    @overload
    def set(self, setting: StringContactSettings, value: str) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: BoolContactSettings, value: bool) -> None: ...  # noqa: E501, E704

    def set(self, setting: Any, value: Any) -> None:
        app.settings.set_contact_setting(
            self._account, self._jid, setting, value)


class GroupChatSettings:
    def __init__(self, account: str, jid: JID) -> None:
        self._account = account
        self._jid = jid

    @overload
    def get(self, setting: StringGroupChatSettings) -> str: ...  # noqa: E704
    @overload
    def get(self, setting: BoolGroupChatSettings) -> bool: ...  # noqa: E704
    @overload
    def get(self, setting: IntGroupChatSettings) -> int: ...  # noqa: E704

    def get(self, setting: Any) -> Any:
        return app.settings.get_group_chat_setting(
            self._account, self._jid, setting)

    @overload
    def set(self, setting: StringGroupChatSettings, value: str) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: BoolGroupChatSettings, value: bool) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: IntGroupChatSettings, value: int) -> None: ...  # noqa: E501, E704

    def set(self, setting: Any, value: Any) -> None:
        app.settings.set_group_chat_setting(
            self._account, self._jid, setting, value)


class Contacts(BaseModule):
    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self._contacts: dict[JID, Union[BareContact, GroupchatContact]] = {}
        self._con.connect_signal('state-changed', self._on_client_state_changed)
        self._con.connect_signal('resume-failed', self._on_client_resume_failed)

    def _on_client_resume_failed(self,
                                 _client: types.Client,
                                 _signal_name: str) -> None:
        self._reset_presence()

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: SimpleClientState) -> None:
        if state.is_disconnected:
            self._reset_presence()

    def add_chat_contact(self, jid: Union[str, JID]) -> BareContact:
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        contact = self._contacts.get(jid)
        if contact is not None:
            if not isinstance(contact, BareContact):
                raise ValueError(f'Trying to add BareContact {jid}, '
                                 f'but contact exists already as {contact}')
            return contact

        contact = BareContact(self._log, jid, self._account)

        self._contacts[jid] = contact
        return contact

    def add_group_chat_contact(self, jid: Union[str, JID]) -> GroupchatContact:
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        contact = self._contacts.get(jid)
        if contact is not None:
            if not isinstance(contact, GroupchatContact):
                raise ValueError(f'Trying to add GroupchatContact {jid}, '
                                 f'but contact exists already as {contact}')
            return contact

        contact = GroupchatContact(self._log, jid, self._account)

        self._contacts[jid] = contact
        return contact

    def add_private_contact(self, jid: Union[str, JID]) -> GroupchatParticipant:
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        if jid.resource is None:
            raise ValueError(f'Trying to add a bare JID as private {jid}')

        contact = self._contacts.get(jid.bare)
        if contact is None:
            group_chat_contact = self.add_group_chat_contact(jid.bare)
            return group_chat_contact.add_resource(jid.resource)

        if not isinstance(contact, GroupchatContact):
            raise ValueError(f'Trying to add GroupchatParticipant {jid}, '
                             f'to BareContact {contact}')

        return contact.add_resource(jid.resource)

    def add_contact(self,
                    jid: Union[str, JID],
                    groupchat: bool = False) -> Union[BareContact,
                                                      GroupchatContact]:
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

    def get_contact(self,
                    jid: Union[str, JID],
                    groupchat: bool = False
                    ) -> types.ContactT:

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

    def get_bare_contact(self, jid: Union[str, JID]) -> Union[BareContact,
                                                              GroupchatContact]:
        '''This method gives direct access to the contacts dict.
           This is helpful when performance is essential. In difference to
           get_contact() this method does not create contacts nor can it handle
           JIDs which are not bare. Use this only if you know the contact
           exists.
        '''
        return self._contacts[jid]

    def get_contacts_with_domain(self,
                                 domain: str
                                 ) -> list[Union[BareContact,
                                                 GroupchatContact]]:

        contacts: list[Union[BareContact, GroupchatContact]] = []
        for contact in self._contacts.values():
            if contact.jid.domain == domain:
                contacts.append(contact)
        return contacts

    def _reset_presence(self) -> None:
        for contact in self._contacts.values():
            if contact.is_groupchat or contact.is_pm_contact:
                continue
            assert isinstance(contact, BareContact)
            contact.update_presence(UNKNOWN_PRESENCE)

    def force_chatstate_update(self) -> None:
        for contact in self._contacts.values():
            contact.force_chatstate_update()


class CommonContact(Observable):
    def __init__(self,
                 logger: LogAdapter,
                 jid: JID,
                 account: str
                 ) -> None:

        Observable.__init__(self, logger)
        self._jid = jid
        self._account = account

    def __hash__(self) -> int:
        return hash(f'{self._account}-{self._jid}')

    def __eq__(self, obj: object) -> bool:
        if not isinstance(obj, CommonContact):
            return NotImplemented

        return (self._account == obj.account and
                obj._jid == self._jid)

    def _module(self, name: str) -> BaseModule:
        return app.get_client(self._account).get_module(name)

    @property
    def jid(self) -> JID:
        return self._jid

    @property
    def account(self) -> str:
        return self._account

    def _on_signal(self,
                   _contact: Union[BareContact,
                                   ResourceContact,
                                   GroupchatContact,
                                   GroupchatParticipant],
                   signal_name: str,
                   *args: Any,
                   **kwargs: Any
                   ) -> None:
        self.notify(signal_name, *args, **kwargs)

    def supports(self, requested_feature: str) -> bool:
        return self._supports(self._jid, requested_feature)

    @staticmethod
    def _supports(jid: JID, requested_feature: str) -> bool:
        disco_info = app.storage.cache.get_last_disco_info(jid)
        if disco_info is None:
            return False

        return disco_info.supports(requested_feature)

    @property
    def is_chat(self) -> bool:
        return False

    @property
    def is_groupchat(self) -> bool:
        return False

    @property
    def is_pm_contact(self) -> bool:
        return False

    @property
    def type_string(self) -> str:
        raise NotImplementedError

    @property
    def is_jingle_available(self) -> bool:
        return False

    def get_address(self, _prefer_real: bool = True) -> JID:
        return self._jid

    @property
    def chatstate(self) -> Optional[Chatstate]:
        return None

    @property
    def chatstate_string(self) -> str:
        return chatstate_to_string(self.chatstate)

    def __repr__(self) -> str:
        return f'{self.jid} ({self._account})'


class BareContact(CommonContact):
    def __init__(self, logger: LogAdapter, jid: JID, account: str) -> None:
        CommonContact.__init__(self, logger, jid, account)

        self.settings = ContactSettings(account, jid)
        self._resources: dict[str, ResourceContact] = {}

        self._avatar_sha = app.storage.cache.get_contact(jid, 'avatar')

    @property
    def is_self(self):
        own_jid = app.get_client(self._account).get_own_jid().new_as_bare()
        return own_jid == self.jid

    def supports(self, requested_feature: str) -> bool:
        for resource in self.iter_resources():
            if resource.supports(requested_feature):
                return True
        return False

    def supports_audio(self) -> bool:
        if (self.supports(Namespace.JINGLE_ICE_UDP) and
                app.is_installed('FARSTREAM')):
            return self.supports(Namespace.JINGLE_RTP_AUDIO)
        return False

    def supports_video(self) -> bool:
        if (self.supports(Namespace.JINGLE_ICE_UDP) and
                app.is_installed('FARSTREAM')):
            return self.supports(Namespace.JINGLE_RTP_VIDEO)
        return False

    def add_resource(self, resource: str) -> ResourceContact:
        assert resource is not None
        # Check if resource is not None because not the whole
        # codebase is type checked and it creates hard to track
        # problems if we create a ResourceContact without resource

        jid = self._jid.new_with(resource=resource)
        assert isinstance(self._log, LogAdapter)
        contact = ResourceContact(self._log, jid, self._account)
        self._resources[resource] = contact
        contact.connect('presence-update', self._on_signal)
        contact.connect('chatstate-update', self._on_signal)
        contact.connect('nickname-update', self._on_signal)
        contact.connect('caps-update', self._on_signal)
        return contact

    def get_resource(self, resource: str) -> ResourceContact:
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    def get_resources(self) -> list[ResourceContact]:
        resources: list[ResourceContact] = []
        for contact in self._resources.values():
            if contact.is_available:
                resources.append(contact)
        return resources

    def iter_resources(self) -> Iterator[ResourceContact]:
        for contact in self._resources.values():
            if contact.is_available:
                yield contact

    @property
    def is_available(self) -> bool:
        # pylint: disable=R1729
        return any([contact.is_available for contact
                    in self._resources.values()])

    @property
    def show(self):
        show_values = [contact.show for contact in self._resources.values()]
        if not show_values:
            return PresenceShowExt.OFFLINE
        return max(show_values)

    @property
    def chatstate(self) -> Optional[Chatstate]:
        chatstates = {contact.chatstate for contact in self._resources.values()}
        chatstates.discard(None)
        if not chatstates:
            return None
        return min(chatstates)

    def force_chatstate_update(self) -> None:
        for contact in self._resources.values():
            contact.notify('chatstate-update')

    @property
    def name(self) -> str:
        item = self._module('Roster').get_item(self._jid)
        if item is not None and item.name:
            return item.name

        nickname = app.storage.cache.get_contact(self._jid, 'nickname')
        if nickname:
            return nickname
        if self._jid.is_domain:
            assert self._jid.domain is not None
            return self._jid.domain

        assert self._jid.localpart is not None
        return self._jid.localpart

    def get_tune(self) -> Optional[TuneData]:
        return self._module('UserTune').get_contact_tune(self._jid)

    def get_location(self) -> Optional[LocationData]:
        return self._module('UserLocation').get_contact_location(self._jid)

    @property
    def avatar_sha(self) -> Optional[str]:
        return app.storage.cache.get_contact(self._jid, 'avatar')

    def get_avatar(self,
                   size: int,
                   scale: int,
                   add_show: bool = True,
                   default: bool = False,
                   style: str = 'circle'):

        show = self.show.value if add_show else None

        transport_icon = None
        if self.is_gateway:
            disco_info = app.storage.cache.get_last_disco_info(self._jid)
            if disco_info is not None:
                if disco_info.gateway_type == 'sms':
                    transport_icon = 'gajim-agent-sms'
                if disco_info.gateway_type == 'irc':
                    transport_icon = 'gajim-agent-irc'
        else:
            for resource_contact in self.iter_resources():
                if resource_contact.identity_type == 'sms':
                    transport_icon = 'gajim-agent-sms'
                    break

        if self.avatar_sha is not None:
            transport_icon = None

        return app.app.avatar_storage.get_surface(
            self,
            size,
            scale,
            show,
            default=default,
            transport_icon=transport_icon,
            style=style)

    def update_presence(self, presence_data: PresenceData) -> None:
        for contact in self._resources.values():
            contact.update_presence(presence_data, notify=False)
        self.notify('presence-update')

    def update_avatar(self, sha: str) -> None:
        if self._avatar_sha == sha:
            return

        self._avatar_sha = sha

        app.storage.cache.set_contact(self._jid, 'avatar', sha)
        app.app.avatar_storage.invalidate_cache(self._jid)
        self.notify('avatar-update')

    @property
    def is_in_roster(self) -> bool:
        item = self._module('Roster').get_item(self._jid)
        return item is not None

    @property
    def is_gateway(self) -> bool:
        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        if disco_info is None:
            return False
        return disco_info.is_gateway

    @property
    def ask(self) -> Optional[str]:
        item = self._module('Roster').get_item(self._jid)
        if item is None:
            return None
        return item.ask

    @property
    def subscription(self) -> Optional[str]:
        item = self._module('Roster').get_item(self._jid)
        if item is None:
            return None
        return item.subscription

    @property
    def groups(self) -> set[str]:
        item = self._module('Roster').get_item(self._jid)
        if item is None:
            return set()
        return item.groups

    @property
    def is_subscribed(self) -> bool:
        return self.subscription in ('from', 'both')

    @property
    def is_blocked(self) -> bool:
        return self._module('Blocking').is_blocked(self._jid)

    def set_blocked(self) -> None:
        self.update_presence(UNKNOWN_PRESENCE)
        self.notify('blocking-update')

    def set_unblocked(self) -> None:
        self.notify('blocking-update')

    @property
    def is_jingle_available(self) -> bool:
        if not self.supports(Namespace.JINGLE_FILE_TRANSFER_5):
            return False
        return self.is_available

    @property
    def is_chat(self) -> bool:
        return True

    @property
    def type_string(self) -> str:
        return 'chat'


class ResourceContact(CommonContact):
    def __init__(self, logger: LogAdapter, jid: JID, account: str) -> None:
        CommonContact.__init__(self, logger, jid, account)

        self._presence = UNKNOWN_PRESENCE

    def supports(self, requested_feature: str) -> bool:
        if not self.is_available:
            return False
        return CommonContact.supports(self, requested_feature)

    @property
    def resource(self) -> str:
        assert self._jid.resource is not None
        return self._jid.resource

    @property
    def identity_type(self) -> Optional[str]:
        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        if disco_info is None:
            return None

        for identity in disco_info.identities:
            if identity.type is not None:
                return identity.type

        return None

    @property
    def is_phone(self):
        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        if disco_info is None:
            return False

        for identity in disco_info.identities:
            if identity.type == 'phone':
                return True
        return False

    @property
    def is_available(self) -> bool:
        return self._presence.available

    @property
    def show(self):
        if not self._presence.available:
            return PresenceShowExt.OFFLINE
        return self._presence.show

    @property
    def status(self) -> str:
        return self._presence.status

    @property
    def priority(self) -> int:
        return self._presence.priority

    @property
    def idle_time(self) -> Optional[float]:
        return self._presence.idle_time

    @property
    def chatstate(self) -> Chatstate:
        return self._module('Chatstate').get_remote_chatstate(self._jid)

    def update_presence(self,
                        presence_data: PresenceData,
                        notify: bool = True
                        ) -> None:
        self._presence = presence_data
        if notify:
            self.notify('presence-update')

    @property
    def type_string(self) -> str:
        raise NotImplementedError


class GroupchatContact(CommonContact):
    def __init__(self, logger: LogAdapter, jid: JID, account: str) -> None:
        CommonContact.__init__(self, logger, jid, account)

        self.settings = GroupChatSettings(account, jid)
        self._resources: dict[str, GroupchatParticipant] = {}

    @property
    def is_groupchat(self) -> bool:
        return True

    @property
    def is_irc(self) -> bool:
        disco_info = self.get_disco()
        if disco_info is None:
            return False
        return disco_info.is_irc

    @property
    def muc_context(self) -> Optional[str]:
        disco_info = self.get_disco()
        if disco_info is None:
            return None

        if disco_info.muc_is_members_only and disco_info.muc_is_nonanonymous:
            return 'private'
        return 'public'

    @property
    def encryption_available(self) -> bool:
        disco_info = self.get_disco()
        if disco_info is None:
            return True

        return (disco_info.muc_is_members_only and
                disco_info.muc_is_nonanonymous)

    def get_config_value(self, field_name: str) -> Any:
        disco_info = self.get_disco()
        assert disco_info is not None
        return disco_info.get_field_value(Namespace.MUC_INFO, field_name)

    def add_resource(self, resource: str) -> GroupchatParticipant:
        assert resource is not None
        # Check if resource is not None because not the whole
        # codebase is type checked and it creates hard to track
        # problems if we create a GroupchatParticipant without resource

        contact = self._resources.get(resource)
        if contact is not None:
            return contact

        jid = self._jid.new_with(resource=resource)
        assert isinstance(self._log, LogAdapter)
        contact = GroupchatParticipant(self._log, jid, self._account)
        self._resources[resource] = contact
        contact.connect('user-joined', self._on_user_signal)
        contact.connect('user-left', self._on_user_signal)
        contact.connect('user-affiliation-changed', self._on_user_signal)
        contact.connect('user-role-changed', self._on_user_signal)
        contact.connect('user-status-show-changed', self._on_user_signal)
        contact.connect('user-avatar-update', self._on_user_signal)
        return contact

    def get_resource(self, resource: str) -> GroupchatParticipant:
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    def get_participants(self) -> Iterator[GroupchatParticipant]:
        for contact in self._resources.values():
            if contact.is_available:
                yield contact

    @property
    def name(self) -> str:
        client = app.get_client(self._account)
        return get_groupchat_name(client, self._jid)

    @property
    def avatar_sha(self) -> Optional[str]:
        return app.storage.cache.get_muc(self._jid, 'avatar')

    def get_avatar(self, size: int, scale: int) -> Optional[cairo.ImageSurface]:
        transport_icon = None
        disco_info = self.get_disco()
        if disco_info is not None:
            for identity in disco_info.identities:
                if identity.type == 'irc':
                    transport_icon = 'gajim-agent-irc'
                break
        return app.app.avatar_storage.get_muc_surface(
            self._account,
            self._jid,
            size,
            scale,
            transport_icon=transport_icon)

    def _on_user_signal(self,
                        contact: GroupchatParticipant,
                        signal_name: str, *args: Any
                        ) -> None:
        self.notify(signal_name, contact, *args)

    def update_avatar(self, *args: Any) -> None:
        app.app.avatar_storage.invalidate_cache(self._jid)
        self.notify('avatar-update')

    def force_chatstate_update(self) -> None:
        for contact in self._resources.values():
            contact.notify('chatstate-update')

    def get_self(self) -> Optional[GroupchatParticipant]:
        nick = self.nickname
        if nick is None:
            return None
        return self.get_resource(nick)

    @property
    def nickname(self) -> Optional[str]:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.nick

    @property
    def occupant_jid(self) -> Optional[JID]:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.occupant_jid

    @property
    def subject(self) -> Optional[MucSubject]:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.subject

    @property
    def is_joined(self) -> bool:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joined

    @property
    def is_joining(self) -> bool:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joining

    @property
    def is_not_joined(self) -> bool:
        muc_data = self._module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return True
        return muc_data.state.is_not_joined

    def set_not_joined(self) -> None:
        for contact in self._resources.values():
            contact.update_presence(UNKNOWN_MUC_PRESENCE)

    def get_user_nicknames(self) -> list[str]:
        client = app.get_client(self._account)
        return client.get_module('MUC').get_joined_users(self._jid)

    def get_disco(self, max_age: int = 0) -> Optional[DiscoInfo]:
        return app.storage.cache.get_last_disco_info(self.jid, max_age=max_age)

    def can_notify(self) -> bool:
        all_ = app.settings.get('notify_on_all_muc_messages')
        room = self.settings.get('notify_on_all_messages')
        return all_ or room

    @property
    def type_string(self) -> str:
        return 'groupchat'


class GroupchatParticipant(CommonContact):
    def __init__(self, logger: LogAdapter, jid: JID, account: str) -> None:
        CommonContact.__init__(self, logger, jid, account)

        self.settings = ContactSettings(account, jid)

        self._client = app.get_client(self._account)

        self._presence = UNKNOWN_MUC_PRESENCE

    @property
    def resource(self) -> str:
        assert self._jid.resource is not None
        return self._jid.resource

    def get_address(self, prefer_real: bool = True) -> JID:
        jid = self._presence.real_jid
        if jid is None or not prefer_real:
            return self._jid
        return jid

    def supports(self, requested_feature: str) -> bool:
        if not self.is_available:
            return False
        return CommonContact.supports(self, requested_feature)

    @property
    def is_pm_contact(self) -> bool:
        return True

    @property
    def is_in_roster(self) -> bool:
        return False

    @property
    def room(self) -> GroupchatContact:
        return self._module('Contacts').get_bare_contact(self.jid.bare)

    @property
    def presence(self) -> MUCPresenceData:
        return self._presence

    def set_presence(self, presence: MUCPresenceData) -> None:
        self._presence = presence

    @property
    def is_available(self) -> bool:
        return self._presence.available

    @property
    def show(self):
        if not self._presence.available:
            return PresenceShowExt.OFFLINE
        return self._presence.show

    @property
    def status(self) -> str:
        return self._presence.status

    @property
    def idle_time(self) -> Optional[float]:
        return self._presence.idle_time

    @property
    def name(self) -> str:
        assert self._jid.resource is not None
        return self._jid.resource

    @property
    def real_jid(self) -> Optional[JID]:
        return self._presence.real_jid

    def get_real_contact(self) -> Optional[BareContact]:
        jid = self._presence.real_jid
        if jid is None:
            return None
        return self._client.get_module('Contacts').get_contact(
            jid.new_as_bare())

    @property
    def affiliation(self) -> Affiliation:
        return self._presence.affiliation

    @property
    def role(self) -> Role:
        return self._presence.role

    @property
    def chatstate(self) -> Chatstate:
        return self._module('Chatstate').get_remote_chatstate(self._jid)

    @property
    def avatar_sha(self) -> str:
        return self._client.get_module('VCardAvatars').get_avatar_sha(self._jid)

    def get_avatar(self,
                   size: int,
                   scale: int,
                   add_show: bool = True,
                   style: str = 'circle'
                   ) -> cairo.ImageSurface:

        show = self.show.value if add_show else None
        return app.app.avatar_storage.get_surface(
            self, size, scale, show, style=style)

    def update_presence(self, presence: MUCPresenceData) -> None:
        self._presence = presence

    def update_avatar(self, *args: Any) -> None:
        app.app.avatar_storage.invalidate_cache(self._jid)
        self.notify('user-avatar-update')

    @property
    def type_string(self) -> str:
        return 'pm'


def can_add_to_roster(contact: Union[BareContact,
                                     GroupchatContact,
                                     GroupchatParticipant]) -> bool:

    if isinstance(contact, GroupchatContact):
        return False

    if isinstance(contact, GroupchatParticipant):
        return contact.real_jid is not None

    if contact.is_self:
        return False
    return not contact.is_in_roster
