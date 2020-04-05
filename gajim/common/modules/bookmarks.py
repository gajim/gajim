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
from typing import Dict
from typing import Set
from typing import Tuple
from typing import Union
from typing import Optional

import nbxmpp
from nbxmpp.protocol import JID
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
        'retract_bookmark',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._bookmark_event_received)
        self._register_pubsub_handler(self._bookmark_2_event_received)
        self._conversion = False
        self._conversion_2 = False
        self._bookmarks = {}
        self._join_timeouts = []
        self._request_in_progress = True

    @property
    def conversion(self) -> bool:
        return self._conversion

    @property
    def conversion_2(self) -> bool:
        return self._conversion_2

    @property
    def bookmarks(self) -> List[BookmarkData]:
        return self._bookmarks.values()

    @property
    def using_bookmark_1(self) -> bool:
        return self._pubsub_support() and self.conversion

    @property
    def using_bookmark_2(self) -> bool:
        return self._pubsub_support() and self.conversion_2

    @event_node(nbxmpp.NS_BOOKMARKS)
    def _bookmark_event_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        if not properties.is_self_message:
            self._log.warning('%s has an open access bookmarks node',
                              properties.jid)
            return

        if not self.using_bookmark_1:
            return

        if self._request_in_progress:
            self._log.info('Ignore update, pubsub request in progress')
            return

        bookmarks = self._convert_to_dict(properties.pubsub_event.data)

        old_bookmarks = self._bookmarks.copy()
        self._bookmarks = bookmarks
        self._act_on_changed_bookmarks(old_bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    @event_node(nbxmpp.NS_BOOKMARKS_2)
    def _bookmark_2_event_received(self, _con, _stanza, properties):
        if not properties.is_self_message:
            self._log.warning('%s has an open access bookmarks node',
                              properties.jid)
            return

        if not self.using_bookmark_2:
            return

        if self._request_in_progress:
            self._log.info('Ignore update, pubsub request in progress')
            return

        old_bookmarks = self._bookmarks.copy()

        if properties.pubsub_event.deleted or properties.pubsub_event.purged:
            self._log.info('Bookmark node deleted/purged')
            self._bookmarks = {}

        elif properties.pubsub_event.retracted:
            jid = properties.pubsub_event.id
            self._log.info('Retract: %s', jid)
            bookmark = self._bookmarks.get(jid)
            if bookmark is not None:
                self._bookmarks.pop(bookmark, None)

        else:
            new_bookmark = properties.pubsub_event.data
            self._bookmarks[new_bookmark.jid] = properties.pubsub_event.data

        self._act_on_changed_bookmarks(old_bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def pass_disco(self, info):
        if app.config.get('dev_force_bookmark_2'):
            self._log.info('Forcing Bookmark 2 usage, '
                           'without server conversion support: %s', info.jid)
            self._conversion_2 = True

        elif nbxmpp.NS_BOOKMARKS_COMPAT in info.features:
            self._conversion_2 = True
            self._log.info('Discovered Bookmarks Conversion 2: %s', info.jid)

        elif nbxmpp.NS_BOOKMARK_CONVERSION in info.features:
            self._conversion = True
            self._log.info('Discovered Bookmarks Conversion: %s', info.jid)

    def _act_on_changed_bookmarks(
            self, old_bookmarks: Dict[str, BookmarkData]) -> None:

        new_bookmarks = self._convert_to_set(self._bookmarks)
        old_bookmarks = self._convert_to_set(old_bookmarks)
        changed = new_bookmarks - old_bookmarks
        if not changed:
            return

        join = [jid for jid, autojoin in changed if autojoin]
        bookmarks = []
        for jid in join:
            self._log.info('Schedule autojoin in 10s for: %s', jid)
            bookmarks.append(self._bookmarks.get(jid))
        # If another client creates a MUC, the MUC is locked until the
        # configuration is finished. Give the user some time to finish
        # the configuration.
        timeout_id = GLib.timeout_add_seconds(
            10, self._join_with_timeout, bookmarks)
        self._join_timeouts.append(timeout_id)

        # TODO: leave mucs
        # leave = [jid for jid, autojoin in changed if not autojoin]

    @staticmethod
    def _convert_to_set(
            bookmarks: Dict[str, BookmarkData]) -> Set[Tuple[str, bool]]:

        set_ = set()
        for jid, bookmark in bookmarks.items():
            set_.add((jid, bookmark.autojoin))
        return set_

    @staticmethod
    def _convert_to_dict(bookmarks: List) -> Dict[str, BookmarkData]:
        _dict = {}  # type: Dict[str, BookmarkData]
        if bookmarks is None:
            return _dict

        for bookmark in bookmarks:
            _dict[bookmark.jid] = bookmark
        return _dict

    def get_bookmark(self, jid: Union[str, JID]) -> BookmarkData:
        return self._bookmarks.get(jid)

    def _pubsub_support(self) -> bool:
        return (self._con.get_module('PEP').supported and
                self._con.get_module('PubSub').publish_options)

    def request_bookmarks(self) -> None:
        if not app.account_is_available(self._account):
            return

        self._request_in_progress = True
        type_ = BookmarkStoreType.PRIVATE
        if self._pubsub_support():
            if self.conversion:
                type_ = BookmarkStoreType.PUBSUB_BOOKMARK_1
            if self._conversion_2:
                type_ = BookmarkStoreType.PUBSUB_BOOKMARK_2

        self._nbxmpp('Bookmarks').request_bookmarks(
            type_, callback=self._bookmarks_received)

    def _bookmarks_received(self, bookmarks: Any) -> None:
        if is_error_result(bookmarks):
            self._log.info(bookmarks)
            bookmarks = None

        self._request_in_progress = False
        self._bookmarks = self._convert_to_dict(bookmarks)
        self.auto_join_bookmarks()
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def store_difference(self, bookmarks: List) -> None:
        if self.using_bookmark_2:
            retract, add_or_modify = self._determine_changed_bookmarks(
                bookmarks, self._bookmarks)

            for bookmark in retract:
                self.remove(bookmark.jid)

            if add_or_modify:
                self.store_bookmarks(add_or_modify)
            self._bookmarks = self._convert_to_dict(bookmarks)

        else:
            self._bookmarks = self._convert_to_dict(bookmarks)
            self.store_bookmarks()

    def store_bookmarks(self, bookmarks: list = None) -> None:
        if not app.account_is_available(self._account):
            return

        type_ = BookmarkStoreType.PRIVATE
        if self._pubsub_support():
            if self.conversion:
                type_ = BookmarkStoreType.PUBSUB_BOOKMARK_1
            if self.conversion_2:
                type_ = BookmarkStoreType.PUBSUB_BOOKMARK_2

        if bookmarks is None:
            bookmarks = self._bookmarks.values()

        self._nbxmpp('Bookmarks').store_bookmarks(bookmarks, type_)

        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def store_bookmark(self, bookmark: BookmarkData) -> None:
        if not app.account_is_available(self._account):
            return

        if not self.using_bookmark_2:
            return

        self._nbxmpp('Bookmarks').store_bookmarks(
            [bookmark], BookmarkStoreType.PUBSUB_BOOKMARK_2)

        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def _join_with_timeout(self, bookmarks: List[Any]) -> None:
        self._join_timeouts.pop(0)
        self.auto_join_bookmarks(bookmarks)

    def auto_join_bookmarks(self,
                            bookmarks: Optional[List[Any]] = None) -> None:
        if bookmarks is None:
            bookmarks = self._bookmarks.values()

        for bookmark in bookmarks:
            if bookmark.autojoin:
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if bookmark.jid not in app.gc_connected[self._account]:
                    # we are not already connected
                    self._log.info('Autojoin Bookmark: %s', bookmark.jid)
                    minimize = app.config.get_per('rooms', bookmark.jid,
                                                  'minimize_on_autojoin', True)
                    app.interface.join_groupchat(self._account,
                                                 str(bookmark.jid),
                                                 minimized=minimize)

    def modify(self, jid: str, **kwargs: Dict[str, str]) -> None:
        bookmark = self._bookmarks.get(jid)
        if bookmark is None:
            return

        new_bookmark = bookmark._replace(**kwargs)
        if new_bookmark == bookmark:
            # No change happened
            return
        self._log.info('Modify bookmark: %s %s', jid, kwargs)
        self._bookmarks[jid] = new_bookmark

        if self.using_bookmark_2:
            self.store_bookmark(new_bookmark)
        else:
            self.store_bookmarks()

    def add_or_modify(self, jid: str, **kwargs: Dict[str, str]) -> None:
        bookmark = self._bookmarks.get(jid)
        if bookmark is not None:
            self.modify(jid, **kwargs)
            return

        new_bookmark = BookmarkData(jid=jid, **kwargs)
        self._bookmarks[jid] = new_bookmark
        self._log.info('Add new bookmark: %s', new_bookmark)

        if self.using_bookmark_2:
            self.store_bookmark(new_bookmark)
        else:
            self.store_bookmarks()

    def remove(self, jid: JID, publish: bool = True) -> None:
        removed = self._bookmarks.pop(jid, False)
        if not removed:
            return
        if publish:
            if self.using_bookmark_2:
                self._nbxmpp('Bookmarks').retract_bookmark(str(jid))
            else:
                self.store_bookmarks()

    @staticmethod
    def _determine_changed_bookmarks(
            new_bookmarks: List[BookmarkData],
            old_bookmarks: Dict[str, BookmarkData]) -> Tuple[
                List[BookmarkData], List[BookmarkData]]:

        new_jids = [bookmark.jid for bookmark in new_bookmarks]
        new_bookmarks = set(new_bookmarks)
        old_bookmarks = set(old_bookmarks.values())

        retract = []
        add_or_modify = []
        changed_bookmarks = new_bookmarks.symmetric_difference(old_bookmarks)

        for bookmark in changed_bookmarks:
            if bookmark.jid not in new_jids:
                retract.append(bookmark)
            if bookmark in new_bookmarks:
                add_or_modify.append(bookmark)
        return retract, add_or_modify

    def get_name_from_bookmark(self, jid: str) -> str:
        bookmark = self._bookmarks.get(jid)
        if bookmark is None:
            return ''
        return bookmark.name

    def is_bookmark(self, jid: str) -> bool:
        return jid in self._bookmarks

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
