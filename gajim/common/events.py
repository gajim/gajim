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

import typing
from typing import Any
from typing import Optional
from typing import Callable

from dataclasses import dataclass
from dataclasses import field

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import LocationData
from nbxmpp.structs import RosterItem
from nbxmpp.structs import TuneData
from nbxmpp.const import InviteType

from gajim.common import app

if typing.TYPE_CHECKING:
    from gajim.common.helpers import AdditionalDataDict
    from gajim.common.const import KindConstant
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
    conn: 'Client'
    on_password: Callable[..., Any]


@dataclass
class Notification(ApplicationEvent):
    name: str = field(init=False, default='notification')
    account: str
    jid: str
    notif_type: str
    title: str
    text: str
    notif_detail: Optional[str] = None
    sound: Optional[str] = None
    icon_name: Optional[str] = None


@dataclass
class SimpleNotification(ApplicationEvent):
    name: str = field(init=False, default='simple-notification')
    account: str
    notif_type: str
    title: str
    text: str


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
    additional_data: 'AdditionalDataDict'
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
    file_props: Any


@dataclass
class FileCompleted(ApplicationEvent):
    name: str = field(init=False, default='file-completed')
    account: str
    file_props: Any
    jid: str


@dataclass
class FileError(ApplicationEvent):
    name: str = field(init=False, default='file-error')
    account: str
    file_props: Any
    jid: str


@dataclass
class FileHashError(ApplicationEvent):
    name: str = field(init=False, default='file-hash-error')
    account: str
    file_props: Any
    jid: str


@dataclass
class FileRequestSent(ApplicationEvent):
    name: str = field(init=False, default='file-request-sent')
    account: str
    file_props: Any
    jid: str


@dataclass
class FileRequestError(ApplicationEvent):
    name: str = field(init=False, default='file-request-error')
    conn: 'Client'
    file_props: Any
    jid: str
    error_msg: str = ''


@dataclass
class FileSendError(ApplicationEvent):
    name: str = field(init=False, default='file-send-error')
    account: str
    file_props: Any
    jid: str


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
class HttpAuthReceived(ApplicationEvent):
    name: str = field(init=False, default='http-auth-received')
    conn: 'Client'
    iq_id: str
    method: str
    url: str
    msg: str
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
    additional_data: 'AdditionalDataDict'
    unique_id: str
    stanza_id: str
    archive_jid: str
    kind: 'KindConstant'


@dataclass
class MessageReceived(ApplicationEvent):
    name: str = field(init=False, default='message-received')
    conn: 'Client'
    stanza: Any
    account: str
    jid: str
    msgtxt: str
    properties: Any
    additional_data: 'AdditionalDataDict'
    unique_id: str
    stanza_id: str
    archive_jid: str
    kind: 'KindConstant'
    fjid: str
    resource: str
    session: Any
    delayed: Optional[float]
    msg_log_id: int
    displaymarking: str


@dataclass
class GcMessageReceived(ApplicationEvent):
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
    name: str = field(init=False, default='roster-item-exchange-received')
    conn: 'Client'
    fjid: str
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
class TuneReceived(ApplicationEvent):
    name: str = field(init=False, default='tune-received')
    account: str
    jid: str
    tune: TuneData
    is_self_message: bool


@dataclass
class LocationReceived(ApplicationEvent):
    name: str = field(init=False, default='location-received')
    account: str
    jid: str
    location: LocationData
    is_self_message: bool


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
    jid: str


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
class RawPresenceReceived(ApplicationEvent):
    name: str = field(init=False, default='raw-pres-received')
    conn: 'Client'
    stanza: Any


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
class InformationEvent(ApplicationEvent):
    name: str = field(init=False, default='information-event')
    dialog_name: str
    args: Optional[Any] = None
    kwargs: Optional[dict[str, Any]] = None
    popup: bool = False


@dataclass
class FileRequestReceivedEvent(ApplicationEvent):
    name: str = field(init=False, default='file-request-received')
    conn: 'Client'
    stanza: Any
    jingle_content: Any
    FT_content: Any
    id_: str = field(init=False)
    fjid: str = field(init=False)
    account: str = field(init=False)
    jid: str = field(init=False)
    file_props: Any = field(init=False)

    def __post_init__(self):
        from gajim.common.jingle_transport import JingleTransportSocks5
        from gajim.common.file_props import FilesProp
        self.id_ = self.stanza.getID()
        self.fjid = self.conn.get_module('Bytestream')._ft_get_from(
            self.stanza)
        self.account = self.conn.name
        self.jid = app.get_jid_without_resource(self.fjid)
        if not self.jingle_content:
            return
        secu = self.jingle_content.getTag('security')
        self.FT_content.use_security = bool(secu)
        if secu:
            fingerprint = secu.getTag('fingerprint')
            if fingerprint:
                self.FT_content.x509_fingerprint = fingerprint.getData()
        if not self.FT_content.transport:
            self.FT_content.transport = JingleTransportSocks5()
            self.FT_content.transport.set_our_jid(
                self.FT_content.session.ourjid)
            self.FT_content.transport.set_connection(
                self.FT_content.session.connection)
        sid = self.stanza.getTag('jingle').getAttr('sid')
        self.file_props = FilesProp.getNewFileProp(self.conn.name, sid)
        self.file_props.transport_sid = self.FT_content.transport.sid
        self.FT_content.file_props = self.file_props
        self.FT_content.transport.set_file_props(self.file_props)
        self.file_props.streamhosts.extend(
            self.FT_content.transport.remote_candidates)
        for host in self.file_props.streamhosts:
            host['initiator'] = self.FT_content.session.initiator
            host['target'] = self.FT_content.session.responder
        self.file_props.session_type = 'jingle'
        self.file_props.stream_methods = Namespace.BYTESTREAM
        desc = self.jingle_content.getTag('description')
        if self.jingle_content.getAttr('creator') == 'initiator':
            file_tag = desc.getTag('file')
            self.file_props.sender = self.fjid
            self.file_props.receiver = self.conn.get_own_jid()
        else:
            file_tag = desc.getTag('file')
            hash_ = file_tag.getTag('hash')
            hash_ = hash_.getData() if hash_ else None
            file_name = file_tag.getTag('name')
            file_name = file_name.getData() if file_name else None
            pjid = app.get_jid_without_resource(self.fjid)
            file_info = self.conn.get_module('Jingle').get_file_info(
                pjid, hash_=hash_, name=file_name, account=self.conn.name)
            self.file_props.file_name = file_info['file-name']
            self.file_props.sender = self.conn.get_own_jid()
            self.file_props.receiver = self.fjid
            self.file_props.type_ = 's'
        for child in file_tag.getChildren():
            name = child.getName()
            val = child.getData()
            if val is None:
                continue
            if name == 'name':
                self.file_props.name = val
            if name == 'size':
                self.file_props.size = int(val)
            if name == 'hash':
                self.file_props.algo = child.getAttr('algo')
                self.file_props.hash_ = val
            if name == 'date':
                self.file_props.date = val

        self.file_props.request_id = self.id_
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            self.file_props.desc = file_desc_tag.getData()
        self.file_props.transfered_size = []
