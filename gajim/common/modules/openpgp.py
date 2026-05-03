# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Final

import random
import secrets
import subprocess
import textwrap
from collections.abc import Generator
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pysequoia as pys
from nbxmpp import Node
from nbxmpp import StanzaMalformed
from nbxmpp.client import Client as nbxmppClient
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.exceptions import StanzaDecrypted
from nbxmpp.modules.openpgp import create_message_stanza
from nbxmpp.modules.openpgp import create_signcrypt_node
from nbxmpp.modules.openpgp import parse_signcrypt
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import EncryptionData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PGPKeyMetadata
from nbxmpp.structs import PGPPublicKey
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import Task

import gajim.common.storage.openpgp.models as mod
from gajim.common import app
from gajim.common import configpaths
from gajim.common import ged
from gajim.common import types
from gajim.common.client import Client
from gajim.common.const import EncryptionInfoMsg
from gajim.common.const import Trust
from gajim.common.events import EncryptionInfo
from gajim.common.events import MucAdded
from gajim.common.events import OpenPGPEvent
from gajim.common.events import SignedIn
from gajim.common.helpers import timeout_add_seconds_once
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.message_util import get_chat_type_and_direction
from gajim.common.modules.util import as_task
from gajim.common.modules.util import CryptoModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import PublicKeyData
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.structs import OutgoingMessage
from gajim.common.util.decorators import cache_with_ttl
from gajim.common.util.decorators import event_filter

NOT_ENCRYPTED_TAGS = [
    ("no-store", Namespace.HINTS),
    ("store", Namespace.HINTS),
    ("no-copy", Namespace.HINTS),
    ("no-permanent-store", Namespace.HINTS),
    ("origin-id", Namespace.SID),
    ("thread", ""),
]
BACKUP_PASSWORD_ALPHABET: Final = "123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"  # noqa: S105


class NoSecretKeyFound(Exception):
    def __init__(self) -> None:
        super().__init__(_("No secret key found"))


class NoSecretKeyImportError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Imported key is not a secret key"))


class SecretKeyExpirationImportError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Imported key has expiration date"))


class MultipleSecretKeysImportError(Exception):
    def __init__(self, secret_certs: list[pys.Cert]) -> None:
        self._secret_certs = secret_certs

    def get_certs(self) -> list[pys.Cert]:
        return self._secret_certs


class BackupDecryptionError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Unable to decrypt the backup with this password"))


class EncryptionTestImportError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Unable to use this key for encrypting messages"))


class DecryptionFailed(Exception):
    pass


def prepare_stanza(stanza: Node, payload: list[Node | str]) -> None:
    delete_nodes(stanza, "openpgp", Namespace.OPENPGP)
    delete_nodes(stanza, "body")

    nodes: list[Node] = []
    for node in payload:
        if isinstance(node, str):
            continue
        name, namespace = node.getName(), node.getNamespace()
        delete_nodes(stanza, name, namespace)
        nodes.append(node)

    for node in nodes:
        stanza.addChild(node=node)


def delete_nodes(stanza: Node, name: str, namespace: str | None = None) -> None:
    attrs = None
    if namespace is not None:
        attrs = {"xmlns": Namespace.OPENPGP}
    nodes = stanza.getTags(name, attrs)
    for node in nodes:
        stanza.delChild(node)


def format_fingerprint(fingerprint: str) -> str:
    fplen = len(fingerprint)
    wordsize = fplen // 8
    buf = ""
    for word in range(0, fplen, wordsize):
        buf += f"{fingerprint[word : word + wordsize]} "
    buf = textwrap.fill(buf, width=28)
    return buf.rstrip()


def find_remote_key(
    public_rows: Sequence[mod.Public], fingerprint: str
) -> mod.Public | None:
    for public in public_rows:
        if public.fingerprint == fingerprint:
            return public


def find_cert_with_fpr(
    certs: list[pys.Cert], fingerprint: str | None
) -> pys.Cert | None:
    if fingerprint is None:
        return certs[0]

    for cert in certs:
        if cert.fingerprint == fingerprint:
            return cert
    return None


@dataclass
class OpenPGPPublicKeyData(PublicKeyData):
    @classmethod
    def from_public(cls, public: mod.Public) -> OpenPGPPublicKeyData:
        return cls(
            active=public.active,
            address=public.remote_jid,
            label=public.label,
            last_seen=public.last_seen,
            fingerprint=public.fingerprint,
            trust=Trust(public.trust),
        )

    def pretty_fingerprint(self) -> str:
        return format_fingerprint(self.fingerprint)


