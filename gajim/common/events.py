# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import Any
from typing import Union

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from functools import cached_property

from nbxmpp.const import Affiliation
from nbxmpp.const import InviteType
from nbxmpp.const import Role
from nbxmpp.const import StatusCode
from nbxmpp.modules.security_labels import Catalog
from nbxmpp.protocol import JID
from nbxmpp.structs import HTTPAuthData
from nbxmpp.structs import LocationData
from nbxmpp.structs import RosterItem
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common.const import EncryptionInfoMsg
from gajim.common.const import JingleState
from gajim.common.file_props import FileProp
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import MessageType

if typing.TYPE_CHECKING:
    from gajim.common.client import Client
    from gajim.common.modules.httpupload import HTTPFileTransfer

ChatListEventT = Union[
    'MessageReceived',
    'MessageCorrected',
    'MessageModerated',
    'PresenceReceived',
    'MessageSent',
    'MessageDeleted',
    'JingleRequestReceived',
    'FileRequestReceivedEvent'
]


@dataclass
class ApplicationEvent:
    name: str


@dataclass
class StyleChanged(ApplicationEvent):
    name: str = field(init=False, default='style-changed')


@dataclass
class ThemeUpdate(ApplicationEvent):
    name: str = field(init=False, default='theme-update')


@dataclass
class ShowChanged(ApplicationEvent):
    name: str = field(init=False, default='our-show')
    account: str
    show: str


@dataclass
class AccountConnected(ApplicationEvent):
    name: str = field(init=False, default='account-connected')
    account: str


@dataclass
class AccountDisconnected(ApplicationEvent):
    name: str = field(init=False, default='account-disconnected')
    account: str


@dataclass
class PlainConnection(ApplicationEvent):
    name: str = field(init=False, default='plain-connection')
    account: str
    connect: Callable[..., Any]
    abort: Callable[..., Any]


@dataclass
class PasswordRequired(ApplicationEvent):
    name: str = field(init=False, default='password-required')
    client: 'Client'
    on_password: Callable[..., Any]


@dataclass
class Notification(ApplicationEvent):
    name: str = field(init=False, default='notification')
    account: str
    type: str
    title: str
    text: str
    jid: JID | str | None = None
    sub_type: str | None = None
    sound: str | None = None
    icon_name: str | None = None
    resource: str | None = None


@dataclass
class ChatRead(ApplicationEvent):
    name: str = field(init=False, default='chat-read')
    account: str
    jid: JID


@dataclass
class StanzaSent(ApplicationEvent):
    name: str = field(init=False, default='stanza-sent')
    account: str
    stanza: Any


@dataclass
class StanzaReceived(ApplicationEvent):
    name: str = field(init=False, default='stanza-received')
    account: str
    stanza: Any


@dataclass
class SignedIn(ApplicationEvent):
    name: str = field(init=False, default='signed-in')
    account: str
    conn: 'Client'


@dataclass
class LocationChanged(ApplicationEvent):
    name: str = field(init=False, default='location-changed')
    info: LocationData | None


@dataclass
class MusicTrackChanged(ApplicationEvent):
    name: str = field(init=False, default='music-track-changed')
    info: TuneData | None


@dataclass
class MessageSent(ApplicationEvent):
    name: str = field(init=False, default='message-sent')
    account: str
    jid: JID
    pk: int
    play_sound: bool = False

    @cached_property
    def message(self) -> mod.Message:
        m = app.storage.archive.get_message_with_pk(self.pk)
        assert m is not None
        return m


@dataclass
class MessageNotSent(ApplicationEvent):
    name: str = field(init=False, default='message-not-sent')
    client: 'Client'
    jid: str
    message: str
    error: str
    time: float


@dataclass
class MessageDeleted(ApplicationEvent):
    name: str = field(init=False, default='message-deleted')
    account: str
    jid: JID
    pk: int


@dataclass
class MessageAcknowledged(ApplicationEvent):
    name: str = field(init=False, default='message-acknowledged')
    account: str
    jid: JID
    pk: int
    stanza_id: str | None


@dataclass
class FileProgress(ApplicationEvent):
    name: str = field(init=False, default='file-progress')
    file_props: FileProp


@dataclass
class FileCompleted(ApplicationEvent):
    name: str = field(init=False, default='file-completed')
    account: str
    file_props: FileProp
    jid: str


@dataclass
class FileError(ApplicationEvent):
    name: str = field(init=False, default='file-error')
    account: str
    file_props: FileProp
    jid: str


@dataclass
class FileHashError(ApplicationEvent):
    name: str = field(init=False, default='file-hash-error')
    account: str
    file_props: FileProp
    jid: str


@dataclass
class FileRequestSent(ApplicationEvent):
    name: str = field(init=False, default='file-request-sent')
    account: str
    file_props: FileProp
    jid: JID


@dataclass
class FileRequestError(ApplicationEvent):
    name: str = field(init=False, default='file-request-error')
    conn: 'Client'
    file_props: FileProp
    jid: str
    error_msg: str = ''


@dataclass
class FileSendError(ApplicationEvent):
    name: str = field(init=False, default='file-send-error')
    account: str
    file_props: FileProp
    jid: str
    error_msg: str = ''


@dataclass
class HTTPUploadStarted(ApplicationEvent):
    name: str = field(init=False, default='http-upload-started')
    account: str
    jid: JID
    transfer: HTTPFileTransfer


@dataclass
class HTTPUploadError(ApplicationEvent):
    name: str = field(init=False, default='http-upload-error')
    account: str
    jid: JID
    error_msg: str


@dataclass
class AccountEnabled(ApplicationEvent):
    name: str = field(init=False, default='account-enabled')
    account: str


@dataclass
class AccountDisabled(ApplicationEvent):
    name: str = field(init=False, default='account-disabled')
    account: str


@dataclass
class FeatureDiscovered(ApplicationEvent):
    name: str = field(init=False, default='feature-discovered')
    account: str
    feature: str


@dataclass
class BookmarksReceived(ApplicationEvent):
    name: str = field(init=False, default='bookmarks-received')
    account: str


@dataclass
class ReadStateSync(ApplicationEvent):
    name: str = field(init=False, default='read-state-sync')
    account: str
    jid: JID
    marker_id: str


@dataclass
class DisplayedReceived(ApplicationEvent):
    name: str = field(init=False, default='displayed-received')
    account: str
    jid: JID
    properties: Any
    type: str
    is_muc_pm: bool
    marker_id: str


@dataclass
class ReactionUpdated(ApplicationEvent):
    name: str = field(init=False, default='reaction-updated')
    account: str
    jid: JID
    reaction_id: str


@dataclass
class HttpAuth(ApplicationEvent):
    name: str = field(init=False, default='http-auth')
    client: 'Client'
    data: HTTPAuthData
    stanza: Any


@dataclass
class AgentRemoved(ApplicationEvent):
    name: str = field(init=False, default='agent-removed')
    conn: 'Client'
    agent: str
    jid_list: list[str]


@dataclass
class GatewayPromptReceived(ApplicationEvent):
    name: str = field(init=False, default='gateway-prompt-received')
    conn: 'Client'
    fjid: str
    jid: str
    resource: str
    desc: str
    prompt: str
    prompt_jid: str
    stanza: Any


@dataclass
class ServerDiscoReceived(ApplicationEvent):
    name: str = field(init=False, default='server-disco-received')


@dataclass
class MucDiscoUpdate(ApplicationEvent):
    name: str = field(init=False, default='muc-disco-update')
    account: str
    jid: JID


@dataclass
class RawMessageReceived(ApplicationEvent):
    name: str = field(init=False, default='raw-message-received')
    account: str
    stanza: Any
    conn: 'Client'


@dataclass
class RawMamMessageReceived(ApplicationEvent):
    name: str = field(init=False, default='raw-mam-message-received')
    account: str
    stanza: Any
    properties: Any


@dataclass
class ArchivingIntervalFinished(ApplicationEvent):
    name: str = field(init=False, default='archiving-interval-finished')
    account: str
    query_id: str


@dataclass
class MessageCorrected(ApplicationEvent):
    name: str = field(init=False, default='message-corrected')
    account: str
    jid: JID
    pk: int
    correction_id: str

    @cached_property
    def message(self) -> mod.Message:
        m = app.storage.archive.get_message_with_pk(self.pk)
        assert m is not None
        return m


@dataclass
class MessageModerated(ApplicationEvent):
    name: str = field(init=False, default='message-moderated')
    account: str
    jid: JID
    moderation: mod.Moderation


@dataclass
class MessageReceived(ApplicationEvent):
    name: str = field(init=False, default='message-received')
    account: str
    jid: JID
    m_type: MessageType
    from_mam: bool
    pk: int

    @cached_property
    def message(self) -> mod.Message:
        m = app.storage.archive.get_message_with_pk(self.pk)
        assert m is not None
        return m


@dataclass
class MessageError(ApplicationEvent):
    name: str = field(init=False, default='message-error')
    account: str
    jid: JID
    message_id: str
    error: Any


