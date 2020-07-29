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

"""
Handles Jingle Transports (currently only ICE-UDP)
"""

from typing import Any  # pylint: disable=unused-import
from typing import Dict  # pylint: disable=unused-import

import logging
import socket
from enum import IntEnum, unique

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.util import generate_id

from gajim.common import app

log = logging.getLogger('gajim.c.jingle_transport')


transports = {}  # type: Dict[str, Any]

def get_jingle_transport(node):
    namespace = node.getNamespace()
    if namespace in transports:
        return transports[namespace](node)


@unique
class TransportType(IntEnum):
    """
    Possible types of a JingleTransport
    """
    ICEUDP = 1
    SOCKS5 = 2
    IBB = 3


class JingleTransport:
    """
    An abstraction of a transport in Jingle sessions
    """

    __slots__ = ['type_', 'candidates', 'remote_candidates', 'connection',
                 'file_props', 'ourjid', 'sid']

    def __init__(self, type_):
        self.type_ = type_
        self.candidates = []
        self.remote_candidates = []

        self.connection = None
        self.file_props = None
        self.ourjid = None
        self.sid = None

    def _iter_candidates(self):
        for candidate in self.candidates:
            yield self.make_candidate(candidate)

    def make_candidate(self, candidate):
        """
        Build a candidate stanza for the given candidate
        """

    def make_transport(self, candidates=None):
        """
        Build a transport stanza with the given candidates (or self.candidates if
        candidates is None)
        """
        if not candidates:
            candidates = list(self._iter_candidates())
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
            self.sid = generate_id()

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
        log.info('candidate dict, %s', candidate)
        attrs = {
            'cid': candidate['candidate_id'],
            'host': candidate['host'],
            'jid': candidate['jid'],
            'port': candidate['port'],
            'priority': candidate['priority'],
            'type': candidate['type']
        }

        return nbxmpp.Node('candidate', attrs=attrs)

    def make_transport(self, candidates=None, add_candidates=True):
        if add_candidates:
            self._add_local_ips_as_candidates()
            self._add_additional_candidates()
            self._add_proxy_candidates()
            transport = JingleTransport.make_transport(self, candidates)
        else:
            transport = nbxmpp.Node('transport')
        transport.setNamespace(Namespace.JINGLE_BYTESTREAM)
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
                'candidate_id': candidate['cid'],
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
        if not app.config.get_per('accounts', self.connection.name,
        'ft_send_local_ips'):
            return
        if not self.connection:
            return
        port = int(app.settings.get('file_transfers_port'))
        #type preference of connection type. XEP-0260 section 2.2
        type_preference = 126
        priority = (2**16) * type_preference

        hosts = set()
        local_ip_cand = []

        my_ip = self.connection.local_address
        if my_ip is None:
            log.warning('No local address available')

        else:
            candidate = {
                'host': my_ip,
                'candidate_id': generate_id(),
                'port': port,
                'type': 'direct',
                'jid': self.ourjid,
                'priority': priority
            }
            hosts.add(my_ip)
            local_ip_cand.append(candidate)

        try:
            for addrinfo in socket.getaddrinfo(socket.gethostname(), None):
                addr = addrinfo[4][0]
                if not addr in hosts and not addr.startswith('127.') and \
                addr != '::1':
                    candidate = {
                        'host': addr,
                        'candidate_id': generate_id(),
                        'port': port,
                        'type': 'direct',
                        'jid': self.ourjid,
                        'priority': priority,
                        'initiator': self.file_props.sender,
                        'target': self.file_props.receiver
                    }
                    hosts.add(addr)
                    local_ip_cand.append(candidate)
        except socket.gaierror:
            pass # ignore address-related errors for getaddrinfo

        try:
            from netifaces import interfaces, ifaddresses, AF_INET, AF_INET6
            for ifaceName in interfaces():
                addresses = ifaddresses(ifaceName)
                if AF_INET in addresses:
                    for address in addresses[AF_INET]:
                        addr = address['addr']
                        if addr in hosts or addr.startswith('127.'):
                            continue
                        candidate = {
                            'host': addr,
                            'candidate_id': generate_id(),
                            'port': port,
                            'type': 'direct',
                            'jid': self.ourjid,
                            'priority': priority,
                            'initiator': self.file_props.sender,
                            'target': self.file_props.receiver
                        }
                        hosts.add(addr)
                        local_ip_cand.append(candidate)
                if AF_INET6 in addresses:
                    for address in addresses[AF_INET6]:
                        addr = address['addr']
                        if addr in hosts or addr.startswith('::1') or \
                        addr.count(':') != 7:
                            continue
                        candidate = {
                            'host': addr,
                            'candidate_id': generate_id(),
                            'port': port,
                            'type': 'direct',
                            'jid': self.ourjid,
                            'priority': priority,
                            'initiator': self.file_props.sender,
                            'target': self.file_props.receiver
                        }
                        hosts.add(addr)
                        local_ip_cand.append(candidate)

        except ImportError:
            pass

        self._add_candidates(local_ip_cand)

    def _add_additional_candidates(self):
        if not self.connection:
            return
        type_preference = 126
        priority = (2**16) * type_preference
        additional_ip_cand = []
        port = int(app.settings.get('file_transfers_port'))
        ft_add_hosts = app.settings.get('ft_add_hosts_to_send')

        if ft_add_hosts:
            hosts = [e.strip() for e in ft_add_hosts.split(',')]
            for host in hosts:
                candidate = {
                    'host': host,
                    'candidate_id': generate_id(),
                    'port': port,
                    'type': 'direct',
                    'jid': self.ourjid,
                    'priority': priority,
                    'initiator': self.file_props.sender,
                    'target': self.file_props.receiver
                }
                additional_ip_cand.append(candidate)

        self._add_candidates(additional_ip_cand)

    def _add_proxy_candidates(self):
        if not self.connection:
            return
        type_preference = 10
        priority = (2**16) * type_preference
        proxy_cand = []
        socks5conn = self.connection
        proxyhosts = socks5conn.get_module('Bytestream')._get_file_transfer_proxies_from_config(self.file_props)

        if proxyhosts:
            self.file_props.proxyhosts = proxyhosts

            for proxyhost in proxyhosts:
                candidate = {
                    'host': proxyhost['host'],
                    'candidate_id': generate_id(),
                    'port': int(proxyhost['port']),
                    'type': 'proxy',
                    'jid': proxyhost['jid'],
                    'priority': priority,
                    'initiator': self.file_props.sender,
                    'target': self.file_props.receiver
                }
                proxy_cand.append(candidate)

        self._add_candidates(proxy_cand)

    def get_content(self):
        sesn = self.connection.get_module('Jingle').get_jingle_session(
            self.ourjid, self.file_props.sid)
        for content in sesn.contents.values():
            if content.transport == self:
                return content

    def _on_proxy_auth_ok(self, proxy):
        log.info('proxy auth ok for %s', str(proxy))
        # send activate request to proxy, send activated confirmation to peer
        if not self.connection:
            return
        sesn = self.connection.get_module('Jingle').get_jingle_session(
            self.ourjid, self.file_props.sid)
        if sesn is None:
            return

        iq = nbxmpp.Iq(to=proxy['jid'], frm=self.ourjid, typ='set')
        auth_id = "au_" + proxy['sid']
        iq.setID(auth_id)
        query = iq.setTag('query', namespace=Namespace.BYTESTREAM)
        query.setAttr('sid', proxy['sid'])
        activate = query.setTag('activate')
        activate.setData(sesn.peerjid)
        iq.setID(auth_id)
        self.connection.connection.send(iq)


        content = nbxmpp.Node('content')
        content.setAttr('creator', 'initiator')
        content_object = self.get_content()
        content.setAttr('name', content_object.name)
        transport = nbxmpp.Node('transport')
        transport.setNamespace(Namespace.JINGLE_BYTESTREAM)
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
        transport.setNamespace(Namespace.JINGLE_IBB)
        transport.setAttr('block-size', self.block_sz)
        transport.setAttr('sid', self.sid)
        return transport

