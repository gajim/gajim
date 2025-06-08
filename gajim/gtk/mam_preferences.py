# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Adw
from gi.repository import Gtk
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.builder import get_builder
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.mam_preferences")


class MamPreferences(GajimAppWindow):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="MamPreferences",
            title=_("Archiving Preferences for %s") % account,
        )

        self.account = account
        self._client = app.get_client(account)
        self._destroyed = False

        self._ui = get_builder("mam_preferences.ui")
        self.set_child(self._ui.mam_box)

        default_store = Gtk.ListStore(str, str)
        default_store.append([_("Always"), "always"])
        default_store.append([_("Contact List"), "roster"])
        default_store.append([_("Never"), "never"])
        self._ui.default_combo.set_model(default_store)

        self._preferences_store = Gtk.ListStore(str, bool)
        self._ui.pref_view.set_model(self._preferences_store)

        self._connect(self._ui.jid_cell_renderer, "edited", self._jid_edited)
        self._connect(self._ui.pref_toggle_cell_renderer, "toggled", self._pref_toggled)
        self._connect(self._ui.add, "clicked", self._on_add)
        self._connect(self._ui.remove, "clicked", self._on_remove)
        self._connect(self._ui.save_button, "clicked", self._on_save)

        self._spinner = Adw.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_mam_box_state(False)
        self._activate_spinner()

        self._client.get_module("MAM").request_preferences(
            callback=self._mam_prefs_received
        )

    def _cleanup(self) -> None:
        self._destroyed = True

    @ensure_not_destroyed
    def _mam_prefs_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._on_error(error.get_text())
            return

        self._disable_spinner()
        self._set_mam_box_state(True)

        self._ui.default_combo.set_active_id(result.default)

        self._preferences_store.clear()
        for jid in result.always:
            self._preferences_store.append([str(jid), True])

        for jid in result.never:
            self._preferences_store.append([str(jid), False])

    @ensure_not_destroyed
    def _mam_prefs_saved(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            self._on_error(error.get_text())
            return

        self._disable_spinner()

        InformationAlertDialog(
            _("Archiving Preferences Saved"),
            _("Your archiving preferences have successfully been saved."),
            callback=self.close,
        )

    def _on_error(self, error: str) -> None:
        self._disable_spinner()

        InformationAlertDialog(
            _("Archiving Preferences Error"), _("Error received: {}").format(error)
        )

        self._set_mam_box_state(True)

    def _set_mam_box_state(self, state: bool) -> None:
        self._ui.mam_box.set_sensitive(state)

    def _jid_edited(
        self, _renderer: Gtk.CellRendererText, path: str, new_text: str
    ) -> None:

        iter_ = self._preferences_store.get_iter(path)
        self._preferences_store.set_value(iter_, 0, new_text)

    def _pref_toggled(self, _renderer: Gtk.CellRendererToggle, path: str):

        iter_ = self._preferences_store.get_iter(path)
        current_value = self._preferences_store[iter_][1]
        self._preferences_store.set_value(iter_, 1, not current_value)

    def _on_add(self, _button: Gtk.Button) -> None:
        self._preferences_store.append(["", False])

    def _on_remove(self, _button: Gtk.Button) -> None:
        rows = self._ui.pref_view.get_selection().get_selected_rows()
        assert rows is not None
        mod, paths = rows
        for path in paths:
            iter_ = mod.get_iter(path)
            self._preferences_store.remove(iter_)

    def _on_save(self, _button: Gtk.Button) -> None:
        self._activate_spinner()
        self._set_mam_box_state(False)
        always: list[str] = []
        never: list[str] = []
        default = self._ui.default_combo.get_active_id()
        for item in self._preferences_store:
            jid, archive = item
            if archive:
                always.append(jid)
            else:
                never.append(jid)
        self._client.get_module("MAM").set_preferences(
            default, always, never, callback=self._mam_prefs_saved
        )

    def _activate_spinner(self) -> None:
        self._spinner.set_visible(True)

    def _disable_spinner(self) -> None:
        self._spinner.set_visible(False)