@dataclass
class RosterItemExchangeEvent(ApplicationEvent):
    name: str = field(init=False, default='roster-item-exchange')
    client: 'Client'
    jid: JID
    exchange_items_list: dict[str, list[str]]
    action: str


@dataclass
class RosterReceived(ApplicationEvent):
    name: str = field(init=False, default='roster-received')
    account: str


@dataclass
class RosterPush(ApplicationEvent):
    name: str = field(init=False, default='roster-push')
    account: str
    item: RosterItem


@dataclass
class SearchFormReceivedEvent(ApplicationEvent):
    name: str = field(init=False, default='search-form-received')
    conn: 'Client'
    is_dataform: bool
    data: Any


@dataclass
class SearchResultReceivedEvent(ApplicationEvent):
    name: str = field(init=False, default='search-result-received')
    conn: 'Client'
    is_dataform: bool
    data: Any


@dataclass
class ReceiptReceived(ApplicationEvent):
    name: str = field(init=False, default='receipt-received')
    account: str
    jid: JID
    receipt_id: str


@dataclass
class CallStarted(ApplicationEvent):
    name: str = field(init=False, default='call-started')
    account: str
    resource_jid: JID


@dataclass
class CallStopped(ApplicationEvent):
    name: str = field(init=False, default='call-stopped')
    account: str
    jid: JID


@dataclass
class CallUpdated(ApplicationEvent):
    name: str = field(init=False, default='call-updated')
    jingle_type: str
    audio_state: JingleState
    video_state: JingleState
    audio_sid: str | None
    video_sid: str | None


@dataclass
class JingleEvent(ApplicationEvent):
    name: str
    conn: 'Client'
    account: str
    fjid: str
    jid: JID
    sid: str
    resource: str
    jingle_session: Any


@dataclass
class JingleConnectedReceived(JingleEvent):
    name: str = field(init=False, default='jingle-connected-received')
    media: Any


@dataclass
class JingleDisconnectedReceived(JingleEvent):
    name: str = field(init=False, default='jingle-disconnected-received')
    media: Any
    reason: str


@dataclass
class JingleRequestReceived(JingleEvent):
    name: str = field(init=False, default='jingle-request-received')
    contents: Any


@dataclass
class JingleFtCancelledReceived(JingleEvent):
    name: str = field(init=False, default='jingle-ft-cancelled-received')
    media: Any
    reason: str


@dataclass
class JingleErrorReceived(JingleEvent):
    name: str = field(init=False, default='jingle-error-received')
    reason: str


@dataclass
class MucAdded(ApplicationEvent):
    name: str = field(init=False, default='muc-added')
    account: str
    jid: JID
    select_chat: bool


@dataclass
class MucDecline(ApplicationEvent):
    name: str = field(init=False, default='muc-decline')
    account: str
    muc: JID
    from_: JID
    reason: str | None


@dataclass
class MucInvitation(ApplicationEvent):
    name: str = field(init=False, default='muc-invitation')
    account: str
    info: Any
    muc: JID
    from_: JID
    reason: str | None
    password: str | None
    type: InviteType
    continued: bool
    thread: str | None


@dataclass
class PingSent(ApplicationEvent):
    name: str = field(init=False, default='ping-sent')
    account: str
    contact: Any


@dataclass
class PingError(ApplicationEvent):
    name: str = field(init=False, default='ping-error')
    account: str
    contact: Any
    error: str


@dataclass
class PingReply(ApplicationEvent):
    name: str = field(init=False, default='ping-reply')
    account: str
    contact: Any
    seconds: float


@dataclass
class SecCatalogReceived(ApplicationEvent):
    name: str = field(init=False, default='sec-catalog-received')
    account: str
    jid: JID
    catalog: Catalog


@dataclass
class PresenceReceived(ApplicationEvent):
    name: str = field(init=False, default='presence-received')
    account: str
    conn: 'Client'
    stanza: Any
    prio: int
    need_add_in_roster: bool
    popup: bool
    ptype: str
    jid: JID
    resource: str
    id_: str
    fjid: str
    timestamp: float
    avatar_sha: str | None
    user_nick: str | None
    show: str
    new_show: str
    old_show: str
    status: str
    contact_list: list[str]
    contact: Any


@dataclass
class SubscribePresenceReceived(ApplicationEvent):
    name: str = field(init=False, default='subscribe-presence-received')
    conn: 'Client'
    account: str
    jid: str
    fjid: str
    status: str
    user_nick: str
    is_transport: bool


