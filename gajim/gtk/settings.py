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
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
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
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.util import iterate_listbox_children
from gajim.gtk.util import open_window
from gajim.gtk.util import SignalManager
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.settings")


class SettingsDialog(GajimAppWindow):
    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        flags: Gtk.DialogFlags,
        settings: list[Setting],
        account: str,
        extend: dict[SettingKind, GenericSetting] | None = None,
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="SettingsDialog",
            title=title,
            default_width=250,
            transient_for=parent,
            add_window_padding=False,
        )

        self.window.add_css_class("settings-dialog")

        self.account = account
        if flags == Gtk.DialogFlags.MODAL:
            self.window.set_modal(True)
        elif flags == Gtk.DialogFlags.DESTROY_WITH_PARENT:
            self.window.set_destroy_with_parent(True)

        self.listbox = SettingsBox(account, extend=extend)
        self.listbox.set_hexpand(True)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for setting in settings:
            self.listbox.add_setting(setting)
        self.listbox.update_states()

        self.set_child(self.listbox)
        self.show()

    def _cleanup(self) -> None:
        del self.listbox

    def get_setting(self, name: str):
        return self.listbox.get_setting(name)


class SettingsBox(Gtk.ListBox, SignalManager):
    def __init__(
        self,
        account: str | None = None,
        jid: str | None = None,
        extend: dict[SettingKind, GenericSetting] | None = None,
    ) -> None:
        Gtk.ListBox.__init__(self)
        SignalManager.__init__(self)
        self.add_css_class("settings-box")
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
            SettingKind.AUTO_AWAY: CutstomAutoAwaySetting,
            SettingKind.AUTO_EXTENDED_AWAY: CutstomAutoExtendedAwaySetting,
            SettingKind.USE_STUN_SERVER: CustomStunServerSetting,
            SettingKind.NOTIFICATIONS: NotificationsSetting,
            SettingKind.DROPDOWN: DropDownSetting,
        }

        if extend is not None:
            for setting, callback in extend:
                self.map[setting] = callback

        self._connect(self, "row-activated", self.on_row_activated)

    def do_unroot(self) -> None:
        Gtk.ListBox.do_unroot(self)
        self.named_settings.clear()
        self._disconnect_all()
        app.check_finalize(self)
        while row := self.get_first_child():
            app.check_finalize(row)
            self.remove(row)

    @staticmethod
    def on_row_activated(_listbox: SettingsBox, row: GenericSetting) -> None:
        row.on_row_activated()

    def add_setting(self, setting: Setting) -> None:
        if not isinstance(setting, Gtk.ListBoxRow):
            if setting.props is not None:
                listitem = self.map[setting.kind](
                    self.account, self.jid, *setting[1:-1], **setting.props
                )
            else:
                listitem = self.map[setting.kind](
                    self.account, self.jid, *setting[1:-1]
                )

        if setting.name is not None:
            self.named_settings[setting.name] = listitem
        self.append(listitem)

    def get_setting(self, name: str) -> GenericSetting:
        return self.named_settings[name]

    def update_states(self) -> None:
        for row in cast(list[GenericSetting], iterate_listbox_children(self)):
            row.update_activatable()


