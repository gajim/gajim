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

from typing import Any
from typing import cast
from typing import Optional

import locale
import logging
from collections import defaultdict

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GObject

from gajim.common import app
from gajim.common import passwords
from gajim.common.const import ClientState
from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.settings import AllSettingsT
from gajim.common import types

from .dialogs import DialogButton
from .dialogs import ConfirmationDialog
from .const import Setting
from .const import SettingKind
from .const import SettingType
from .menus import build_accounts_menu
from .settings import SettingsDialog
from .settings import SettingsBox
from .settings import PopoverSetting
from .util import get_app_window
from .util import open_window

log = logging.getLogger('gajim.gui.accounts')


class AccountsWindow(Gtk.ApplicationWindow):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('AccountsWindow')
        self.set_default_size(700, 550)
        self.set_resizable(True)
        self.set_title(_('Accounts'))
        self._need_relogin: dict[str, list[AllSettingsT]] = {}
        self._accounts: dict[str, Account] = {}

        self._menu = AccountMenu()
        self._settings = Settings()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.add(self._menu)
        box.add(self._settings)
        self.add(box)

        for account in app.get_accounts_sorted():
            self.add_account(account, initial=True)

        self._menu.connect('menu-activated', self._on_menu_activated)
        self.connect('destroy', self._on_destroy)
        self.connect_after('key-press-event', self._on_key_press)

        self.show_all()

    def _on_menu_activated(self,
                           _listbox: Gtk.ListBox,
                           account: str,
                           name: str) -> None:
        if name == 'back':
            self._settings.set_page('add-account')
            self._check_relogin()
        elif name == 'remove':
            self.on_remove_account(account)
        else:
            self._settings.set_page(name)

    def _on_key_press(self,
                      _widget: AccountsWindow,
                      event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, _widget: AccountsWindow) -> None:
        self._check_relogin()
        app.check_finalize(self)

    def update_account_label(self, account: str) -> None:
        self._accounts[account].update_account_label()

    def update_proxy_list(self) -> None:
        for account in self._accounts:
            self._settings.update_proxy_list(account)

    def _check_relogin(self) -> None:
        for account, r_settings in self._need_relogin.items():
            settings = self._get_relogin_settings(account)
            active = app.settings.get_account_setting(account, 'active')
            if settings != r_settings:
                self._need_relogin[account] = settings
                if active:
                    self._relog(account)
                break

    def _relog(self, account: str) -> None:
        if not app.account_is_connected(account):
            return

        def relog():
            client = app.get_client(account)
            client.disconnect(gracefully=True,
                              reconnect=True,
                              destroy_client=True)

        ConfirmationDialog(
            _('Re-Login'),
            _('Re-Login now?'),
            _('To apply all changes instantly, you have to re-login.'),
            [DialogButton.make('Cancel',
                               text=_('_Later')),
             DialogButton.make('Accept',
                               text=_('_Re-Login'),
                               callback=relog)],
            transient_for=self).show()

    @staticmethod
    def _get_relogin_settings(account: str) -> list[AllSettingsT]:
        values: list[AllSettingsT] = []
        values.append(
            app.settings.get_account_setting(account, 'client_cert'))
        values.append(app.settings.get_account_setting(account, 'proxy'))
        values.append(app.settings.get_account_setting(account, 'resource'))
        values.append(
            app.settings.get_account_setting(account, 'use_custom_host'))
        values.append(app.settings.get_account_setting(account, 'custom_host'))
        values.append(app.settings.get_account_setting(account, 'custom_port'))
        return values

    @staticmethod
    def on_remove_account(account: str) -> None:
        open_window('RemoveAccount', account=account)

    def remove_account(self, account: str) -> None:
        del self._need_relogin[account]
        self._accounts[account].remove()

    def add_account(self, account: str, initial: bool = False) -> None:
        self._need_relogin[account] = self._get_relogin_settings(account)
        self._accounts[account] = Account(account, self._menu, self._settings)
        if not initial:
            self._accounts[account].show()

    def select_account(self, account: str, page: Optional[str] = None) -> None:
        try:
            self._accounts[account].select(page)
        except KeyError:
            log.warning('select_account() failed, account %s not found',
                        account)

    def enable_account(self, account: str, state: bool) -> None:
        self._accounts[account].enable_account(state)


