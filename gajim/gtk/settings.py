# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Pango

from gajim.common import app
from gajim.common import passwords
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from gajim import gtkgui_helpers

from gajim.gtk.util import get_image_button
from gajim.gtk.util import MaxWidthComboBoxText
from gajim.gtk.util import open_window
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType


class SettingsDialog(Gtk.ApplicationWindow):
    def __init__(self, parent, title, flags, settings, account,
                 extend=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_title(title)
        self.set_transient_for(parent)
        self.set_resizable(False)
        self.set_default_size(250, -1)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_style_context().add_class('settings-dialog')
        self.account = account
        if flags == Gtk.DialogFlags.MODAL:
            self.set_modal(True)
        elif flags == Gtk.DialogFlags.DESTROY_WITH_PARENT:
            self.set_destroy_with_parent(True)

        self.listbox = SettingsBox(account, extend)
        self.listbox.set_hexpand(True)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for setting in settings:
            self.listbox.add_setting(setting)
        self.listbox.update_states()

        self.add(self.listbox)

        self.show_all()
        self.connect_after('key-press-event', self.on_key_press)

    def on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_setting(self, name):
        return self.listbox.get_setting(name)


class SettingsBox(Gtk.ListBox):
    def __init__(self, account=None, jid=None, context=None, extend=None):
        Gtk.ListBox.__init__(self)
        self.get_style_context().add_class('settings-box')
        self.account = account
        self.jid = jid
        self.context = context
        self.named_settings = {}

        self.map = {
            SettingKind.SWITCH: SwitchSetting,
            SettingKind.SPIN: SpinSetting,
            SettingKind.DIALOG: DialogSetting,
            SettingKind.ENTRY: EntrySetting,
            SettingKind.COLOR: ColorSetting,
            SettingKind.ACTION: ActionSetting,
            SettingKind.LOGIN: LoginSetting,
            SettingKind.FILECHOOSER: FileChooserSetting,
            SettingKind.CALLBACK: CallbackSetting,
            SettingKind.PRIORITY: PrioritySetting,
            SettingKind.HOSTNAME: CutstomHostnameSetting,
            SettingKind.CHANGEPASSWORD: ChangePasswordSetting,
            SettingKind.COMBO: ComboSetting,
            SettingKind.POPOVER: PopoverSetting,
            SettingKind.AUTO_AWAY: CutstomAutoAwaySetting,
            SettingKind.AUTO_EXTENDED_AWAY: CutstomAutoExtendedAwaySetting,
            SettingKind.USE_STUN_SERVER: CutstomStunServerSetting
        }

        if extend is not None:
            for setting, callback in extend:
                self.map[setting] = callback

        self.connect('row-activated', self.on_row_activated)

    @staticmethod
    def on_row_activated(_listbox, row):
        row.on_row_activated()

    def add_setting(self, setting):
        if not isinstance(setting, Gtk.ListBoxRow):
            if setting.props is not None:
                listitem = self.map[setting.kind](self.account,
                                                  self.jid,
                                                  self.context,
                                                  *setting[1:-1],
                                                  **setting.props)
            else:
                listitem = self.map[setting.kind](self.account,
                                                  self.jid,
                                                  self.context,
                                                  *setting[1:-1])

        if setting.name is not None:
            self.named_settings[setting.name] = listitem
        self.add(listitem)

    def get_setting(self, name):
        return self.named_settings[name]

    def update_states(self):
        for row in self.get_children():
            row.update_activatable()


class GenericSetting(Gtk.ListBoxRow):
    def __init__(self,
                 account,
                 jid,
                 context,
                 label,
                 type_,
                 value,
                 name,
                 callback,
                 data,
                 desc,
                 bind,
                 inverted,
                 enabled_func):
        Gtk.ListBoxRow.__init__(self)
        self._grid = Gtk.Grid()
        self._grid.set_size_request(-1, 30)
        self._grid.set_column_spacing(12)

        self.callback = callback
        self.type_ = type_
        self.value = value
        self.data = data
        self.label = label
        self.account = account
        self.jid = jid
        self.context = context
        self.name = name
        self.bind = bind
        self.inverted = inverted
        self.enabled_func = enabled_func
        self.setting_value = self.get_value()

        description_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0)
        description_box.set_valign(Gtk.Align.CENTER)

        settingtext = Gtk.Label(label=label)
        settingtext.set_hexpand(True)
        settingtext.set_halign(Gtk.Align.START)
        settingtext.set_valign(Gtk.Align.CENTER)
        settingtext.set_vexpand(True)
        description_box.add(settingtext)

        if desc is not None:
            description = Gtk.Label(label=desc)
            description.set_name('SubDescription')
            description.set_hexpand(True)
            description.set_halign(Gtk.Align.START)
            description.set_valign(Gtk.Align.CENTER)
            description.set_xalign(0)
            description.set_line_wrap(True)
            description.set_line_wrap_mode(Pango.WrapMode.WORD)
            description.set_max_width_chars(50)
            description_box.add(description)

        self._grid.add(description_box)

        self.setting_box = Gtk.Box(spacing=12)
        self.setting_box.set_size_request(200, -1)
        self.setting_box.set_valign(Gtk.Align.CENTER)
        self.setting_box.set_name('GenericSettingBox')
        self._grid.add(self.setting_box)
        self.add(self._grid)

        self._bind_sensitive_state()

    def _bind_sensitive_state(self):
        if self.bind is None:
            return

        app.settings.bind_signal(self.bind,
                                 self,
                                 'set_sensitive',
                                 account=self.account,
                                 inverted=self.inverted)

        if self.type_ == SettingType.CONTACT:
            value = app.settings.get_contact_setting(
                self.account, self.jid, self.bind)

        elif self.type_ == SettingType.GROUP_CHAT:
            value = app.settings.get_group_chat_setting(
                self.account, self.jid, self.bind)

        elif self.type_ == SettingType.ACCOUNT_CONFIG:
            value = app.settings.get_account_setting(self.account, self.bind)

        else:
            value = app.settings.get(self.bind)

        if self.inverted:
            value = not value
        self.set_sensitive(value)

    def get_value(self):
        return self.__get_value(self.type_,
                                self.value,
                                self.account,
                                self.jid,
                                self.context)

    @staticmethod
    def __get_value(type_, value, account, jid, context):
        if value is None:
            return None
        if type_ == SettingType.VALUE:
            return value

        if type_ == SettingType.CONTACT:
            return app.settings.get_contact_setting(account, jid, value)

        if type_ == SettingType.GROUP_CHAT:
            value = app.settings.get_group_chat_setting(
                account, jid, value, context)

        if type_ == SettingType.CONFIG:
            return app.settings.get(value)

        if type_ == SettingType.ACCOUNT_CONFIG:
            if value == 'password':
                return passwords.get_password(account)
            if value == 'no_log_for':
                no_log = app.settings.get_account_setting(
                    account, 'no_log_for').split()
                return account not in no_log
            return app.settings.get_account_setting(account, value)

        if type_ == SettingType.ACTION:
            if value.startswith('-'):
                return account + value
            return value

        raise ValueError('Wrong SettingType?')

    def set_value(self, state):
        if self.type_ == SettingType.CONFIG:
            app.settings.set(self.value, state)

        elif self.type_ == SettingType.ACCOUNT_CONFIG:
            if self.value == 'password':
                passwords.save_password(self.account, state)
            if self.value == 'no_log_for':
                self.set_no_log_for(self.account, state)
            else:
                app.settings.set_account_setting(self.account,
                                                 self.value,
                                                 state)

        elif self.type_ == SettingType.CONTACT:
            app.settings.set_contact_setting(
                self.account, self.jid, self.value, state)

        elif self.type_ == SettingType.GROUP_CHAT:
            app.settings.set_group_chat_setting(
                self.account, self.jid, self.value, state, self.context)

        if self.callback is not None:
            self.callback(state, self.data)

    @staticmethod
    def set_no_log_for(account, state):
        no_log = app.settings.get_account_setting(account, 'no_log_for').split()
        if state and account in no_log:
            no_log.remove(account)
        elif not state and account not in no_log:
            no_log.append(account)
        app.settings.set_account_setting(account,
                                         'no_log_for',
                                         ' '.join(no_log))

    def on_row_activated(self):
        raise NotImplementedError

    def update_activatable(self):
        if self.enabled_func is None:
            return

        enabled_func_value = self.enabled_func()
        self.set_activatable(enabled_func_value)
        self.set_sensitive(enabled_func_value)

    def _add_action_button(self, kwargs):
        icon_name = kwargs.get('button-icon-name')
        button_text = kwargs.get('button-text')
        tooltip_text = kwargs.get('button-tooltip') or ''
        style = kwargs.get('button-style')

        if icon_name is not None:
            button = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.MENU)

        elif button_text is not None:
            button = Gtk.Button(label=button_text)

        else:
            return

        if style is not None:
            for css_class in style.split(' '):
                button.get_style_context().add_class(css_class)

        button.connect('clicked', kwargs['button-callback'])
        button.set_tooltip_text(tooltip_text)
        self.setting_box.add(button)


