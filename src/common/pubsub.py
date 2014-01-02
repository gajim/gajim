# -*- coding:utf-8 -*-
## src/common/pubsub.py
##
## Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
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

import nbxmpp
from common import gajim
#TODO: Doesn't work
#from common.connection_handlers import PEP_CONFIG
PEP_CONFIG = 'pep_config'
from common import ged
from common.connection_handlers_events import PubsubReceivedEvent
from common.connection_handlers_events import PubsubBookmarksReceivedEvent
import logging
log = logging.getLogger('gajim.c.pubsub')

class ConnectionPubSub:
    def __init__(self):
        self.__callbacks = {}
        gajim.nec.register_incoming_event(PubsubBookmarksReceivedEvent)
        gajim.ged.register_event_handler('pubsub-bookmarks-received',
            ged.CORE, self._nec_pubsub_bookmarks_received)

    def cleanup(self):
        gajim.ged.remove_event_handler('pubsub-bookmarks-received',
            ged.CORE, self._nec_pubsub_bookmarks_received)

    def send_pb_subscription_query(self, jid, cb, *args, **kwargs):
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('get', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('subscriptions')

        id_ = self.connection.send(query)

        self.__callbacks[id_] = (cb, args, kwargs)

    def send_pb_subscribe(self, jid, node, cb, *args, **kwargs):
        if not self.connection or self.connected < 2:
            return
        our_jid = gajim.get_jid_from_account(self.name)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('subscribe', {'node': node, 'jid': our_jid})

        id_ = self.connection.send(query)

        self.__callbacks[id_] = (cb, args, kwargs)

    def send_pb_unsubscribe(self, jid, node, cb, *args, **kwargs):
        if not self.connection or self.connected < 2:
            return
        our_jid = gajim.get_jid_from_account(self.name)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

        id_ = self.connection.send(query)

        self.__callbacks[id_] = (cb, args, kwargs)

    def send_pb_publish(self, jid, node, item, id_=None, options=None):
        """
        Publish item to a node
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        e = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        p = e.addChild('publish', {'node': node})
        attrs = {}
        if id_:
            attrs = {'id': id_}
        p.addChild('item', attrs, [item])
        if options:
            p = e.addChild('publish-options')
            p.addChild(node=options)

        self.connection.send(query)

    def send_pb_retrieve(self, jid, node, cb=None, *args, **kwargs):
        """
        Get items from a node
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('get', to=jid)
        r = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        r = r.addChild('items', {'node': node})
        id_ = self.connection.send(query)

        if cb:
            self.__callbacks[id_] = (cb, args, kwargs)

    def send_pb_retract(self, jid, node, id_):
        """
        Delete item from a node
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        r = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        r = r.addChild('retract', {'node': node, 'notify': '1'})
        r = r.addChild('item', {'id': id_})

        self.connection.send(query)

    def send_pb_purge(self, jid, node):
        """
        Purge node: Remove all items
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        d = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        d = d.addChild('purge', {'node': node})

        self.connection.send(query)

    def send_pb_delete(self, jid, node, on_ok=None, on_fail=None):
        """
        Delete node
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        d = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        d = d.addChild('delete', {'node': node})

        def response(con, resp, jid, node):
            if resp.getType() == 'result' and on_ok:
                on_ok(jid, node)
            elif on_fail:
                msg = resp.getErrorMsg()
                on_fail(jid, node, msg)

        self.connection.SendAndCallForResponse(query, response, {'jid': jid,
            'node': node})

    def send_pb_create(self, jid, node, configure=False, configure_form=None):
        """
        Create a new node
        """
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        c = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB)
        c = c.addChild('create', {'node': node})
        if configure:
            conf = c.addChild('configure')
            if configure_form is not None:
                conf.addChild(node=configure_form)

        self.connection.send(query)

    def send_pb_configure(self, jid, node, form):
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('set', to=jid)
        c = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        c = c.addChild('configure', {'node': node})
        c.addChild(node=form)

        self.connection.send(query)

    def _PubSubCB(self, conn, stanza):
        log.debug('_PubsubCB')
        try:
            cb, args, kwargs = self.__callbacks.pop(stanza.getID())
            cb(conn, stanza, *args, **kwargs)
        except Exception:
            pass
        gajim.nec.push_incoming_event(PubsubReceivedEvent(None,
            conn=self, stanza=stanza))

    def _nec_pubsub_bookmarks_received(self, obj):
        if obj.conn.name != self.name:
            return
        bm_jids = [b['jid'] for b in self.bookmarks]
        for bm in obj.bookmarks:
            if bm['jid'] not in bm_jids:
                self.bookmarks.append(bm)
        # We got bookmarks from pubsub, now get those from xml to merge them
        self.get_bookmarks(storage_type='xml')

    def _PubSubErrorCB(self, conn, stanza):
        log.debug('_PubsubErrorCB')
        pubsub = stanza.getTag('pubsub')
        if not pubsub:
            return
        items = pubsub.getTag('items')
        if not items:
            return
        if items.getAttr('node') == 'storage:bookmarks':
            # Receiving bookmarks from pubsub failed, so take them from xml
            self.get_bookmarks(storage_type='xml')

    def request_pb_configuration(self, jid, node):
        if not self.connection or self.connected < 2:
            return
        query = nbxmpp.Iq('get', to=jid)
        e = query.addChild('pubsub', namespace=nbxmpp.NS_PUBSUB_OWNER)
        e = e.addChild('configure', {'node': node})
        id_ = self.connection.getAnID()
        query.setID(id_)
        self.awaiting_answers[id_] = (PEP_CONFIG,)
        self.connection.send(query)
