#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from enum import IntEnum

from gi.repository import Adw
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common.helpers import idle_add_once

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.vcard_grid import LABEL_DICT
from gajim.gtk.vcard_listbox import VCardListBox


class EditorState(IntEnum):
    READ_ONLY = 0
    EDIT = 1
    PROGRESS = 2
    ERROR = 3


@Gtk.Template(string=get_ui_string("vcard_editor.ui"))
class VCardEditor(Adw.PreferencesGroup, SignalManager):
    __gtype_name__ = "VCardEditor"

    __gsignals__ = {
        "request-save": (GObject.SignalFlags.RUN_LAST, None, (object,)),
        "scroll-to": (GObject.SignalFlags.RUN_LAST, None, (Gtk.ListBoxRow,)),
    }

    _header_stack: Gtk.Stack = Gtk.Template.Child()
    _edit_button: Gtk.MenuButton = Gtk.Template.Child()
    _header_box: Gtk.Box = Gtk.Template.Child()
    _add_button: Gtk.MenuButton = Gtk.Template.Child()
    _cancel_button: Gtk.Button = Gtk.Template.Child()
    _save_button: Gtk.Button = Gtk.Template.Child()
    _content_stack: Gtk.Stack = Gtk.Template.Child()
    _error_page: Adw.StatusPage = Gtk.Template.Child()
    _back_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        Adw.PreferencesGroup.__init__(self)
        SignalManager.__init__(self)

        self._in_progress = False

        self._vcard: VCard = VCard()
        self._vcard_listbox = VCardListBox()
        self._content_stack.add_named(self._vcard_listbox, "vcard")

        field_menu = Gio.Menu()
        for name, label in LABEL_DICT.items():
            field_menu.append(label, f"profile.add-{name}")
        self._add_button.set_menu_model(field_menu)

        action_group = Gio.SimpleActionGroup()
        for action in LABEL_DICT:
            act = Gio.SimpleAction.new(f"add-{action}", None)
            self._connect(act, "activate", self._on_add_action)
            action_group.add_action(act)
        self._header_box.insert_action_group("profile", action_group)

        self._connect(
            self._cancel_button,
            "clicked",
            self._on_button_clicked,
            EditorState.READ_ONLY,
        )
        self._connect(
            self._back_button, "clicked", self._on_button_clicked, EditorState.EDIT
        )
        self._connect(
            self._edit_button, "clicked", self._on_button_clicked, EditorState.EDIT
        )
        self._connect(
            self._save_button, "clicked", self._on_button_clicked, EditorState.PROGRESS
        )

        self._content_stack.set_visible_child_name("vcard")

    def run_destroy(self) -> None:
        self._disconnect_all()
        app.check_finalize(self)

    def get_vcard(self) -> VCard:
        return self._vcard

    def set_vcard(self, vcard: VCard) -> None:
        self._vcard = vcard
        self._set_state(EditorState.READ_ONLY)

    def set_save_successful(self):
        self._vcard = self._vcard_listbox.get_vcard()
        self._set_state(EditorState.READ_ONLY)

    def set_error(self, title: str, text: str) -> None:
        self._error_page.set_title(title)
        self._error_page.set_description(text)
        self._set_state(EditorState.ERROR)

    def set_enabled(self, enabled: bool, reason: str = "") -> None:
        self._save_button.set_sensitive(enabled)
        self._save_button.set_tooltip_text(reason)
        self._edit_button.set_sensitive(enabled)
        self._edit_button.set_tooltip_text(reason)

    def _on_add_action(
        self, action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        field = action.get_name().removeprefix("add-")
        row = self._vcard_listbox.add_field(field)
        idle_add_once(self.emit, "scroll-to", row)

    def _set_state(self, state: EditorState) -> None:
        match state:
            case EditorState.READ_ONLY:
                self._vcard_listbox.load(self._vcard, edit_mode=False)
                self._header_stack.set_visible_child_name("read-only")
                self._content_stack.set_visible_child_name("vcard")

            case EditorState.EDIT:
                if not self._vcard_listbox.in_edit_mode():
                    self._vcard_listbox.load(self._vcard, edit_mode=True)
                self._header_stack.set_visible_child_name("edit")
                self._content_stack.set_visible_child_name("vcard")

            case EditorState.PROGRESS:
                self._header_stack.set_visible_child_name("empty")
                self._content_stack.set_visible_child_name("progress")
                self.emit("request-save", self._vcard.copy())

            case EditorState.ERROR:
                self._header_stack.set_visible_child_name("empty")
                self._content_stack.set_visible_child_name("error")

            case _:
                raise ValueError("Unknown state {state}")

    def _on_button_clicked(self, _button: Gtk.Button, state: EditorState) -> None:
        self._set_state(state)