class SwitchSetting(GenericSetting):
    def __init__(self, *args, **kwargs):
        GenericSetting.__init__(self, *args)

        self.switch = Gtk.Switch()
        if self.type_ == SettingType.ACTION:
            self.switch.set_action_name('app.%s' % self.setting_value)
            state = app.app.get_action_state(self.setting_value)
            self.switch.set_active(state.get_boolean())
        else:
            self.switch.set_active(self.setting_value)
        self.switch.connect('notify::active', self.on_switch)
        self.switch.set_hexpand(True)
        self.switch.set_halign(Gtk.Align.END)
        self.switch.set_valign(Gtk.Align.CENTER)

        self._switch_state_label = Gtk.Label()
        self._switch_state_label.set_xalign(1)
        self._switch_state_label.set_valign(Gtk.Align.CENTER)
        self._set_label(self.setting_value)

        box = Gtk.Box(spacing=12)
        box.set_halign(Gtk.Align.END)
        box.add(self._switch_state_label)
        box.add(self.switch)
        self.setting_box.add(box)

        self._add_action_button(kwargs)

        self.show_all()

    def on_row_activated(self):
        state = self.switch.get_active()
        self.switch.set_active(not state)

    def on_switch(self, switch, *args):
        value = switch.get_active()
        self.set_value(value)
        self._set_label(value)

    def _set_label(self, active):
        text = Q_('?switch:On') if active else Q_('?switch:Off')
        self._switch_state_label.set_text(text)


