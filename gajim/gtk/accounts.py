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

from functools import partial

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common import passwords
from gajim.common import helpers
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.connection import Connection
from gajim.common.zeroconf.connection_zeroconf import ConnectionZeroconf
from gajim.common.const import Option
from gajim.common.const import OptionKind
from gajim.common.const import OptionType

from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import config

from gajim.options_dialog import OptionsDialog
from gajim.options_dialog import OptionsBox

from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import YesNoDialog


class AccountsWindow(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('AccountsWindow')
        self.set_default_size(700, 550)
        self.set_resizable(False)
        self.set_title(_('Accounts'))
        self.need_relogin = {}

        glade_objects = ['stack', 'box', 'account_list']
        self.builder = gtkgui_helpers.get_gtk_builder('accounts_window.ui')
        for obj in glade_objects:
            setattr(self, obj, self.builder.get_object(obj))

        self.account_list.add(Preferences(self))
        account_item = AddAccount()
        self.account_list.add(account_item)
        account_item.set_activatable()

        accounts = app.config.get_per('accounts')
        accounts.sort()
        for account in accounts:
            self.need_relogin[account] = self.get_relogin_options(account)
            account_item = Account(account, self)
            self.account_list.add(account_item)
            account_item.set_activatable()

        self.add(self.box)
        self.builder.connect_signals(self)

        self.connect('destroy', self.on_destroy)
        self.connect('key-press-event', self.on_key_press)

        self._activate_preferences_page()
        self.show_all()

        app.ged.register_event_handler(
            'our-show', ged.GUI2, self._nec_our_status)

    def _nec_our_status(self, event):
        self.update_accounts()

    def _activate_preferences_page(self):
        row = self.account_list.get_row_at_index(0)
        self.account_list.select_row(row)
        self.account_list.emit('row-activated', row)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def on_destroy(self, *args):
        self.check_relogin()
        app.ged.remove_event_handler(
            'our-show', ged.GUI2, self._nec_our_status)

    def on_child_visible(self, stack, *args):
        page = stack.get_visible_child_name()
        if page is None:
            return
        if page == 'account':
            self.check_relogin()

    def update_accounts(self):
        for row in self.account_list.get_children():
            row.get_child().update()

    @staticmethod
    def on_row_activated(listbox, row):
        row.get_child().on_row_activated()

    def remove_all_pages(self):
        for page in self.stack.get_children():
            self.stack.remove(page)

    def set_page(self, page, name):
        self.remove_all_pages()
        self.stack.add_named(page, name)
        page.update()
        page.show_all()
        self.stack.set_visible_child(page)

    def update_proxy_list(self):
        page = self.stack.get_child_by_name('connection')
        if page is None:
            return
        page.listbox.get_option('proxy').update_values()

    def check_relogin(self):
        for account in self.need_relogin:
            options = self.get_relogin_options(account)
            active = app.config.get_per('accounts', account, 'active')
            if options != self.need_relogin[account]:
                self.need_relogin[account] = options
                if active:
                    self.relog(account)
                break

    def relog(self, account):
        if app.connections[account].connected == 0:
            return

        if account == app.ZEROCONF_ACC_NAME:
            app.connections[app.ZEROCONF_ACC_NAME].update_details()
            return

        def login(account, show_before, status_before):
            """
            Login with previous status
            """
            # first make sure connection is really closed,
            # 0.5 may not be enough
            app.connections[account].disconnect(True)
            app.interface.roster.send_status(
                account, show_before, status_before)

        def relog(account):
            show_before = app.SHOW_LIST[app.connections[account].connected]
            status_before = app.connections[account].status
            app.interface.roster.send_status(
                account, 'offline', _('Be right back.'))
            GLib.timeout_add(500, login, account, show_before, status_before)

        YesNoDialog(
            _('Relogin now?'),
            _('If you want all the changes to apply instantly, '
              'you must relogin.'),
            transient_for=self,
            on_response_yes=lambda *args: relog(account))

    @staticmethod
    def get_relogin_options(account):
        if account == app.ZEROCONF_ACC_NAME:
            options = ['zeroconf_first_name', 'zeroconf_last_name',
                       'zeroconf_jabber_id', 'zeroconf_email', 'keyid']
        else:
            options = ['client_cert', 'proxy', 'resource',
                       'use_custom_host', 'custom_host', 'custom_port',
                       'keyid']

        values = []
        for option in options:
            values.append(app.config.get_per('accounts', account, option))
        return values

    def on_remove_account(self, button, account):
        if app.events.get_events(account):
            app.interface.raise_dialog('unread-events-on-remove-account')
            return

        if app.config.get_per('accounts', account, 'is_zeroconf'):
            # Should never happen as button is insensitive
            return

        win_opened = False
        if app.interface.msg_win_mgr.get_controls(acct=account):
            win_opened = True
        elif account in app.interface.instances:
            for key in app.interface.instances[account]:
                if (app.interface.instances[account][key] and
                        key != 'remove_account'):
                    win_opened = True
                    break

        # Detect if we have opened windows for this account

        def remove(account):
            if (account in app.interface.instances and
                    'remove_account' in app.interface.instances[account]):
                dialog = app.interface.instances[account]['remove_account']
                dialog.window.present()
            else:
                if account not in app.interface.instances:
                    app.interface.instances[account] = {}
                app.interface.instances[account]['remove_account'] = \
                    config.RemoveAccountWindow(account)
        if win_opened:
            ConfirmationDialog(
                _('You have opened chat in account %s') % account,
                _('All chat and groupchat windows will be closed. '
                  'Do you want to continue?'),
                on_response_ok=(remove, account),
                transient_for=self)
        else:
            remove(account)

    def remove_account(self, account):
        for row in self.account_list.get_children():
            if row.get_child().account == account:
                self.account_list.remove(row)
                del self.need_relogin[account]
                break
        self._activate_preferences_page()

    def add_account(self, account):
        account_item = Account(account, self)
        self.account_list.add(account_item)
        account_item.set_activatable()
        self.account_list.show_all()
        self.stack.show_all()
        self.need_relogin[account] = self.get_relogin_options(account)

    def select_account(self, account):
        for row in self.account_list.get_children():
            if row.get_child().account == account:
                self.account_list.select_row(row)
                self.account_list.emit('row-activated', row)
                break

    @staticmethod
    def enable_account(account):
        if account == app.ZEROCONF_ACC_NAME:
            app.connections[account] = ConnectionZeroconf(account)
        else:
            app.connections[account] = Connection(account)

        app.plugin_manager.register_modules_for_account(
            app.connections[account])

        # update variables
        app.interface.instances[account] = {
            'infos': {}, 'disco': {}, 'gc_config': {}, 'search': {},
            'online_dialog': {}, 'sub_request': {}}
        app.interface.minimized_controls[account] = {}
        app.connections[account].connected = 0
        app.groups[account] = {}
        app.contacts.add_account(account)
        app.gc_connected[account] = {}
        app.automatic_rooms[account] = {}
        app.newly_added[account] = []
        app.to_be_removed[account] = []
        if account == app.ZEROCONF_ACC_NAME:
            app.nicks[account] = app.ZEROCONF_ACC_NAME
        else:
            app.nicks[account] = app.config.get_per(
                'accounts', account, 'name')
        app.block_signed_in_notifications[account] = True
        app.sleeper_state[account] = 'off'
        app.last_message_time[account] = {}
        app.status_before_autoaway[account] = ''
        app.gajim_optional_features[account] = []
        app.caps_hash[account] = ''
        helpers.update_optional_features(account)
        # refresh roster
        if len(app.connections) >= 2:
            # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        gui_menu_builder.build_accounts_menu()

    @staticmethod
    def disable_account(account):
        app.interface.roster.close_all(account)
        if account == app.ZEROCONF_ACC_NAME:
            app.connections[account].disable_account()
        app.connections[account].cleanup()
        del app.connections[account]
        del app.interface.instances[account]
        del app.interface.minimized_controls[account]
        del app.nicks[account]
        del app.block_signed_in_notifications[account]
        del app.groups[account]
        app.contacts.remove_account(account)
        del app.gc_connected[account]
        del app.automatic_rooms[account]
        del app.to_be_removed[account]
        del app.newly_added[account]
        del app.sleeper_state[account]
        del app.last_message_time[account]
        del app.status_before_autoaway[account]
        del app.gajim_optional_features[account]
        del app.caps_hash[account]
        if len(app.connections) >= 2:
            # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.config.set_per(
            'accounts', account, 'roster_version', '')
        app.interface.roster.setup_and_draw_roster()
        gui_menu_builder.build_accounts_menu()


