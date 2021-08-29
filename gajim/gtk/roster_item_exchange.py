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

from gi.repository import Gtk

from gajim.common import app
from gajim.common import i18n
from gajim.common.i18n import _

from .dialogs import InformationDialog
from .util import get_builder


class RosterItemExchange(Gtk.ApplicationWindow):
    """
    Used when someone sends a Roster Item Exchange suggestion (XEP-0144)
    """
    def __init__(self, account, action, exchange_list, jid_from,
                 message_body=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Contact List Exchange'))

        self.account = account
        self._client = app.get_client(account)

        self._action = action
        self._exchange_list = exchange_list
        self._jid_from = jid_from

        self._ui = get_builder('roster_item_exchange.ui')
        self.add(self._ui.roster_item_exchange)

        # Set label depending on action
        contact = self._client.get_module('Contacts').get_contact(jid_from)
        if action == 'add':
            type_label = _('%(name)s (%(jid)s) would like to add some '
                           'contacts to your contact list.') % {
                               'name': contact.name,
                               'jid': self._jid_from}
        elif action == 'modify':
            type_label = _('%(name)s (%(jid)s) would like to modify some '
                           'contacts in your contact list.') % {
                               'name': contact.name,
                               'jid': self._jid_from}
        elif action == 'delete':
            type_label = _('%(name)s (%(jid)s) would like to delete some '
                           'contacts from your contact list.') % {
                               'name': contact.name,
                               'jid': self._jid_from}
        self._ui.type_label.set_text(type_label)

        if message_body:
            buffer_ = self._ui.body_textview.get_buffer()
            buffer_.set_text(message_body)
        else:
            self._ui.body_scrolledwindow.hide()

        # Treeview
        model = Gtk.ListStore(bool, str, str, str, str)
        self._ui.items_list_treeview.set_model(model)
        # Columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property('activatable', True)
        renderer1.connect('toggled', self._toggled)
        if self._action == 'add':
            title = _('Add')
        elif self._action == 'modify':
            title = _('Modify')
        elif self._action == 'delete':
            title = _('Delete')
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, title, renderer1, active=0)
        renderer2 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _('JID'), renderer2, text=1)
        renderer3 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _('Name'), renderer3, text=2)
        renderer4 = Gtk.CellRendererText()
        self._ui.items_list_treeview.insert_column_with_attributes(
            -1, _('Groups'), renderer4, text=3)

        # Init contacts
        self.model = self._ui.items_list_treeview.get_model()
        self.model.clear()

        if action == 'add':
            self._add()
        elif action == 'modify':
            self._modify()
        elif action == 'delete':
            self._delete()

        self._ui.connect_signals(self)

    def _toggled(self, cell, path):
        model = self._ui.items_list_treeview.get_model()
        iter_ = model.get_iter(path)
        model[iter_][0] = not cell.get_active()

    def _add(self):
        for jid in self._exchange_list:
            contact = self._client.get_module('Contacts').get_contact(jid)
            name = self._exchange_list[jid][0]
            groups = ''
            num_list = len(self._exchange_list[jid][1])
            current = 0
            for group in self._exchange_list[jid][1]:
                current += 1
                if current == num_list:
                    groups = groups + group
                else:
                    groups = groups + group + ', '
            if not contact.is_in_roster:
                self.show_all()
                iter_ = self.model.append()
                self.model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

        self._ui.accept_button.set_label(_('Add'))

    def _modify(self):
        for jid in self._exchange_list:
            is_right = True
            contact = self._client.get_module('Contacts').get_contact(jid)
            name = self._exchange_list[jid][0]
            groups = ''

            if name != contact.name:
                is_right = False
            num_list = len(self._exchange_list[jid][1])
            current = 0
            for group in self._exchange_list[jid][1]:
                current += 1
                if group not in contact.groups:
                    is_right = False
                if current == num_list:
                    groups = groups + group
                else:
                    groups = groups + group + ', '
            if not is_right and contact.is_in_roster:
                self.show_all()
                iter_ = self.model.append()
                self.model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

        self._ui.accept_button.set_label(_('Modify'))

    def _delete(self):
        for jid in self._exchange_list:
            contact = self._client.get_module('Contacts').get_contact(jid)
            name = self._exchange_list[jid][0]
            groups = ''
            num_list = len(self._exchange_list[jid][1])
            current = 0
            for group in self._exchange_list[jid][1]:
                current += 1
                if current == num_list:
                    groups = groups + group
                else:
                    groups = groups + group + ', '
            if contact.is_in_roster:
                self.show_all()
                iter_ = self.model.append()
                self.model.set(iter_, 0, True, 1, jid, 2, name, 3, groups)

        self._ui.accept_button.set_label(_('Delete'))

    def _on_accept_button_clicked(self, _widget):
        model = self._ui.items_list_treeview.get_model()
        iter_ = model.get_iter_first()
        if self._action == 'add':
            count = 0
            while iter_:
                if model[iter_][0]:
                    count += 1
                    # It is selected
                    contact = self._client.get_module('Contacts').get_contact(
                        self._jid_from)
                    message = _('%(name)s %(jid)s suggested me to add you to '
                                'my contact list.') % {
                                    'name': contact.name,
                                    'jid': self._jid_from}
                    # Keep same groups and same nickname
                    groups = model[iter_][3].split(', ')
                    if groups == ['']:
                        groups = []
                    jid = model[iter_][1]
                    if app.jid_is_transport(self._jid_from):
                        self._client.get_module('Presence').automatically_added.append(
                            jid)
                    # TODO:
                    app.interface.roster.req_sub(
                        self, jid, message, self.account, groups=groups,
                        nickname=model[iter_][2], auto_auth=True)
                iter_ = model.iter_next(iter_)
            InformationDialog(i18n.ngettext('Added %d contact',
                                            'Added %d contacts',
                                            count, count, count))
        elif self._action == 'modify':
            count = 0
            while iter_:
                if model[iter_][0]:
                    count += 1
                    # It is selected
                    jid = model[iter_][1]
                    # Keep same groups and same nickname
                    groups = model[iter_][3].split(', ')
                    if groups == ['']:
                        groups = []
                    # TODO:
                    for contact in app.contacts.get_contact(self.account, jid):
                        contact.name = model[iter_][2]
                    self._client.get_module('Roster').update_contact(
                        jid, model[iter_][2], groups)
                    self._client.get_module('Roster').draw_contact(
                        jid, self.account)
                    # Update opened chats
                    # TODO:
                    ctrl = app.window.get_control(self.account, jid)
                    if ctrl:
                        ctrl.update_ui()

                iter_ = model.iter_next(iter_)
        elif self._action == 'delete':
            count = 0
            while iter_:
                if model[iter_][0]:
                    count += 1
                    # It is selected
                    jid = model[iter_][1]
                    self._client.get_module('Presence').unsubscribe(jid)
                    # TODO:
                    app.interface.roster.remove_contact(jid, self.account)
                    app.contacts.remove_jid(self.account, jid)
                iter_ = model.iter_next(iter_)
            InformationDialog(i18n.ngettext('Removed %d contact',
                                            'Removed %d contacts',
                                            count, count, count))
        self.destroy()

    def _on_cancel_button_clicked(self, _widget):
        self.destroy()
