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

from gajim import gui_menu_builder
from gajim.dialogs import PassphraseDialog

from gajim.gtk.settings import SettingsDialog
from gajim.gtk.settings import SettingsBox
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import ConfirmationDialogDoubleRadio
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import YesNoDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_builder
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType


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

        self._ui = get_builder('accounts_window.ui')

        self._ui.account_list.add(Preferences(self))
        account_item = AddAccount()
        self._ui.account_list.add(account_item)
        account_item.set_activatable()

        accounts = app.config.get_per('accounts')
        accounts.sort()
        for account in accounts:
            self.need_relogin[account] = self.get_relogin_settings(account)
            account_item = Account(account, self)
            self._ui.account_list.add(account_item)
            account_item.set_activatable()

        self.add(self._ui.box)
        self._ui.connect_signals(self)

        self.connect('destroy', self.on_destroy)
        self.connect('key-press-event', self.on_key_press)

        self._activate_preferences_page()
        self.show_all()

        app.ged.register_event_handler(
            'our-show', ged.GUI2, self._nec_our_status)

    @property
    def stack(self):
        return self._ui.stack

    def _nec_our_status(self, event):
        self.update_accounts()

    def _activate_preferences_page(self):
        row = self._ui.account_list.get_row_at_index(0)
        self._ui.account_list.select_row(row)
        self._ui.account_list.emit('row-activated', row)

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
        for row in self._ui.account_list.get_children():
            row.get_child().update()

    @staticmethod
    def on_row_activated(listbox, row):
        row.get_child().on_row_activated()

    def remove_all_pages(self):
        for page in self._ui.stack.get_children():
            self._ui.stack.remove(page)

    def set_page(self, page, name):
        self.remove_all_pages()
        self._ui.stack.add_named(page, name)
        page.update()
        page.show_all()
        self._ui.stack.set_visible_child(page)

    def update_proxy_list(self):
        page = self._ui.stack.get_child_by_name('connection')
        if page is None:
            return
        page.listbox.get_setting('proxy').update_values()

    def check_relogin(self):
        for account in self.need_relogin:
            settings = self.get_relogin_settings(account)
            active = app.config.get_per('accounts', account, 'active')
            if settings != self.need_relogin[account]:
                self.need_relogin[account] = settings
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
    def get_relogin_settings(account):
        if account == app.ZEROCONF_ACC_NAME:
            settings = ['zeroconf_first_name', 'zeroconf_last_name',
                        'zeroconf_jabber_id', 'zeroconf_email']
        else:
            settings = ['client_cert', 'proxy', 'resource',
                        'use_custom_host', 'custom_host', 'custom_port']

        values = []
        for setting in settings:
            values.append(app.config.get_per('accounts', account, setting))
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
                    RemoveAccountWindow(account)
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
        for row in self._ui.account_list.get_children():
            if row.get_child().account == account:
                self._ui.account_list.remove(row)
                del self.need_relogin[account]
                break
        self._activate_preferences_page()

    def add_account(self, account):
        account_item = Account(account, self)
        self._ui.account_list.add(account_item)
        account_item.set_activatable()
        self._ui.account_list.show_all()
        self._ui.stack.show_all()
        self.need_relogin[account] = self.get_relogin_settings(account)

    def select_account(self, account):
        for row in self._ui.account_list.get_children():
            if row.get_child().account == account:
                self._ui.account_list.select_row(row)
                self._ui.account_list.emit('row-activated', row)
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

        self.settings = PreferencesPage()
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
        self.settings.update_states()
        self.parent.set_page(self.settings, 'pref')

    def update(self):
        pass


class Account(Gtk.Box):
    def __init__(self, account, parent):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=12)
        self.account = account
        if account == app.ZEROCONF_ACC_NAME:
            self.settings = ZeroConfPage(account, parent)
        else:
            self.settings = AccountPage(account, parent)
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
        self.settings.update_states()
        self.parent.set_page(self.settings, 'account')

    def update(self):
        self.label.set_text(app.get_account_label(self.account))
        self._update_image()

    def _update_image(self):
        show = helpers.get_current_show(self.account)
        icon = get_icon_name(show)
        self.image.set_from_icon_name(icon, Gtk.IconSize.MENU)


