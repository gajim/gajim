import gajim

from common import xmpp
from common import helpers

import random
import string

from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256

import base64

class StanzaSession:
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
		self.features = {}

	def generate_thread_id(self):
		return "".join([random.choice(string.letters) for x in xrange(0,32)])


class EncryptedStanzaSession(StanzaSession):
	def __init__(self, conn, jid, thread_id, type = 'chat'):
		StanzaSession.__init__(self, conn, jid, thread_id, type = 'chat')

		self.n = 128

		self.cipher = AES
		self.hash_alg = SHA256

		self.en_key = '................'
		self.de_key = '----------------'

		self.en_counter = 777
		self.de_counter = 777 ^ (2 ** (self.n - 1))

		self.encrypter = self.cipher.new(self.en_key, self.cipher.MODE_CTR, counter=self.encryptcounter)
		self.decrypter = self.cipher.new(self.de_key, self.cipher.MODE_CTR, counter=self.decryptcounter)

		self.compression = None

		self.enable_encryption = False

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
		self.en_counter = (self.en_counter + 1) % 2 ** self.n
		return self.encode_mpi_with_padding(self.en_counter)
	
	def decryptcounter(self):
		self.de_counter = (self.de_counter + 1) % 2 ** self.n
		return self.encode_mpi_with_padding(self.de_counter)

	def encrypt_stanza(self, stanza):
		encryptable = filter(lambda x: x.getName() not in ('error', 'amp', 'thread'), stanza.getChildren())

		# XXX can also encrypt contents of <error/> elements in stanzas @type = 'error'
		# (except for <defined-condition xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/> child elements)

		old_en_counter = self.en_counter

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
		c.NT.mac = base64.b64encode(self.hmac(m_content, old_en_counter, self.en_key))

		return stanza

	def hmac(self, content, counter, key):
		return HMAC.new(key, content + self.encode_mpi_with_padding(counter), self.hash_alg).digest()

	def compress(self, plaintext):
		if self.compression == None:
			return plaintext

	def decompress(self, compressed):
		if self.compression == None:
			return compressed 

	def encrypt(self, encryptable):
		len_padding = 16 - (len(encryptable) % 16)
		encryptable += len_padding * ' '

		return self.encrypter.encrypt(encryptable)

	def decrypt_stanza(self, stanza):
		c = stanza.getTag(name='c', namespace='http://www.xmpp.org/extensions/xep-0200.html#ns')

		stanza.delChild(c)

		# contents of <c>, minus <mac>, minus whitespace
		macable = ''.join(map(str, filter(lambda x: x.getName() != 'mac', c.getChildren())))

		received_mac = base64.b64decode(c.getTagData('mac'))
		calculated_mac = self.hmac(macable, self.de_counter, self.de_key)

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

	def negotiate_e2e():
		pass

#<x type='form' xmlns='jabber:x:data'>
#      <field type='hidden' var='FORM_TYPE'>
#        <value>urn:xmpp:ssn</value>
#      </field>
#      <field type='boolean' var='accept'>
#        <value>1</value>
#        <required/>
#      </field>
#      <field type='list-single' var='otr'>
#        <option><value>false</value></option>
#        <option><value>true</value></option>
#        <required/>
#      </field>
#      <field type='list-single' var='disclosure'>
#        <option><value>never</value></option>
#        <required/>
#      </field>
#      <field type='list-single' var='security'>
#        <option><value>e2e</value></option>
#        <option><value>c2s</value></option>
#        <required/>
#      </field>
#      <field type='list-single' var='modp'>
#        <option><value>5</value></option>
#        <option><value>14</value></option>
#        <option><value>2</value></option>
#        <option><value>1</value></option>
#      </field>
#      <field type='hidden' var='crypt_algs'>
#        <value>aes128-ctr</value>
#      </field>
#      <field type='hidden' var='hash_algs'>
#        <value>sha256</value>
#      </field>
#      <field type='hidden' var='compress'>
#        <value>none</value>
#      </field>
#      <field type='list-multi' var='stanzas'>
#        <option><value>message</value></option>
#        <option><value>iq</value></option>
#        <option><value>presence</value></option>
#      </field>
#      <field type='hidden' var='init_pubkey'>
#        <value>none</value>
#      </field>
#      <field type='hidden' var='resp_pubkey'>
#       <value>none</value>
#      </field>
#      <field type='list-single' var='ver'>
#        <option><value>1.3</value></option>
#        <option><value>1.2</value></option>
#      </field>
#      <field type='hidden' var='rekey_freq'>
#        <value>4294967295</value>
#      </field>
#      <field type='hidden' var='my_nonce'>
#        <value> ** Alice's Base64 encoded ESession ID ** </value>
#      </field>
#      <field type='hidden' var='sas_algs'>
#        <value>sas28x5</value>
#      </field>
#      <field type='hidden' var='dhhashes'>
#        <value> ** Base64 encoded value of He5 ** </value>
#        <value> ** Base64 encoded value of He14 ** </value>
#        <value> ** Base64 encoded value of He2 ** </value>
#        <value> ** Base64 encoded value of He1 ** </value>
#      </field>
#    </x> 

	def terminate_e2e():
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
