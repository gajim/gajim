# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0048: Bookmarks

import logging
import copy
from collections import OrderedDict

import nbxmpp

from gajim.common import app
from gajim.common import helpers
from gajim.common.const import BookmarkStorageType
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.modules.util import from_xs_boolean
from gajim.common.modules.util import to_xs_boolean

log = logging.getLogger('gajim.c.m.bookmarks')


class Bookmarks:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self.bookmarks = {}
        self.available = False

        self.handlers = []

    def get_sorted_bookmarks(self, short_name=False):
        # This returns a sorted by name copy of the bookmarks
        sorted_bookmarks = {}
        for jid, bookmarks in self.bookmarks.items():
            bookmark_copy = copy.deepcopy(bookmarks)
            if not bookmark_copy['name']:
                # No name was given for this bookmark
                # Use the first part of JID instead
                name = jid.split("@")[0]
                bookmark_copy['name'] = name

            if short_name:
                name = bookmark_copy['name']
                name = (name[:42] + '..') if len(name) > 42 else name
                bookmark_copy['name'] = name

            sorted_bookmarks[jid] = bookmark_copy
        return OrderedDict(
            sorted(sorted_bookmarks.items(),
                   key=lambda bookmark: bookmark[1]['name'].lower()))

    def _pubsub_support(self):
        return (self._con.get_module('PEP').supported and
                self._con.get_module('PubSub').publish_options)

    def get_bookmarks(self, storage_type=None):
        if not app.account_is_connected(self._account):
            return

        if storage_type in (None, BookmarkStorageType.PUBSUB):
            if self._pubsub_support():
                self._request_pubsub_bookmarks()
            else:
                # Fallback, request private storage
                self._request_private_bookmarks()
        else:
            log.info('Request Bookmarks (PrivateStorage)')
            self._request_private_bookmarks()

    def _request_pubsub_bookmarks(self):
        log.info('Request Bookmarks (PubSub)')
        self._con.get_module('PubSub').send_pb_retrieve(
            '', 'storage:bookmarks',
            cb=self._pubsub_bookmarks_received)

    def _pubsub_bookmarks_received(self, conn, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('No pubsub bookmarks: %s', stanza.getError())
            # Fallback, request private storage
            self._request_private_bookmarks()
            return

        self.available = True
        log.info('Received Bookmarks (PubSub)')
        self._parse_bookmarks(stanza)
        self._request_private_bookmarks()

    def _request_private_bookmarks(self):
        if not app.account_is_connected(self._account):
            return

        iq = nbxmpp.Iq(typ='get')
        query = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        query.addChild(name='storage', namespace='storage:bookmarks')
        log.info('Request Bookmarks (PrivateStorage)')
        self._con.connection.SendAndCallForResponse(
            iq, self._private_bookmarks_received)

    def _private_bookmarks_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('No private bookmarks: %s', stanza.getError())
        else:
            self.available = True
            log.info('Received Bookmarks (PrivateStorage)')
            merged = self._parse_bookmarks(stanza, check_merge=True)
            if merged and self._pubsub_support():
                log.info('Merge PrivateStorage with PubSub')
                self.store_bookmarks(BookmarkStorageType.PUBSUB)
        self.auto_join_bookmarks()
        app.nec.push_incoming_event(BookmarksReceivedEvent(
            None, account=self._account))

    @staticmethod
    def _get_storage_node(stanza):
        node = stanza.getTag('pubsub', namespace=nbxmpp.NS_PUBSUB)
        if node is None:
            node = stanza.getTag('event', namespace=nbxmpp.NS_PUBSUB_EVENT)
            if node is None:
                # Private Storage
                query = stanza.getQuery()
                if query is None:
                    return
                storage = query.getTag('storage',
                                       namespace=nbxmpp.NS_BOOKMARKS)
                if storage is None:
                    return
                return storage

        items_node = node.getTag('items')
        if items_node is None:
            return
        if items_node.getAttr('node') != nbxmpp.NS_BOOKMARKS:
            return

        item_node = items_node.getTag('item')
        if item_node is None:
            return

        storage = item_node.getTag('storage', namespace=nbxmpp.NS_BOOKMARKS)
        if storage is None:
            return
        return storage

    def _parse_bookmarks(self, stanza, check_merge=False):
        merged = False
        storage = self._get_storage_node(stanza)
        if storage is None:
            return

        NS_GAJIM_BM = 'xmpp:gajim.org/bookmarks'
        confs = storage.getTags('conference')
        for conf in confs:
            autojoin_val = conf.getAttr('autojoin')
            if not autojoin_val:  # not there (it's optional)
                autojoin_val = False
            minimize_val = conf.getTag('minimize', namespace=NS_GAJIM_BM)
            if not minimize_val:  # not there, try old Gajim behaviour
                minimize_val = conf.getAttr('minimize')
                if not minimize_val:  # not there (it's optional)
                    minimize_val = False
            else:
                minimize_val = minimize_val.getData()

            print_status = conf.getTag('print_status', namespace=NS_GAJIM_BM)
            if not print_status:  # not there, try old Gajim behaviour
                print_status = conf.getTagData('print_status')
                if not print_status:  # not there, try old Gajim behaviour
                    print_status = conf.getTagData('show_status')
            else:
                print_status = print_status.getData()

            try:
                jid = helpers.parse_jid(conf.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it'
                            % conf.getAttr('jid'))
                continue

            if check_merge:
                if jid in self.bookmarks:
                    continue
                merged = True

            log.debug('Found Bookmark: %s', jid)
            self.bookmarks[jid] = {
                'name': conf.getAttr('name'),
                'autojoin': from_xs_boolean(autojoin_val),
                'minimize': from_xs_boolean(minimize_val),
                'password': conf.getTagData('password'),
                'nick': conf.getTagData('nick'),
                'print_status': print_status}

        return merged

    def _build_storage_node(self):
        NS_GAJIM_BM = 'xmpp:gajim.org/bookmarks'
        storage_node = nbxmpp.Node(
            tag='storage', attrs={'xmlns': 'storage:bookmarks'})
        for jid, bm in self.bookmarks.items():
            conf_node = storage_node.addChild(name="conference")
            conf_node.setAttr('jid', jid)
            conf_node.setAttr('autojoin', to_xs_boolean(bm['autojoin']))
            conf_node.setAttr('name', bm['name'])
            conf_node.setTag('minimize', namespace=NS_GAJIM_BM).setData(
                to_xs_boolean(bm['minimize']))
            # Only add optional elements if not empty
            # Note: need to handle both None and '' as empty
            #   thus shouldn't use "is not None"
            if bm.get('nick', None):
                conf_node.setTagData('nick', bm['nick'])
            if bm.get('password', None):
                conf_node.setTagData('password', bm['password'])
            if bm.get('print_status', None):
                conf_node.setTag(
                    'print_status',
                    namespace=NS_GAJIM_BM).setData(bm['print_status'])
        return storage_node

    @staticmethod
    def get_bookmark_publish_options():
        options = nbxmpp.Node(nbxmpp.NS_DATA + ' x',
                              attrs={'type': 'submit'})
        f = options.addChild('field',
                             attrs={'var': 'FORM_TYPE', 'type': 'hidden'})
        f.setTagData('value', nbxmpp.NS_PUBSUB_PUBLISH_OPTIONS)
        f = options.addChild('field', attrs={'var': 'pubsub#access_model'})
        f.setTagData('value', 'whitelist')
        return options

    def store_bookmarks(self, storage_type=None):
        if not app.account_is_connected(self._account):
            return

        storage_node = self._build_storage_node()

        if storage_type is None:
            if self._pubsub_support():
                self._pubsub_store(storage_node)
            self._private_store(storage_node)
        elif storage_type == BookmarkStorageType.PUBSUB:
            if self._pubsub_support():
                self._pubsub_store(storage_node)
        elif storage_type == BookmarkStorageType.PRIVATE:
            self._private_store(storage_node)

    def _pubsub_store(self, storage_node):
        self._con.get_module('PubSub').send_pb_publish(
            '', 'storage:bookmarks', storage_node, 'current',
            options=self.get_bookmark_publish_options(),
            cb=self._pubsub_store_result)
        log.info('Publish Bookmarks (PubSub)')

    def _private_store(self, storage_node):
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVATE, payload=storage_node)
        log.info('Publish Bookmarks (PrivateStorage)')
        self._con.connection.SendAndCallForResponse(
            iq, self._private_store_result)

    def _pubsub_store_result(self, conn, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.error('Error: %s', stanza.getError())
            return

    def _private_store_result(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.error('Error: %s', stanza.getError())
            return

    def auto_join_bookmarks(self):
        if app.is_invisible(self._account):
            return
        for jid, bm in self.bookmarks.items():
            if bm['autojoin']:
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if jid not in app.gc_connected[self._account]:
                    # we are not already connected
                    app.interface.join_gc_room(
                        self._account, jid, bm['nick'],
                        bm['password'], minimize=bm['minimize'])

    def add_bookmark(self, name, jid, autojoin,
                     minimize, password, nick):
        self.bookmarks[jid] = {
            'name': name,
            'autojoin': autojoin,
            'minimize': minimize,
            'password': password,
            'nick': nick,
            'print_status': None}

        self.store_bookmarks()
        app.nec.push_incoming_event(BookmarksReceivedEvent(
            None, account=self._account))

    def get_name_from_bookmark(self, jid):
        fallback = jid.split('@')[0]
        try:
            return self.bookmarks[jid]['name'] or fallback
        except KeyError:
            return fallback

    def purge_pubsub_bookmarks(self):
        log.info('Purge/Delete Bookmarks on PubSub, '
                 'because publish options are not available')
        self._con.get_module('PubSub').send_pb_purge('', 'storage:bookmarks')
        self._con.get_module('PubSub').send_pb_delete('', 'storage:bookmarks')


class BookmarksReceivedEvent(NetworkIncomingEvent):
    name = 'bookmarks-received'
    base_network_events = []


def get_instance(*args, **kwargs):
    return Bookmarks(*args, **kwargs), 'Bookmarks'
