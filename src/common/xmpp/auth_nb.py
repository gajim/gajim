##   auth_nb.py
##       based on auth.py
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
Provides library with all Non-SASL and SASL authentication mechanisms.
Can be used both for client and transport authentication.
'''
import sys
from protocol import *
from auth import *
from client import PlugIn
import sha,base64,random,dispatcher_nb

try:
	import kerberos
	have_kerberos = True
except ImportError:
	have_kerberos = False

GSS_STATE_STEP = 0
GSS_STATE_WRAP = 1

def challenge_splitter(data):
	''' Helper function that creates a dict from challenge string.
	Sample chalenge string:
		username="example.org",realm="somerealm",\
		nonce="OA6MG9tEQGm2hh",cnonce="OA6MHXh6VqTrRk",\
		nc=00000001,qop="auth,auth-int,auth-conf",charset=utf-8
	in the above example:
		dict['qop'] = ('auth','auth-int','auth-conf')
		dict['realm'] = 'somerealm'
	'''
	X_KEYWORD, X_VALUE, X_END = 0, 1, 2
	quotes_open = False
	keyword, value = '', ''
	dict, arr = {}, None
	
	expecting = X_KEYWORD
	for iter in range(len(data) + 1):
		end = False
		if iter == len(data):
			expecting = X_END
			end = True
		else:
			char = data[iter]
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
				dict[keyword] = arr
				arr = None
			else:
				dict[keyword] = value
			value, keyword = '', ''
			expecting = X_KEYWORD
			quotes_open = False
	return dict

class SASL(PlugIn):
	''' Implements SASL authentication. '''
	def __init__(self,username,password, on_sasl):
		PlugIn.__init__(self)
		self.username=username
		self.password=password or ''
		self.on_sasl = on_sasl
		self.realm = None
	def plugin(self,owner):
		if 'version' not in self._owner.Dispatcher.Stream._document_attrs: 
			self.startsasl='not-supported'
		elif self._owner.Dispatcher.Stream.features:
			try: 
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed: 
				pass
		else: self.startsasl=None

	def auth(self):
		''' Start authentication. Result can be obtained via "SASL.startsasl" attribute and will be
			either "success" or "failure". Note that successfull auth will take at least
			two Dispatcher.Process() calls. '''
		if self.startsasl: 
			pass
		elif self._owner.Dispatcher.Stream.features:
			try: 
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed: 
				pass
		else: self._owner.RegisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)

	def plugout(self):
		''' Remove SASL handlers from owner's dispatcher. Used internally. '''
		self._owner.UnregisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)
		self._owner.UnregisterHandler('challenge', self.SASLHandler, xmlns=NS_SASL)
		self._owner.UnregisterHandler('failure', self.SASLHandler, xmlns=NS_SASL)
		self._owner.UnregisterHandler('success', self.SASLHandler, xmlns=NS_SASL)

	def FeaturesHandler(self, conn, feats):
		''' Used to determine if server supports SASL auth. Used internally. '''
		if not feats.getTag('mechanisms', namespace=NS_SASL):
			self.startsasl='not-supported'
			self.DEBUG('SASL not supported by server', 'error')
			return
		self.mecs=[]
		for mec in feats.getTag('mechanisms', namespace=NS_SASL).getTags('mechanism'):
			self.mecs.append(mec.getData())
		self._owner.RegisterHandler('challenge', self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler('failure', self.SASLHandler, xmlns=NS_SASL)
		self._owner.RegisterHandler('success', self.SASLHandler, xmlns=NS_SASL)
		self.MechanismHandler()

	def MechanismHandler(self):
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
			except kerberos.GSSError, e:
				self.DEBUG('GSSAPI authentication failed: %s' % str(e), 'warn')
		elif 'DIGEST-MD5' in self.mecs:
			self.mecs.remove('DIGEST-MD5')
			node=Node('auth',attrs={'xmlns': NS_SASL, 'mechanism': 'DIGEST-MD5'})
			self.mechanism = 'DIGEST-MD5'
		elif 'PLAIN' in self.mecs:
			self.mecs.remove('PLAIN')
			sasl_data = u'%s\x00%s\x00%s' % (self.username + '@' + \
				self._owner.Server, self.username, self.password)
			sasl_data = sasl_data.encode('utf-8').encode('base64').replace(
				'\n','')
			node = Node('auth', attrs={'xmlns': NS_SASL, 'mechanism': 'PLAIN'}, 
				payload=[sasl_data])
			self.mechanism = 'PLAIN'
		else:
			self.startsasl='failure'
			self.DEBUG('I can only use DIGEST-MD5, GSSAPI and PLAIN mecanisms.', 'error')
			if self.on_sasl:
				self.on_sasl()
			return
		self.startsasl='in-process'
		self._owner.send(node.__str__())
		raise NodeProcessed

	def SASLHandler(self, conn, challenge):
		''' Perform next SASL auth step. Used internally. '''
		if challenge.getNamespace() != NS_SASL: 
			return
		if challenge.getName() == 'failure':
			self.startsasl = 'failure'
			try: 
				reason = challenge.getChildren()[0]
			except Exception: 
				reason = challenge
			self.DEBUG('Failed SASL authentification: %s' % reason, 'error')
			if len(self.mecs) > 0:
				# There are other mechanisms to test
				self.MechanismHandler()
				raise NodeProcessed
			if self.on_sasl :
				self.on_sasl ()
			raise NodeProcessed
		elif challenge.getName() == 'success':
			self.startsasl='success'
			self.DEBUG('Successfully authenticated with remote server.', 'ok')
			handlers=self._owner.Dispatcher.dumpHandlers()
			self._owner.Dispatcher.PlugOut()
			dispatcher_nb.Dispatcher().PlugIn(self._owner)
			self._owner.Dispatcher.restoreHandlers(handlers)
			self._owner.User = self.username
			if self.on_sasl :
				self.on_sasl ()
			raise NodeProcessed
########################################3333
		incoming_data = challenge.getData()
		data=base64.decodestring(incoming_data)
		self.DEBUG('Got challenge:'+data,'ok')
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
		chal = challenge_splitter(data)
		if not self.realm and 'realm' in chal:
			self.realm = chal['realm']
		if 'qop' in chal and ((isinstance(chal['qop'], str) and \
		chal['qop'] =='auth') or (isinstance(chal['qop'], list) and 'auth' in \
		chal['qop'])):
			resp={}
			resp['username'] = self.username
			if self.realm:
				resp['realm'] = self.realm
			else:
				resp['realm'] = self._owner.Server
			resp['nonce']=chal['nonce']
			cnonce=''
			for i in range(7):
				cnonce += hex(int(random.random() * 65536 * 4096))[2:]
			resp['cnonce'] = cnonce
			resp['nc'] = ('00000001')
			resp['qop'] = 'auth'
			resp['digest-uri'] = 'xmpp/'+self._owner.Server
			A1=C([H(C([resp['username'], resp['realm'], self.password])), 
						resp['nonce'], resp['cnonce']])
			A2=C(['AUTHENTICATE',resp['digest-uri']])
			response= HH(C([HH(A1), resp['nonce'], resp['nc'], resp['cnonce'],
						resp['qop'], HH(A2)]))
			resp['response'] = response
			resp['charset'] = 'utf-8'
			sasl_data = u''
			for key in ('charset', 'username', 'realm', 'nonce', 'nc', 'cnonce', 'digest-uri', 'response', 'qop'):
				if key in ['nc','qop','response','charset']: 
					sasl_data += u"%s=%s," % (key,resp[key])
				else: 
					sasl_data += u'%s="%s",' % (key,resp[key])
			sasl_data = sasl_data[:-1].encode('utf-8').encode('base64').replace(
				'\r','').replace('\n','')
			node = Node('response', attrs={'xmlns':NS_SASL}, payload=[sasl_data])
			self._owner.send(node.__str__())
		elif 'rspauth' in chal: 
			self._owner.send(Node('response', attrs={'xmlns':NS_SASL}).__str__())
		else: 
			self.startsasl='failure'
			self.DEBUG('Failed SASL authentification: unknown challenge', 'error')
		if self.on_sasl :
				self.on_sasl ()
		raise NodeProcessed
	
class NonBlockingNonSASL(PlugIn):
	''' Implements old Non-SASL (JEP-0078) authentication used 
	in jabberd1.4 and transport authentication.
	'''
	def __init__(self, user, password, resource, on_auth):
		''' Caches username, password and resource for auth. '''
		PlugIn.__init__(self)
		self.DBG_LINE ='gen_auth'
		self.user = user
		self.password= password or ''
		self.resource = resource
		self.on_auth = on_auth

	def plugin(self, owner):
		''' Determine the best auth method (digest/0k/plain) and use it for auth.
			Returns used method name on success. Used internally. '''
		if not self.resource: 
			return self.authComponent(owner)
		self.DEBUG('Querying server about possible auth methods', 'start')
		self.owner = owner 
		
		resp = owner.Dispatcher.SendAndWaitForResponse(
			Iq('get', NS_AUTH, payload=[Node('username', payload=[self.user])]), func=self._on_username
		)
		
	def _on_username(self, resp):
		if not isResultNode(resp):
			self.DEBUG('No result node arrived! Aborting...','error')
			return self.on_auth(None)
		iq=Iq(typ='set',node=resp)
		query=iq.getTag('query')
		query.setTagData('username',self.user)
		query.setTagData('resource',self.resource)

		if query.getTag('digest'):
			self.DEBUG("Performing digest authentication",'ok')
			query.setTagData('digest', 
				sha.new(self.owner.Dispatcher.Stream._document_attrs['id']+self.password).hexdigest())
			if query.getTag('password'): 
				query.delChild('password')
			self._method='digest'
		elif query.getTag('token'):
			token=query.getTagData('token')
			seq=query.getTagData('sequence')
			self.DEBUG("Performing zero-k authentication",'ok')
			hash = sha.new(sha.new(self.password).hexdigest()+token).hexdigest()
			for foo in xrange(int(seq)): 
				hash = sha.new(hash).hexdigest()
			query.setTagData('hash',hash)
			self._method='0k'
		else:
			self.DEBUG("Sequre methods unsupported, performing plain text authentication",'warn')
			query.setTagData('password',self.password)
			self._method='plain'
		resp=self.owner.Dispatcher.SendAndWaitForResponse(iq, func=self._on_auth)
		
	def _on_auth(self, resp):
		if isResultNode(resp):
			self.DEBUG('Sucessfully authenticated with remove host.','ok')
			self.owner.User=self.user
			self.owner.Resource=self.resource
			self.owner._registered_name=self.owner.User+'@'+self.owner.Server+'/'+self.owner.Resource
			return self.on_auth(self._method)
		self.DEBUG('Authentication failed!','error')
		return self.on_auth(None)

	def authComponent(self,owner):
		''' Authenticate component. Send handshake stanza and wait for result. Returns "ok" on success. '''
		self.handshake=0
		owner.send(Node(NS_COMPONENT_ACCEPT+' handshake',
			payload=[sha.new(owner.Dispatcher.Stream._document_attrs['id']+self.password).hexdigest()]))
		owner.RegisterHandler('handshake', self.handshakeHandler, xmlns=NS_COMPONENT_ACCEPT)
		self._owner.onreceive(self._on_auth_component)
		
	def _on_auth_component(self, data):
		''' called when we receive some response, after we send the handshake '''
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not self.handshake:
			self.DEBUG('waiting on handshake', 'notify')
			return
		self._owner.onreceive(None)
		owner._registered_name=self.user
		if self.handshake+1: 
			return self.on_auth('ok')
		self.on_auth(None)

	def handshakeHandler(self,disp,stanza):
		''' Handler for registering in dispatcher for accepting transport authentication. '''
		if stanza.getName() == 'handshake': 
			self.handshake=1
		else: 
			self.handshake=-1
	
class NonBlockingBind(Bind):
	''' Bind some JID to the current connection to allow router know of our location.'''
	def plugin(self, owner):
		''' Start resource binding, if allowed at this time. Used internally. '''
		if self._owner.Dispatcher.Stream.features:
			try: 
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed: 
				pass
		else: self._owner.RegisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)

	def plugout(self):
		''' Remove Bind handler from owner's dispatcher. Used internally. '''
		self._owner.UnregisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)

	def NonBlockingBind(self, resource=None, on_bound=None):
		''' Perform binding. Use provided resource name or random (if not provided). '''
		self.on_bound = on_bound
		self._resource = resource
		if self._resource: 
			self._resource = [Node('resource', payload=[self._resource])]
		else: 
			self._resource = []
			
		self._owner.onreceive(None)
		resp=self._owner.Dispatcher.SendAndWaitForResponse(
			Protocol('iq',typ='set',
				payload=[Node('bind', attrs={'xmlns':NS_BIND}, payload=self._resource)]), 
				func=self._on_bound)
	def _on_bound(self, resp):
		if isResultNode(resp):
			if resp.getTag('bind') and resp.getTag('bind').getTagData('jid'):
				self.bound.append(resp.getTag('bind').getTagData('jid'))
				self.DEBUG('Successfully bound %s.'%self.bound[-1],'ok')
				jid=JID(resp.getTag('bind').getTagData('jid'))
				self._owner.User=jid.getNode()
				self._owner.Resource=jid.getResource()
				self._owner.SendAndWaitForResponse(Protocol('iq', typ='set', 
					payload=[Node('session', attrs={'xmlns':NS_SESSION})]),
					func=self._on_session)
				return
		if resp:
			self.DEBUG('Binding failed: %s.' % resp.getTag('error'),'error')
			self.on_bound(None)
		else:
			self.DEBUG('Binding failed: timeout expired.', 'error')
			self.on_bound(None)
			
	def _on_session(self, resp):
		self._owner.onreceive(None)
		if isResultNode(resp):
			self.DEBUG('Successfully opened session.', 'ok')
			self.session = 1
			self.on_bound('ok')
		else:
			self.DEBUG('Session open failed.', 'error')
			self.session = 0
			self.on_bound(None)
		self._owner.onreceive(None)
		if isResultNode(resp):
			self.DEBUG('Successfully opened session.', 'ok')
			self.session = 1
			self.on_bound('ok')
		else:
			self.DEBUG('Session open failed.', 'error')
			self.session = 0
			self.on_bound(None)

