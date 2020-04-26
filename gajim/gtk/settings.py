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
from gi.repository import GObject
from gi.repository import Pango

from gajim.common import app
from gajim.common import passwords
from gajim.common.i18n import _

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
        self.listbox.connect('row-activated', self.on_row_activated)
        self.connect('key-press-event', self.on_key_press)

    def on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    @staticmethod
    def on_row_activated(_listbox, row):
        row.on_row_activated()

    def get_setting(self, name):
        return self.listbox.get_setting(name)


class SettingsBox(Gtk.ListBox):
    def __init__(self, account, extend=None):
        Gtk.ListBox.__init__(self)
        self.get_style_context().add_class('settings-box')
        self.account = account
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
            SettingKind.PROXY: ProxyComboSetting,
            SettingKind.PRIORITY: PrioritySetting,
            SettingKind.HOSTNAME: CutstomHostnameSetting,
            SettingKind.CHANGEPASSWORD: ChangePasswordSetting,
            SettingKind.COMBO: ComboSetting,
            SettingKind.CHATSTATE_COMBO: ChatstateComboSetting,
        }

        if extend is not None:
            for setting, callback in extend:
                self.map[setting] = callback

    def add_setting(self, setting):
        if not isinstance(setting, Gtk.ListBoxRow):
            if setting.props is not None:
                listitem = self.map[setting.kind](
                    self.account, *setting[1:-1], **setting.props)
            else:
                listitem = self.map[setting.kind](self.account, *setting[1:-1])
        listitem.connect('notify::setting-value', self.on_setting_changed)
        if setting.name is not None:
            self.named_settings[setting.name] = listitem
        self.add(listitem)

    def get_setting(self, name):
        return self.named_settings[name]

    def update_states(self):
        values = []
        values.append((None, None))
        for row in self.get_children():
            name = row.name
            if name is None:
                continue
            value = row.get_property('setting-value')
            values.append((name, value))

        for name, value in values:
            for row in self.get_children():
                row.update_activatable(name, value)

    def on_setting_changed(self, widget, *args):
        value = widget.get_property('setting-value')
        for row in self.get_children():
            row.update_activatable(widget.name, value)


class GenericSetting(Gtk.ListBoxRow):
    def __init__(self, account, label, type_, value,
                 name, callback, data, desc, enabledif, enabled_func):
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
        self.name = name
        self.enabledif = enabledif
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

        self.setting_box = Gtk.Box(spacing=6)
        self.setting_box.set_size_request(200, -1)
        self.setting_box.set_valign(Gtk.Align.CENTER)
        self.setting_box.set_name('GenericSettingBox')
        self._grid.add(self.setting_box)
        self.add(self._grid)

    def do_get_property(self, prop):
        if prop.name == 'setting-value':
            return self.setting_value
        raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'setting-value':
            self.setting_value = value
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def get_value(self):
        return self.__get_value(self.type_, self.value, self.account)

    @staticmethod
    def __get_value(type_, value, account):
        if value is None:
            return None
        if type_ == SettingType.VALUE:
            return value

        if type_ == SettingType.CONFIG:
            return app.config.get(value)

        if type_ == SettingType.ACCOUNT_CONFIG:
            if value == 'password':
                return passwords.get_password(account)
            if value == 'no_log_for':
                no_log = app.config.get_per(
                    'accounts', account, 'no_log_for').split()
                return account not in no_log
            return app.config.get_per('accounts', account, value)

        if type_ == SettingType.ACTION:
            if value.startswith('-'):
                return account + value
            return value

        raise ValueError('Wrong SettingType?')

    def set_value(self, state):
        if self.type_ == SettingType.CONFIG:
            app.config.set(self.value, state)
        if self.type_ == SettingType.ACCOUNT_CONFIG:
            if self.value == 'password':
                passwords.save_password(self.account, state)
            if self.value == 'no_log_for':
                self.set_no_log_for(self.account, state)
            else:
                app.config.set_per('accounts', self.account, self.value, state)

        if self.callback is not None:
            self.callback(state, self.data)

        self.set_property('setting-value', state)

    @staticmethod
    def set_no_log_for(account, state):
        no_log = app.config.get_per('accounts', account, 'no_log_for').split()
        if state and account in no_log:
            no_log.remove(account)
        elif not state and account not in no_log:
            no_log.append(account)
        app.config.set_per('accounts', account, 'no_log_for', ' '.join(no_log))

    def on_row_activated(self):
        raise NotImplementedError

    def update_activatable(self, name, value):
        enabled_func_value = True
        if self.enabled_func is not None:
            enabled_func_value = self.enabled_func()

        enabledif_value = True
        if self.enabledif is not None and self.enabledif[0] == name:
            enabledif_value = (name, value) == self.enabledif

        self.set_activatable(enabled_func_value and enabledif_value)
        self.set_sensitive(enabled_func_value and enabledif_value)


