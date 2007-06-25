import xmpp
import gajim

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

	def _PubSubCB(self, conn, stanza):
		try:
			cb, args, kwargs = self.__callbacks.pop(stanza.getID())
			cb(conn, stanza, *args, **kwargs)
		except:
			pass
