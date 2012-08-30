##
## Copyright (C) 2006 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gajim
import xmpp
from jingle_transport import *
from common.socks5 import Socks5ReceiverClient, Socks5SenderClient


class JingleFileTransferStates:
    '''
    This class implements the state machine design pattern
    '''

    def __init__(self, jingleft):
        self.jft = jingleft

    def action(self, args=None):
        '''
        This method MUST be overriden by a subclass
        '''
        raise Exception('This is an abstract method!!')


class StateInitialized(JingleFileTransferStates):
    '''
    This state initializes the file transfer
    '''

    def action(self, args=None):
        if self.jft.weinitiate:
            # update connection's fileprops
            self.jft._listen_host()
            # Listen on configured port for file transfer
        else:
            fingerprint = None
            if self.jft.use_security:
                fingerprint = 'client'
            # Connect to the candidate host, on success call on_connect method
            gajim.socks5queue.connect_to_hosts(self.jft.session.connection.name,
                self.jft.file_props.sid, self.jft.on_connect,
                self.jft._on_connect_error, fingerprint=fingerprint)


class StateCandSent(JingleFileTransferStates):
    '''
    This state sends our nominated candidate
    '''

    def _sendCand(self, args):
        if 'candError' in args:
            self.jft.nominated_cand['our-cand'] = False
            self.jft.send_error_candidate()
            return
        # Send candidate used
        streamhost = args['streamhost']
        self.jft.nominated_cand['our-cand'] = streamhost
        content = xmpp.Node('content')
        content.setAttr('creator', 'initiator')
        content.setAttr('name', self.jft.name)
        transport = xmpp.Node('transport')
        transport.setNamespace(xmpp.NS_JINGLE_BYTESTREAM)
        transport.setAttr('sid', self.jft.transport.sid)
        candidateused = xmpp.Node('candidate-used')
        candidateused.setAttr('cid', streamhost['cid'])
        transport.addChild(node=candidateused)
        content.addChild(node=transport)
        self.jft.session.send_transport_info(content)

    def action(self, args=None):
        self._sendCand(args)


class  StateCandReceived(JingleFileTransferStates):
    '''
    This state happens when we receive a candidate.
    It takes the arguments: canError if we receive a candidate-error
    '''

    def _recvCand(self, args):
        if 'candError' in args:
            return
        content = args['content']
        streamhost_cid = content.getTag('transport').getTag('candidate-used').\
            getAttr('cid')
        streamhost_used = None
        for cand in self.jft.transport.candidates:
            if cand['candidate_id'] == streamhost_cid:
                streamhost_used = cand
                break
        if streamhost_used == None:
            log.info("unknow streamhost")
            return
        # We save the candidate nominated by peer
        self.jft.nominated_cand['peer-cand'] = streamhost_used

    def action(self, args=None):
        self._recvCand(args)


class StateCandSentAndRecv( StateCandSent, StateCandReceived):
    '''
    This state happens when we have received and sent the candidates.
    It takes the boolean argument: sendCand in order to decide whether
    we should execute the action of when we receive or send a candidate.
    '''

    def action(self, args=None):
        if args['sendCand']:
            self._sendCand(args)
        else:
            self._recvCand(args)


class StateTransportReplace(JingleFileTransferStates):
    '''
    This state initiates transport replace
    '''

    def action(self, args=None):
        self.jft.session.transport_replace()


class StateTransfering(JingleFileTransferStates):
    '''
    This state will start the transfer depeding on the type of transport
    we have.
    '''

    def __start_IBB_transfer(self, con):
        fp = open(self.jft.file_props.file_name, 'r')
        con.OpenStream( self.jft.file_props.sid, self.jft.session.peerjid, fp,
            blocksize=4096)

    def __start_SOCK5_transfer(self):
        # It tells wether we start the transfer as client or server
        mode = None
        if self.jft.isOurCandUsed():
            mode = 'client'
            streamhost_used = self.jft.nominated_cand['our-cand']
        else:
            mode = 'server'
            streamhost_used = self.jft.nominated_cand['peer-cand']
        if streamhost_used['type'] == 'proxy':
            self.jft.file_props.is_a_proxy = True
            # This needs to be changed when requesting
            if self.jft.weinitiate:
                self.jft.file_props.proxy_sender = streamhost_used['initiator']
                self.jft.file_props.proxy_receiver = streamhost_used['target']
            else:
                self.jft.file_props.proxy_sender = streamhost_used['target']
                self.jft.file_props.proxy_receiver = streamhost_used[
                    'initiator']
        # This needs to be changed when requesting
        if not self.jft.weinitiate and streamhost_used['type'] == 'proxy':
            r = gajim.socks5queue.readers
            for reader in r:
                if r[reader].host == streamhost_used['host'] and \
                r[reader].connected:
                    return
        # This needs to be changed when requesting
        if self.jft.weinitiate and streamhost_used['type'] == 'proxy':
            s = gajim.socks5queue.senders
            for sender in s:
                if s[sender].host == streamhost_used['host'] and \
                s[sender].connected:
                    return
        if streamhost_used['type'] == 'proxy':
            self.jft.file_props.streamhost_used = True
            streamhost_used['sid'] = self.jft.file_props.sid
            self.jft.file_props.streamhosts = []
            self.jft.file_props.streamhosts.append(streamhost_used)
            self.jft.file_props.proxyhosts = []
            self.jft.file_props.proxyhosts.append(streamhost_used)
            # This needs to be changed when requesting
            if self.jft.weinitiate:
                gajim.socks5queue.idx += 1
                idx = gajim.socks5queue.idx
                sockobj = Socks5SenderClient(gajim.idlequeue, idx,
                    gajim.socks5queue, _sock=None,
                    host=str(streamhost_used['host']),
                    port=int(streamhost_used['port']), fingerprint=None,
                    connected=False, file_props=self.jft.file_props)
            else:
                sockobj = Socks5ReceiverClient(gajim.idlequeue, streamhost_used,
                    sid=self.jft.file_props.sid,
                    file_props=self.jft.file_props, fingerprint=None)
            sockobj.proxy = True
            sockobj.streamhost = streamhost_used
            gajim.socks5queue.add_sockobj(self.jft.session.connection.name,
                sockobj, 'sender')
            streamhost_used['idx'] = sockobj.queue_idx
            # If we offered the nominated candidate used, we activate
            # the proxy
            if not self.jft.isOurCandUsed():
                gajim.socks5queue.on_success[self.jft.file_props.sid] = \
                self.jft.transport._on_proxy_auth_ok
            # TODO: add on failure
        else:
            jid = gajim.get_jid_without_resource(self.jft.session.ourjid)
            gajim.socks5queue.send_file(self.jft.file_props,
                self.jft.session.connection.name, mode)

    def action(self, args=None):
        if self.jft.transport.type_ == TransportType.IBB:
            self.__start_IBB_transfer(self.jft.session.connection)

        elif self.jft.transport.type_ == TransportType.SOCKS5:
            self.__start_SOCK5_transfer()


