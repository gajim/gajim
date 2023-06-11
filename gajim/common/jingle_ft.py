# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


# Handles  Jingle File Transfer (XEP 0234)


from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import logging
import threading
import uuid
from enum import IntEnum
from enum import unique

import nbxmpp
from nbxmpp import JID
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import helpers
from gajim.common.events import FileRequestReceivedEvent
from gajim.common.file_props import FileProp
from gajim.common.file_props import FilesProp
from gajim.common.jingle_content import contents
from gajim.common.jingle_content import JingleContent
from gajim.common.jingle_ftstates import StateCandReceived
from gajim.common.jingle_ftstates import StateCandSent
from gajim.common.jingle_ftstates import StateCandSentAndRecv
from gajim.common.jingle_ftstates import StateInitialized
from gajim.common.jingle_ftstates import StateTransfering
from gajim.common.jingle_ftstates import StateTransportReplace
from gajim.common.jingle_transport import JingleTransportSocks5
from gajim.common.jingle_transport import TransportType
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.datetime import utc_now

if TYPE_CHECKING:
    from gajim.common.jingle_session import JingleSession
    from gajim.common.jingle_transport import JingleTransport

log = logging.getLogger('gajim.c.jingle_ft')


@unique
class State(IntEnum):
    NOT_STARTED = 0
    INITIALIZED = 1
    # We send the candidates and we are waiting for a reply
    CAND_SENT = 2
    # We received the candidates and we are waiting to reply
    CAND_RECEIVED = 3
    # We have sent and received the candidates
    # This also includes any candidate-error received or sent
    CAND_SENT_AND_RECEIVED = 4
    TRANSPORT_REPLACE = 5
    # We are transferring the file
    TRANSFERRING = 6