class GenericSetting(Gtk.ListBoxRow, SignalManager):
    def __init__(
        self,
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
        enabled_func: Callable[..., bool] | None = None,
    ) -> None:

        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

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
            "feather-lock-symbolic",
        )
        self._locked_icon.set_visible(False)
        self._locked_icon.set_visible(False)
        self._locked_icon.set_halign(Gtk.Align.END)
        self._locked_icon.set_tooltip_text(_("Setting is locked by the system"))

        self._grid.attach(self._locked_icon, 0, 0, 1, 1)

        description_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        description_box.set_valign(Gtk.Align.CENTER)

        settingtext = Gtk.Label(label=label)
        settingtext.set_hexpand(True)
        settingtext.set_halign(Gtk.Align.START)
        settingtext.set_valign(Gtk.Align.CENTER)
        settingtext.set_vexpand(True)
        description_box.append(settingtext)

        if desc is not None:
            description = Gtk.Label(
                label=desc,
                name="SubDescription",
                hexpand=True,
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                xalign=0,
                wrap=True,
                max_width_chars=50,
            )
            description_box.append(description)

        self._grid.attach(description_box, 0, 1, 1, 1)

        self.setting_box = Gtk.Box(spacing=12)
        self.setting_box.set_size_request(200, -1)
        self.setting_box.set_valign(Gtk.Align.CENTER)
        self.setting_box.set_name("GenericSettingBox")
        self._grid.attach(self.setting_box, 1, 0, 1, 2)
        self.set_child(self._grid)

        self._bind_sensitive_state()

    def do_unroot(self) -> None:
        self._disconnect_all()
        app.settings.disconnect_signals(self)
        del self.callback
        del self.enabled_func
        Gtk.ListBoxRow.do_unroot(self)
        # app.check_finalize() is called when the SettingsBox is destroyed

    def _bind_sensitive_state(self) -> None:
        if self.bind is None:
            return

        bind_setting_type, setting, account, jid = self._parse_bind()

        app.settings.bind_signal(
            setting,
            self,
            "set_sensitive",
            account=account,
            jid=jid,
            inverted=self.inverted,
        )

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

    def _parse_bind(self) -> tuple[SettingType, str, str | None, JID | None]:
        assert self.bind is not None
        if "::" not in self.bind:
            return SettingType.CONFIG, self.bind, None, None

        bind_setting_type, setting = self.bind.split("::")
        if bind_setting_type == "account":
            return SettingType.ACCOUNT_CONFIG, setting, self.account, None

        if bind_setting_type == "contact":
            return SettingType.CONTACT, setting, self.account, self.jid

        if bind_setting_type == "group_chat":
            return SettingType.GROUP_CHAT, setting, self.account, self.jid
        raise ValueError(f"Invalid bind argument: {self.bind}")

    def get_value(self):
        return self.__get_value(self.type_, self.value, self.account, self.jid)

    @staticmethod
    def __get_value(
        type_: SettingType, value: AllSettingsT, account: str, jid: JID
    ) -> AllSettingsT | None:
        if value is None:
            return None
        if type_ == SettingType.VALUE:
            return value

        if type_ == SettingType.CONTACT:
            return app.settings.get_contact_setting(account, jid, value)

        if type_ == SettingType.GROUP_CHAT:
            return app.settings.get_group_chat_setting(account, jid, value)

        if type_ == SettingType.CONFIG:
            return app.settings.get(value)

        if type_ == SettingType.ACCOUNT_CONFIG:
            if value == "password":
                return passwords.get_password(account)
            return app.settings.get_account_setting(account, value)

        if type_ == SettingType.ACTION:
            assert isinstance(value, str)
            if value.startswith("-"):
                return account + value
            return value

        raise ValueError("Wrong SettingType?")

    def set_value(self, state: AllSettingsT) -> None:
        if self.type_ == SettingType.CONFIG:
            app.settings.set(self.value, state)

        elif self.type_ == SettingType.ACCOUNT_CONFIG:
            if self.value == "password":
                assert isinstance(state, str)
                passwords.save_password(self.account, state)
            else:
                app.settings.set_account_setting(self.account, self.value, state)

        elif self.type_ == SettingType.CONTACT:
            app.settings.set_contact_setting(self.account, self.jid, self.value, state)

        elif self.type_ == SettingType.GROUP_CHAT:
            app.settings.set_group_chat_setting(
                self.account, self.jid, self.value, state
            )

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

    def _add_action_button(
        self, kwargs: dict[str, str | Callable[..., None] | None]
    ) -> None:
        icon_name = cast(str, kwargs.get("button-icon-name"))
        button_text = cast(str, kwargs.get("button-text"))
        tooltip_text = cast(str, kwargs.get("button-tooltip") or "")
        style = cast(str, kwargs.get("button-style"))

        if icon_name is not None:
            button = Gtk.Button.new_from_icon_name(icon_name)

        elif button_text is not None:
            button = Gtk.Button(label=button_text)

        else:
            return

        if style is not None:
            for css_class in style.split(" "):
                button.add_css_class(css_class)

        callback = kwargs["button-callback"]
        assert isinstance(callback, Callable)
        self._connect(button, "clicked", callback)
        button.set_tooltip_text(tooltip_text)
        self.setting_box.append(button)


