##
## Copyright (C) 2006 Gajim Team
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.

"""
Handles Jingle sessions (XEP 0166)
"""

#TODO:
# * 'senders' attribute of 'content' element
# * security preconditions
# * actions:
#   - content-modify
#   - session-info
#   - security-info
#   - transport-accept, transport-reject
#   - Tie-breaking
# * timeout

from common import gajim
import nbxmpp
from common.jingle_transport import get_jingle_transport, JingleTransportIBB
from common.jingle_content import get_jingle_content, JingleContentSetupException
from common.jingle_content import JingleContent
from common.jingle_ft import STATE_TRANSPORT_REPLACE
from common.connection_handlers_events import *
import logging
log = logging.getLogger("gajim.c.jingle_session")

# FIXME: Move it to JingleSession.States?
class JingleStates(object):
    """
    States in which jingle session may exist
    """
    ended = 0
    pending = 1
    active = 2

class OutOfOrder(Exception):
    """
    Exception that should be raised when an action is received when in the wrong
    state
    """

class TieBreak(Exception):
    """
    Exception that should be raised in case of a tie, when we overrule the other
    action
    """

class JingleSession(object):
    """
    This represents one jingle session, that is, one or more content types
    negotiated between an initiator and a responder.
    """

    def __init__(self, con, weinitiate, jid, iq_id=None, sid=None,
                werequest=False):
        """
        con -- connection object,
        weinitiate -- boolean, are we the initiator?
        jid - jid of the other entity
        """
        self.contents = {} # negotiated contents
        self.connection = con # connection to use
        # our full jid
        self.ourjid = gajim.get_jid_from_account(self.connection.name)
        if con.server_resource:
            self.ourjid = self.ourjid + '/' + con.server_resource
        self.peerjid = jid # jid we connect to
        # jid we use as the initiator
        self.initiator = weinitiate and self.ourjid or self.peerjid
        # jid we use as the responder
        self.responder = weinitiate and self.peerjid or self.ourjid
        # are we an initiator?
        self.weinitiate = weinitiate
        # Are we requesting or offering a file?
        self.werequest = werequest
        self.request = False
        # what state is session in? (one from JingleStates)
        self.state = JingleStates.ended
        if not sid:
            sid = con.connection.getAnID()
        self.sid = sid # sessionid
        # iq stanza id, used to determine which sessions to summon callback
        # later on when iq-result stanza arrives
        if iq_id is not None:
            self.iq_ids = [iq_id]
        else:
            self.iq_ids = []
        self.accepted = True # is this session accepted by user
        # Tells whether this session is a file transfer or not
        self.session_type_FT = False
        # callbacks to call on proper contents
        # use .prepend() to add new callbacks, especially when you're going
        # to send error instead of ack
        self.callbacks = {
                'content-accept':       [self.__ack, self.__on_content_accept,
                                         self.__broadcast],
                'content-add':          [self.__ack,
                                        self.__on_content_add, self.__broadcast
                                        ], #TODO
                'content-modify':       [self.__ack], #TODO
                'content-reject':       [self.__ack, self.__on_content_remove],
                'content-remove':       [self.__ack, self.__on_content_remove],
                'description-info':     [self.__ack, self.__broadcast], #TODO
                'security-info':        [self.__ack], #TODO
                'session-accept':       [self.__ack, self.__on_session_accept,
                                         self.__on_content_accept,
                                         self.__broadcast],
                'session-info':         [self.__ack, self.__broadcast,
                                         self.__on_session_info ],
                'session-initiate':     [self.__ack, self.__on_session_initiate,
                                         self.__broadcast],
                'session-terminate':    [self.__ack,self.__on_session_terminate,
                                         self.__broadcast_all],
                'transport-info':       [self.__ack, self.__broadcast],
                'transport-replace':    [self.__ack, self.__broadcast,
                                         self.__on_transport_replace], #TODO
                'transport-accept':     [self.__ack], #TODO
                'transport-reject':     [self.__ack], #TODO
                'iq-result':            [self.__broadcast],
                'iq-error':             [self.__on_error],
        }

    def collect_iq_id(self, iq_id):
        if iq_id is not None:
            self.iq_ids.append(iq_id)

    def approve_session(self):
        """
        Called when user accepts session in UI (when we aren't the initiator)
        """
        self.accept_session()

    def decline_session(self):
        """
        Called when user declines session in UI (when we aren't the initiator)
        """
        reason = nbxmpp.Node('reason')
        reason.addChild('decline')
        self._session_terminate(reason)

    def cancel_session(self):
        """
        Called when user declines session in UI (when we aren't the initiator)
        """
        reason = nbxmpp.Node('reason')
        reason.addChild('cancel')
        self._session_terminate(reason)

    def approve_content(self, media, name=None):
        content = self.get_content(media, name)
        if content:
            content.accepted = True
            self.on_session_state_changed(content)

    def reject_content(self, media, name=None):
        content = self.get_content(media, name)
        if content:
            if self.state == JingleStates.active:
                self.__content_reject(content)
            content.destroy()
            self.on_session_state_changed()

    def end_session(self):
        """
        Called when user stops or cancel session in UI
        """
        reason = nbxmpp.Node('reason')
        if self.state == JingleStates.active:
            reason.addChild('success')
        else:
            reason.addChild('cancel')
        self._session_terminate(reason)

    def get_content(self, media=None, name=None):
        if media is None:
            return
        for content in self.contents.values():
            if content.media == media:
                if name is None or content.name == name:
                    return content

    def add_content(self, name, content, creator='we'):
        """
        Add new content to session. If the session is active, this will send
        proper stanza to update session

        Creator must be one of ('we', 'peer', 'initiator', 'responder')
        """
        assert creator in ('we', 'peer', 'initiator', 'responder')
        if (creator == 'we' and self.weinitiate) or (creator == 'peer' and \
        not self.weinitiate):
            creator = 'initiator'
        elif (creator == 'peer' and self.weinitiate) or (creator == 'we' and \
        not self.weinitiate):
            creator = 'responder'
        content.creator = creator
        content.name = name
        self.contents[(creator, name)] = content
        if (creator == 'initiator') == self.weinitiate:
            # The content is from us, accept it
            content.accepted = True

    def remove_content(self, creator, name, reason=None):
        """
        Remove the content `name` created by `creator`
        by sending content-remove, or by sending session-terminate if
        there is no content left.
        """
        if (creator, name) in self.contents:
            content = self.contents[(creator, name)]
            self.__content_remove(content, reason)
            self.contents[(creator, name)].destroy()
        if not self.contents:
            self.end_session()

    def modify_content(self, creator, name, transport = None):
        '''
        Currently used for transport replacement
        '''
        content = self.contents[(creator,name)]
        transport.set_sid(content.transport.sid)
        transport.set_file_props(content.transport.file_props)
        content.transport = transport
        # The content will have to be resend now that it is modified
        content.sent = False
        content.accepted = True

    def on_session_state_changed(self, content=None):
        if self.state == JingleStates.ended:
            # Session not yet started, only one action possible: session-initiate
            if self.is_ready() and self.weinitiate:
                self.__session_initiate()
        elif self.state == JingleStates.pending:
            # We can either send a session-accept or a content-add
            if self.is_ready() and not self.weinitiate:
                self.__session_accept()
            elif content and (content.creator == 'initiator') == self.weinitiate:
                self.__content_add(content)
            elif content and self.weinitiate:
                self.__content_accept(content)
        elif self.state == JingleStates.active:
            # We can either send a content-add or a content-accept. However, if
            # we are sending a file we can only use session_initiate.
            if not content:
                return
            we_created_content = (content.creator == 'initiator') \
                                 == self.weinitiate
            if we_created_content and content.media == 'file':
                self.__session_initiate()
            if we_created_content:
                # We initiated this content. It's a pending content-add.
                self.__content_add(content)
            else:
                # The other side created this content, we accept it.
                self.__content_accept(content)

    def is_ready(self):
        """
        Return True when all codecs and candidates are ready (for all contents)
        """
        return (any((content.is_ready() for content in self.contents.values()))
            and self.accepted)

    def accept_session(self):
        """
        Mark the session as accepted
        """
        self.accepted = True
        self.on_session_state_changed()

    def start_session(self):
        """
        Mark the session as ready to be started
        """
        self.accepted = True
        self.on_session_state_changed()

    def send_session_info(self):
        pass

    def send_content_accept(self, content):
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('content-accept')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)

    def send_transport_info(self, content):
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('transport-info')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())

    def send_description_info(self, content):
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('description-info')
        jingle.addChild(node=content)
        self.connection.connection.send(stanza)

    def on_stanza(self, stanza):
        """
        A callback for ConnectionJingle. It gets stanza, then tries to send it to
        all internally registered callbacks. First one to raise
        nbxmpp.NodeProcessed breaks function
        """
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
            if action not in ['session-initiate','session-terminate'] \
                    and self.state == JingleStates.ended:
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

    def __ack(self, stanza, jingle, error, action):
        """
        Default callback for action stanzas -- simple ack and stop processing
        """
        response = stanza.buildReply('result')
        response.delChild(response.getQuery())
        self.connection.connection.send(response)

    def __on_error(self, stanza, jingle, error, action):
        # FIXME
        text = error.getTagData('text')
        error_name = None
        for child in error.getChildren():
            if child.getNamespace() == nbxmpp.NS_JINGLE_ERRORS:
                error_name = child.getName()
                break
            elif child.getNamespace() == nbxmpp.NS_STANZAS:
                error_name = child.getName()
        self.__dispatch_error(error_name, text, error.getAttr('type'))

    def transport_replace(self):
        transport = JingleTransportIBB()
        # For debug only, delete this and replace for a function
        # that will identify contents by its sid
        for creator, name in self.contents.keys():
            self.modify_content(creator, name, transport)
            cont = self.contents[(creator, name)]
            cont.transport = transport
        stanza, jingle = self.__make_jingle('transport-replace')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'transport-replace')
        self.connection.connection.send(stanza)
        self.state = JingleStates.pending

    def __on_transport_replace(self, stanza, jingle, error, action):
        for content in jingle.iterTags('content'):
            creator = content['creator']
            name = content['name']
            if (creator, name) in self.contents:
                transport_ns = content.getTag('transport').getNamespace()
                if transport_ns == nbxmpp.NS_JINGLE_ICE_UDP:
                    # FIXME: We don't manage anything else than ICE-UDP now...
                    # What was the previous transport?!?
                    # Anyway, content's transport is not modifiable yet
                    pass
                elif transport_ns == nbxmpp.NS_JINGLE_IBB:
                    transport = JingleTransportIBB()
                    self.modify_content(creator, name, transport)
                    self.state = JingleStates.pending
                    self.contents[(creator,name)].state = STATE_TRANSPORT_REPLACE
                    self.__ack(stanza, jingle, error, action)
                    self.__session_accept()
                    self.contents[(creator,name)].start_IBB_transfer()
                else:
                    stanza, jingle = self.__make_jingle('transport-reject')
                    content = jingle.setTag('content', attrs={'creator': creator,
                            'name': name})
                    content.setTag('transport', namespace=transport_ns)
                    self.connection.connection.send(stanza)
                    raise nbxmpp.NodeProcessed
            else:
                # FIXME: This ressource is unknown to us, what should we do?
                # For now, reject the transport
                stanza, jingle = self.__make_jingle('transport-reject')
                c = jingle.setTag('content', attrs={'creator': creator,
                        'name': name})
                c.setTag('transport', namespace=transport_ns)
                self.connection.connection.send(stanza)
                raise nbxmpp.NodeProcessed

    def __on_session_info(self, stanza, jingle, error, action):
        # TODO: ringing, active, (un)hold, (un)mute
        if self.state != JingleStates.active:
            raise OutOfOrder
        payload = jingle.getPayload()
        for p in payload:
            if p.getName() == 'checksum':
                hash_ = p.getTag('file').getTag(name='hash',
                    namespace=nbxmpp.NS_HASHES)
                algo = hash_.getAttr('algo')
                if algo in nbxmpp.Hashes.supported:
                    file_props = FilesProp.getFileProp(self.connection.name,
                                                       self.sid)
                    file_props.algo = algo
                    file_props.hash_ = hash_.getData()
                    raise nbxmpp.NodeProcessed
        self.__send_error(stanza, 'feature-not-implemented', 'unsupported-info',
                          type_='modify')
        raise nbxmpp.NodeProcessed

    def __on_content_remove(self, stanza, jingle, error, action):
        for content in jingle.iterTags('content'):
            creator = content['creator']
            name = content['name']
            if (creator, name) in self.contents:
                content = self.contents[(creator, name)]
                # TODO: this will fail if content is not an RTP content
                gajim.nec.push_incoming_event(JingleDisconnectedReceivedEvent(
                    None, conn=self.connection, jingle_session=self,
                    media=content.media, reason='removed'))
                content.destroy()
        if not self.contents:
            reason = nbxmpp.Node('reason')
            reason.setTag('success')
            self._session_terminate(reason)

    def __on_session_accept(self, stanza, jingle, error, action):
        # FIXME
        if self.state != JingleStates.pending:
            raise OutOfOrder
        self.state = JingleStates.active

    def __on_content_accept(self, stanza, jingle, error, action):
        """
        Called when we get content-accept stanza or equivalent one (like
        session-accept)
        """
        # check which contents are accepted
        for content in jingle.iterTags('content'):
            creator = content['creator']
            # TODO
            name = content['name']

    def __on_content_add(self, stanza, jingle, error, action):
        if self.state == JingleStates.ended:
            raise OutOfOrder
        parse_result = self.__parse_contents(jingle)
        contents = parse_result[0]
        rejected_contents = parse_result[1]
        for name, creator in rejected_contents:
            # TODO
            content = JingleContent()
            self.add_content(name, content, creator)
            self.__content_reject(content)
            self.contents[(content.creator, content.name)].destroy()
        gajim.nec.push_incoming_event(JingleRequestReceivedEvent(None,
            conn=self.connection, jingle_session=self, contents=contents))

    def __on_session_initiate(self, stanza, jingle, error, action):
        """
        We got a jingle session request from other entity, therefore we are the
        receiver... Unpack the data, inform the user
        """
        if self.state != JingleStates.ended:
            raise OutOfOrder
        self.initiator = jingle['initiator']
        self.responder = self.ourjid
        self.peerjid = self.initiator
        self.accepted = False   # user did not accept this session yet
        # TODO: If the initiator is unknown to the receiver (e.g., via presence
        # subscription) and the receiver has a policy of not communicating via
        # Jingle with unknown entities, it SHOULD return a <service-unavailable/>
        # error.
        # Lets check what kind of jingle session does the peer want
        contents, contents_rejected, reason_txt = self.__parse_contents(jingle)
        # If we are not receivin a file
        # Check if there's already a session with this user:
        if contents[0][0] != 'file':
            for session in self.connection.iter_jingle_sessions(self.peerjid):
                if not session is self:
                    reason = nbxmpp.Node('reason')
                    alternative_session = reason.setTag('alternative-session')
                    alternative_session.setTagData('sid', session.sid)
                    self.__ack(stanza, jingle, error, action)
                    self._session_terminate(reason)
                    raise nbxmpp.NodeProcessed
        else:
            # Stop if we don't have the requested file or the peer is not
            # allowed to request the file
            request = \
                 jingle.getTag('content').getTag('description').getTag('request')
            if request:
                self.request = True
                h = request.getTag('file').getTag('hash')
                h = h.getData() if h else None
                n = request.getTag('file').getTag('name')
                n = n.getData() if n else None
                pjid = gajim.get_jid_without_resource(self.peerjid)
                file_info = self.connection.get_file_info(pjid, h, n,
                                                     self.connection.name)
                if not file_info:
                    log.warning('The peer ' + pjid + \
                                ' is requesting a ' + \
                                'file that we dont have or ' + \
                                'it is not allowed to request')
                    self.decline_session()
                    raise nbxmpp.NodeProcessed
        # If there's no content we understand...
        if not contents:
            # TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
            reason = nbxmpp.Node('reason')
            reason.setTag(reason_txt)
            self.__ack(stanza, jingle, error, action)
            self._session_terminate(reason)
            raise nbxmpp.NodeProcessed
        self.state = JingleStates.pending
        # Send event about starting a session
        gajim.nec.push_incoming_event(JingleRequestReceivedEvent(None,
            conn=self.connection, jingle_session=self, contents=contents))

    def __broadcast(self, stanza, jingle, error, action):
        """
        Broadcast the stanza contents to proper content handlers
        """
        #if jingle is None: # it is a iq-result stanza
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
                text = 'Content %s (created by %s) does not exist' % (name, creator)
                self.__send_error(stanza, 'bad-request', text=text, type_='_modify')
                raise nbxmpp.NodeProcessed
            else:
                cn = self.contents[(creator, name)]
                cn.on_stanza(stanza, content, error, action)

    def __on_session_terminate(self, stanza, jingle, error, action):
        self.connection.delete_jingle_session(self.sid)
        reason, text = self.__reason_from_stanza(jingle)
        if reason not in ('success', 'cancel', 'decline'):
            self.__dispatch_error(reason, text)
        if text:
            text = '%s (%s)' % (reason, text)
        else:
            # TODO
            text = reason
        if reason == 'cancel' and self.session_type_FT:
            gajim.nec.push_incoming_event(JingleTransferCancelledEvent(None,
                conn=self.connection, jingle_session=self, media=None,
                reason=text))

    def __broadcast_all(self, stanza, jingle, error, action):
        """
        Broadcast the stanza to all content handlers
        """
        for content in self.contents.values():
            content.on_stanza(stanza, None, error, action)

    def __parse_contents(self, jingle):
        # TODO: Needs some reworking
        contents = []
        contents_rejected = []
        reasons = set()
        for element in jingle.iterTags('content'):
            transport = get_jingle_transport(element.getTag('transport'))
            if transport:
                transport.ourjid = self.ourjid
            content_type = get_jingle_content(element.getTag('description'))
            if content_type:
                try:
                    if transport:
                        content = content_type(self, transport)
                        self.add_content(element['name'],
                                content, 'peer')
                        contents.append((content.media,))
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

    def __dispatch_error(self, error=None, text=None, type_=None):
        if text:
            text = '%s (%s)' % (error, text)
        if type_ != 'modify':
            gajim.nec.push_incoming_event(JingleErrorReceivedEvent(None,
                conn=self.connection, jingle_session=self,
                reason=text or error))

    def __reason_from_stanza(self, stanza):
        # TODO: Move to GUI?
        reason = 'success'
        reasons = ['success', 'busy', 'cancel', 'connectivity-error',
                'decline', 'expired', 'failed-application', 'failed-transport',
                'general-error', 'gone', 'incompatible-parameters', 'media-error',
                'security-error', 'timeout', 'unsupported-applications',
                'unsupported-transports']
        tag = stanza.getTag('reason')
        text = ''
        if tag:
            text = tag.getTagData('text')
            for r in reasons:
                if tag.getTag(r):
                    reason = r
                    break
        return (reason, text)

    def __make_jingle(self, action, reason=None):
        stanza = nbxmpp.Iq(typ='set', to=nbxmpp.JID(self.peerjid),
            frm=self.ourjid)
        attrs = {'action': action,
                'sid': self.sid,
                'initiator' : self.initiator}
        jingle = stanza.addChild('jingle', attrs=attrs,
            namespace=nbxmpp.NS_JINGLE)
        if reason is not None:
            jingle.addChild(node=reason)
        return stanza, jingle

    def __send_error(self, stanza, error, jingle_error=None, text=None, type_=None):
        err_stanza = nbxmpp.Error(stanza, '%s %s' % (nbxmpp.NS_STANZAS, error))
        err = err_stanza.getTag('error')
        if type_:
            err.setAttr('type', type_)
        if jingle_error:
            err.setTag(jingle_error, namespace=nbxmpp.NS_JINGLE_ERRORS)
        if text:
            err.setTagData('text', text)
        self.connection.connection.send(err_stanza)
        self.__dispatch_error(jingle_error or error, text, type_)

    def __append_content(self, jingle, content):
        """
        Append <content/> element to <jingle/> element, with (full=True) or
        without (full=False) <content/> children
        """
        jingle.addChild('content',
                attrs={'name': content.name, 'creator': content.creator})

    def __append_contents(self, jingle):
        """
        Append all <content/> elements to <jingle/>
        """
        # TODO: integrate with __appendContent?
        # TODO: parameters 'name', 'content'?
        for content in self.contents.values():
            if content.is_ready():
                self.__append_content(jingle, content)

    def __session_initiate(self):
        assert self.state == JingleStates.ended
        stanza, jingle = self.__make_jingle('session-initiate')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'session-initiate-sent')
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())
        self.state = JingleStates.pending

    def __session_accept(self):
        assert self.state == JingleStates.pending
        stanza, jingle = self.__make_jingle('session-accept')
        self.__append_contents(jingle)
        self.__broadcast(stanza, jingle, None, 'session-accept-sent')
        self.connection.connection.send(stanza)
        self.collect_iq_id(stanza.getID())
        self.state = JingleStates.active

    def __session_info(self, payload=None):
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('session-info')
        if payload:
            jingle.addChild(node=payload)
        self.connection.connection.send(stanza)

    def _JingleFileTransfer__session_info(self, p):
        # For some strange reason when I call
        # self.session.__session_info(h) from the jingleFileTransfer object
        # within a thread, this method gets called instead. Even though, it
        # isn't being called explicitly.
        self.__session_info(p)

    def _session_terminate(self, reason=None):
        stanza, jingle = self.__make_jingle('session-terminate', reason=reason)
        self.__broadcast_all(stanza, jingle, None, 'session-terminate-sent')
        if self.connection.connection and self.connection.connected >= 2:
            self.connection.connection.send(stanza)
        # TODO: Move to GUI?
        reason, text = self.__reason_from_stanza(jingle)
        if reason not in ('success', 'cancel', 'decline'):
            self.__dispatch_error(reason, text)
        if text:
            text = '%s (%s)' % (reason, text)
        else:
            text = reason
        self.connection.delete_jingle_session(self.sid)
        gajim.nec.push_incoming_event(JingleDisconnectedReceivedEvent(None,
            conn=self.connection, jingle_session=self, media=None,
            reason=text))

    def __content_add(self, content):
        # TODO: test
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('content-add')
        self.__append_content(jingle, content)
        self.__broadcast(stanza, jingle, None, 'content-add-sent')
        id_ = self.connection.connection.send(stanza)
        self.collect_iq_id(id_)

    def __content_accept(self, content):
        # TODO: test
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('content-accept')
        self.__append_content(jingle, content)
        self.__broadcast(stanza, jingle, None, 'content-accept-sent')
        id_ = self.connection.connection.send(stanza)
        self.collect_iq_id(id_)

    def __content_reject(self, content):
        assert self.state != JingleStates.ended
        stanza, jingle = self.__make_jingle('content-reject')
        self.__append_content(jingle, content)
        self.connection.connection.send(stanza)
        # TODO: this will fail if content is not an RTP content
        gajim.nec.push_incoming_event(JingleDisconnectedReceivedEvent(None,
            conn=self.connection, jingle_session=self, media=content.media,
            reason='rejected'))

    def __content_modify(self):
        assert self.state != JingleStates.ended

    def __content_remove(self, content, reason=None):
        assert self.state != JingleStates.ended
        if self.connection.connection and self.connection.connected > 1:
            stanza, jingle = self.__make_jingle('content-remove', reason=reason)
            self.__append_content(jingle, content)
            self.connection.connection.send(stanza)
        # TODO: this will fail if content is not an RTP content
        gajim.nec.push_incoming_event(JingleDisconnectedReceivedEvent(None,
            conn=self.connection, jingle_session=self, media=content.media,
            reason='removed'))

    def content_negotiated(self, media):
        gajim.nec.push_incoming_event(JingleConnectedReceivedEvent(None,
            conn=self.connection, jingle_session=self, media=media))


