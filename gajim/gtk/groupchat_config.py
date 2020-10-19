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

from nbxmpp.namespaces import Namespace
from nbxmpp.errors import StanzaError
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.const import MUCUser

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util import get_builder

log = logging.getLogger('gajim.gtk.groupchat_config')


class GroupchatConfig(Gtk.ApplicationWindow):
    def __init__(self, account, jid, own_affiliation, form=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Group Chat Configuration'))
        self._destroyed = False

        self.account = account
        self.jid = jid
        self._own_affiliation = own_affiliation

        self._ui = get_builder('groupchat_config.ui')
        self.add(self._ui.grid)

        # Activate Add button only for Admins and Owners
        if self._own_affiliation in ('admin', 'owner'):
            self._ui.add_button.set_sensitive(True)
            self._ui.add_button.set_tooltip_text('')

        disco_info = app.storage.cache.get_last_disco_info(self.jid)
        visible = disco_info.supports(Namespace.REGISTER)
        self._ui.reserved_name_column.set_visible(visible)
        self._ui.info_button.set_sensitive(False)

        self._form = form
        self._affiliations = {}
        self._new_affiliations = {}

        con = app.connections[self.account]
        for affiliation in ('owner', 'admin', 'member', 'outcast'):
            con.get_module('MUC').get_affiliation(
                self.jid,
                affiliation,
                callback=self._on_affiliations_received,
                user_data=affiliation)

        if form is not None:
            self._ui.stack.set_visible_child_name('config')
            self._data_form_widget = DataFormWidget(form)
            self._data_form_widget.connect('is-valid', self._on_is_valid)
            self._data_form_widget.validate()
            self._ui.config_grid.add(self._data_form_widget)
        else:
            self._ui.stack.get_child_by_name('config').hide()
            self._ui.stack.get_child_by_name('config').set_no_show_all(True)
            self._ui.stack.set_visible_child_name('affiliation')

        self._ui.connect_signals(self)
        self.connect('delete-event', self._cancel)
        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self.show_all()
        self._ui.stack.notify('visible-child-name')

    def _on_is_valid(self, _widget, is_valid):
        self._ui.ok_button.set_sensitive(is_valid)

    def _get_current_treeview(self):
        page_name = self._ui.stack.get_visible_child_name()
        return getattr(self._ui, '%s_treeview' % page_name)

    def _on_add(self, *args):
        page_name = self._ui.stack.get_visible_child_name()
        if page_name == 'outcast':
            affiliation_edit, jid_edit = self._allowed_to_edit('outcast')
            text = None
            affiliation = 'outcast'
        else:
            affiliation_edit, jid_edit = self._allowed_to_edit('member')
            text = _('Member')
            affiliation = 'member'

        treeview = self._get_current_treeview()
        iter_ = treeview.get_model().append([None,
                                             None,
                                             None,
                                             affiliation,
                                             text,
                                             affiliation_edit,
                                             jid_edit])

        # Scroll to added row
        path = treeview.get_model().get_path(iter_)
        treeview.scroll_to_cell(path, None, False, 0, 0)
        treeview.get_selection().unselect_all()
        treeview.get_selection().select_path(path)

    def _on_remove(self, *args):
        treeview = self._get_current_treeview()
        model, paths = treeview.get_selection().get_selected_rows()

        owner_count = self._get_owner_count()
        references = []
        for path in paths:
            if model[path][MUCUser.AFFILIATION] == 'owner':
                if owner_count < 2:
                    # There must be at least one owner
                    ErrorDialog(_('Error'),
                                _('A Group Chat needs at least one Owner'))
                    return
                owner_count -= 1
            references.append(Gtk.TreeRowReference.new(model, path))

        for ref in references:
            iter_ = model.get_iter(ref.get_path())
            model.remove(iter_)

    def _on_jid_edited(self, _renderer, path, new_text):
        old_text = self._ui.affiliation_store[path][MUCUser.JID]
        if new_text == old_text:
            return

        if self._jid_exists(new_text):
            self._raise_error()
            return

        self._ui.affiliation_store[path][MUCUser.JID] = new_text

    def _on_outcast_jid_edited(self, _renderer, path, new_text):
        old_text = self._ui.outcast_store[path][MUCUser.JID]
        if new_text == old_text:
            return

        if self._jid_exists(new_text):
            self._raise_error()
            return

        self._ui.outcast_store[path][MUCUser.JID] = new_text
        self._ui.outcast_store[path][MUCUser.AFFILIATION] = 'outcast'

    def _on_nick_edited(self, _renderer, path, new_text):
        self._ui.affiliation_store[path][MUCUser.NICK] = new_text

    def _on_reason_edited(self, _renderer, path, new_text):
        self._ui.outcast_store[path][MUCUser.REASON] = new_text

    def _on_affiliation_changed(self, cell_renderer_combo,
                                path_string, new_iter):
        combo_store = cell_renderer_combo.get_property('model')
        affiliation_text = combo_store.get_value(new_iter, 0)
        affiliation = combo_store.get_value(new_iter, 1)

        store = self._ui.affiliation_treeview.get_model()

        store[path_string][MUCUser.AFFILIATION] = affiliation
        store[path_string][MUCUser.AFFILIATION_TEXT] = affiliation_text

    def _on_selection_changed(self, tree_selection):
        sensitive = bool(tree_selection.count_selected_rows())
        selected_affiliations = self._get_selected_affiliations(tree_selection)
        self._set_remove_button_state(sensitive, selected_affiliations)

    def _jid_exists(self, jid):
        stores = [self._ui.affiliation_store, self._ui.outcast_store]

        for store in stores:
            for row in store:
                if row[MUCUser.JID] == jid:
                    return True
        return False

    @staticmethod
    def _get_selected_affiliations(tree_selection):
        model, paths = tree_selection.get_selected_rows()
        selected_affiliations = set()
        for path in paths:
            selected_affiliations.add(model[path][MUCUser.AFFILIATION])
        return selected_affiliations

    def _on_switch_page(self, stack, _pspec):
        page_name = stack.get_visible_child_name()
        self._set_button_box_state(page_name)
        if page_name == 'config':
            return

        treeview = getattr(self._ui, '%s_treeview' % page_name)
        sensitive = bool(treeview.get_selection().count_selected_rows())

        selected_affiliations = self._get_selected_affiliations(
            treeview.get_selection())
        self._set_remove_button_state(sensitive, selected_affiliations)

    def _set_button_box_state(self, page_name):
        affiliation = self._own_affiliation in ('admin', 'owner')
        page = page_name != 'config'
        self._ui.treeview_buttonbox.set_visible(affiliation and page)
        self._ui.info_button.set_sensitive(page_name == 'outcast')

    def _set_remove_button_state(self, sensitive, selected_affiliations):
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

        if set(['owner', 'admin']).intersection(selected_affiliations):
            self._ui.remove_button.set_sensitive(False)
            self._ui.remove_button.set_tooltip_text(
                _('You are not allowed to modify the affiliation '
                  'of Admins and Owners'))
            return

        self._ui.remove_button.set_sensitive(True)

    def _get_owner_count(self):
        owner_count = 0
        for row in self._ui.affiliation_store:
            if row[MUCUser.AFFILIATION] == 'owner':
                owner_count += 1
        return owner_count

    def _allowed_to_edit(self, affiliation):
        if self._own_affiliation == 'owner':
            return True, True

        if self._own_affiliation == 'admin':
            if affiliation in ('admin', 'owner'):
                return False, False
            return False, True
        return False, False

    def _on_ok(self, *args):
        if self._own_affiliation in ('admin', 'owner'):
            self._set_affiliations()

        if self._form is not None and self._own_affiliation == 'owner':
            form = self._data_form_widget.get_submit_form()
            con = app.connections[self.account]
            con.get_module('MUC').set_config(self.jid, form)
        self.destroy()

    def _get_diff(self):
        stores = [self._ui.affiliation_store, self._ui.outcast_store]

        self._new_affiliations = {}
        for store in stores:
            for row in store:
                if not row[MUCUser.JID]:
                    # Ignore empty JID field
                    continue

                attr = 'nick'
                if row[MUCUser.AFFILIATION] == 'outcast':
                    attr = 'reason'

                self._new_affiliations[row[MUCUser.JID]] = {
                    'affiliation': row[MUCUser.AFFILIATION],
                    attr: row[MUCUser.NICK_OR_REASON]}

        old_jids = set(self._affiliations.keys())
        new_jids = set(self._new_affiliations.keys())
        remove = old_jids - new_jids
        add = new_jids - old_jids
        modified = new_jids - remove - add

        return add, remove, modified

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self._on_cancel()

    def _on_cancel(self, *args):
        self._cancel()
        self.destroy()

    def _cancel(self, *args):
        if self._form and self._own_affiliation == 'owner':
            con = app.connections[self.account]
            con.get_module('MUC').cancel_config(self.jid)

    def _on_destroy(self, *args):
        self._destroyed = True

    def _set_affiliations(self):
        add, remove, modified = self._get_diff()

        diff_dict = {}
        for jid in add:
            diff_dict[jid] = self._new_affiliations[jid]

        for jid in remove:
            diff_dict[jid] = {'affiliation': 'none'}

        for jid in modified:
            if self._new_affiliations[jid] == self._affiliations[jid]:
                # Not modified
                continue

            diff_dict[jid] = self._new_affiliations[jid]
            if self._new_affiliations[jid]['affiliation'] == 'outcast':
                # New affiliation is outcast, check if the reason changed.
                # In case the affiliation was 'admin', 'owner' or 'member'
                # before, there is no reason.
                new_reason = self._new_affiliations[jid]['reason']
                old_reason = self._affiliations[jid].get('reason')
                if new_reason == old_reason:
                    diff_dict[jid].pop('reason', None)

            else:
                # New affiliation is not outcast, check if the nick has changed.
                # In case the affiliation was 'outcast' there is no nick.
                new_nick = self._new_affiliations[jid]['nick']
                old_nick = self._affiliations[jid].get('nick')
                if new_nick == old_nick:
                    diff_dict[jid].pop('nick', None)

        if not diff_dict:
            # No changes were made
            return
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(self.jid, diff_dict)

    def _on_affiliations_received(self, task):
        affiliation = task.get_user_data()
        try:
            result = task.finish()
        except StanzaError as error:
            log.info('Error while requesting %s affiliations: %s',
                     affiliation, error.condition)
            return

        if affiliation == 'outcast':
            self._ui.stack.get_child_by_name('outcast').show()

        for jid, attrs in result.users.items():
            affiliation_edit, jid_edit = self._allowed_to_edit(affiliation)
            if affiliation == 'outcast':
                reason = attrs.get('reason')
                self._ui.outcast_store.append(
                    [str(jid),
                     reason,
                     None,
                     affiliation,
                     None,
                     affiliation_edit,
                     jid_edit])
                self._affiliations[jid] = {'affiliation': affiliation,
                                           'reason': reason}
            else:
                nick = attrs.get('nick')
                role = attrs.get('role')
                self._ui.affiliation_store.append(
                    [str(jid),
                     nick,
                     role,
                     affiliation,
                     _(affiliation.capitalize()),
                     affiliation_edit,
                     jid_edit])
                self._affiliations[jid] = {'affiliation': affiliation,
                                           'nick': nick}
                if role is not None:
                    self._ui.role_column.set_visible(True)

    @staticmethod
    def _raise_error():
        ErrorDialog(_('Error'),
                    _('An entry with this XMPP Address already exists'))