class AddAccount(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=12)

        self.account = None

        self.label = Gtk.Label(label=_('Add Account…'))
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)

        self.image = Gtk.Image.new_from_icon_name(
            'list-add-symbolic', Gtk.IconSize.MENU)

        self.add(self.image)
        self.add(self.label)

    def set_activatable(self):
        self.get_parent().set_selectable(False)

    def on_row_activated(self):
        app.app.activate_action('add-account')

    def update(self):
        pass


class Preferences(Gtk.Box):
    def __init__(self, parent):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=12)

        self.options = PreferencesPage()
        self.parent = parent
        self.account = None

        self.label = Gtk.Label(label=_('Preferences'))
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)

        self.image = Gtk.Image.new_from_icon_name(
            'system-run-symbolic', Gtk.IconSize.MENU)

        self.add(self.image)
        self.add(self.label)

    def set_activatable(self):
        pass

    def on_row_activated(self):
        self.options.update_states()
        self.parent.set_page(self.options, 'pref')

    def update(self):
        pass


class Account(Gtk.Box):
    def __init__(self, account, parent):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=12)
        self.account = account
        if account == app.ZEROCONF_ACC_NAME:
            self.options = ZeroConfPage(account, parent)
        else:
            self.options = AccountPage(account, parent)
        self.parent = parent

        self.label = Gtk.Label(label=app.get_account_label(account))
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)

        self.image = Gtk.Image()
        self._update_image()

        self.add(self.image)
        self.add(self.label)

    def set_activatable(self):
        if self.account == app.ZEROCONF_ACC_NAME:
            zeroconf = app.is_installed('ZEROCONF')
            self.get_parent().set_activatable(zeroconf)
            self.get_parent().set_sensitive(zeroconf)
            if not zeroconf:
                self.get_parent().set_tooltip_text(
                    _('Please check if Avahi or Bonjour is installed.'))

    def on_row_activated(self):
        self.options.update_states()
        self.parent.set_page(self.options, 'account')

    def update(self):
        self.label.set_text(app.get_account_label(self.account))
        self._update_image()

    def _update_image(self):
        show = helpers.get_current_show(self.account)
        icon = gtkgui_helpers.get_iconset_name_for(show)
        self.image.set_from_icon_name(icon, Gtk.IconSize.MENU)


