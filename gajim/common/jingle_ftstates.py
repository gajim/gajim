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

import logging

import nbxmpp
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.jingle_transport import TransportType
from gajim.common.socks5 import Socks5ReceiverClient
from gajim.common.socks5 import Socks5SenderClient

log = logging.getLogger('gajim.c.jingle_ftstates')


class JingleFileTransferStates:
    '''
    This class implements the state machine design pattern
    '''

    def __init__(self, jingleft):
        self.jft = jingleft

    def action(self, args=None):
        '''
        This method MUST be overridden by a subclass
        '''
        raise NotImplementedError('This is an abstract method!')


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
            app.socks5queue.connect_to_hosts(self.jft.session.connection.name,
                self.jft.file_props.transport_sid, self.jft.on_connect,
                self.jft._on_connect_error, fingerprint=fingerprint)


class StateCandSent(JingleFileTransferStates):
    '''
    This state sends our nominated candidate
    '''

    def _send_candidate(self, args):
        if 'candError' in args:
            self.jft.nominated_cand['our-cand'] = False
            self.jft.send_error_candidate()
            return
        # Send candidate used
        streamhost = args['streamhost']
        self.jft.nominated_cand['our-cand'] = streamhost
        content = nbxmpp.Node('content')
        content.setAttr('creator', 'initiator')
        content.setAttr('name', self.jft.name)
        transport = nbxmpp.Node('transport')
        transport.setNamespace(Namespace.JINGLE_BYTESTREAM)
        transport.setAttr('sid', self.jft.transport.sid)
        candidateused = nbxmpp.Node('candidate-used')
        candidateused.setAttr('cid', streamhost['candidate_id'])
        transport.addChild(node=candidateused)
        content.addChild(node=transport)
        self.jft.session.send_transport_info(content)

    def action(self, args=None):
        self._send_candidate(args)


class StateCandReceived(JingleFileTransferStates):
    '''
    This state happens when we receive a candidate.
    It takes the arguments: canError if we receive a candidate-error
    '''

    def _recv_candidate(self, args):
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
        if streamhost_used is None:
            log.info("unknown streamhost")
            return
        # We save the candidate nominated by peer
        self.jft.nominated_cand['peer-cand'] = streamhost_used

    def action(self, args=None):
        self._recv_candidate(args)


class StateCandSentAndRecv(StateCandSent, StateCandReceived):
    '''
    This state happens when we have received and sent the candidates.
    It takes the boolean argument: sendCand in order to decide whether
    we should execute the action of when we receive or send a candidate.
    '''

    def action(self, args=None):
        if args['sendCand']:
            self._send_candidate(args)
        else:
            self._recv_candidate(args)


class StateTransportReplace(JingleFileTransferStates):
    '''
    This state initiates transport replace
    '''

    def action(self, args=None):
        self.jft.session.transport_replace()


class StateTransfering(JingleFileTransferStates):
    '''
    This state will start the transfer depending on the type of transport
    we have.
    '''

    def _start_ibb_transfer(self, con):
        self.jft.file_props.transport_sid = self.jft.transport.sid
        fp = open(self.jft.file_props.file_name, 'rb')
        con.get_module('IBB').send_open(self.jft.session.peerjid,
                                        self.jft.file_props.sid,
                                        fp)

    def _start_sock5_transfer(self):
        # It tells whether we start the transfer as client or server
        mode = None
        if self.jft.is_our_candidate_used():
            mode = 'client'
            streamhost_used = self.jft.nominated_cand['our-cand']
            app.socks5queue.remove_server(self.jft.file_props.transport_sid)
        else:
            mode = 'server'
            streamhost_used = self.jft.nominated_cand['peer-cand']
            app.socks5queue.remove_client(self.jft.file_props.transport_sid)
            app.socks5queue.remove_other_servers(streamhost_used['host'])
        if streamhost_used['type'] == 'proxy':
            self.jft.file_props.is_a_proxy = True
            if self.jft.file_props.type_ == 's' and self.jft.weinitiate:
                self.jft.file_props.proxy_sender = streamhost_used['initiator']
                self.jft.file_props.proxy_receiver = streamhost_used['target']
            else:
                self.jft.file_props.proxy_sender = streamhost_used['target']
                self.jft.file_props.proxy_receiver = streamhost_used[
                    'initiator']
            if self.jft.file_props.type_ == 's':
                s = app.socks5queue.senders
                for sender in s:
                    if s[sender].host == streamhost_used['host'] and \
                    s[sender].connected:
                        return
            elif self.jft.file_props.type_ == 'r':
                r = app.socks5queue.readers
                for reader in r:
                    if r[reader].host == streamhost_used['host'] and \
                    r[reader].connected:
                        return
            else:
                raise TypeError
            self.jft.file_props.streamhost_used = True
            streamhost_used['sid'] = self.jft.file_props.transport_sid
            self.jft.file_props.streamhosts = []
            self.jft.file_props.streamhosts.append(streamhost_used)
            self.jft.file_props.proxyhosts = []
            self.jft.file_props.proxyhosts.append(streamhost_used)
            if self.jft.file_props.type_ == 's':
                app.socks5queue.idx += 1
                idx = app.socks5queue.idx
                sockobj = Socks5SenderClient(app.idlequeue, idx,
                                             app.socks5queue, _sock=None,
                                             host=str(streamhost_used['host']),
                                             port=int(streamhost_used['port']),
                                             fingerprint=None, connected=False,
                                             file_props=self.jft.file_props)
            else:
                sockobj = Socks5ReceiverClient(app.idlequeue, streamhost_used,
                    transport_sid=self.jft.file_props.transport_sid,
                    file_props=self.jft.file_props, fingerprint=None)
            sockobj.proxy = True
            sockobj.streamhost = streamhost_used
            app.socks5queue.add_sockobj(self.jft.session.connection.name,
                                          sockobj)
            streamhost_used['idx'] = sockobj.queue_idx
            # If we offered the nominated candidate used, we activate
            # the proxy
            if not self.jft.is_our_candidate_used():
                app.socks5queue.on_success[self.jft.file_props.transport_sid]\
                    = self.jft.transport._on_proxy_auth_ok
            # TODO: add on failure
        else:
            app.socks5queue.send_file(self.jft.file_props,
                                        self.jft.session.connection.name, mode)

    def action(self, args=None):
        if self.jft.transport.type_ == TransportType.IBB:
            self._start_ibb_transfer(self.jft.session.connection)
        elif self.jft.transport.type_ == TransportType.SOCKS5:
            self._start_sock5_transfer()
