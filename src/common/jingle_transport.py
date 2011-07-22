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

"""
Handles Jingle Transports (currently only ICE-UDP)
"""

import xmpp
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
    datagram = 1
    streaming = 2


class JingleTransport(object):
    """
    An abstraction of a transport in Jingle sessions
    """

    def __init__(self, type_):
        self.type = type_
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
        transport = xmpp.Node('transport', payload=candidates)
        return transport

    def parse_transport_stanza(self, transport):
        """
        Return the list of transport candidates from a transport stanza
        """
        return []

class JingleTransportSocks5(JingleTransport):
    """
    Socks5 transport in jingle scenario
    Note: Don't forget to call set_file_props after initialization
    """
    def __init__(self, node=None):
        JingleTransport.__init__(self, TransportType.streaming)
        self.connection = None
        self.remote_candidates = []
        self.sid = None
        if node and node.getAttr('sid'):
            self.sid = node.getAttr('sid')

    def set_file_props(self, file_props):
        self.file_props = file_props

    def set_our_jid(self, jid):
        self.ourjid = jid

    def set_connection(self, conn):
        self.connection = conn
        if not self.sid:
            self.sid = self.connection.connection.getAnID()

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

        return xmpp.Node('candidate', attrs=attrs)

    def make_transport(self, candidates=None):
        self._add_local_ips_as_candidates()
        self._add_additional_candidates()
        self._add_proxy_candidates()
        transport = JingleTransport.make_transport(self, candidates)
        transport.setNamespace(xmpp.NS_JINGLE_BYTESTREAM)
        transport.setAttr('sid', self.sid)
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
                'port': candidate['port'],
                'cid': candidate['cid'],
                'type': typ
            }
            candidates.append(cand)

            # we need this when we construct file_props on session-initiation
        self.remote_candidates = candidates
        return candidates


    def _add_local_ips_as_candidates(self):
        if not self.connection:
            return
        local_ip_cand = []
        port = gajim.config.get('file_transfers_port')
        type_preference = 126 #type preference of connection type. XEP-0260 section 2.2
        c = {'host': self.connection.peerhost[0]}
        c['candidate_id'] = self.connection.connection.getAnID()
        c['port'] = port
        c['type'] = 'direct'
        c['jid'] = self.ourjid
        c['priority'] = (2**16) * type_preference

        local_ip_cand.append(c)

        for addr in socket.getaddrinfo(socket.gethostname(), None):
            if not addr[4][0] in local_ip_cand and not addr[4][0].startswith('127'):
                c = {'host': addr[4][0]}
                c['candidate_id'] = self.connection.connection.getAnID()
                c['port'] = port
                c['type'] = 'direct'
                c['jid'] = self.ourjid
                c['priority'] = (2**16) * type_preference
                c['initiator'] = self.file_props['sender']
                c['target'] = self.file_props['receiver']
                local_ip_cand.append(c)

        self.candidates += local_ip_cand

    def _add_additional_candidates(self):
        if not self.connection:
            return
        type_preference = 126
        additional_ip_cand = []
        port = gajim.config.get('file_transfers_port')
        ft_add_hosts = gajim.config.get('ft_add_hosts_to_send')

        if ft_add_hosts:
            hosts = [e.strip() for e in ft_add_hosts.split(',')]
            for h in hosts:
                c = {'host': h}
                c['candidate_id'] = self.connection.connection.getAnID()
                c['port'] = port
                c['type'] = 'direct'
                c['jid'] = self.ourjid
                c['priority'] = (2**16) * type_preference
                c['initiator'] = self.file_props['sender']
                c['target'] = self.file_props['receiver']
                additional_ip_cand.append(c)
        self.candidates += additional_ip_cand

    def _add_proxy_candidates(self):
        if not self.connection:
            return
        type_preference = 10
        proxy_cand = []
        socks5conn = self.connection
        proxyhosts = socks5conn._get_file_transfer_proxies_from_config(self.file_props)

        if proxyhosts:
            self.file_props['proxy_receiver'] = unicode(
                self.file_props['receiver'])
            self.file_props['proxy_sender'] = unicode(self.file_props['sender'])
            self.file_props['proxyhosts'] = proxyhosts

            for proxyhost in proxyhosts:
                c = {'host': proxyhost['host']}
                c['candidate_id'] = self.connection.connection.getAnID()
                c['port'] = proxyhost['port']
                c['type'] = 'proxy'
                c['jid'] = proxyhost['jid']
                c['priority'] = (2**16) * type_preference
                c['initiator'] = self.file_props['sender']
                c['target'] = self.file_props['receiver']
                proxy_cand.append(c)
        self.candidates += proxy_cand

    def get_content(self):
        sesn = self.connection.get_jingle_session(self.ourjid,
            self.file_props['session-sid'])
        for content in sesn.contents.values():
            if content.transport == self:
                return content

    def _on_proxy_auth_ok(self, proxy):
        log.info('proxy auth ok for ' + str(proxy))
        # send activate request to proxy, send activated confirmation to peer
        if not self.connection:
            return
        file_props = self.file_props
        iq = xmpp.Iq(to=proxy['initiator'], typ='set')
        auth_id = "au_" + proxy['sid']
        iq.setID(auth_id)
        query = iq.setTag('query', namespace=xmpp.NS_BYTESTREAM)
        query.setAttr('sid', proxy['sid'])
        activate = query.setTag('activate')
        activate.setData(file_props['proxy_receiver'])
        iq.setID(auth_id)
        self.connection.connection.send(iq)

        content = xmpp.Node('content')
        content.setAttr('creator', 'initiator')
        c = self.get_content()
        content.setAttr('name', c.name)
        transport = xmpp.Node('transport')
        transport.setNamespace(xmpp.NS_JINGLE_BYTESTREAM)
        activated = xmpp.Node('activated')
        cid = None
        for host in self.candidates:
            if host['host'] == proxy['host'] and host['jid'] == proxy['jid'] \
            and host['port'] == proxy['port']:
                cid = host['candidate_id']
                break
        if cid is None:
            return
        activated.setAttr('cid', cid)
        transport.addChild(node=activated)
        content.addChild(node=transport)
        sesn = self.connection.get_jingle_session(self.ourjid,
            self.file_props['session-sid'])

        if sesn is None:
            return
        sesn.send_transport_info(content)


