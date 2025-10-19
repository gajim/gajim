# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Message Util module

from __future__ import annotations

from typing import Literal

from datetime import datetime
from datetime import UTC

import nbxmpp.structs
from nbxmpp.modules.security_labels import SecurityLabel
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties

from gajim.common.const import EME_MESSAGES
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.structs import MUCData
from gajim.common.structs import ReplyData

UNKNOWN_MESSAGE = _('Message content unknown')


def get_eme_message(eme_data: nbxmpp.structs.EMEData) -> str:
    try:
        return EME_MESSAGES[eme_data.namespace]
    except KeyError:
        return EME_MESSAGES['fallback'] % eme_data.name


def get_chat_type_and_direction(
    muc_data: MUCData | None, own_jid: JID, properties: MessageProperties
) -> tuple[MessageType, ChatDirection]:

    assert properties.jid is not None
    if properties.type.is_groupchat:
        assert muc_data is not None
        direction = ChatDirection.INCOMING
        if muc_data.occupant_id is not None:
            if muc_data.occupant_id == properties.occupant_id:
                direction = ChatDirection.OUTGOING

        elif muc_data.nick == properties.jid.resource:
            direction = ChatDirection.OUTGOING

        return MessageType.GROUPCHAT, direction

    assert properties.from_ is not None
    if properties.from_.bare_match(own_jid):
        direction = ChatDirection.OUTGOING
    else:
        direction = ChatDirection.INCOMING

    if properties.is_muc_pm:
        return MessageType.PM, direction

    return MessageType.CHAT, direction


def get_real_jid(
    properties: MessageProperties,
    contact: GroupchatParticipant,
) -> JID | None:

    if properties.is_mam_message:
        if properties.muc_user is None:
            return None
        return properties.muc_user.jid

    real_jid = contact.real_jid
    if real_jid is None:
        return None
    return real_jid.new_as_bare()


def get_occupant_info(
    account: str,
    remote_jid: JID,
    own_bare_jid: JID,
    direction: ChatDirection,
    timestamp: datetime,
    contact: GroupchatParticipant,
    properties: MessageProperties,
) -> mod.Occupant | None:

    assert properties.jid is not None
    if properties.jid.is_bare:
        return None

    if direction == ChatDirection.OUTGOING:
        real_jid = own_bare_jid
    else:
        real_jid = get_real_jid(properties, contact)

    occupant_id = get_occupant_id(contact, properties) or real_jid
    if occupant_id is None:
        return None

    resource = properties.jid.resource
    assert resource is not None

    occupant = mod.Occupant(
        account_=account,
        remote_jid_=remote_jid.new_as_bare(),
        id=str(occupant_id),
        real_remote_jid_=real_jid or VALUE_MISSING,
        nickname=resource,
        updated_at=timestamp,
    )

    if contact.avatar_sha is not None:
        # avatar_sha is only available if we have presence from this contact
        # We don’t want to overwrite the previous avatar
        occupant.avatar_sha = contact.avatar_sha

    return occupant


def get_occupant_id(
    contact: GroupchatParticipant, properties: MessageProperties
) -> str | None:

    if not properties.occupant_id:
        return None

    if contact.room.supports(Namespace.OCCUPANT_ID):
        return properties.occupant_id
    return None


def get_message_timestamp(properties: MessageProperties) -> datetime:
    timestamp = properties.timestamp
    if properties.mam is not None:
        timestamp = properties.mam.timestamp
    return datetime.fromtimestamp(timestamp, tz=UTC)


def convert_message_type(type_: MessageType) -> Literal['chat', 'groupchat']:
    if type_ in (MessageType.CHAT, MessageType.PM):
        return 'chat'
    return 'groupchat'


def get_nickname_from_message(message: mod.Message) -> str:
    if message.resource is None:
        nickname = message.remote.jid.localpart
        assert nickname is not None
        return nickname

    if message.occupant is not None:
        nickname = message.occupant.nickname
        assert nickname is not None
        return nickname

    nickname = message.resource
    assert nickname is not None
    return nickname


def get_security_label(
    account: str, remote_jid: JID, timestamp: datetime, label: SecurityLabel | None
) -> mod.SecurityLabel | None:
    if label is None:
        return None

    displaymarking = label.displaymarking
    if displaymarking is None:
        return None

    return mod.SecurityLabel(
        account_=account,
        remote_jid_=remote_jid,
        label_hash=label.get_label_hash(),
        displaymarking=displaymarking.name,
        fgcolor=displaymarking.fgcolor,
        bgcolor=displaymarking.bgcolor,
        updated_at=timestamp,
    )


def get_reply(data: nbxmpp.structs.ReplyData | ReplyData | None) -> mod.Reply | None:
    if data is None:
        return None

    return mod.Reply(id=data.id, to=data.to)
