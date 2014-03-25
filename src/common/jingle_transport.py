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
Handles Jingle Transports (currently only ICE-UDP)
"""

import nbxmpp
import socket
from common import gajim
from common.protocol.bytestream import ConnectionSocks5Bytestream
import logging

log = logging.getLogger('gajim.c.jingle_transport')


transports = {}

def get_jingle_transport(node):
    namespace = node.getNamespace()
    if namespace in transports:
        return transports[namespace](node)


class TransportType(object):
    """
    Possible types of a JingleTransport
    """
    ICEUDP = 1
    SOCKS5 = 2
    IBB = 3


class JingleTransport(object):
    """
    An abstraction of a transport in Jingle sessions
    """

    def __init__(self, type_):
        self.type_ = type_
        self.candidates = []
        self.remote_candidates = []

    def _iter_candidates(self):
        for candidate in self.candidates:
            yield self.make_candidate(candidate)

    def make_candidate(self, candidate):
        """
        Build a candidate stanza for the given candidate
        """
        pass

    def make_transport(self, candidates=None):
        """
        Build a transport stanza with the given candidates (or self.candidates if
        candidates is None)
        """
        if not candidates:
            candidates = self._iter_candidates()
        else:
            candidates = (self.make_candidate(candidate) for candidate in candidates)
        transport = nbxmpp.Node('transport', payload=candidates)
        return transport

    def parse_transport_stanza(self, transport):
        """
        Return the list of transport candidates from a transport stanza
        """
        return []

    def set_connection(self, conn):
        self.connection = conn
        if not self.sid:
            self.sid = self.connection.connection.getAnID()

    def set_file_props(self, file_props):
        self.file_props = file_props

    def set_our_jid(self, jid):
        self.ourjid = jid

    def set_sid(self, sid):
        self.sid = sid

class JingleTransportSocks5(JingleTransport):
    """
    Socks5 transport in jingle scenario
    Note: Don't forget to call set_file_props after initialization
    """
    def __init__(self, node=None):
        JingleTransport.__init__(self, TransportType.SOCKS5)
        self.connection = None
        self.remote_candidates = []
        self.sid = None
        if node and node.getAttr('sid'):
            self.sid = node.getAttr('sid')


    def make_candidate(self, candidate):
        import logging
        log = logging.getLogger()
        log.info('candidate dict, %s' % candidate)
        attrs = {
            'cid': candidate['candidate_id'],
            'host': candidate['host'],
            'jid': candidate['jid'],
            'port': candidate['port'],
            'priority': candidate['priority'],
            'type': candidate['type']
        }

        return nbxmpp.Node('candidate', attrs=attrs)

    def make_transport(self, candidates=None, add_candidates = True):
        if  add_candidates:
            self._add_local_ips_as_candidates()
            self._add_additional_candidates()
            self._add_proxy_candidates()
            transport = JingleTransport.make_transport(self, candidates)
        else:
            transport = nbxmpp.Node('transport')
        transport.setNamespace(nbxmpp.NS_JINGLE_BYTESTREAM)
        transport.setAttr('sid', self.sid)
        if self.file_props.dstaddr:
            transport.setAttr('dstaddr', self.file_props.dstaddr)
        return transport

    def parse_transport_stanza(self, transport):
        candidates = []
        for candidate in transport.iterTags('candidate'):
            typ = 'direct' # default value
            if candidate.has_attr('type'):
                typ = candidate['type']
            cand = {
                'state': 0,
                'target': self.ourjid,
                'host': candidate['host'],
                'port': int(candidate['port']),
                'cid': candidate['cid'],
                'type': typ,
                'priority': candidate['priority']
            }
            candidates.append(cand)

            # we need this when we construct file_props on session-initiation
        if candidates:
            self.remote_candidates = candidates
        return candidates


    def _add_candidates(self, candidates):
        for cand in candidates:
            in_remote = False
            for cand2 in self.remote_candidates:
                if cand['host'] == cand2['host'] and \
                cand['port'] == cand2['port']:
                    in_remote = True
                    break
            if not in_remote:
                self.candidates.append(cand)

    def _add_local_ips_as_candidates(self):
        if not gajim.config.get_per('accounts', self.connection.name,
        'ft_send_local_ips'):
            return
        if not self.connection:
            return
        port = int(gajim.config.get('file_transfers_port'))
        #type preference of connection type. XEP-0260 section 2.2
        type_preference = 126
        priority = (2**16) * type_preference

        hosts = set()
        local_ip_cand = []

        c = {'host': self.connection.peerhost[0],
             'candidate_id': self.connection.connection.getAnID(),
             'port': port,
             'type': 'direct',
             'jid': self.ourjid,
             'priority': priority}
        hosts.add(self.connection.peerhost[0])
        local_ip_cand.append(c)

        try:
            for addrinfo in socket.getaddrinfo(socket.gethostname(), None):
                addr = addrinfo[4][0]
                if not addr in hosts and not addr.startswith('127'):
                    c = {'host': addr,
                         'candidate_id': self.connection.connection.getAnID(),
                         'port': port,
                         'type': 'direct',
                         'jid': self.ourjid,
                         'priority': priority,
                         'initiator': self.file_props.sender,
                         'target': self.file_props.receiver}
                    hosts.add(addr)
                    local_ip_cand.append(c)
        except socket.gaierror:
            pass # ignore address-related errors for getaddrinfo

        self._add_candidates(local_ip_cand)

    def _add_additional_candidates(self):
        if not self.connection:
            return
        type_preference = 126
        priority = (2**16) * type_preference
        additional_ip_cand = []
        port = int(gajim.config.get('file_transfers_port'))
        ft_add_hosts = gajim.config.get('ft_add_hosts_to_send')

        if ft_add_hosts:
            hosts = [e.strip() for e in ft_add_hosts.split(',')]
            for h in hosts:
                c = {'host': h,
                     'candidate_id': self.connection.connection.getAnID(),
                     'port': port,
                     'type': 'direct',
                     'jid': self.ourjid,
                     'priority': priority,
                     'initiator': self.file_props.sender,
                     'target': self.file_props.receiver}
                additional_ip_cand.append(c)

        self._add_candidates(additional_ip_cand)

    def _add_proxy_candidates(self):
        if not self.connection:
            return
        type_preference = 10
        priority = (2**16) * type_preference
        proxy_cand = []
        socks5conn = self.connection
        proxyhosts = socks5conn._get_file_transfer_proxies_from_config(self.file_props)

        if proxyhosts:
            self.file_props.proxyhosts = proxyhosts

            for proxyhost in proxyhosts:
                c = {'host': proxyhost['host'],
                     'candidate_id': self.connection.connection.getAnID(),
                     'port': int(proxyhost['port']),
                     'type': 'proxy',
                     'jid': proxyhost['jid'],
                     'priority': priority,
                     'initiator': self.file_props.sender,
                     'target': self.file_props.receiver}
                proxy_cand.append(c)

        self._add_candidates(proxy_cand)

    def get_content(self):
        sesn = self.connection.get_jingle_session(self.ourjid,
            self.file_props.sid)
        for content in sesn.contents.values():
            if content.transport == self:
                return content

    def _on_proxy_auth_ok(self, proxy):
        log.info('proxy auth ok for ' + str(proxy))
        # send activate request to proxy, send activated confirmation to peer
        if not self.connection:
            return
        sesn = self.connection.get_jingle_session(self.ourjid,
            self.file_props.sid)
        if sesn is None:
            return

        iq = nbxmpp.Iq(to=proxy['jid'], frm=self.ourjid, typ='set')
        auth_id = "au_" + proxy['sid']
        iq.setID(auth_id)
        query = iq.setTag('query', namespace=nbxmpp.NS_BYTESTREAM)
        query.setAttr('sid', proxy['sid'])
        activate = query.setTag('activate')
        activate.setData(sesn.peerjid)
        iq.setID(auth_id)
        self.connection.connection.send(iq)


        content = nbxmpp.Node('content')
        content.setAttr('creator', 'initiator')
        c = self.get_content()
        content.setAttr('name', c.name)
        transport = nbxmpp.Node('transport')
        transport.setNamespace(nbxmpp.NS_JINGLE_BYTESTREAM)
        transport.setAttr('sid', proxy['sid'])
        activated = nbxmpp.Node('activated')
        cid = None

        if 'cid' in proxy:
            cid = proxy['cid']
        else:
            for host in self.candidates:
                if host['host'] == proxy['host'] and host['jid'] == proxy['jid'] \
                and host['port'] == proxy['port']:
                    cid = host['candidate_id']
                    break
        if cid is None:
            raise Exception('cid is missing')
        activated.setAttr('cid', cid)
        transport.addChild(node=activated)
        content.addChild(node=transport)
        sesn.send_transport_info(content)


class JingleTransportIBB(JingleTransport):

    def __init__(self, node=None, block_sz=None):

        JingleTransport.__init__(self, TransportType.IBB)

        if block_sz:
            self.block_sz = block_sz
        else:
            self.block_sz = '4096'

        self.connection = None
        self.sid = None
        if node and node.getAttr('sid'):
            self.sid = node.getAttr('sid')


    def make_transport(self):

        transport = nbxmpp.Node('transport')
        transport.setNamespace(nbxmpp.NS_JINGLE_IBB)
        transport.setAttr('block-size', self.block_sz)
        transport.setAttr('sid', self.sid)
        return transport

try:
    from gi.repository import Farstream
except Exception:
    pass

class JingleTransportICEUDP(JingleTransport):
    def __init__(self, node):
        JingleTransport.__init__(self, TransportType.ICEUDP)

    def make_candidate(self, candidate):
        types = {Farstream.CandidateType.HOST: 'host',
            Farstream.CandidateType.SRFLX: 'srflx',
            Farstream.CandidateType.PRFLX: 'prflx',
            Farstream.CandidateType.RELAY: 'relay',
            Farstream.CandidateType.MULTICAST: 'multicast'}
        attrs = {
            'component': candidate.component_id,
            'foundation': '1', # hack
            'generation': '0',
            'ip': candidate.ip,
            'network': '0',
            'port': candidate.port,
            'priority': int(candidate.priority), # hack
            'id': gajim.get_an_id()
        }
        if candidate.type in types:
            attrs['type'] = types[candidate.type]
        if candidate.proto == Farstream.NetworkProtocol.UDP:
            attrs['protocol'] = 'udp'
        else:
            # we actually don't handle properly different tcp options in jingle
            attrs['protocol'] = 'tcp'
        return nbxmpp.Node('candidate', attrs=attrs)

    def make_transport(self, candidates=None):
        transport = JingleTransport.make_transport(self, candidates)
        transport.setNamespace(nbxmpp.NS_JINGLE_ICE_UDP)
        if self.candidates and self.candidates[0].username and \
                self.candidates[0].password:
            transport.setAttr('ufrag', self.candidates[0].username)
            transport.setAttr('pwd', self.candidates[0].password)
        return transport

    def parse_transport_stanza(self, transport):
        candidates = []
        for candidate in transport.iterTags('candidate'):
            foundation = str(candidate['foundation'])
            component_id = int(candidate['component'])
            ip = str(candidate['ip'])
            port = int(candidate['port'])
            base_ip = None
            base_port = 0
            if candidate['protocol'] == 'udp':
                proto = Farstream.NetworkProtocol.UDP
            else:
                # we actually don't handle properly different tcp options in
                # jingle
                proto = Farstream.NetworkProtocol.TCP
            priority = int(candidate['priority'])
            types = {'host': Farstream.CandidateType.HOST,
                'srflx': Farstream.CandidateType.SRFLX,
                'prflx': Farstream.CandidateType.PRFLX,
                'relay': Farstream.CandidateType.RELAY,
                'multicast': Farstream.CandidateType.MULTICAST}
            if 'type' in candidate and candidate['type'] in types:
                type_ = types[candidate['type']]
            else:
                log.warning('Unknown type %s' % candidate['type'])
                type_ = Farstream.CandidateType.HOST
            username = str(transport['ufrag'])
            password = str(transport['pwd'])
            ttl = 0

            cand = Farstream.Candidate.new_full(foundation, component_id, ip,
                port, base_ip, base_port, proto, priority, type_, username,
                password, ttl)

            candidates.append(cand)
        self.remote_candidates.extend(candidates)
        return candidates

transports[nbxmpp.NS_JINGLE_ICE_UDP] = JingleTransportICEUDP
transports[nbxmpp.NS_JINGLE_BYTESTREAM] = JingleTransportSocks5
transports[nbxmpp.NS_JINGLE_IBB] = JingleTransportIBB