class JingleTransportIBB(JingleTransport):
    
    def __init__(self, node=None, block_sz=None):
        
        JingleTransport.__init__(self, TransportType.streaming)
        
        if block_sz:
            self.block_sz = block_sz
        else:
            self.block_sz = '4096'
            
        self.connection = None
        self.sid = None
        if node and node.getAttr('sid'):
            self.sid = node.getAttr('sid')


    def set_sid(self, sid):
        self.sid = sid
            
    def make_transport(self):
        
        transport = xmpp.Node('transport')
        transport.setNamespace(xmpp.NS_JINGLE_IBB)
        transport.setAttr('block-size', self.block_sz)
        transport.setAttr('sid', self.sid)
        return transport       
    
    def set_file_props(self, file_props):
        self.file_props = file_props

    
import farsight

class JingleTransportICEUDP(JingleTransport):
    def __init__(self, node):
        JingleTransport.__init__(self, TransportType.datagram)

    def make_candidate(self, candidate):
        types = {farsight.CANDIDATE_TYPE_HOST: 'host',
                farsight.CANDIDATE_TYPE_SRFLX: 'srflx',
                farsight.CANDIDATE_TYPE_PRFLX: 'prflx',
                farsight.CANDIDATE_TYPE_RELAY: 'relay',
                farsight.CANDIDATE_TYPE_MULTICAST: 'multicast'}
        attrs = {
                'component': candidate.component_id,
                'foundation': '1', # hack
                'generation': '0',
                'ip': candidate.ip,
                'network': '0',
                'port': candidate.port,
                'priority': int(candidate.priority), # hack
        }
        if candidate.type in types:
            attrs['type'] = types[candidate.type]
        if candidate.proto == farsight.NETWORK_PROTOCOL_UDP:
            attrs['protocol'] = 'udp'
        else:
            # we actually don't handle properly different tcp options in jingle
            attrs['protocol'] = 'tcp'
        return xmpp.Node('candidate', attrs=attrs)

    def make_transport(self, candidates=None):
        transport = JingleTransport.make_transport(self, candidates)
        transport.setNamespace(xmpp.NS_JINGLE_ICE_UDP)
        if self.candidates and self.candidates[0].username and \
                self.candidates[0].password:
            transport.setAttr('ufrag', self.candidates[0].username)
            transport.setAttr('pwd', self.candidates[0].password)
        return transport

    def parse_transport_stanza(self, transport):
        candidates = []
        for candidate in transport.iterTags('candidate'):
            cand = farsight.Candidate()
            cand.component_id = int(candidate['component'])
            cand.ip = str(candidate['ip'])
            cand.port = int(candidate['port'])
            cand.foundation = str(candidate['foundation'])
            #cand.type = farsight.CANDIDATE_TYPE_LOCAL
            cand.priority = int(candidate['priority'])

            if candidate['protocol'] == 'udp':
                cand.proto = farsight.NETWORK_PROTOCOL_UDP
            else:
                # we actually don't handle properly different tcp options in jingle
                cand.proto = farsight.NETWORK_PROTOCOL_TCP

            cand.username = str(transport['ufrag'])
            cand.password = str(transport['pwd'])

            #FIXME: huh?
            types = {'host': farsight.CANDIDATE_TYPE_HOST,
                                    'srflx': farsight.CANDIDATE_TYPE_SRFLX,
                                    'prflx': farsight.CANDIDATE_TYPE_PRFLX,
                                    'relay': farsight.CANDIDATE_TYPE_RELAY,
                                    'multicast': farsight.CANDIDATE_TYPE_MULTICAST}
            if 'type' in candidate and candidate['type'] in types:
                cand.type = types[candidate['type']]
            else:
                print 'Unknown type %s', candidate['type']
            candidates.append(cand)
        self.remote_candidates.extend(candidates)
        return candidates

transports[xmpp.NS_JINGLE_ICE_UDP] = JingleTransportICEUDP
transports[xmpp.NS_JINGLE_BYTESTREAM] = JingleTransportSocks5
transports[xmpp.NS_JINGLE_IBB] = JingleTransportIBB
