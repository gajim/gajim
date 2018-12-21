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

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import logging
import copy
from collections import OrderedDict

import nbxmpp
from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common.const import PEPEventType
from gajim.common.nec import NetworkEvent
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule
from gajim.common.modules.pep import AbstractPEPData
from gajim.common.modules.util import from_xs_boolean
from gajim.common.modules.util import to_xs_boolean


log = logging.getLogger('gajim.c.m.bookmarks')

NS_GAJIM_BM = 'xmpp:gajim.org/bookmarks'


class BookmarksData(AbstractPEPData):

    type_ = PEPEventType.BOOKMARKS


class Bookmarks(AbstractPEPModule):

    name = 'storage'
    namespace = 'storage:bookmarks'
    pep_class = BookmarksData
    store_publish = False
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con)

        self.bookmarks = {}
        self.conversion = False
        self._join_timeouts = []
        self._request_in_progress = False

    def pass_disco(self, from_, _identities, features, _data, _node):
        if nbxmpp.NS_BOOKMARK_CONVERSION not in features:
            return
        self.conversion = True
        log.info('Discovered Bookmarks Conversion: %s', from_)

    def _extract_info(self, item):
        storage = item.getTag('storage', namespace=self.namespace)
        if storage is None:
            raise StanzaMalformed('No storage node')
        return storage

    def _notification_received(self, jid: nbxmpp.JID, user_pep: Any) -> None:
        if self._request_in_progress:
            log.info('Ignore update, pubsub request in progress')
            return

        if not self._con.get_own_jid().bareMatch(jid):
            log.warning('%s has an open access bookmarks node', jid)
            return

        if not self._pubsub_support() or not self.conversion:
            return

        old_bookmarks = self._convert_to_set(self.bookmarks)
        self.bookmarks = self._parse_bookmarks(user_pep.data)
        self._act_on_changed_bookmarks(old_bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def _act_on_changed_bookmarks(self, old_bookmarks):
        new_bookmarks = self._convert_to_set(self.bookmarks)
        changed = new_bookmarks - old_bookmarks
        if not changed:
            return

        join = [jid for jid, autojoin in changed if autojoin]
        for jid in join:
            log.info('Schedule autojoin in 10s for: %s', jid)
        # If another client creates a MUC, the MUC is locked until the
        # configuration is finished. Give the user some time to finish
        # the configuration.
        timeout_id = GLib.timeout_add_seconds(
            10, self._join_with_timeout, join)
        self._join_timeouts.append(timeout_id)

        # TODO: leave mucs
        # leave = [jid for jid, autojoin in changed if not autojoin]

    @staticmethod
    def _convert_to_set(bookmarks):
        set_ = set()
        for jid in bookmarks:
            set_.add((jid, bookmarks[jid]['autojoin']))
        return set_

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

    def _pubsub_support(self) -> bool:
        return (self._con.get_module('PEP').supported and
                self._con.get_module('PubSub').publish_options)

    def get_bookmarks(self):
        if not app.account_is_connected(self._account):
            return

        if self._pubsub_support() and self.conversion:
            self._request_pubsub_bookmarks()
        else:
            self._request_private_bookmarks()

    def _request_pubsub_bookmarks(self) -> None:
        log.info('Request Bookmarks (PubSub)')
        self._request_in_progress = True
        self._con.get_module('PubSub').send_pb_retrieve(
            '', 'storage:bookmarks', cb=self._bookmarks_received)

    def _request_private_bookmarks(self) -> None:
        self._request_in_progress = True
        iq = nbxmpp.Iq(typ='get')
        query = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        query.addChild(name='storage', namespace='storage:bookmarks')
        log.info('Request Bookmarks (PrivateStorage)')
        self._con.connection.SendAndCallForResponse(
            iq, self._bookmarks_received, {})

    def _bookmarks_received(self, _con, stanza):
        self._request_in_progress = False
        if not nbxmpp.isResultNode(stanza):
            log.info('No bookmarks found: %s', stanza.getError())
        else:
            log.info('Received Bookmarks')
            storage = self._get_storage_node(stanza)
            if storage is not None:
                self.bookmarks = self._parse_bookmarks(storage)
                self.auto_join_bookmarks()

        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

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

    @staticmethod
    def _parse_bookmarks(storage: nbxmpp.Node) -> Dict[str, Dict[str, Any]]:
        bookmarks = {}
        confs = storage.getTags('conference')
        for conf in confs:
            autojoin_val = conf.getAttr('autojoin')
            if not autojoin_val:  # not there (it's optional)
                autojoin_val = False

            minimize_val = conf.getTag('minimize', namespace=NS_GAJIM_BM)
            if not minimize_val:
                minimize_val = False
            else:
                minimize_val = minimize_val.getData()

            print_status = conf.getTag('print_status', namespace=NS_GAJIM_BM)
            if not print_status:  # not there, try old Gajim behaviour
                print_status = None
            else:
                print_status = print_status.getData()

            try:
                jid = helpers.parse_jid(conf.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            conf.getAttr('jid'))
                continue

            bookmark = {
                'name': conf.getAttr('name'),
                'password': conf.getTagData('password'),
                'nick': conf.getTagData('nick'),
                'print_status': print_status
            }

            try:
                bookmark['autojoin'] = from_xs_boolean(autojoin_val)
                bookmark['minimize'] = from_xs_boolean(minimize_val)
            except ValueError as error:
                log.warning(error)
                continue

            log.debug('Found Bookmark: %s', jid)
            bookmarks[jid] = bookmark

        return bookmarks

    @staticmethod
    def _build_storage_node(bookmarks):
        storage_node = nbxmpp.Node(
            tag='storage', attrs={'xmlns': 'storage:bookmarks'})
        for jid, bm in bookmarks.items():
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

    def _build_node(self, _data):
        pass

    @staticmethod
    def get_bookmark_publish_options() -> nbxmpp.Node:
        options = nbxmpp.Node(nbxmpp.NS_DATA + ' x',
                              attrs={'type': 'submit'})
        field = options.addChild('field',
                                 attrs={'var': 'FORM_TYPE', 'type': 'hidden'})
        field.setTagData('value', nbxmpp.NS_PUBSUB_PUBLISH_OPTIONS)
        field = options.addChild('field', attrs={'var': 'pubsub#access_model'})
        field.setTagData('value', 'whitelist')
        return options

    def store_bookmarks(self):
        if not app.account_is_connected(self._account):
            return

        storage_node = self._build_storage_node(self.bookmarks)
        if self._pubsub_support() and self.conversion:
            self._pubsub_store(storage_node)
        else:
            self._private_store(storage_node)

    def _pubsub_store(self, storage_node: nbxmpp.Node) -> None:
        self._con.get_module('PubSub').send_pb_publish(
            '', 'storage:bookmarks', storage_node, 'current',
            options=self.get_bookmark_publish_options(),
            cb=self._pubsub_store_result)
        log.info('Publish Bookmarks (PubSub)')

    def _private_store(self, storage_node: nbxmpp.Node) -> None:
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVATE, payload=storage_node)
        log.info('Publish Bookmarks (PrivateStorage)')
        self._con.connection.SendAndCallForResponse(
            iq, self._private_store_result)

    @staticmethod
    def _pubsub_store_result(_con, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.error('Error: %s', stanza.getError())
            return

    @staticmethod
    def _private_store_result(stanza: nbxmpp.Iq) -> None:
        if not nbxmpp.isResultNode(stanza):
            log.error('Error: %s', stanza.getError())
            return

    def _join_with_timeout(self, bookmarks: Optional[List[str]] = None) -> None:
        self._join_timeouts.pop(0)
        self.auto_join_bookmarks(bookmarks)

    def auto_join_bookmarks(self, bookmarks: Optional[List[str]] = None) -> None:
        if app.is_invisible(self._account):
            return
        if bookmarks is None:
            bookmarks = self.bookmarks.keys()

        for jid in bookmarks:
            bookmark = self.bookmarks[jid]
            if bookmark['autojoin']:
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if jid not in app.gc_connected[self._account]:
                    # we are not already connected
                    log.info('Autojoin Bookmark: %s', jid)
                    app.interface.join_gc_room(
                        self._account, jid, bookmark['nick'],
                        bookmark['password'], minimize=bookmark['minimize'])

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
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def get_name_from_bookmark(self, jid: str) -> str:
        fallback = jid.split('@')[0]
        try:
            return self.bookmarks[jid]['name'] or fallback
        except KeyError:
            return fallback

    def purge_pubsub_bookmarks(self) -> None:
        log.info('Purge/Delete Bookmarks on PubSub, '
                 'because publish options are not available')
        self._con.get_module('PubSub').send_pb_purge('', 'storage:bookmarks')
        self._con.get_module('PubSub').send_pb_delete('', 'storage:bookmarks')

    def _remove_timeouts(self):
        for _id in self._join_timeouts:
            GLib.source_remove(_id)

    def cleanup(self):
        self._remove_timeouts()


def get_instance(*args, **kwargs):
    return Bookmarks(*args, **kwargs), 'Bookmarks'
