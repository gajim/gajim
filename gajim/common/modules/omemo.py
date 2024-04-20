# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0384: OMEMO Encryption

from __future__ import annotations

from typing import Any

import binascii
import threading
from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import PresenceType
from nbxmpp.errors import StanzaError
from nbxmpp.modules.omemo import create_omemo_message
from nbxmpp.modules.omemo import get_key_transport_message
from nbxmpp.modules.util import is_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import OMEMOMessage
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import Task
from omemo_dr.aes import aes_encrypt_file
from omemo_dr.const import OMEMOTrust
from omemo_dr.exceptions import DecryptionFailed
from omemo_dr.exceptions import DuplicateMessage
from omemo_dr.exceptions import KeyExchangeMessage
from omemo_dr.exceptions import MessageNotForDevice
from omemo_dr.exceptions import SelfMessage
from omemo_dr.identitykey import IdentityKey
from omemo_dr.session_manager import OMEMOSessionManager
from omemo_dr.structs import OMEMOBundle
from omemo_dr.structs import OMEMOConfig

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common import types
from gajim.common.const import EncryptionData
from gajim.common.const import EncryptionInfoMsg
from gajim.common.const import Trust as GajimTrust
from gajim.common.const import XmppUriQuery
from gajim.common.events import EncryptionInfo
from gajim.common.events import MucAdded
from gajim.common.events import MucDiscoUpdate
from gajim.common.events import SignedIn
from gajim.common.helpers import event_filter
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.modules.util import as_task
from gajim.common.modules.util import event_node
from gajim.common.modules.util import prepare_stanza
from gajim.common.storage.omemo import OMEMOStorage
from gajim.common.structs import OutgoingMessage
from gajim.common.util.decorators import lru_cache_with_ttl

ALLOWED_TAGS = [
    ('request', Namespace.RECEIPTS),
    ('active', Namespace.CHATSTATES),
    ('gone', Namespace.CHATSTATES),
    ('inactive', Namespace.CHATSTATES),
    ('paused', Namespace.CHATSTATES),
    ('composing', Namespace.CHATSTATES),
    ('markable', Namespace.CHATMARKERS),
    ('no-store', Namespace.HINTS),
    ('store', Namespace.HINTS),
    ('no-copy', Namespace.HINTS),
    ('no-permanent-store', Namespace.HINTS),
    ('replace', Namespace.CORRECT),
    ('thread', None),
    ('origin-id', Namespace.SID),
]

DeviceIdT = int
IdentityT = tuple[DeviceIdT, IdentityKey]