class EntrySetting(GenericSetting):
    def __init__(self, *args):
        GenericSetting.__init__(self, *args)

        self.entry = Gtk.Entry()
        self.entry.set_text(str(self.setting_value))
        self.entry.connect('notify::text', self.on_text_change)
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_alignment(1)

        if self.value == 'password':
            self.entry.set_invisible_char('*')
            self.entry.set_visibility(False)

        self.setting_box.pack_end(self.entry, True, True, 0)

        self.show_all()

    def on_text_change(self, *args):
        text = self.entry.get_text()
        self.set_value(text)

    def on_row_activated(self):
        self.entry.grab_focus()


class ColorSetting(GenericSetting):
    def __init__(self, *args):
        GenericSetting.__init__(self, *args)

        rgba = Gdk.RGBA()
        rgba.parse(self.setting_value)
        self.color_button = Gtk.ColorButton()
        self.color_button.set_rgba(rgba)
        self.color_button.connect('color-set', self.on_color_set)
        self.color_button.set_valign(Gtk.Align.CENTER)
        self.color_button.set_halign(Gtk.Align.END)

        self.setting_box.pack_end(self.color_button, True, True, 0)

        self.show_all()

    def on_color_set(self, button):
        rgba = button.get_rgba()
        self.set_value(rgba.to_string())
        app.css_config.refresh()

    def on_row_activated(self):
        self.color_button.grab_focus()


class DialogSetting(GenericSetting):
    def __init__(self, *args, dialog):
        GenericSetting.__init__(self, *args)
        self.dialog = dialog

        self.setting_value = Gtk.Label()
        self.setting_value.set_text(self.get_setting_value())
        self.setting_value.set_halign(Gtk.Align.END)
        self.setting_box.pack_start(self.setting_value, True, True, 0)

        self.show_all()

    def show_dialog(self, parent):
        if self.dialog:
            dialog = self.dialog(self.account, parent)
            dialog.connect('destroy', self.on_destroy)

    def on_destroy(self, *args):
        self.setting_value.set_text(self.get_setting_value())

    def get_setting_value(self):
        self.setting_value.hide()
        return ''

    def on_row_activated(self):
        self.show_dialog(self.get_toplevel())


