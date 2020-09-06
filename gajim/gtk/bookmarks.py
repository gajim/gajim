# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from enum import IntEnum

from gi.repository import Gtk
from gi.repository import Gdk
from nbxmpp.structs import BookmarkData
from nbxmpp.protocol import validate_resourcepart
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import validate_jid
from gajim.common.i18n import _

from gajim.gtk.util import get_builder


log = logging.getLogger('gajim.gtk.bookmarks')


class Column(IntEnum):
    ADDRESS = 0
    NAME = 1
    NICK = 2
    PASSWORD = 3
    AUTOJOIN = 4


class Bookmarks(Gtk.ApplicationWindow):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Bookmarks for %s' % app.get_account_label(account)))
        self.set_default_size(700, 500)

        self.account = account

        self._ui = get_builder('bookmarks.ui')
        self.add(self._ui.bookmarks_grid)

        con = app.connections[account]
        for bookmark in con.get_module('Bookmarks').bookmarks:
            self._ui.bookmarks_store.append([str(bookmark.jid),
                                             bookmark.name,
                                             bookmark.nick,
                                             bookmark.password,
                                             bookmark.autojoin])

        self._ui.bookmarks_view.set_search_equal_func(self._search_func)

        self._ui.connect_signals(self)
        self.connect_after('key-press-event', self._on_key_press)

        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_selection_changed(self, selection):
        _, iter_ = selection.get_selected()
        self._ui.remove_button.set_sensitive(iter_ is not None)

    def _on_address_edited(self, _renderer, path, new_value):
        iter_ = self._ui.bookmarks_store.get_iter(path)
        if not new_value:
            return

        try:
            jid = validate_jid(new_value)
        except ValueError as error:
            log.warning('Invalid JID: %s (%s)', error, new_value)
            return

        if not jid.is_bare:
            log.warning('Invalid JID: only bare JIDs allowed (%s)', jid)
            return

        self._ui.bookmarks_store.set_value(iter_,
                                           Column.ADDRESS,
                                           new_value or None)

    def _on_name_edited(self, _renderer, path, new_value):
        iter_ = self._ui.bookmarks_store.get_iter(path)
        self._ui.bookmarks_store.set_value(iter_,
                                           Column.NAME,
                                           new_value or None)

    def _on_nick_edited(self, _renderer, path, new_value):
        iter_ = self._ui.bookmarks_store.get_iter(path)

        if new_value:
            try:
                validate_resourcepart(new_value)
            except ValueError as error:
                log.warning('Invalid nickname: %s', error)
                return

        self._ui.bookmarks_store.set_value(iter_,
                                           Column.NICK,
                                           new_value or None)

    def _on_password_edited(self, _renderer, path, new_value):
        iter_ = self._ui.bookmarks_store.get_iter(path)
        self._ui.bookmarks_store.set_value(iter_,
                                           Column.PASSWORD,
                                           new_value or None)

    def _on_autojoin_toggled(self, _renderer, path):
        iter_ = self._ui.bookmarks_store.get_iter(path)
        new_value = not self._ui.bookmarks_store[iter_][Column.AUTOJOIN]
        self._ui.bookmarks_store.set_value(iter_, Column.AUTOJOIN, new_value)

    def _on_add_clicked(self, _button):
        iter_ = self._ui.bookmarks_store.append([None, None, None, None, False])
        self._ui.bookmarks_view.get_selection().select_iter(iter_)
        path = self._ui.bookmarks_store.get_path(iter_)
        self._ui.bookmarks_view.scroll_to_cell(path, None, False)

    def _on_remove_clicked(self, _button):
        mod, paths = self._ui.bookmarks_view.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.bookmarks_store.remove(iter_)

    def _on_apply_clicked(self, _button):
        bookmarks = []
        for row in self._ui.bookmarks_store:
            if not row[Column.ADDRESS]:
                continue

            bookmark = BookmarkData(jid=JID.from_string(row[Column.ADDRESS]),
                                    name=row[Column.NAME],
                                    autojoin=row[Column.AUTOJOIN],
                                    password=row[Column.PASSWORD],
                                    nick=row[Column.NICK])
            bookmarks.append(bookmark)

        con = app.connections[self.account]
        con.get_module('Bookmarks').store_difference(bookmarks)
        self.destroy()

    @staticmethod
    def _search_func(model, _column, search_text, iter_):
        return search_text.lower() not in model[iter_][0].lower()