class GenericSettingPage(Gtk.Box):
    def __init__(self, account, parent, settings):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.account = account
        self.parent = parent

        button = Gtk.Button.new_from_icon_name(
            'go-previous-symbolic', Gtk.IconSize.MENU)
        button.set_halign(Gtk.Align.START)
        button.connect('clicked', self._on_back_button)
        if not isinstance(self, (AccountPage, PreferencesPage, ZeroConfPage)):
            self.pack_start(button, False, True, 0)

        self.listbox = SettingsBox(account)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_vexpand(False)
        self.listbox.set_valign(Gtk.Align.END)

        for setting in settings:
            self.listbox.add_setting(setting)
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
        row.on_row_activated()

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

    def set_page(self, settings, name):
        settings.update_states()
        self.get_toplevel().set_page(settings, name)

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

        switch.connect('state-set', self._on_enable_switch, self.account)
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

    def _on_enable_switch(self, switch, state, account):
        def _disable():
            app.connections[account].change_status('offline', 'offline')
            app.connections[account].disconnect(reconnect=False)
            self.parent.disable_account(account)
            app.config.set_per('accounts', account, 'active', False)
            switch.set_state(state)

        old_state = app.config.get_per('accounts', account, 'active')
        if old_state == state:
            return

        if (account in app.connections and
                app.connections[account].connected > 0):
            # Connecting or connected
            NewConfirmationDialog(
                _('Disable Account'),
                _('Account %s is still connected') % account,
                _('All chat and group chat windows will be closed. '
                  'Do you want to continue?'),
                [DialogButton.make('Cancel',
                                   callback=lambda: switch.set_active(True)),
                 DialogButton.make('Remove',
                                   text=_('Disable Account'),
                                   callback=_disable)],
                transient_for=self.parent).show()
            return Gdk.EVENT_STOP

        if state:
            self.parent.enable_account(account)
        else:
            self.parent.disable_account(account)
        app.config.set_per('accounts', account, 'active', state)


class PreferencesPage(GenericSettingPage):
    def __init__(self):

        settings = [
            Setting(SettingKind.SWITCH, _('Merge Accounts'),
                    SettingType.ACTION, 'merge'),
            ]

        GenericSettingPage.__init__(self, None, None, settings)


class AccountPage(GenericSettingPage):
    def __init__(self, account, parent=None):

        general = partial(
            self.set_page, GeneralPage(account, self), 'general')
        connection = partial(
            self.set_page, ConnectionPage(account, self), 'connection')

        settings = [
            Setting(SettingKind.ENTRY, _('Label'),
                    SettingType.ACCOUNT_CONFIG, 'account_label',
                    callback=self._on_account_name_change),

            Setting(SettingKind.LOGIN, _('Login'), SettingType.DIALOG,
                    props={'dialog': LoginDialog}),

            Setting(SettingKind.ACTION, _('Profile'), SettingType.ACTION,
                    '-profile', props={'action_args': account}),

            Setting(SettingKind.CALLBACK, _('General'),
                    name='general', props={'callback': general}),

            Setting(SettingKind.CALLBACK, _('Connection'),
                    name='connection', props={'callback': connection}),

            Setting(SettingKind.ACTION, _('Import Contacts'), SettingType.ACTION,
                    '-import-contacts', props={'action_args': account}),

            Setting(SettingKind.DIALOG, _('Client Certificate'),
                    SettingType.DIALOG, props={'dialog': CertificateDialog}),
            ]

        GenericSettingPage.__init__(self, account, parent, settings)
        self._add_top_buttons(parent)

    def _on_account_name_change(self, account_name, *args):
        self.parent.update_accounts()


