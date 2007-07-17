from common import gajim

from common import xmpp
from common import helpers
from common import exceptions

import random
import string

import math
import os
import time

from common import dh
import xmpp.c14n

from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256

import base64

class StanzaSession(object):
	def __init__(self, conn, jid, thread_id, type):
		self.conn = conn

		self.jid = jid

		self.type = type

		if thread_id:
			self.received_thread_id = True
			self.thread_id = thread_id
		else:
			self.received_thread_id = False
			if type == 'normal':
				self.thread_id = None
			else:
				self.thread_id = self.generate_thread_id()

		self.last_send = 0
		self.status = None
		self.negotiated = {}
	
	def generate_thread_id(self):
		return "".join([random.choice(string.letters) for x in xrange(0,32)])

	def send(self, msg):
		if self.thread_id and isinstance(msg, xmpp.Message):
			msg.setThread(self.thread_id)

		msg.setAttr('to', self.jid)
		self.conn.send_stanza(msg)
	
		if isinstance(msg, xmpp.Message):
			self.last_send = time.time()

	def reject_negotiation(self, body = None):
		msg = xmpp.Message()
		feature = msg.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')
		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='accept', value='0'))

		feature.addChild(node=x)

		if body:
			msg.setBody(body)

		self.send(msg)

		self.cancelled_negotiation()

	def cancelled_negotiation(self):
		'''A negotiation has been cancelled, so reset this session to its default state.'''
		self.status = None
		self.negotiated = {}

	def terminate(self):
		msg = xmpp.Message()
		feature = msg.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')
		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='terminate', value='1'))

		feature.addChild(node=x)

		self.send(msg)

		self.status = None

	def acknowledge_termination(self):
		# we could send an acknowledgement message here, but we won't.
		self.status = None

# an encrypted stanza negotiation has several states. i've represented them as the following values in the 'status' 
# attribute of the session object:

# 1. None:
#				default state
# 2. 'requested-e2e':
#				this client has initiated an esession negotiation and is waiting for
#				a response
# 3. 'responded-e2e':
#				this client has responded to an esession negotiation request and is
#				waiting for the initiator to identify itself and complete the
#				negotiation
# 4. 'identified-alice':
#				this client identified itself and is waiting for the responder to 
#				identify itself and complete the negotiation
# 5. 'active':
#				an encrypted session has been successfully negotiated. messages of
#				any of the types listed in 'encryptable_stanzas' should be encrypted
# 			before they're sent.

# the transition between these states is handled in gajim.py's
#	handle_session_negotiation method.

