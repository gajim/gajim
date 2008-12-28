# -*- coding:utf-8 -*-
## src/common/pubsub.py
##
## Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import xmpp
import gajim
import connection_handlers

class ConnectionPubSub:
	def __init__(self):
		self.__callbacks={}

	def send_pb_subscription_query(self, jid, cb, *args, **kwargs):
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('get', to=jid)
		pb = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		pb.addChild('subscriptions')

		id_ = self.connection.send(query)

		self.__callbacks[id_]=(cb, args, kwargs)

	def send_pb_subscribe(self, jid, node, cb, *args, **kwargs):
		if not self.connection or self.connected < 2:
			return
		our_jid = gajim.get_jid_from_account(self.name)
		query = xmpp.Iq('set', to=jid)
		pb = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		pb.addChild('subscribe', {'node': node, 'jid': our_jid})

		id_ = self.connection.send(query)

		self.__callbacks[id_]=(cb, args, kwargs)

	def send_pb_unsubscribe(self, jid, node, cb, *args, **kwargs):
		if not self.connection or self.connected < 2:
			return
		our_jid = gajim.get_jid_from_account(self.name)
		query = xmpp.Iq('set', to=jid)
		pb = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

		id_ = self.connection.send(query)

		self.__callbacks[id_]=(cb, args, kwargs)

	def send_pb_publish(self, jid, node, item, id_):
		'''Publish item to a node.'''
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('set', to=jid)
		e = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		e = e.addChild('publish', {'node': node})
		e = e.addChild('item', {'id': id_}, [item])	# TODO: we should generate id... or we shouldn't?

		self.connection.send(query)

	def send_pb_retract(self, jid, node, id_):
		'''Delete item from a node'''
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('set', to=jid)
		r = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		r = r.addChild('retract', {'node': node, 'notify': '1'})
		r = r.addChild('item', {'id': id_})

		self.connection.send(query)

	def send_pb_delete(self, jid, node):
		'''Deletes node.'''
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('set', to=jid)
		d = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		d = d.addChild('delete', {'node': node})

		def response(con, resp, jid, node):
			if resp.getType() == 'result':
				self.dispatch('PUBSUB_NODE_REMOVED', (jid, node))
			else:
				msg = resp.getErrorMsg()
				self.dispatch('PUBSUB_NODE_NOT_REMOVED', (jid, node, msg))

		self.connection.SendAndCallForResponse(query, response, {'jid': jid,
			'node': node})

	def send_pb_create(self, jid, node, configure = False, configure_form = None):
		'''Creates new node.'''
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('set', to=jid)
		c = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
		c = c.addChild('create', {'node': node})
		if configure:
			conf = c.addChild('configure')
			if configure_form is not None:
				conf.addChild(node=configure_form)

		self.connection.send(query)

	def send_pb_configure(self, jid, node, form):
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('set', to=jid)
		c = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB_OWNER)
		c = c.addChild('configure', {'node': node})
		c.addChild(node=form)

		self.connection.send(query)

	def _PubSubCB(self, conn, stanza):
		try:
			cb, args, kwargs = self.__callbacks.pop(stanza.getID())
			cb(conn, stanza, *args, **kwargs)
		except Exception:
			pass

	def request_pb_configuration(self, jid, node):
		if not self.connection or self.connected < 2:
			return
		query = xmpp.Iq('get', to=jid)
		e = query.addChild('pubsub', namespace=xmpp.NS_PUBSUB_OWNER)
		e = e.addChild('configure', {'node': node})
		id_ = self.connection.getAnID()
		query.setID(id_)
		self.awaiting_answers[id_] = (connection_handlers.PEP_CONFIG,)
		self.connection.send(query)

# vim: se ts=3:
