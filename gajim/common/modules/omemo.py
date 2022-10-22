# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of OMEMO Gajim Plugin.
#
# OMEMO Gajim Plugin is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# OMEMO Gajim Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OMEMO Gajim Plugin. If not, see <http://www.gnu.org/licenses/>.

# XEP-0384: OMEMO Encryption

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Optional

import binascii
import threading
from pathlib import Path

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.errors import StanzaError
from nbxmpp.const import PresenceType
from nbxmpp.const import Affiliation
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import OMEMOMessage
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.omemo import create_omemo_message
from nbxmpp.modules.omemo import get_key_transport_message
from nbxmpp.modules.util import is_error
from nbxmpp.task import Task

from gi.repository import GLib

from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common import types
from gajim.common.structs import OutgoingMessage
from gajim.common.const import EncryptionInfoMsg
from gajim.common.const import EncryptionData
from gajim.common.const import Trust as GajimTrust
from gajim.common.i18n import _
from gajim.common.events import EncryptionAnnouncement
from gajim.common.events import MucAdded
from gajim.common.events import MucDiscoUpdate
from gajim.common.events import SignedIn
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.util import event_node
from gajim.common.modules.util import as_task
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.omemo.aes import aes_encrypt_file
from gajim.common.omemo.state import OmemoState
from gajim.common.omemo.state import KeyExchangeMessage
from gajim.common.omemo.state import SelfMessage
from gajim.common.omemo.state import MessageNotForDevice
from gajim.common.omemo.state import DecryptionFailed
from gajim.common.omemo.state import DuplicateMessage
from gajim.common.omemo.util import Trust
from gajim.common.modules.util import prepare_stanza


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

ENCRYPTION_NAME = 'OMEMO'