class GenericOptionPage(Gtk.Box):
    def __init__(self, account, parent, options):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.account = account
        self.parent = parent

        button = Gtk.Button.new_from_icon_name(
            'go-previous-symbolic', Gtk.IconSize.MENU)
        button.set_halign(Gtk.Align.START)
        button.connect('clicked', self._on_back_button)
        if not isinstance(self, (AccountPage, PreferencesPage, ZeroConfPage)):
            self.pack_start(button, False, True, 0)

        self.listbox = OptionsBox(account)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_vexpand(False)
        self.listbox.set_valign(Gtk.Align.END)

        for option in options:
            self.listbox.add_option(option)
        self.listbox.update_states()

        self.pack_end(self.listbox, True, True, 0)

        self.listbox.connect('row-activated', self.on_row_activated)

    def _on_back_button(self, *args):
        account_window = self.get_toplevel()
        child = account_window.stack.get_visible_child()
        account_window.remove_all_pages()
        account_window.stack.add_named(child.parent, 'account')
        account_window.stack.set_visible_child_name('account')

    def update_states(self):
        self.listbox.update_states()

    def on_row_activated(self, listbox, row):
        row.get_child().on_row_activated()

    def set_entry_text(self, toggle, update=False):
        account_label = app.get_account_label(self.account)
        if update:
            self.entry.set_text(account_label)
            return
        if toggle.get_active():
            self.entry.set_sensitive(True)
            self.entry.grab_focus()
        else:
            self.entry.set_sensitive(False)
            value = self.entry.get_text()
            if not value:
                value = account_label
            app.config.set_per('accounts', self.account,
                               'account_label', value or self.account)
            if app.config.get_per('accounts', self.account, 'active'):
                app.interface.roster.draw_account(self.account)
                gui_menu_builder.build_accounts_menu()

    def update(self):
        pass

    def set_page(self, options, name):
        options.update_states()
        self.get_toplevel().set_page(options, name)

    def _add_top_buttons(self, parent):
        # This adds the Account enable switch and the back button
        box = Gtk.Box()
        box.set_hexpand(True)
        box.set_halign(Gtk.Align.FILL)
        switch = Gtk.Switch()
        switch.set_active(app.config.get_per('accounts', self.account, 'active'))
        switch.set_vexpand(False)
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_halign(Gtk.Align.END)
        if self.account == app.ZEROCONF_ACC_NAME and not app.is_installed('ZEROCONF'):
            switch.set_sensitive(False)
            switch.set_active(False)

        switch.connect('notify::active', self._on_enable_switch, self.account)
        box.pack_start(switch, False, False, 0)
        if self.account != app.ZEROCONF_ACC_NAME:
            button = Gtk.Button(label=_('Remove'))
            button.connect(
                'clicked', parent.on_remove_account, self.account)
            button.get_style_context().add_class('destructive-action')
            button.set_halign(Gtk.Align.END)
            switch.set_vexpand(False)
            box.pack_end(button, False, False, 0)
        self.pack_start(box, True, True, 0)

    def _on_enable_switch(self, switch, param, account):
        old_state = app.config.get_per('accounts', account, 'active')
        state = switch.get_active()
        if old_state == state:
            return

        if (account in app.connections and
                app.connections[account].connected > 0):
            # connecting or connected
            app.interface.raise_dialog('connected-on-disable-account')
            switch.set_active(not state)
            return
        if state:
            self.parent.enable_account(account)
        else:
            self.parent.disable_account(account)
        app.config.set_per('accounts', account, 'active', state)


