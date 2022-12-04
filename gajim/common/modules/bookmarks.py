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

from __future__ import annotations

from typing import Any
from typing import Union
from typing import Optional
from typing import cast

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MessageProperties
from nbxmpp.task import Task

from gi.repository import GLib

from gajim.common import app
from gajim.common import types
from gajim.common.events import BookmarksReceived
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.util import event_node

NODE_MAX_NS = 'http://jabber.org/protocol/pubsub#config-node-max'


class Bookmarks(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._bookmark_event_received)
        self._register_pubsub_handler(self._bookmark_1_event_received)
        self._conversion = False
        self._compat = False
        self._compat_pep = False
        self._node_max = False
        self._bookmarks: types.BookmarksDict = {}
        self._join_timeouts: list[int] = []
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
    def bookmarks(self) -> list[BookmarkData]:
        return list(self._bookmarks.values())

    @property
    def pep_bookmarks_used(self) -> bool:
        return self._bookmark_module() == 'PEPBookmarks'

    @property
    def nativ_bookmarks_used(self) -> bool:
        return self._bookmark_module() == 'NativeBookmarks'

    @event_node(Namespace.BOOKMARKS)
    def _bookmark_event_received(self,
                                 _con: types.xmppClient,
                                 _stanza: Any,
                                 properties: MessageProperties
                                 ) -> None:
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
        app.ged.raise_event(
            BookmarksReceived(account=self._account))

    @event_node(Namespace.BOOKMARKS_1)
    def _bookmark_1_event_received(self,
                                   _con: types.xmppClient,
                                   _stanza: Any,
                                   properties: MessageProperties
                                   ) -> None:
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
        app.ged.raise_event(
            BookmarksReceived(account=self._account))

    def pass_disco(self, info: DiscoInfo) -> None:
        self._node_max = NODE_MAX_NS in info.features
        self._compat_pep = Namespace.BOOKMARKS_COMPAT_PEP in info.features
        self._compat = Namespace.BOOKMARKS_COMPAT in info.features
        self._conversion = Namespace.BOOKMARK_CONVERSION in info.features

    def _bookmark_module(self) -> str:
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
                                  current_bookmarks: types.BookmarksDict
                                  ) -> None:
        new_bookmarks = self._convert_to_set(self._bookmarks)
        old_bookmarks = self._convert_to_set(current_bookmarks)
        changed = new_bookmarks - old_bookmarks
        if not changed:
            return

        join = [jid for jid, autojoin in changed if autojoin]
        bookmarks: list[BookmarkData] = []
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
    def _convert_to_set(bookmarks: types.BookmarksDict
                        ) -> set[tuple[JID, bool]]:
        set_: set[tuple[JID, bool]] = set()
        for jid, bookmark in bookmarks.items():
            set_.add((jid, bookmark.autojoin))
        return set_

    @staticmethod
    def _convert_to_dict(bookmarks: Optional[list[BookmarkData]]
                         ) -> types.BookmarksDict:
        _dict: types.BookmarksDict = {}
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
            bookmarks: list[BookmarkData] = task.finish()
        except Exception as error:
            self._log.warning(error)
            bookmarks = []

        self._request_in_progress = False

        self._cleanup_bookmarks(bookmarks)
        self._bookmarks = self._convert_to_dict(bookmarks)
        self.auto_join_bookmarks(self.bookmarks)
        app.ged.raise_event(
            BookmarksReceived(account=self._account))

    def _cleanup_bookmarks(self, bookmarks: list[BookmarkData]) -> None:
        for bookmark in list(bookmarks):
            contact = self._client.get_module('Contacts').get_contact(
                bookmark.jid, groupchat=True)
            if not isinstance(contact, GroupchatContact):
                # The contact exists probably in the roster and is therefore
                # assumed to not be a MUC
                self._log.warning('Received bookmark but jid is not '
                                  'a groupchat: %s', bookmark.jid)
                bookmarks.remove(bookmark)

    def store_bookmarks(self, bookmarks: list[BookmarkData]) -> None:
        if not app.account_is_available(self._account):
            return

        if not self.nativ_bookmarks_used:
            bookmarks = self.bookmarks

        self._nbxmpp(self._bookmark_module()).store_bookmarks(bookmarks)

        app.ged.raise_event(
            BookmarksReceived(account=self._account))

    def _join_with_timeout(self, bookmarks: list[BookmarkData]) -> None:
        self._join_timeouts.pop(0)
        self.auto_join_bookmarks(bookmarks)

    def auto_join_bookmarks(self, bookmarks: list[BookmarkData]) -> None:
        for bookmark in bookmarks:
            if bookmark.autojoin:
                self._log.info('Autojoin Bookmark: %s', bookmark.jid)
                self._con.get_module('MUC').join(bookmark.jid)

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

    def _remove_timeouts(self) -> None:
        for _id in self._join_timeouts:
            GLib.source_remove(_id)

    def cleanup(self) -> None:
        self._remove_timeouts()
