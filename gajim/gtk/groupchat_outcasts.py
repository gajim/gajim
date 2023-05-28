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

from __future__ import annotations

from typing import cast
from typing import NamedTuple

import logging
from enum import IntEnum

from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.structs import AffiliationResult
from nbxmpp.task import Task

from gajim.common.client import Client
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.apply_button_box import ApplyButtonBox
from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ErrorDialog

log = logging.getLogger('gajim.gtk.groupchat_outcasts')


class OutcastRow(NamedTuple):
    jid: str
    reason: str | None


class Column(IntEnum):
    JID = 0
    REASON = 1


class GroupchatOutcasts(Gtk.Box):
    def __init__(self, client: Client, contact: GroupchatContact) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self._client = client
        self._contact = contact
        self._current_rows: set[OutcastRow] = set()

        self_contact = contact.get_self()
        assert self_contact is not None
        self._own_affiliation = self_contact.affiliation.value

        self._ui = get_builder('groupchat_outcast.ui')

        self._treeview = self._ui.outcast_treeview
        self._store = self._ui.outcast_store

        self.add(self._ui.main_box)
        self._apply_button = ApplyButtonBox(_('Apply'),
                                            on_clicked=self._on_apply)
        self._ui.button_box.pack_end(self._apply_button, False, False, 0)

        if self._own_affiliation in ('admin', 'owner'):
            self._ui.add_button.set_sensitive(True)
            self._ui.add_button.set_tooltip_text('')

        self._ui.connect_signals(self)

        self._client.get_module('MUC').get_affiliation(
            self._contact.jid,
            'outcast',
            callback=self._on_outcasts_received)

    def _on_apply(self, _button: Gtk.Button) -> None:
        self._begin_progress()
        self._set_outcasts()

    def _begin_progress(self) -> None:
        self._ui.outcast_scrolled.set_sensitive(False)
        self._ui.add_remove_button_box.set_sensitive(False)

    def _end_progress(self) -> None:
        self._ui.outcast_scrolled.set_sensitive(True)
        self._ui.add_remove_button_box.set_sensitive(True)

    def _on_add(self, _button: Gtk.Button) -> None:
        iter_ = self._store.append([None, None, True])

        path = self._store.get_path(iter_)
        self._treeview.scroll_to_cell(path, None, False, 0, 0)
        self._treeview.get_selection().unselect_all()
        self._treeview.get_selection().select_path(path)

        self._update_apply_button_state()

    def _on_remove(self, _button: Gtk.Button) -> None:
        _model, paths = self._treeview.get_selection().get_selected_rows()

        references: list[Gtk.TreeRowReference] = []
        for path in paths:
            references.append(Gtk.TreeRowReference.new(self._store, path))

        for ref in references:
            path = ref.get_path()
            assert path is not None
            iter_ = self._store.get_iter(path)
            self._store.remove(iter_)

        self._update_apply_button_state()

    def _on_jid_edited(self,
                       _renderer: Gtk.CellRendererText,
                       path: str,
                       new_text: str) -> None:

        old_text = self._store[path][Column.JID]
        if new_text == old_text:
            return

        if self._jid_exists(new_text):
            self._raise_error()
            return

        self._store[path][Column.JID] = new_text
        self._update_apply_button_state()

    def _on_reason_edited(self,
                          _renderer: Gtk.CellRendererText,
                          path: str,
                          new_text: str) -> None:
        self._store[path][Column.REASON] = new_text or None
        self._update_apply_button_state()

    def _on_selection_changed(self, tree_selection: Gtk.TreeSelection) -> None:
        sensitive = bool(tree_selection.count_selected_rows())
        self._set_remove_button_state(sensitive)

    def _jid_exists(self, jid: str) -> bool:
        return any(row[Column.JID] == jid for row in self._store)

    def _set_remove_button_state(self, sensitive: bool) -> None:
        value = self._own_affiliation in ('admin', 'owner')
        self._ui.remove_button.set_sensitive(sensitive and value)

    def _update_apply_button_state(self):
        if self._own_affiliation not in ('admin', 'owner'):
            return
        new_rows = self._get_new_rows()
        self._apply_button.set_button_state(new_rows != self._current_rows)

    def _allowed_to_edit(self) -> bool:
        return self._own_affiliation in ('owner', 'admin')

    def _get_new_rows(self) -> set[OutcastRow]:
        rows: set[OutcastRow] = set()

        for row in self._store:
            if not row[Column.JID]:
                continue

            rows.add(OutcastRow(jid=row[Column.JID],
                                reason=row[Column.REASON]))
        return rows

    def _get_diff(self) -> tuple[list[OutcastRow], list[OutcastRow]]:

        new_rows = self._get_new_rows()

        before = {row.jid for row in self._current_rows}
        after = {row.jid for row in new_rows}

        removed = before - after
        removed_rows = [row for row in self._current_rows if row.jid in removed]

        added = after - before
        added_rows = [row for row in new_rows if row.jid in added]

        same = after - removed - added
        same_rows = {row for row in new_rows if row.jid in same}
        modified_rows = list(same_rows - self._current_rows)

        return removed_rows, added_rows + modified_rows

    def _set_outcasts(self) -> None:
        removed_rows, other_rows = self._get_diff()

        outcasts = {}
        for row in other_rows:
            outcasts[row.jid] = {'affiliation': 'outcast'}
            if row.reason:
                outcasts[row.jid]['reason'] = row.reason

        for row in removed_rows:
            outcasts[row.jid] = {'affiliation': 'none'}

        self._client.get_module('MUC').set_affiliation(
            self._contact.jid,
            outcasts,
            callback=self._on_affiliation_finished)

    def _on_affiliation_finished(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            log.info('Error while setting outcasts: %s', error)
            self._end_progress()
            self._apply_button.set_error(str(error))
            return

        self._current_rows = self._get_new_rows()
        self._end_progress()
        self._apply_button.set_success()

    def _on_outcasts_received(self, task: Task) -> None:
        try:
            result = cast(AffiliationResult, task.finish())
        except StanzaError as error:
            log.info('Error while requesting outcasts: %s', error.condition)
            return

        editable = self._allowed_to_edit()
        for jid, attrs in result.users.items():
            reason = attrs.get('reason')

            jid = str(jid)
            self._store.append([jid, reason, editable])

            self._current_rows.add(OutcastRow(jid=jid, reason=reason))

    @staticmethod
    def _raise_error() -> None:
        ErrorDialog(_('Error'),
                    _('An entry with this XMPP Address already exists'))