class SwitchSetting(GenericSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args)

        self.switch = Gtk.Switch()
        if self.type_ == SettingType.ACTION:
            self.switch.set_action_name(f"app.{self.setting_value}")
            assert isinstance(self.setting_value, str)
            state = app.app.get_action_state(self.setting_value)
            assert state is not None
            self.switch.set_active(state.get_boolean())
        else:
            assert isinstance(self.setting_value, bool)
            self.switch.set_active(self.setting_value)
        self._connect(self.switch, "notify::active", self.on_switch)
        self.switch.set_hexpand(True)
        self.switch.set_halign(Gtk.Align.END)
        self.switch.set_valign(Gtk.Align.CENTER)

        self._switch_state_label = Gtk.Label()
        self._switch_state_label.set_xalign(1)
        self._switch_state_label.set_valign(Gtk.Align.CENTER)
        assert isinstance(self.setting_value, bool)
        self._set_label(self.setting_value)

        box = Gtk.Box(spacing=12)
        box.set_halign(Gtk.Align.END)
        box.append(self._switch_state_label)
        box.append(self.switch)
        self.setting_box.append(box)

        self._add_action_button(kwargs)

    def on_row_activated(self) -> None:
        state = self.switch.get_active()
        self.switch.set_active(not state)

    def on_switch(self, switch: Gtk.Switch, *args: Any) -> None:
        value = switch.get_active()
        self.set_value(value)
        self._set_label(value)

    def _set_label(self, active: bool) -> None:
        text = p_("Switch", "On") if active else p_("Switch", "Off")
        self._switch_state_label.set_text(text)


class EntrySetting(GenericSetting):
    def __init__(self, *args: Any) -> None:
        GenericSetting.__init__(self, *args)

        self.entry = Gtk.Entry()
        self.entry.set_text(str(self.setting_value))
        self._changed_handler_id = self._connect(
            self.entry, "changed", self._on_text_change
        )
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_alignment(1)

        if self.value == "password":
            self.entry.set_visibility(False)

        self.setting_box.append(self.entry)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        if self.entry.get_text() == value:
            return

        with self.entry.handler_block(self._changed_handler_id):
            self.entry.set_text(value)

    def _on_text_change(self, *args: Any) -> None:
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
        color_dialog = Gtk.ColorDialog()
        self.color_button = Gtk.ColorDialogButton(dialog=color_dialog)
        self.color_button.set_rgba(rgba)
        self._connect(self.color_button, "notify::rgba", self.on_color_set)
        self.color_button.set_valign(Gtk.Align.CENTER)
        self.color_button.set_halign(Gtk.Align.END)
        self.color_button.set_hexpand(True)

        self.setting_box.append(self.color_button)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        rgba = Gdk.RGBA()
        rgba.parse(value)
        self.color_button.set_rgba(rgba)

    def on_color_set(self, color_button: Gtk.ColorDialogButton, *args: Any) -> None:
        rgba = color_button.get_rgba()
        self.set_value(rgba.to_string())
        app.css_config.refresh()

    def on_row_activated(self) -> None:
        self.color_button.grab_focus()


class DialogSetting(GenericSetting):
    def __init__(self, *args: Any, dialog: Any) -> None:
        GenericSetting.__init__(self, *args)
        self._dialog_cls = dialog

        self.setting_value = Gtk.Label()
        self.setting_value.set_text(self.get_setting_value())
        self.setting_value.set_halign(Gtk.Align.END)
        self.setting_value.set_hexpand(True)
        self.setting_box.append(self.setting_value)

    def show_dialog(self) -> None:
        window = self.get_root()
        assert isinstance(window, Gtk.Root)
        self._dialog_cls(self.account, window)

    def on_destroy(self, *args: Any) -> None:
        self.setting_value.set_text(self.get_setting_value())

    def get_setting_value(self) -> str:
        self.setting_value.hide()
        return ""

    def on_row_activated(self) -> None:
        self.show_dialog()


class SpinSetting(GenericSetting):
    def __init__(self, *args: Any, range_: tuple[float, float, float]) -> None:
        GenericSetting.__init__(self, *args)

        lower, upper, step = range_
        adjustment = Gtk.Adjustment(
            value=0,
            lower=lower,
            upper=upper,
            step_increment=step,
            page_increment=10,
            page_size=0,
        )

        self.spin = Gtk.SpinButton(
            adjustment=adjustment,
            halign=Gtk.Align.END,
            hexpand=True,
            numeric=True,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            valign=Gtk.Align.CENTER,
            width_chars=5,
        )

        assert isinstance(self.setting_value, int | float)
        if isinstance(self.setting_value, float):
            self.spin.set_digits(3)

        self.spin.set_value(float(self.setting_value))

        self._connect(self.spin, "notify::value", self.on_value_change)

        self.setting_box.append(self.spin)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

    def _on_setting_changed(self, value: float, *args: Any) -> None:
        self.spin.set_value(value)

    def on_row_activated(self) -> None:
        self.spin.grab_focus()

    def on_value_change(self, spin: Gtk.SpinButton, *args: Any) -> None:
        if self.value in list(get_args(FloatSettings)):
            value = spin.get_value()
        else:
            value = spin.get_value_as_int()
        self.set_value(value)


