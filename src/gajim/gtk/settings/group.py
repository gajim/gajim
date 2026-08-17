# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app
from gajim.common.ged import EventHelper

from gajim.gtk.const import Setting
from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.settings.model import SettingGObj
from gajim.gtk.settings.row import GenericSetting
from gajim.gtk.settings.row import get_registered_row
from gajim.gtk.util.classes import SignalManager


class GajimPreferencesGroup(Adw.PreferencesGroup, SignalManager, EventHelper):
    __gtype_name__ = "GajimPreferencesGroup"

    def __init__(
        self,
        key: str,
        *,
        account: str | None = None,
        jid: str | None = None,
        description: str = "",
        title: str = "",
        header_suffix: Gtk.Widget | None = None,
    ) -> None:
        EventHelper.__init__(self)
        SignalManager.__init__(self)
        Adw.PreferencesGroup.__init__(
            self, description=description, title=title, header_suffix=header_suffix
        )

        self.key = key
        self.account = account
        self.jid = jid
        self.named_settings: dict[str, GenericSetting] = {}

    def do_unroot(self) -> None:
        self._disconnect_all()
        self.unregister_events()
        Adw.PreferencesGroup.do_unroot(self)
        self.named_settings.clear()
        app.check_finalize(self)

    def add_setting(self, setting: Setting | Adw.ActionRow) -> None:
        if isinstance(setting, Adw.ActionRow):
            self.add(setting)
            return

        row_cls = get_registered_row(setting.kind)
        row = row_cls(self.account, self.jid, *setting[1:-1], **setting.props or {})

        if setting.name is not None:
            self.named_settings[setting.name] = row
        self.add(row)
        row.update_activatable()

    def get_setting(self, name: str) -> GenericSetting:
        return self.named_settings[name]

    def bind_settings_model(self, model: Any) -> None:
        self.bind_model(model, self._create_widgets)

    def _create_widgets(self, obj: SettingGObj):
        row_cls = get_registered_row(obj.props.kind)
        row = row_cls.from_settingobj(self.account, self.jid, obj)
        if obj.props.name is not None:
            self.named_settings[obj.props.name] = row

        row.update_activatable()
        return row

    def add_copy_button(self) -> None:
        button = CopyButton()
        self._connect(button, "clicked", self._on_clipboard_button_clicked)
        self.set_header_suffix(button)

    def _on_clipboard_button_clicked(self, _widget: Gtk.Button) -> None:
        app.window.get_clipboard().set(self._get_clipboard_text())

    def _get_clipboard_text(self) -> str:
        raise NotImplementedError
