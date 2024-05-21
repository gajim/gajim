# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import operator
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

import cairo
from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import Chatstate
from nbxmpp.const import PresenceShow
from nbxmpp.const import Role
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import LocationData
from nbxmpp.structs import MucSubject
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common import types
from gajim.common.client_modules import ClientModules
from gajim.common.const import PresenceShowExt
from gajim.common.const import SimpleClientState
from gajim.common.helpers import chatstate_to_string
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import Observable
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import LogAdapter
from gajim.common.setting_values import AllContactSettings
from gajim.common.setting_values import AllContactSettingsT
from gajim.common.setting_values import AllGroupChatSettings
from gajim.common.setting_values import AllGroupChatSettingsT
from gajim.common.setting_values import BoolContactSettings
from gajim.common.setting_values import BoolGroupChatSettings
from gajim.common.setting_values import IntGroupChatSettings
from gajim.common.setting_values import StringContactSettings
from gajim.common.setting_values import StringGroupChatSettings
from gajim.common.structs import MUCPresenceData
from gajim.common.structs import PresenceData
from gajim.common.structs import UNKNOWN_MUC_PRESENCE
from gajim.common.structs import UNKNOWN_PRESENCE


class ContactSettings:
    def __init__(self, account: str, jid: JID) -> None:
        self._account = account
        self._jid = jid

    @overload
    def get(self, setting: StringContactSettings) -> str: ...  # noqa: E704
    @overload
    def get(self, setting: BoolContactSettings) -> bool: ...  # noqa: E704

    def get(self, setting: AllContactSettings) -> AllContactSettingsT:
        return app.settings.get_contact_setting(
            self._account, self._jid, setting)

    @overload
    def set(self, setting: StringContactSettings, value: str | None) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: BoolContactSettings, value: bool | None) -> None: ...  # noqa: E501, E704

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

    def get(self, setting: AllGroupChatSettings) -> AllGroupChatSettingsT:
        return app.settings.get_group_chat_setting(
            self._account, self._jid, setting)

    @overload
    def set(self, setting: StringGroupChatSettings, value: str | None) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: BoolGroupChatSettings, value: bool | None) -> None: ...  # noqa: E501, E704
    @overload
    def set(self, setting: IntGroupChatSettings, value: int | None) -> None: ...  # noqa: E501, E704

    def set(self, setting: Any, value: Any) -> None:
        app.settings.set_group_chat_setting(
            self._account, self._jid, setting, value)


class Contacts(BaseModule):
    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self._contacts: dict[JID, BareContact | GroupchatContact] = {}
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

    def add_chat_contact(self, jid: str | JID) -> BareContact:
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

    def add_group_chat_contact(self, jid: str | JID) -> GroupchatContact:
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        contact = self._contacts.get(jid)
        if contact is not None:
            if not isinstance(contact, GroupchatContact):
                raise ValueError(f'Trying to add GroupchatContact {jid}, '
                                 f'but contact already exists as {contact} '
                                 f'(in roster: {contact.is_in_roster})')
            return contact

        contact = GroupchatContact(self._log, jid, self._account)

        self._contacts[jid] = contact
        return contact

    def add_private_contact(self, jid: str | JID) -> GroupchatParticipant:
        if isinstance(jid, str):
            jid = JID.from_string(jid)

        if jid.resource is None:
            raise ValueError(f'Trying to add a bare JID as private {jid}')

        contact = self._contacts.get(jid.new_as_bare())
        if contact is None:
            group_chat_contact = self.add_group_chat_contact(jid.bare)
            return group_chat_contact.add_resource(jid.resource)

        if not isinstance(contact, GroupchatContact):
            raise ValueError(f'Trying to add GroupchatParticipant {jid}, '
                             f'to BareContact {contact}')

        return contact.add_resource(jid.resource)

    def add_contact(self,
                    jid: str | JID,
                    groupchat: bool = False) -> BareContact | GroupchatContact:
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
                    jid: str | JID,
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

    def get_bare_contact(self,
                         jid: str | JID
                         ) -> BareContact | GroupchatContact:
        '''This method gives direct access to the contacts dict.
           This is helpful when performance is essential. In difference to
           get_contact() this method does not create contacts nor can it handle
           JIDs which are not bare. Use this only if you know the contact
           exists.
        '''
        return self._contacts[jid]

    def get_contacts_with_domain(self,
                                 domain: str
                                 ) -> list[BareContact | GroupchatContact]:

        contacts: list[BareContact | GroupchatContact] = []
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