class Settings(Gtk.ScrolledWindow):
    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._stack = Gtk.Stack(vhomogeneous=False)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.get_style_context().add_class('settings-stack')
        self._stack.add_named(AddNewAccountPage(), 'add-account')

        self.add(self._stack)
        self._page_signal_ids: dict[GenericSettingPage, int] = {}
        self._pages: dict[str, list[GenericSettingPage]] = defaultdict(list)

    def add_page(self, page: GenericSettingPage) -> None:
        self._pages[page.account].append(page)
        self._stack.add_named(page, f'{page.account}-{page.name}')
        self._page_signal_ids[page] = page.connect_signal(self._stack)

    def set_page(self, name: str) -> None:
        self._stack.set_visible_child_name(name)

    def remove_account(self, account: str) -> None:
        for page in self._pages[account]:
            signal_id = self._page_signal_ids[page]
            del self._page_signal_ids[page]
            self._stack.disconnect(signal_id)
            self._stack.remove(page)
            page.destroy()
        del self._pages[account]

    def update_proxy_list(self, account: str) -> None:
        for page in self._pages[account]:
            if page.name != 'connection':
                continue
            assert isinstance(page, ConnectionPage)
            page.update_proxy_entries()


class AccountMenu(Gtk.Box):

    __gsignals__ = {
        'menu-activated': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        self.set_hexpand(False)
        self.set_size_request(160, -1)

        self.get_style_context().add_class('accounts-menu')

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)

        self._accounts_listbox = Gtk.ListBox()
        self._accounts_listbox.set_sort_func(self._sort_func)
        self._accounts_listbox.get_style_context().add_class(
            'accounts-menu-listbox')
        self._accounts_listbox.connect('row-activated',
                                       self._on_account_row_activated)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self._accounts_listbox)
        self._stack.add_named(scrolled, 'accounts')
        self.add(self._stack)

    @staticmethod
    def _sort_func(row1: AccountRow, row2: AccountRow) -> int:
        return locale.strcoll(row1.label.lower(), row2.label.lower())

    def add_account(self, row: AccountRow) -> None:
        self._accounts_listbox.add(row)
        sub_menu = AccountSubMenu(row.account)
        self._stack.add_named(sub_menu, f'{row.account}-menu')

        sub_menu.connect('row-activated', self._on_sub_menu_row_activated)

    def remove_account(self, row: AccountRow) -> None:
        if self._stack.get_visible_child_name() != 'accounts':
            # activate 'back' button
            listbox = cast(Gtk.ListBox, self._stack.get_visible_child())
            back_row = cast(Gtk.ListBoxRow, listbox.get_row_at_index(1))
            back_row.emit('activate')
        self._accounts_listbox.remove(row)
        sub_menu = self._stack.get_child_by_name(f'{row.account}-menu')
        self._stack.remove(sub_menu)
        row.destroy()
        sub_menu.destroy()

    def _on_account_row_activated(self,
                                  _listbox: Gtk.ListBox,
                                  row: AccountRow
                                  ) -> None:
        self._stack.set_visible_child_name(f'{row.account}-menu')
        listbox = cast(Gtk.ListBox, self._stack.get_visible_child())
        listbox_row = cast(Gtk.ListBoxRow, listbox.get_row_at_index(2))
        listbox_row.emit('activate')

    def _on_sub_menu_row_activated(self,
                                   listbox: AccountSubMenu,
                                   row: MenuItem) -> None:
        if row.name == 'back':
            self._stack.set_visible_child_full(
                'accounts', Gtk.StackTransitionType.OVER_RIGHT)

        if row.name in ('back', 'remove'):
            self.emit('menu-activated', listbox.account, row.name)

        else:
            self.emit('menu-activated',
                      listbox.account,
                      f'{listbox.account}-{row.name}')

    def set_page(self, account: str, page_name: str) -> None:
        sub_menu = cast(
            AccountSubMenu, self._stack.get_child_by_name(f'{account}-menu'))
        sub_menu.select_row_by_name(page_name)
        self.emit('menu-activated', account, f'{account}-{page_name}')

    def update_account_label(self, account: str) -> None:
        self._accounts_listbox.invalidate_sort()
        sub_menu = cast(
            AccountSubMenu, self._stack.get_child_by_name(f'{account}-menu'))
        sub_menu.update()