try:
    from gi.repository import Farstream
except ImportError:
    pass

class JingleTransportICEUDP(JingleTransport):
    def __init__(self, node):
        JingleTransport.__init__(self, TransportType.ICEUDP)

    def make_candidate(self, candidate):
        types = {
            Farstream.CandidateType.HOST: 'host',
            Farstream.CandidateType.SRFLX: 'srflx',
            Farstream.CandidateType.PRFLX: 'prflx',
            Farstream.CandidateType.RELAY: 'relay',
            Farstream.CandidateType.MULTICAST: 'multicast'
        }
        attrs = {
            'component': candidate.component_id,
            'foundation': '1', # hack
            'generation': '0',
            'ip': candidate.ip,
            'network': '0',
            'port': candidate.port,
            'priority': int(candidate.priority), # hack
            'id': app.get_an_id()
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
        transport.setNamespace(Namespace.JINGLE_ICE_UDP)
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
            types = {
                'host': Farstream.CandidateType.HOST,
                'srflx': Farstream.CandidateType.SRFLX,
                'prflx': Farstream.CandidateType.PRFLX,
                'relay': Farstream.CandidateType.RELAY,
                'multicast': Farstream.CandidateType.MULTICAST
            }
            if 'type' in candidate and candidate['type'] in types:
                type_ = types[candidate['type']]
            else:
                log.warning('Unknown type %s', candidate['type'])
                type_ = Farstream.CandidateType.HOST
            username = str(transport['ufrag'])
            password = str(transport['pwd'])
            ttl = 0

            cand = Farstream.Candidate.new_full(foundation, component_id, ip,
                                                port, base_ip, base_port,
                                                proto, priority, type_,
                                                username, password, ttl)

            candidates.append(cand)
        self.remote_candidates.extend(candidates)
        return candidates

transports[Namespace.JINGLE_ICE_UDP] = JingleTransportICEUDP
transports[Namespace.JINGLE_BYTESTREAM] = JingleTransportSocks5
transports[Namespace.JINGLE_IBB] = JingleTransportIBB