class SpinSetting(GenericSetting):
    def __init__(self, *args, range_):
        GenericSetting.__init__(self, *args)

        lower, upper = range_
        adjustment = Gtk.Adjustment(value=0,
                                    lower=lower,
                                    upper=upper,
                                    step_increment=1,
                                    page_increment=10,
                                    page_size=0)

        self.spin = Gtk.SpinButton()
        self.spin.set_adjustment(adjustment)
        self.spin.set_numeric(True)
        self.spin.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)
        self.spin.set_value(self.setting_value)
        self.spin.set_halign(Gtk.Align.END)
        self.spin.set_valign(Gtk.Align.CENTER)
        self.spin.connect('notify::value', self.on_value_change)

        self.setting_box.pack_start(self.spin, True, True, 0)

        self.show_all()

    def on_row_activated(self):
        self.spin.grab_focus()

    def on_value_change(self, spin, *args):
        value = spin.get_value_as_int()
        self.set_value(value)


class FileChooserSetting(GenericSetting):
    def __init__(self, *args, filefilter):
        GenericSetting.__init__(self, *args)

        button = Gtk.FileChooserButton(title=self.label,
                                       action=Gtk.FileChooserAction.OPEN)
        button.set_halign(Gtk.Align.END)

        # GTK Bug: The FileChooserButton expands without limit
        # get the label and use set_max_wide_chars()
        label = button.get_children()[0].get_children()[0].get_children()[1]
        label.set_max_width_chars(20)

        if filefilter:
            name, pattern = filefilter
            filter_ = Gtk.FileFilter()
            filter_.set_name(name)
            filter_.add_pattern(pattern)
            button.add_filter(filter_)
            button.set_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        button.add_filter(filter_)

        if self.setting_value:
            button.set_filename(self.setting_value)
        button.connect('selection-changed', self.on_select)

        clear_button = get_image_button(
            'edit-clear-all-symbolic', _('Clear File'))
        clear_button.connect('clicked', lambda *args: button.unselect_all())
        self.setting_box.pack_start(button, True, True, 0)
        self.setting_box.pack_start(clear_button, False, False, 0)

        self.show_all()

    def on_select(self, filechooser):
        self.set_value(filechooser.get_filename() or '')

    def on_row_activated(self):
        pass


class CallbackSetting(GenericSetting):
    def __init__(self, *args, callback):
        GenericSetting.__init__(self, *args)
        self.callback = callback
        self.show_all()

    def on_row_activated(self):
        self.callback()


class ActionSetting(GenericSetting):
    def __init__(self, *args, account):
        GenericSetting.__init__(self, *args)
        action_name = '%s%s' % (account, self.value)
        self.action = gtkgui_helpers.get_action(action_name)
        self.variant = GLib.Variant.new_string(account)
        self.on_enable()

        self.show_all()
        self.action.connect('notify::enabled', self.on_enable)

    def on_enable(self, *args):
        self.set_sensitive(self.action.get_enabled())

    def on_row_activated(self):
        self.action.activate(self.variant)


class LoginSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)
        self.setting_value.set_selectable(True)

    def get_setting_value(self):
        jid = app.get_jid_from_account(self.account)
        return jid


