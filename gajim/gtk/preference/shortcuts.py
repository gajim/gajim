# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal

from collections.abc import Callable

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import DialogResponse
from gajim.gtk.const import SHORTCUT_CATEGORIES
from gajim.gtk.const import SHORTCUTS
from gajim.gtk.settings import GajimPreferencePage
from gajim.gtk.settings import GajimPreferencesGroup
from gajim.gtk.sidebar_switcher import SideBarMenuItem
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

# All keyvals:
# https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gdk/gdkkeysyms.h


class ShortcutsPage(GajimPreferencePage, SignalManager):
    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            key="shortcuts",
            title=_("Shortcuts"),
            groups=[],
            menu=SideBarMenuItem(
                "shortcuts",
                _("Shortcuts"),
                icon_name="lucide-keyboard-symbolic",
            ),
        )
        SignalManager.__init__(self)

        self._shortcut_rows: dict[str, ShortcutsManagerRow] = {}

        self._user_shortcuts = app.app.get_user_shortcuts()

        self._load_shortcuts()

    def do_unroot(self) -> None:
        self._disconnect_all()
        del self._shortcut_rows
        GajimPreferencePage.do_unroot(self)

    def _load_shortcuts(self) -> None:
        preferences_groups: dict[str, GajimPreferencesGroup] = {}
        for category, title in SHORTCUT_CATEGORIES.items():
            preferences_group = GajimPreferencesGroup(key=category, title=title)
            preferences_groups[category] = preferences_group
            self.add(preferences_group)

        for action_name, shortcut_data in SHORTCUTS.items():
            if not shortcut_data.allow_rebind:
                continue

            row = ShortcutsManagerRow(action_name)
            self._connect(row, "activated", self._on_activated)

            custom_accelerators = self._user_shortcuts.get(action_name)
            if (
                custom_accelerators is not None
                and custom_accelerators != shortcut_data.accelerators
            ):
                row.set_accelerators(custom_accelerators, True)
            else:
                row.set_accelerators(shortcut_data.accelerators, False)

            preferences_groups[shortcut_data.category].add(row)
            self._shortcut_rows[action_name] = row

    def _on_activated(self, row: ShortcutsManagerRow) -> None:
        parent = cast(Adw.ApplicationWindow, self.get_root())
        KeyEntryDialog(self._on_shortcut_edited, row.action_name, parent=parent)

    def _on_shortcut_edited(
        self,
        response: Literal["reset", "apply"],
        action_name: str,
        new_accelerator_name: str,
    ) -> None:
        row = self._shortcut_rows[action_name]

        if response == "reset":
            self._user_shortcuts.pop(action_name, None)
            row.set_accelerators(SHORTCUTS[action_name].accelerators, False)
            app.app.set_user_shortcuts(self._user_shortcuts)
            return

        new_accelerators = [new_accelerator_name]
        if new_accelerators != SHORTCUTS[action_name].accelerators:
            self._user_shortcuts[action_name] = new_accelerators
            row.set_accelerators(new_accelerators, True)
            app.app.set_user_shortcuts(self._user_shortcuts)


@Gtk.Template(string=get_ui_string("shortcuts_manager_row.ui"))
class ShortcutsManagerRow(Adw.ActionRow):
    __gtype_name__ = "ShortcutsManagerRow"

    _accelerator_badge: Gtk.Label = Gtk.Template.Child()
    _accelerator_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, action_name: str):
        Adw.ActionRow.__init__(self)

        self._action_name = action_name
        self.set_activatable(True)
        self.set_title(SHORTCUTS[self._action_name].label)

    @property
    def action_name(self) -> str:
        return self._action_name

    def set_accelerators(self, accelerators: list[str], is_custom: bool) -> None:
        # Process first accelerator only
        accelerator_label = "-"
        if accelerators:
            success, keyval, state = Gtk.accelerator_parse(accelerators[0])
            if success:
                accelerator_label = Gtk.accelerator_get_label(keyval, state) or "-"

        self._accelerator_label.set_label(accelerator_label)
        self._accelerator_badge.set_visible(is_custom)


class KeyEntryDialog(AlertDialog):
    def __init__(
        self, callback: Callable[..., None], action_name: str, parent: Gtk.Window
    ) -> None:
        AlertDialog.__init__(
            self,
            heading=_("Edit Shortcut"),
            body=_(
                "Press the keys you want to associate with this action. "
                "To disable this shortcut, click apply."
            ),
            responses=[
                DialogResponse("close", _("Cancel")),
                DialogResponse("reset", _("Reset")),
                DialogResponse("apply", _("Apply"), "suggested", True),
            ],
            parent=parent,
        )

        self._callback = callback

        self._action_name = action_name

        self._accelerator_name = ""

        controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

        self._shortcut_label = Gtk.Label(label=_("No keys pressed"))
        self._shortcut_label.add_css_class("bold")
        self._shortcut_label.add_css_class("accent")
        self._shortcut_label.add_css_class("py-6")
        self.set_extra_child(self._shortcut_label)

        self.connect("response", self._on_response)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if not Gtk.accelerator_valid(keyval, state):
            # Modifier combination (e.g. Alt_L + Control_L)
            return Gdk.EVENT_STOP

        self._accelerator_name = Gtk.accelerator_name(keyval, state)
        self._shortcut_label.set_label(Gtk.accelerator_get_label(keyval, state))
        return Gdk.EVENT_STOP

    def _on_response(self, _dialog: Adw.AlertDialog, response_id: str) -> None:
        if response_id == "close":
            return

        self._callback(response_id, self._action_name, self._accelerator_name)
