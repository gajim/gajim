# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import InformationDialog
from gajim.gtk.util import EventHelper

log = logging.getLogger('gajim.gtk.mam_preferences')


class MamPreferences(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Archiving Preferences for %s') % account)

        self.connect_after('key-press-event', self._on_key_press)

        self.account = account
        self._client = app.get_client(account)
        self._destroyed = False

        self._ui = get_builder('mam_preferences.ui')
        self.add(self._ui.mam_box)

        self._spinner = Gtk.Spinner()
        self._ui.overlay.add_overlay(self._spinner)

        self._set_mam_box_state(False)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)
        self.show_all()

        self._activate_spinner()

        self._client.get_module('MAM').request_preferences(
            callback=self._mam_prefs_received)

    def _on_destroy(self, widget: MamPreferences) -> None:
        self._destroyed = True

    def _mam_prefs_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._on_error(error.get_text())
            return

        self._disable_spinner()
        self._set_mam_box_state(True)

        self._ui.default_combo.set_active_id(result.default)
        self._ui.preferences_store.clear()
        for jid in result.always:
            self._ui.preferences_store.append([str(jid), True])

        for jid in result.never:
            self._ui.preferences_store.append([str(jid), False])

    def _mam_prefs_saved(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            self._on_error(error.get_text())
            return

        self._disable_spinner()

        def _on_ok():
            self.destroy()

        ConfirmationDialog(
            _('Archiving Preferences'),
            _('Archiving Preferences Saved'),
            _('Your archiving preferences have successfully been saved.'),
            [DialogButton.make('OK',
                               callback=_on_ok)]).show()

    def _on_error(self, error: str) -> None:
        self._disable_spinner()

        InformationDialog(_('Archiving Preferences Error'),
                          _('Error received: {}').format(error))

        self._set_mam_box_state(True)

    def _set_mam_box_state(self, state: bool) -> None:
        self._ui.mam_box.set_sensitive(state)

    def _jid_edited(self,
                    _renderer: Gtk.CellRendererText,
                    path: str,
                    new_text: str) -> None:

        iter_ = self._ui.preferences_store.get_iter(path)
        self._ui.preferences_store.set_value(iter_, 0, new_text)

    def _pref_toggled(self,
                      _renderer: Gtk.CellRendererToggle,
                      path: str):

        iter_ = self._ui.preferences_store.get_iter(path)
        current_value = self._ui.preferences_store[iter_][1]
        self._ui.preferences_store.set_value(iter_, 1, not current_value)

    def _on_add(self, _button: Gtk.Button) -> None:
        self._ui.preferences_store.append(['', False])

    def _on_remove(self, _button: Gtk.Button) -> None:
        rows = self._ui.pref_view.get_selection().get_selected_rows()
        assert rows is not None
        mod, paths = rows
        for path in paths:
            iter_ = mod.get_iter(path)
            self._ui.preferences_store.remove(iter_)

    def _on_save(self, _button: Gtk.Button) -> None:
        self._activate_spinner()
        self._set_mam_box_state(False)
        always: list[str] = []
        never: list[str] = []
        default = self._ui.default_combo.get_active_id()
        for item in self._ui.preferences_store:
            jid, archive = item
            if archive:
                always.append(jid)
            else:
                never.append(jid)
        self._client.get_module('MAM').set_preferences(
            default, always, never, callback=self._mam_prefs_saved)

    def _activate_spinner(self) -> None:
        self._spinner.show()
        self._spinner.start()

    def _disable_spinner(self) -> None:
        self._spinner.hide()
        self._spinner.stop()

    def _on_key_press(self,
                      _widget: MamPreferences,
                      event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