class SwitchSetting(GenericSetting):

    __gproperties__ = {
        "setting-value": (bool, 'Switch Value', '', False,
                          GObject.ParamFlags.READWRITE),}

    def __init__(self, *args):
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

        self.setting_box.add(self.switch)

        self.show_all()

    def on_row_activated(self):
        state = self.switch.get_active()
        self.switch.set_active(not state)

    def on_switch(self, switch, *args):
        value = switch.get_active()
        self.set_value(value)


class EntrySetting(GenericSetting):

    __gproperties__ = {
        "setting-value": (str, 'Entry Value', '', '',
                          GObject.ParamFlags.READWRITE),}

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

    __gproperties__ = {
        "setting-value": (str, 'Color Value', '', '',
                          GObject.ParamFlags.READWRITE),
    }

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

    __gproperties__ = {
        "setting-value": (str, 'Dummy', '', '',
                          GObject.ParamFlags.READWRITE),}

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

    __gproperties__ = {
        "setting-value": (int, 'Priority', '', -128, 127, 0,
                          GObject.ParamFlags.READWRITE),}

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

    __gproperties__ = {
        "setting-value": (str, 'Certificate Path', '', '',
                          GObject.ParamFlags.READWRITE),}

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

    __gproperties__ = {
        "setting-value": (str, 'Dummy', '', '',
                          GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, callback):
        GenericSetting.__init__(self, *args)
        self.callback = callback
        self.show_all()

    def on_row_activated(self):
        self.callback()


class ActionSetting(GenericSetting):

    __gproperties__ = {
        "setting-value": (str, 'Dummy', '', '',
                          GObject.ParamFlags.READWRITE),}

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

    def update_activatable(self, name, value):
        super().update_activatable(name, value)
        anonym = app.config.get_per('accounts', self.account, 'anonymous_auth')
        self.set_activatable(not anonym)


class ComboSetting(GenericSetting):

    __gproperties__ = {
        "setting-value": (str, 'Proxy', '', '',
                          GObject.ParamFlags.READWRITE),}

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


class ChatstateComboSetting(ComboSetting):
    def on_value_change(self, combo):
        self.set_value(combo.get_active_id())
        if 'muc' in self.value:
            app.config.del_all_per('rooms', 'send_chatstate')
        else:
            app.config.del_all_per('contacts', 'send_chatstate')


class ProxyComboSetting(GenericSetting):

    __gproperties__ = {
        "setting-value": (str, 'Proxy', '', '',
                          GObject.ParamFlags.READWRITE),}

    def __init__(self, *args):
        GenericSetting.__init__(self, *args)

        self.combo = MaxWidthComboBoxText()
        self.combo.set_valign(Gtk.Align.CENTER)

        self._signal_id = None
        self.update_values()

        button = get_image_button(
            'preferences-system-symbolic', _('Manage Proxies'))
        button.set_action_name('app.manage-proxies')
        button.set_valign(Gtk.Align.CENTER)

        self.setting_box.pack_start(self.combo, True, True, 0)
        self.setting_box.pack_start(button, False, True, 0)
        self.show_all()

    def _block_signal(self, state):
        if state:
            if self._signal_id is None:
                return
            self.combo.disconnect(self._signal_id)
        else:
            self._signal_id = self.combo.connect('changed',
                                                 self.on_value_change)
            self.combo.emit('changed')

    def update_values(self):
        self._block_signal(True)
        proxies = app.config.get_per('proxies')
        proxies.insert(0, _('No Proxy'))
        self.combo.remove_all()
        for index, value in enumerate(proxies):
            self.combo.insert_text(-1, value)
            if value == self.setting_value or index == 0:
                self.combo.set_active(index)
        self._block_signal(False)

    def on_value_change(self, combo):
        if combo.get_active() == 0:
            self.set_value('')
        else:
            self.set_value(combo.get_active_text())

    def on_row_activated(self):
        pass


class PrioritySetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        adjust = app.config.get_per(
            'accounts', self.account, 'adjust_priority_with_status')
        if adjust:
            return _('Adjust to Status')

        priority = app.config.get_per('accounts', self.account, 'priority')
        return str(priority)


class CutstomHostnameSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self):
        custom = app.config.get_per('accounts', self.account, 'use_custom_host')
        return _('On') if custom else _('Off')


class ChangePasswordSetting(DialogSetting):
    def __init__(self, *args, **kwargs):
        DialogSetting.__init__(self, *args, **kwargs)

    def show_dialog(self, parent):
        parent.destroy()
        open_window('ChangePassword', account=self.account)

    def update_activatable(self, name, value):
        activatable = False
        if self.account in app.connections:
            con = app.connections[self.account]
            activatable = con.state.is_available and con.register_supported
        self.set_activatable(activatable)