class GeneralPage(GenericSettingPage):
    def __init__(self, account, parent=None):

        settings = [
            Setting(SettingKind.SWITCH, _('Connect on startup'),
                    SettingType.ACCOUNT_CONFIG, 'autoconnect'),

            Setting(SettingKind.SWITCH, _('Reconnect when connection is lost'),
                    SettingType.ACCOUNT_CONFIG, 'autoreconnect'),

            Setting(SettingKind.SWITCH, _('Save conversations for all contacts'),
                    SettingType.ACCOUNT_CONFIG, 'no_log_for',
                    desc=_('Store conversations on the harddrive')),

            Setting(SettingKind.SWITCH, _('Server Message Archive'),
                    SettingType.ACCOUNT_CONFIG, 'sync_logs_with_server',
                    desc=_('Messages get stored on the server. '
                           'The archive is used to sync messages '
                           'between multiple devices. (XEP-0313)')),

            Setting(SettingKind.SWITCH, _('Global Status'),
                    SettingType.ACCOUNT_CONFIG, 'sync_with_global_status',
                    desc=_('Synchronise the status of all accounts')),

            Setting(SettingKind.SWITCH, _('Message Carbons'),
                    SettingType.ACCOUNT_CONFIG, 'enable_message_carbons',
                    desc=_('All your other online devices get copies '
                           'of sent and received messages. XEP-0280')),

            Setting(SettingKind.SWITCH, _('Use file transfer proxies'),
                    SettingType.ACCOUNT_CONFIG, 'use_ft_proxies'),
            ]
        GenericSettingPage.__init__(self, account, parent, settings)


class ConnectionPage(GenericSettingPage):
    def __init__(self, account, parent=None):

        settings = [
            Setting(SettingKind.SWITCH, 'HTTP_PROXY',
                    SettingType.ACCOUNT_CONFIG, 'use_env_http_proxy',
                    desc=_('Use environment variable')),

            Setting(SettingKind.PROXY, _('Proxy'),
                    SettingType.ACCOUNT_CONFIG, 'proxy', name='proxy'),

            Setting(SettingKind.SWITCH, _('Warn on insecure connection'),
                    SettingType.ACCOUNT_CONFIG,
                    'warn_when_insecure_ssl_connection'),

            Setting(SettingKind.SWITCH, _('Send keep-alive packets'),
                    SettingType.ACCOUNT_CONFIG, 'keep_alives_enabled'),

            Setting(SettingKind.HOSTNAME, _('Hostname'), SettingType.DIALOG,
                    desc=_('Manually set the hostname for the server'),
                    props={'dialog': CutstomHostnameDialog}),

            Setting(SettingKind.ENTRY, _('Resource'),
                    SettingType.ACCOUNT_CONFIG, 'resource'),

            Setting(SettingKind.PRIORITY, _('Priority'),
                    SettingType.DIALOG, props={'dialog': PriorityDialog}),
            ]

        GenericSettingPage.__init__(self, account, parent, settings)


class ZeroConfPage(GenericSettingPage):
    def __init__(self, account, parent=None):

        settings = [
            Setting(SettingKind.DIALOG, _('Profile'),
                    SettingType.DIALOG, props={'dialog': ZeroconfProfileDialog}),

            Setting(SettingKind.SWITCH, _('Connect on startup'),
                    SettingType.ACCOUNT_CONFIG, 'autoconnect',
                    desc=_('Use environment variable')),

            Setting(SettingKind.SWITCH, _('Save conversations for all contacts'),
                    SettingType.ACCOUNT_CONFIG, 'no_log_for',
                    desc=_('Store conversations on the harddrive')),

            Setting(SettingKind.SWITCH, _('Global Status'),
                    SettingType.ACCOUNT_CONFIG, 'sync_with_global_status',
                    desc=_('Synchronize the status of all accounts')),
            ]

        GenericSettingPage.__init__(self, account, parent, settings)
        self._add_top_buttons(None)


class ZeroconfProfileDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.ENTRY, _('First Name'),
                    SettingType.ACCOUNT_CONFIG, 'zeroconf_first_name'),

            Setting(SettingKind.ENTRY, _('Last Name'),
                    SettingType.ACCOUNT_CONFIG, 'zeroconf_last_name'),

            Setting(SettingKind.ENTRY, _('Jabber ID'),
                    SettingType.ACCOUNT_CONFIG, 'zeroconf_jabber_id'),

            Setting(SettingKind.ENTRY, _('Email'),
                    SettingType.ACCOUNT_CONFIG, 'zeroconf_email'),
            ]

        SettingsDialog.__init__(self, parent, _('Profile'),
                               Gtk.DialogFlags.MODAL, settings, account)


class PriorityDialog(SettingsDialog):
    def __init__(self, account, parent):

        neg_priority = app.config.get('enable_negative_priority')
        if neg_priority:
            range_ = (-128, 127)
        else:
            range_ = (0, 127)

        settings = [
            Setting(SettingKind.SWITCH, _('Adjust to status'),
                    SettingType.ACCOUNT_CONFIG, 'adjust_priority_with_status',
                    'adjust'),

            Setting(SettingKind.SPIN, _('Priority'),
                    SettingType.ACCOUNT_CONFIG, 'priority',
                    enabledif=('adjust', False), props={'range_': range_}),
            ]

        SettingsDialog.__init__(self, parent, _('Priority'),
                               Gtk.DialogFlags.MODAL, settings, account)

        self.connect('destroy', self.on_destroy)

    def on_destroy(self, *args):
        # Update priority
        if self.account not in app.connections:
            return
        show = app.SHOW_LIST[app.connections[self.account].connected]
        status = app.connections[self.account].status
        app.connections[self.account].change_status(show, status)


class CutstomHostnameDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.SWITCH, _('Enable'),
                    SettingType.ACCOUNT_CONFIG, 'use_custom_host', name='custom'),

            Setting(SettingKind.ENTRY, _('Hostname'),
                    SettingType.ACCOUNT_CONFIG, 'custom_host',
                    enabledif=('custom', True)),

            Setting(SettingKind.ENTRY, _('Port'),
                    SettingType.ACCOUNT_CONFIG, 'custom_port',
                    enabledif=('custom', True)),
            ]

        SettingsDialog.__init__(self, parent, _('Connection Settings'),
                               Gtk.DialogFlags.MODAL, settings, account)


class CertificateDialog(SettingsDialog):
    def __init__(self, account, parent):

        Settings = [
            Setting(SettingKind.FILECHOOSER, _('Client Certificate'),
                    SettingType.ACCOUNT_CONFIG, 'client_cert',
                    props={'filefilter': (_('PKCS12 Files'), '*.p12')}),

            Setting(SettingKind.SWITCH, _('Encrypted Certificate'),
                    SettingType.ACCOUNT_CONFIG, 'client_cert_encrypted'),
            ]

        SettingsDialog.__init__(self, parent, _('Certificate Settings'),
                               Gtk.DialogFlags.MODAL, Settings, account)


class LoginDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.ENTRY, _('Password'),
                    SettingType.ACCOUNT_CONFIG, 'password', name='password',
                    enabledif=('savepass', True)),

            Setting(SettingKind.SWITCH, _('Save Password'),
                    SettingType.ACCOUNT_CONFIG, 'savepass', name='savepass'),

            Setting(SettingKind.CHANGEPASSWORD, _('Change Password'),
                    SettingType.DIALOG, callback=self.on_password_change,
                    props={'dialog': None}),
            ]

        SettingsDialog.__init__(self, parent, _('Login Settings'),
                               Gtk.DialogFlags.MODAL, settings, account)

        self.connect('destroy', self.on_destroy)

    def on_password_change(self, new_password, data):
        passwords.save_password(self.account, new_password)

    def on_destroy(self, *args):
        savepass = app.config.get_per('accounts', self.account, 'savepass')
        if not savepass:
            passwords.delete_password(self.account)