@dataclass
class SubscribedPresenceReceived(ApplicationEvent):
    name: str = field(init=False, default='subscribed-presence-received')
    account: str
    jid: str


@dataclass
class UnsubscribedPresenceReceived(ApplicationEvent):
    name: str = field(init=False, default='unsubscribed-presence-received')
    conn: 'Client'
    account: str
    jid: str


@dataclass
class FileRequestReceivedEvent(ApplicationEvent):
    name: str = field(init=False, default='file-request-received')
    conn: 'Client'
    stanza: Any
    id_: str
    fjid: str
    account: str
    jid: JID
    file_props: FileProp


@dataclass
class AllowGajimUpdateCheck(ApplicationEvent):
    name: str = field(init=False, default='allow-gajim-update-check')


@dataclass
class GajimUpdateAvailable(ApplicationEvent):
    name: str = field(init=False, default='gajim-update-available')
    version: str
    setup_url: str


@dataclass
class MUCNicknameChanged(ApplicationEvent):
    name: str = field(init=False, default='muc-nickname-changed')
    is_self: bool
    new_name: str
    old_name: str
    timestamp: datetime.datetime


@dataclass
class MUCRoomConfigChanged(ApplicationEvent):
    name: str = field(init=False, default='muc-room-config-changed')
    timestamp: datetime.datetime
    status_codes: set[StatusCode]


@dataclass
class MUCRoomConfigFinished(ApplicationEvent):
    name: str = field(init=False, default='muc-room-config-finished')
    timestamp: datetime.datetime


@dataclass
class MUCRoomPresenceError(ApplicationEvent):
    name: str = field(init=False, default='muc-room-presence-error')
    timestamp: datetime.datetime
    error: str


@dataclass
class MUCRoomKicked(ApplicationEvent):
    name: str = field(init=False, default='muc-room-kicked')
    timestamp: datetime.datetime
    status_codes: set[StatusCode] | None
    reason: str | None
    actor: str | None


@dataclass
class MUCRoomDestroyed(ApplicationEvent):
    name: str = field(init=False, default='muc-room-destroyed')
    timestamp: datetime.datetime
    reason: str | None
    alternate: JID | None


@dataclass
class MUCUserJoined(ApplicationEvent):
    name: str = field(init=False, default='muc-user-joined')
    timestamp: datetime.datetime
    is_self: bool
    nick: str
    status_codes: set[StatusCode] | None


@dataclass
class MUCUserLeft(ApplicationEvent):
    name: str = field(init=False, default='muc-user-left')
    timestamp: datetime.datetime
    is_self: bool
    nick: str
    status_codes: set[StatusCode] | None
    reason: str | None
    actor: str | None


@dataclass
class MUCUserRoleChanged(ApplicationEvent):
    name: str = field(init=False, default='muc-user-role-changed')
    timestamp: datetime.datetime
    is_self: bool
    nick: str
    role: Role
    reason: str | None
    actor: str | None


@dataclass
class MUCUserAffiliationChanged(ApplicationEvent):
    name: str = field(init=False, default='muc-user-affiliation-changed')
    timestamp: datetime.datetime
    is_self: bool
    nick: str
    affiliation: Affiliation
    reason: str | None
    actor: str | None


@dataclass
class MUCAffiliationChanged(ApplicationEvent):
    name: str = field(init=False, default='room-affiliation-changed')
    timestamp: datetime.datetime
    nick: str
    affiliation: Affiliation


@dataclass
class MUCUserStatusShowChanged(ApplicationEvent):
    name: str = field(init=False, default='muc-user-status-show-changed')
    timestamp: datetime.datetime
    is_self: bool
    nick: str
    status: str
    show_value: str


@dataclass
class EncryptionInfo(ApplicationEvent):
    name: str = field(init=False, default='encryption-check')
    account: str
    jid: JID
    message: EncryptionInfoMsg


@dataclass
class DBMigration(ApplicationEvent):
    name: str = field(init=False, default='db-migration')


@dataclass
class DBMigrationProgress(ApplicationEvent):
    name: str = field(init=False, default='db-migration-progress')
    count: int
    progress: int

    @property
    def value(self) -> str:
        value = 100
        if self.count != 0:
            value = self.progress / self.count * 100
        return f'{value:05.2f}'


@dataclass
class DBMigrationFinished(ApplicationEvent):
    name: str = field(init=False, default='db-migration-finished')

@dataclass
class DBMigrationError(ApplicationEvent):
    name: str = field(init=False, default='db-migration-error')
    exception: Exception
