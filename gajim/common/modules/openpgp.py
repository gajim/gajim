# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import datetime as dt
import secrets
import subprocess
import textwrap
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
from gajim.common.const import Trust
from gajim.common.events import SignedIn
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.util import event_node
from gajim.common.structs import OutgoingMessage
from gajim.common.util.decorators import event_filter

NOT_ENCRYPTED_TAGS = [
    ("no-store", Namespace.HINTS),
    ("store", Namespace.HINTS),
    ("no-copy", Namespace.HINTS),
    ("no-permanent-store", Namespace.HINTS),
    ("origin-id", Namespace.SID),
    ("thread", ""),
]


class NoSecretKeyFound(Exception):
    def __init__(self) -> None:
        super().__init__(_("No secret key found"))


class NoSecretKeyImportError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Imported key is not a secret key"))


class SecretKeyExpirationImportError(Exception):
    def __init__(self) -> None:
        super().__init__(_("Imported key has expiration date"))


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
    return buf.rstrip().upper()


def find_remote_key(
    public_rows: Sequence[mod.Public], fingerprint: str
) -> mod.Public | None:
    for public in public_rows:
        if public.fingerprint == fingerprint:
            return public


@dataclass
class OpenPGPPublicKeyData:
    active: bool
    address: JID
    label: str | None
    last_seen: dt.datetime | None
    fingerprint: str
    trust: Trust

    @classmethod
    def from_public(cls, public: mod.Public) -> OpenPGPPublicKeyData:
        return cls(
            active=public.active,
            address=public.jid,
            label=public.label,
            last_seen=public.last_seen,
            fingerprint=public.fingerprint,
            trust=Trust(public.trust),
        )

    def pretty_fingerprint(self) -> str:
        return format_fingerprint(self.fingerprint)