class OpenPGP(BaseModule, CryptoModule):
    _nbxmpp_extends = "OpenPGP"
    _nbxmpp_methods = [
        "set_keylist",
        "request_keylist",
        "set_public_key",
        "request_public_key",
        "set_secret_key",
        "request_secret_key",
    ]

    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self.decrypt_message,
                ns=Namespace.OPENPGP,
                priority=9,
            ),
        ]

        self._register_pubsub_handler(self._keylist_notification_received)
        self.register_events(
            [
                ("signed-in", ged.CORE, self._on_signed_in),
                ("muc-added", ged.PREGUI, self._on_muc_added),
            ]
        )

        self._own_jid = self._get_own_bare_jid()
        self._secret_cert = None
        self._backup_password = None

        self._load_secret_keys()
        self._migrate_secret_keys()

        timeout_add_seconds_once(random.randint(30, 60), self.check_secret_key_backup)

        app.settings.connect_signal(
            "openpgp_backup_secret_key", self._on_backup_settng_changed, self._account
        )

    def _on_backup_settng_changed(self, enabled: bool, *args: Any) -> None:
        if enabled:
            self.check_secret_key_backup()

    def _load_secret_keys(self) -> None:
        if row := app.storage.openpgp.get_secret_key(self._account):
            secret, self._secret_key_date = row
            self._secret_cert = pys.Cert.from_bytes(secret.key)
            self._backup_password = secret.backup_password

            self._log.info(
                "Found secret key: %s, %s",
                self._secret_cert.fingerprint.upper(),
                self._secret_key_date,
            )

    def _migrate_secret_keys(self) -> None:
        if self._secret_cert is not None:
            return

        plugin_data_path = (
            Path(configpaths.get("MY_DATA")) / "openpgp" / str(self._own_jid)
        )
        if not plugin_data_path.exists():
            return

        self._log.info("Try to migrate secret keys from openpgp plugin")

        try:
            result = subprocess.check_output(  # noqa: S603
                [  # noqa: S607
                    "gpg",
                    "--homedir",
                    plugin_data_path.resolve(),
                    "--armor",
                    "--export-secret-key",
                ]
            )
        except Exception as error:
            self._log.warning("Unable to migrate secret keys: %s", error)
            return

        try:
            certs = pys.Cert.split_bytes(result)
        except Exception as error:
            self._log.warning("Failed to convert keys to certs: %s", error)
            return

        for cert in certs:
            user_ids = set(map(str, cert.user_ids))
            if self._own_jid.to_iri() not in user_ids:
                continue

            if not cert.has_secret_keys:
                continue

            assert cert.secrets is not None
            backup_password = self.generate_backup_password()
            app.storage.openpgp.store_secret_key(
                self._account, cert, backup_password=backup_password
            )
            self._log.info(
                "Successfully migrated secret key: %s", cert.fingerprint.upper()
            )
            self._load_secret_keys()
            break

    @event_filter(["account"])
    def _on_signed_in(self, _event: SignedIn) -> None:
        if self.secret_key_exists():
            self.request_keylist()
            self.set_public_key()

    def secret_key_exists(self) -> bool:
        return self._secret_cert is not None

    def generate_key(self) -> None:
        assert self._secret_cert is None
        cert = pys.Cert.generate(
            self._own_jid.to_iri(), profile=pys.Profile.RFC4880, validity_seconds=None
        )
        assert cert.secrets is not None

        backup_password = self.generate_backup_password()
        app.storage.openpgp.store_secret_key(
            self._account, cert, backup_password=backup_password
        )
        self._log.info("Generated key %s", cert.fingerprint.upper())
        self._load_secret_keys()
        self.set_public_key()
        self.request_keylist()
        self.check_secret_key_backup()

    def get_backup_password(self) -> str | None:
        return self._backup_password

    def test_backup_password(self, data: bytes, password: str) -> None:
        try:
            decrypted = pys.decrypt(data, passwords=[password])
        except Exception:
            raise BackupDecryptionError

        if decrypted.bytes is None:
            raise BackupDecryptionError

        pys.Cert.split_bytes(decrypted.bytes)

        self._backup_password = password
        app.storage.openpgp.store_secret_key_backup_password(self._account, password)
        self.check_secret_key_backup()

    def import_key(
        self,
        data: str | bytes,
        backup_password: str | None = None,
        fingerprint: str | None = None,
    ) -> None:
        if self._secret_cert is not None:
            raise ValueError("A secret key already exists")

        if isinstance(data, str):
            data = data.encode()

        if backup_password is not None:
            decrypted = pys.decrypt(data, passwords=[backup_password])
            if decrypted.bytes is None:
                raise NoSecretKeyImportError

            data = decrypted.bytes

        secret_certs = pys.Cert.split_bytes(data)
        self._log.info("Certs in import data: %s", secret_certs)

        if len(secret_certs) > 1 and not fingerprint:
            raise MultipleSecretKeysImportError(secret_certs)

        cert = find_cert_with_fpr(secret_certs, fingerprint)
        if cert is None:
            raise NoSecretKeyImportError

        if not cert.has_secret_keys:
            self._log.warning(
                "Found public key in secret key backup: %s", cert.fingerprint
            )
            raise NoSecretKeyImportError

        if cert.expiration is not None:
            raise SecretKeyExpirationImportError

        assert cert.secrets is not None

        try:
            pys.encrypt(b"", recipients=[cert], signer=cert.secrets.signer())
        except Exception:
            raise EncryptionTestImportError

        user_ids = set(map(str, cert.user_ids))
        if self._own_jid.to_iri() not in user_ids:
            cert = cert.add_user_id(
                value=self._own_jid.to_iri(), certifier=cert.secrets.certifier()
            )

        assert cert.secrets is not None
        if not backup_password:
            backup_password = self.generate_backup_password()

        app.storage.openpgp.store_secret_key(self._account, cert, backup_password)
        self._load_secret_keys()
        self.set_public_key()
        self.request_keylist()
        self.check_secret_key_backup()

    def set_public_key(self) -> None:
        self._log.info("Publish public key")

        assert self._secret_cert is not None
        # Make sure we dont accidentally publish the secret key
        public_cert = pys.Cert.from_bytes(bytes(self._secret_cert))
        assert not public_cert.has_secret_keys

        self._nbxmpp("OpenPGP").set_public_key(
            bytes(public_cert),
            self._secret_cert.fingerprint.upper(),
            self._secret_key_date.timestamp(),
        )

    def request_public_key(self, jid: JID, fingerprint: str) -> None:
        self._log.info("Request public key %s - %s", fingerprint, jid)
        self._nbxmpp("OpenPGP").request_public_key(
            jid, fingerprint, callback=self._public_key_received, user_data=fingerprint
        )

    def _public_key_received(self, task: Task) -> None:
        fingerprint = task.get_user_data()
        try:
            result = cast(PGPPublicKey | None, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            self._log.error("Public Key %s not found: %s", fingerprint, error)
            return

        if result is None:
            self._log.error("Public Key Node %s is empty", fingerprint)
            return

        self._log.info("Received public key: %s", fingerprint)

        try:
            cert = pys.Cert.from_bytes(result.key)
        except Exception:
            self._log.exception("Unable to parse public key")
            return

        user_ids = set(map(str, cert.user_ids))
        if result.jid.to_iri() not in user_ids:
            self._log.warning(
                "Ignore public key because of invalid user id: %s, user ids: %s",
                cert.fingerprint.upper(),
                user_ids,
            )
            return

        trust = Trust.UNDECIDED
        if app.settings.get_account_setting(self._account, "openpgp_blind_trust"):
            trust = Trust.BLIND

        app.storage.openpgp.store_public_key(self._account, result.jid, cert, trust)

    def set_keylist(self, keylist: list[PGPKeyMetadata] | None = None) -> None:
        if keylist is None:
            assert self._secret_cert is not None
            keylist = [
                PGPKeyMetadata(
                    self._own_jid,
                    self._secret_cert.fingerprint.upper(),
                    self._secret_key_date.timestamp(),
                )
            ]

        self._log.info("Publish keylist")
        self._nbxmpp("OpenPGP").set_keylist(keylist)

    @event_node(Namespace.OPENPGP_PK)
    def _keylist_notification_received(
        self, _client: nbxmppClient, _stanza: Node, properties: MessageProperties
    ) -> None:
        assert properties.pubsub_event is not None
        assert properties.jid is not None

        keylist: list[PGPKeyMetadata] = []
        if properties.pubsub_event.data:
            keylist = cast(list[PGPKeyMetadata], properties.pubsub_event.data)

        self._process_keylist(keylist, properties.jid)

    @cache_with_ttl(ttl=7200)
    def _request_keylist_ttl(self, remote_jid: JID) -> None:
        self.request_keylist(remote_jid)

    def request_keylist(self, jid: JID | None = None) -> None:
        if jid is None:
            jid = self._own_jid

        self._log.info("Fetch keylist %s", jid)

        self._nbxmpp("OpenPGP").request_keylist(
            jid, callback=self._keylist_received, user_data=jid
        )

    def _keylist_received(self, task: Task) -> None:
        jid = cast(JID, task.get_user_data())
        try:
            keylist = cast(list[PGPKeyMetadata] | None, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            self._log.error("Keylist query failed: %s", error)
            if self._own_jid.bare_match(jid) and self._secret_cert is not None:
                self.set_keylist()
            return

        self._log.info("Keylist received from %s", jid)
        self._process_keylist(keylist, jid)

    def _validate_active_fingerprints(
        self, keylist: list[PGPKeyMetadata]
    ) -> tuple[set[str], bool]:
        own_fpr_found = False
        active_fprs: set[str] = set()
        for key in keylist:
            if not key.fingerprint.isupper():
                self._log.warning("lower-cased fingerprint: %s", key.fingerprint)
                continue

            if (
                self._secret_cert is not None
                and self._secret_cert.fingerprint.upper() == key.fingerprint
            ):
                # Remove own fingerprint from the list
                own_fpr_found = True
                continue

            active_fprs.add(key.fingerprint)

        return active_fprs, own_fpr_found

    def _process_keylist(
        self, keylist: list[PGPKeyMetadata] | None, from_jid: JID
    ) -> None:

        self._log.info("Received keylist from %s", from_jid)
        own_keylist = self._own_jid.bare_match(from_jid)

        if own_keylist and not self.secret_key_exists():
            self._log.info("Ignore own keylist because no secret key was found")
            return

        if not keylist:
            self._log.info("Keylist is empty")
            if own_keylist:
                self.set_keylist()
            app.storage.openpgp.update_public_keys(
                self._account, from_jid, active=False
            )
            return

        active_fprs, own_fpr_found = self._validate_active_fingerprints(keylist)
        self._log.info("Active keys: %s, own key found: %s", active_fprs, own_fpr_found)

        known_fprs = app.storage.openpgp.get_known_fingerprints(
            self._account, [from_jid]
        )

        unknown_fprs = active_fprs - known_fprs
        inactive_fprs = known_fprs - active_fprs

        if active_fprs:
            app.storage.openpgp.update_public_keys(
                self._account, from_jid, fingerprints=active_fprs, active=True
            )

        if inactive_fprs:
            app.storage.openpgp.update_public_keys(
                self._account, from_jid, fingerprints=inactive_fprs, active=False
            )

        for fingerprint in unknown_fprs:
            self.request_public_key(from_jid, fingerprint)

        if own_keylist and not own_fpr_found:
            assert self._secret_cert is not None
            self._log.info("Own public key not published")
            keylist.append(
                PGPKeyMetadata(
                    self._own_jid,
                    self._secret_cert.fingerprint.upper(),
                    self._secret_key_date.timestamp(),
                )
            )
            self.set_keylist(keylist)

    def _process_muc_message(self, properties: MessageProperties) -> str | None:

        assert properties.jid is not None
        resource = properties.jid.resource
        if properties.muc_ofrom is not None:
            # History Message from MUC
            return properties.muc_ofrom.bare

        contact = self._client.get_module("Contacts").get_contact(properties.jid)
        assert isinstance(contact, GroupchatParticipant)
        if contact.real_jid is not None:
            return contact.real_jid.bare

        self._log.error("Unable to find jid for group chat message from %s", resource)
        return None

    def _get_signer_from_message(
        self, remote_jid: JID, properties: MessageProperties
    ) -> JID | None:
        muc_data = None
        if properties.type.is_groupchat:
            muc_data = self._client.get_module("MUC").get_muc_data(remote_jid)
            if muc_data is None:
                self._log.warning("Groupchat message from unknown MUC: %s", remote_jid)
                return

        _, direction = get_chat_type_and_direction(muc_data, self._own_jid, properties)
        if direction == ChatDirection.OUTGOING:
            return self._own_jid

        if not properties.from_muc:
            return properties.remote_jid

        if properties.mam:
            self._log.info("Message received, archive: %s", properties.mam.archive)
            if properties.muc_user is None or properties.muc_user.jid is None:
                self._log.warning(
                    "Received MAM message which can not be mapped to a real jid"
                )
                return None
            return properties.muc_user.jid.new_as_bare()

        else:
            assert properties.jid is not None
            contact = self._client.get_module("Contacts").get_contact(properties.jid)
            if isinstance(contact, GroupchatParticipant):
                if contact.real_jid is not None:
                    return contact.real_jid.new_as_bare()

    def decrypt_message(
        self, _client: nbxmppClient, stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_openpgp:
            return

        assert properties.openpgp is not None

        if self._secret_cert is None:
            self._log.warning(
                "Received encrypted message but no secret key is available"
            )
            return

        self._log.info("Received encrypted message from %s", properties.jid)

        remote_jid = properties.remote_jid
        assert remote_jid is not None
        assert self._secret_cert.secrets is not None
        assert self._secret_cert.has_secret_keys

        signer_jid = self._get_signer_from_message(remote_jid, properties)
        if signer_jid is None:
            self._log.warning("Unable to determine remote jid for message")
            return

        remote_public_keys = app.storage.openpgp.get_public_keys(
            self._account,
            [signer_jid],
            only_active=False,
        )
        if self._own_jid == signer_jid:
            own_public_key = app.storage.openpgp.get_public_key_from_secret(
                self._account, self._own_jid, self._secret_cert
            )
            remote_public_keys.append(own_public_key)

        def _store(_key_id: list[str]) -> list[pys.Cert]:
            return [public.key for public in remote_public_keys]

        try:
            decrypted = pys.decrypt(
                bytes=properties.openpgp,
                decryptor=self._secret_cert.secrets.decryptor(),
                store=_store,
            )
        except Exception as error:
            self._log.warning(error)
            return

        assert decrypted.bytes is not None
        payload = decrypted.bytes.decode()

        signcrypt = Node(node=payload)

        try:
            payload, recipients, _timestamp = parse_signcrypt(signcrypt)
        except StanzaMalformed as error:
            self._log.warning("Malformed payload: %s", error)
            self._log.warning(payload)
            return

        to_address = self._own_jid
        if properties.type.is_groupchat:
            to_address = remote_jid

        if to_address not in recipients:
            self._log.warning("to attr not valid")
            self._log.warning(signcrypt)
            return

        prepare_stanza(stanza, payload)

        fingerprint = decrypted.valid_sigs[0].certificate.upper()
        remote_key = find_remote_key(remote_public_keys, fingerprint)
        if remote_key is None:
            self._log.warning("Unable to find remote key: %s", fingerprint)
            return

        properties.encrypted = EncryptionData(
            protocol="OpenPGP", key=fingerprint, trust=remote_key.trust
        )

        raise StanzaDecrypted

    def check_send_preconditions(self, contact: types.ChatContactT) -> bool:
        match contact:
            case GroupchatContact():
                if not self._is_compatible_muc(contact.jid):
                    app.ged.raise_event(
                        EncryptionInfo(
                            account=contact.account,
                            jid=contact.jid,
                            type=EncryptionInfoMsg.BAD_MUC_CONFIG,
                            message=EncryptionInfoMsg.BAD_MUC_CONFIG.value.format(
                                encryption="OpenPGP"
                            ),
                        )
                    )
                    return False

                return True

            case BareContact():
                if contact.is_self:
                    return self.secret_key_exists()

                active, undecided = self._remote_has_active_keys(contact.jid)
                if not active:
                    self.request_keylist(contact.jid)
                    app.ged.raise_event(
                        EncryptionInfo(
                            account=contact.account,
                            jid=contact.jid,
                            type=EncryptionInfoMsg.QUERY_DEVICES,
                            message=EncryptionInfoMsg.QUERY_DEVICES.value,
                        )
                    )
                    return False

                if undecided:
                    app.ged.raise_event(
                        EncryptionInfo(
                            account=contact.account,
                            jid=contact.jid,
                            type=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS,
                            message=EncryptionInfoMsg.UNDECIDED_FINGERPRINTS.value,
                        )
                    )
                    return False
                return True

            case _:
                raise ValueError(f"Unhandled contact type: {contact!r}")

    @event_filter(["account"])
    def _on_muc_added(self, event: MucAdded) -> None:
        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.jid)
        if not isinstance(contact, GroupchatContact):
            self._log.warning("%s is not a groupchat contact", contact)
            return

        # Event is triggert on every join, avoid multiple connects
        contact.disconnect_all_from_obj(self)
        contact.connect("room-joined", self._on_muc_event)
        contact.connect("user-affiliation-changed", self._on_muc_event)
        contact.connect("room-affiliation-changed", self._on_muc_event)
        contact.connect("room-affiliations-received", self._on_muc_event)

    def _on_muc_event(
        self, contact: GroupchatContact, _signal_name: str, *args: Any
    ) -> None:

        if not self._is_compatible_muc(contact.jid):
            return

        self._check_groupchat_members_keys(contact.jid)

    def _get_groupchat_members(self, remote_jid: JID) -> set[JID]:
        affiliations = self._client.get_module("MUC").get_affiliations(
            remote_jid, include_outcast=False
        )
        members: set[JID] = set()
        members.update(*affiliations.values())
        return members

    def _check_groupchat_members_keys(self, remote_jid: JID) -> None:
        for jid in self._get_groupchat_members(remote_jid):
            if not self._is_contact_in_roster(jid):
                self._log.info("%s not in roster, query keylist...", jid)
                self._request_keylist_ttl(jid)

    def _is_contact_in_roster(self, remote_jid: JID) -> bool:
        if remote_jid == self._own_jid:
            return True

        roster_item = self._client.get_module("Roster").get_item(remote_jid)
        if roster_item is None:
            return False

        contact = self._client.get_module("Contacts").get_contact(remote_jid)
        assert isinstance(contact, BareContact)
        return contact.subscription == "both"

    def _is_compatible_muc(self, remote_jid: JID) -> bool:
        disco_info = app.storage.cache.get_last_disco_info(remote_jid)
        assert disco_info is not None
        return disco_info.muc_is_members_only and disco_info.muc_is_nonanonymous

    def _remote_has_active_keys(self, remote: JID) -> tuple[bool, bool]:
        public_keys = app.storage.openpgp.get_public_keys(
            self._account,
            [remote],
            trust=[Trust.VERIFIED, Trust.BLIND, Trust.UNDECIDED],
        )
        for key in public_keys:
            if key.trust == Trust.UNDECIDED:
                return True, True

        return bool(public_keys), False

    def encrypt_message(self, message: OutgoingMessage) -> None:
        if self._secret_cert is None:
            raise NoSecretKeyFound

        remote_jid = message.contact.jid

        jids = [self._own_jid]
        if message.is_groupchat:
            jids += self._get_groupchat_members(remote_jid)
        else:
            jids += [remote_jid]

        recipients = app.storage.openpgp.get_public_keys(
            self._account,
            jids,
            trust=[Trust.VERIFIED, Trust.BLIND],
        )

        recipient_certs = [public.key for public in recipients]
        recipient_certs.append(self._secret_cert)

        self._log.info(
            "Encrypt to recipients:\n%s",
            "\n".join([r.fingerprint.upper() for r in recipient_certs]),
        )

        payload = create_signcrypt_node(
            message.get_stanza(), [remote_jid], NOT_ENCRYPTED_TAGS
        )
        payload = str(payload).encode("utf8")

        assert self._secret_cert.secrets is not None

        encrypted_payload = pys.encrypt(
            signer=self._secret_cert.secrets.signer(),
            recipients=recipient_certs,
            bytes=payload,
            armor=False,
        )

        assert encrypted_payload is not None

        create_message_stanza(
            message.get_stanza(), encrypted_payload, bool(message.get_text())
        )

        message.set_encryption(
            EncryptionData(
                protocol="OpenPGP",
                key=self._secret_cert.fingerprint.upper(),
                trust=Trust.VERIFIED,
            )
        )

    def generate_backup_password(self) -> str:
        return "-".join(
            "".join(secrets.choice(BACKUP_PASSWORD_ALPHABET) for _ in range(4))
            for _ in range(6)
        )

    @as_task
    def backup_secret_key(
        self, cert_bytes: bytes | None = None
    ) -> Generator[Any, None]:
        _task = yield  # noqa: F841

        if self._secret_cert is None:
            self._log.info("No secret key found, backup not possible")
            return

        self._log.info("Backup secret key")
        assert self._backup_password is not None

        if cert_bytes is None:
            assert self._secret_cert.secrets is not None
            cert_bytes = bytes(self._secret_cert.secrets)

        # ToDo: This is the armored key, we need it un-armored but this
        # is currently blocked by a missing feature of pysequoia
        encrypted_payload = pys.encrypt(
            passwords=[self._backup_password], bytes=cert_bytes, armor=False
        )

        result = yield self.set_secret_key(encrypted_payload)
        raise_if_error(result)

    def check_secret_key_backup(self) -> None:
        if not app.account_is_available(self._account):
            return

        if not app.settings.get_account_setting(
            self._account, "openpgp_backup_secret_key"
        ):
            return

        self._log.info("Check secret key backup")
        self.request_secret_key(callback=self._secret_key_received)

    def _secret_key_received(self, task: Task) -> None:
        try:
            encrypted_bytes = cast(bytes | None, task.finish())
        except StanzaError as error:
            if error.condition == "item-not-found":
                self.backup_secret_key()
            else:
                self._log.error("Error on secret key request: %s", error)
                if self.secret_key_exists():
                    app.ged.raise_event(
                        OpenPGPEvent(
                            account=self._account,
                            type="unknown-error",
                            error=str(error),
                        )
                    )
            return

        except Exception as error:
            self._log.error("Error on secret key request: %s", error)
            if self.secret_key_exists():
                app.ged.raise_event(
                    OpenPGPEvent(
                        account=self._account, type="unknown-error", error=str(error)
                    )
                )
            return

        if not encrypted_bytes:
            self._log.info("No secret key backup found")
            self.backup_secret_key()
            return

        if not self.secret_key_exists():
            app.ged.raise_event(OpenPGPEvent(self._account, type="setup"))
            return

        if self._backup_password is None:
            self._log.info("Backup password not available, unable to decrypt backup")
            return

        try:
            decrypted = pys.decrypt(
                passwords=[self._backup_password], bytes=encrypted_bytes
            )
        except Exception as error:
            self._log.warning("Unable to decrypt secret key backup: %s", error)
            app.ged.raise_event(OpenPGPEvent(self._account, type="decryption-error"))
            return

        if decrypted.bytes is None:
            self._log.warning("No bytes after decryption")
            self.backup_secret_key()
            return

        secret_certs = pys.Cert.split_bytes(decrypted.bytes)
        self._log.info("Found certs in server backup: %s", secret_certs)

        assert self._secret_cert is not None
        assert self._secret_cert.secrets is not None

        for cert in secret_certs:
            if not cert.has_secret_keys:
                self._log.warning(
                    "Found public key in secret key backup: %s", cert.fingerprint
                )
                continue

            if cert.fingerprint == self._secret_cert.fingerprint:
                self._log.info("Found our secret key server backup")
                return

        self._log.info("Secret key not found in server backup")
        our_cert_bytes = bytes(self._secret_cert.secrets)
        self.backup_secret_key(decrypted.bytes + our_cert_bytes)

    def get_our_public_key(self) -> OpenPGPPublicKeyData | None:
        if self._secret_cert is None:
            return None

        return OpenPGPPublicKeyData(
            active=True,
            address=self._own_jid,
            label=None,
            last_seen=None,
            fingerprint=self._secret_cert.fingerprint.upper(),
            trust=Trust.VERIFIED,
        )

    def get_public_keys(self, jid: JID, *, is_groupchat: bool) -> list[PublicKeyData]:

        trust = [Trust.UNDECIDED] if is_groupchat else None
        public_key_data = app.storage.openpgp.get_public_keys(
            self._account, [jid], trust=trust, only_active=False
        )
        return [OpenPGPPublicKeyData.from_public(public) for public in public_key_data]

    def compose_trust_uri(self, jid: JID) -> str:
        return ""

    def remove_public_key(self, public_key_data: PublicKeyData) -> None:
        app.storage.openpgp.remove_public_key(
            self._account, public_key_data.address, public_key_data.fingerprint
        )

    def set_public_key_trust(
        self, public_key_data: PublicKeyData, trust: Trust
    ) -> None:
        app.storage.openpgp.update_public_keys(
            self._account,
            public_key_data.address,
            [public_key_data.fingerprint],
            trust=trust,
        )

    def clear_fingerprints(self) -> None:
        self.set_keylist()
