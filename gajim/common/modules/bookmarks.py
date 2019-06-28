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
from typing import List
from typing import Optional

import copy

import nbxmpp
from nbxmpp.util import is_error_result
from nbxmpp.structs import BookmarkData
from nbxmpp.const import BookmarkStoreType
from gi.repository import GLib

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


class Bookmarks(BaseModule):

    _nbxmpp_extends = 'Bookmarks'
    _nbxmpp_methods = [
        'request_bookmarks',
        'store_bookmarks',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._bookmark_event_received)
        self._conversion = False
        self._bookmarks = []
        self._join_timeouts = []
        self._request_in_progress = False

    @property
    def conversion(self):
        return self._conversion

    @property
    def bookmarks(self):
        return self._bookmarks

    @bookmarks.setter
    def bookmarks(self, value):
        self._bookmarks = value

    @event_node(nbxmpp.NS_BOOKMARKS)
    def _bookmark_event_received(self, _con, _stanza, properties):
        bookmarks = properties.pubsub_event.data

        if not properties.is_self_message:
            self._log.warning('%s has an open access bookmarks node',
                              properties.jid)
            return

        if not self._pubsub_support() or not self.conversion:
            return

        if self._request_in_progress:
            self._log.info('Ignore update, pubsub request in progress')
            return

        old_bookmarks = self._convert_to_set(self._bookmarks)
        self._bookmarks = bookmarks
        self._act_on_changed_bookmarks(old_bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def pass_disco(self, info):
        if nbxmpp.NS_BOOKMARK_CONVERSION not in info.features:
            return
        self._conversion = True
        self._log.info('Discovered Bookmarks Conversion: %s', info.jid)

    def _act_on_changed_bookmarks(self, old_bookmarks):
        new_bookmarks = self._convert_to_set(self._bookmarks)
        changed = new_bookmarks - old_bookmarks
        if not changed:
            return

        join = [jid for jid, autojoin in changed if autojoin]
        bookmarks = []
        for jid in join:
            self._log.info('Schedule autojoin in 10s for: %s', jid)
            bookmarks.append(self.get_bookmark_from_jid(jid))
        # If another client creates a MUC, the MUC is locked until the
        # configuration is finished. Give the user some time to finish
        # the configuration.
        timeout_id = GLib.timeout_add_seconds(
            10, self._join_with_timeout, bookmarks)
        self._join_timeouts.append(timeout_id)

        # TODO: leave mucs
        # leave = [jid for jid, autojoin in changed if not autojoin]

    @staticmethod
    def _convert_to_set(bookmarks):
        set_ = set()
        for bookmark in bookmarks:
            set_.add((bookmark.jid, bookmark.autojoin))
        return set_

    def get_bookmark_from_jid(self, jid):
        for bookmark in self._bookmarks:
            if bookmark.jid == jid:
                return bookmark

    def get_sorted_bookmarks(self, short_name=False):
        # This returns a sorted by name copy of the bookmarks
        sorted_bookmarks = []
        for bookmark in self._bookmarks:
            bookmark_copy = copy.deepcopy(bookmark)
            if not bookmark_copy.name:
                # No name was given for this bookmark
                # Use the first part of JID instead
                name = bookmark_copy.jid.split("@")[0]
                bookmark_copy = bookmark_copy._replace(name=name)

            if short_name:
                name = bookmark_copy.name
                name = (name[:42] + '..') if len(name) > 42 else name
                bookmark_copy = bookmark_copy._replace(name=name)

            sorted_bookmarks.append(bookmark_copy)

        sorted_bookmarks.sort(key=lambda x: x.name.lower())
        return sorted_bookmarks

    def _pubsub_support(self) -> bool:
        return (self._con.get_module('PEP').supported and
                self._con.get_module('PubSub').publish_options)

    def request_bookmarks(self):
        if not app.account_is_connected(self._account):
            return

        self._request_in_progress = True
        type_ = BookmarkStoreType.PRIVATE
        if self._pubsub_support() and self.conversion:
            type_ = BookmarkStoreType.PUBSUB

        self._nbxmpp('Bookmarks').request_bookmarks(
            type_, callback=self._bookmarks_received)

    def _bookmarks_received(self, bookmarks):
        if is_error_result(bookmarks):
            self._log.info('Error: %s', bookmarks)
            bookmarks = []

        self._request_in_progress = False
        self._bookmarks = bookmarks
        self.auto_join_bookmarks()
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def store_bookmarks(self):
        if not app.account_is_connected(self._account):
            return

        type_ = BookmarkStoreType.PRIVATE
        if self._pubsub_support() and self.conversion:
            type_ = BookmarkStoreType.PUBSUB

        self._nbxmpp('Bookmarks').store_bookmarks(self._bookmarks, type_)

        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def _join_with_timeout(self, bookmarks: List[Any]) -> None:
        self._join_timeouts.pop(0)
        self.auto_join_bookmarks(bookmarks)

    def auto_join_bookmarks(self, bookmarks: Optional[List[Any]] = None) -> None:
        if app.is_invisible(self._account):
            return

        if bookmarks is None:
            bookmarks = self._bookmarks

        for bookmark in bookmarks:
            if bookmark.autojoin:
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if bookmark.jid not in app.gc_connected[self._account]:
                    # we are not already connected
                    self._log.info('Autojoin Bookmark: %s', bookmark.jid)
                    minimize = app.config.get_per('rooms', bookmark.jid,
                                                  'minimize_on_autojoin', True)
                    app.interface.join_gc_room(
                        self._account, bookmark.jid, bookmark.nick,
                        bookmark.password, minimize=minimize)

    def add_bookmark(self, name, jid, autojoin, password, nick):
        bookmark = BookmarkData(jid=jid,
                                name=name,
                                autojoin=autojoin,
                                password=password,
                                nick=nick)
        self._bookmarks.append(bookmark)
        self.store_bookmarks()

    def remove(self, jid: str, publish: bool = True) -> None:
        bookmark = self.get_bookmark_from_jid(jid)
        if bookmark is None:
            return
        self._bookmarks.remove(bookmark)
        if publish:
            self.store_bookmarks()

    def get_name_from_bookmark(self, jid: str) -> str:
        fallback = jid.split('@')[0]
        bookmark = self.get_bookmark_from_jid(jid)
        if bookmark is None:
            return fallback
        return bookmark.name or fallback

    def is_bookmark(self, jid: str) -> bool:
        return self.get_bookmark_from_jid(jid) is not None

    def purge_pubsub_bookmarks(self) -> None:
        self._log.info('Purge/Delete Bookmarks on PubSub, '
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
