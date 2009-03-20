##   auth_nb.py
##       based on auth.py, changes backported up to revision 1.41
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
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
'''
Provides plugs for SASL and NON-SASL authentication mechanisms.
Can be used both for client and transport authentication.

See client_nb.py
'''
from protocol import NS_SASL, NS_SESSION, NS_STREAMS, NS_BIND, NS_AUTH
from protocol import Node, NodeProcessed, isResultNode, Iq, Protocol, JID
from plugin import PlugIn
import base64
import random
import itertools
import dispatcher_nb
import hashlib

import logging
log = logging.getLogger('gajim.c.x.auth_nb')

def HH(some): return hashlib.md5(some).hexdigest()
def H(some): return hashlib.md5(some).digest()
def C(some): return ':'.join(some)

try:
	import kerberos
	have_kerberos = True
except ImportError:
	have_kerberos = False

GSS_STATE_STEP = 0
GSS_STATE_WRAP = 1
SASL_FAILURE = 'failure'
SASL_SUCCESS = 'success'
SASL_UNSUPPORTED = 'not-supported'
SASL_IN_PROCESS = 'in-process'

def challenge_splitter(data):
	''' Helper function that creates a dict from challenge string.

	Sample challenge string:
		username="example.org",realm="somerealm",\
		nonce="OA6MG9tEQGm2hh",cnonce="OA6MHXh6VqTrRk",\
		nc=00000001,qop="auth,auth-int,auth-conf",charset=utf-8

	Expected result for challan:
		dict['qop'] = ('auth','auth-int','auth-conf')
		dict['realm'] = 'somerealm'
	'''
	X_KEYWORD, X_VALUE, X_END = 0, 1, 2
	quotes_open = False
	keyword, value = '', ''
	dict_ = {}
	arr = None

	expecting = X_KEYWORD
	for iter_ in range(len(data) + 1):
		end = False
		if iter_ == len(data):
			expecting = X_END
			end = True
		else:
			char = data[iter_]
		if expecting == X_KEYWORD:
			if char == '=':
				expecting  = X_VALUE
			elif char in (',', ' ', '\t'):
				pass
			else:
				keyword = '%s%c' % (keyword, char)
		elif expecting == X_VALUE:
			if char == '"':
				if quotes_open:
					end = True
				else:
					quotes_open = True
			elif char in (',', ' ', '\t'):
				if quotes_open:
					if not arr:
						arr = [value]
					else:
						arr.append(value)
					value = ""
				else:
					end = True
			else:
				value = '%s%c' % (value, char)
		if end:
			if arr:
				arr.append(value)
				dict_[keyword] = arr
				arr = None
			else:
				dict_[keyword] = value
			value, keyword = '', ''
			expecting = X_KEYWORD
			quotes_open = False
	return dict_