class OpenPGP(BaseModule):
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
            ]
        )

        self._own_jid = self._get_own_bare_jid()
        self._secret_cert = None

        self._load_secret_keys()
        self._migrate_secret_keys()

    def _load_secret_keys(self) -> None:
        if secret_key := app.storage.openpgp.get_secret_key(self._own_jid):
            self._secret_cert, self._secret_key_date = secret_key
            self._log.info(
                "Found secret key: %s, %s",
                self._secret_cert.fingerprint,
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
            app.storage.openpgp.store_secret_key(self._own_jid, cert.secrets)
            self._log.info("Successfully migrated secret key: %s", cert.fingerprint)
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
        cert = pys.Cert.generate(self._own_jid.to_iri(), profile=pys.Profile.RFC4880)
        assert cert.secrets is not None

        # Workaround because pysequoia allows not to generate certs
        # without expiration
        cert = cert.set_expiration(
            dt.datetime(year=2099, month=12, day=31, tzinfo=dt.UTC),
            certifier=cert.secrets.certifier(),
        )
        assert cert.secrets is not None

        app.storage.openpgp.store_secret_key(self._own_jid, cert.secrets)
        self._log.info("Generated key %s", cert.fingerprint)
        self._load_secret_keys()
        self.set_public_key()

    def import_key(self, data: str | bytes, password: str | None = None) -> None:
        if self._secret_cert is not None:
            raise ValueError("A secret key already exists")

        if isinstance(data, str):
            data = data.encode()

        if password is not None:
            decrypted = pys.decrypt(data, passwords=[password])
            assert decrypted.bytes is not None
            data = decrypted.bytes

        cert = pys.Cert.from_bytes(data)
        if not cert.has_secret_keys:
            raise NoSecretKeyImportError

        if cert.expiration is not None:
            raise SecretKeyExpirationImportError

        assert cert.secrets is not None
        # Test encrypt message to check if key is encrypted
        pys.encrypt(b"", recipients=[cert], signer=cert.secrets.signer())

        user_ids = set(map(str, cert.user_ids))
        if self._own_jid.to_iri() not in user_ids:
            cert = cert.add_user_id(
                value=self._own_jid.to_iri(), certifier=cert.secrets.certifier()
            )

        assert cert.secrets is not None
        app.storage.openpgp.store_secret_key(self._own_jid, cert.secrets)
        self._load_secret_keys()
        self.set_public_key()

    def set_public_key(self) -> None:
        self._log.info("Publish public key")

        assert self._secret_cert is not None
        # Make sure we dont accidentally publish the secret key
        public_cert = pys.Cert.from_bytes(bytes(self._secret_cert))
        assert not public_cert.has_secret_keys

        self._nbxmpp("OpenPGP").set_public_key(
            bytes(public_cert),
            self._secret_cert.fingerprint,
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
                cert.fingerprint,
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
                    self._secret_cert.fingerprint,
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

    def _process_keylist(
        self, keylist: list[PGPKeyMetadata] | None, from_jid: JID
    ) -> None:

        if self._own_jid.bare_match(from_jid):
            self._process_own_keylist(keylist)
            return

        self._log.info("Received keylist from %s", from_jid)

        if not keylist:
            self._log.info("Keylist is empty")
            return

        known_fingerprints = app.storage.openpgp.get_fingerprints(
            self._account, [from_jid]
        )

        for key in keylist:
            if not key.fingerprint.isupper():
                self._log.warning("lower-cased fingerprint: %s", key.fingerprint)
                continue

            self._log.info(key.fingerprint)
            if key.fingerprint not in known_fingerprints:
                self.request_public_key(from_jid, key.fingerprint)

    def _process_own_keylist(self, keylist: list[PGPKeyMetadata] | None) -> None:
        self._log.info("Received own keylist")
        if self._secret_cert is None:
            self._log.info("No secret key available, ignore own keylist")
            return

        if not keylist:
            self._log.warning("Our keylist is empty")
            self.set_keylist()
            return

        is_key_published = False
        for key in keylist:
            if not key.fingerprint.isupper():
                self._log.warning("lower-cased fingerprint: %s", key.fingerprint)
                continue

            self._log.info(key.fingerprint)

            if key.fingerprint == self._secret_cert.fingerprint.upper():
                self._log.info("Own fingerprint found in keys list")
                is_key_published = True

        if is_key_published:
            return

        self._log.info("Own fingerprint not published")
        keylist.append(
            PGPKeyMetadata(
                self._own_jid,
                self._secret_cert.fingerprint,
                self._secret_key_date.timestamp(),
            )
        )
        self.set_keylist(keylist)

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

        remote_public_keys = app.storage.openpgp.get_public_keys(
            self._account, [remote_jid]
        )

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
            self._log.warning("Decryption failed: %s", error)
            self._log.warning(payload)
            return

        if not any(map(self._own_jid.bare_match, recipients)):
            self._log.warning("to attr not valid")
            self._log.warning(signcrypt)
            return

        prepare_stanza(stanza, payload)

        fingerprint = decrypted.valid_sigs[0].certificate
        remote_key = find_remote_key(remote_public_keys, fingerprint)
        if remote_key is None:
            self._log.warning("Unable to find remote key: %s", fingerprint)
            return

        properties.encrypted = EncryptionData(
            protocol="OpenPGP", key=fingerprint, trust=remote_key.trust
        )

        raise StanzaDecrypted

    def check_send_preconditions(self, contact: types.ChatContactT) -> bool:
        # jid = str(contact.jid)
        if self._secret_cert is None:
            return False

        if isinstance(contact, GroupchatContact):  # noqa: SIM103
            return False
        return True

    def encrypt_message(self, message: OutgoingMessage) -> None:
        if self._secret_cert is None:
            raise NoSecretKeyFound

        remote_jid = message.contact.jid

        recipients: list[mod.Public] = []
        recipients += app.storage.openpgp.get_public_keys(
            self._account,
            [self._own_jid, remote_jid],
            trust=[Trust.VERIFIED, Trust.BLIND],
        )

        recipient_certs = [public.key for public in recipients]
        recipient_certs.append(self._secret_cert)

        self._log.info(
            "Encrypt to recipients:\n%s",
            "\n".join([r.fingerprint for r in recipient_certs]),
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
                key=self._secret_cert.fingerprint,
                trust=Trust.VERIFIED,
            )
        )

    def backup_secret_key(self) -> None:
        if self._secret_cert is None:
            raise NoSecretKeyFound

        alphabet = "123456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
        password = "-".join(
            "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(6)
        )

        # ToDo: This is the armored key, we need it un-armored but this
        # is currently blocked by a missing feature of pysequoia
        cert_bytes = str(self._secret_cert.secrets).encode()
        encrypted_payload = pys.encrypt(
            passwords=[password], bytes=cert_bytes, armor=False
        )
        self.set_secret_key(encrypted_payload)

    def get_our_public_key(self) -> OpenPGPPublicKeyData:
        assert self._secret_cert is not None

        return OpenPGPPublicKeyData(
            active=True,
            address=self._own_jid,
            label=None,
            last_seen=None,
            fingerprint=self._secret_cert.fingerprint,
            trust=Trust.VERIFIED,
        )

    def get_public_keys(
        self, jid: JID, *, is_groupchat: bool
    ) -> list[OpenPGPPublicKeyData]:

        trust = [Trust.UNDECIDED] if is_groupchat else None
        public_key_data = app.storage.openpgp.get_public_keys(
            self._account, [jid], trust=trust, only_active=False
        )
        return [OpenPGPPublicKeyData.from_public(public) for public in public_key_data]

    def compose_trust_uri(self, jid: JID) -> None:
        return None

    def remove_public_key(self, public_key_data: OpenPGPPublicKeyData) -> None:
        app.storage.openpgp.remove_public_key(
            self._account, public_key_data.address, public_key_data.fingerprint
        )

    def set_public_key_trust(
        self, public_key_data: OpenPGPPublicKeyData, trust: Trust
    ) -> None:
        app.storage.openpgp.update_public_key(
            self._account,
            public_key_data.address,
            public_key_data.fingerprint,
            trust=trust,
        )

    def clear_fingerprints(self) -> None:
        self.set_keylist()
