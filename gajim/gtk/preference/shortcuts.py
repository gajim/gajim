# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import DialogResponse
from gajim.gtk.settings import GajimPreferencePage
from gajim.gtk.settings import GajimPreferencesGroup
from gajim.gtk.shortcut_manager import GajimShortcut
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

# All keyvals:
# https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gdk/gdkkeysyms.h

SHORTCUT_CATEGORIES = {
    "general": _("General"),
    "chats": _("Chats"),
    "messages": _("Messages"),
}


class ShortcutsPage(GajimPreferencePage, SignalManager):
    key = "shortcuts"
    icon_name = "lucide-keyboard-symbolic"
    label = _("Shortcuts")

    def __init__(self) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Shortcuts"),
            groups=[],
        )
        SignalManager.__init__(self)

        preferences_groups: dict[str, GajimPreferencesGroup] = {}
        for category, title in SHORTCUT_CATEGORIES.items():
            preferences_group = GajimPreferencesGroup(key=category, title=title)
            preferences_groups[category] = preferences_group
            self.add(preferences_group)

        self._manager = app.app.get_shortcut_manager()
        for shortcut in self._manager.iter_shortcuts():
            if not shortcut.allow_rebind:
                continue

            row = ShortcutRow(shortcut)
            self._connect(row, "activated", self._on_activated)

            preferences_groups[shortcut.category].add(row)

    def do_unroot(self) -> None:
        self._disconnect_all()
        GajimPreferencePage.do_unroot(self)

    def _on_activated(self, row: ShortcutRow) -> None:
        parent = cast(Adw.ApplicationWindow, self.get_root())
        dialog = KeyEntryDialog(parent=parent)
        dialog.connect("response", self._on_shortcut_edited, row.shortcut)

    def _on_shortcut_edited(
        self,
        dialog: KeyEntryDialog,
        response_id: str,
        shortcut: GajimShortcut,
    ) -> None:
        if response_id == "close":
            return

        if response_id == "reset":
            shortcut.reset()
            self._manager.store_user_shortcuts()
            return

        shortcut.set_custom_accelerators(dialog.get_accelerators())
        self._manager.store_user_shortcuts()


@Gtk.Template(string=get_ui_string("shortcut_row.ui"))
class ShortcutRow(Adw.ActionRow, SignalManager):
    __gtype_name__ = "ShortcutRow"

    _accelerator_badge: Gtk.Label = Gtk.Template.Child()
    _accelerator_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, shortcut: GajimShortcut) -> None:
        Adw.ActionRow.__init__(self)
        SignalManager.__init__(self)

        self._shortcut = shortcut
        self.set_activatable(True)
        self.set_title(shortcut.label)
        self._update_fields()

        self._connect(self._shortcut, "notify::trigger", self._on_trigger_changed)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Adw.ActionRow.do_unroot(self)

    def _update_fields(self):
        self._accelerator_badge.set_visible(self._shortcut.has_custom_accel())
        self._accelerator_label.set_label(self._shortcut.get_accel_label())

    def _on_trigger_changed(
        self, shortcut: GajimShortcut, _pspec: GObject.ParamSpec
    ) -> None:
        self._update_fields()

    @property
    def shortcut(self) -> GajimShortcut:
        return self._shortcut


class KeyEntryDialog(AlertDialog):
    def __init__(self, parent: Gtk.Window) -> None:
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

    def get_accelerators(self) -> list[str] | None:
        if self._accelerator_name:
            return [self._accelerator_name]
        return None

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