class OMEMO(BaseModule):

    _nbxmpp_extends = 'OMEMO'
    _nbxmpp_methods = [
        'set_devicelist',
        'request_devicelist',
        'set_bundle',
        'request_bundle',
    ]

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._message_received,
                          ns=Namespace.OMEMO_TEMP,
                          priority=9),
            StanzaHandler(name='presence',
                          callback=self._on_muc_user_presence,
                          ns=Namespace.MUC_USER,
                          priority=48),
        ]

        self._register_pubsub_handler(self._devicelist_notification_received)
        self.register_events([
            ('signed-in', ged.CORE, self._on_signed_in),
            ('muc-disco-update', ged.GUI1, self._on_muc_disco_update),
            ('muc-added', ged.GUI1, self._on_muc_added)
        ])

        self.allow_groupchat = True

        self._own_jid = self._client.get_own_jid().bare

        data_dir = Path(configpaths.get('MY_DATA'))
        db_path = data_dir / f'omemo_{self._own_jid}.db'
        storage = OMEMOStorage(self._account, db_path, self._log)

        omemo_config = OMEMOConfig(default_prekey_amount=100,
                                   min_prekey_amount=80,
                                   spk_archive_seconds=86400 * 15,
                                   spk_cycle_seconds=86400,
                                   unacknowledged_count=2000)

        self._backend = OMEMOSessionManager(
            self._own_jid, storage, omemo_config, self._account)
        self._backend.register_signal('republish-bundle',
                                      self._on_republish_bundle)

        self._omemo_groupchats: set[str] = set()
        self._muc_temp_store: dict[bytes, str] = {}

    @event_filter(['account'])
    def _on_signed_in(self, _event: SignedIn) -> None:
        self._log.info('Publish our bundle after sign in')
        self.set_bundle()
        self.request_devicelist()

    @event_filter(['account'])
    def _on_muc_disco_update(self, event: MucDiscoUpdate) -> None:
        self._check_if_omemo_capable(str(event.jid))

    @event_filter(['account'])
    def _on_muc_added(self, event: MucAdded) -> None:
        client = app.get_client(event.account)
        contact = client.get_module('Contacts').get_contact(event.jid)
        if not isinstance(contact, GroupchatContact):
            self._log.warning('%s is not a groupchat contact', contact)
            return

        # Event is triggert on every join, avoid multiple connects
        contact.disconnect_all_from_obj(self)
        contact.connect('room-joined', self._on_room_joined)

    def _on_room_joined(self,
                        contact: GroupchatContact,
                        _signal_name: str
                        ) -> None:

        jid = str(contact.jid)
        self._check_if_omemo_capable(jid)
        if self._is_omemo_groupchat(jid):
            self._get_affiliation_list(jid)

    def _on_republish_bundle(self,
                             _session: OMEMOSessionManager,
                             _signal_name: str,
                             bundle: OMEMOBundle
                             ) -> None:

        self.set_bundle(bundle=bundle)

    @property
    def backend(self) -> OMEMOSessionManager:
        return self._backend

    def check_send_preconditions(self, contact: types.ChatContactT) -> bool:
        jid = str(contact.jid)
        if contact.is_groupchat:
            if not self._groupchat_pre_conditions_satisfied(contact):
                return False

        else:
            if not self._chat_pre_conditions_satisfied(contact):
                return False

        if self.backend.get_identity_infos(jid,
                                           only_active=True,
                                           trust=OMEMOTrust.UNDECIDED):
            self._log.info('Undecided keys for %s', jid)
            app.ged.raise_event(EncryptionInfo(
                account=contact.account,
                jid=contact.jid,
                message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS))
            return False

        self._log.debug('Sending message to %s', jid)

        return True

    def _groupchat_pre_conditions_satisfied(
            self,
            contact: types.GroupchatContactT
        ) -> bool:

        jid = str(contact.jid)
        if not self._is_omemo_groupchat(jid):
            app.ged.raise_event(EncryptionInfo(
                account=contact.account,
                jid=contact.jid,
                message=EncryptionInfoMsg.BAD_OMEMO_CONFIG))
            return False

        has_trusted_keys = False
        for member_jid in self.backend.get_group_members(jid):
            self._request_bundles_for_new_devices(member_jid)
            if self._has_trusted_keys(member_jid):
                has_trusted_keys = True

        if not has_trusted_keys:
            self._log.info('No trusted keys for %s', jid)
            app.ged.raise_event(EncryptionInfo(
                account=contact.account,
                jid=contact.jid,
                message=EncryptionInfoMsg.NO_FINGERPRINTS))
            return False
        return True

    def _chat_pre_conditions_satisfied(
            self,
            contact: types.ChatContactT
        ) -> bool:

        jid = str(contact.jid)
        if not self.backend.get_devices(jid, without_self=True):
            self.request_devicelist(jid)
            app.ged.raise_event(EncryptionInfo(
                account=contact.account,
                jid=contact.jid,
                message=EncryptionInfoMsg.QUERY_DEVICES))
            return False

        if not self._has_trusted_keys(jid):
            self._log.info('No trusted keys for %s', jid)
            app.ged.raise_event(EncryptionInfo(
                account=contact.account,
                jid=contact.jid,
                message=EncryptionInfoMsg.NO_FINGERPRINTS))
            return False
        return True

    def _is_omemo_groupchat(self, room_jid: str) -> bool:
        return room_jid in self._omemo_groupchats

    def encrypt_message(self, event: OutgoingMessage) -> bool:
        if not event.text:
            return False

        client = app.get_client(self._account)
        contact = client.get_module('Contacts').get_contact(event.jid)

        omemo_message = self.backend.encrypt(str(event.jid),
                                             event.text,
                                             groupchat=contact.is_groupchat)
        if omemo_message is None:
            raise Exception('Encryption error')

        create_omemo_message(event.stanza, omemo_message,
                             node_whitelist=ALLOWED_TAGS)

        if event.is_groupchat:
            self._muc_temp_store[omemo_message.payload] = event.text

        event.additional_data['encrypted'] = {
            'name': 'OMEMO',
            'trust': GajimTrust[OMEMOTrust.VERIFIED.name]}

        self._debug_print_stanza(event.stanza)
        return True

    def encrypt_file(self,
                     transfer: HTTPFileTransfer,
                     callback: Callable[..., Any]
                     ) -> None:

        thread = threading.Thread(target=self._encrypt_file_thread,
                                  args=(transfer, callback))
        thread.daemon = True
        thread.start()

    @staticmethod
    def _encrypt_file_thread(transfer: HTTPFileTransfer,
                             callback: Callable[..., Any],
                             *args: Any,
                             **kwargs: Any
                             ) -> None:

        result = aes_encrypt_file(transfer.get_data())
        transfer.size = len(result.payload)
        fragment = binascii.hexlify(result.iv + result.key).decode()
        transfer.set_uri_transform_func(
            lambda uri: f'aesgcm{uri[5:]}#{fragment}')
        transfer.set_encrypted_data(result.payload)
        GLib.idle_add(callback, transfer)

    def _send_key_transport_message(self,
                                    typ: str,
                                    jid: str,
                                    devices: list[int]
                                    ) -> None:

        omemo_message = self.backend.encrypt_key_transport(jid, devices)
        if omemo_message is None:
            self._log.warning('Key transport message to %s (%s) failed',
                              jid, devices)
            return

        transport_message = get_key_transport_message(typ, jid, omemo_message)
        self._log.info('Send key transport message to %s (%s)', jid, devices)
        self._client.send_stanza(transport_message)

    def _message_received(self,
                          _client: types.xmppClient,
                          stanza: Message,
                          properties: MessageProperties
                          ) -> None:

        if not properties.is_omemo:
            return

        if properties.is_carbon_message and properties.carbon.is_sent:
            from_jid = self._own_jid

        elif properties.is_mam_message:
            from_jid = self._process_mam_message(properties)

        elif properties.from_muc:
            from_jid = self._process_muc_message(properties)

        else:
            from_jid = properties.jid.bare

        if from_jid is None:
            return

        self._log.info('Message received from: %s', from_jid)

        assert isinstance(properties.omemo, OMEMOMessage)
        try:
            plaintext, fingerprint, trust = self.backend.decrypt_message(
                properties.omemo, from_jid)
        except (KeyExchangeMessage, DuplicateMessage):
            raise NodeProcessed

        except SelfMessage:
            if not properties.from_muc:
                raise NodeProcessed

            if properties.omemo.payload not in self._muc_temp_store:
                self._log.warning("Can't decrypt own group chat message")
                return

            del self._muc_temp_store[properties.omemo.payload]
            return

        except DecryptionFailed:
            return

        except MessageNotForDevice:
            if properties.omemo.payload is None:
                # Key Transport message for another device
                return

            plaintext = _('This message was encrypted with OMEMO, '
                          'but not for your device.')
            # Neither trust nor fingerprint can be verified if we didn't
            # successfully decrypt the message
            trust = OMEMOTrust.UNTRUSTED
            fingerprint = None

        prepare_stanza(stanza, plaintext)
        self._debug_print_stanza(stanza)
        properties.encrypted = EncryptionData({
            'name': 'OMEMO',
            'fingerprint': fingerprint or 'Unknown',
            'trust': GajimTrust[trust.name]})

    def _process_muc_message(self,
                             properties: MessageProperties
                             ) -> str | None:

        resource = properties.jid.resource
        if properties.muc_ofrom is not None:
            # History Message from MUC
            return properties.muc_ofrom.bare

        contact = self._client.get_module('Contacts').get_contact(
            properties.jid)
        if contact.real_jid is not None:
            return contact.real_jid.bare

        self._log.error(
            'Unable to find jid for group chat message from %s', resource)
        return None

    def _process_mam_message(self,
                             properties: MessageProperties
                             ) -> str | None:

        self._log.info('Message received, archive: %s', properties.mam.archive)
        if properties.from_muc:
            self._log.info('MUC MAM Message received')
            if properties.muc_user is None or properties.muc_user.jid is None:
                self._log.warning('Received MAM message which can '
                                  'not be mapped to a real jid')
                return None
            return properties.muc_user.jid.bare
        return properties.from_.bare

    def _on_muc_user_presence(self,
                              _client: types.xmppClient,
                              _stanza: Presence,
                              properties: PresenceProperties
                              ) -> None:

        if properties.type == PresenceType.ERROR:
            return

        if properties.is_muc_destroyed:
            return

        room = properties.jid.bare

        if properties.muc_user is None or properties.muc_user.jid is None:
            # No real jid found
            return

        jid = properties.muc_user.jid.bare
        if properties.muc_user.affiliation in (Affiliation.OUTCAST,
                                               Affiliation.NONE):
            self.backend.remove_group_member(room, jid)
        else:
            self.backend.add_group_member(room, jid)

        if self._is_omemo_groupchat(room):
            if not self._is_contact_in_roster(jid):
                # Query Devicelists from JIDs not in our Roster
                self._log.info('%s not in roster, query devicelist...', jid)
                self._request_device_list_ttl(jid)

    def _get_affiliation_list(self, room_jid: str) -> None:
        for affiliation in ('owner', 'admin', 'member'):
            self._nbxmpp('MUC').get_affiliation(
                room_jid,
                affiliation,
                callback=self._on_affiliations_received,
                user_data=room_jid)

    def _on_affiliations_received(self, task: Task) -> None:
        room_jid = task.get_user_data()
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info('Affiliation request failed: %s', error)
            return

        for user_jid in result.users:
            jid = str(user_jid)
            self.backend.add_group_member(room_jid, jid)

            if not self._is_contact_in_roster(jid):
                self._log.info('%s not in roster, query devicelist...', jid)
                self._request_device_list_ttl(jid)

    def _is_contact_in_roster(self, jid: str) -> bool:
        if jid == self._own_jid:
            return True

        roster_item = self._client.get_module('Roster').get_item(jid)
        if roster_item is None:
            return False

        contact = self._client.get_module('Contacts').get_contact(jid)
        return contact.subscription == 'both'

    def _check_if_omemo_capable(self, jid: str) -> None:
        disco_info = app.storage.cache.get_last_disco_info(jid)
        if disco_info.muc_is_members_only and disco_info.muc_is_nonanonymous:
            self._log.info('OMEMO room discovered: %s', jid)
            self._omemo_groupchats.add(jid)
        else:
            self._log.info('OMEMO room removed due to config change: %s', jid)
            self._omemo_groupchats.discard(jid)

    def _request_bundles_for_new_devices(self, jid_: str) -> None:
        for jid in [jid_, self._own_jid]:
            device_ids = self.backend.get_devices_without_sessions(jid)
            for device_id in device_ids:
                self._request_bundle_ttl(jid, device_id)

    def _has_trusted_keys(self, jid: str) -> bool:
        if self.backend.get_identity_infos(
                jid,
                only_active=True,
                trust=[OMEMOTrust.VERIFIED, OMEMOTrust.BLIND]):
            return True
        return False

    def set_bundle(self, bundle: OMEMOBundle | None = None) -> None:
        if bundle is None:
            bundle = self.backend.get_bundle(Namespace.OMEMO_TEMP)
        self._nbxmpp('OMEMO').set_bundle(bundle,
                                         self.backend.get_our_device())

    @lru_cache_with_ttl(maxsize=512, ttl=7200)
    def _request_bundle_ttl(self, jid: str, device_id: int) -> None:
        self.request_bundle(jid, device_id)

    @as_task
    def request_bundle(self, jid: str, device_id: int):
        _task = yield  # noqa: F841

        self._log.info('Request device bundle %s %s', device_id, jid)

        bundle = yield self._nbxmpp('OMEMO').request_bundle(jid, device_id)

        if is_error(bundle) or bundle is None:
            self._log.info('Bundle request failed: %s %s: %s',
                           jid, device_id, bundle)
            return

        try:
            self.backend.build_session(jid, bundle)
        except Exception as error:
            self._log.error('Building session failed: %s', error)
            return

        self._log.info('Session created for: %s', jid)
        # TODO: In MUC we should send a groupchat message
        self._send_key_transport_message('chat', jid, [device_id])

        # Trigger dialog to trust new Fingerprints if
        # the Chat Window is Open
        app.ged.raise_event(EncryptionInfo(
            account=self._account,
            jid=JID.from_string(jid),
            message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS))

    def set_devicelist(self, devicelist: list[int] | None = None) -> None:
        devicelist_: set[int] = {self.backend.get_our_device()}
        if devicelist is not None:
            devicelist_.update(devicelist)
        self._log.info('Publishing own devicelist: %s', devicelist_)
        self._nbxmpp('OMEMO').set_devicelist(devicelist_)

    def clear_devicelist(self) -> None:
        self.backend.update_devicelist(
            self._own_jid, [self.backend.get_our_device()])
        self.set_devicelist()

    @lru_cache_with_ttl(maxsize=512, ttl=7200)
    def _request_device_list_ttl(self, jid: str) -> None:
        self.request_devicelist(jid)

    @as_task
    def request_devicelist(self, jid: str | None = None):
        _task = yield  # noqa: F841

        if jid is None:
            jid = self._own_jid

        self._log.info('Request devicelist for %s', jid)

        devicelist = yield self._nbxmpp('OMEMO').request_devicelist(jid=jid)
        if is_error(devicelist) or devicelist is None:
            self._log.info('Devicelist request failed: %s %s', jid, devicelist)
            devicelist = []

        self._process_devicelist_update(jid, devicelist)

    @event_node(Namespace.OMEMO_TEMP_DL)
    def _devicelist_notification_received(self,
                                          _client: types.xmppClient,
                                          _stanza: Message,
                                          properties: MessageProperties
                                          ) -> None:

        if properties.pubsub_event.retracted:
            return

        devicelist = properties.pubsub_event.data or []

        self._process_devicelist_update(str(properties.jid), devicelist)

    def _process_devicelist_update(self,
                                   jid: str,
                                   devicelist: list[int]
                                   ) -> None:

        own_devices = jid is None or self._client.get_own_jid().bare_match(jid)
        if own_devices:
            jid = self._own_jid

        self._log.info('Received device list for %s: %s', jid, devicelist)
        # Pass a copy, we need the full list for potential set_devicelist()
        self.backend.update_devicelist(jid, list(devicelist))

        if own_devices:
            if not self.backend.is_our_device_published():
                # Our own device_id is not in the list, it could be
                # overwritten by some other client
                self.set_devicelist(devicelist)

        self._request_bundles_for_new_devices(jid)

    def _debug_print_stanza(self, stanza: Any) -> None:
        stanzastr = '\n' + stanza.__str__(fancy=True)
        stanzastr = stanzastr[0:-1]
        self._log.debug(stanzastr)

    def compose_trust_uri(self, jid: JID) -> str:
        verified_identities = [
            (info.device_id, info.public_key)
            for info in self._backend.get_identity_infos(
                jid.bare, only_active=True, trust=OMEMOTrust.VERIFIED)
        ]
        if self._client.is_own_jid(jid):
            verified_identities.insert(0, self._backend.get_our_identity())
        return compose_trust_uri(jid, verified_identities)

    def cleanup(self) -> None:
        BaseModule.cleanup(self)
        self._backend.destroy()
        del self._backend


def compose_trust_uri(jid: JID, devices: list[IdentityT]) -> str:
    query = (
        XmppUriQuery.MESSAGE.value,
        [(f'omemo-sid-{sid}', ik.get_fingerprint()) for sid, ik in devices]
    ) if devices else None
    uri = jid.new_as_bare().to_iri(query)
    return uri