class EncryptedStanzaSession(StanzaSession):
	def __init__(self, conn, jid, thread_id, type = 'chat'):
		StanzaSession.__init__(self, conn, jid, thread_id, type = 'chat')

		self.loggable = True

		self.xes = {}
		self.es = {}

		self.n = 128

		self.enable_encryption = False

		# _s denotes 'self' (ie. this client)
		self._kc_s = None
	
		# _o denotes 'other' (ie. the client at the other end of the session)
		self._kc_o = None

	# keep the encrypter updated with my latest cipher key
	def set_kc_s(self, value):
		self._kc_s = value
		self.encrypter = self.cipher.new(self._kc_s, self.cipher.MODE_CTR, counter=self.encryptcounter)

	def get_kc_s(self):
		return self._kc_s

	# keep the decrypter updated with the other party's latest cipher key
	def set_kc_o(self, value):
		self._kc_o = value
		self.decrypter = self.cipher.new(self._kc_o, self.cipher.MODE_CTR, counter=self.decryptcounter)
	
	def get_kc_o(self):
		return self._kc_o

	kc_s = property(get_kc_s, set_kc_s)
	kc_o = property(get_kc_o, set_kc_o)
	
	# convert a large integer to a big-endian bitstring
	def encode_mpi(self, n):
		if n >= 256:
			return self.encode_mpi(n / 256) + chr(n % 256)
		else:
			return chr(n)

	# convert a large integer to a big-endian bitstring, padded with \x00s to 16 bytes
	def encode_mpi_with_padding(self, n):
		ret = self.encode_mpi(n)

		mod = len(ret) % 16
		if mod != 0:
			ret = ((16 - mod) * '\x00') + ret

		return ret

	# convert a big-endian bitstring to an integer
	def decode_mpi(self, s):
		if len(s) == 0:
			return 0
		else:
			return 256 * self.decode_mpi(s[:-1]) + ord(s[-1])

	def encryptcounter(self):
		self.c_s = (self.c_s + 1) % (2 ** self.n)
		return self.encode_mpi_with_padding(self.c_s)
	
	def decryptcounter(self):
		self.c_o = (self.c_o + 1) % (2 ** self.n)
		return self.encode_mpi_with_padding(self.c_o)

	def encrypt_stanza(self, stanza):
		encryptable = filter(lambda x: x.getName() not in ('error', 'amp', 'thread'), stanza.getChildren())

		# XXX can also encrypt contents of <error/> elements in stanzas @type = 'error'
		# (except for <defined-condition xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/> child elements)

		old_en_counter = self.c_s

		for element in encryptable:
			stanza.delChild(element)

		plaintext = ''.join(map(str, encryptable))

		m_compressed = self.compress(plaintext)
		m_final = self.encrypt(m_compressed)

		c = stanza.NT.c
		c.setNamespace('http://www.xmpp.org/extensions/xep-0200.html#ns')
		c.NT.data = base64.b64encode(m_final)

		# XXX check for rekey request, handle <key/> elements

		m_content = ''.join(map(str, c.getChildren()))
		c.NT.mac = base64.b64encode(self.hmac(self.km_s, m_content + self.encode_mpi(old_en_counter)))

		return stanza

	def hmac(self, key, content):
		return HMAC.new(key, content, self.hash_alg).digest()

	def sha256(self, string):
		sh = SHA256.new()
		sh.update(string)
		return sh.digest()
	
	base28_chr = "acdefghikmopqruvwxy123456789"

	def sas_28x5(self, m_a, form_b):
		sha = self.sha256(m_a + form_b + 'Short Authentication String')
		lsb24 = self.decode_mpi(sha[-3:])
		return self.base28(lsb24)

	def base28(self, n):
		if n >= 28:
			return self.base28(n / 28) + self.base28_chr[n % 28]
		else:
			return self.base28_chr[n]

	def generate_initiator_keys(self, k):
		return (self.hmac(k, 'Initiator Cipher Key'),
						self.hmac(k, 'Initiator MAC Key'),
						self.hmac(k, 'Initiator SIGMA Key')		 )

	def generate_responder_keys(self, k):
		return (self.hmac(k, 'Responder Cipher Key'),
						self.hmac(k, 'Responder MAC Key'),
						self.hmac(k, 'Responder SIGMA Key')		)

	def compress(self, plaintext):
		if self.compression == None:
			return plaintext

	def decompress(self, compressed):
		if self.compression == None:
			return compressed 

	def encrypt(self, encryptable):
		len_padding = 16 - (len(encryptable) % 16)
		if len_padding != 16:
			encryptable += len_padding * ' '

		return self.encrypter.encrypt(encryptable)

	# FIXME: use a real PRNG
	def random_bytes(self, bytes):
		return os.urandom(bytes)

	def generate_nonce(self):
		return self.random_bytes(8)

	def decrypt_stanza(self, stanza):
		c = stanza.getTag(name='c', namespace='http://www.xmpp.org/extensions/xep-0200.html#ns')

		stanza.delChild(c)

		# contents of <c>, minus <mac>, minus whitespace
		macable = ''.join(map(str, filter(lambda x: x.getName() != 'mac', c.getChildren())))

		received_mac = base64.b64decode(c.getTagData('mac'))
		calculated_mac = self.hmac(self.km_o, macable + self.encode_mpi_with_padding(self.c_o))

		if not calculated_mac == received_mac:
			raise 'bad signature (%s != %s)' % (repr(received_mac), repr(calculated_mac))

		m_final = base64.b64decode(c.getTagData('data'))
		m_compressed = self.decrypt(m_final)
		plaintext = self.decompress(m_compressed)

		try:
			parsed = xmpp.Node(node='<node>' + plaintext + '</node>')
		except:
			raise exceptions.DecryptionError

		for child in parsed.getChildren():
			stanza.addChild(node=child)

		return stanza

	def decrypt(self, ciphertext):
		return self.decrypter.decrypt(ciphertext)

	def logging_preference(self):
		if gajim.config.get('log_encrypted_sessions'):
			return ["may", "mustnot"]
		else:
			return ["mustnot", "may"]

	def negotiate_e2e(self):
		self.negotiated = {}

		request = xmpp.Message()
		feature = request.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='form')

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='accept', value='1', typ='boolean', required=True))

		# this field is incorrectly called 'otr' in XEPs 0116 and 0217
		x.addChild(node=xmpp.DataField(name='logging', typ='list-single', options=self.logging_preference(), required=True))

		# unsupported options: 'disabled', 'enabled'
		x.addChild(node=xmpp.DataField(name='disclosure', typ='list-single', options=['never'], required=True))
		x.addChild(node=xmpp.DataField(name='security', typ='list-single', options=['e2e'], required=True))
		x.addChild(node=xmpp.DataField(name='crypt_algs', value='aes128-ctr', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='hash_algs', value='sha256', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='compress', value='none', typ='hidden'))

		# unsupported options: 'iq', 'presence'
		x.addChild(node=xmpp.DataField(name='stanzas', typ='list-multi', options=['message']))

		x.addChild(node=xmpp.DataField(name='init_pubkey', value='none', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='resp_pubkey', value='none', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='ver', value='1.0', typ='hidden'))

		x.addChild(node=xmpp.DataField(name='rekey_freq', value='4294967295', typ='hidden'))

		x.addChild(node=xmpp.DataField(name='sas_algs', value='sas28x5', typ='hidden'))

		self.n_s = self.generate_nonce()
	
		x.addChild(node=xmpp.DataField(name='my_nonce', value=base64.b64encode(self.n_s), typ='hidden'))

		modp_options = [ 5, 14, 2, 1 ]

		x.addChild(node=xmpp.DataField(name='modp', typ='list-single', options=map(lambda x: [ None, x ], modp_options)))

		dhhashes = map(lambda x: self.make_dhhash(x), modp_options)
		x.addChild(node=xmpp.DataField(name='dhhashes', typ='hidden', value=dhhashes))

		self.form_a = ''.join(map(lambda el: xmpp.c14n.c14n(el), x.getChildren()))

		feature.addChild(node=x)

		self.status = 'requested-e2e'

		self.send(request)
	
	# 4.3 esession response (bob)
	def verify_options_bob(self, form):
		negotiated = {}
		not_acceptable = []
		ask_user = {}

		fixed = { 'disclosure': 'never',
								'security': 'e2e',
							'crypt_algs': 'aes128-ctr',
							'hash_algs': 'sha256',
								'compress': 'none',
								'stanzas': 'message',
						'init_pubkey': 'none',
						'resp_pubkey': 'none',
										'ver': '1.0',
								'sas_algs': 'sas28x5' }

		self.encryptable_stanzas = ['message']

		self.sas_algs = 'sas28x5'
		self.cipher = AES
		self.hash_alg = SHA256
		self.compression = None

		for name, field in map(lambda name: (name, form.getField(name)), form.asDict().keys()):
			options = map(lambda x: x[1], field.getOptions())
			values = field.getValues()

			if not field.getType() in ('list-single', 'list-multi'):
				options = values

			if name in fixed:
				if fixed[name] in options:
					negotiated[name] = fixed[name]
				else:
					not_acceptable.append(name)
			elif name == 'rekey_freq':
				preferred = int(options[0])
				negotiated['rekey_freq'] = preferred
				self.rekey_freq = preferred
			elif name == 'logging':
				my_prefs = self.logging_preference()

				if my_prefs[0] in options:
					pref = my_prefs[0]
					negotiated['logging'] = pref
				else:
					for pref in my_prefs:
						if pref in options:
							ask_user['logging'] = pref
							break

					if not 'logging' in ask_user:
						not_acceptable.append(name)
			else:
				# some things are handled elsewhere, some things are not-implemented
				pass

		return (negotiated, not_acceptable, ask_user)

	# 4.3 esession response (bob)
	def respond_e2e_bob(self, form, negotiated, not_acceptable):
		response = xmpp.Message()
		feature = response.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='accept', value='true'))

		for name in negotiated:
			x.addChild(node=xmpp.DataField(name=name, value=negotiated[name]))

		self.negotiated = negotiated

		# the offset of the group we chose (need it to match up with the dhhash)
		group_order = 0
		self.modp = int(form.getField('modp').getOptions()[group_order][1])
		x.addChild(node=xmpp.DataField(name='modp', value=self.modp))

		g = dh.generators[self.modp]
		p = dh.primes[self.modp]

		self.n_o = base64.b64decode(form['my_nonce'])

		dhhashes = form.getField('dhhashes').getValues()
		self.He = base64.b64decode(dhhashes[group_order].encode("utf8"))

		bytes = int(self.n / 8)

		self.n_s = self.generate_nonce()

		self.c_o = self.decode_mpi(self.random_bytes(bytes)) # n-bit random number
		self.c_s = self.c_o ^ (2 ** (self.n - 1))

		self.y = self.srand(2 ** (2 * self.n - 1), p - 1)
		self.d = self.powmod(g, self.y, p)

		to_add = { 'my_nonce': self.n_s,
							 'dhkeys': self.encode_mpi(self.d), 
							 'counter': self.encode_mpi(self.c_o), 
							 'nonce': self.n_o }

		for name in to_add:
			b64ed = base64.b64encode(to_add[name])
			x.addChild(node=xmpp.DataField(name=name, value=b64ed))

		self.form_a = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))
		self.form_b = ''.join(map(lambda el: xmpp.c14n.c14n(el), x.getChildren()))

		self.status = 'responded-e2e'

		feature.addChild(node=x)
		
		if not_acceptable:
			pass
# XXX
#  <error code='406' type='modify'>
#    <not-acceptable xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
#    <feature xmlns='http://jabber.org/protocol/feature-neg'>
#      <field var='security'/>
#    </feature>
#  </error>

		self.send(response)

	# 'Alice Accepts'
	def verify_options_alice(self, form):
#		1.	Verify that the ESession options selected by Bob are acceptable

		negotiated = {}
		ask_user = {}
		not_acceptable = []

		if not form['logging'] in self.logging_preference():
			not_acceptable.append(form['logging'])
		elif form['logging'] != self.logging_preference()[0]:
			ask_user['logging'] = form['logging']
		else:
			negotiated['logging'] = self.logging_preference()[0]

		return (negotiated, not_acceptable, ask_user)

	# 'Alice Accepts', continued
	def accept_e2e_alice(self, form, negotiated):
		self.encryptable_stanzas = ['message']
		self.sas_algs = 'sas28x5'
		self.cipher = AES
		self.hash_alg = SHA256
		self.compression = None

		self.negotiated = negotiated

#		2.	Return a <not-acceptable/> error to Bob unless: 1 < d < p - 1
		self.form_b = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))

		accept = xmpp.Message()
		feature = accept.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		result = xmpp.DataForm(typ='result')

		self.c_s = self.decode_mpi(base64.b64decode(form['counter']))
		self.c_o = self.c_s ^ (2 ** (self.n - 1))

		self.n_o = base64.b64decode(form['my_nonce'])

		mod_p = int(form['modp'])
		p = dh.primes[mod_p]
		x = self.xes[mod_p]
		e = self.es[mod_p]

		self.d = self.decode_mpi(base64.b64decode(form['dhkeys']))

		self.k = self.sha256(self.encode_mpi(self.powmod(self.d, x, p)))

		result.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		result.addChild(node=xmpp.DataField(name='accept', value='1'))
		result.addChild(node=xmpp.DataField(name='nonce', value=base64.b64encode(self.n_o)))
		result.addChild(node=xmpp.DataField(name='dhkeys', value=base64.b64encode(self.encode_mpi(e))))

		secrets = gajim.interface.list_secrets(self.conn.name, self.jid.getStripped()) 
		rshashes = [self.hmac(self.n_s, rs) for rs in secrets]

		# XXX add some random fake rshashes here

		rshashes.sort()

		rshashes = [base64.b64encode(rshash) for rshash in rshashes]
		result.addChild(node=xmpp.DataField(name='rshashes', value=rshashes))

		form_a2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), result.getChildren()))

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(self.k)
		
		# MUST securely destroy K unless it will be used later to generate the final shared secret

		old_c_s = self.c_s

		mac_a = self.hmac(self.ks_s, self.n_o + self.n_s + self.encode_mpi(e) + self.form_a + form_a2)
		id_a = self.encrypt(mac_a)

		m_a = self.hmac(self.km_s, self.encode_mpi(old_c_s) + id_a)

		# check for a retained secret
		# if none exists, prompt the user with the SAS
		if self.sas_algs == 'sas28x5':
			self.sas = self.sas_28x5(m_a, self.form_b)
			
		result.addChild(node=xmpp.DataField(name='identity', value=base64.b64encode(id_a)))
		result.addChild(node=xmpp.DataField(name='mac', value=base64.b64encode(m_a)))

		feature.addChild(node=result)
		self.send(accept)
		
		self.status = 'identified-alice'
	
	# 4.5 esession accept (bob)
	def accept_e2e_bob(self, form):
		response = xmpp.Message()

		init = response.NT.init
		init.setNamespace('http://www.xmpp.org/extensions/xep-0116.html#ns-init')

		x = xmpp.DataForm(typ='result')

		for field in ('nonce', 'dhkeys', 'rshashes', 'identity', 'mac'):
			assert field in form.asDict(), "alice's form didn't have a %s field" % field

		# 4.5.1 generating provisory session keys
		e = self.decode_mpi(base64.b64decode(form['dhkeys']))
		p = dh.primes[self.modp]

		if (self.sha256(self.encode_mpi(e)) != self.He) or (not 1 < e < (p - 1)):
			raise exceptions.NegotiationError, "invalid DH value 'e'"

		k = self.sha256(self.encode_mpi(self.powmod(e, self.y, p)))

		self.kc_o, self.km_o, self.ks_o = self.generate_initiator_keys(k)

		# 4.5.2 verifying alice's identity
		id_a = base64.b64decode(form['identity'])
		m_a = base64.b64decode(form['mac'])

		m_a_calculated = self.hmac(self.km_o, self.encode_mpi(self.c_o) + id_a)

		if m_a_calculated != m_a:
			raise exceptions.NegotiationError, 'calculated m_a differs from received m_a'

		mac_a = self.decrypt(id_a)

		macable_children = filter(lambda x: x.getVar() not in ('mac', 'identity'), form.getChildren())
		form_a2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), macable_children))

		mac_a_calculated = self.hmac(self.ks_o, self.n_s + self.n_o + self.encode_mpi(e) + self.form_a + form_a2)

		if mac_a_calculated != mac_a:
			raise exceptions.NegotiationError, 'calculated mac_a differs from received mac_a'

		# 4.5.4 generating bob's final session keys

		srs = ''
	
		secrets = gajim.interface.list_secrets(self.conn.name, self.jid.getStripped())
		rshashes = [base64.b64decode(rshash) for rshash in form.getField('rshashes').getValues()]

		for secret in secrets:
			if self.hmac(self.n_o, secret) in rshashes:
				srs = secret
				break

		# other shared secret, we haven't got one.
		oss = ''

		# check for a retained secret
		# if none exists, prompt the user with the SAS
		if self.sas_algs == 'sas28x5':
			self.sas = self.sas_28x5(m_a, self.form_b)
		
		k = self.sha256(k + srs + oss)

		# XXX I can skip generating ks_o here
		self.kc_s, self.km_s, self.ks_s = self.generate_responder_keys(k)
		self.kc_o, self.km_o, self.ks_o = self.generate_initiator_keys(k)

		# 4.5.5
		if srs:
			srshash = self.hmac(srs, 'Shared Retained Secret')
		else:
			srshash = self.random_bytes(32)

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField(name='nonce', value=base64.b64encode(self.n_o)))
		x.addChild(node=xmpp.DataField(name='srshash', value=base64.b64encode(srshash)))

		form_b2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), x.getChildren()))

		old_c_s = self.c_s

		mac_b = self.hmac(self.ks_s, self.n_o + self.n_s + self.encode_mpi(self.d) + self.form_b + form_b2)
		id_b = self.encrypt(mac_b)

		m_b = self.hmac(self.km_s, self.encode_mpi(old_c_s) + id_b)

		x.addChild(node=xmpp.DataField(name='identity', value=base64.b64encode(id_b)))
		x.addChild(node=xmpp.DataField(name='mac', value=base64.b64encode(m_b)))

		init.addChild(node=x)

		self.send(response)

		self.do_retained_secret(k, srs)

		if self.negotiated['logging'] == 'mustnot':
			self.loggable = False

		self.status = 'active'
		self.enable_encryption = True

	def final_steps_alice(self, form):
		srs = ''
		secrets = gajim.interface.list_secrets(self.conn.name, self.jid.getStripped())

		srshash = base64.b64decode(form['srshash'])

		for secret in secrets:
			if self.hmac(secret, 'Shared Retained Secret') == srshash:
				srs = secret
				break

		oss = ''
		k = self.sha256(self.k + srs + oss)
		del self.k

		self.do_retained_secret(k, srs)

		# don't need to calculate ks_s here

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(k)
		self.kc_o, self.km_o, self.ks_o = self.generate_responder_keys(k)

		# 4.6.2 Verifying Bob's Identity

		m_b = base64.b64decode(form['mac'])
		id_b = base64.b64decode(form['identity'])

		m_b_calculated = self.hmac(self.km_o, self.encode_mpi(self.c_o) + id_b)

		if m_b_calculated != m_b:
			raise exceptions.NegotiationError, 'calculated m_b differs from received m_b'

		mac_b = self.decrypt(id_b)

		macable_children = filter(lambda x: x.getVar() not in ('mac', 'identity'), form.getChildren())
		form_b2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), macable_children))

		mac_b_calculated = self.hmac(self.ks_o, self.n_s + self.n_o + self.encode_mpi(self.d) + self.form_b + form_b2)

		if mac_b_calculated != mac_b:
			raise exceptions.NegotiationError, 'calculated mac_b differs from received mac_b'

# Note: If Alice discovers an error then she SHOULD ignore any encrypted content she received in the stanza.
	
		if self.negotiated['logging'] == 'mustnot':
			self.loggable = False

		self.status = 'active'
		self.enable_encryption = True

	# calculate and store the new retained secret
	# prompt the user to check the remote party's identity (if necessary)
	def do_retained_secret(self, k, srs):
		new_srs = self.hmac(k, 'New Retained Secret')
		account = self.conn.name
		bjid = self.jid.getStripped()

		if srs:
			gajim.interface.replace_secret(account, bjid, srs, new_srs)
		else:
			self.check_identity()
			gajim.interface.save_new_secret(account, bjid, new_srs)

	# generate a random number between 'bottom' and 'top'
	def srand(self, bottom, top):
		# minimum number of bytes needed to represent that range
		bytes = int(math.ceil(math.log(top - bottom, 256)))

		# in retrospect, this is horribly inadequate.
		return (self.decode_mpi(self.random_bytes(bytes)) % (top - bottom)) + bottom

	def make_dhhash(self, modp):
		p = dh.primes[modp]
		g = dh.generators[modp]

		x = self.srand(2 ** (2 * self.n - 1), p - 1)

		# XXX this may be a source of performance issues
		e = self.powmod(g, x, p)

		self.xes[modp] = x
		self.es[modp] = e

		He = self.sha256(self.encode_mpi(e))

		return base64.b64encode(He)

	# a faster version of (base ** exp) % mod
	#		taken from <http://lists.danga.com/pipermail/yadis/2005-September/001445.html> 
	def powmod(self, base, exp, mod):
		square = base % mod
		result = 1

		while exp > 0:
			if exp & 1: # exponent is odd
				result = (result * square) % mod

			square = (square * square) % mod
			exp /= 2

		return result

	def terminate_e2e(self):
		self.terminate()

		self.enable_encryption = False

	def acknowledge_termination(self):
		StanzaSession.acknowledge_termination(self)
		
		self.enable_encryption = False

	def fail_bad_negotiation(self, reason):
		'''they've tried to feed us a bogus value, send an error and cancel everything.'''
		err = xmpp.Error(xmpp.Message(), xmpp.ERR_FEATURE_NOT_IMPLEMENTED)
		err.T.error.T.text.setData(reason)
		self.send(err)
		self.status = None

	def is_loggable(self):
		account = self.conn.name
		no_log_for = gajim.config.get_per('accounts', account, 'no_log_for')

		if not no_log_for:
			no_log_for = ''

		no_log_for = no_log_for.split()

		return self.loggable and account not in no_log_for and self.jid not in no_log_for
