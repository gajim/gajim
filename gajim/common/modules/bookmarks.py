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
from typing import Set
from typing import Tuple
from typing import Union
from typing import Optional
from typing import cast

import functools

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData
from nbxmpp.task import Task
from gi.repository import GLib

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.types import BookmarksDict
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


NODE_MAX_NS = 'http://jabber.org/protocol/pubsub#config-node-max'


class Bookmarks(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._bookmark_event_received)
        self._register_pubsub_handler(self._bookmark_1_event_received)
        self._conversion = False
        self._compat = False
        self._compat_pep = False
        self._node_max = False
        self._bookmarks: BookmarksDict = {}
        self._join_timeouts: List[int] = []
        self._request_in_progress = True

    @property
    def conversion(self) -> bool:
        return self._conversion

    @property
    def compat(self) -> bool:
        return self._compat

    @property
    def compat_pep(self) -> bool:
        return self._compat_pep

    @property
    def bookmarks(self) -> List[BookmarkData]:
        return list(self._bookmarks.values())

    @property
    def pep_bookmarks_used(self) -> bool:
        return self._bookmark_module() == 'PEPBookmarks'

    @property
    def nativ_bookmarks_used(self) -> bool:
        return self._bookmark_module() == 'NativeBookmarks'

    @event_node(Namespace.BOOKMARKS)
    def _bookmark_event_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        if not properties.is_self_message:
            self._log.warning('%s has an open access bookmarks node',
                              properties.jid)
            return

        if not self.pep_bookmarks_used:
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

    @event_node(Namespace.BOOKMARKS_1)
    def _bookmark_1_event_received(self, _con, _stanza, properties):
        if not properties.is_self_message:
            self._log.warning('%s has an open access bookmarks node',
                              properties.jid)
            return

        if not self.nativ_bookmarks_used:
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
                self._bookmarks.pop(jid, None)

        else:
            new_bookmark: BookmarkData = properties.pubsub_event.data
            self._bookmarks[new_bookmark.jid] = new_bookmark

        self._act_on_changed_bookmarks(old_bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def pass_disco(self, info):
        self._node_max = NODE_MAX_NS in info.features
        self._compat_pep = Namespace.BOOKMARKS_COMPAT_PEP in info.features
        self._compat = Namespace.BOOKMARKS_COMPAT in info.features
        self._conversion = Namespace.BOOKMARK_CONVERSION in info.features

    @functools.lru_cache(maxsize=1)
    def _bookmark_module(self):
        if not self._con.get_module('PubSub').publish_options:
            return 'PrivateBookmarks'

        if app.settings.get('dev_force_bookmark_2'):
            return 'NativeBookmarks'

        if self._compat_pep and self._node_max:
            return 'NativeBookmarks'

        if self._conversion:
            return 'PEPBookmarks'
        return 'PrivateBookmarks'

    def _act_on_changed_bookmarks(self,
                                  current_bookmarks: BookmarksDict) -> None:
        new_bookmarks = self._convert_to_set(self._bookmarks)
        old_bookmarks = self._convert_to_set(current_bookmarks)
        changed = new_bookmarks - old_bookmarks
        if not changed:
            return

        join = [jid for jid, autojoin in changed if autojoin]
        bookmarks: List[BookmarkData] = []
        for jid in join:
            self._log.info('Schedule autojoin in 10s for: %s', jid)
            bookmarks.append(cast(BookmarkData, self._bookmarks.get(jid)))
        # If another client creates a MUC, the MUC is locked until the
        # configuration is finished. Give the user some time to finish
        # the configuration.
        timeout_id = GLib.timeout_add_seconds(
            10, self._join_with_timeout, bookmarks)
        self._join_timeouts.append(timeout_id)

        # TODO: leave mucs
        # leave = [jid for jid, autojoin in changed if not autojoin]

    @staticmethod
    def _convert_to_set(bookmarks: BookmarksDict) -> Set[Tuple[JID, bool]]:
        set_: Set[Tuple[JID, bool]] = set()
        for jid, bookmark in bookmarks.items():
            set_.add((jid, bookmark.autojoin))
        return set_

    @staticmethod
    def _convert_to_dict(
            bookmarks: Optional[List[BookmarkData]]) -> BookmarksDict:
        _dict: BookmarksDict = {}
        if not bookmarks:
            return _dict

        for bookmark in bookmarks:
            _dict[bookmark.jid] = bookmark
        return _dict

    def get_bookmark(self, jid: Union[str, JID]) -> Optional[BookmarkData]:
        return self._bookmarks.get(cast(JID, jid))

    def request_bookmarks(self) -> None:
        if not app.account_is_available(self._account):
            return

        self._request_in_progress = True
        self._nbxmpp(self._bookmark_module()).request_bookmarks(
            callback=self._bookmarks_received)

    def _bookmarks_received(self, task: Task) -> None:
        try:
            bookmarks: List[BookmarkData] = task.finish()
        except Exception as error:
            self._log.warning(error)
            bookmarks = []

        self._request_in_progress = False
        self._bookmarks = self._convert_to_dict(bookmarks)
        self.auto_join_bookmarks(self.bookmarks)
        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def store_bookmarks(self, bookmarks: List[BookmarkData]) -> None:
        if not app.account_is_available(self._account):
            return

        if not self.nativ_bookmarks_used:
            bookmarks = self.bookmarks

        self._nbxmpp(self._bookmark_module()).store_bookmarks(bookmarks)

        app.nec.push_incoming_event(
            NetworkEvent('bookmarks-received', account=self._account))

    def _join_with_timeout(self, bookmarks: List[BookmarkData]) -> None:
        self._join_timeouts.pop(0)
        self.auto_join_bookmarks(bookmarks)

    def auto_join_bookmarks(self, bookmarks: List[BookmarkData]) -> None:
        for bookmark in bookmarks:
            if bookmark.autojoin:
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if bookmark.jid not in app.gc_connected[self._account]:
                    # we are not already connected
                    self._log.info('Autojoin Bookmark: %s', bookmark.jid)
                    minimize = app.settings.get_group_chat_setting(
                        self._account,
                        bookmark.jid,
                        'minimize_on_autojoin')
                    app.interface.join_groupchat(self._account,
                                                 str(bookmark.jid),
                                                 minimized=minimize)

    def modify(self, jid: JID, **kwargs: Any) -> None:
        bookmark = self._bookmarks.get(jid)
        if bookmark is None:
            return

        new_bookmark = bookmark._replace(**kwargs)
        if new_bookmark == bookmark:
            # No change happened
            return
        self._log.info('Modify bookmark: %s %s', jid, kwargs)
        self._bookmarks[jid] = new_bookmark

        self.store_bookmarks([new_bookmark])

    def add_or_modify(self, jid: JID, **kwargs: Any) -> None:
        bookmark = self._bookmarks.get(jid)
        if bookmark is not None:
            self.modify(jid, **kwargs)
            return

        new_bookmark = BookmarkData(jid=jid, **kwargs)
        self._bookmarks[jid] = new_bookmark
        self._log.info('Add new bookmark: %s', new_bookmark)

        self.store_bookmarks([new_bookmark])

    def remove(self, jid: JID, publish: bool = True) -> None:
        removed = self._bookmarks.pop(jid, False)
        if not removed:
            return
        if publish:
            if self.nativ_bookmarks_used:
                self._nbxmpp('NativeBookmarks').retract_bookmark(jid)
            else:
                self.store_bookmarks(self.bookmarks)

    def get_name_from_bookmark(self, jid: Union[str, JID]) -> Optional[str]:
        bookmark = self._bookmarks.get(cast(JID, jid))
        if bookmark is None:
            return bookmark
        return bookmark.name

    def is_bookmark(self, jid: Union[str, JID]) -> bool:
        return jid in self._bookmarks

    def _remove_timeouts(self):
        for _id in self._join_timeouts:
            GLib.source_remove(_id)

    def cleanup(self):
        self._remove_timeouts()


def get_instance(*args, **kwargs):
    return Bookmarks(*args, **kwargs), 'Bookmarks'
