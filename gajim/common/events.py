# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import typing
from typing import Any
from typing import Union
from typing import Optional
from typing import Callable

from dataclasses import dataclass
from dataclasses import field

from nbxmpp.protocol import JID
from nbxmpp.structs import HTTPAuthData
from nbxmpp.structs import RosterItem
from nbxmpp.structs import TuneData
from nbxmpp.const import InviteType

from gajim.common.file_props import FileProp
from gajim.common.const import KindConstant
from gajim.common.helpers import AdditionalDataDict

if typing.TYPE_CHECKING:
    from gajim.common.client import Client


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
class AccountDisonnected(ApplicationEvent):
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
    jid: Optional[Union[JID, str]] = None
    sub_type: Optional[str] = None
    sound: Optional[str] = None
    icon_name: Optional[str] = None


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
class MusicTrackChanged(ApplicationEvent):
    name: str = field(init=False, default='music-track-changed')
    info: Optional[TuneData]


@dataclass
class MessageSent(ApplicationEvent):
    name: str = field(init=False, default='message-sent')
    account: str
    jid: str
    message: str
    message_id: str
    chatstate: Optional[str]
    timestamp: float
    additional_data: AdditionalDataDict
    label: Optional[str]
    correct_id: Optional[str]
    play_sound: bool


@dataclass
class MessageNotSent(ApplicationEvent):
    name: str = field(init=False, default='message-not-sent')
    client: 'Client'
    jid: str
    message: str
    error: str
    time: float


@dataclass
class AdHocCommandError(ApplicationEvent):
    name: str = field(init=False, default='adhoc-command-error')
    conn: 'Client'
    error: str


@dataclass
class AdHocCommandActionResponse(ApplicationEvent):
    name: str = field(init=False, default='adhoc-command-action-response')
    conn: 'Client'
    command: Any


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
    jid: str


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
class BaseChatMarkerEvent(ApplicationEvent):
    name: str
    account: str
    jid: JID
    properties: Any
    type: str
    is_muc_pm: bool
    marker_id: str


@dataclass
class ReadStateSync(BaseChatMarkerEvent):
    name: str = field(init=False, default='read-state-sync')


@dataclass
class DisplayedReceived(BaseChatMarkerEvent):
    name: str = field(init=False, default='displayed-received')


@dataclass
class IqErrorReceived(ApplicationEvent):
    name: str = field(init=False, default='iq-error-received')
    account: str
    properties: Any


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
class MessageUpdated(ApplicationEvent):
    name: str = field(init=False, default='message-updated')
    account: str
    jid: str
    msgtxt: str
    properties: Any
    correct_id: str


@dataclass
class MamMessageReceived(ApplicationEvent):
    name: str = field(init=False, default='mam-message-received')
    account: str
    jid: str
    msgtxt: str
    properties: Any
    additional_data: AdditionalDataDict
    unique_id: str
    stanza_id: str
    archive_jid: str
    kind: KindConstant


@dataclass
class MessageReceived(ApplicationEvent):
    name: str = field(init=False, default='message-received')
    conn: 'Client'
    stanza: Any
    account: str
    jid: str
    msgtxt: str
    properties: Any
    additional_data: AdditionalDataDict
    unique_id: str
    stanza_id: str
    fjid: str
    resource: str
    session: Any
    delayed: Optional[float]
    msg_log_id: int
    displaymarking: str


@dataclass
class GcMessageReceived(MessageReceived):
    name: str = field(init=False, default='gc-message-received')
    room_jid: str


@dataclass
class MessageError(ApplicationEvent):
    name: str = field(init=False, default='message-error')
    account: str
    jid: str
    room_jid: str
    message_id: str
    error: Any


@dataclass
class RosterItemExchangeEvent(ApplicationEvent):
    name: str = field(init=False, default='roster-item-exchange')
    client: 'Client'
    jid: JID
    exchange_items_list: list[str]
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
class PluginAdded(ApplicationEvent):
    name: str = field(init=False, default='plugin-added')
    plugin: Any


@dataclass
class PluginRemoved(ApplicationEvent):
    name: str = field(init=False, default='plugin-removed')
    plugin: Any


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
    jid: str
    receipt_id: str


@dataclass
class JingleEvent(ApplicationEvent):
    name: str
    conn: 'Client'
    account: str
    fjid: str
    jid: str
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


@dataclass
class MucDecline(ApplicationEvent):
    name: str = field(init=False, default='muc-decline')
    account: str
    muc: JID
    from_: JID
    reason: Optional[str]


@dataclass
class MucInvitation(ApplicationEvent):
    name: str = field(init=False, default='muc-invitation')
    account: str
    info: Any
    muc: JID
    from_: JID
    reason: Optional[str]
    password: Optional[str]
    type: InviteType
    continued: bool
    thread: Optional[str]


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
    seconds: int


@dataclass
class SecCatalogReceived(ApplicationEvent):
    name: str = field(init=False, default='sec-catalog-received')
    account: str
    jid: str
    catalog: dict[str, Any]


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
    jid: str
    resource: str
    id_: str
    fjid: str
    timestamp: float
    avatar_sha: Optional[str]
    user_nick: Optional[str]
    idle_time: Optional[float]
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
    jid: str
    file_props: FileProp


@dataclass
class AllowGajimUpdateCheck(ApplicationEvent):
    name: str = field(init=False, default='allow-gajim-update-check')


@dataclass
class GajimUpdateAvailable(ApplicationEvent):
    name: str = field(init=False, default='gajim-update-available')
    version: str
