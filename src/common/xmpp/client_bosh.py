##   client_bosh.py
##
##   Copyright (C) 2008 Tomas Karasek <tom.to.the.k@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

import locale, random
import protocol
import simplexml
import debug
import dispatcher_nb
from client_nb import NBCommonClient

DBG_BOSHCLIENT='boshclient'

class BOSHClient(NBCommonClient):
	'''
	BOSH (XMPP over HTTP) client implementation. It should provide the same
	methods and functionality as NonBlockingClient.
	'''


	def __init__(self, server, bosh_conn_mgr, port=5222, bosh_port=5280,
	on_connect=None, on_connect_failure=None, on_proxy_failure=None, caller=None):
		'''
		Class constuctor has the same parameters as NBCommonClient plus bosh_conn_mgr
		and bosh_port - Connection manager address and port. bosh_conn_mgr should be
		in form: 'http://httpcm.jabber.org/http-bind/'
		Tcp connection will be opened to bosh_conn_mgr:bosh_port instead of 
		server:port.
		'''
		self.bosh_protocol, self.bosh_host, self.bosh_uri = self.urisplit(bosh_conn_mgr)
		if self.bosh_protocol is None:
			self.bosh_protocol = 'http'

		self.bosh_port = bosh_port

		if self.bosh_uri == '':
			bosh_uri = '/'

		self.xmpp_server = server
		self.xmpp_port = port

		self.bosh_hold = 1
		self.bosh_wait=60
		self.bosh_rid=-1
		self.bosh_httpversion = 'HTTP/1.1'

		NBCommonClient.__init__(self, self.bosh_host, self.bosh_port, caller=caller,
			on_connect=on_connect, on_connect_failure=on_connect_failure,
			on_proxy_failure=on_proxy_failure)
		
		# Namespace and DBG are detected in NBCommonClient constructor
		# with isinstance(). Since BOSHClient is descendant of NBCommonClient
		# and client_bosh.py is NOT imported in client_nb.py, NB_COMPONENT_ACCEPT
		# is put to namespace. This is not very nice, thus:
		# TODO: refactor Namespace and DBG recognition in NBCommonClient or
		# derived classes  
		self.Namespace, self.DBG = protocol.NS_HTTP_BIND, DBG_BOSHCLIENT
		# pop of DBG_COMPONENT
		self.debug_flags.pop()
		self.debug_flags.append(self.DBG)
		self.debug_flags.append(simplexml.DBG_NODEBUILDER)


	def urisplit(self, uri):
		'''
		Function for splitting URI string to tuple (protocol, host, path).
		e.g. urisplit('http://httpcm.jabber.org/webclient') returns
		('http', 'httpcm.jabber.org', '/webclient')
		'''
		import re
		regex = '(([^:/]+)(://))?([^/]*)(/?.*)'
		grouped = re.match(regex, uri).groups()
		proto, host, path = grouped[1], grouped[3], grouped[4]
		return proto, host, path

	
	def _on_connected(self):
		'''
		method called after socket starts connecting from NonBlockingTcp._do_connect
		'''
		self.onreceive(self.on_bosh_session_init_response)
		dispatcher_nb.Dispatcher().PlugIn(self)


	def parse_http_message(self, message):
		'''
		splits http message to tuple (
		  statusline - list of e.g. ['HTTP/1.1', '200', 'OK'],
		  headers - dictionary of headers e.g. {'Content-Length': '604',
		            'Content-Type': 'text/xml; charset=utf-8'},
		  httpbody - string with http body
		)  
		'''
		message = message.replace('\r','')
		(header, httpbody) = message.split('\n\n')
		header = header.split('\n')
		statusline = header[0].split(' ')
		header = header[1:]
		headers = {}
		for dummy in header:
			row = dummy.split(' ',1)
			headers[row[0][:-1]] = row[1]
		return (statusline, headers, httpbody)


	def on_bosh_session_init_response(self, data):
		'''
		Called on init response - should check relevant attributes from body tag
		'''
		if data:
			statusline, headers, httpbody = self.parse_http_message(data)

			if statusline[1] != '200':
				self.DEBUG(self.DBG, "HTTP Error in received session init response: %s" 
					% statusline, 'error')
				# error handling TBD!

			# ATM, whole <body> tag is pass to ProcessNonBocking.
			# Question is how to peel off the body tag from incoming stanzas and make
			# use of ordinar xmpp traffic handling.
			self.Dispatcher.ProcessNonBlocking(httpbody)


	def _check_stream_start(self, ns, tag, attrs):
		'''
		callback stub called from XML Parser when <stream..> is discovered
		'''
		self.DEBUG(self.DBG, 'CHECK_STREAM_START: ns: %s, tag: %s, attrs: %s'
			% (ns, tag, attrs), 'info')


	def StreamInit(self):
		'''
		Initiation of BOSH session. Called instead of Dispatcher.StreamInit()
		Initial body tag is created and sent to Conn Manager.
		'''
		self.Dispatcher.Stream = simplexml.NodeBuilder()
		self.Dispatcher.Stream._dispatch_depth = 2
		self.Dispatcher.Stream.dispatch = self.Dispatcher.dispatch
		self.Dispatcher.Stream.stream_header_received = self._check_stream_start
		self.debug_flags.append(simplexml.DBG_NODEBUILDER)
		self.Dispatcher.Stream.DEBUG = self.DEBUG
		self.Dispatcher.Stream.features = None

		initial_body_tag = simplexml.Node('body')
		initial_body_tag.setNamespace(self.Namespace)
		initial_body_tag.setAttr('content', 'text/xml; charset=utf-8')
		initial_body_tag.setAttr('hold', str(self.bosh_hold))
		initial_body_tag.setAttr('to', self.xmpp_server)
		initial_body_tag.setAttr('wait', str(self.bosh_wait))

		r = random.Random()
		r.seed()
		# with 50-bit random initial rid, session would have to go up
		# to 7881299347898368 messages to raise rid over 2**53 
		# (see http://www.xmpp.org/extensions/xep-0124.html#rids)
		self.bosh_rid = r.getrandbits(50)
		initial_body_tag.setAttr('rid', str(self.bosh_rid))

		if locale.getdefaultlocale()[0]:
			initial_body_tag.setAttr('xml:lang',
				locale.getdefaultlocale()[0].split('_')[0])
		initial_body_tag.setAttr('xmpp:version', '1.0')
		initial_body_tag.setAttr('xmlns:xmpp', 'urn:xmpp:xbosh')

		self.send(self.build_bosh_message(initial_body_tag))


	def build_bosh_message(self, httpbody):
		'''
		Builds bosh http message with given body.
		Values for headers and status line fields are taken from class variables.
		)  
		'''
		headers = ['POST %s HTTP/1.1' % self.bosh_uri,
			'Host: %s' % self.bosh_host,
			'Content-Type: text/xml; charset=utf-8',
			'Content-Length: %s' % len(str(httpbody)),
			'\r\n']
		headers = '\r\n'.join(headers)
		return('%s%s\r\n' % (headers, httpbody))



