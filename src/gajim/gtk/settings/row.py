# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import get_args

import logging
from collections.abc import Callable
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.settings.types import AppFloatSettings
from gajim.common.util.av import AudioInputManager

from gajim.gtk.const import CHATSTATE_SETTING_ENUM
from gajim.gtk.const import CLOSE_ACTION_ENUM
from gajim.gtk.const import CONNECTION_TYPE_ENUM
from gajim.gtk.const import ENCRYPTION_SETTING_ENUM
from gajim.gtk.const import FILE_PREVIEW_SIZE_ENUM
from gajim.gtk.const import HISTORYMAXAGE_SETTING_ENUM
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.const import STYLE_ENUM
from gajim.gtk.const import WINDOW_STARTUP_ENUM
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.settings.model import SettingGObj
from gajim.gtk.settings.model import SpinRange
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.settings")


def _get_workspaces() -> dict[str, str]:
    workspaces: dict[str, str] = {"": _("Disabled")}
    for workspace_id in app.settings.get_workspaces():
        name = app.settings.get_workspace_setting(workspace_id, "name")
        workspaces[workspace_id] = name
    return workspaces


def _get_proxies() -> dict[str, str]:
    proxies = {"": _("System")}
    proxies.update({proxy: proxy for proxy in app.settings.get_proxies()})
    proxies["no-proxy"] = _("No Proxy")
    return proxies


def _get_theme_items() -> list[str]:
    return ["default", *app.css_config.themes]


def _create_av_combo_items() -> dict[str, str]:
    audio_input_devices = AudioInputManager().get_devices()
    items = enumerate(
        sorted(
            audio_input_devices.items(),
            key=lambda x: "" if x[1].startswith("auto") else x[0].lower(),
        )
    )
    combo_items: dict[str, str] = {}
    for _index, (name, value) in items:
        combo_items[value] = name
    return combo_items


DropDownValues = {
    "default_workspace": _get_workspaces,
    "send_chatstate_default": CHATSTATE_SETTING_ENUM,
    "gc_send_chatstate_default": CHATSTATE_SETTING_ENUM,
    "encryption_default": ENCRYPTION_SETTING_ENUM,
    "chat_history_max_age": HISTORYMAXAGE_SETTING_ENUM,
    "proxy": _get_proxies,
    "custom_type": CONNECTION_TYPE_ENUM,
    "show_main_window_on_startup": WINDOW_STARTUP_ENUM,
    "action_on_close": CLOSE_ACTION_ENUM,
    "gc_sync_threshold_public_default": THRESHOLD_OPTIONS,
    "preview_max_file_size": FILE_PREVIEW_SIZE_ENUM,
    "roster_theme": _get_theme_items,
    "dark_theme": STYLE_ENUM,
    "audio_input_device": _create_av_combo_items,
    "global_proxy": _get_proxies,
}


class GenericSetting(Adw.ActionRow, SignalManager):
    def __init__(
        self,
        account: str,
        jid: JID,
        label: str,
        type_: SettingType,
        value: Any | None,
        name: str | None,
        callback: Callable[..., None] | None = None,
        data: Any | None = None,
        desc: str | None = None,
        bind: str | None = None,
        inverted: bool = False,
        enabled_func: Callable[..., bool] | None = None,
        **kwargs: Any,
    ) -> None:
        Adw.ActionRow.__init__(
            self, activatable=True, title=label, subtitle=desc or "", use_markup=False
        )
        SignalManager.__init__(self)

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

        self._client: types.Client | None = None
        if self.account and app.account_is_connected(self.account):
            self._client = app.get_client(self.account)

        self.setting_box = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)

        self._locked_icon = Gtk.Image.new_from_icon_name(
            "lucide-lock-symbolic",
        )
        self._locked_icon.set_visible(False)
        self._locked_icon.set_tooltip_text(_("Setting is locked by the system"))
        self._action_overlay = Gtk.Overlay(child=self.setting_box)
        self._action_overlay.add_overlay(self._locked_icon)

        self.add_suffix(self._action_overlay)

        self._bind_sensitive_state()

        self._add_action_button(kwargs)

        self.__post_init__()

        self._connect(self, "activated", self._on_activated)

    def __post_init__(self) -> None:
        return

    @classmethod
    def from_settingobj(cls, account: str, jid: JID, obj: SettingGObj) -> Any:
        return cls(
            account,
            jid,
            obj.props.label,
            obj.props.type,
            obj.props.value,
            obj.props.name,
            obj.props.callback,
            obj.props.data,
            obj.props.desc,
            obj.props.bind,
            obj.props.inverted,
            obj.props.enabled_func,
            **obj.props_,
        )

    def do_unroot(self) -> None:
        Adw.ActionRow.do_unroot(self)
        self._disconnect_all()
        app.settings.disconnect_signals(self)
        del self.callback
        del self.enabled_func
        app.check_finalize(self)

    def _on_activated(self, row: Adw.ActionRow) -> None:
        return

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
            assert account is not None
            assert jid is not None
            value = app.settings.get_contact_setting(account, jid, setting)

        elif bind_setting_type == SettingType.GROUP_CHAT:
            assert account is not None
            assert jid is not None
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact(jid, groupchat=True)
            assert isinstance(contact, GroupchatContact)
            value = app.settings.get_group_chat_setting(
                account, jid, "setting", contact.muc_context
            )

        elif bind_setting_type == SettingType.ACCOUNT_CONFIG:
            assert account is not None
            value = app.settings.get_account_setting(account, setting)

        else:
            value = app.settings.get(setting)

        assert isinstance(value, bool)
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

    def get_value(self) -> Any | None:
        return self.__get_value(self.type_, self.value, self.account, self.jid)

    @staticmethod
    def __get_value(
        type_: SettingType, value: Any | None, account: str, jid: JID
    ) -> Any | None:
        if value is None:
            return None

        if type_ == SettingType.VALUE:
            return value

        if type_ == SettingType.CONTACT:
            return app.settings.get_contact_setting(account, jid, value)

        if type_ == SettingType.GROUP_CHAT:
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact(jid, groupchat=True)
            assert isinstance(contact, GroupchatContact)
            return app.settings.get_group_chat_setting(
                account, jid, value, contact.muc_context
            )

        if type_ == SettingType.CONFIG:
            return app.settings.get(value)

        if type_ == SettingType.ACCOUNT_CONFIG:
            return app.settings.get_account_setting(account, value)

        if type_ == SettingType.ACTION:
            assert isinstance(value, str)
            if value.startswith("-"):
                return account + value
            return value

        raise ValueError("Wrong SettingType?")

    def set_value(self, state: Any) -> None:
        if self.type_ == SettingType.CONFIG:
            app.settings.set(self.value, state)

        elif self.type_ == SettingType.ACCOUNT_CONFIG:
            app.settings.set_account_setting(self.account, self.value, state)

        elif self.type_ == SettingType.CONTACT:
            app.settings.set_contact_setting(self.account, self.jid, self.value, state)

        elif self.type_ == SettingType.GROUP_CHAT:
            client = app.get_client(self.account)
            contact = client.get_module("Contacts").get_contact(
                self.jid, groupchat=True
            )
            assert isinstance(contact, GroupchatContact)
            app.settings.set_group_chat_setting(
                self.account, self.jid, self.value, contact.muc_context, state
            )

        if self.callback is not None:
            self.callback(state, self.data)

    def update_activatable(self) -> None:
        if self.type_ == SettingType.CONFIG:
            assert isinstance(self.value, str)
            if app.settings.has_app_override(self.value):
                self.set_activatable(False)
                self.set_sensitive(False)
                self._locked_icon.set_visible(True)
                return

        if self.enabled_func is None:
            return

        enabled_func_value = self.enabled_func()
        self.set_activatable(enabled_func_value)
        self.set_sensitive(enabled_func_value)

    def _add_action_button(
        self, kwargs: dict[str, str | Callable[..., None] | None]
    ) -> None:
        icon_name = kwargs.get("button-icon-name")
        button_text = kwargs.get("button-text")
        tooltip_text = cast(str, kwargs.get("button-tooltip") or "")
        style = kwargs.get("button-style")

        if icon_name is not None:
            assert isinstance(icon_name, str)
            button = Gtk.Button.new_from_icon_name(icon_name)

        elif button_text is not None:
            assert isinstance(button_text, str)
            button = Gtk.Button(label=button_text)

        else:
            return

        if style is not None:
            assert isinstance(style, str)
            for css_class in style.split(" "):
                button.add_css_class(css_class)

        callback = kwargs["button-callback"]
        assert isinstance(callback, Callable)
        self._connect(button, "clicked", callback)
        button.set_tooltip_text(tooltip_text)

        sensitive = bool(kwargs.get("button-sensitive", True))
        button.set_sensitive(sensitive)

        self.setting_box.append(button)


class SwitchSetting(GenericSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

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
        self._connect(self.switch, "notify::active", self._on_active_notify)
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
        self.setting_box.prepend(box)

        self.set_activatable_widget(self.switch)

    def _on_active_notify(self, switch: Gtk.Switch, *args: Any) -> None:
        value = switch.get_active()
        self.set_value(value)
        self._set_label(value)

    def _set_label(self, active: bool) -> None:
        text = p_("Switch", "On") if active else p_("Switch", "Off")
        self._switch_state_label.set_text(text)


class EntrySetting(GenericSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        self.entry = Gtk.Entry()
        self.entry.set_text(str(self.setting_value))
        self._changed_handler_id = self._connect(
            self.entry, "changed", self._on_text_change
        )
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_alignment(1)

        self.setting_box.prepend(self.entry)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

        self.set_activatable_widget(self.entry)

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        if self.entry.get_text() == value:
            return

        with self.entry.handler_block(self._changed_handler_id):
            self.entry.set_text(value)

    def _on_text_change(self, *args: Any) -> None:
        text = self.entry.get_text()
        self.set_value(text)


class ColorSetting(GenericSetting):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        rgba = Gdk.RGBA()
        assert isinstance(self.setting_value, str)
        rgba.parse(self.setting_value)
        color_dialog = Gtk.ColorDialog()
        self.color_button = Gtk.ColorDialogButton(dialog=color_dialog)
        self.color_button.set_rgba(rgba)
        self._connect(self.color_button, "notify::rgba", self._on_color_set)
        self.color_button.set_valign(Gtk.Align.CENTER)
        self.color_button.set_halign(Gtk.Align.END)
        self.color_button.set_hexpand(True)

        self.setting_box.prepend(self.color_button)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

        self.set_activatable_widget(self.color_button)

    def _on_setting_changed(self, value: str, *args: Any) -> None:
        rgba = Gdk.RGBA()
        rgba.parse(value)
        self.color_button.set_rgba(rgba)

    def _on_color_set(self, color_button: Gtk.ColorDialogButton, *args: Any) -> None:
        rgba = color_button.get_rgba()
        self.set_value(rgba.to_string())
        app.css_config.refresh()


class SpinSetting(GenericSetting):
    def __init__(
        self, *args: Any, range_: tuple[float, float, float] | SpinRange, **kwargs: Any
    ) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        if not isinstance(range_, SpinRange):
            range_ = SpinRange(*range_)

        adjustment = Gtk.Adjustment(
            value=0,
            lower=range_.lower,
            upper=range_.upper,
            step_increment=range_.step,
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
            digits=range_.digits,
        )

        assert isinstance(self.setting_value, int | float | str)
        self.spin.set_value(float(self.setting_value))

        self._connect(self.spin, "notify::value", self._on_value_change)

        self.setting_box.prepend(self.spin)

        assert isinstance(self.value, str)
        app.settings.connect_signal(
            self.value, self._on_setting_changed, account=self.account, jid=self.jid
        )

        self.set_activatable_widget(self.spin)

    def _on_setting_changed(self, value: float, *args: Any) -> None:
        self.spin.set_value(value)

    def _on_value_change(self, spin: Gtk.SpinButton, *args: Any) -> None:
        if self.value in list(get_args(AppFloatSettings)):
            value = spin.get_value()
        else:
            value = spin.get_value_as_int()
        self.set_value(value)


class FileChooserSetting(GenericSetting):
    def __init__(self, *args: Any, filefilters: list[Filter], **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)
        button = FileChooserButton(filters=filefilters, label=self.label)
        button.set_halign(Gtk.Align.END)

        if self.setting_value:
            assert isinstance(self.setting_value, str)
            button.set_path(Path(self.setting_value))

        self._connect(button, "path-picked", self._on_select)

        clear_button = Gtk.Button(
            icon_name="lucide-brush-cleaning-symbolic", tooltip_text=_("Clear File")
        )
        self._connect(clear_button, "clicked", lambda *args: button.reset())  # type: ignore
        self.setting_box.prepend(clear_button)
        self.setting_box.prepend(button)

        self.set_activatable_widget(button)

    def _on_select(
        self, _file_chooser_button: FileChooserButton, file_paths: list[Path]
    ) -> None:
        if not file_paths:
            return

        self.set_value(str(file_paths[0]))


class CallbackSetting(GenericSetting):
    def __init__(self, *args: Any, callback: Callable[..., Any], **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)
        self.callback = callback

    def _on_activated(self, row: Adw.ActionRow) -> None:
        self.callback()


class ActionSetting(GenericSetting):
    def __init__(self, *args: Any, variant: GLib.Variant, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)
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

    def _on_activated(self, row: Adw.ActionRow) -> None:
        if self.action is not None:
            self.action.activate(self.variant)


class DropDownSetting(GenericSetting):
    def __init__(
        self, *args: Any, data: list[str] | dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_halign(Gtk.Align.END)
        box.set_hexpand(True)

        if data is None:
            data = DropDownValues[self.value]
            if callable(data):
                data = data()

        self._dropdown: GajimDropDown[Any] = GajimDropDown(data=data, fixed_width=15)
        self._dropdown.select_key(self.setting_value)
        self._dropdown.connect("notify::selected", self._on_selected)
        box.append(self._dropdown)

        self.setting_box.prepend(box)

        self.set_activatable_widget(self._dropdown)

    def do_unroot(self) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        GenericSetting.do_unroot(self)
        self._dropdown.run_destroy()
        del self._dropdown

    def _on_selected(self, dropdown: GajimDropDown[Any], *args: Any) -> None:
        item = dropdown.get_selected_item()
        assert item is not None
        self.set_value(item.key)

    def update_entries(self, data: list[str] | dict[str, str]) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        self._dropdown.set_data(data)
        self._dropdown.connect("notify::selected", self._on_selected)

    def select_key(self, key: Any) -> None:
        self._dropdown.disconnect_by_func(self._on_selected)
        self._dropdown.select_key(key)
        self._dropdown.connect("notify::selected", self._on_selected)


class DialogSetting(GenericSetting):
    def __init__(self, *args: Any, dialog: str, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        self._dialog = dialog

        image = Gtk.Image.new_from_icon_name("lucide-chevron-right-symbolic")
        self.add_suffix(image)

    def _on_activated(self, row: Adw.ActionRow) -> None:
        open_window(self._dialog, account=self.account)  # type: ignore


class SubPageSetting(GenericSetting):
    def __init__(self, *args: Any, subpage: str, **kwargs: Any) -> None:
        GenericSetting.__init__(self, *args, **kwargs)

        self._subpage = subpage

        self._label = Gtk.Label()
        self.add_suffix(self._label)

        image = Gtk.Image.new_from_icon_name("lucide-chevron-right-symbolic")
        self.add_suffix(image)

        if self.value is not None:
            self.set_label(self.setting_value)
            app.settings.bind_signal(
                self.value,
                self,
                "set_label",
                account=self.account,
                jid=self.jid,
                inverted=self.inverted,
            )

    def set_label(self, enabled: bool) -> None:
        text = p_("Switch", "On") if enabled else p_("Switch", "Off")
        self._label.set_text(text)

    def _on_activated(self, row: Adw.ActionRow) -> None:
        nav = row.get_ancestor(Adw.NavigationView)
        if nav is None:
            return

        nav.activate_action("navigation.push", GLib.Variant("s", self._subpage))


_registered_row_map: dict[str | int, Any] = {
    SettingKind.SWITCH: SwitchSetting,
    SettingKind.SPIN: SpinSetting,
    SettingKind.DIALOG: DialogSetting,
    SettingKind.SUBPAGE: SubPageSetting,
    SettingKind.ENTRY: EntrySetting,
    SettingKind.COLOR: ColorSetting,
    SettingKind.ACTION: ActionSetting,
    SettingKind.FILECHOOSER: FileChooserSetting,
    SettingKind.CALLBACK: CallbackSetting,
    SettingKind.DROPDOWN: DropDownSetting,
    SettingKind.GENERIC: GenericSetting,
}


def register_rows(mapping: dict[str, Any]) -> None:
    _registered_row_map.update(mapping)


def get_registered_row(name: SettingKind | str) -> Any:
    return _registered_row_map[name]