class PreferencesPage(GenericOptionPage):
    def __init__(self):

        options = [
            Option(OptionKind.SWITCH, _('Merge Accounts'),
                   OptionType.ACTION, 'merge'),

            Option(OptionKind.SWITCH, _('Use PGP Agent'),
                   OptionType.ACTION, 'agent'),
            ]

        GenericOptionPage.__init__(self, None, None, options)


class AccountPage(GenericOptionPage):
    def __init__(self, account, parent=None):

        general = partial(
            self.set_page, GeneralPage(account, self), 'general')
        connection = partial(
            self.set_page, ConnectionPage(account, self), 'connection')

        options = [
            Option(OptionKind.ENTRY, _('Label'),
                   OptionType.ACCOUNT_CONFIG, 'account_label',
                   callback=self._on_account_name_change),

            Option(OptionKind.LOGIN, _('Login'), OptionType.DIALOG,
                   props={'dialog': LoginDialog}),

            Option(OptionKind.ACTION, _('Profile'), OptionType.ACTION,
                   '-profile', props={'action_args': account}),

            Option(OptionKind.CALLBACK, _('General'),
                   name='general', props={'callback': general}),

            Option(OptionKind.CALLBACK, _('Connection'),
                   name='connection', props={'callback': connection}),

            Option(OptionKind.ACTION, _('Import Contacts'), OptionType.ACTION,
                   '-import-contacts', props={'action_args': account}),

            Option(OptionKind.DIALOG, _('Client Certificate'),
                   OptionType.DIALOG, props={'dialog': CertificateDialog}),

            Option(OptionKind.GPG, _('OpenPGP Key'), OptionType.DIALOG,
                   props={'dialog': None}),
            ]

        GenericOptionPage.__init__(self, account, parent, options)
        self._add_top_buttons(parent)

    def _on_account_name_change(self, account_name, *args):
        self.parent.update_accounts()


