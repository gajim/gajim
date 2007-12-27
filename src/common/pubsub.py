import xmpp
import gajim
import connection_handlers

class ConnectionPubSub:
	def __init__(self):
		self.__callbacks={}

	def send_pb_subscription_query(self, jid, cb, *args, **kwargs):
		query = xmpp.Iq('get', to=jid)
		pb = query.addChild('pubsub', {'xmlns': xmpp.NS_PUBSUB})
		pb.addChild('subscriptions')

		id = self.connection.send(query)

		self.__callbacks[id]=(cb, args, kwargs)

	def send_pb_subscribe(self, jid, node, cb, *args, **kwargs):
		our_jid = gajim.get_jid_from_account(self.name)
		query = xmpp.Iq('set', to=jid)
		pb = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		pb.addChild('subscribe', {'node': node, 'jid': our_jid})

		id = self.connection.send(query)

		self.__callbacks[id]=(cb, args, kwargs)

	def send_pb_unsubscribe(self, jid, node, cb, *args, **kwargs):
		our_jid = gajim.get_jid_from_account(self.name)
		query = xmpp.Iq('set', to=jid)
		pb = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

		id = self.connection.send(query)

		self.__callbacks[id]=(cb, args, kwargs)

	def send_pb_publish(self, jid, node, item, id):
		'''Publish item to a node.'''
		query = xmpp.Iq('set', to=jid)
		e = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		e = e.addChild('publish', {'node': node})
		e = e.addChild('item', {'id': id}, [item])	# TODO: we should generate id... or we shouldn't?

		self.connection.send(query)

	def send_pb_delete(self, jid, node):
		'''Deletes node.'''
		query = xmpp.Iq('set', to=jid)
		d = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		d = d.addChild('delete', {'node': node})

		self.connection.send(query)

	def send_pb_create(self, jid, node, configure = False, configure_form = None):
		'''Creates new node.'''
		query = xmpp.Iq('set', to=jid)
		c = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		c = c.addChild('create', {'node': node})
		if configure:
			conf = c.addChild('configure')
			if configure_form is not None:
				conf.addChild(node=configure_form)

		self.connection.send(query)

	def send_pb_configure(self, jid, node, cb, *cbargs, **cbkwargs):
		query = xmpp.Iq('set', to=jid)
		c = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		c = c.addChild('configure', {'node': node})

		id = self.connection.send(query)

		def on_configure(self, connection, query):
			try:
				filledform = cb(stanza['pubsub']['configure']['x'], *cbargs, **cbkwargs)
				#TODO: Build a form
				#TODO: Send it

			except CancelConfigure:
				cancel = xmpp.Iq('set', to=jid)
				ca = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
				ca = ca.addChild('configure', {'node': node})
				#ca = ca.addChild('x', namespace=xmpp.NS_DATA, {'type': 'cancel'})

				self.connection.send(cancel)

		self.__callbacks[id] = (on_configure, (), {})

	def _PubSubCB(self, conn, stanza):
		try:
			cb, args, kwargs = self.__callbacks.pop(stanza.getID())
			cb(conn, stanza, *args, **kwargs)
		except:
			pass

	def request_pb_configuration(self, jid, node):
		query = xmpp.Iq('get', to=jid)
		e = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB_OWNER)
		e = e.addChild('configure', {'node': node})
		id = self.connection.getAnID()
		query.setID(id)
		self.awaiting_answers[id] = (connection_handlers.PEP_ACCESS_MODEL,)
		self.connection.send(query)