class RemoveAccountWindow:
    """
    Ask whether to remove from gajim only or both from gajim and the server,
    then remove the account given
    """

    def on_remove_account_window_destroy(self, widget):
        if self.account in app.interface.instances:
            del app.interface.instances[self.account]['remove_account']

    def on_cancel_button_clicked(self, widget):
        self._ui.remove_account_window.destroy()

    def __init__(self, account):
        self.account = account
        self._ui = get_builder('remove_account_window.ui')
        active_window = app.app.get_active_window()
        self._ui.remove_account_window.set_transient_for(active_window)
        self._ui.remove_account_window.set_title(_('Removing account %s') % self.account)
        self._ui.connect_signals(self)
        self._ui.remove_account_window.show_all()

    def on_remove_button_clicked(self, widget):
        def remove():
            if self.account in app.connections and \
            app.connections[self.account].connected and \
            not self._ui.remove_and_unregister_radiobutton.get_active():
                # change status to offline only if we will not remove this JID from
                # server
                app.connections[self.account].change_status('offline', 'offline')
            if self._ui.remove_and_unregister_radiobutton.get_active():
                if not self.account in app.connections:
                    ErrorDialog(
                        _('Account is disabled'),
                        _('To unregister from a server, the account must be '
                        'enabled.'),
                        transient_for=self._ui.remove_account_window)
                    return
                if not app.connections[self.account].password:
                    def on_ok(passphrase, checked):
                        if passphrase == -1:
                            # We don't remove account cause we canceled pw window
                            return
                        app.connections[self.account].password = passphrase
                        app.connections[self.account].unregister_account(
                                self._on_remove_success)

                    PassphraseDialog(
                            _('Password required'),
                            _('Enter your password for account %s') % self.account,
                            _('Save password'), ok_handler=on_ok,
                            transient_for=self._ui.remove_account_window)
                    return
                app.connections[self.account].unregister_account(
                        self._on_remove_success)
            else:
                self._on_remove_success(True)

        if self.account in app.connections and \
        app.connections[self.account].connected:
            ConfirmationDialog(
                _('Account "%s" is connected to the server') % self.account,
                _('If you remove it, the connection will be lost.'),
                on_response_ok=remove,
                transient_for=self._ui.remove_account_window)
        else:
            remove()

    def on_remove_response_ok(self, is_checked):
        if is_checked[0]:
            self._on_remove_success(True)

    def _on_remove_success(self, res):
        # action of unregistration has failed, we don't remove the account
        # Error message is send by connect_and_auth()
        if not res:
            ConfirmationDialogDoubleRadio(
                    _('Connection to server %s failed') % self.account,
                    _('What would you like to do?'),
                    _('Remove only from Gajim'),
                    _('Don\'t remove anything. I\'ll try again later'),
                    on_response_ok=self.on_remove_response_ok, is_modal=False,
                    transient_for=self._ui.remove_account_window)
            return
        # Close all opened windows
        app.interface.roster.close_all(self.account, force=True)
        if self.account in app.connections:
            app.connections[self.account].disconnect(reconnect=False)
            app.connections[self.account].cleanup()
            del app.connections[self.account]
        app.logger.remove_roster(app.get_jid_from_account(self.account))
        # Delete password must be before del_per() because it calls set_per()
        # which would recreate the account with defaults values if not found
        passwords.delete_password(self.account)
        app.config.del_per('accounts', self.account)
        del app.interface.instances[self.account]
        if self.account in app.nicks:
            del app.interface.minimized_controls[self.account]
            del app.nicks[self.account]
            del app.block_signed_in_notifications[self.account]
            del app.groups[self.account]
            app.contacts.remove_account(self.account)
            del app.gc_connected[self.account]
            del app.automatic_rooms[self.account]
            del app.to_be_removed[self.account]
            del app.newly_added[self.account]
            del app.sleeper_state[self.account]
            del app.last_message_time[self.account]
            del app.status_before_autoaway[self.account]
            del app.gajim_optional_features[self.account]
            del app.caps_hash[self.account]
        if len(app.connections) >= 2: # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        app.app.remove_account_actions(self.account)
        gui_menu_builder.build_accounts_menu()

        window = app.get_app_window('AccountsWindow')
        if window is not None:
            window.remove_account(self.account)
        self._ui.remove_account_window.destroy()

    def destroy(self):
        self._ui.remove_account_window.destroy()