class GeneralPage(GenericOptionPage):
    def __init__(self, account, parent=None):

        options = [
            Option(OptionKind.SWITCH, _('Connect on startup'),
                   OptionType.ACCOUNT_CONFIG, 'autoconnect'),

            Option(OptionKind.SWITCH, _('Reconnect when connection is lost'),
                   OptionType.ACCOUNT_CONFIG, 'autoreconnect'),

            Option(OptionKind.SWITCH, _('Save conversations for all contacts'),
                   OptionType.ACCOUNT_CONFIG, 'no_log_for',
                   desc=_('Store conversations on the harddrive')),

            Option(OptionKind.SWITCH, _('Server Message Archive'),
                   OptionType.ACCOUNT_CONFIG, 'sync_logs_with_server',
                   desc=_('Messages get stored on the server.\n'
                          'The archive is used to sync messages\n'
                          'between multiple devices.\n'
                          'XEP-0313')),

            Option(OptionKind.SWITCH, _('Global Status'),
                   OptionType.ACCOUNT_CONFIG, 'sync_with_global_status',
                   desc=_('Synchronise the status of all accounts')),

            Option(OptionKind.SWITCH, _('Message Carbons'),
                   OptionType.ACCOUNT_CONFIG, 'enable_message_carbons',
                   desc=_('All your other online devices get copies\n'
                          'of sent and received messages.\n'
                          'XEP-0280')),

            Option(OptionKind.SWITCH, _('Use file transfer proxies'),
                   OptionType.ACCOUNT_CONFIG, 'use_ft_proxies'),
            ]
        GenericOptionPage.__init__(self, account, parent, options)


class ConnectionPage(GenericOptionPage):
    def __init__(self, account, parent=None):

        options = [
            Option(OptionKind.SWITCH, 'HTTP_PROXY',
                   OptionType.ACCOUNT_CONFIG, 'use_env_http_proxy',
                   desc=_('Use environment variable')),

            Option(OptionKind.PROXY, _('Proxy'),
                   OptionType.ACCOUNT_CONFIG, 'proxy', name='proxy'),

            Option(OptionKind.SWITCH, _('Warn on insecure connection'),
                   OptionType.ACCOUNT_CONFIG,
                   'warn_when_insecure_ssl_connection'),

            Option(OptionKind.SWITCH, _('Send keep-alive packets'),
                   OptionType.ACCOUNT_CONFIG, 'keep_alives_enabled'),

            Option(OptionKind.HOSTNAME, _('Hostname'), OptionType.DIALOG,
                   desc=_('Manually set the hostname for the server'),
                   props={'dialog': CutstomHostnameDialog}),

            Option(OptionKind.ENTRY, _('Resource'),
                   OptionType.ACCOUNT_CONFIG, 'resource'),

            Option(OptionKind.PRIORITY, _('Priority'),
                   OptionType.DIALOG, props={'dialog': PriorityDialog}),
            ]

        GenericOptionPage.__init__(self, account, parent, options)


class ZeroConfPage(GenericOptionPage):
    def __init__(self, account, parent=None):

        options = [
            Option(OptionKind.DIALOG, _('Profile'),
                   OptionType.DIALOG, props={'dialog': ZeroconfProfileDialog}),

            Option(OptionKind.SWITCH, _('Connect on startup'),
                   OptionType.ACCOUNT_CONFIG, 'autoconnect',
                   desc=_('Use environment variable')),

            Option(OptionKind.SWITCH, _('Save conversations for all contacts'),
                   OptionType.ACCOUNT_CONFIG, 'no_log_for',
                   desc=_('Store conversations on the harddrive')),

            Option(OptionKind.SWITCH, _('Global Status'),
                   OptionType.ACCOUNT_CONFIG, 'sync_with_global_status',
                   desc=_('Synchronize the status of all accounts')),

            Option(OptionKind.GPG, _('OpenPGP Key'),
                   OptionType.DIALOG, props={'dialog': None}),
            ]

        GenericOptionPage.__init__(self, account, parent, options)
        self._add_top_buttons(None)


