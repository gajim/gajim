# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Message Util module

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import EMEData
from nbxmpp.structs import MessageProperties

from gajim.common.const import EME_MESSAGES
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.structs import MUCData


def get_eme_message(eme_data: EMEData) -> str:
    try:
        return EME_MESSAGES[eme_data.namespace]
    except KeyError:
        return EME_MESSAGES['fallback'] % eme_data.name


def get_chat_type_and_direction(
    muc_data: MUCData | None, own_jid: JID, properties: MessageProperties
) -> tuple[MessageType, ChatDirection]:

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

    if not properties.type.is_chat:
        raise ValueError('Invalid message type', properties.type)

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
    properties: MessageProperties
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

    return mod.Occupant(
        account_=account,
        remote_jid_=remote_jid,
        id=str(occupant_id),
        real_remote_jid_=real_jid or VALUE_MISSING,
        nickname=resource,
        updated_at=timestamp,
    )


def get_occupant_id(
    contact: GroupchatParticipant,
    properties: MessageProperties
) -> str | None:

    if not properties.occupant_id:
        return None

    if contact.room.supports(Namespace.OCCUPANT_ID):
        return properties.occupant_id
    return None


def get_message_timestamp(
    properties: MessageProperties
) -> datetime:
    timestamp = properties.timestamp
    if properties.is_mam_message:
        timestamp = properties.mam.timestamp
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def convert_message_type(type_: MessageType) -> str:
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