class AccountSubMenu(Gtk.ListBox):

    __gsignals__ = {
        'update': (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }

    def __init__(self, account: str) -> None:
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.get_style_context().add_class('accounts-menu-listbox')

        self._account = account

        self.add(AccountLabelMenuItem(self, self._account))
        self.add(BackMenuItem())
        self.add(PageMenuItem('general', _('General')))
        self.add(PageMenuItem('privacy', _('Privacy')))
        self.add(PageMenuItem('connection', _('Connection')))
        self.add(PageMenuItem('advanced', _('Advanced')))
        self.add(RemoveMenuItem())

    @property
    def account(self) -> str:
        return self._account

    def select_row_by_name(self, row_name: str) -> None:
        for row in self.get_children():
            if not isinstance(row, PageMenuItem):
                continue
            if row.name == row_name:
                self.select_row(row)
                return

    def update(self) -> None:
        self.emit('update', self._account)


class MenuItem(Gtk.ListBoxRow):
    def __init__(self, name: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        self._name = name
        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=12)
        self._label = Gtk.Label()

        self.add(self._box)

    @property
    def name(self) -> str:
        return self._name


class RemoveMenuItem(MenuItem):
    def __init__(self) -> None:
        super().__init__('remove')
        self._label.set_text(_('Remove'))
        image = Gtk.Image.new_from_icon_name('user-trash-symbolic',
                                             Gtk.IconSize.MENU)

        self.set_selectable(False)
        image.get_style_context().add_class('error-color')

        self._box.add(image)
        self._box.add(self._label)


class AccountLabelMenuItem(MenuItem):
    def __init__(self, parent: AccountSubMenu, account: str) -> None:
        super().__init__('account-label')
        self._update_account_label(parent, account)

        self.set_selectable(False)
        self.set_sensitive(False)
        self.set_activatable(False)

        image = Gtk.Image.new_from_icon_name('avatar-default-symbolic',
                                             Gtk.IconSize.MENU)
        image.get_style_context().add_class('insensitive-fg-color')

        self._label.get_style_context().add_class('accounts-label-row')
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_xalign(0)

        self._box.add(image)
        self._box.add(self._label)

        parent.connect('update', self._update_account_label)

    def _update_account_label(self,
                              _listbox: Gtk.ListBox,
                              account: str
                              ) -> None:
        account_label = app.get_account_label(account)
        self._label.set_text(account_label)


class BackMenuItem(MenuItem):
    def __init__(self) -> None:
        super().__init__('back')
        self.set_selectable(False)

        self._label.set_text(_('Back'))

        image = Gtk.Image.new_from_icon_name('go-previous-symbolic',
                                             Gtk.IconSize.MENU)
        image.get_style_context().add_class('insensitive-fg-color')

        self._box.add(image)
        self._box.add(self._label)


class PageMenuItem(MenuItem):
    def __init__(self, name: str, label: str) -> None:
        super().__init__(name)

        if name == 'general':
            icon = 'preferences-system-symbolic'
        elif name == 'privacy':
            icon = 'preferences-system-privacy-symbolic'
        elif name == 'connection':
            icon = 'preferences-system-network-symbolic'
        elif name == 'advanced':
            icon = 'preferences-other-symbolic'
        else:
            icon = 'dialog-error-symbolic'

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        self._label.set_text(label)

        self._box.add(image)
        self._box.add(self._label)


class Account:
    def __init__(self,
                 account: str,
                 menu: AccountMenu,
                 settings: Settings
                 ) -> None:
        self._account = account
        self._menu = menu
        self._settings = settings

        self._settings.add_page(GeneralPage(account))
        self._settings.add_page(ConnectionPage(account))
        self._settings.add_page(PrivacyPage(account))
        self._settings.add_page(AdvancedPage(account))

        self._account_row = AccountRow(account)
        self._menu.add_account(self._account_row)

    def select(self, page_name: Optional[str] = None) -> None:
        self._account_row.emit('activate')
        if page_name is not None:
            self._menu.set_page(self._account, page_name)

    def show(self) -> None:
        self._menu.show_all()
        self._settings.show_all()
        self.select()

    def remove(self) -> None:
        self._menu.remove_account(self._account_row)
        self._settings.remove_account(self._account)

    def update_account_label(self) -> None:
        self._account_row.update_account_label()
        self._menu.update_account_label(self._account)

    def enable_account(self, state: bool) -> None:
        self._account_row.enable_account(state)

    @property
    def menu(self) -> AccountMenu:
        return self._menu

    @property
    def account(self) -> str:
        return self._account

    @property
    def settings(self) -> str:
        return self._account


class AccountRow(Gtk.ListBoxRow):
    def __init__(self, account: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.set_selectable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self._account = account

        self._label = Gtk.Label(label=app.get_account_label(account))
        self._label.set_halign(Gtk.Align.START)
        self._label.set_hexpand(True)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_xalign(0)
        self._label.set_width_chars(18)

        next_icon = Gtk.Image.new_from_icon_name('go-next-symbolic',
                                                 Gtk.IconSize.MENU)
        next_icon.get_style_context().add_class('insensitive-fg-color')

        account_enabled = app.settings.get_account_setting(
            self._account, 'active')
        self._switch = Gtk.Switch()
        self._switch.set_active(account_enabled)
        self._switch.set_vexpand(False)

        self._switch_state_label = Gtk.Label()
        self._switch_state_label.set_xalign(0)
        self._switch_state_label.set_valign(Gtk.Align.CENTER)
        label_width = max(len(Q_('?switch:On')), len(Q_('?switch:Off')))
        self._switch_state_label.set_width_chars(label_width)
        self._set_label(account_enabled)

        self._switch.connect(
            'state-set', self._on_enable_switch, self._account)

        box.add(self._switch)
        box.add(self._switch_state_label)
        box.add(Gtk.Separator())
        box.add(self._label)
        box.add(next_icon)
        self.add(box)

    @property
    def account(self) -> str:
        return self._account

    @property
    def label(self) -> str:
        return self._label.get_text()

    def update_account_label(self) -> None:
        self._label.set_text(app.get_account_label(self._account))

    def enable_account(self, state: bool) -> None:
        self._switch.set_state(state)
        self._set_label(state)

    def _set_label(self, active: bool) -> None:
        text = Q_('?switch:On') if active else Q_('?switch:Off')
        self._switch_state_label.set_text(text)

    def _on_enable_switch(self,
                          switch: Gtk.Switch,
                          state: bool,
                          account: str
                          ) -> int:

        def _disable() -> None:
            client = app.get_client(account)
            client.connect_signal('state-changed', self._on_state_changed)
            client.change_status('offline', 'offline')
            switch.set_state(state)
            self._set_label(state)

        account_is_active = app.settings.get_account_setting(account, 'active')
        if account_is_active == state:
            return Gdk.EVENT_PROPAGATE

        if (account_is_active and
                not app.get_client(account).state.is_disconnected):
            # Connecting or connected
            window = cast(AccountsWindow, get_app_window('AccountsWindow'))
            account_label = app.get_account_label(account)
            ConfirmationDialog(
                _('Disable Account'),
                _('Account %s is still connected') % account_label,
                _('All chat and group chat windows will be closed.'),
                [DialogButton.make('Cancel',
                                   callback=lambda: switch.set_active(True)),
                 DialogButton.make('Remove',
                                   text=_('_Disable Account'),
                                   callback=_disable)],
                transient_for=window).show()
            return Gdk.EVENT_STOP

        if state:
            app.app.enable_account(account)
        else:
            app.app.disable_account(account)

        return Gdk.EVENT_PROPAGATE

    def _on_state_changed(self,
                          client: types.Client,
                          _signal_name: str,
                          client_state: ClientState
                          ) -> None:

        if client_state.is_disconnected:
            app.app.disable_account(client.account)


class AddNewAccountPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_margin_top(24)
        pixbuf = Gtk.IconTheme.load_icon_for_scale(
            Gtk.IconTheme.get_default(),
            'org.gajim.Gajim-symbolic',
            100,
            self.get_scale_factor(),
            Gtk.IconLookupFlags.FORCE_SIZE)
        self.add(Gtk.Image.new_from_pixbuf(pixbuf))

        button = Gtk.Button(label=_('Add Account'))
        button.get_style_context().add_class('suggested-action')
        button.set_action_name('app.add-account')
        button.set_halign(Gtk.Align.CENTER)
        self.add(button)


class GenericSettingPage(Gtk.Box):

    name = ''

    def __init__(self, account: str, settings: list[Setting]) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_valign(Gtk.Align.START)
        self.set_vexpand(True)
        self.account = account

        self.listbox = SettingsBox(account)
        self.listbox.get_style_context().add_class('border')
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_vexpand(False)
        self.listbox.set_valign(Gtk.Align.END)

        for setting in settings:
            self.listbox.add_setting(setting)
        self.listbox.update_states()

        self.pack_end(self.listbox, True, True, 0)

    def connect_signal(self, stack: Gtk.Stack) -> int:
        return stack.connect('notify::visible-child',
                             self._on_visible_child_changed)

    def _on_visible_child_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        if self == stack.get_visible_child():
            self.listbox.update_states()


class GeneralPage(GenericSettingPage):

    name = 'general'

    def __init__(self, account: str) -> None:

        workspaces = self._get_workspaces()

        settings = [
            Setting(SettingKind.ENTRY,
                    _('Label'),
                    SettingType.ACCOUNT_CONFIG,
                    'account_label',
                    callback=self._on_account_name_change),

            Setting(SettingKind.POPOVER,
                    _('Default Workspace'),
                    SettingType.ACCOUNT_CONFIG,
                    'default_workspace',
                    props={'entries': workspaces},
                    desc=_('Chats from this account will use this workspace by '
                           'default')),

            Setting(SettingKind.COLOR,
                    _('Color'),
                    SettingType.ACCOUNT_CONFIG,
                    'account_color',
                    desc=_('Recognize your account by color')),

            Setting(SettingKind.LOGIN,
                    _('Login'),
                    SettingType.DIALOG,
                    desc=_('Change your account’s password, etc.'),
                    bind='account::anonymous_auth',
                    inverted=True,
                    props={'dialog': LoginDialog}),

            Setting(SettingKind.ACTION,
                    _('Import Contacts'),
                    SettingType.ACTION,
                    '-import-contacts',
                    props={'account': account}),

            # Currently not supported by nbxmpp
            #
            # Setting(SettingKind.DIALOG,
            #         _('Client Certificate'),
            #         SettingType.DIALOG,
            #         props={'dialog': CertificateDialog}),

            Setting(SettingKind.SWITCH,
                    _('Connect on startup'),
                    SettingType.ACCOUNT_CONFIG,
                    'autoconnect'),

            Setting(SettingKind.SWITCH,
                    _('Global Status'),
                    SettingType.ACCOUNT_CONFIG,
                    'sync_with_global_status',
                    desc=_('Synchronise the status of all accounts')),

            Setting(SettingKind.SWITCH,
                    _('Remember Last Status'),
                    SettingType.ACCOUNT_CONFIG,
                    'restore_last_status',
                    desc=_('Restore status and status message of your '
                           'last session')),

            Setting(SettingKind.SWITCH,
                    _('Use file transfer proxies'),
                    SettingType.ACCOUNT_CONFIG,
                    'use_ft_proxies'),
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _get_workspaces() -> dict[str, str]:
        workspaces: dict[str, str] = {'': _('Disabled')}
        for workspace_id in app.settings.get_workspaces():
            name = app.settings.get_workspace_setting(workspace_id, 'name')
            workspaces[workspace_id] = name
        return workspaces

    def _on_account_name_change(self, *args: Any) -> None:
        window = cast(AccountsWindow, get_app_window('AccountsWindow'))
        window.update_account_label(self.account)
        build_accounts_menu()


class PrivacyPage(GenericSettingPage):

    name = 'privacy'

    def __init__(self, account: str) -> None:
        self._account = account
        self._client: Optional[types.Client] = None
        if app.account_is_connected(account):
            self._client = app.get_client(account)

        history_max_age = {
            -1: _('Forever'),
            0: _('Until Gajim is Closed'),
            86400: _('1 Day'),
            604800: _('1 Week'),
            2629743: _('1 Month'),
            7889229: _('3 Months'),
            15778458: _('6 Months'),
            31556926: _('1 Year'),
        }

        chatstate_entries = {
            'all': _('Enabled'),
            'composing_only': _('Composing Only'),
            'disabled': _('Disabled'),
        }

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Idle Time'),
                    SettingType.ACCOUNT_CONFIG,
                    'send_idle_time',
                    callback=self._send_idle_time,
                    desc=_('Disclose the time of your last activity')),

            Setting(SettingKind.SWITCH,
                    _('Local System Time'),
                    SettingType.ACCOUNT_CONFIG,
                    'send_time_info',
                    callback=self._send_time_info,
                    desc=_('Disclose the local system time of the '
                           'device Gajim runs on')),

            Setting(SettingKind.SWITCH,
                    _('Operating System'),
                    SettingType.ACCOUNT_CONFIG,
                    'send_os_info',
                    callback=self._send_os_info,
                    desc=_('Disclose information about the '
                           'operating system you currently use')),

            Setting(SettingKind.SWITCH,
                    _('Media Playback'),
                    SettingType.ACCOUNT_CONFIG,
                    'publish_tune',
                    callback=self._publish_tune,
                    desc=_('Disclose information about media that is '
                           'currently being played on your system.')),

            Setting(SettingKind.SWITCH,
                    _('Ignore Unknown Contacts'),
                    SettingType.ACCOUNT_CONFIG,
                    'ignore_unknown_contacts',
                    desc=_('Ignore everything from contacts not in your '
                           'contact list')),

            Setting(SettingKind.SWITCH,
                    _('Send Message Receipts'),
                    SettingType.ACCOUNT_CONFIG,
                    'answer_receipts',
                    desc=_('Tell your contacts if you received a message')),

            Setting(SettingKind.POPOVER,
                    _('Send Chatstate'),
                    SettingType.ACCOUNT_CONFIG,
                    'send_chatstate_default',
                    desc=_('Default for chats'),
                    props={'entries': chatstate_entries,
                           'button-text': _('Reset'),
                           'button-tooltip': _('Reset all chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_send_chatstate}),

            Setting(SettingKind.POPOVER,
                    _('Send Chatstate in Group Chats'),
                    SettingType.ACCOUNT_CONFIG,
                    'gc_send_chatstate_default',
                    desc=_('Default for group chats'),
                    props={'entries': chatstate_entries,
                           'button-text': _('Reset'),
                           'button-tooltip': _('Reset all group chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_gc_send_chatstate}),

            Setting(SettingKind.SWITCH,
                    _('Send Read Markers'),
                    SettingType.VALUE,
                    app.settings.get_account_setting(
                        account, 'send_marker_default'),
                    callback=self._send_read_marker,
                    desc=_('Default for chats and private group chats'),
                    props={'button-text': _('Reset'),
                           'button-tooltip': _('Reset all chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_send_read_marker}),

            Setting(SettingKind.POPOVER,
                    _('Keep Chat History'),
                    SettingType.ACCOUNT_CONFIG,
                    'chat_history_max_age',
                    props={'entries': history_max_age},
                    desc=_('How long Gajim should keep your chat history')),

            Setting(SettingKind.ACTION,
                    _('Export Chat History'),
                    SettingType.ACTION,
                    '-export-history',
                    props={'account': account},
                    desc=_('Export your chat history from Gajim'))
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _reset_send_chatstate(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings('send_chatstate', None)

    @staticmethod
    def _reset_gc_send_chatstate(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings('send_chatstate', None)

    def _send_idle_time(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module('LastActivity').set_enabled(state)

    def _send_time_info(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module('EntityTime').set_enabled(state)

    def _send_os_info(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module('SoftwareVersion').set_enabled(state)

    def _publish_tune(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module('UserTune').set_enabled(state)

    def _send_read_marker(self, state: bool, _data: Any) -> None:
        app.settings.set_account_setting(
            self._account, 'send_marker_default', state)
        app.settings.set_account_setting(
            self._account, 'gc_send_marker_private_default', state)

    def _reset_send_read_marker(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings('send_marker', None)
        app.settings.set_group_chat_settings(
            'send_marker', None, context='private')


class ConnectionPage(GenericSettingPage):

    name = 'connection'

    def __init__(self, account: str) -> None:

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Proxy'),
                    SettingType.ACCOUNT_CONFIG,
                    'proxy',
                    name='proxy',
                    props={'entries': self._get_proxies(),
                           'default-text': _('System'),
                           'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_proxy_edit}),

            Setting(SettingKind.HOSTNAME,
                    _('Hostname'),
                    SettingType.DIALOG,
                    desc=_('Manually set the hostname for the server'),
                    props={'dialog': CutstomHostnameDialog}),

            Setting(SettingKind.ENTRY,
                    _('Resource'),
                    SettingType.ACCOUNT_CONFIG,
                    'resource'),

            Setting(SettingKind.PRIORITY,
                    _('Priority'),
                    SettingType.DIALOG,
                    props={'dialog': PriorityDialog}),

            Setting(SettingKind.SWITCH,
                    _('Use Unencrypted Connection'),
                    SettingType.ACCOUNT_CONFIG,
                    'use_plain_connection',
                    desc=_('Use an unencrypted connection to the server')),

            Setting(SettingKind.SWITCH,
                    _('Confirm Unencrypted Connection'),
                    SettingType.ACCOUNT_CONFIG,
                    'confirm_unencrypted_connection',
                    desc=_('Show a confirmation dialog before connecting '
                           'unencrypted')),
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _get_proxies() -> dict[str, str]:
        return {proxy: proxy for proxy in app.settings.get_proxies()}

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        open_window('ManageProxies')

    def update_proxy_entries(self) -> None:
        popover_row = cast(PopoverSetting, self.listbox.get_setting('proxy'))
        popover_row.update_entries(self._get_proxies())


class AdvancedPage(GenericSettingPage):

    name = 'advanced'

    def __init__(self, account: str) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Contact Information'),
                    SettingType.ACCOUNT_CONFIG,
                    'request_user_data',
                    desc=_('Request contact information (Tune, Location)')),

            Setting(SettingKind.SWITCH,
                    _('Accept all Contact Requests'),
                    SettingType.ACCOUNT_CONFIG,
                    'autoauth',
                    desc=_('Automatically accept all contact requests')),

            Setting(SettingKind.POPOVER,
                    _('Filetransfer Preference'),
                    SettingType.ACCOUNT_CONFIG,
                    'filetransfer_preference',
                    props={'entries': {'httpupload': _('Upload Files'),
                                       'jingle': _('Send Files Directly')}},
                    desc=_('Preferred file transfer mechanism for '
                           'file drag&drop on a chat window')),
            Setting(SettingKind.SWITCH,
                    _('Security Labels'),
                    SettingType.ACCOUNT_CONFIG,
                    'enable_security_labels',
                    desc=_('Show labels describing confidentiality of '
                           'messages, if the server supports XEP-0258'))
        ]
        GenericSettingPage.__init__(self, account, settings)


class PriorityDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        neg_priority = app.settings.get('enable_negative_priority')
        if neg_priority:
            range_ = (-128, 127)
        else:
            range_ = (0, 127)

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Adjust to status'),
                    SettingType.ACCOUNT_CONFIG,
                    'adjust_priority_with_status'),

            Setting(SettingKind.SPIN,
                    _('Priority'),
                    SettingType.ACCOUNT_CONFIG,
                    'priority',
                    bind='account::adjust_priority_with_status',
                    inverted=True,
                    props={'range_': range_}),
        ]

        SettingsDialog.__init__(self, parent, _('Priority'),
                                Gtk.DialogFlags.MODAL, settings, account)

        self.connect('destroy', self.on_destroy)

    def on_destroy(self, *args: Any) -> None:
        # Update priority
        if self.account not in app.settings.get_active_accounts():
            return
        client = app.get_client(self.account)
        show = client.status
        status = client.status_message
        client.change_status(show, status)


class CutstomHostnameDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        type_values = ('START TLS', 'DIRECT TLS', 'PLAIN')

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Enable'),
                    SettingType.ACCOUNT_CONFIG,
                    'use_custom_host'),

            Setting(SettingKind.ENTRY,
                    _('Hostname'),
                    SettingType.ACCOUNT_CONFIG,
                    'custom_host',
                    bind='account::use_custom_host'),

            Setting(SettingKind.SPIN,
                    _('Port'),
                    SettingType.ACCOUNT_CONFIG,
                    'custom_port',
                    bind='account::use_custom_host',
                    props={'range_': (0, 65535)},),

            Setting(SettingKind.COMBO,
                    _('Type'),
                    SettingType.ACCOUNT_CONFIG,
                    'custom_type',
                    bind='account::use_custom_host',
                    props={'combo_items': type_values}),
        ]

        SettingsDialog.__init__(self, parent, _('Connection Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class CertificateDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(SettingKind.FILECHOOSER,
                    _('Client Certificate'),
                    SettingType.ACCOUNT_CONFIG,
                    'client_cert',
                    props={'filefilter': (_('PKCS12 Files'), '*.p12')}),

            Setting(SettingKind.SWITCH,
                    _('Encrypted Certificate'),
                    SettingType.ACCOUNT_CONFIG,
                    'client_cert_encrypted'),
        ]

        SettingsDialog.__init__(self, parent, _('Certificate Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class LoginDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(SettingKind.ENTRY,
                    _('Password'),
                    SettingType.ACCOUNT_CONFIG,
                    'password',
                    bind='account::savepass'),

            Setting(SettingKind.SWITCH,
                    _('Save Password'),
                    SettingType.ACCOUNT_CONFIG,
                    'savepass',
                    enabled_func=(lambda: not app.settings.get('use_keyring') or
                                  passwords.is_keyring_available())),

            Setting(SettingKind.CHANGEPASSWORD,
                    _('Change Password'),
                    SettingType.DIALOG,
                    callback=self.on_password_change,
                    props={'dialog': None}),

            Setting(SettingKind.SWITCH,
                    _('Use GSSAPI'),
                    SettingType.ACCOUNT_CONFIG,
                    'enable_gssapi'),
        ]

        SettingsDialog.__init__(self, parent, _('Login Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)

        self.connect('destroy', self.on_destroy)

    def on_password_change(self, new_password: str, _data: Any) -> None:
        passwords.save_password(self.account, new_password)

    def on_destroy(self, *args: Any) -> None:
        savepass = app.settings.get_account_setting(self.account, 'savepass')
        if not savepass:
            passwords.delete_password(self.account)