class ZeroconfProfileDialog(OptionsDialog):
    def __init__(self, account, parent):

        options = [
            Option(OptionKind.ENTRY, _('First Name'),
                   OptionType.ACCOUNT_CONFIG, 'zeroconf_first_name'),

            Option(OptionKind.ENTRY, _('Last Name'),
                   OptionType.ACCOUNT_CONFIG, 'zeroconf_last_name'),

            Option(OptionKind.ENTRY, _('Jabber ID'),
                   OptionType.ACCOUNT_CONFIG, 'zeroconf_jabber_id'),

            Option(OptionKind.ENTRY, _('Email'),
                   OptionType.ACCOUNT_CONFIG, 'zeroconf_email'),
            ]

        OptionsDialog.__init__(self, parent, _('Profile'),
                               Gtk.DialogFlags.MODAL, options, account)


class PriorityDialog(OptionsDialog):
    def __init__(self, account, parent):

        neg_priority = app.config.get('enable_negative_priority')
        if neg_priority:
            range_ = (-128, 127)
        else:
            range_ = (0, 127)

        options = [
            Option(OptionKind.SWITCH, _('Adjust to status'),
                   OptionType.ACCOUNT_CONFIG, 'adjust_priority_with_status',
                   'adjust'),

            Option(OptionKind.SPIN, _('Priority'),
                   OptionType.ACCOUNT_CONFIG, 'priority',
                   enabledif=('adjust', False), props={'range_': range_}),
            ]

        OptionsDialog.__init__(self, parent, _('Priority'),
                               Gtk.DialogFlags.MODAL, options, account)

        self.connect('destroy', self.on_destroy)

    def on_destroy(self, *args):
        # Update priority
        if self.account not in app.connections:
            return
        show = app.SHOW_LIST[app.connections[self.account].connected]
        status = app.connections[self.account].status
        app.connections[self.account].change_status(show, status)


class CutstomHostnameDialog(OptionsDialog):
    def __init__(self, account, parent):

        options = [
            Option(OptionKind.SWITCH, _('Enable'),
                   OptionType.ACCOUNT_CONFIG, 'use_custom_host', name='custom'),

            Option(OptionKind.ENTRY, _('Hostname'),
                   OptionType.ACCOUNT_CONFIG, 'custom_host',
                   enabledif=('custom', True)),

            Option(OptionKind.ENTRY, _('Port'),
                   OptionType.ACCOUNT_CONFIG, 'custom_port',
                   enabledif=('custom', True)),
            ]

        OptionsDialog.__init__(self, parent, _('Connection Options'),
                               Gtk.DialogFlags.MODAL, options, account)


class CertificateDialog(OptionsDialog):
    def __init__(self, account, parent):

        options = [
            Option(OptionKind.FILECHOOSER, _('Client Certificate'),
                   OptionType.ACCOUNT_CONFIG, 'client_cert',
                   props={'filefilter': (_('PKCS12 Files'), '*.p12')}),

            Option(OptionKind.SWITCH, _('Encrypted Certificate'),
                   OptionType.ACCOUNT_CONFIG, 'client_cert_encrypted'),
            ]

        OptionsDialog.__init__(self, parent, _('Certificate Options'),
                               Gtk.DialogFlags.MODAL, options, account)


class LoginDialog(OptionsDialog):
    def __init__(self, account, parent):

        options = [
            Option(OptionKind.ENTRY, _('Password'),
                   OptionType.ACCOUNT_CONFIG, 'password', name='password',
                   enabledif=('savepass', True)),

            Option(OptionKind.SWITCH, _('Save Password'),
                   OptionType.ACCOUNT_CONFIG, 'savepass', name='savepass'),

            Option(OptionKind.CHANGEPASSWORD, _('Change Password'),
                   OptionType.DIALOG, callback=self.on_password_change,
                   props={'dialog': None}),
            ]

        OptionsDialog.__init__(self, parent, _('Login Options'),
                               Gtk.DialogFlags.MODAL, options, account)

        self.connect('destroy', self.on_destroy)

    def on_password_change(self, new_password, data):
        passwords.save_password(self.account, new_password)

    def on_destroy(self, *args):
        savepass = app.config.get_per('accounts', self.account, 'savepass')
        if not savepass:
            passwords.save_password(self.account, '')