class JingleFileTransfer(JingleContent):
    def __init__(self,
                 session: JingleSession,
                 file_props: FileProp,
                 transport: JingleTransport | None = None,
                 senders: str | None = None
                 ) -> None:

        JingleContent.__init__(self, session, transport, senders)
        log.info('transport value: %s', transport)
        # events we might be interested in
        self.callbacks['session-initiate'] += [self.__on_session_initiate]
        self.callbacks['session-initiate-sent'] += [
            self.__on_session_initiate_sent]
        self.callbacks['content-add'] += [self.__on_session_initiate]
        self.callbacks['session-accept'] += [self.__on_session_accept]
        self.callbacks['session-terminate'] += [self.__on_session_terminate]
        self.callbacks['session-info'] += [self.__on_session_info]
        self.callbacks['transport-accept'] += [self.__on_transport_accept]
        self.callbacks['transport-replace'] += [self.__on_transport_replace]
        self.callbacks['session-accept-sent'] += [self.__transport_setup]
        # fallback transport method
        self.callbacks['transport-reject'] += [self.__on_transport_reject]
        self.callbacks['transport-info'] += [self.__on_transport_info]
        self.callbacks['iq-result'] += [self.__on_iq_result]

        self.file_props = file_props
        self.weinitiate = self.session.weinitiate
        self.werequest = self.session.werequest

        if transport is None:
            self.transport = JingleTransportSocks5()
        self.transport.set_connection(session.connection)
        self.transport.set_file_props(self.file_props)
        self.transport.set_our_jid(session.ourjid)
        log.info('ourjid: %s', session.ourjid)

        if self.session.werequest:
            self.file_props.sender = self.session.peerjid
            self.file_props.receiver = self.session.ourjid
        else:
            self.file_props.sender = self.session.ourjid
            self.file_props.receiver = self.session.peerjid
        self.file_props.session_type = 'jingle'
        self.file_props.sid = session.sid
        self.file_props.transferred_size = []
        self.file_props.transport_sid = self.transport.sid

        self.session = session
        self.media = 'file'
        self.nominated_cand = {}
        self.state = State.NOT_STARTED
        self.states = {
            State.INITIALIZED: StateInitialized(self),
            State.CAND_SENT: StateCandSent(self),
            State.CAND_RECEIVED: StateCandReceived(self),
            State.TRANSFERRING: StateTransfering(self),
            State.TRANSPORT_REPLACE: StateTransportReplace(self),
            State.CAND_SENT_AND_RECEIVED: StateCandSentAndRecv(self)
        }

    def __state_changed(self,
                        nextstate: State,
                        args: dict[str, Any] | None = None
                        ) -> None:
        # Executes the next state action and sets the next state
        current_state = self.state
        st = self.states[nextstate]
        st.action(args)
        # state can have been changed during the action. Don't go back.
        if self.state == current_state:
            self.state = nextstate

    def __on_session_initiate(self,
                              stanza: nbxmpp.Node,
                              content: nbxmpp.Node,
                              error: nbxmpp.Node | None,
                              action: str
                              ) -> None:
        log.debug('Jingle FT request received')
        self._raise_event(stanza, content)

        account = self.session.connection.name
        jid = self.session.connection.get_module('Bytestream')._ft_get_from(
            stanza)
        jid = JID.from_string(jid)
        sid = stanza.getTag('jingle').getAttr('sid')
        assert sid is not None

        ft_data = mod.FileTransfer(
            state=1,
            source=[mod.JingleFT(type='jingleft', sid=sid)],
        )

        message_data = mod.Message(
            account_=account,
            remote_jid_=jid.new_as_bare(),
            resource=jid.resource,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id=str(uuid.uuid4()),
            filetransfer=[ft_data],
        )

        app.storage.archive.insert_object(message_data)

        if self.session.request:
            # accept the request
            self.session.approve_content(self.media, self.name)
            self.session.accept_session()

    def _raise_event(self,
                     stanza: nbxmpp.Node,
                     content: nbxmpp.Node
                     ) -> None:
        con = self.session.connection
        id_ = stanza.getID()
        fjid = con.get_module('Bytestream')._ft_get_from(stanza)
        account = con.name
        jid = app.get_jid_without_resource(fjid)
        jid = JID.from_string(jid)
        if not content:
            return

        if not self.transport:
            self.transport = JingleTransportSocks5()
            self.transport.set_our_jid(self.session.ourjid)
            self.transport.set_connection(con)

        sid = stanza.getTag('jingle').getAttr('sid')
        file_props = FilesProp.getNewFileProp(account, sid)
        file_props.transport_sid = self.transport.sid

        self.transport.set_file_props(file_props)
        file_props.streamhosts.extend(self.transport.remote_candidates)

        for host in file_props.streamhosts:
            host['initiator'] = self.session.initiator
            host['target'] = self.session.responder

        file_props.session_type = 'jingle'
        desc = content.getTag('description')
        if content.getAttr('creator') == 'initiator':
            file_tag = desc.getTag('file')
            file_props.sender = fjid
            file_props.receiver = str(con.get_own_jid())
        else:
            file_tag = desc.getTag('file')
            hash_ = file_tag.getTag('hash')
            hash_ = hash_.getData() if hash_ else None
            file_name = file_tag.getTag('name')
            file_name = file_name.getData() if file_name else None
            pjid = app.get_jid_without_resource(fjid)
            file_info = con.get_module('Jingle').get_file_info(
                pjid, hash_=hash_, name=file_name, account=account)
            file_props.file_name = file_info['file-name']
            file_props.sender = str(con.get_own_jid())
            file_props.receiver = fjid
            file_props.type_ = 's'

        for child in file_tag.getChildren():
            name = child.getName()
            val = child.getData()
            if val is None:
                continue
            if name == 'name':
                file_props.name = val
            if name == 'size':
                file_props.size = int(val)
            if name == 'hash':
                file_props.algo = child.getAttr('algo')
                file_props.hash_ = val
            if name == 'date':
                file_props.date = val

        file_props.request_id = id_
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            file_props.desc = file_desc_tag.getData()
        file_props.transferred_size = []

        app.ged.raise_event(FileRequestReceivedEvent(
            conn=con,
            stanza=stanza,
            id_=id_,
            fjid=fjid,
            account=account,
            jid=jid,
            file_props=file_props))

    def __on_session_initiate_sent(self,
                                   stanza: nbxmpp.Node,
                                   content: nbxmpp.Node,
                                   error: nbxmpp.Node | None,
                                   action: str
                                   ) -> None:
        pass

    def __send_hash(self) -> None:
        # Send hash in a session info
        checksum = nbxmpp.Node(tag='checksum',
                               payload=[
                                   nbxmpp.Node(tag='file',
                                               payload=[self._compute_hash()])
                               ])
        checksum.setNamespace(Namespace.JINGLE_FILE_TRANSFER_5)
        self.session.__session_info(checksum)
        pjid = app.get_jid_without_resource(self.session.peerjid)
        file_info = {
            'name': self.file_props.name,
            'file-name': self.file_props.file_name,
            'hash': self.file_props.hash_,
            'size': self.file_props.size,
            'date': self.file_props.date,
            'peerjid': pjid
        }
        self.session.connection.get_module('Jingle').set_file_info(file_info)

    def _compute_hash(self) -> nbxmpp.Hashes2 | None:
        # Calculates the hash and returns a xep-300 hash stanza
        if self.file_props.algo is None:
            return
        try:
            file_ = open(self.file_props.file_name, 'rb')
        except OSError:
            # can't open file
            return
        h = nbxmpp.Hashes2()
        hash_ = h.calculateHash(self.file_props.algo, file_)
        file_.close()
        # DEBUG
        # hash_ = '1294809248109223'
        if not hash_:
            # Hash algorithm not supported
            return
        self.file_props.hash_ = hash_
        h.addHash(hash_, self.file_props.algo)
        return h

    def on_cert_received(self) -> None:
        self.session.approve_session()
        self.session.approve_content('file', name=self.name)

    def __on_session_accept(self,
                            stanza: nbxmpp.Node,
                            content: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        log.info('__on_session_accept')
        if self.state == State.TRANSPORT_REPLACE:
            # If we are requesting we don't have the file
            if self.session.werequest:
                raise nbxmpp.NodeProcessed
            # We send the file
            self.__state_changed(State.TRANSFERRING)
            raise nbxmpp.NodeProcessed
        self.file_props.streamhosts = self.transport.remote_candidates
        # Calculate file hash in a new thread
        # if we haven't sent the hash already.
        if self.file_props.hash_ is None and self.file_props.algo and \
                not self.werequest:
            self.hash_thread = threading.Thread(target=self.__send_hash)
            self.hash_thread.start()
        for host in self.file_props.streamhosts:
            host['initiator'] = self.session.initiator
            host['target'] = self.session.responder
            host['sid'] = self.file_props.sid
        if self.transport.type_ == TransportType.SOCKS5:
            sid = self.file_props.transport_sid
            app.socks5queue.connect_to_hosts(self.session.connection.name,
                                             sid,
                                             self.on_connect,
                                             self._on_connect_error,
                                             receiving=False)
            raise nbxmpp.NodeProcessed
        self.__state_changed(State.TRANSFERRING)
        raise nbxmpp.NodeProcessed

    def __on_session_terminate(self,
                               stanza: nbxmpp.Node,
                               content: nbxmpp.Node,
                               error: nbxmpp.Node | None,
                               action: str
                               ) -> None:
        log.info('__on_session_terminate')

    def __on_session_info(self,
                          stanza: nbxmpp.Node,
                          content: nbxmpp.Node,
                          error: nbxmpp.Node | None,
                          action: str
                          ) -> None:
        pass

    def __on_transport_accept(self,
                              stanza: nbxmpp.Node,
                              content: nbxmpp.Node,
                              error: nbxmpp.Node | None,
                              action: str
                              ) -> None:
        log.info('__on_transport_accept')

    def __on_transport_replace(self,
                               stanza: nbxmpp.Node,
                               content: nbxmpp.Node,
                               error: nbxmpp.Node | None,
                               action: str
                               ) -> None:
        log.info('__on_transport_replace')

    def __on_transport_reject(self,
                              stanza: nbxmpp.Node,
                              content: nbxmpp.Node,
                              error: nbxmpp.Node | None,
                              action: str
                              ) -> None:
        log.info('__on_transport_reject')

    def __on_transport_info(self,
                            stanza: nbxmpp.Node,
                            content: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        log.info('__on_transport_info')
        cand_error = content.getTag('transport').getTag('candidate-error')
        cand_used = content.getTag('transport').getTag('candidate-used')
        if (cand_error or cand_used) and \
                self.state >= State.CAND_SENT_AND_RECEIVED:
            raise nbxmpp.NodeProcessed
        if cand_error:
            if not app.socks5queue.listener.connections:
                app.socks5queue.listener.disconnect()
            self.nominated_cand['peer-cand'] = False
            if self.state == State.CAND_SENT:
                if not self.nominated_cand['our-cand'] and \
                   not self.nominated_cand['peer-cand']:
                    if not self.weinitiate:
                        return
                    self.__state_changed(State.TRANSPORT_REPLACE)
                else:
                    response = stanza.buildReply('result')
                    response.delChild(response.getQuery())
                    self.session.connection.connection.send(response)
                    self.__state_changed(State.TRANSFERRING)
                    raise nbxmpp.NodeProcessed
            else:
                args = {'candError': True}
                self.__state_changed(State.CAND_RECEIVED, args)
            return
        if cand_used:
            streamhost_cid = cand_used.getAttr('cid')
            streamhost_used = None
            for cand in self.transport.candidates:
                if cand['candidate_id'] == streamhost_cid:
                    streamhost_used = cand
                    break
            if streamhost_used is None or streamhost_used['type'] == 'proxy':
                if (app.socks5queue.listener and
                        not app.socks5queue.listener.connections):
                    app.socks5queue.listener.disconnect()
        if content.getTag('transport').getTag('activated'):
            self.state = State.TRANSFERRING
            app.socks5queue.send_file(self.file_props,
                                      self.session.connection.name, 'client')
            return
        args = {'content': content,
                'sendCand': False}
        if self.state == State.CAND_SENT:
            self.__state_changed(State.CAND_SENT_AND_RECEIVED, args)
            self.__state_changed(State.TRANSFERRING)
            raise nbxmpp.NodeProcessed
        self.__state_changed(State.CAND_RECEIVED, args)

    def __on_iq_result(self,
                       stanza: nbxmpp.Node,
                       content: nbxmpp.Node,
                       error: nbxmpp.Node | None,
                       action: str
                       ) -> None:
        log.info('__on_iq_result')

        if self.state in (State.NOT_STARTED, State.CAND_RECEIVED):
            self.__state_changed(State.INITIALIZED)
        elif self.state == State.CAND_SENT_AND_RECEIVED:
            if (not self.nominated_cand['our-cand'] and
                    not self.nominated_cand['peer-cand']):
                if not self.weinitiate:
                    return
                self.__state_changed(State.TRANSPORT_REPLACE)
                return
            # initiate transfer
            self.__state_changed(State.TRANSFERRING)

    def __transport_setup(self,
                          stanza: nbxmpp.Node,
                          content: nbxmpp.Node,
                          error: nbxmpp.Node | None,
                          action: str
                          ) -> None:
        # Sets up a few transport specific things for the file transfer
        if self.transport.type_ == TransportType.IBB:
            # No action required, just set the state to transferring
            self.state = State.TRANSFERRING
        else:
            self._listen_host()

    def on_connect(self, streamhost):
        '''
        send candidate-used stanza
        '''
        log.info('send_candidate_used')
        if streamhost is None:
            return
        args = {'streamhost': streamhost,
                'sendCand': True}
        self.nominated_cand['our-cand'] = streamhost
        self.__send_candidate(args)

    def _on_connect_error(self, sid: str) -> None:
        log.info('connect error, sid=%s', sid)
        args = {'candError': True,
                'sendCand': True}
        self.__send_candidate(args)

    def __send_candidate(self, args: dict[str, Any]) -> None:
        if self.state == State.CAND_RECEIVED:
            self.__state_changed(State.CAND_SENT_AND_RECEIVED, args)
        else:
            self.__state_changed(State.CAND_SENT, args)

    def _store_socks5_sid(self, sid: str, hash_id: str) -> None:
        # callback from socsk5queue.start_listener
        self.file_props.hash_ = hash_id

    def _listen_host(self) -> None:
        receiver = self.file_props.receiver
        sender = self.file_props.sender
        sha_str = helpers.get_auth_sha(self.file_props.sid, sender,
                                       receiver)
        self.file_props.sha_str = sha_str
        port = app.settings.get('file_transfers_port')
        listener = app.socks5queue.start_listener(
            port,
            sha_str,
            self._store_socks5_sid,
            self.file_props,
            typ='sender' if self.weinitiate else 'receiver')
        if not listener:
            # send error message, notify the user
            return

    def is_our_candidate_used(self) -> bool:
        '''
        If this method returns true then the candidate we nominated will be
        used, if false, the candidate nominated by peer will be used
        '''

        if not self.nominated_cand['peer-cand']:
            return True
        if not self.nominated_cand['our-cand']:
            return False
        peer_pr = int(self.nominated_cand['peer-cand']['priority'])
        our_pr = int(self.nominated_cand['our-cand']['priority'])
        if peer_pr != our_pr:
            return our_pr > peer_pr
        return self.weinitiate

    def start_ibb_transfer(self) -> None:
        if self.file_props.type_ == 's':
            self.__state_changed(State.TRANSFERRING)


def get_content(desc) -> JingleFileTransfer:
    return JingleFileTransfer


contents[Namespace.JINGLE_FILE_TRANSFER_5] = get_content
