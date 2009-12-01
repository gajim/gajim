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

transports = {}

def get_jingle_transport(node):
	namespace = node.getNamespace()
	if namespace in transports:
		return transports[namespace]()


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
		transport = xmpp.Node('transport', payload=candidates)
		return transport

	def parse_transport_stanza(self, transport):
		"""
		Return the list of transport candidates from a transport stanza
		"""
		return []


import farsight

class JingleTransportICEUDP(JingleTransport):
	def __init__(self):
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

# vim: se ts=3: