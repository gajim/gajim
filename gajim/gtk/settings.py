# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import get_args

import logging
from collections.abc import Callable

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import passwords
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.setting_values import AllSettingsT
from gajim.common.setting_values import FloatSettings

from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.util import get_image_button
from gajim.gtk.util import MaxWidthComboBoxText
from gajim.gtk.util import open_window

log = logging.getLogger('gajim.gtk.settings')


class SettingsDialog(Gtk.ApplicationWindow):
    def __init__(self,
                 parent: Gtk.Window,
                 title: str,
                 flags: Gtk.DialogFlags,
                 settings: list[Setting],
                 account: str,
                 extend: dict[SettingKind, GenericSetting] | None = None
                 ) -> None:
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

        self.listbox = SettingsBox(account, extend=extend)
        self.listbox.set_hexpand(True)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for setting in settings:
            self.listbox.add_setting(setting)
        self.listbox.update_states()

        self.add(self.listbox)

        self.show_all()
        self.connect_after('key-press-event', self.on_key_press)
        self.connect_after('destroy', self.__on_destroy)

    def __on_destroy(self, widget: SettingsDialog) -> None:
        app.check_finalize(self)

    def on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_setting(self, name: str):
        return self.listbox.get_setting(name)


class SettingsBox(Gtk.ListBox):
    def __init__(self,
                 account: str | None = None,
                 jid: str | None = None,
                 extend: dict[SettingKind, GenericSetting] | None = None
                 ) -> None:
        Gtk.ListBox.__init__(self)
        self.get_style_context().add_class('settings-box')
        self.account = account
        self.jid = jid
        self.named_settings: dict[str, GenericSetting] = {}

        self.map: dict[SettingKind, GenericSetting] = {
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
            SettingKind.USE_STUN_SERVER: CustomStunServerSetting,
            SettingKind.NOTIFICATIONS: NotificationsSetting,
        }

        if extend is not None:
            for setting, callback in extend:
                self.map[setting] = callback

        self.connect('row-activated', self.on_row_activated)
        self.connect('destroy', self.__on_destroy)

    @staticmethod
    def __on_destroy(widget: SettingsBox) -> None:
        app.check_finalize(widget)
        for row in widget.get_children():
            app.check_finalize(row)

    @staticmethod
    def on_row_activated(_listbox: SettingsBox, row: GenericSetting) -> None:
        row.on_row_activated()

    def add_setting(self, setting: Setting) -> None:
        if not isinstance(setting, Gtk.ListBoxRow):
            if setting.props is not None:
                listitem = self.map[setting.kind](self.account,
                                                  self.jid,
                                                  *setting[1:-1],
                                                  **setting.props)
            else:
                listitem = self.map[setting.kind](self.account,
                                                  self.jid,
                                                  *setting[1:-1])

        if setting.name is not None:
            self.named_settings[setting.name] = listitem
        self.add(listitem)

    def get_setting(self, name: str) -> GenericSetting:
        return self.named_settings[name]

    def update_states(self) -> None:
        for row in cast(list[GenericSetting], self.get_children()):
            row.update_activatable()


class GenericSetting(Gtk.ListBoxRow):
    def __init__(self,
                 account: str,
                 jid: JID,
                 label: str,
                 type_: SettingType,
                 value: AllSettingsT,
                 name: str | None,
                 callback: Callable[..., None] | None = None,
                 data: Any | None = None,
                 desc: str | None = None,
                 bind: str | None = None,
                 inverted: bool = False,
                 enabled_func: Callable[..., bool] | None = None
                 ) -> None:

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
        self.name = name
        self.bind = bind
        self.inverted = inverted
        self.enabled_func = enabled_func
        self.setting_value = self.get_value()

        self._locked_icon = Gtk.Image.new_from_icon_name(
            'feather-lock-symbolic',
            Gtk.IconSize.MENU)
        self._locked_icon.set_visible(False)
        self._locked_icon.set_no_show_all(True)
        self._locked_icon.set_halign(Gtk.Align.END)
        self._locked_icon.set_tooltip_text(_('Setting is locked by the system'))

        self._grid.add(self._locked_icon)

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

    def _bind_sensitive_state(self) -> None:
        if self.bind is None:
            return

        bind_setting_type, setting, account, jid = self._parse_bind()

        app.settings.bind_signal(setting,
                                 self,
                                 'set_sensitive',
                                 account=account,
                                 jid=jid,
                                 inverted=self.inverted)

        if bind_setting_type == SettingType.CONTACT:
            value = app.settings.get_contact_setting(account, jid, setting)

        elif bind_setting_type == SettingType.GROUP_CHAT:
            value = app.settings.get_group_chat_setting(account, jid, setting)

        elif bind_setting_type == SettingType.ACCOUNT_CONFIG:
            value = app.settings.get_account_setting(account, setting)

        else:
            value = app.settings.get(setting)

        if self.inverted:
            value = not value
        self.set_sensitive(value)

    def _parse_bind(self) -> tuple[SettingType,
                                   str,
                                   str | None,
                                   JID | None]:
        assert self.bind is not None
        if '::' not in self.bind:
            return SettingType.CONFIG, self.bind, None, None

        bind_setting_type, setting = self.bind.split('::')
        if bind_setting_type == 'account':
            return SettingType.ACCOUNT_CONFIG, setting, self.account, None

        if bind_setting_type == 'contact':
            return SettingType.CONTACT, setting, self.account, self.jid

        if bind_setting_type == 'group_chat':
            return SettingType.GROUP_CHAT, setting, self.account, self.jid
        raise ValueError(f'Invalid bind argument: {self.bind}')

    def get_value(self):
        return self.__get_value(self.type_,
                                self.value,
                                self.account,
                                self.jid)

    @staticmethod
    def __get_value(type_: SettingType,
                    value: AllSettingsT,
                    account: str,
                    jid: JID
                    ) -> AllSettingsT | None:
        if value is None:
            return None
        if type_ == SettingType.VALUE:
            return value

        if type_ == SettingType.CONTACT:
            return app.settings.get_contact_setting(account, jid, value)

        if type_ == SettingType.GROUP_CHAT:
            return app.settings.get_group_chat_setting(
                account, jid, value)

        if type_ == SettingType.CONFIG:
            return app.settings.get(value)

        if type_ == SettingType.ACCOUNT_CONFIG:
            if value == 'password':
                return passwords.get_password(account)
            return app.settings.get_account_setting(account, value)

        if type_ == SettingType.ACTION:
            assert isinstance(value, str)
            if value.startswith('-'):
                return account + value
            return value

        raise ValueError('Wrong SettingType?')

    def set_value(self, state: AllSettingsT) -> None:
        if self.type_ == SettingType.CONFIG:
            app.settings.set(self.value, state)

        elif self.type_ == SettingType.ACCOUNT_CONFIG:
            if self.value == 'password':
                assert isinstance(state, str)
                passwords.save_password(self.account, state)
            else:
                app.settings.set_account_setting(self.account,
                                                 self.value,
                                                 state)

        elif self.type_ == SettingType.CONTACT:
            app.settings.set_contact_setting(
                self.account, self.jid, self.value, state)

        elif self.type_ == SettingType.GROUP_CHAT:
            app.settings.set_group_chat_setting(
                self.account, self.jid, self.value, state)

        if self.callback is not None:
            self.callback(state, self.data)

    def on_row_activated(self) -> None:
        raise NotImplementedError

    def update_activatable(self) -> None:
        if self.type_ == SettingType.CONFIG:
            if app.settings.has_app_override(self.value):
                self.set_activatable(False)
                self.set_sensitive(False)
                self._locked_icon.show()
                return

        if self.enabled_func is None:
            return

        enabled_func_value = self.enabled_func()
        self.set_activatable(enabled_func_value)
        self.set_sensitive(enabled_func_value)

    def _add_action_button(self,
                           kwargs: dict[str, str | Callable[..., None] | None]
                           ) -> None:
        icon_name = cast(str, kwargs.get('button-icon-name'))
        button_text = cast(str, kwargs.get('button-text'))
        tooltip_text = cast(str, kwargs.get('button-tooltip') or '')
        style = cast(str, kwargs.get('button-style'))

        if icon_name is not None:
            button = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.MENU)

        elif button_text is not None:
            button = Gtk.Button(label=button_text)

        else:
            return

        if style is not None:
            for css_class in style.split(' '):
                button.get_style_context().add_class(css_class)

        callback = kwargs['button-callback']
        assert isinstance(callback, Callable)
        button.connect('clicked', callback)
        button.set_tooltip_text(tooltip_text)
        self.setting_box.add(button)


class SwitchSetting(GenericSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args)

        self.switch = Gtk.Switch()
        if self.type_ == SettingType.ACTION:
            self.switch.set_action_name(f'app.{self.setting_value}')
            assert isinstance(self.setting_value, str)
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

    def on_row_activated(self) -> None:
        state = self.switch.get_active()
        self.switch.set_active(not state)

    def on_switch(self, switch: Gtk.Switch, *args: Any) -> None:
        value = switch.get_active()
        self.set_value(value)
        self._set_label(value)

    def _set_label(self, active: bool) -> None:
        text = p_('Switch', 'On') if active else p_('Switch', 'Off')
        self._switch_state_label.set_text(text)


class EntrySetting(GenericSetting):
    def __init__(self, *args: Any) -> None:
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

        assert isinstance(self.value, str)
        app.settings.connect_signal(self.value,
                                    self._on_setting_changed,
                                    account=self.account,
                                    jid=self.jid)

        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        self.entry.set_text(value)

    def _on_destroy(self, *args: Any) -> None:
        app.settings.disconnect_signals(self)

    def on_text_change(self, *args: Any) -> None:
        text = self.entry.get_text()
        self.set_value(text)

    def on_row_activated(self) -> None:
        self.entry.grab_focus()


class ColorSetting(GenericSetting):
    def __init__(self, *args: Any) -> None:
        GenericSetting.__init__(self, *args)

        rgba = Gdk.RGBA()
        assert isinstance(self.setting_value, str)
        rgba.parse(self.setting_value)
        self.color_button = Gtk.ColorButton()
        self.color_button.set_rgba(rgba)
        self.color_button.connect('color-set', self.on_color_set)
        self.color_button.set_valign(Gtk.Align.CENTER)
        self.color_button.set_halign(Gtk.Align.END)

        self.setting_box.pack_end(self.color_button, True, True, 0)

        assert isinstance(self.value, str)
        app.settings.connect_signal(self.value,
                                    self._on_setting_changed,
                                    account=self.account,
                                    jid=self.jid)

        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        rgba = Gdk.RGBA()
        rgba.parse(value)
        self.color_button.set_rgba(rgba)

    def _on_destroy(self, *args: Any) -> None:
        app.settings.disconnect_signals(self)

    def on_color_set(self, button: Gtk.ColorButton) -> None:
        rgba = button.get_rgba()
        self.set_value(rgba.to_string())
        app.css_config.refresh()

    def on_row_activated(self) -> None:
        self.color_button.grab_focus()


class DialogSetting(GenericSetting):
    def __init__(self, *args: Any, dialog: SettingsDialog) -> None:
        GenericSetting.__init__(self, *args)
        self.dialog = dialog

        self.setting_value = Gtk.Label()
        self.setting_value.set_text(self.get_setting_value())
        self.setting_value.set_halign(Gtk.Align.END)
        self.setting_box.pack_start(self.setting_value, True, True, 0)

        self.show_all()

    def show_dialog(self, parent: Gtk.Window) -> None:
        if self.dialog:
            dialog = self.dialog(self.account, parent)
            dialog.connect('destroy', self.on_destroy)

    def on_destroy(self, *args: Any) -> None:
        self.setting_value.set_text(self.get_setting_value())

    def get_setting_value(self) -> str:
        self.setting_value.hide()
        return ''

    def on_row_activated(self) -> None:
        window = self.get_toplevel()
        assert isinstance(window, Gtk.Window)
        self.show_dialog(window)


class SpinSetting(GenericSetting):
    def __init__(self, *args: Any, range_: tuple[float, float, float]) -> None:
        GenericSetting.__init__(self, *args)

        lower, upper, step = range_
        adjustment = Gtk.Adjustment(value=0,
                                    lower=lower,
                                    upper=upper,
                                    step_increment=step,
                                    page_increment=10,
                                    page_size=0)

        self.spin = Gtk.SpinButton()
        self.spin.set_adjustment(adjustment)
        self.spin.set_numeric(True)
        self.spin.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)

        assert self.setting_value is not None
        if isinstance(self.setting_value, float):
            self.spin.set_digits(3)

        self.spin.set_value(float(self.setting_value))
        self.spin.set_halign(Gtk.Align.FILL)
        self.spin.set_valign(Gtk.Align.CENTER)
        self.spin.connect('notify::value', self.on_value_change)

        self.setting_box.pack_start(self.spin, True, True, 0)

        assert isinstance(self.value, str)
        app.settings.connect_signal(self.value,
                                    self._on_setting_changed,
                                    account=self.account,
                                    jid=self.jid)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_setting_changed(self, value: float, *args: Any) -> None:
        self.spin.set_value(value)

    def _on_destroy(self, *args: Any) -> None:
        app.settings.disconnect_signals(self)

    def on_row_activated(self) -> None:
        self.spin.grab_focus()

    def on_value_change(self, spin: Gtk.SpinButton, *args: Any) -> None:
        if self.value in list(get_args(FloatSettings)):
            value = spin.get_value()
        else:
            value = spin.get_value_as_int()
        self.set_value(value)


class FileChooserSetting(GenericSetting):
    def __init__(self, *args: Any, filefilter: tuple[str, str]) -> None:
        GenericSetting.__init__(self, *args)

        button = Gtk.FileChooserButton(title=self.label,
                                       action=Gtk.FileChooserAction.OPEN)
        button.set_halign(Gtk.Align.END)

        # GTK Bug: The FileChooserButton expands without limit
        # get the label and use set_max_wide_chars()
        inner_button = cast(Gtk.Button, button.get_children()[0])
        inner_box = cast(Gtk.Box, inner_button.get_children()[0])
        inner_label = cast(Gtk.Label, inner_box.get_children()[1])
        inner_label.set_max_width_chars(20)

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
            assert isinstance(self.setting_value, str)
            button.set_filename(self.setting_value)
        button.connect('selection-changed', self.on_select)

        clear_button = get_image_button(
            'edit-clear-all-symbolic', _('Clear File'))
        clear_button.connect('clicked', lambda *args: button.unselect_all())
        self.setting_box.pack_start(button, True, True, 0)
        self.setting_box.pack_start(clear_button, False, False, 0)

        self.show_all()

    def on_select(self, filechooser: Gtk.FileChooser) -> None:
        self.set_value(filechooser.get_filename() or '')

    def on_row_activated(self) -> None:
        pass


class CallbackSetting(GenericSetting):
    def __init__(self, *args: Any, callback: Callable[..., Any]) -> None:
        GenericSetting.__init__(self, *args)
        self.callback = callback
        self.show_all()

    def on_row_activated(self) -> None:
        self.callback()


class ActionSetting(GenericSetting):
    def __init__(self, *args: Any, account: str) -> None:
        GenericSetting.__init__(self, *args)
        action_name = f'{account}{self.value}'
        self.action = app.app.lookup_action(action_name)
        if self.action is None:
            log.error('Action not found: %s', action_name)
            return
        self.variant = GLib.Variant.new_string(account)
        self.on_enable()

        self.show_all()
        self._handler_id = self.action.connect(
            'notify::enabled', self.on_enable)
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args: Any) -> None:
        if self.action is not None:
            self.action.disconnect(self._handler_id)

    def on_enable(self, *args: Any) -> None:
        if self.action is not None:
            self.set_sensitive(self.action.get_enabled())

    def on_row_activated(self) -> None:
        if self.action is not None:
            self.action.activate(self.variant)


class LoginSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        jid = app.get_jid_from_account(self.account)
        return jid


class PopoverSetting(GenericSetting):
    def __init__(self,
                 *args: Any,
                 entries: list[str] | dict[str, str],
                 **kwargs: Any
                 ) -> None:
        GenericSetting.__init__(self, *args)

        self._entries = self._convert_to_dict(entries)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                      spacing=12)
        box.set_halign(Gtk.Align.END)
        box.set_hexpand(True)

        self._default_text = cast(str, kwargs.get('default-text'))

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

        assert isinstance(self.value, str)
        app.settings.connect_signal(self.value,
                                    self._on_setting_changed,
                                    account=self.account,
                                    jid=self.jid)

        self.connect('destroy', self._on_destroy)

        self.show_all()

    @staticmethod
    def _convert_to_dict(entries: list[Any] | dict[Any, Any]
                         ) -> dict[Any, Any]:
        if isinstance(entries, list):
            entries = {key: key for key in entries}
        return entries

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        text = self._entries.get(value)
        if text is None:
            text = self._default_text or ''

        self._current_label.set_text(text)

    def _add_menu_entries(self) -> None:
        if self._default_text is not None:
            self._menu_listbox.add(PopoverRow(self._default_text, ''))

        for value, label in self._entries.items():
            self._menu_listbox.add(PopoverRow(label, value))

        self._menu_listbox.show_all()

    def _on_menu_row_activated(self,
                               listbox: Gtk.ListBox,
                               row: PopoverRow
                               ) -> None:
        listbox.unselect_all()
        self._popover.popdown()

        self.set_value(row.value)

    def on_row_activated(self) -> None:
        self._popover.popup()

    def update_entries(self, entries: list[str] | dict[str, str]) -> None:
        self._entries = self._convert_to_dict(entries)
        self._menu_listbox.foreach(self._menu_listbox.remove)
        self._add_menu_entries()

    def _on_destroy(self, *args: Any) -> None:
        self._popover.destroy()
        app.settings.disconnect_signals(self)


class PopoverRow(Gtk.ListBoxRow):
    def __init__(self, label: str, value: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.label = label
        self.value = value

        row_label = Gtk.Label(label=label)
        row_label.set_xalign(0)
        self.add(row_label)


class ComboSetting(GenericSetting):
    def __init__(self,
                 *args: Any,
                 combo_items: list[str | tuple[str, str]]
                 ) -> None:
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

    def on_value_change(self, combo: Gtk.ComboBox) -> None:
        active_id = combo.get_active_id()
        if active_id is not None:
            self.set_value(active_id)

    def on_row_activated(self) -> None:
        pass


class PrioritySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        adjust = app.settings.get_account_setting(
            self.account, 'adjust_priority_with_status')
        if adjust:
            return _('Adjust to Status')

        priority = app.settings.get_account_setting(self.account, 'priority')
        return str(priority)


class CutstomHostnameSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        custom = app.settings.get_account_setting(self.account,
                                                  'use_custom_host')
        return p_('Switch', 'On') if custom else p_('Switch', 'Off')


class ChangePasswordSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def show_dialog(self, parent: Gtk.Window) -> None:
        parent.destroy()
        open_window('ChangePassword', account=self.account)

    def update_activatable(self) -> None:
        activatable = False
        if self.account in app.settings.get_active_accounts():
            client = app.get_client(self.account)
            activatable = (client.state.is_available and
                           client.get_module('Register').supported)
        self.set_activatable(activatable)


class CutstomAutoAwaySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get('autoaway')
        return p_('Switch', 'On') if value else p_('Switch', 'Off')


class CutstomAutoExtendedAwaySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get('autoxa')
        return p_('Switch', 'On') if value else p_('Switch', 'Off')


class CustomStunServerSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get('use_stun_server')
        return p_('Switch', 'On') if value else p_('Switch', 'Off')


class NotificationsSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get('show_notifications')
        return p_('Switch', 'On') if value else p_('Switch', 'Off')
