# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


# Handles Jingle sessions (XEP 0166)

# TODO:
# * 'senders' attribute of 'content' element
# * security preconditions
# * actions:
#   - content-modify
#   - session-info
#   - security-info
#   - transport-accept, transport-reject
#   - Tie-breaking
# * timeout

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import logging
import uuid
from collections.abc import Callable
from enum import Enum
from enum import unique

import nbxmpp
from nbxmpp import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common import events
from gajim.common.client import Client
from gajim.common.file_props import FilesProp
from gajim.common.jingle_content import get_jingle_content
from gajim.common.jingle_content import JingleContent
from gajim.common.jingle_content import JingleContentSetupException
from gajim.common.jingle_ft import State
from gajim.common.jingle_transport import get_jingle_transport
from gajim.common.jingle_transport import JingleTransportIBB
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.datetime import utc_now

if TYPE_CHECKING:
    from gajim.common.jingle_transport import JingleTransport


log = logging.getLogger('app.c.jingle_session')


JINGLE_EVENTS = {
    'jingle-connected-received': events.JingleConnectedReceived,
    'jingle-disconnected-received': events.JingleDisconnectedReceived,
    'jingle-request-received': events.JingleRequestReceived,
    'jingle-ft-cancelled-received': events.JingleFtCancelledReceived,
    'jingle-error-received': events.JingleErrorReceived
}


# FIXME: Move it to JingleSession.States?
@unique
class JingleStates(Enum):
    '''
    States in which jingle session may exist
    '''
    ENDED = 0
    PENDING = 1
    ACTIVE = 2


class OutOfOrder(Exception):
    '''
    Exception that should be raised when an action is received when in the wrong
    state
    '''


class TieBreak(Exception):
    '''
    Exception that should be raised in case of a tie, when we overrule the other
    action
    '''


class FailedApplication(Exception):
    '''
    Exception that should be raised in case responder supports none of the
    payload-types offered by the initiator
    '''