class FileChooserSetting(GenericSetting):
    def __init__(self, *args: Any, filefilters: list[Filter]) -> None:
        GenericSetting.__init__(self, *args)
        button = FileChooserButton(filters=filefilters, label=self.label)
        button.set_halign(Gtk.Align.END)

        if self.setting_value:
            assert isinstance(self.setting_value, str)
            button.set_path(Path(self.setting_value))

        self._connect(button, "path-picked", self.on_select)

        clear_button = button = Gtk.Button(
            icon_name="edit-clear-all-symbolic", tooltip_text=_("Clear File")
        )
        self._connect(clear_button, "clicked", lambda *args: button.reset())  # type: ignore
        self.setting_box.append(button)
        self.setting_box.append(clear_button)

    def on_select(
        self, _file_chooser_button: FileChooserButton, file_paths: list[Path]
    ) -> None:
        if not file_paths:
            return

        self.set_value(str(file_paths[0]))

    def on_row_activated(self) -> None:
        pass


class CallbackSetting(GenericSetting):
    def __init__(self, *args: Any, callback: Callable[..., Any]) -> None:
        GenericSetting.__init__(self, *args)
        self.callback = callback

    def do_unroot(self) -> None:
        # TODO test, currently not in use
        GenericSetting.do_unroot(self)
        del self.callback

    def on_row_activated(self) -> None:
        self.callback()


class ActionSetting(GenericSetting):
    def __init__(self, *args: Any, variant: GLib.Variant) -> None:
        GenericSetting.__init__(self, *args)
        assert isinstance(self.value, str)
        if self.value.startswith("app."):
            self.action = app.app.lookup_action(self.value[4:])
        else:
            self.action = app.window.lookup_action(self.value)

        if self.action is None:
            log.error("Action not found: %s", self.value)
            return

        self.variant = variant
        self.on_enable()

        self._connect(self.action, "notify::enabled", self.on_enable)

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


class DropDownSetting(GenericSetting):
    def __init__(
        self, *args: Any, data: list[str] | dict[str, Any], **kwargs: Any
    ) -> None:
        GenericSetting.__init__(self, *args)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_halign(Gtk.Align.END)
        box.set_hexpand(True)

        self._dropdown = GajimDropDown(data=data, fixed_width=15)
        self._dropdown.select_key(self.setting_value)
        self._dropdown.connect("notify::selected", self._on_selected)
        box.append(self._dropdown)

        self.setting_box.append(box)

        self._add_action_button(kwargs)

    def do_unroot(self) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        GenericSetting.do_unroot(self)
        app.check_finalize(self._dropdown)
        del self._dropdown

    def _on_selected(self, dropdown: GajimDropDown, *args: Any) -> None:
        item = dropdown.get_selected_item()
        assert item is not None
        self.set_value(item.props.key)

    def update_entries(self, data: list[str] | dict[str, str]) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        self._dropdown.set_data(data)
        self._dropdown.connect("notify::selected", self._on_selected)

    def select_key(self, key: Any) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        self._dropdown.select_key(key)
        self._dropdown.connect("notify::selected", self._on_selected)

    def on_row_activated(self) -> None:
        pass


class PrioritySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        adjust = app.settings.get_account_setting(
            self.account, "adjust_priority_with_status"
        )
        if adjust:
            return _("Adjust to Status")

        priority = app.settings.get_account_setting(self.account, "priority")
        return str(priority)


class CutstomHostnameSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        custom = app.settings.get_account_setting(self.account, "use_custom_host")
        return p_("Switch", "On") if custom else p_("Switch", "Off")


class ChangePasswordSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def show_dialog(self) -> None:
        settings_box = self.get_parent()
        assert isinstance(settings_box, SettingsBox)
        settings_dialog = settings_box.get_root()
        assert isinstance(settings_dialog, Gtk.ApplicationWindow)
        settings_dialog.destroy()
        open_window("ChangePassword", account=self.account)

    def update_activatable(self) -> None:
        activatable = False
        if self.account in app.settings.get_active_accounts():
            client = app.get_client(self.account)
            activatable = (
                client.state.is_available and client.get_module("Register").supported
            )
        self.set_activatable(activatable)


class CutstomAutoAwaySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get("autoaway")
        return p_("Switch", "On") if value else p_("Switch", "Off")


class CutstomAutoExtendedAwaySetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get("autoxa")
        return p_("Switch", "On") if value else p_("Switch", "Off")


class CustomStunServerSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get("use_stun_server")
        return p_("Switch", "On") if value else p_("Switch", "Off")


class NotificationsSetting(DialogSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DialogSetting.__init__(self, *args, **kwargs)

    def get_setting_value(self) -> str:
        value = app.settings.get("show_notifications")
        return p_("Switch", "On") if value else p_("Switch", "Off")
