import gajim

from common import xmpp
from common import helpers

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

		if isinstance(jid, str) or isinstance(jid, unicode):
			self.jid = xmpp.JID(jid)
		else:
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
		self.features = {}

	def generate_thread_id(self):
		return "".join([random.choice(string.letters) for x in xrange(0,32)])

	def send(self, msg):
		if self.thread_id:
			msg.setThread(self.thread_id)

		msg.setAttr('to', self.jid)
		self.conn.send_stanza(msg)

		self.last_send = time.time()

class EncryptedStanzaSession(StanzaSession):
	def __init__(self, conn, jid, thread_id, type = 'chat'):
		StanzaSession.__init__(self, conn, jid, thread_id, type = 'chat')

		self.n = 128

		self.cipher = AES
		self.hash_alg = SHA256

		self.compression = None

		self.xes = {}
		self.es = {}

		self.enable_encryption = False

		self._kc_s = None
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

	# this should be more generic?
	def sha256(self, string):
		sh = SHA256.new()
		sh.update(string)
		return sh.digest()
  
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

	def generate_nonce(self):
		# FIXME: this isn't a very good PRNG
		return os.urandom(8)

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
			raise DecryptionError

		for child in parsed.getChildren():
			stanza.addChild(node=child)

		return stanza

	def decrypt(self, ciphertext):
		return self.decrypter.decrypt(ciphertext)

	def negotiate_e2e(self):
		request = xmpp.Message()
		feature = request.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='form')

		x.addChild(node=xmpp.DataField(name='FORM_TYPE', value='urn:xmpp:ssn', typ='hidden'))
		x.addChild(node=xmpp.DataField(name='accept', value='1', typ='boolean', required=True))

		# this field is incorrectly called 'otr' in XEPs 0116 and 0217
		# unsupported options: 'mustnot'
		x.addChild(node=xmpp.DataField(name='logging', typ='list-single', options=['may'], required=True))

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

	# generate a random number between 'bottom' and 'top'
	def srand(self, bottom, top):
		# minimum number of bytes needed to represent that range
		bytes = int(math.ceil(math.log(top - bottom, 256)))

		# FIXME: use a real PRNG
		# in retrospect, this is horribly inadequate.
		return (self.decode_mpi(os.urandom(bytes)) % (top - bottom)) + bottom

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
	# 	taken from <http://lists.danga.com/pipermail/yadis/2005-September/001445.html> 
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
		self.status = None

	# 'Alice Accepts'
	def accept_e2e_alice(self, form):
#   1.  Verify that the ESession options selected by Bob are acceptable
#   2.  Return a <not-acceptable/> error to Bob unless: 1 < d < p - 1
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

		# TODO: store and return rshashes, or at least randomly generate some
		result.addChild(node=xmpp.DataField(name='rshashes', value=[]))

		form_a2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), result.getChildren()))

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(self.k)
		
		# MUST securely destroy K unless it will be used later to generate the final shared secret

		old_c_s = self.c_s

		mac_a = self.hmac(self.ks_s, self.n_o + self.n_s + self.encode_mpi(e) + self.form_a + form_a2)
		id_a = self.encrypt(mac_a)

		m_a = self.hmac(self.km_s, self.encode_mpi(old_c_s) + id_a)

		result.addChild(node=xmpp.DataField(name='identity', value=base64.b64encode(id_a)))
		result.addChild(node=xmpp.DataField(name='mac', value=base64.b64encode(m_a)))

		feature.addChild(node=result)
		self.send(accept)
		
		self.status = 'identified-alice'

	def final_steps_alice(self, form):
		# Alice MUST identify the shared retained secret (SRS) by selecting from her client's list of the secrets it retained from sessions with Bob's clients (the most recent secret for each of the clients he has used to negotiate ESessions with Alice's client).

		# Alice does this by using each secret in the list in turn as the key to calculate the HMAC (with SHA256) of the string "Shared Retained Secret", and comparing the calculated value with the value in the 'srshash' field she received from Bob (see Sending Bob's Identity). Once she finds a match, and has confirmed that the secret has not expired (because it is older than an implementation-defined period of time), then she has found the SRS.


		srs = ''
		oss = ''
		self.k = self.sha256(self.k + srs + oss)

		# Alice MUST destroy all her copies of the old retained secret (SRS) she was keeping for Bob's client, and calculate a new retained secret for this session:

		srs = self.hmac('New Retained Secret', self.k)

		# Alice MUST securely store the new value along with the retained secrets her client shares with Bob's other clients.

		# don't need to calculate ks_s here

		self.kc_s, self.km_s, self.ks_s = self.generate_initiator_keys(self.k)
		self.kc_o, self.km_o, self.ks_o = self.generate_responder_keys(self.k) 

#4.6.2 Verifying Bob's Identity

		id_b = base64.b64decode(form['identity'])

		m_b = self.hmac(self.encode_mpi(self.c_o) + id_b, self.km_o)

		mac_b = self.decrypt(id_b)

		form_b2 = ''.join(map(lambda el: xmpp.c14n.c14n(el), form.getChildren()))

		mac_b = self.hmac(self.n_s + self.n_o + self.encode_mpi(self.d) + self.form_b + form_b2, self.ks_o)

# Note: If Alice discovers an error then she SHOULD ignore any encrypted content she received in the stanza.
		# XXX check for MAC equality?

		self.status = 'active'
		self.enable_encryption = True

	def accept_e2e_bob(self):
		pass
 

#<message from='alice@example.org/pda' to='bob@example.com/laptop'>
#  <thread>ffd7076498744578d10edabfe7f4a866</thread>
#  <c xmlns='http://www.xmpp.org/extensions/xep-0200.html#ns'>
#    <data> ** Base64 encoded encrypted terminate form ** </data>
#    <old> ** Base64 encoded old MAC key ** </old>
#    <mac> ** Base64 encoded a_mac ** </mac>
#  </c>
#</message>

# <feature xmlns='http://jabber.org/protocol/feature-neg'>
#    <x xmlns='jabber:x:data' type='submit'>
#      <field var='FORM_TYPE'>
#        <value>urn:xmpp:ssn</value>
#      </field>
#      <field var='terminate'><value>1</value></field>
#    </x>
#  </feature>
