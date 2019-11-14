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

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.common.i18n import _

from .service_registration import ServiceRegistration
from .dialogs import ErrorDialog
from .util import get_builder
from .util import EventHelper
from .util import open_window


class AddNewContactWindow(Gtk.ApplicationWindow, EventHelper):

    uid_labels = {'jabber': _('XMPP Address'),
                  'gadu-gadu': _('GG Number'),
                  'icq': _('ICQ Number')}

    def __init__(self, account=None, contact_jid=None, user_nick=None, group=None):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_resizable(False)
        self.set_title(_('Add Contact'))

        self.connect_after('key-press-event', self._on_key_press)

        self.account = account
        self.adding_jid = False

        if contact_jid is not None:
            contact_jid = app.get_jid_without_resource(contact_jid)

        # fill accounts with active accounts
        accounts = app.get_enabled_accounts_with_labels()

        if not accounts:
            return

        if not account:
            self.account = accounts[0][0]

        self._ui = get_builder('add_new_contact_window.ui')
        self.add(self._ui.add_contact_box)
        self._ui.connect_signals(self)

        self.subscription_table = [
            self._ui.uid_label, self._ui.uid_entry,
            self._ui.show_contact_info_button,
            self._ui.nickname_label, self._ui.nickname_entry,
            self._ui.group_label, self._ui.group_comboboxentry
        ]

        self._ui.add_button.grab_default()

        self.agents = {'jabber': []}
        self.gateway_prompt = {}
        # types to which we are not subscribed but account has an agent for it
        self.available_types = []
        for acct in accounts:
            for j in app.contacts.get_jid_list(acct[0]):
                if app.jid_is_transport(j):
                    type_ = app.get_transport_name_from_jid(j, False)
                    if not type_:
                        continue
                    if type_ in self.agents:
                        self.agents[type_].append(j)
                    else:
                        self.agents[type_] = [j]
                    self.gateway_prompt[j] = {'desc': None, 'prompt': None}
        # Now add the one to which we can register
        for acct in accounts:
            for type_ in app.connections[acct[0]].available_transports:
                if type_ in self.agents:
                    continue
                self.agents[type_] = []
                for jid_ in app.connections[acct[0]].available_transports[type_]:
                    if jid_ not in self.agents[type_]:
                        self.agents[type_].append(jid_)
                        self.gateway_prompt[jid_] = {'desc': None,
                                                     'prompt': None}
                self.available_types.append(type_)

        uf_type = {'jabber': 'XMPP', 'gadu-gadu': 'Gadu Gadu', 'icq': 'ICQ'}
        # Jabber as first
        liststore = self._ui.protocol_combobox.get_model()
        liststore.append(['XMPP', 'xmpp', 'jabber'])
        for type_, services in self.agents.items():
            if type_ == 'jabber':
                continue
            if type_ in uf_type:
                liststore.append([uf_type[type_], type_ + '-online', type_])
            else:
                liststore.append([type_, type_ + '-online', type_])

            if account:
                for service in services:
                    con = app.connections[account]
                    con.get_module('Gateway').request_gateway_prompt(service)
        self._ui.protocol_combobox.set_active(0)
        self._ui.auto_authorize_checkbutton.show()

        if contact_jid:
            self.jid_escaped = True
            type_ = app.get_transport_name_from_jid(contact_jid)
            if not type_:
                type_ = 'jabber'
            if type_ == 'jabber':
                self._ui.uid_entry.set_text(contact_jid)
                transport = None
            else:
                uid, transport = app.get_name_and_server_from_jid(contact_jid)
                self._ui.uid_entry.set_text(uid.replace('%', '@', 1))

            self._ui.show_contact_info_button.set_sensitive(True)

            # set protocol_combobox
            model = self._ui.protocol_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][2] == type_:
                    self._ui.protocol_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1

            # set protocol_jid_combobox
            self._ui.protocol_jid_combobox.set_active(0)
            model = self._ui.protocol_jid_combobox.get_model()
            iter_ = model.get_iter_first()
            i = 0
            while iter_:
                if model[iter_][0] == transport:
                    self._ui.protocol_jid_combobox.set_active(i)
                    break
                iter_ = model.iter_next(iter_)
                i += 1
            if user_nick:
                self._ui.nickname_entry.set_text(user_nick)
            self._ui.nickname_entry.grab_focus()
        else:
            self.jid_escaped = False
            self._ui.uid_entry.grab_focus()
        group_names = []
        for acct in accounts:
            for g in app.groups[acct[0]].keys():
                if g not in helpers.special_groups and g not in group_names:
                    group_names.append(g)
        group_names.sort()
        i = 0
        for g in group_names:
            self._ui.group_comboboxentry.append_text(g)
            if group == g:
                self._ui.group_comboboxentry.set_active(i)
            i += 1

        if len(accounts) > 1:
            liststore = self._ui.account_combobox.get_model()
            for acc in accounts:
                liststore.append(acc)

            self._ui.account_combobox.set_active_id(self.account)
            self._ui.account_label.show()
            self._ui.account_combobox.show()

        if len(self.agents) > 1:
            self._ui.protocol_label.show()
            self._ui.protocol_combobox.show()

        if self.account:
            message_buffer = self._ui.message_textview.get_buffer()
            msg = helpers.from_one_line(helpers.get_subscription_request_msg(
                self.account))
            message_buffer.set_text(msg)

        self._ui.uid_entry.connect('changed', self.on_uid_entry_changed)
        self.show_all()

        self.register_events([
            ('gateway-prompt-received', ged.GUI1, self._nec_gateway_prompt_received),
            ('presence-received', ged.GUI1, self._nec_presence_received),
        ])

    def on_uid_entry_changed(self, widget):
        is_empty = bool(not self._ui.uid_entry.get_text() == '')
        self._ui.show_contact_info_button.set_sensitive(is_empty)

    def on_show_contact_info_button_clicked(self, _widget):
        """
        Ask for vCard
        """
        jid = self._ui.uid_entry.get_text().strip()
        client = app.get_client(self.account)
        contact = client.get_module('Contacts').get_contact(jid)
        open_window('ContactInfo', account=self.account, contact=contact)

    def on_register_button_clicked(self, widget):
        model = self._ui.protocol_jid_combobox.get_model()
        row = self._ui.protocol_jid_combobox.get_active()
        jid = model[row][0]
        ServiceRegistration(self.account, jid)

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def on_cancel_button_clicked(self, widget):
        """
        When Cancel button is clicked
        """
        self.destroy()

    def on_message_textbuffer_changed(self, widget):
        self._ui.save_message_revealer.show()
        self._ui.save_message_revealer.set_reveal_child(True)

    def on_add_button_clicked(self, widget):
        """
        When Subscribe button is clicked
        """
        jid = self._ui.uid_entry.get_text().strip()
        if not jid:
            ErrorDialog(
                _('%s Missing') % self._ui.uid_label.get_text(),
                (_('You must supply the %s of the new contact.') %
                    self._ui.uid_label.get_text())
            )
            return

        model = self._ui.protocol_combobox.get_model()
        row = self._ui.protocol_combobox.get_active_iter()
        type_ = model[row][2]
        if type_ != 'jabber':
            model = self._ui.protocol_jid_combobox.get_model()
            row = self._ui.protocol_jid_combobox.get_active()
            transport = model[row][0]
            if self.account and not self.jid_escaped:
                self.adding_jid = (jid, transport, type_)
                con = app.connections[self.account]
                con.get_module('Gateway').request_gateway_prompt(transport, jid)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        else:
            self._add_jid(jid, type_)

    def _add_jid(self, jid, type_):
        # check if jid is conform to RFC and stringprep it
        try:
            jid = helpers.parse_jid(jid)
        except helpers.InvalidFormat as s:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, str(s))
            return

        # No resource in jid
        if jid.find('/') >= 0:
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('The user ID must not contain a resource.'))
            return

        if jid == app.get_jid_from_account(self.account):
            pritext = _('Invalid User ID')
            ErrorDialog(pritext, _('You cannot add yourself to your contact list.'))
            return

        if not app.account_is_available(self.account):
            ErrorDialog(
                _('Account Offline'),
                _('Your account must be online to add new contacts.')
            )
            return

        nickname = self._ui.nickname_entry.get_text() or ''
        # get value of account combobox, if account was not specified
        if not self.account:
            model = self._ui.account_combobox.get_model()
            index = self._ui.account_combobox.get_active()
            self.account = model[index][1]

        # Check if jid is already in roster
        if jid in app.contacts.get_jid_list(self.account):
            c = app.contacts.get_first_contact_from_jid(self.account, jid)
            if _('Not in contact list') not in c.groups and c.sub in ('both', 'to'):
                ErrorDialog(
                    _('Contact Already in Contact List'),
                    _('This contact is already in your contact list.'))
                return

        if type_ == 'jabber':
            message_buffer = self._ui.message_textview.get_buffer()
            start_iter = message_buffer.get_start_iter()
            end_iter = message_buffer.get_end_iter()
            message = message_buffer.get_text(start_iter, end_iter, True)
            if self._ui.save_message_checkbutton.get_active():
                msg = helpers.to_one_line(message)
                app.settings.set_account_setting(self.account,
                                                 'subscription_request_msg',
                                                 msg)
        else:
            message = ''
        group = self._ui.group_comboboxentry.get_child().get_text()
        groups = []
        if group:
            groups = [group]
        auto_auth = self._ui.auto_authorize_checkbutton.get_active()

        client = app.get_client(self.account)
        client.get_module('Presence').subscribe(jid,
                                                message,
                                                nickname,
                                                groups=groups,
                                                auto_auth=auto_auth)

        self.destroy()

    def on_account_combobox_changed(self, widget):
        account = widget.get_active_id()
        message_buffer = self._ui.message_textview.get_buffer()
        message_buffer.set_text(helpers.get_subscription_request_msg(account))
        self.account = account

    def on_protocol_jid_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        if not iter_:
            return
        jid_ = model[iter_][0]
        model = self._ui.protocol_combobox.get_model()
        iter_ = self._ui.protocol_combobox.get_active_iter()
        type_ = model[iter_][2]

        desc = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            desc = self.gateway_prompt[jid_]['desc']

        if desc:
            self._ui.prompt_label.set_markup(desc)
            self._ui.prompt_label.show()
        else:
            self._ui.prompt_label.hide()

        prompt = None
        if self.agents[type_] and jid_ in self.gateway_prompt:
            prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self._ui.uid_label.set_text(prompt)

    def on_protocol_combobox_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()
        type_ = model[iter_][2]
        model = self._ui.protocol_jid_combobox.get_model()
        model.clear()
        if self.agents[type_]:
            for jid_ in self.agents[type_]:
                model.append([jid_])
            self._ui.protocol_jid_combobox.set_active(0)
        desc = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                desc = self.gateway_prompt[jid_]['desc']

        if desc:
            self._ui.prompt_label.set_markup(desc)
            self._ui.prompt_label.show()
        else:
            self._ui.prompt_label.hide()

        if len(self.agents[type_]) > 1:
            self._ui.protocol_jid_combobox.show()
        else:
            self._ui.protocol_jid_combobox.hide()
        prompt = None
        if self.agents[type_]:
            jid_ = self.agents[type_][0]
            if jid_ in self.gateway_prompt:
                prompt = self.gateway_prompt[jid_]['prompt']
        if not prompt:
            if type_ in self.uid_labels:
                prompt = self.uid_labels[type_]
            else:
                prompt = _('User ID:')
        self._ui.uid_label.set_text(prompt)

        if type_ == 'jabber':
            self._ui.message_scrolledwindow.show()
            self._ui.save_message_checkbutton.show()
        else:
            self._ui.message_scrolledwindow.hide()
            self._ui.save_message_checkbutton.hide()
        if type_ in self.available_types:
            self._ui.register_hbox.show()
            self._ui.auto_authorize_checkbutton.hide()
            self._ui.connected_label.hide()
            self._subscription_table_hide()
            self._ui.add_button.set_sensitive(False)
        else:
            self._ui.register_hbox.hide()
            if type_ != 'jabber':
                model = self._ui.protocol_jid_combobox.get_model()
                row = self._ui.protocol_jid_combobox.get_active()
                jid = model[row][0]
                contact = app.contacts.get_first_contact_from_jid(
                    self.account, jid)
                if contact is None or contact.show in ('offline', 'error'):
                    self._subscription_table_hide()
                    self._ui.connected_label.show()
                    self._ui.add_button.set_sensitive(False)
                    self._ui.auto_authorize_checkbutton.hide()
                    return
            self._subscription_table_show()
            self._ui.auto_authorize_checkbutton.show()
            self._ui.connected_label.hide()
            self._ui.add_button.set_sensitive(True)

    def transport_signed_in(self, jid):
        model = self._ui.protocol_jid_combobox.get_model()
        row = self._ui.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self._ui.register_hbox.hide()
            self._ui.connected_label.hide()
            self._subscription_table_show()
            self._ui.auto_authorize_checkbutton.show()
            self._ui.add_button.set_sensitive(True)

    def transport_signed_out(self, jid):
        model = self._ui.protocol_jid_combobox.get_model()
        row = self._ui.protocol_jid_combobox.get_active()
        _jid = model[row][0]
        if _jid == jid:
            self._subscription_table_hide()
            self._ui.auto_authorize_checkbutton.hide()
            self._ui.connected_label.show()
            self._ui.add_button.set_sensitive(False)

    def _nec_presence_received(self, obj):
        if app.jid_is_transport(obj.jid):
            if obj.old_show == 0 and obj.new_show > 1:
                self.transport_signed_in(obj.jid)
            elif obj.old_show > 1 and obj.new_show == 0:
                self.transport_signed_out(obj.jid)

    def _nec_gateway_prompt_received(self, obj):
        if self.adding_jid:
            jid, transport, type_ = self.adding_jid
            if obj.stanza.getError():
                ErrorDialog(
                    _('Error while adding transport contact'),
                    _('This error occurred while adding a contact for transport '
                      '%(transport)s:\n\n%(error)s') % {
                        'transport': transport,
                        'error': obj.stanza.getErrorMsg()})
                return
            if obj.prompt_jid:
                self._add_jid(obj.prompt_jid, type_)
            else:
                jid = jid.replace('@', '%') + '@' + transport
                self._add_jid(jid, type_)
        elif obj.jid in self.gateway_prompt:
            if obj.desc:
                self.gateway_prompt[obj.jid]['desc'] = obj.desc
            if obj.prompt:
                self.gateway_prompt[obj.jid]['prompt'] = obj.prompt

    def _subscription_table_hide(self):
        for widget in self.subscription_table:
            widget.hide()

    def _subscription_table_show(self):
        for widget in self.subscription_table:
            widget.show()
