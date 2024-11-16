# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.bookmarks")


class Bookmarks(GajimAppWindow):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="Bookmarks",
            title=_("Bookmarks for %s") % app.get_account_label(account),
            default_width=700,
            default_height=500,
        )

        self.account = account

        self._ui = get_builder("bookmarks.ui")
        self.set_child(self._ui.bookmarks_grid)

        client = app.get_client(account)
        for bookmark in client.get_module("Bookmarks").bookmarks:
            self._ui.bookmarks_store.append(
                [
                    str(bookmark.jid),
                    bookmark.name,
                    bookmark.nick,
                    bookmark.password,
                    bookmark.autojoin,
                ]
            )

        self._ui.bookmarks_view.set_search_equal_func(self._search_func)

    @staticmethod
    def _search_func(
        model: Gtk.TreeModel, _column: int, search_text: str, iter_: Gtk.TreeIter
    ):
        return search_text.lower() not in model[iter_][0].lower()

    def _cleanup(self):
        pass
