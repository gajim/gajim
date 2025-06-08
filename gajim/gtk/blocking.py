# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import logging

from gi.repository import Adw
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.blocking_list")


class BlockingList(GajimAppWindow):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="BlockingList",
            title=_("Blocking List for %s")
            % app.settings.get_account_setting(account, "account_label"),
        )

        self.account = account
        self._client = app.get_client(account)
        self._prev_blocked_jids: set[JID] = set()

        self._ui = get_builder("blocking_list.ui")
        self.set_child(self._ui.blocking_grid)

        self._blocking_store = Gtk.ListStore(str)
        self._ui.block_view.set_model(self._blocking_store)

        self._spinner = Adw.Spinner(valign=Gtk.Align.CENTER)
        self._ui.overlay.add_overlay(self._spinner)

        self._set_grid_state(False)

        self._activate_spinner()

        self._connect(self._ui.jid_cell_renderer, "edited", self._jid_edited)
        self._connect(self._ui.add_button, "clicked", self._on_add)
        self._connect(self._ui.remove_button, "clicked", self._on_remove)
        self._connect(self._ui.save_button, "clicked", self._on_save)

        self._client.get_module("Blocking").request_blocking_list(
            callback=self._on_blocking_list_received
        )

    def _show_error(self, error: str) -> None:
        SimpleDialog(_("Error"), error)

    def _on_blocking_list_received(self, task: Task) -> None:
        try:
            blocking_list = cast(set[JID], task.finish())
        except StanzaError as error:
            self._set_grid_state(False)
            self._show_error(to_user_string(error))
            return

        self._prev_blocked_jids = blocking_list
        self._blocking_store.clear()

        for jid in blocking_list:
            self._blocking_store.append([str(jid)])

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

        self.close()

    def _set_grid_state(self, state: bool) -> None:
        self._ui.blocking_grid.set_sensitive(state)

    def _jid_edited(
        self, _renderer: Gtk.CellRendererText, path: str, new_text: str
    ) -> None:
        iter_ = self._blocking_store.get_iter(path)
        self._blocking_store.set_value(iter_, 0, new_text)

    def _on_add(self, _button: Any) -> None:
        self._blocking_store.append([""])

    def _on_remove(self, _button: Any) -> None:
        selected_rows = self._ui.block_view.get_selection().get_selected_rows()
        if selected_rows is None:
            return

        mod, paths = selected_rows
        for path in paths:
            iter_ = mod.get_iter(path)
            self._blocking_store.remove(iter_)

    def _on_save(self, _button: Gtk.Button) -> None:
        self._activate_spinner()
        self._set_grid_state(False)

        blocked_jids: set[JID] = set()
        for item in self._blocking_store:
            if not item[0]:
                # No address/placeholder
                continue
            blocked_jids.add(JID.from_string(item[0]))

        unblock_jids = self._prev_blocked_jids - blocked_jids
        block_jids = blocked_jids - self._prev_blocked_jids

        self._client.get_module("Blocking").update_blocking_list(
            block_jids, unblock_jids, callback=self._on_save_result  # type: ignore
        )

    def _activate_spinner(self) -> None:
        self._spinner.set_visible(True)

    def _disable_spinner(self) -> None:
        self._spinner.set_visible(False)

    def _cleanup(self) -> None:
        pass
