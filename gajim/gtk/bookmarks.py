# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder

log = logging.getLogger('gajim.gtk.bookmarks')


class Bookmarks(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Bookmarks for %s') % app.get_account_label(account))
        self.set_default_size(700, 500)

        self.account = account

        self._ui = get_builder('bookmarks.ui')
        self.add(self._ui.bookmarks_grid)

        client = app.get_client(account)
        for bookmark in client.get_module('Bookmarks').bookmarks:
            self._ui.bookmarks_store.append([str(bookmark.jid),
                                             bookmark.name,
                                             bookmark.nick,
                                             bookmark.password,
                                             bookmark.autojoin])

        self._ui.bookmarks_view.set_search_equal_func(self._search_func)

        self._ui.connect_signals(self)
        self.connect_after('key-press-event', self._on_key_press)

        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    @staticmethod
    def _search_func(model: Gtk.TreeModel,
                     _column: int,
                     search_text: str,
                     iter_: Gtk.TreeIter):
        return search_text.lower() not in model[iter_][0].lower()
