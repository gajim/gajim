# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ErrorDialog

log = logging.getLogger('gajim.gtk.blocking_list')


class BlockingList(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Blocking List for %s') % account)

        self.connect_after('key-press-event', self._on_key_press)

        self.account = account
        self._client = app.get_client(account)
        self._prev_blocked_jids: set[JID] = set()

        self._ui = get_builder('blocking_list.ui')
        self.add(self._ui.blocking_grid)

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_grid_state(False)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._client.get_module('Blocking').request_blocking_list(
            callback=self._on_blocking_list_received)

    def _show_error(self, error: str) -> None:
        ErrorDialog(_('Error!'), error)

    def _on_blocking_list_received(self, task: Task) -> None:
        try:
            blocking_list = cast(set[JID], task.finish())
        except StanzaError as error:
            self._set_grid_state(False)
            self._show_error(to_user_string(error))
            return

        self._prev_blocked_jids = blocking_list
        self._ui.blocking_store.clear()

        for jid in blocking_list:
            self._ui.blocking_store.append([str(jid)])

        self._set_grid_state(True)
        self._disable_spinner()

    def _on_save_result(self, task: Task):
        try:
            task.finish()
        except StanzaError as error:
            self._show_error(to_user_string(error))
            self._disable_spinner()
            self._set_grid_state(True)
            return

        self.destroy()

    def _set_grid_state(self, state: bool) -> None:
        self._ui.blocking_grid.set_sensitive(state)

    def _jid_edited(self,
                    _renderer: Gtk.CellRendererText,
                    path: str,
                    new_text: str
                    ) -> None:
        iter_ = self._ui.blocking_store.get_iter(path)
        self._ui.blocking_store.set_value(iter_, 0, new_text)

    def _on_add(self, _button: Gtk.ToolButton) -> None:
        self._ui.blocking_store.append([''])

    def _on_remove(self, _button: Gtk.ToolButton) -> None:
        selected_rows = self._ui.block_view.get_selection().get_selected_rows()
        mod, paths = selected_rows
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.blocking_store.remove(iter_)

    def _on_save(self, _button: Gtk.Button) -> None:
        self._activate_spinner()
        self._set_grid_state(False)

        blocked_jids: set[JID] = set()
        for item in self._ui.blocking_store:
            if not item[0]:
                # No address/placeholder
                continue
            blocked_jids.add(JID.from_string(item[0].lower()))

        unblock_jids = self._prev_blocked_jids - blocked_jids
        block_jids = blocked_jids - self._prev_blocked_jids

        self._client.get_module('Blocking').update_blocking_list(
            block_jids, unblock_jids, callback=self._on_save_result)

    def _activate_spinner(self) -> None:
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self) -> None:
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