class JingleSession:
    '''
    This represents one jingle session, that is, one or more content types
    negotiated between an initiator and a responder.
    '''

    def __init__(self,
                 con: Client,
                 weinitiate: bool,
                 jid: str,
                 iq_id: str | None = None,
                 sid: str | None = None,
                 werequest: bool = False
                 ) -> None:
        '''
        con -- connection object,
        weinitiate -- boolean, are we the initiator?
        jid - jid of the other entity
        '''
        # negotiated contents
        self.contents: dict[tuple[str, str], JingleContent] = {}
        self.connection = con  # connection to use
        # our full jid
        self.ourjid = str(self.connection.get_own_jid())
        self.peerjid = jid  # jid we connect to
        # jid we use as the initiator
        self.initiator = self.ourjid if weinitiate else self.peerjid
        # jid we use as the responder
        self.responder = self.peerjid if weinitiate else self.ourjid
        # are we an initiator?
        self.weinitiate = weinitiate
        # Are we requesting or offering a file?
        self.werequest = werequest
        self.request = False
        # what state is session in? (one from JingleStates)
        self.state = JingleStates.ENDED
        if not sid:
            sid = generate_id()
        self.sid = sid  # sessionid
        # iq stanza id, used to determine which sessions to summon callback
        # later on when iq-result stanza arrives
        if iq_id is not None:
            self.iq_ids = [iq_id]
        else:
            self.iq_ids = []
        self.accepted = True  # is this session accepted by user
        # Tells whether this session is a file transfer or not
        self.session_type_ft = False
        # callbacks to call on proper contents
        # use .prepend() to add new callbacks, especially when you're going
        # to send error instead of ack
        self.callbacks: dict[str, list[Callable[
            [nbxmpp.Node, nbxmpp.Node, nbxmpp.Node | None, str],
            None]]] = {
            'content-accept': [self.__ack,
                               self.__on_content_accept,
                               self.__broadcast],
            'content-add': [self.__ack,
                            self.__on_content_add,
                            self.__broadcast],  # TODO
            'content-modify': [self.__ack],  # TODO
            'content-reject': [self.__ack, self.__on_content_remove],
            'content-remove': [self.__ack, self.__on_content_remove],
            'description-info': [self.__ack, self.__broadcast],  # TODO
            'security-info': [self.__ack],  # TODO
            'session-accept': [self.__ack, self.__on_session_accept,
                               self.__on_content_accept,
                               self.__broadcast],
            'session-info': [self.__ack, self.__broadcast,
                             self.__on_session_info],
            'session-initiate': [self.__ack, self.__on_session_initiate,
                                 self.__broadcast],
            'session-terminate': [self.__ack, self.__on_session_terminate,
                                  self.__broadcast_all],
            'transport-info': [self.__ack, self.__broadcast],
            'transport-replace': [self.__ack, self.__broadcast,
                                  self.__on_transport_replace],  # TODO
            'transport-accept': [self.__ack, self.__on_session_accept,
                                 self.__on_content_accept,
                                 self.__broadcast],
            'transport-reject': [self.__ack],  # TODO
            'iq-result': [self.__broadcast],
            'iq-error': [self.__on_error],
        }

    def collect_iq_id(self, iq_id: str) -> None:
        if iq_id is not None:
            self.iq_ids.append(iq_id)

    def approve_session(self) -> None:
        '''
        Called when user accepts session in UI (when we aren't the initiator)
        '''
        self.accept_session()

    def decline_session(self) -> None:
        '''
        Called when user declines session in UI (when we aren't the initiator)
        '''
        reason = nbxmpp.Node('reason')
        reason.addChild('decline')
        self._session_terminate(reason)

    def cancel_session(self) -> None:
        '''
        Called when user declines session in UI (when we aren't the initiator)
        '''
        reason = nbxmpp.Node('reason')
        reason.addChild('cancel')
        self._session_terminate(reason)

    def approve_content(self, media: str, name: str | None = None) -> None:
        content = self.get_content(media, name)
        if content:
            content.accepted = True
            self.on_session_state_changed(content)

    def reject_content(self, media: str, name: str | None = None) -> None:
        content = self.get_content(media, name)
        if content:
            if self.state == JingleStates.ACTIVE:
                self.__content_reject(content)
            content.destroy()
            self.on_session_state_changed()

    def end_session(self) -> None:
        '''
        Called when user stops or cancel session in UI
        '''
        reason = nbxmpp.Node('reason')
        if self.state == JingleStates.ACTIVE:
            reason.addChild('success')
        else:
            reason.addChild('cancel')
        self._session_terminate(reason)

    def get_content(self,
                    media: str | None = None,
                    name: str | None = None
                    ) -> JingleContent | None:
        if media is None:
            return None
        for content in self.contents.values():
            if content.media == media:
                if name is None or content.name == name:
                    return content
        return None

    def add_content(self,
                    name: str,
                    content: JingleContent,
                    creator: str = 'we'
                    ) -> None:
        '''
        Add new content to session. If the session is active, this will send
        proper stanza to update session

        Creator must be one of ('we', 'peer', 'initiator', 'responder')
        '''
        assert creator in ('we', 'peer', 'initiator', 'responder')
        if ((creator == 'we' and self.weinitiate) or
                (creator == 'peer' and not self.weinitiate)):
            creator = 'initiator'
        elif ((creator == 'peer' and self.weinitiate) or
                (creator == 'we' and not self.weinitiate)):
            creator = 'responder'
        content.creator = creator
        content.name = name
        self.contents[(creator, name)] = content
        if (creator == 'initiator') == self.weinitiate:
            # The content is from us, accept it
            content.accepted = True

    def remove_content(self,
                       creator: str,
                       name: str,
                       reason: nbxmpp.Node | None = None
                       ) -> None:
        '''
        Remove the content `name` created by `creator`
        by sending content-remove, or by sending session-terminate if
        there is no content left.
        '''
        if (creator, name) in self.contents:
            content = self.contents[(creator, name)]
            self.__content_remove(content, reason)
            self.contents[(creator, name)].destroy()
        if not self.contents:
            self.end_session()

    def modify_content(self,
                       creator: str,
                       name: str,
                       transport: JingleTransport | None = None
                       ) -> None:
        '''
        Currently used for transport replacement
        '''
        content = self.contents[(creator, name)]
        file_props = content.transport.file_props
        file_props.transport_sid = transport.sid
        transport.set_file_props(file_props)
        content.transport = transport
        # The content will have to be resend now that it is modified
        content.sent = False
        content.accepted = True

    def on_session_state_changed(self,
                                 content: JingleContent | None = None
                                 ) -> None:
        if self.state == JingleStates.ENDED:
            # Session not yet started, only one action possible:
            # session-initiate
            if self.is_ready() and self.weinitiate:
                self.__session_initiate()
        elif self.state == JingleStates.PENDING:
            # We can either send a session-accept or a content-add
            if self.is_ready() and not self.weinitiate:
                self.__session_accept()
            elif (content and
                  (content.creator == 'initiator') == self.weinitiate):
                self.__content_add(content)
            elif content and self.weinitiate:
                self.__content_accept(content)
        elif self.state == JingleStates.ACTIVE:
            # We can either send a content-add or a content-accept. However, if
            # we are sending a file we can only use session_initiate.
            if not content:
                return
            is_initiator = content.creator == 'initiator'
            we_created_content = is_initiator == self.weinitiate
            if we_created_content and content.media == 'file':
                self.__session_initiate()
            if we_created_content:
                # We initiated this content. It's a pending content-add.
                self.__content_add(content)
            else:
                # The other side created this content, we accept it.
                self.__content_accept(content)

    def is_ready(self) -> bool:
        '''
        Return True when all codecs and candidates are ready (for all contents)
        '''
        ready = [content.is_ready() for content in self.contents.values()]
        return all(ready) and self.accepted

    def accept_session(self) -> None:
        '''
        Mark the session as accepted
        '''
        self.accepted = True
        self.on_session_state_changed()

    def start_session(self) -> None:
        '''
        Mark the session as ready to be started
        '''
        self.accepted = True
        self.on_session_state_changed()

    def send_session_info(self) -> Any:
        pass

    def send_content_accept(self, content: nbxmpp.Node) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('content-accept')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)

    def send_transport_info(self, content: nbxmpp.Node) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('transport-info')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())

    def send_description_info(self, content: nbxmpp.Node) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('description-info')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)

    def on_stanza(self, stanza: nbxmpp.Node) -> None:
        '''
        A callback for ConnectionJingle. It gets stanza, then tries to send
        it to all internally registered callbacks. First one to raise
        nbxmpp.NodeProcessed breaks function
        '''
        jingle = stanza.getTag('jingle')
        error = stanza.getTag('error')
        if error:
            # it's an iq-error stanza
            action = 'iq-error'
        elif jingle:
            # it's a jingle action
            action = jingle.getAttr('action')
            if action not in self.callbacks:
                self.__send_error(stanza, 'bad-request')
                return
            # FIXME: If we aren't initiated and it's not a session-initiate...
            if action not in ['session-initiate', 'session-terminate'] \
                    and self.state == JingleStates.ENDED:
                self.__send_error(stanza, 'item-not-found', 'unknown-session')
                return
        else:
            # it's an iq-result (ack) stanza
            action = 'iq-result'
        callables = self.callbacks[action]
        try:
            for call in callables:
                call(stanza=stanza, jingle=jingle, error=error, action=action)
        except nbxmpp.NodeProcessed:
            pass
        except TieBreak:
            self.__send_error(stanza, 'conflict', 'tiebreak')
        except OutOfOrder:
            # FIXME
            self.__send_error(stanza, 'unexpected-request', 'out-of-order')
        except FailedApplication:
            reason = nbxmpp.Node('reason')
            reason.addChild('failed-application')
            self._session_terminate(reason)

    def __ack(self,
              stanza: nbxmpp.Node,
              jingle: nbxmpp.Node,
              error: nbxmpp.Node | None,
              action: str
              ) -> None:
        '''
        Default callback for action stanzas -- simple ack and stop processing
        '''
        response = stanza.buildReply('result')
        response.delChild(response.getQuery())
        self.connection.connection.send(response)

    def __on_error(self,
                   stanza: nbxmpp.Node,
                   jingle: nbxmpp.Node,
                   error: nbxmpp.Node,
                   action: str
                   ) -> None:
        # FIXME
        text = error.getTagData('text')
        error_name = None
        for child in error.getChildren():
            if child.getNamespace() == Namespace.JINGLE_ERRORS:
                error_name = child.getName()
                break
            if child.getNamespace() == Namespace.STANZAS:
                error_name = child.getName()
        self.__dispatch_error(error_name, text, error.getAttr('type'))

    def transport_replace(self) -> None:
        transport = JingleTransportIBB()
        # For debug only, delete this and replace for a function
        # that will identify contents by its sid
        for creator, name in self.contents:
            self.modify_content(creator, name, transport)
            cont = self.contents[(creator, name)]
            cont.transport = transport
        stanza, jingle = self.__make_jingle('transport-replace')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'transport-replace')
        self.connection.connection.send(stanza)
        self.state = JingleStates.PENDING

    def __on_transport_replace(self,
                               stanza: nbxmpp.Node,
                               jingle: nbxmpp.Node,
                               error: nbxmpp.Node | None,
                               action: str
                               ) -> None:
        for content in jingle.iterTags('content'):
            creator = content['creator']
            name = content['name']
            transport_ns = content.getTag('transport').getNamespace()
            if (creator, name) in self.contents:
                if transport_ns == Namespace.JINGLE_ICE_UDP:
                    # FIXME: We don't manage anything else than ICE-UDP now...
                    # What was the previous transport?!?
                    # Anyway, content's transport is not modifiable yet
                    pass
                elif transport_ns == Namespace.JINGLE_IBB:
                    transport = JingleTransportIBB(node=content.getTag(
                        'transport'))
                    self.modify_content(creator, name, transport)
                    self.state = JingleStates.PENDING
                    self.contents[(creator, name)].state = \
                        State.TRANSPORT_REPLACE
                    self.__ack(stanza, jingle, error, action)
                    self.__transport_accept(transport)
                else:
                    stanza, jingle = self.__make_jingle('transport-reject')
                    content = jingle.setTag('content',
                                            attrs={'creator': creator,
                                                   'name': name})
                    content.setTag('transport', namespace=transport_ns)
                    self.connection.connection.send(stanza)
                    raise nbxmpp.NodeProcessed
            else:
                # FIXME: This resource is unknown to us, what should we do?
                # For now, reject the transport
                stanza, jingle = self.__make_jingle('transport-reject')
                content = jingle.setTag('content', attrs={'creator': creator,
                                                          'name': name})
                content.setTag('transport', namespace=transport_ns)
                self.connection.connection.send(stanza)
                raise nbxmpp.NodeProcessed

    def __on_session_info(self,
                          stanza: nbxmpp.Node,
                          jingle: nbxmpp.Node,
                          error: nbxmpp.Node | None,
                          action: str
                          ) -> None:
        # TODO: active, (un)hold, (un)mute
        ringing = jingle.getTag('ringing')
        if ringing is not None:
            # ignore ringing
            raise nbxmpp.NodeProcessed
        if self.state != JingleStates.ACTIVE:
            raise OutOfOrder
        for child in jingle.getChildren():
            if child.getName() == 'checksum':
                hash_ = child.getTag('file').getTag(
                    name='hash',
                    namespace=Namespace.HASHES_2)
                if hash_ is None:
                    continue
                algo = hash_.getAttr('algo')
                if algo in nbxmpp.Hashes2.supported:
                    file_props = FilesProp.getFileProp(self.connection.name,
                                                       self.sid)
                    file_props.algo = algo
                    file_props.hash_ = hash_.getData()
                    raise nbxmpp.NodeProcessed
        self.__send_error(stanza, 'feature-not-implemented', 'unsupported-info',
                          type_='modify')
        raise nbxmpp.NodeProcessed

    def __on_content_remove(self,
                            stanza: nbxmpp.Node,
                            jingle: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        for content in jingle.iterTags('content'):
            creator = content['creator']
            name = content['name']
            if (creator, name) in self.contents:
                content = self.contents[(creator, name)]
                # TODO: this will fail if content is not an RTP content
                self._raise_event('jingle-disconnected-received',
                                  media=content.media,
                                  reason='removed')
                content.destroy()
        if not self.contents:
            reason = nbxmpp.Node('reason')
            reason.setTag('success')
            self._session_terminate(reason)

    def __on_session_accept(self,
                            stanza: nbxmpp.Node,
                            jingle: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        # FIXME
        if self.state != JingleStates.PENDING:
            raise OutOfOrder
        self.state = JingleStates.ACTIVE

    @staticmethod
    def __on_content_accept(stanza: nbxmpp.Node,
                            jingle: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        '''
        Called when we get content-accept stanza or equivalent one (like
        session-accept)
        '''
        # check which contents are accepted
        # for content in jingle.iterTags('content'):
        #     creator = content['creator']
        #     name = content['name']
        return

    def __on_content_add(self,
                         stanza: nbxmpp.Node,
                         jingle: nbxmpp.Node,
                         error: nbxmpp.Node | None,
                         action: str
                         ) -> None:
        if self.state == JingleStates.ENDED:
            raise OutOfOrder
        parse_result = self.__parse_contents(jingle)
        contents = parse_result[0]
        # rejected_contents = parse_result[1]
        # for name, creator in rejected_contents:
        #     content = JingleContent()
        #     self.add_content(name, content, creator)
        #     self.__content_reject(content)
        #     self.contents[(content.creator, content.name)].destroy()
        self._raise_event('jingle-request-received', contents=contents)

    def __on_session_initiate(self,
                              stanza: nbxmpp.Node,
                              jingle: nbxmpp.Node,
                              error: nbxmpp.Node | None,
                              action: str
                              ) -> None:
        '''
        We got a jingle session request from other entity, therefore we are the
        receiver... Unpack the data, inform the user
        '''
        if self.state != JingleStates.ENDED:
            raise OutOfOrder

        # In "session-initiate", the <jingle/> element SHOULD possess an
        # 'initiator' attribute. If it differs from the JID 'from', jingle
        # 'initiator' SHOULD be ignored.
        if jingle['initiator'] is None:
            self.initiator = stanza['from']
        elif jingle['initiator'] != stanza['from']:
            self.initiator = stanza['from']
        else:
            self.initiator = jingle['initiator']

        self.responder = self.ourjid
        self.peerjid = self.initiator
        self.accepted = False   # user did not accept this session yet
        # TODO: If the initiator is unknown to the receiver (e.g., via presence
        # subscription) and the receiver has a policy of not communicating via
        # Jingle with unknown entities, it SHOULD return a
        # <service-unavailable/> error.
        # Lets check what kind of jingle session does the peer want
        contents, _contents_rejected, reason_txt = self.__parse_contents(jingle)

        # If there's no content we understand...
        if not contents:
            # TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
            reason = nbxmpp.Node('reason')
            reason.setTag(reason_txt)
            self.__ack(stanza, jingle, error, action)
            self._session_terminate(reason)
            raise nbxmpp.NodeProcessed

        # If we are not receiving a file
        # Check if there's already a session with this user:
        if contents[0].media != 'file':
            jingle_module = self.connection.get_module('Jingle')
            for session in jingle_module.get_jingle_sessions(self.peerjid):
                if session is not self:
                    reason = nbxmpp.Node('reason')
                    alternative_session = reason.setTag('alternative-session')
                    alternative_session.setTagData('sid', session.sid)
                    self.__ack(stanza, jingle, error, action)
                    self._session_terminate(reason)
                    raise nbxmpp.NodeProcessed
        else:
            # Stop if we don't have the requested file or the peer is not
            # allowed to request the file
            request = contents[0].senders == 'responder'
            if request:
                self.request = True
                hash_tag = request.getTag('file').getTag('hash')
                hash_data = hash_tag.getData() if hash_tag else None
                n = request.getTag('file').getTag('name')
                n = n.getData() if n else None
                pjid = app.get_jid_without_resource(self.peerjid)
                file_info = self.connection.get_module('Jingle').get_file_info(
                    pjid, hash_data, n, self.connection.name)
                if not file_info:
                    log.warning('The peer %s is requesting a '
                                'file that we don’t have or '
                                'it is not allowed to request', pjid)
                    self.decline_session()
                    raise nbxmpp.NodeProcessed

        self.state = JingleStates.PENDING
        # Send event about starting a session
        self._raise_event('jingle-request-received', contents=contents)

        # Check if it's an A/V call and add it to the archive
        content_types: list[str] = []
        for item in contents:
            content_types.append(item.media)
        if not any(item in ('audio', 'video') for item in content_types):
            return

        account = self.connection.name
        jid = JID.from_string(self.peerjid)

        call_data = mod.Call(
            sid=self.sid,
            state=0,  # TODO
        )

        message = mod.Message(
            account_=account,
            remote_jid_=jid.new_as_bare(),
            resource=None,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id=str(uuid.uuid4()),
            call=call_data,
        )

        app.storage.archive.insert_object(message)

    def __broadcast(self,
                    stanza: nbxmpp.Node,
                    jingle: nbxmpp.Node,
                    error: nbxmpp.Node | None,
                    action: str
                    ) -> None:
        '''
        Broadcast the stanza contents to proper content handlers
        '''
        # if jingle is None: # it is a iq-result stanza
        #    for cn in self.contents.values():
        #        cn.on_stanza(stanza, None, error, action)
        #    return
        # special case: iq-result stanza does not come with a jingle element
        if action == 'iq-result':
            for cn in self.contents.values():
                cn.on_stanza(stanza, None, error, action)
            return
        for content in jingle.iterTags('content'):
            name = content['name']
            creator = content['creator']
            if (creator, name) not in self.contents:
                text = f'Content {name} (created by {creator}) does not exist'
                self.__send_error(stanza,
                                  'bad-request',
                                  text=text,
                                  type_='modify')
                raise nbxmpp.NodeProcessed

            cn = self.contents[(creator, name)]
            cn.on_stanza(stanza, content, error, action)

    def __on_session_terminate(self,
                               stanza: nbxmpp.Node,
                               jingle: nbxmpp.Node,
                               error: nbxmpp.Node | None,
                               action: str
                               ) -> None:
        self.connection.get_module('Jingle').delete_jingle_session(self.sid)
        reason, text = self.__reason_from_stanza(jingle)
        if reason not in ('success', 'cancel', 'decline'):
            self.__dispatch_error(reason, text)
        if text:
            text = f'{reason} ({text})'
        else:
            # TODO
            text = reason
        if reason == 'decline':
            self._raise_event('jingle-disconnected-received',
                              media=None,
                              reason=text)
        if reason == 'success':
            self._raise_event('jingle-disconnected-received',
                              media=None,
                              reason=text)
        if reason == 'cancel' and self.session_type_ft:
            pass
            # TODO: Jingle FT
            # self._raise_event('jingle-ft-cancelled-received',
            #                   media=None,
            #                   reason=text)

    def __broadcast_all(self,
                        stanza: nbxmpp.Node,
                        jingle: nbxmpp.Node,
                        error: nbxmpp.Node | None,
                        action: str
                        ) -> None:
        '''
        Broadcast the stanza to all content handlers
        '''
        for content in self.contents.values():
            content.on_stanza(stanza, None, error, action)

    def __parse_contents(self,
                         jingle: nbxmpp.Node
                         ) -> tuple[
                             list[JingleContent],
                             list[tuple[str, str]],
                             str | None]:
        # TODO: Needs some reworking
        contents: list[JingleContent] = []
        contents_rejected: list[tuple[str, str]] = []
        reasons: set[str] = set()
        for element in jingle.iterTags('content'):
            transport = get_jingle_transport(element.getTag('transport'))
            if transport:
                transport.ourjid = self.ourjid
            content_type = get_jingle_content(element.getTag('description'))
            if content_type:
                try:
                    if transport:
                        content = content_type(self, transport=transport)
                        self.add_content(element['name'],
                                         content,
                                         'peer')
                        contents.append(content)
                    else:
                        reasons.add('unsupported-transports')
                        contents_rejected.append((element['name'], 'peer'))
                except JingleContentSetupException:
                    reasons.add('failed-application')
            else:
                contents_rejected.append((element['name'], 'peer'))
                reasons.add('unsupported-applications')
        failure_reason = None
        # Store the first reason of failure
        for reason in ('failed-application', 'unsupported-transports',
                       'unsupported-applications'):
            if reason in reasons:
                failure_reason = reason
                break
        return (contents, contents_rejected, failure_reason)

    def __dispatch_error(self,
                         error: str | None = None,
                         text: str | None = None,
                         type_: str | None = None
                         ) -> None:
        if text:
            text = '{error} ({text})'
        if type_ != 'modify':
            self._raise_event('jingle-error-received', reason=text or error)

    @staticmethod
    def __reason_from_stanza(stanza: nbxmpp.Node) -> tuple[str, str]:
        # TODO: Move to GUI?
        reason = 'success'
        reasons = [
            'success', 'busy', 'cancel', 'connectivity-error', 'decline',
            'expired', 'failed-application', 'failed-transport',
            'general-error', 'gone', 'incompatible-parameters', 'media-error',
            'security-error', 'timeout', 'unsupported-applications',
            'unsupported-transports'
        ]
        tag = stanza.getTag('reason')
        text = ''
        if tag:
            text = tag.getTagData('text')
            for r in reasons:
                if tag.getTag(r):
                    reason = r
                    break
        return (reason, text)

    def __make_jingle(self,
                      action: str,
                      reason: nbxmpp.Node | None = None
                      ) -> tuple[Iq, nbxmpp.Node]:
        stanza = nbxmpp.Iq(typ='set', to=nbxmpp.JID.from_string(self.peerjid),
                           frm=self.ourjid)
        attrs = {
            'action': action,
            'sid': self.sid,
            'initiator': self.initiator
        }
        jingle = stanza.addChild('jingle', attrs=attrs,
                                 namespace=Namespace.JINGLE)
        if reason is not None:
            jingle.addChild(node=reason)
        return stanza, jingle

    def __send_error(self,
                     stanza: nbxmpp.Node,
                     error: str | None,
                     jingle_error: str | None = None,
                     text: str | None = None,
                     type_: str | None = None
                     ) -> None:
        err_stanza = nbxmpp.Error(stanza, f'{Namespace.STANZAS} {error}')
        err = err_stanza.getTag('error')
        if type_:
            err.setAttr('type', type_)
        if jingle_error:
            err.setTag(jingle_error, namespace=Namespace.JINGLE_ERRORS)
        if text:
            err.setTagData('text', text)
        self.connection.connection.send(err_stanza)
        self.__dispatch_error(jingle_error or error, text, type_)

    @staticmethod
    def __append_content(jingle: nbxmpp.Node, content: JingleContent) -> None:
        '''
        Append <content/> element to <jingle/> element
        '''
        jingle.addChild('content',
                        attrs={'name': content.name,
                               'creator': content.creator,
                               'senders': content.senders})

    def __append_contents(self, jingle: nbxmpp.Node) -> None:
        '''
        Append all <content/> elements to <jingle/>
        '''
        # TODO: integrate with __appendContent?
        # TODO: parameters 'name', 'content'?
        for content in self.contents.values():
            if content.is_ready():
                self.__append_content(jingle, content)

    def __session_initiate(self) -> None:
        assert self.state == JingleStates.ENDED
        stanza, jingle = self.__make_jingle('session-initiate')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'session-initiate-sent')
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())
        self.state = JingleStates.PENDING

    def __session_accept(self) -> None:
        assert self.state == JingleStates.PENDING
        stanza, jingle = self.__make_jingle('session-accept')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'session-accept-sent')
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())
        self.state = JingleStates.ACTIVE

    def __session_info(self, payload: nbxmpp.Node | None = None) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('session-info')
        if payload:
            jingle.addChild(node=payload)
        self.connection.connection.send(stanza)

    def _JingleFileTransfer__session_info(self, payload: nbxmpp.Node) -> None:
        # For some strange reason when I call
        # self.session.__session_info(payload) from the jingleFileTransfer
        # object within a thread, this method gets called instead. Even though,
        # it isn't being called explicitly.
        self.__session_info(payload)

    def _session_terminate(self, reason: nbxmpp.Node | None = None) -> None:
        stanza, jingle = self.__make_jingle('session-terminate', reason=reason)
        self.__broadcast_all(stanza, jingle, None, 'session-terminate-sent')
        if self.connection.connection and self.connection.state.is_available:
            self.connection.connection.send(stanza)
        # TODO: Move to GUI?
        reason_text, text = self.__reason_from_stanza(jingle)
        if reason not in ('success', 'cancel', 'decline'):
            self.__dispatch_error(reason_text, text)
        if text:
            text = f'{reason_text} ({text})'
        else:
            text = reason_text
        self.connection.get_module('Jingle').delete_jingle_session(self.sid)
        self._raise_event('jingle-disconnected-received',
                          media=None,
                          reason=text)

    def __content_add(self, content: JingleContent) -> None:
        # TODO: test
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('content-add')
        self.__append_content(jingle, content)
        self.__broadcast(stanza, jingle, None, 'content-add-sent')
        id_ = self.connection.connection.send(stanza)
        self.collect_iq_id(id_)

    def __content_accept(self, content: JingleContent) -> None:
        # TODO: test
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('content-accept')
        self.__append_content(jingle, content)
        self.__broadcast(stanza, jingle, None, 'content-accept-sent')
        id_ = self.connection.connection.send(stanza)
        self.collect_iq_id(id_)

    def __content_reject(self, content: JingleContent) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('content-reject')
        self.__append_content(jingle, content)
        self.connection.connection.send(stanza)
        # TODO: this will fail if content is not an RTP content
        self._raise_event('jingle-disconnected-received',
                          media=content.media,
                          reason='rejected')

    def __content_remove(self,
                         content: JingleContent,
                         reason: nbxmpp.Node | None = None
                         ) -> None:
        assert self.state != JingleStates.ENDED
        if self.connection.connection and self.connection.state.is_available:
            stanza, jingle = self.__make_jingle('content-remove', reason=reason)
            self.__append_content(jingle, content)
            self.connection.connection.send(stanza)
        # TODO: this will fail if content is not an RTP content
        self._raise_event('jingle-disconnected-received',
                          media=content.media,
                          reason='removed')

    def content_negotiated(self, media: str) -> None:
        self._raise_event('jingle-connected-received', media=media)

    def __transport_accept(self, transport: JingleTransport) -> None:
        assert self.state != JingleStates.ENDED
        stanza, jingle = self.__make_jingle('transport-accept')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'transport-accept')
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())
        self.state = JingleStates.ACTIVE

    def _raise_event(self, name: str, **kwargs: Any) -> None:
        jid, resource = app.get_room_and_nick_from_fjid(
            str(self.peerjid))
        jid = JID.from_string(jid)
        event_class = JINGLE_EVENTS[name]

        app.ged.raise_event(
            event_class(conn=self.connection,
                        account=self.connection.name,
                        fjid=self.peerjid,
                        jid=jid,
                        sid=self.sid,
                        resource=resource,
                        jingle_session=self,
                        **kwargs))