class SASL(PlugIn):
	'''
	Implements SASL authentication. Can be plugged into NonBlockingClient
	to start authentication.
	'''
	def __init__(self, username, password, on_sasl):
		'''
		:param user: XMPP username
		:param password: XMPP password
		:param on_sasl: Callback, will be called after each SASL auth-step.
		'''
		PlugIn.__init__(self)
		self.username = username
		self.password = password
		self.on_sasl = on_sasl
		self.realm = None
	
	def plugin(self, owner):
		if 'version' not in self._owner.Dispatcher.Stream._document_attrs:
			self.startsasl = SASL_UNSUPPORTED
		elif self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher,
					self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self.startsasl = None

	def plugout(self):
		''' Remove SASL handlers from owner's dispatcher. Used internally. '''
		if 'features' in  self._owner.__dict__:
			self._owner.UnregisterHandler('features', self.FeaturesHandler,
				xmlns=NS_STREAMS)
		if 'challenge' in  self._owner.__dict__:
			self._owner.UnregisterHandler('challenge', self.SASLHandler,
				xmlns=NS_SASL)
		if 'failure' in  self._owner.__dict__:
			self._owner.UnregisterHandler('failure', self.SASLHandler,
				xmlns=NS_SASL)
		if 'success' in  self._owner.__dict__:
			self._owner.UnregisterHandler('success', self.SASLHandler,
				xmlns=NS_SASL)

	def auth(self):
		'''
		Start authentication. Result can be obtained via "SASL.startsasl"
		attribute and will be either SASL_SUCCESS or SASL_FAILURE.

		Note that successfull auth will take at least two Dispatcher.Process()
		calls.
		'''
		if self.startsasl:
			pass
		elif self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher,
					self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self._owner.RegisterHandler('features',
				self.FeaturesHandler, xmlns=NS_STREAMS)

	def FeaturesHandler(self, conn, feats):
		''' Used to determine if server supports SASL auth. Used internally. '''
		if not feats.getTag('mechanisms', namespace=NS_SASL):
			self.startsasl='not-supported'
			log.error('SASL not supported by server')
			return
		self.mecs = []
		for mec in feats.getTag('mechanisms', namespace=NS_SASL).getTags(
		'mechanism'):
			self.mecs.append(mec.getData())

		self._owner.RegisterHandler('challenge', self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler('failure', self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler('success', self.SASLHandler, xmlns=NS_SASL)
		self.MechanismHandler()

	def MechanismHandler(self):
		if 'ANONYMOUS' in self.mecs and self.username is None:
			self.mecs.remove('ANONYMOUS')
			node = Node('auth',attrs={'xmlns': NS_SASL, 'mechanism': 'ANONYMOUS'})
			self.mechanism = 'ANONYMOUS'
			self.startsasl = SASL_IN_PROCESS
			self._owner.send(str(node))
			raise NodeProcessed
		if 'GSSAPI' in self.mecs and have_kerberos:
			self.mecs.remove('GSSAPI')
			try:
				self.gss_vc = kerberos.authGSSClientInit('xmpp@' + \
					self._owner.xmpp_hostname)[1]
				kerberos.authGSSClientStep(self.gss_vc, '')
				response = kerberos.authGSSClientResponse(self.gss_vc)
				node=Node('auth',attrs={'xmlns': NS_SASL, 'mechanism': 'GSSAPI'},
					payload=(response or ''))
				self.mechanism = 'GSSAPI'
				self.gss_step = GSS_STATE_STEP
				self.startsasl = SASL_IN_PROCESS
				self._owner.send(str(node))
				raise NodeProcessed
			except kerberos.GSSError, e:
				log.info('GSSAPI authentication failed: %s' % str(e))
		if 'DIGEST-MD5' in self.mecs:
			self.mecs.remove('DIGEST-MD5')
			node = Node('auth',attrs={'xmlns': NS_SASL, 'mechanism': 'DIGEST-MD5'})
			self.mechanism = 'DIGEST-MD5'
			self.startsasl = SASL_IN_PROCESS
			self._owner.send(str(node))
			raise NodeProcessed
		if 'PLAIN' in self.mecs:
			self.mecs.remove('PLAIN')
			self.mechanism = 'PLAIN'
			self._owner._caller.get_password(self.set_password)
			self.startsasl = SASL_IN_PROCESS
			raise NodeProcessed
		self.startsasl = SASL_FAILURE
		log.error('I can only use DIGEST-MD5, GSSAPI and PLAIN mecanisms.')
		if self.on_sasl:
			self.on_sasl()
		return

	def SASLHandler(self, conn, challenge):
		''' Perform next SASL auth step. Used internally. '''
		if challenge.getNamespace() != NS_SASL:
			return
		### Handle Auth result
		if challenge.getName() == 'failure':
			self.startsasl = SASL_FAILURE
			try:
				reason = challenge.getChildren()[0]
			except Exception:
				reason = challenge
			log.error('Failed SASL authentification: %s' % reason)
			if len(self.mecs) > 0:
				# There are other mechanisms to test
				self.MechanismHandler()
				raise NodeProcessed
			if self.on_sasl:
				self.on_sasl()
			raise NodeProcessed
		elif challenge.getName() == 'success':
			self.startsasl = SASL_SUCCESS
			log.info('Successfully authenticated with remote server.')
			handlers = self._owner.Dispatcher.dumpHandlers()
	
			# Bosh specific dispatcher replugging
			# save old features. They will be used in case we won't get response on
			# stream restart after SASL auth (happens with XMPP over BOSH with
			# Openfire) 
			old_features = self._owner.Dispatcher.Stream.features
			self._owner.Dispatcher.PlugOut()
			dispatcher_nb.Dispatcher.get_instance().PlugIn(self._owner,
				after_SASL=True, old_features=old_features)
			self._owner.Dispatcher.restoreHandlers(handlers)
			self._owner.User = self.username

			if self.on_sasl:
				self.on_sasl()
			raise NodeProcessed

		### Perform auth step
		incoming_data = challenge.getData()
		data=base64.decodestring(incoming_data)
		log.info('Got challenge:' + data)

		if self.mechanism == 'GSSAPI':
			if self.gss_step == GSS_STATE_STEP:
				rc = kerberos.authGSSClientStep(self.gss_vc, incoming_data)
				if rc != kerberos.AUTH_GSS_CONTINUE:
					self.gss_step = GSS_STATE_WRAP
			elif self.gss_step == GSS_STATE_WRAP:
				rc = kerberos.authGSSClientUnwrap(self.gss_vc, incoming_data)
				response = kerberos.authGSSClientResponse(self.gss_vc)
				rc = kerberos.authGSSClientWrap(self.gss_vc, response,
					kerberos.authGSSClientUserName(self.gss_vc))
			response = kerberos.authGSSClientResponse(self.gss_vc)
			if not response:
				response = ''
			self._owner.send(Node('response', attrs={'xmlns':NS_SASL},
				payload=response).__str__())
			raise NodeProcessed
		
		# magic foo...
		chal = challenge_splitter(data)
		if not self.realm and 'realm' in chal:
			self.realm = chal['realm']
		if 'qop' in chal and ((isinstance(chal['qop'], str) and \
		chal['qop'] =='auth') or (isinstance(chal['qop'], list) and 'auth' in \
		chal['qop'])):
			self.resp = {}
			self.resp['username'] = self.username
			if self.realm:
				self.resp['realm'] = self.realm
			else:
				self.resp['realm'] = self._owner.Server
			self.resp['nonce'] = chal['nonce']
			self.resp['cnonce'] = ''.join("%x" % randint(0, 2**28) for randint in
				itertools.repeat(random.randint, 7))
			self.resp['nc'] = ('00000001')
			self.resp['qop'] = 'auth'
			self.resp['digest-uri'] = 'xmpp/' + self._owner.Server
			self.resp['charset'] = 'utf-8'
			# Password is now required
			self._owner._caller.get_password(self.set_password)
		elif 'rspauth' in chal:
			self._owner.send(str(Node('response', attrs={'xmlns':NS_SASL})))
		else:
			self.startsasl = SASL_FAILURE
			log.error('Failed SASL authentification: unknown challenge')
		if self.on_sasl:
			self.on_sasl()
		raise NodeProcessed
	
	def set_password(self, password):
		if password is None:
			self.password = ''
		else:
			self.password = password
		if self.mechanism == 'DIGEST-MD5':
			A1 = C([H(C([self.resp['username'], self.resp['realm'],
				self.password])), self.resp['nonce'], self.resp['cnonce']])
			A2 = C(['AUTHENTICATE', self.resp['digest-uri']])
			response= HH(C([HH(A1), self.resp['nonce'], self.resp['nc'],
				self.resp['cnonce'], self.resp['qop'], HH(A2)]))
			self.resp['response'] = response
			sasl_data = u''
			for key in ('charset', 'username', 'realm', 'nonce', 'nc', 'cnonce',
			'digest-uri', 'response', 'qop'):
				if key in ('nc','qop','response','charset'):
					sasl_data += u"%s=%s," % (key, self.resp[key])
				else:
					sasl_data += u'%s="%s",' % (key, self.resp[key])
			sasl_data = sasl_data[:-1].encode('utf-8').encode('base64').replace(
				'\r', '').replace('\n', '')
			node = Node('response', attrs={'xmlns':NS_SASL}, payload=[sasl_data])
		elif self.mechanism == 'PLAIN':
			sasl_data = u'%s\x00%s\x00%s' % (self.username + '@' + \
				self._owner.Server, self.username, self.password)
			sasl_data = sasl_data.encode('utf-8').encode('base64').replace(
				'\n', '')
			node = Node('auth', attrs={'xmlns': NS_SASL, 'mechanism': 'PLAIN'},
				payload=[sasl_data])
		self._owner.send(str(node))


class NonBlockingNonSASL(PlugIn):
	'''
	Implements old Non-SASL (JEP-0078) authentication used in jabberd1.4 and
	transport authentication.
	'''
	def __init__(self, user, password, resource, on_auth):
		''' Caches username, password and resource for auth. '''
		PlugIn.__init__(self)
		self.user = user
		if password is None:
			self.password = ''
		else:
			self.password = password
		self.resource = resource
		self.on_auth = on_auth

	def plugin(self, owner):
		'''
		Determine the best auth method (digest/0k/plain) and use it for auth.
		Returns used method name on success. Used internally.
		'''
		log.info('Querying server about possible auth methods')
		self.owner = owner

		owner.Dispatcher.SendAndWaitForResponse(
			Iq('get', NS_AUTH, payload=[Node('username', payload=[self.user])]),
			func=self._on_username)

	def _on_username(self, resp):
		if not isResultNode(resp):
			log.error('No result node arrived! Aborting...')
			return self.on_auth(None)

		iq=Iq(typ='set',node=resp)
		query = iq.getTag('query')
		query.setTagData('username',self.user)
		query.setTagData('resource',self.resource)

		if query.getTag('digest'):
			log.info("Performing digest authentication")
			query.setTagData('digest',
				hashlib.sha1(self.owner.Dispatcher.Stream._document_attrs['id']
				+ self.password).hexdigest())
			if query.getTag('password'):
				query.delChild('password')
			self._method = 'digest'
		elif query.getTag('token'):
			token = query.getTagData('token')
			seq = query.getTagData('sequence')
			log.info("Performing zero-k authentication")

			def hasher(s):
				return hashlib.sha1(s).hexdigest()

			def hash_n_times(s, count):
				return count and hasher(hash_n_times(s, count-1)) or s

			hash_ = hash_n_times(hasher(hasher(self.password) + token), int(seq))
			query.setTagData('hash', hash_)
			self._method='0k'
		else:
			log.warn("Sequre methods unsupported, performing plain text \
				authentication")
			query.setTagData('password', self.password)
			self._method = 'plain'
		resp = self.owner.Dispatcher.SendAndWaitForResponse(iq,func=self._on_auth)

	def _on_auth(self, resp):
		if isResultNode(resp):
			log.info('Sucessfully authenticated with remote host.')
			self.owner.User = self.user
			self.owner.Resource = self.resource
			self.owner._registered_name = self.owner.User+'@'+self.owner.Server+\
				'/'+self.owner.Resource
			return self.on_auth(self._method)
		log.error('Authentication failed!')
		return self.on_auth(None)


class NonBlockingBind(PlugIn):
	'''
	Bind some JID to the current connection to allow router know of our
	location. Must be plugged after successful SASL auth.
	'''
	def __init__(self):
		PlugIn.__init__(self)
		self.bound = None

	def plugin(self, owner):
		''' Start resource binding, if allowed at this time. Used internally. '''
		if self._owner.Dispatcher.Stream.features:
			try:
				self.FeaturesHandler(self._owner.Dispatcher, 
					self._owner.Dispatcher.Stream.features)
			except NodeProcessed:
				pass
		else:
			self._owner.RegisterHandler('features', self.FeaturesHandler,
				xmlns=NS_STREAMS)

	def FeaturesHandler(self, conn, feats):
		'''
		Determine if server supports resource binding and set some internal
		attributes accordingly.
		'''
		if not feats.getTag('bind', namespace=NS_BIND):
			log.error('Server does not requested binding.')
			# we try to bind resource anyway
			#self.bound='failure'
			self.bound = []
			return
		if feats.getTag('session', namespace=NS_SESSION):
			self.session = 1
		else:
			self.session = -1
		self.bound = []

	def plugout(self):
		''' Remove Bind handler from owner's dispatcher. Used internally. '''
		self._owner.UnregisterHandler('features', self.FeaturesHandler,
			xmlns=NS_STREAMS)

	def NonBlockingBind(self, resource=None, on_bound=None):
		''' Perform binding.
		Use provided resource name or random (if not provided).
		'''
		self.on_bound = on_bound
		self._resource = resource
		if self._resource:
			self._resource = [Node('resource', payload=[self._resource])]
		else:
			self._resource = []

		self._owner.onreceive(None)
		self._owner.Dispatcher.SendAndWaitForResponse(
			Protocol('iq',typ='set', payload=[Node('bind', attrs={'xmlns':NS_BIND},
			payload=self._resource)]), func=self._on_bound)

	def _on_bound(self, resp):
		if isResultNode(resp):
			if resp.getTag('bind') and resp.getTag('bind').getTagData('jid'):
				self.bound.append(resp.getTag('bind').getTagData('jid'))
				log.info('Successfully bound %s.' % self.bound[-1])
				jid = JID(resp.getTag('bind').getTagData('jid'))
				self._owner.User = jid.getNode()
				self._owner.Resource = jid.getResource()
				self._owner.SendAndWaitForResponse(Protocol('iq', typ='set',
					payload=[Node('session', attrs={'xmlns':NS_SESSION})]),
					func=self._on_session)
				return
		if resp:
			log.error('Binding failed: %s.' % resp.getTag('error'))
			self.on_bound(None)
		else:
			log.error('Binding failed: timeout expired.')
			self.on_bound(None)

	def _on_session(self, resp):
		self._owner.onreceive(None)
		if isResultNode(resp):
			log.info('Successfully opened session.')
			self.session = 1
			self.on_bound('ok')
		else:
			log.error('Session open failed.')
			self.session = 0
			self.on_bound(None)

# vim: se ts=3:
