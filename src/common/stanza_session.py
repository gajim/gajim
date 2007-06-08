import gajim

from common import xmpp
from common import helpers

import random
import string

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