# Module name
name = 'OMEMO'
zeroconf = False


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

        self.encryption_name = 'OMEMO'
        self.allow_groupchat = True

        self._own_jid = self._client.get_own_jid().bare
        self._backend = self._get_backend()

        self._omemo_groupchats: set[str] = set()
        self._muc_temp_store: dict[bytes, str] = {}
        self._query_for_bundles: list[str] = []
        self._device_bundle_querys: list[int] = []
        self._query_for_devicelists: list[str] = []

    def _on_signed_in(self, _event: SignedIn) -> None:
        self._log.info('Announce Support after Sign In')
        self._query_for_bundles = []
        self.set_bundle()
        self.request_devicelist()

    def _on_muc_disco_update(self, event: MucDiscoUpdate) -> None:
        self._check_if_omemo_capable(str(event.jid))

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
        if self.is_omemo_groupchat(jid):
            self.get_affiliation_list(jid)

    @property
    def backend(self) -> OmemoState:
        return self._backend

    def _get_backend(self) -> OmemoState:
        data_dir = Path(configpaths.get('MY_DATA'))
        db_path = data_dir / f'omemo_{self._own_jid}.db'
        return OmemoState(self._own_jid, db_path, self._account, self)

    def check_send_preconditions(self, contact: types.ChatContactT) -> bool:
        jid = str(contact.jid)
        if contact.is_groupchat:
            if not self.is_omemo_groupchat(jid):
                app.ged.raise_event(EncryptionAnnouncement(
                    account=contact.account,
                    jid=contact.jid,
                    message=EncryptionInfoMsg.BAD_OMEMO_CONFIG))
                return False

            missing = True
            for member_jid in self.backend.get_muc_members(jid):
                if not self.are_keys_missing(member_jid):
                    missing = False
            if missing:
                self._log.info('%s => No Trusted Fingerprints for %s',
                               contact.account, jid)
                app.ged.raise_event(EncryptionAnnouncement(
                    account=contact.account,
                    jid=contact.jid,
                    message=EncryptionInfoMsg.NO_FINGERPRINTS))
                return False
        else:
            # check if we have devices for the contact
            if not self.backend.get_devices(jid, without_self=True):
                self.request_devicelist(jid)
                app.ged.raise_event(EncryptionAnnouncement(
                    account=contact.account,
                    jid=contact.jid,
                    message=EncryptionInfoMsg.QUERY_DEVICES))
                return False

            # check if bundles are missing for some devices
            if self.backend.storage.hasUndecidedFingerprints(jid):
                self._log.info('%s => Undecided Fingerprints for %s',
                               contact.account, jid)
                app.ged.raise_event(EncryptionAnnouncement(
                    account=contact.account,
                    jid=contact.jid,
                    message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS))
                return False

        if self._new_fingerprints_available(contact):
            return False

        self._log.debug('%s => Sending Message to %s',
                        contact.account, jid)

        return True

    def _new_fingerprints_available(self, contact: types.ChatContactT) -> bool:
        fingerprints: list[int] = []
        if contact.is_groupchat:
            for member_jid in self.backend.get_muc_members(str(contact.jid),
                                                           without_self=False):
                fingerprints = self.backend.storage.getNewFingerprints(
                    member_jid)
                if fingerprints:
                    break

        else:
            fingerprints = self.backend.storage.getNewFingerprints(
                str(contact.jid))

        if not fingerprints:
            return False

        app.ged.raise_event(EncryptionAnnouncement(
            account=contact.account,
            jid=contact.jid,
            message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS))

        return True

    def is_omemo_groupchat(self, room_jid: str) -> bool:
        return room_jid in self._omemo_groupchats

    def encrypt_message(self, event: OutgoingMessage) -> bool:
        if not event.message:
            return False

        omemo_message = self.backend.encrypt(str(event.jid), event.message)
        if omemo_message is None:
            raise Exception('Encryption error')

        create_omemo_message(event.stanza, omemo_message,
                             node_whitelist=ALLOWED_TAGS)

        if event.is_groupchat:
            self._muc_temp_store[omemo_message.payload] = event.message
        else:
            event.xhtml = None
            event.encrypted = ENCRYPTION_NAME
            event.additional_data['encrypted'] = {
                'name': ENCRYPTION_NAME,
                'trust': GajimTrust[Trust.VERIFIED.name]}

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
            lambda uri: 'aesgcm%s#%s' % (uri[5:], fragment))
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
        self._log.info('Send key transport message %s (%s)', jid, devices)
        self._client.connection.send(transport_message)

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
                self._log.warning("Can't decrypt own GroupChat Message")
                return

            plaintext = self._muc_temp_store[properties.omemo.payload]
            fingerprint = self.backend.own_fingerprint
            trust = Trust.VERIFIED
            del self._muc_temp_store[properties.omemo.payload]

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
            trust = Trust.UNTRUSTED
            fingerprint = None

        prepare_stanza(stanza, plaintext)
        self._debug_print_stanza(stanza)
        properties.encrypted = EncryptionData({
            'name': ENCRYPTION_NAME,
            'fingerprint': fingerprint,
            'trust': GajimTrust[trust.name]})

    def _process_muc_message(self,
                             properties: MessageProperties
                             ) -> Optional[str]:

        resource = properties.jid.resource
        if properties.muc_ofrom is not None:
            # History Message from MUC
            return properties.muc_ofrom.bare

        contact = self._client.get_module('Contacts').get_contact(
            properties.jid)
        if contact.real_jid is not None:
            return contact.real_jid.bare

        assert isinstance(properties.omemo, OMEMOMessage)
        self._log.info('Groupchat: Last resort trying to find SID in DB')
        from_jid = self.backend.storage.getJidFromDevice(properties.omemo.sid)
        if not from_jid:
            self._log.error(
                "Can't decrypt GroupChat Message from %s", resource)
            return None
        return from_jid

    def _process_mam_message(self,
                             properties: MessageProperties
                             ) -> Optional[str]:

        self._log.info('Message received, archive: %s', properties.mam.archive)
        if properties.from_muc:
            self._log.info('MUC MAM Message received')
            if properties.muc_user is None or properties.muc_user.jid is None:
                self._log.warning('Received MAM Message which can '
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
            self.backend.remove_muc_member(room, jid)
        else:
            self.backend.add_muc_member(room, jid)

        if self.is_omemo_groupchat(room):
            if not self.is_contact_in_roster(jid):
                # Query Devicelists from JIDs not in our Roster
                self._log.info('%s not in Roster, query devicelist...', jid)
                self.request_devicelist(jid)

    def get_affiliation_list(self, room_jid: str) -> None:
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
            self.backend.add_muc_member(room_jid, jid)

            if not self.is_contact_in_roster(jid):
                # Query Devicelists from JIDs not in our Roster
                self._log.info('%s not in Roster, query devicelist...', jid)
                self.request_devicelist(jid)

    def is_contact_in_roster(self, jid: str) -> bool:
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

    def _check_for_missing_sessions(self, jid: str) -> None:
        devices_without_session = self.backend.devices_without_sessions(jid)
        for device_id in devices_without_session:
            if device_id in self._device_bundle_querys:
                continue
            self._device_bundle_querys.append(device_id)
            self.request_bundle(jid, device_id)

    def are_keys_missing(self, contact_jid: str) -> bool:
        ''' Checks if devicekeys are missing and queries the
            bundles

            Parameters
            ----------
            contact_jid : str
                bare jid of the contact

            Returns
            -------
            bool
                Returns True if there are no trusted Fingerprints
        '''

        # Fetch Bundles of own other Devices
        if self._own_jid not in self._query_for_bundles:

            devices_without_session = self.backend.devices_without_sessions(
                self._own_jid)

            self._query_for_bundles.append(self._own_jid)

            if devices_without_session:
                for device_id in devices_without_session:
                    self.request_bundle(self._own_jid, device_id)

        # Fetch Bundles of contacts devices
        if contact_jid not in self._query_for_bundles:

            devices_without_session = self.backend.devices_without_sessions(
                contact_jid)

            self._query_for_bundles.append(contact_jid)

            if devices_without_session:
                for device_id in devices_without_session:
                    self.request_bundle(contact_jid, device_id)

        if self.backend.has_trusted_keys(contact_jid):
            return False
        return True

    def set_bundle(self) -> None:
        self._nbxmpp('OMEMO').set_bundle(self.backend.bundle,
                                         self.backend.own_device)

    @as_task
    def request_bundle(self, jid: str, device_id: int):
        _task = yield  # noqa: F841

        self._log.info('Fetch device bundle %s %s', device_id, jid)

        bundle = yield self._nbxmpp('OMEMO').request_bundle(jid, device_id)

        if is_error(bundle) or bundle is None:
            self._log.info('Bundle request failed: %s %s: %s',
                           jid, device_id, bundle)
            return

        self.backend.build_session(jid, device_id, bundle)
        self._log.info('Session created for: %s', jid)
        # TODO: In MUC we should send a groupchat message
        self._send_key_transport_message('chat', jid, [device_id])

        # Trigger dialog to trust new Fingerprints if
        # the Chat Window is Open
        app.ged.raise_event(EncryptionAnnouncement(
            account=self._account,
            jid=JID.from_string(jid),
            message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS))

    def set_devicelist(self, devicelist: Optional[list[int]] = None) -> None:
        devicelist_: set[int] = set([self.backend.own_device])
        if devicelist is not None:
            devicelist_.update(devicelist)
        self._log.info('Publishing own devicelist: %s', devicelist_)
        self._nbxmpp('OMEMO').set_devicelist(devicelist_)

    def clear_devicelist(self) -> None:
        self.backend.update_devicelist(
            self._own_jid, [self.backend.own_device])
        self.set_devicelist()

    @as_task
    def request_devicelist(self, jid: Optional[str] = None):
        _task = yield  # noqa

        if jid is None:
            jid = self._own_jid

        if jid in self._query_for_devicelists:
            return

        self._query_for_devicelists.append(jid)

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

        if jid in self._query_for_bundles:
            self._query_for_bundles.remove(jid)

        if own_devices:
            if not self.backend.is_own_device_published:
                # Our own device_id is not in the list, it could be
                # overwritten by some other client
                self.set_devicelist(devicelist)

        self._check_for_missing_sessions(jid)

    def _debug_print_stanza(self, stanza: Any) -> None:
        stanzastr = '\n' + stanza.__str__(fancy=True)  # pylint: disable=unnecessary-dunder-call # noqa
        stanzastr = stanzastr[0:-1]
        self._log.debug(stanzastr)
