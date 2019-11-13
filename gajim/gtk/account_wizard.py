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

import os

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from nbxmpp.modules import dataforms

from gajim.common import app
from gajim.common import ged
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common import connection
from gajim.common.i18n import _
from gajim.common.nec import EventHelper

from gajim import dataforms_widget
from gajim import gui_menu_builder

from gajim.gtk.util import get_builder
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.proxies import ManageProxies
from gajim.gtk.dataform import FakeDataFormWidget


class AccountCreationWizard(EventHelper):
    def __init__(self):
        EventHelper.__init__(self)
        self.xml = get_builder('account_creation_wizard_window.ui')
        self.window = self.xml.get_object('account_creation_wizard_window')
        active_window = app.app.get_active_window()
        self.window.set_transient_for(active_window)

        # Connect events from comboboxtext_entry
        server_comboboxtext = self.xml.get_object('server_comboboxtext')
        entry = self.xml.get_object('server_comboboxtext_entry')
        entry.connect('key_press_event',
                      self.on_entry_key_press_event, server_comboboxtext)

        server_comboboxtext1 = self.xml.get_object('server_comboboxtext1')

        self.update_proxy_list()

        # parse servers.json
        server_file_path = os.path.join(
            configpaths.get('DATA'), 'other', 'servers.json')
        servers = helpers.load_json(server_file_path, 'servers', [])

        servers_model = self.xml.get_object('server_liststore')
        for server in servers:
            servers_model.append((server,))

        server_comboboxtext.set_model(servers_model)
        server_comboboxtext1.set_model(servers_model)

        # Generic widgets
        self.notebook = self.xml.get_object('notebook')
        self.cancel_button = self.xml.get_object('cancel_button')
        self.back_button = self.xml.get_object('back_button')
        self.forward_button = self.xml.get_object('forward_button')
        self.finish_button = self.xml.get_object('finish_button')
        self.advanced_button = self.xml.get_object('advanced_button')
        self.finish_label = self.xml.get_object('finish_label')
        self.go_online_checkbutton = self.xml.get_object(
            'go_online_checkbutton')
        self.show_vcard_checkbutton = self.xml.get_object(
            'show_vcard_checkbutton')
        self.progressbar = self.xml.get_object('progressbar')

        # some vars
        self.update_progressbar_timeout_id = None

        self.notebook.set_current_page(0)
        self.xml.connect_signals(self)
        self.window.show_all()

        self.register_events([
            ('new-account-connected', ged.GUI1, self._nec_new_acc_connected),
            ('new-account-not-connected', ged.GUI1, self._nec_new_acc_not_connected),
            ('account-created', ged.GUI1, self._nec_acc_is_ok),
            ('account-not-created', ged.GUI1, self._nec_acc_is_not_ok),
        ])

    def on_wizard_window_destroy(self, widget):
        page = self.notebook.get_current_page()
        if page in (4, 5) and self.account in app.connections:
            # connection instance is saved in app.connections and we canceled
            # the addition of the account
            del app.connections[self.account]
            if self.account in app.config.get_per('accounts'):
                app.config.del_per('accounts', self.account)
        self.unregister_events()
        del app.interface.instances['account_creation_wizard']

    def on_save_password_checkbutton_toggled(self, widget):
        self.xml.get_object('password_entry').grab_focus()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_back_button_clicked(self, widget):
        cur_page = self.notebook.get_current_page()
        self.forward_button.set_sensitive(True)
        if cur_page in (1, 2):
            self.notebook.set_current_page(0)
            self.back_button.set_sensitive(False)
        elif cur_page == 3:
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
            self.notebook.set_current_page(2)  # show server page
        elif cur_page == 4:
            if self.account in app.connections:
                del app.connections[self.account]
                if self.account in app.config.get_per('accounts'):
                    app.config.del_per('accounts', self.account)
            self.notebook.set_current_page(2)
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
        elif cur_page == 6:  # finish page
            self.forward_button.show()
            if self.modify:
                self.notebook.set_current_page(1)  # Go to parameters page
            else:
                self.notebook.set_current_page(2)  # Go to server page

    def on_anonymous_checkbutton1_toggled(self, widget):
        active = widget.get_active()
        self.xml.get_object('username_entry').set_sensitive(not active)
        self.xml.get_object('password_entry').set_sensitive(not active)
        self.xml.get_object('save_password_checkbutton').set_sensitive(
            not active)

    def show_finish_page(self):
        self.cancel_button.hide()
        self.back_button.hide()
        self.forward_button.hide()
        if self.modify:
            finish_text = '<big><b>%s</b></big>\n\n%s' % (
                _('Account has been added successfully'),
                _('You can set advanced account options by pressing the '
                  'Advanced button, or later by choosing the Accounts menu item '
                  'under the Edit menu from the main window.'))
        else:
            finish_text = '<big><b>%s</b></big>\n\n%s' % (
                _('Your new account has been created successfully'),
                _('You can set advanced account options by pressing the '
                  'Advanced button, or later by choosing the Accounts menu item '
                  'under the Edit menu from the main window.'))
        self.finish_label.set_markup(finish_text)
        self.finish_button.show()
        self.finish_button.set_property('has-default', True)
        self.advanced_button.show()
        self.go_online_checkbutton.show()
        img = self.xml.get_object('finish_image')
        if self.modify:
            img.set_from_icon_name('emblem-ok-symbolic', Gtk.IconSize.DIALOG)
            img.get_style_context().add_class('success-color')
        else:
            img.set_from_icon_name('org.gajim.Gajim', Gtk.IconSize.DIALOG)
        self.show_vcard_checkbutton.set_active(not self.modify)
        self.notebook.set_current_page(6) # show finish page

    def on_forward_button_clicked(self, widget):
        cur_page = self.notebook.get_current_page()

        if cur_page == 0:
            widget = self.xml.get_object('use_existing_account_radiobutton')
            if widget.get_active():
                self.modify = True
                self.notebook.set_current_page(1)
            else:
                self.modify = False
                self.notebook.set_current_page(2)
            self.back_button.set_sensitive(True)
            return

        if cur_page == 1:
            # We are adding an existing account
            anonymous = self.xml.get_object('anonymous_checkbutton1').\
                get_active()
            username = self.xml.get_object('username_entry').get_text().strip()
            if not username and not anonymous:
                pritext = _('Invalid username')
                sectext = _(
                    'You must provide a username to configure this account.')
                ErrorDialog(pritext, sectext)
                return
            server = self.xml.get_object('server_comboboxtext_entry').\
                get_text().strip()
            savepass = self.xml.get_object('save_password_checkbutton').\
                get_active()
            password = self.xml.get_object('password_entry').get_text()

            if anonymous:
                jid = ''
            else:
                jid = username + '@'
            jid += server
            # check if jid is conform to RFC and stringprep it
            try:
                jid = helpers.parse_jid(jid)
            except helpers.InvalidFormat as s:
                pritext = _('Invalid XMPP Address')
                ErrorDialog(pritext, str(s))
                return

            self.account = server
            i = 1
            while self.account in app.config.get_per('accounts'):
                self.account = server + str(i)
                i += 1

            username, server = app.get_name_and_server_from_jid(jid)
            if self.xml.get_object('anonymous_checkbutton1').get_active():
                self.save_account('', server, False, '', anonymous=True)
            else:
                self.save_account(username, server, savepass, password)
            self.show_finish_page()
        elif cur_page == 2:
            # We are creating a new account
            server = self.xml.get_object('server_comboboxtext_entry1').\
                get_text()

            if not server:
                ErrorDialog(
                    _('Invalid server'),
                    _('Please provide a server on which you want to register.'))
                return
            self.account = server
            i = 1
            while self.account in app.config.get_per('accounts'):
                self.account = server + str(i)
                i += 1

            config = self.get_config('', server, '', '')
            # Get advanced options
            proxies_combobox = self.xml.get_object('proxies_combobox')
            active = proxies_combobox.get_active()
            proxy = proxies_combobox.get_model()[active][0]
            if proxy == _('None'):
                proxy = ''
            config['proxy'] = proxy

            config['use_custom_host'] = self.xml.get_object(
                'custom_host_port_checkbutton').get_active()
            custom_port = self.xml.get_object('custom_port_entry').get_text()
            try:
                custom_port = int(custom_port)
            except Exception:
                ErrorDialog(
                    _('Invalid entry'),
                    _('Custom port must be a port number.'))
                return
            config['custom_port'] = custom_port
            config['custom_host'] = self.xml.get_object(
                'custom_host_entry').get_text()

            if self.xml.get_object('anonymous_checkbutton2').get_active():
                self.modify = True
                self.save_account('', server, False, '', anonymous=True)
                self.show_finish_page()
            else:
                self.notebook.set_current_page(5)  # show creating page
                self.back_button.hide()
                self.forward_button.hide()
                self.update_progressbar_timeout_id = GLib.timeout_add(
                    100, self.update_progressbar)
                # Get form from serveur
                con = connection.Connection(self.account)
                app.connections[self.account] = con
                con.new_account(self.account, config)
        elif cur_page == 3:
            checked = self.xml.get_object('ssl_checkbutton').get_active()
            if checked:
                hostname = app.connections[self.account].new_account_info[
                    'hostname']
                # Check if cert is already in file
                certs = ''
                my_ca_certs = configpaths.get('MY_CACERTS')
                if os.path.isfile(my_ca_certs):
                    with open(my_ca_certs) as f:
                        certs = f.read()
                if self.ssl_cert in certs:
                    ErrorDialog(
                        _('Certificate Already in File'),
                        _('This certificate is already in file %s, so it\'s '
                          'not added again.') % my_ca_certs)
                else:
                    with open(my_ca_certs, 'a') as f:
                        f.write(hostname + '\n')
                        f.write(self.ssl_cert + '\n\n')
                    app.connections[self.account].new_account_info[
                        'ssl_fingerprint_sha1'] = self.ssl_fingerprint_sha1
                    app.connections[self.account].new_account_info[
                        'ssl_fingerprint_sha256'] = self.ssl_fingerprint_sha256
            self.notebook.set_current_page(4)  # show fom page
        elif cur_page == 4:
            if self.is_form:
                form = self.data_form_widget.data_form
            else:
                form = self.data_form_widget.get_submit_form()
            app.connections[self.account].send_new_account_infos(
                form, self.is_form)
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
            self.xml.get_object('progressbar_label').set_markup(
                '<b>Account is being created</b>\n\nPlease wait…')
            self.notebook.set_current_page(5)  # show creating page
            self.back_button.hide()
            self.forward_button.hide()
            self.update_progressbar_timeout_id = GLib.timeout_add(
                100, self.update_progressbar)

    def update_proxy_list(self):
        proxies_combobox = self.xml.get_object('proxies_combobox')
        model = Gtk.ListStore(str)
        proxies_combobox.set_model(model)
        proxies = app.config.get_per('proxies')
        proxies.insert(0, _('None'))
        for proxy in proxies:
            model.append([proxy])
        proxies_combobox.set_active(0)

    def on_manage_proxies_button_clicked(self, _widget):
        window = app.get_app_window(ManageProxies)
        if window is None:
            ManageProxies()
        else:
            window.present()

    def on_custom_host_port_checkbutton_toggled(self, widget):
        self.xml.get_object('custom_host_hbox').set_sensitive(
            widget.get_active())

    def update_progressbar(self):
        self.progressbar.pulse()
        return True  # loop forever

    def _nec_new_acc_connected(self, obj):
        """
        Connection to server succeded, present the form to the user
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        self.back_button.show()
        self.forward_button.show()
        self.is_form = obj.is_form
        empty_config = True
        if obj.is_form:
            dataform = dataforms.extend_form(node=obj.config)
            self.data_form_widget = dataforms_widget.DataFormWidget()
            self.data_form_widget.selectable = True
            self.data_form_widget.set_data_form(dataform)
            empty_config = False
        else:
            self.data_form_widget = FakeDataFormWidget(obj.config)
            for field in obj.config:
                if field in ('key', 'instructions', 'x', 'registered'):
                    continue
                empty_config = False
                break
        self.data_form_widget.show_all()
        self.xml.get_object('form_vbox').pack_start(
            self.data_form_widget, True, True, 0)
        if empty_config:
            self.forward_button.set_sensitive(False)
            self.notebook.set_current_page(4)  # show form page
            return
        self.ssl_fingerprint_sha1 = obj.ssl_fingerprint_sha1
        self.ssl_fingerprint_sha256 = obj.ssl_fingerprint_sha256
        self.ssl_cert = obj.ssl_cert
        if obj.ssl_msg:
            # An SSL warning occured, show it
            hostname = app.connections[self.account].new_account_info[
                'hostname']
            self.xml.get_object('ssl_label').set_markup(_(
                '<b>Security Warning</b>'
                '\n\nThe authenticity of the %(hostname)s SSL certificate could'
                ' be invalid.\nSSL Error: %(error)s\n'
                'Do you still want to connect to this server?') % {
                'hostname': hostname, 'error': obj.ssl_msg})
            if obj.errnum in (18, 27):
                text = _(
                    'Add this certificate to the list of trusted '
                    'certificates.\nSHA-1 fingerprint of the certificate:\n'
                    '%(sha1)s\nSHA-256 fingerprint of the certificate:\n'
                    '%(sha256)s') % {'sha1': obj.ssl_fingerprint_sha1,
                                     'sha256': obj.ssl_fingerprint_sha256}
                self.xml.get_object('ssl_checkbutton').set_label(text)
            else:
                self.xml.get_object('ssl_checkbutton').set_no_show_all(True)
                self.xml.get_object('ssl_checkbutton').hide()
            self.notebook.set_current_page(3)  # show SSL page
        else:
            self.notebook.set_current_page(4)  # show form page

    def _nec_new_acc_not_connected(self, obj):
        """
        Account creation failed: connection to server failed
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        if self.account not in app.connections:
            return
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        del app.connections[self.account]
        if self.account in app.config.get_per('accounts'):
            app.config.del_per('accounts', self.account)
        self.back_button.show()
        self.cancel_button.show()
        self.go_online_checkbutton.hide()
        self.show_vcard_checkbutton.hide()
        img = self.xml.get_object('finish_image')
        img.set_from_icon_name("dialog-error", Gtk.IconSize.DIALOG)
        finish_text = '<big><b>%s</b></big>\n\n%s' % (
            _('An error occurred during account creation'), obj.reason)
        self.finish_label.set_markup(finish_text)
        self.notebook.set_current_page(6)  # show finish page

    def _nec_acc_is_ok(self, obj):
        """
        Account creation succeeded
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        self.create_vars(obj.account_info)
        self.show_finish_page()

        # Register plugin modules after successful registration
        # Some plugins need the registered JID to function properly
        app.plugin_manager.register_modules_for_account(obj.conn)

        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)

    def _nec_acc_is_not_ok(self, obj):
        """
        Account creation failed
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        self.back_button.show()
        self.cancel_button.show()
        self.go_online_checkbutton.hide()
        self.show_vcard_checkbutton.hide()
        del app.connections[self.account]
        if self.account in app.config.get_per('accounts'):
            app.config.del_per('accounts', self.account)
        img = self.xml.get_object('finish_image')
        img.set_from_icon_name("dialog-error", Gtk.IconSize.DIALOG)
        finish_text = '<big><b>%s</b></big>\n\n%s' % (_(
            'An error occurred during account creation'), obj.reason)
        self.finish_label.set_markup(finish_text)
        self.notebook.set_current_page(6)  # show finish page

        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)

    def on_advanced_button_clicked(self, widget):
        from gajim.gtk.accounts import AccountsWindow
        window = app.get_app_window(AccountsWindow)
        if window is None:
            window = AccountsWindow()
        else:
            window.present()
        window.select_account(self.account)
        self.window.destroy()

    def on_finish_button_clicked(self, widget):
        go_online = self.xml.get_object('go_online_checkbutton').get_active()
        show_vcard = self.xml.get_object('show_vcard_checkbutton').get_active()
        self.window.destroy()
        if show_vcard:
            app.interface.show_vcard_when_connect.append(self.account)
        if go_online:
            app.interface.roster.send_status(self.account, 'online', '')

    def on_username_entry_key_press_event(self, widget, event):
        # Check for pressed @ and jump to combobox if found
        if event.keyval == Gdk.KEY_at:
            entry = self.xml.get_object('server_comboboxtext_entry')
            entry.grab_focus()
            entry.set_position(-1)
            return True

    def on_entry_key_press_event(self, widget, event, combobox):
        # If backspace is pressed in empty field, return to the nick entry field
        backspace = event.keyval == Gdk.KEY_BackSpace
        empty = len(combobox.get_active_text()) == 0
        if backspace and empty and self.modify:
            username_entry = self.xml.get_object('username_entry')
            username_entry.grab_focus()
            username_entry.set_position(-1)
            return True

    def get_config(self, login, server, savepass, password, anonymous=False):
        config = {}
        config['name'] = login
        config['account_label'] = '%s@%s' % (login, server)
        config['hostname'] = server
        config['savepass'] = savepass
        config['password'] = password
        config['anonymous_auth'] = anonymous
        config['priority'] = 5
        config['autoconnect'] = True
        config['no_log_for'] = ''
        config['sync_with_global_status'] = True
        config['proxy'] = ''
        config['use_custom_host'] = False
        config['custom_port'] = 0
        config['custom_host'] = ''
        return config

    def save_account(self, login, server, savepass, password, anonymous=False):
        if self.account in app.connections:
            ErrorDialog(
                _('Account name is in use'),
                _('You already have an account using this name.'))
            return
        con = connection.Connection(self.account)
        con.password = password

        config = self.get_config(login, server, savepass, password, anonymous)

        if not self.modify:
            con.new_account(self.account, config)
            return
        app.connections[self.account] = con
        self.create_vars(config)

    def create_vars(self, config):
        app.config.add_per('accounts', self.account)

        config['account_label'] = '%s@%s' % (config['name'], config['hostname'])
        if not config['savepass']:
            config['password'] = ''

        for opt in config:
            app.config.set_per('accounts', self.account, opt, config[opt])

        # update variables
        app.interface.instances[self.account] = {
            'infos': {}, 'disco': {},
            'gc_config': {}, 'search': {}, 'online_dialog': {},
            'sub_request': {}}
        app.interface.minimized_controls[self.account] = {}
        app.connections[self.account].connected = 0
        app.groups[self.account] = {}
        app.contacts.add_account(self.account)
        app.gc_connected[self.account] = {}
        app.automatic_rooms[self.account] = {}
        app.newly_added[self.account] = []
        app.to_be_removed[self.account] = []
        app.nicks[self.account] = config['name']
        app.block_signed_in_notifications[self.account] = True
        app.sleeper_state[self.account] = 'off'
        app.last_message_time[self.account] = {}
        app.status_before_autoaway[self.account] = ''
        app.gajim_optional_features[self.account] = []
        app.caps_hash[self.account] = ''
        helpers.update_optional_features(self.account)
        # action must be added before account window is updated
        app.app.add_account_actions(self.account)
        # refresh accounts window
        window = app.get_app_window('AccountsWindow')
        if window is not None:
            window.add_account(self.account)
        # refresh roster
        if len(app.connections) >= 2:
            # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        gui_menu_builder.build_accounts_menu()