class NBComponentBind(ComponentBind):
	''' ComponentBind some JID to the current connection to allow 
	router know of our location.
	'''
	def plugin(self,owner):
		''' Start resource binding, if allowed at this time. Used internally. '''
		if self._owner.Dispatcher.Stream.features:
			try: 
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed: 
				pass
		else:
			self._owner.RegisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)
			self.needsUnregister = 1

	def plugout(self):
		''' Remove ComponentBind handler from owner's dispatcher. Used internally. '''
		if self.needsUnregister:
			self._owner.UnregisterHandler('features', self.FeaturesHandler, xmlns=NS_STREAMS)
	
	def Bind(self, domain = None, on_bind = None):
		''' Perform binding. Use provided domain name (if not provided). '''
		self._owner.onreceive(self._on_bound)
		self.on_bind = on_bind
	
	def _on_bound(self, resp):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if self.bound is None:
			return
		self._owner.onreceive(None)
		self._owner.SendAndWaitForResponse(
			Protocol('bind', attrs={'name':domain}, xmlns=NS_COMPONENT_1), 
			func=self._on_bind_reponse)
	
	def _on_bind_reponse(self, res):
		if resp and resp.getAttr('error'):
			self.DEBUG('Binding failed: %s.' % resp.getAttr('error'), 'error')
		elif resp:
			self.DEBUG('Successfully bound.', 'ok')
			if self.on_bind:
				self.on_bind('ok')
		else:
			self.DEBUG('Binding failed: timeout expired.', 'error')
		if self.on_bind:
			self.on_bind(None)

# vim: se ts=3:
