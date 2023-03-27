# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2015 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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

from __future__ import annotations

from typing import Any
from typing import Optional

import time
from collections import defaultdict
from pathlib import Path

from nbxmpp.structs import OMEMOBundle
from nbxmpp.structs import OMEMOMessage
from omemo_dr.ecc.djbec import CurvePublicKey
from omemo_dr.exceptions import DuplicateMessageException
from omemo_dr.identitykey import IdentityKey
from omemo_dr.identitykeypair import IdentityKeyPair
from omemo_dr.protocol.prekeywhispermessage import PreKeyWhisperMessage
from omemo_dr.protocol.whispermessage import WhisperMessage
from omemo_dr.sessionbuilder import SessionBuilder
from omemo_dr.sessioncipher import SessionCipher
from omemo_dr.state.prekeybundle import PreKeyBundle
from omemo_dr.util.keyhelper import KeyHelper

from gajim.common import app
from gajim.common import configpaths
from gajim.common import types
from gajim.common.omemo.aes import aes_decrypt
from gajim.common.omemo.aes import aes_encrypt
from gajim.common.omemo.aes import get_new_iv
from gajim.common.omemo.aes import get_new_key
from gajim.common.omemo.util import DEFAULT_PREKEY_AMOUNT
from gajim.common.omemo.util import get_fingerprint
from gajim.common.omemo.util import MIN_PREKEY_AMOUNT
from gajim.common.omemo.util import SPK_ARCHIVE_TIME
from gajim.common.omemo.util import SPK_CYCLE_TIME
from gajim.common.omemo.util import Trust
from gajim.common.omemo.util import UNACKNOWLEDGED_COUNT
from gajim.common.storage.omemo import OMEMOStorage


class OmemoState:
    def __init__(self,
                 account: str,
                 own_jid: str,
                 xmpp_con: types.xmppClient
                 ) -> None:

        self._account = account
        self._own_jid = own_jid
        self._log = xmpp_con._log
        self._session_ciphers: dict[
            str, dict[int, SessionCipher]] = defaultdict(dict)

        data_dir = Path(configpaths.get('MY_DATA'))
        db_path = data_dir / f'omemo_{self._own_jid}.db'
        self._storage = OMEMOStorage(account, db_path, self._log)

        self.xmpp_con = xmpp_con

        self._log.info('%s PreKeys available',
                       self._storage.getPreKeyCount())

        self._device_store: dict[str, set[int]] = defaultdict(set)
        self._muc_member_store: dict[str, set[str]] = defaultdict(set)

        reg_id = self._storage.getLocalRegistrationId()
        if reg_id is None:
            raise ValueError('No own device found')

        self._own_device = reg_id
        self.add_device(self._own_jid, self._own_device)
        self._log.info('Our device id: %s', self._own_device)

        for jid, device in self._storage.getActiveDeviceTuples():
            self._log.info('Load device from storage: %s - %s', jid, device)
            self.add_device(jid, device)

    def build_session(self,
                      jid: str,
                      device_id: int,
                      bundle: OMEMOBundle
                      ) -> None:

        session = SessionBuilder(self._storage, self._storage, self._storage,
                                 self._storage, jid, device_id)

        registration_id = self._storage.getLocalRegistrationId()

        prekey = bundle.pick_prekey()
        otpk = CurvePublicKey(prekey['key'][1:])

        spk = CurvePublicKey(bundle.spk['key'][1:])
        ik = IdentityKey(CurvePublicKey(bundle.ik[1:]))

        prekey_bundle = PreKeyBundle(registration_id,
                                     device_id,
                                     prekey['id'],
                                     otpk,
                                     bundle.spk['id'],
                                     spk,
                                     bundle.spk_signature,
                                     ik)

        session.processPreKeyBundle(prekey_bundle)
        self._get_session_cipher(jid, device_id)

    @property
    def storage(self) -> OMEMOStorage:
        return self._storage

    @property
    def own_fingerprint(self) -> str:
        return get_fingerprint(self._storage.getIdentityKeyPair())

    @property
    def bundle(self) -> OMEMOBundle:
        self._check_pre_key_count()

        bundle: dict[str, Any] = {'otpks': []}
        for k in self._storage.loadPendingPreKeys():
            key = k.getKeyPair().getPublicKey().serialize()
            bundle['otpks'].append({'key': key, 'id': k.getId()})

        ik_pair = self._storage.getIdentityKeyPair()
        bundle['ik'] = ik_pair.getPublicKey().serialize()

        self._cycle_signed_pre_key(ik_pair)

        spk = self._storage.loadSignedPreKey(
            self._storage.getCurrentSignedPreKeyId())
        bundle['spk_signature'] = spk.getSignature()
        bundle['spk'] = {'key': spk.getKeyPair().getPublicKey().serialize(),
                         'id': spk.getId()}

        return OMEMOBundle(**bundle)

    def decrypt_message(self,
                        omemo_message: OMEMOMessage,
                        jid: str
                        ) -> tuple[str, str, Trust]:

        if omemo_message.sid == self.own_device:
            self._log.info('Received previously sent message by us')
            raise SelfMessage

        try:
            encrypted_key, prekey = omemo_message.keys[self.own_device]
        except KeyError:
            self._log.info('Received message not for our device')
            raise MessageNotForDevice

        try:
            if prekey:
                key, fingerprint, trust = self._process_pre_key_message(
                    jid, omemo_message.sid, encrypted_key)
            else:
                key, fingerprint, trust = self._process_message(
                    jid, omemo_message.sid, encrypted_key)

        except DuplicateMessageException:
            self._log.info('Received duplicated message')
            raise DuplicateMessage

        except Exception as error:
            self._log.warning(error)
            raise DecryptionFailed

        if omemo_message.payload is None:
            self._log.debug('Decrypted Key Exchange Message')
            raise KeyExchangeMessage

        try:
            result = aes_decrypt(key, omemo_message.iv, omemo_message.payload)
        except Exception as error:
            self._log.warning(error)
            raise DecryptionFailed

        self._log.debug('Decrypted Message => %s', result)
        return result, fingerprint, trust

    def _get_whisper_message(self,
                             jid: str,
                             device: int,
                             key: bytes
                             ) -> tuple[bytes, bool]:

        cipher = self._get_session_cipher(jid, device)
        cipher_key = cipher.encrypt(key)
        prekey = isinstance(cipher_key, PreKeyWhisperMessage)
        return cipher_key.serialize(), prekey

    def encrypt(self, jid: str, plaintext: str) -> Optional[OMEMOMessage]:
        try:
            devices_for_encryption = self.get_devices_for_encryption(jid)
        except NoDevicesFound:
            self._log.warning('No devices for encryption found for: %s', jid)
            return

        result = aes_encrypt(plaintext)
        whisper_messages: dict[
            str, dict[int, tuple[bytes, bool]]] = defaultdict(dict)

        for jid_, device in devices_for_encryption:
            count = self._storage.getUnacknowledgedCount(jid_, device)
            if count >= UNACKNOWLEDGED_COUNT:
                self._log.warning('Set device inactive %s because of %s '
                                  'unacknowledged messages', device, count)
                self.remove_device(jid_, device)

            try:
                whisper_messages[jid_][device] = self._get_whisper_message(
                    jid_, device, result.key)
            except Exception:
                self._log.exception('Failed to encrypt')
                continue

        recipients = set(whisper_messages.keys())
        if jid != self._own_jid:
            recipients -= {self._own_jid}
        if not recipients:
            self._log.error('Encrypted keys empty')
            return

        encrypted_keys: dict[int, tuple[bytes, bool]] = {}
        for jid_ in whisper_messages:
            encrypted_keys.update(whisper_messages[jid_])

        self._log.debug('Finished encrypting message')
        return OMEMOMessage(sid=self.own_device,
                            keys=encrypted_keys,
                            iv=result.iv,
                            payload=result.payload)

    def encrypt_key_transport(self,
                              jid: str,
                              devices: list[int]
                              ) -> Optional[OMEMOMessage]:

        whisper_messages: dict[
            str, dict[int, tuple[bytes, bool]]] = defaultdict(dict)
        for device in devices:
            try:
                whisper_messages[jid][device] = self._get_whisper_message(
                    jid, device, get_new_key())
            except Exception:
                self._log.exception('Failed to encrypt')
                continue

        if not whisper_messages[jid]:
            self._log.error('Encrypted keys empty')
            return

        self._log.debug('Finished Key Transport message')
        return OMEMOMessage(sid=self.own_device,
                            keys=whisper_messages[jid],
                            iv=get_new_iv(),
                            payload=None)

    def has_trusted_keys(self, jid: str) -> bool:
        inactive = self._storage.getInactiveSessionsKeys(jid)
        trusted = self._storage.getTrustedFingerprints(jid)
        return bool(set(trusted) - set(inactive))

    def devices_without_sessions(self, jid: str) -> list[int]:
        known_devices = self.get_devices(jid, without_self=True)
        missing_devices = [dev
                           for dev in known_devices
                           if not self._storage.containsSession(jid, dev)]
        if missing_devices:
            self._log.info('Missing device sessions for %s: %s',
                           jid, missing_devices)
        return missing_devices

    def _get_session_cipher(self, jid: str, device_id: int) -> SessionCipher:
        try:
            return self._session_ciphers[jid][device_id]
        except KeyError:
            cipher = SessionCipher(self._storage, self._storage, self._storage,
                                   self._storage, jid, device_id)
            self._session_ciphers[jid][device_id] = cipher
            return cipher

    def _process_pre_key_message(self,
                                 jid: str,
                                 device: int,
                                 key: bytes
                                 ) -> tuple[bytes, str, Trust]:

        self._log.info('Process pre key message from %s', jid)
        pre_key_message = PreKeyWhisperMessage.from_bytes(key)
        if not pre_key_message.getPreKeyId():
            raise Exception('Received Pre Key Message '
                            'without PreKey => %s' % jid)

        session_cipher = self._get_session_cipher(jid, device)
        key = session_cipher.decryptPkmsg(pre_key_message)

        identity_key = pre_key_message.getIdentityKey()
        trust = self._get_trust_from_identity_key(jid, identity_key)
        fingerprint = get_fingerprint(identity_key)

        self._storage.setIdentityLastSeen(jid, identity_key)

        self.xmpp_con.set_bundle()
        self.add_device(jid, device)
        return key, fingerprint, trust

    def _process_message(self,
                         jid: str,
                         device: int,
                         key: bytes
                         ) -> tuple[bytes, str, Trust]:

        self._log.info('Process message from %s', jid)
        message = WhisperMessage.from_bytes(key)

        session_cipher = self._get_session_cipher(jid, device)
        key = session_cipher.decryptMsg(message)

        identity_key = self._get_identity_key_from_device(jid, device)
        trust = self._get_trust_from_identity_key(jid, identity_key)
        fingerprint = get_fingerprint(identity_key)

        self._storage.setIdentityLastSeen(jid, identity_key)

        self.add_device(jid, device)

        return key, fingerprint, trust

    @staticmethod
    def _get_identity_key_from_pk_message(key):
        pre_key_message = PreKeyWhisperMessage.from_bytes(key)
        return pre_key_message.getIdentityKey()

    def _get_identity_key_from_device(self,
                                      jid: str,
                                      device: int
                                      ) -> Optional[IdentityKey]:

        session_record = self._storage.loadSession(jid, device)
        return session_record.getSessionState().getRemoteIdentityKey()

    def _get_trust_from_identity_key(self,
                                     jid: str,
                                     identity_key: IdentityKey
                                     ) -> Trust:

        trust = self._storage.getTrustForIdentity(jid, identity_key)
        return Trust(trust) if trust is not None else Trust.UNDECIDED

    def _check_pre_key_count(self) -> None:
        # Check if enough PreKeys are available
        pre_key_count = self._storage.getPreKeyCount()
        if pre_key_count < MIN_PREKEY_AMOUNT:
            missing_count = DEFAULT_PREKEY_AMOUNT - pre_key_count
            self._storage.generateNewPreKeys(missing_count)
            self._log.info('%s PreKeys created', missing_count)

    def _cycle_signed_pre_key(self, ik_pair: IdentityKeyPair) -> None:
        # Publish every SPK_CYCLE_TIME a new SignedPreKey
        # Delete all existing SignedPreKeys that are older
        # then SPK_ARCHIVE_TIME

        # Check if SignedPreKey exist and create if not
        if not self._storage.getCurrentSignedPreKeyId():
            spk = KeyHelper.generateSignedPreKey(
                ik_pair, self._storage.getNextSignedPreKeyId())
            self._storage.storeSignedPreKey(spk.getId(), spk)
            self._log.debug('New SignedPreKey created, because none existed')

        # if SPK_CYCLE_TIME is reached, generate a new SignedPreKey
        now = int(time.time())
        timestamp = self._storage.getSignedPreKeyTimestamp(
            self._storage.getCurrentSignedPreKeyId())

        if int(timestamp) < now - SPK_CYCLE_TIME:
            spk = KeyHelper.generateSignedPreKey(
                ik_pair, self._storage.getNextSignedPreKeyId())
            self._storage.storeSignedPreKey(spk.getId(), spk)
            self._log.debug('Cycled SignedPreKey')

        # Delete all SignedPreKeys that are older than SPK_ARCHIVE_TIME
        timestamp = now - SPK_ARCHIVE_TIME
        self._storage.removeOldSignedPreKeys(timestamp)

    def update_devicelist(self, jid: str, devicelist: list[int]) -> None:
        for device in list(devicelist):
            if device == self.own_device:
                continue
            count = self._storage.getUnacknowledgedCount(jid, device)
            if count > UNACKNOWLEDGED_COUNT:
                self._log.warning('Ignore device because of %s unacknowledged'
                                  ' messages: %s %s', count, jid, device)
                devicelist.remove(device)

        self._device_store[jid] = set(devicelist)
        self._log.info('Saved devices for %s', jid)
        self._storage.setActiveState(jid, devicelist)

    def add_muc_member(self, room_jid: str, jid: str) -> None:
        self._log.info('Saved MUC member %s %s', room_jid, jid)
        self._muc_member_store[room_jid].add(jid)

    def remove_muc_member(self, room_jid: str, jid: str) -> None:
        self._log.info('Removed MUC member %s %s', room_jid, jid)
        self._muc_member_store[room_jid].discard(jid)

    def get_muc_members(self,
                        room_jid: str,
                        without_self: bool = True
                        ) -> set[str]:

        members = set(self._muc_member_store[room_jid])
        if without_self:
            members.discard(self._own_jid)
        return members

    def add_device(self, jid: str, device: int) -> None:
        self._device_store[jid].add(device)

    def remove_device(self, jid: str, device: int) -> None:
        self._device_store[jid].discard(device)
        self._storage.setInactive(jid, device)

    def get_devices(self, jid: str, without_self: bool = False) -> set[int]:
        devices = set(self._device_store[jid])
        if without_self:
            devices.discard(self.own_device)
        return devices

    def get_devices_for_encryption(self, jid: str) -> set[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []

        client = app.get_client(self._account)
        contact = client.get_module('Contacts').get_contact(jid)
        if contact.is_groupchat:
            devices_for_encryption = self._get_devices_for_muc_encryption(jid)
        else:
            devices_for_encryption = self._get_devices_for_encryption(jid)

        if not devices_for_encryption:
            raise NoDevicesFound

        devices_for_encryption += self._get_own_devices_for_encryption()
        return set(devices_for_encryption)

    def _get_devices_for_muc_encryption(self,
                                        jid: str
                                        ) -> list[tuple[str, int]]:

        devices_for_encryption: list[tuple[str, int]] = []
        for jid_ in self._muc_member_store[jid]:
            devices_for_encryption += self._get_devices_for_encryption(jid_)
        return devices_for_encryption

    def _get_own_devices_for_encryption(self) -> list[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []
        own_devices = self.get_devices(self._own_jid, without_self=True)
        for device in own_devices:
            if self._storage.isTrusted(self._own_jid, device):
                devices_for_encryption.append((self._own_jid, device))
        return devices_for_encryption

    def _get_devices_for_encryption(self, jid: str) -> list[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []
        devices = self.get_devices(jid)

        for device in devices:
            if self._storage.isTrusted(jid, device):
                devices_for_encryption.append((jid, device))
        return devices_for_encryption

    @property
    def own_device(self) -> int:
        return self._own_device

    @property
    def devices_for_publish(self) -> set[int]:
        devices = self.get_devices(self._own_jid)
        if self.own_device not in devices:
            devices.add(self.own_device)
        return devices

    @property
    def is_own_device_published(self) -> bool:
        return self.own_device in self.get_devices(self._own_jid)


class NoDevicesFound(Exception):
    pass


class NoValidSessions(Exception):
    pass


class SelfMessage(Exception):
    pass


class MessageNotForDevice(Exception):
    pass


class DecryptionFailed(Exception):
    pass


class KeyExchangeMessage(Exception):
    pass


class InvalidMessage(Exception):
    pass


class DuplicateMessage(Exception):
    pass