class CommonContact(Observable, ClientModules):
    def __init__(self,
                 logger: LogAdapter,
                 jid: JID,
                 account: str
                 ) -> None:

        Observable.__init__(self, logger)
        ClientModules.__init__(self, account)
        self._jid = jid
        self._account = account
        self._gateway_type: str | None = None

    def __hash__(self) -> int:
        return hash(f'{self._account}-{self._jid}')

    def __eq__(self, obj: object) -> bool:
        if not isinstance(obj, CommonContact):
            return NotImplemented

        return (self._account == obj.account and
                obj._jid == self._jid)

    @property
    def jid(self) -> JID:
        return self._jid

    @property
    def account(self) -> str:
        return self._account

    def _on_signal(
        self,
        _contact: (BareContact |
                   ResourceContact |
                   GroupchatContact |
                   GroupchatParticipant),
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
    def chatstate(self) -> Chatstate | None:
        return None

    @property
    def chatstate_string(self) -> str:
        return chatstate_to_string(self.chatstate)

    @property
    def is_muted(self) -> bool:
        mute_until = self.settings.get('mute_until')
        if not mute_until:
            return False

        until = datetime.fromisoformat(mute_until)
        is_muted = until > datetime.now(timezone.utc)
        if not is_muted:
            # Reset the setting to default
            GLib.idle_add(self.settings.set, 'mute_until', None)
        return is_muted

    def __repr__(self) -> str:
        return f'{self.jid} ({self._account})'

    def _get_transport_icon_name(self) -> str | None:
        if self._gateway_type is not None:
            return f'gateway-{self._gateway_type}'

        domain_disco = app.storage.cache.get_last_disco_info(self._jid.domain)
        if domain_disco is None:
            return None

        if gateway_type := domain_disco.gateway_type:
            self._gateway_type = gateway_type
            return f'gateway-{gateway_type}'

    def update_gateway_type(self, gateway_type: str | None):
        if gateway_type == self._gateway_type:
            return

        self._gateway_type = gateway_type
        self.notify('avatar-update')


class BareContact(CommonContact):
    def __init__(self, logger: LogAdapter, jid: JID, account: str) -> None:
        CommonContact.__init__(self, logger, jid, account)

        self.settings = ContactSettings(account, jid)
        self._resources: dict[str, ResourceContact] = {}

        self._avatar_sha = app.storage.cache.get_contact(
            account, jid, 'avatar')

        self._presence = UNKNOWN_PRESENCE

    @property
    def is_self(self):
        own_jid = app.get_client(self._account).get_own_jid().new_as_bare()
        return own_jid == self.jid

    def supports(self, requested_feature: str) -> bool:
        if not self._resources:
            return super().supports(requested_feature)
        return any(resource.supports(requested_feature)
                   for resource in self.iter_resources())

    @property
    def supports_audio(self) -> bool:
        if (self.supports(Namespace.JINGLE_ICE_UDP) and
                app.is_installed('FARSTREAM')):
            return self.supports(Namespace.JINGLE_RTP_AUDIO)
        return False

    @property
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

    def has_resources(self) -> bool:
        return bool(self._resources)

    def get_resource(self, resource: str) -> ResourceContact:
        contact = self._resources.get(resource)
        if contact is None:
            contact = self.add_resource(resource)
        return contact

    def get_active_resource(self) -> ResourceContact | None:
        if not self._resources:
            return None

        return sorted(self._resources.values(),
                      key=operator.attrgetter('show'))[-1]

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
        if not self._resources:
            return self._presence.available
        return any(contact.is_available for contact
                   in self._resources.values())

    @property
    def show(self) -> PresenceShow | Literal[PresenceShowExt.OFFLINE]:
        if not self._resources:
            if not self._presence.available:
                return PresenceShowExt.OFFLINE
            return self._presence.show

        res = self.get_active_resource()
        assert res is not None
        return res.show

    @property
    def status(self) -> str:
        if not self._resources:
            return self._presence.status

        res = self.get_active_resource()
        assert res is not None
        return res.status

    @property
    def idle_datetime(self) -> datetime | None:
        if not self._resources:
            return self._presence.idle_datetime

        res = self.get_active_resource()
        assert res is not None
        return res.idle_datetime

    @property
    def chatstate(self) -> Chatstate | None:
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
        item = self.get_module('Roster').get_item(self._jid)
        if item is not None and item.name:
            return item.name

        nickname = app.storage.cache.get_contact(
            self._account, self._jid, 'nickname')
        if nickname:
            return nickname
        if self._jid.is_domain:
            assert self._jid.domain is not None
            return self._jid.domain

        assert self._jid.localpart is not None
        return self._jid.localpart

    def get_tune(self) -> TuneData | None:
        return self.get_module('UserTune').get_contact_tune(self._jid)

    def get_location(self) -> LocationData | None:
        return self.get_module('UserLocation').get_contact_location(self._jid)

    @property
    def avatar_sha(self) -> str | None:
        return app.storage.cache.get_contact(
            self._account, self._jid, 'avatar')

    def set_avatar_sha(self, sha: str) -> None:
        app.storage.cache.set_contact(self._account, self._jid, 'avatar', sha)

    def get_avatar(self,
                   size: int,
                   scale: int,
                   add_show: bool = True,
                   default: bool = False,
                   style: str = 'circle'):

        show = self.show.value if add_show else None

        transport_icon = self._get_transport_icon_name()

        return app.app.avatar_storage.get_surface(
            self,
            size,
            scale,
            show,
            default=default,
            transport_icon=transport_icon,
            style=style)

    def update_presence(self, presence_data: PresenceData) -> None:
        self._presence = presence_data
        if not presence_data.available:
            for contact in self._resources.values():
                contact.update_presence(presence_data, notify=False)
        self.notify('presence-update')

    def update_avatar(self, sha: str) -> None:
        if self._avatar_sha == sha:
            return

        self._avatar_sha = sha

        app.storage.cache.set_contact(self._account, self._jid, 'avatar', sha)
        app.app.avatar_storage.invalidate_cache(self._jid)
        self.notify('avatar-update')

    @property
    def is_in_roster(self) -> bool:
        item = self.get_module('Roster').get_item(self._jid)
        return item is not None

    @property
    def is_gateway(self) -> bool:
        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        if disco_info is None:
            return False
        return disco_info.is_gateway

    @property
    def ask(self) -> str | None:
        item = self.get_module('Roster').get_item(self._jid)
        if item is None:
            return None
        return item.ask

    @property
    def subscription(self) -> str | None:
        item = self.get_module('Roster').get_item(self._jid)
        if item is None:
            return None
        return item.subscription

    @property
    def groups(self) -> set[str]:
        item = self.get_module('Roster').get_item(self._jid)
        if item is None:
            return set()
        return item.groups

    @property
    def is_subscribed(self) -> bool:
        return self.subscription in ('from', 'both')

    @property
    def is_blocked(self) -> bool:
        return self.get_module('Blocking').is_blocked(self._jid)

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

    @property
    def is_bot(self) -> bool:
        disco_info = app.storage.cache.get_last_disco_info(self._jid)

        if disco_info is not None and disco_info.has_identity('client', 'bot'):
            return True

        return any(r.is_bot for r in self.iter_resources())


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
    def identity_type(self) -> str | None:
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

        return any(identity.type == 'phone' for
                   identity in disco_info.identities)

    @property
    def is_bot(self):
        disco_info = app.storage.cache.get_last_disco_info(self._jid)
        return (disco_info is not None
                and disco_info.has_identity('client', 'bot'))

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
    def idle_datetime(self) -> datetime | None:
        return self._presence.idle_datetime

    @property
    def chatstate(self) -> Chatstate | None:
        return self.get_module('Chatstate').get_remote_chatstate(self._jid)

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

    @property
    def is_muted(self) -> bool:
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
    def muc_context(self) -> str | None:
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
    def avatar_sha(self) -> str | None:
        return app.storage.cache.get_muc(self._account, self._jid, 'avatar')

    def set_avatar_sha(self, sha: str) -> None:
        app.storage.cache.set_muc(self._account, self._jid, 'avatar', sha)

    def get_avatar(self, size: int, scale: int) -> cairo.ImageSurface:
        transport_icon = self._get_transport_icon_name()

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

    def get_self(self) -> GroupchatParticipant | None:
        nick = self.nickname
        if nick is None:
            return None
        return self.get_resource(nick)

    @property
    def nickname(self) -> str | None:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.nick

    @property
    def occupant_jid(self) -> JID | None:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.occupant_jid

    @property
    def subject(self) -> MucSubject | None:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return None
        return muc_data.subject

    @property
    def is_joined(self) -> bool:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joined

    @property
    def is_joining(self) -> bool:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return False
        return muc_data.state.is_joining

    @property
    def is_not_joined(self) -> bool:
        muc_data = self.get_module('MUC').get_muc_data(self._jid)
        if muc_data is None:
            return True
        return muc_data.state.is_not_joined

    def set_not_joined(self) -> None:
        for contact in self._resources.values():
            contact.update_presence(UNKNOWN_MUC_PRESENCE)

    def get_user_nicknames(self) -> list[str]:
        client = app.get_client(self._account)
        return client.get_module('MUC').get_joined_users(str(self._jid))

    def get_disco(self, max_age: int = 0) -> DiscoInfo | None:
        return app.storage.cache.get_last_disco_info(self.jid, max_age=max_age)

    def can_notify(self) -> bool:
        all_ = app.settings.get('notify_on_all_muc_messages')
        room = self.settings.get('notify_on_all_messages')
        return all_ or room

    @property
    def type_string(self) -> str:
        return 'groupchat'

    def has_composing_participants(self) -> bool:
        return bool(self.get_module('Chatstate').get_composers(self._jid))

    def get_composers(self) -> list['GroupchatParticipant']:
        return self.get_module('Chatstate').get_composers(self._jid)


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
        contact = self.get_module('Contacts').get_bare_contact(self.jid.bare)
        assert isinstance(contact, GroupchatContact)
        return contact

    @property
    def muc_context(self) -> str | None:
        return self.room.muc_context

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
    def idle_datetime(self) -> datetime | None:
        return self._presence.idle_datetime

    @property
    def name(self) -> str:
        assert self._jid.resource is not None
        return self._jid.resource

    @property
    def real_jid(self) -> JID | None:
        return self._presence.real_jid

    def get_real_contact(self) -> BareContact | None:
        jid = self._presence.real_jid
        if jid is None:
            return None
        contact = self._client.get_module('Contacts').get_contact(
            jid.new_as_bare())
        assert isinstance(contact, BareContact)
        return contact

    @property
    def affiliation(self) -> Affiliation:
        return self._presence.affiliation

    @property
    def role(self) -> Role:
        return self._presence.role

    @property
    def chatstate(self) -> Chatstate | None:
        return self.get_module('Chatstate').get_remote_chatstate(self._jid)

    @property
    def avatar_sha(self) -> str | None:
        return self._client.get_module('VCardAvatars').get_avatar_sha(
            self._jid)

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

    @property
    def occupant_id(self) -> str | None:
        return self._presence.occupant_id

    @property
    def is_self(self) -> bool:
        data = self.get_module('MUC').get_muc_data(self.room.jid)
        assert data is not None
        return data.nick == self.name


def can_add_to_roster(
    contact: BareContact | GroupchatContact | GroupchatParticipant
) -> bool:

    if isinstance(contact, GroupchatContact):
        return False

    if isinstance(contact, GroupchatParticipant):
        return contact.real_jid is not None

    if contact.is_self:
        return False
    return not contact.is_in_roster
