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

log = logging.getLogger('gajim.gtk.groupchat_affiliation')


class AffiliationRow(NamedTuple):
    jid: str
    nick: str | None
    affiliation: str


class Column(IntEnum):
    JID = 0
    NICK = 1
    AFFILIATION = 2
    AFFILIATION_TEXT = 3


class GroupchatAffiliation(Gtk.Box):
    def __init__(self, client: Client, contact: GroupchatContact) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self._client = client
        self._contact = contact
        self._current_rows: set[AffiliationRow] = set()

        self_contact = contact.get_self()
        assert self_contact is not None
        self._own_affiliation = self_contact.affiliation.value

        self._ui = get_builder('groupchat_affiliation.ui')

        self._treeview = self._ui.affiliation_treeview
        self._store = self._ui.affiliation_store

        self.add(self._ui.main_box)
        self._apply_button = ApplyButtonBox(_('Apply'),
                                            on_clicked=self._on_apply)
        self._ui.button_box.pack_end(self._apply_button, False, False, 0)

        if self._own_affiliation in ('admin', 'owner'):
            self._ui.add_button.set_sensitive(True)
            self._ui.add_button.set_tooltip_text('')

        self._ui.connect_signals(self)

        for affiliation in ('owner', 'admin', 'member'):
            self._client.get_module('MUC').get_affiliation(
                self._contact.jid,
                affiliation,
                callback=self._on_affiliations_received,
                user_data=affiliation)

    def _on_apply(self, _button: Gtk.Button) -> None:
        self._begin_progress()
        self._set_affiliations()

    def _begin_progress(self) -> None:
        self._ui.affiliation_scrolled.set_sensitive(False)
        self._ui.add_remove_button_box.set_sensitive(False)

    def _end_progress(self) -> None:
        self._ui.affiliation_scrolled.set_sensitive(True)
        self._ui.add_remove_button_box.set_sensitive(True)

    def _on_add(self, _button: Gtk.Button) -> None:
        affiliation_edit, jid_edit = self._allowed_to_edit('member')

        iter_ = self._store.append([None,
                                    None,
                                    'member',
                                    _('Member'),
                                    affiliation_edit,
                                    jid_edit])

        path = self._store.get_path(iter_)
        self._treeview.scroll_to_cell(path, None, False, 0, 0)
        self._treeview.get_selection().unselect_all()
        self._treeview.get_selection().select_path(path)

        self._update_apply_button_state()

    def _on_remove(self, _button: Gtk.Button) -> None:
        _model, paths = self._treeview.get_selection().get_selected_rows()

        owner_count = len([row for row in self._store
                           if row[Column.AFFILIATION] == 'owner'])
        references: list[Gtk.TreeRowReference] = []
        for path in paths:
            if self._store[path][Column.AFFILIATION] == 'owner':
                if owner_count < 2:
                    # There must be at least one owner
                    ErrorDialog(_('Error'),
                                _('A Group Chat needs at least one Owner'))
                    return
                owner_count -= 1
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

    def _on_nick_edited(self,
                        _renderer: Gtk.CellRendererText,
                        path: str,
                        new_text: str) -> None:
        self._store[path][Column.NICK] = new_text or None
        self._update_apply_button_state()

    def _on_affiliation_changed(self,
                                cell_renderer_combo: Gtk.CellRendererCombo,
                                path_string: str,
                                new_iter: Gtk.TreeIter) -> None:

        combo_store = cell_renderer_combo.get_property('model')
        affiliation_text = combo_store.get_value(new_iter, 0)
        affiliation = combo_store.get_value(new_iter, 1)

        self._store[path_string][Column.AFFILIATION] = affiliation
        self._store[path_string][Column.AFFILIATION_TEXT] = affiliation_text
        self._update_apply_button_state()

    def _on_selection_changed(self, tree_selection: Gtk.TreeSelection) -> None:
        sensitive = bool(tree_selection.count_selected_rows())
        selected_affiliations = self._get_selected_affiliations(tree_selection)
        self._set_remove_button_state(sensitive, selected_affiliations)

    def _jid_exists(self, jid: str) -> bool:
        return any(row[Column.JID] == jid for row in self._store)

    @staticmethod
    def _get_selected_affiliations(tree_selection: Gtk.TreeSelection
                                   ) -> set[str]:
        model, paths = tree_selection.get_selected_rows()
        selected_affiliations: set[str] = set()
        for path in paths:
            selected_affiliations.add(model[path][Column.AFFILIATION])
        return selected_affiliations

    def _set_remove_button_state(self,
                                 sensitive: bool,
                                 selected_affiliations: set[str]) -> None:

        if self._own_affiliation not in ('admin', 'owner'):
            self._ui.remove_button.set_sensitive(False)
            return

        self._ui.remove_button.set_tooltip_text('')

        if not sensitive:
            self._ui.remove_button.set_sensitive(False)
            return

        if self._own_affiliation == 'owner':
            self._ui.remove_button.set_sensitive(True)
            return

        if {'owner', 'admin'}.intersection(selected_affiliations):
            self._ui.remove_button.set_sensitive(False)
            self._ui.remove_button.set_tooltip_text(
                _('You are not allowed to modify the affiliation '
                  'of Admins and Owners'))
            return

        self._ui.remove_button.set_sensitive(True)

    def _update_apply_button_state(self):
        if self._own_affiliation not in ('admin', 'owner'):
            return
        new_rows = self._get_new_rows()
        self._apply_button.set_button_state(new_rows != self._current_rows)

    def _allowed_to_edit(self, affiliation: str) -> tuple[bool, bool]:
        if self._own_affiliation == 'owner':
            return True, True

        if self._own_affiliation == 'admin':
            if affiliation in ('admin', 'owner'):
                return False, False
            return False, True
        return False, False

    def _get_new_rows(self) -> set[AffiliationRow]:
        rows: set[AffiliationRow] = set()

        for row in self._store:
            if not row[Column.JID]:
                continue

            rows.add(AffiliationRow(jid=row[Column.JID],
                                    nick=row[Column.NICK],
                                    affiliation=row[Column.AFFILIATION]))
        return rows

    def _get_diff(self) -> list[AffiliationRow]:

        new_rows = self._get_new_rows()

        before = {row.jid for row in self._current_rows}
        after = {row.jid for row in new_rows}

        removed = before - after
        removed_rows = [row for row in self._current_rows if row.jid in removed]
        removed_rows = [row._replace(affiliation='none')
                        for row in removed_rows]

        added = after - before
        added_rows = [row for row in new_rows if row.jid in added]

        same = after - removed - added
        same_rows = {row for row in new_rows if row.jid in same}
        modified_rows = list(same_rows - self._current_rows)

        return removed_rows + added_rows + modified_rows

    def _set_affiliations(self) -> None:
        diff_rows = self._get_diff()

        affiliations = {}
        for row in diff_rows:
            affiliations[row.jid] = {'affiliation': row.affiliation}
            if row.nick:
                affiliations[row.jid]['nick'] = row.nick

        self._client.get_module('MUC').set_affiliation(
            self._contact.jid,
            affiliations,
            callback=self._on_affiliation_finished)

    def _on_affiliation_finished(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            log.info('Error while setting affiliations: %s', error)
            self._end_progress()
            self._apply_button.set_error(str(error))
            return

        self._current_rows = self._get_new_rows()
        self._end_progress()
        self._apply_button.set_success()

    def _on_affiliations_received(self, task: Task) -> None:
        affiliation = task.get_user_data()
        try:
            result = cast(AffiliationResult, task.finish())
        except StanzaError as error:
            log.info('Error while requesting %s affiliations: %s',
                     affiliation, error.condition)
            return

        for jid, attrs in result.users.items():
            affiliation_edit, jid_edit = self._allowed_to_edit(affiliation)
            nick = attrs.get('nick')

            jid = str(jid)
            self._store.append([jid,
                                nick,
                                affiliation,
                                _(affiliation.capitalize()),
                                affiliation_edit,
                                jid_edit])

            self._current_rows.add(AffiliationRow(jid=jid,
                                                  nick=nick,
                                                  affiliation=affiliation))

    @staticmethod
    def _raise_error() -> None:
        ErrorDialog(_('Error'),
                    _('An entry with this XMPP Address already exists'))