class PopoverSetting(GenericSetting):
    def __init__(self, *args, entries, **kwargs):
        GenericSetting.__init__(self, *args)

        self._entries = self._convert_to_dict(entries)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                      spacing=12)
        box.set_halign(Gtk.Align.END)
        box.set_hexpand(True)

        self._default_text = kwargs.get('default-text')

        self._current_label = Gtk.Label()
        self._current_label.set_valign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_icon_name('pan-down-symbolic',
                                             Gtk.IconSize.MENU)
        image.set_valign(Gtk.Align.CENTER)

        box.add(self._current_label)
        box.add(image)

        self._menu_listbox = Gtk.ListBox()
        self._menu_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._add_menu_entries()
        self._menu_listbox.connect('row-activated',
                                   self._on_menu_row_activated)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_propagate_natural_height(True)
        scrolled_window.set_propagate_natural_width(True)
        scrolled_window.set_max_content_height(400)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self._menu_listbox)
        scrolled_window.show_all()

        self._popover = Gtk.Popover()
        self._popover.get_style_context().add_class('combo')
        self._popover.set_relative_to(image)
        self._popover.set_position(Gtk.PositionType.BOTTOM)
        self._popover.add(scrolled_window)

        self.setting_box.add(box)

        self._add_action_button(kwargs)

        text = self._entries.get(self.setting_value, self._default_text or '')
        self._current_label.set_text(text)

        self._bind_label()

        self.connect('destroy', self._on_destroy)

        self.show_all()

    @staticmethod
    def _convert_to_dict(entries):
        if isinstance(entries, list):
            entries = {key: key for key in entries}
        return entries

    def _bind_label(self):
        if self.type_ not in (SettingType.CONFIG, SettingType.ACCOUNT_CONFIG):
            return

        app.settings.connect_signal(self.value,
                                    self._on_setting_changed,
                                    account=self.account)

    def _on_setting_changed(self, value, *args):
        text = self._entries.get(value)
        if text is None:
            text = self._default_text or ''

        self._current_label.set_text(text)

    def _add_menu_entries(self):
        if self._default_text is not None:
            self._menu_listbox.add(PopoverRow(self._default_text, ''))

        for value, label in self._entries.items():
            self._menu_listbox.add(PopoverRow(label, value))

        self._menu_listbox.show_all()

    def _on_menu_row_activated(self, listbox, row):
        listbox.unselect_all()
        self._popover.popdown()

        self.set_value(row.value)

    def on_row_activated(self):
        self._popover.popup()

    def update_entries(self, entries):
        self._entries = self._convert_to_dict(entries)
        self._menu_listbox.foreach(self._menu_listbox.remove)
        self._add_menu_entries()

    def _on_destroy(self, *args):
        app.settings.disconnect_signals(self)


class PopoverRow(Gtk.ListBoxRow):
    def __init__(self, label, value):
        Gtk.ListBoxRow.__init__(self)
        self.label = label
        self.value = value

        label = Gtk.Label(label=label)
        label.set_xalign(0)
        self.add(label)


class ComboSetting(GenericSetting):
    def __init__(self, *args, combo_items):
        GenericSetting.__init__(self, *args)

        self.combo = MaxWidthComboBoxText()
        self.combo.set_valign(Gtk.Align.CENTER)

        for index, value in enumerate(combo_items):
            if isinstance(value, tuple):
                value, label = value
                self.combo.append(value, _(label))
            else:
                self.combo.append(value, value)
            if value == self.setting_value or index == 0:
                self.combo.set_active(index)

        self.combo.connect('changed', self.on_value_change)

        self.setting_box.pack_start(self.combo, True, True, 0)
        self.show_all()

    def on_value_change(self, combo):
        self.set_value(combo.get_active_id())

    def on_row_activated(self):
        pass


class PrioritySetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        adjust = app.settings.get_account_setting(
            self.account, 'adjust_priority_with_status')
        if adjust:
            return _('Adjust to Status')

        priority = app.settings.get_account_setting(self.account, 'priority')
        return str(priority)


class CutstomHostnameSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        custom = app.settings.get_account_setting(self.account,
                                                  'use_custom_host')
        return Q_('?switch:On') if custom else Q_('?switch:Off')


class ChangePasswordSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def show_dialog(self, parent):
        parent.destroy()
        open_window('ChangePassword', account=self.account)

    def update_activatable(self):
        activatable = False
        if self.account in app.connections:
            con = app.connections[self.account]
            activatable = (con.state.is_available and
                           con.get_module('Register').supported)
        self.set_activatable(activatable)


class CutstomAutoAwaySetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        value = app.settings.get('autoaway')
        return Q_('?switch:On') if value else Q_('?switch:Off')


class CutstomAutoExtendedAwaySetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        value = app.settings.get('autoxa')
        return Q_('?switch:On') if value else Q_('?switch:Off')


class CutstomStunServerSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        value = app.settings.get('use_stun_server')
        return Q_('?switch:On') if value else Q_('?switch:Off')
