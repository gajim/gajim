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

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.mam_preferences")


@Gtk.Template.from_string(string=get_ui_string("preferences/mam_preferences.ui"))
class MamPreferences(Gtk.Box, SignalManager):
    __gtype_name__ = "ArchivingPreferences"

    _default_combo: Gtk.ComboBox = Gtk.Template.Child()
    _pref_view: Gtk.TreeView = Gtk.Template.Child()
    _jid_cell_renderer: Gtk.CellRendererText = Gtk.Template.Child()
    _pref_toggle_cell_renderer: Gtk.CellRendererToggle = Gtk.Template.Child()
    _spinner: Adw.Spinner = Gtk.Template.Child()
    _add: Gtk.Button = Gtk.Template.Child()
    _remove: Gtk.Button = Gtk.Template.Child()
    _save_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self.account = account
        self._client = app.get_client(account)
        self._destroyed = False

        default_store = Gtk.ListStore(str, str)
        default_store.append([_("Always"), "always"])
        default_store.append([_("Contact List"), "roster"])
        default_store.append([_("Never"), "never"])
        self._default_combo.set_model(default_store)

        self._preferences_store = Gtk.ListStore(str, bool)
        self._pref_view.set_model(self._preferences_store)

        self._connect(self._jid_cell_renderer, "edited", self._jid_edited)
        self._connect(self._pref_toggle_cell_renderer, "toggled", self._pref_toggled)
        self._connect(self._add, "clicked", self._on_add)
        self._connect(self._remove, "clicked", self._on_remove)
        self._connect(self._save_button, "clicked", self._on_save)

        self._set_mam_box_state(False)
        self._activate_spinner()

        self._client.get_module("MAM").request_preferences(
            callback=self._mam_prefs_received
        )

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        self._destroyed = True
        app.check_finalize(self)

    @ensure_not_destroyed
    def _mam_prefs_received(self, task: Task) -> None:
        self._disable_spinner()
        self._set_mam_box_state(True)

        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            log.error("Failed to store archiving preferences: %s", error)
            return

        self._default_combo.set_active_id(result.default)

        self._preferences_store.clear()
        for jid in result.always:
            self._preferences_store.append([str(jid), True])

        for jid in result.never:
            self._preferences_store.append([str(jid), False])

    @ensure_not_destroyed
    def _mam_prefs_saved(self, task: Task) -> None:
        self._disable_spinner()
        self._set_mam_box_state(True)

        try:
            task.finish()
        except StanzaError as error:
            log.error("Failed to store archiving preferences: %s", error)
            return

    def _set_mam_box_state(self, state: bool) -> None:
        self.set_sensitive(state)

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
        rows = self._pref_view.get_selection().get_selected_rows()
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
        default = self._default_combo.get_active_id()
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
