#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.modules.user_avatar import Avatar
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.avatar import clip_circle
from gajim.gtk.avatar_selector import AvatarSelector
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.vcard_editor import ADDABLE_FIELDS
from gajim.gtk.vcard_editor import copy_vcard
from gajim.gtk.vcard_editor import VCardEditor
from gajim.gtk.vcard_editor import VCardRemoval

GObject.type_ensure(Adw.StatusPage)


@dataclass
class _ProfileDraft:
    vcard: VCard
    nickname: str


@Gtk.Template(string=get_ui_string("profile_editor.ui"))
class ProfileEditor(Gtk.Box, SignalManager):
    __gtype_name__ = "ProfileEditor"

    __gsignals__ = {
        "save-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (object, str),
        ),
        "cancel-requested": (GObject.SignalFlags.RUN_LAST, None, ()),
        "avatar-update-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (object, Gdk.Texture),
        ),
        "avatar-editing-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool,),
        ),
        "changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (str, str)),
    }

    _header_box: Gtk.Box = Gtk.Template.Child()
    _add_button: Gtk.MenuButton = Gtk.Template.Child()
    _cancel_button: Gtk.Button = Gtk.Template.Child()
    _save_button: Gtk.Button = Gtk.Template.Child()
    _profile_stack: Gtk.Stack = Gtk.Template.Child()
    _error_page: Adw.StatusPage = Gtk.Template.Child()
    _back_button: Gtk.Button = Gtk.Template.Child()
    _avatar_selector_box: Gtk.Box = Gtk.Template.Child()
    _avatar_cancel: Gtk.Button = Gtk.Template.Child()
    _avatar_update_button: Gtk.Button = Gtk.Template.Child()

    def __init__(
        self, scrolled: Gtk.ScrolledWindow, toast_overlay: Adw.ToastOverlay
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._scrolled = scrolled
        self._toast_overlay = toast_overlay
        self._avatar_selector: AvatarSelector | None = None
        self._snapshot: _ProfileDraft | None = None
        self._editing = False
        self._avatar_editing = False
        self._busy = False
        self._save_available = False
        self._save_unavailable_reason = ""

        self.remove(self._header_box)
        self.remove(self._avatar_selector_box)
        self._setup_header()
        self._setup_content()
        self._update_controls()

    def get_header(self) -> Gtk.Widget:
        return self._header_box

    def get_avatar_editor(self) -> Gtk.Widget:
        return self._avatar_selector_box

    def load_snapshot(self, vcard: VCard, nickname: str) -> None:
        self._toast_overlay.dismiss_all()
        self.finish_avatar_editing()
        self._snapshot = _ProfileDraft(copy_vcard(vcard), nickname)
        self._editing = False
        self._load_draft(self._snapshot)
        self._show_profile_page()

    def begin_edit(self) -> bool:
        if self._snapshot is None or self._busy:
            return False
        self._editing = True
        self._load_draft(self._snapshot)
        self._show_profile_page()
        return True

    def get_draft(self) -> tuple[VCard, str]:
        return self._vcard_editor.get_vcard(), self._vcard_editor.get_nickname()

    def get_change_state(self) -> tuple[bool, bool]:
        return self._vcard_editor.get_dirty_state()

    def has_unsaved_changes(self) -> bool:
        return self._editing and any(self._vcard_editor.get_dirty_state())

    def discard_changes(self, vcard: VCard, nickname: str) -> None:
        self.load_snapshot(vcard, nickname)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()

    def set_save_available(self, available: bool, reason: str = "") -> None:
        self._save_available = available
        self._save_unavailable_reason = reason
        self._update_save_button()

    def acknowledge_saved(self, vcard_saved: bool, nickname_saved: bool) -> None:
        assert self._snapshot is not None
        if vcard_saved:
            self._snapshot.vcard = self._vcard_editor.get_vcard()
        if nickname_saved:
            self._snapshot.nickname = self._vcard_editor.get_nickname()
        self._vcard_editor.acknowledge_saved(vcard_saved, nickname_saved)
        self._update_controls()

    def show_error(self, title: str, text: str) -> None:
        self._error_page.set_title(title)
        self._error_page.set_description(text)
        self._profile_stack.set_visible_child_name("error")
        self._update_controls()

    def start_avatar_edit(self, path: str | Path) -> bool:
        if self._busy:
            return False
        if self._avatar_selector is None:
            self._avatar_selector = AvatarSelector()
            self._connect(
                self._avatar_selector,
                "prepared-changed",
                self._update_controls,
            )
            self._avatar_selector_box.prepend(self._avatar_selector)
        self._avatar_selector.prepare_crop_area(str(path))
        if not self._avatar_editing:
            self._avatar_editing = True
            self.emit("avatar-editing-changed", True)
        return self._avatar_selector.prepared

    def finish_avatar_editing(self) -> None:
        if not self._avatar_editing:
            return
        self._avatar_editing = False
        self.emit("avatar-editing-changed", False)

    def end_edit(self) -> None:
        self._toast_overlay.dismiss_all()
        self.finish_avatar_editing()
        self._editing = False
        self._show_profile_page()

    def do_unroot(self) -> None:
        self._disconnect_all()
        self._avatar_selector = None
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _load_draft(self, draft: _ProfileDraft) -> None:
        self._vcard_editor.load(draft.vcard, draft.nickname)

    def _setup_header(self) -> None:
        self._add_menu = Gio.Menu()
        self._add_button.set_menu_model(self._add_menu)
        self._connect(self._cancel_button, "clicked", self._on_cancel_clicked)
        self._connect(self._save_button, "clicked", self._on_save_clicked)

        action_group = Gio.SimpleActionGroup()
        for action in ADDABLE_FIELDS:
            act = Gio.SimpleAction.new(f"add-{action}", None)
            self._connect(act, "activate", self._on_add_action)
            action_group.add_action(act)
        self._header_box.insert_action_group("profile", action_group)

    def _update_add_menu(self, *_args: object) -> None:
        present = self._vcard_editor.get_present_field_names()
        self._add_menu.remove_all()
        for name, label in ADDABLE_FIELDS.items():
            if name in present:
                continue
            self._add_menu.append(label, f"profile.add-{name}")
        self._update_controls()

    def _update_controls(self, *_args: object) -> None:
        editable = self._editing and not self._busy
        self._vcard_editor.set_sensitive(editable)
        self._cancel_button.set_sensitive(editable)
        self._add_button.set_sensitive(editable and self._add_menu.get_n_items() > 0)
        self._avatar_selector_box.set_sensitive(not self._busy)
        self._avatar_cancel.set_sensitive(not self._busy)
        self._avatar_update_button.set_sensitive(
            not self._busy
            and self._avatar_selector is not None
            and self._avatar_selector.prepared
        )
        self._back_button.set_sensitive(not self._busy)
        self._update_save_button()

    def _setup_content(self) -> None:
        self._vcard_editor = VCardEditor()
        self._connect(self._vcard_editor, "changed", self._on_vcard_editor_changed)
        self._connect(self._vcard_editor, "properties-changed", self._update_add_menu)
        self._connect(self._vcard_editor, "property-removed", self._on_property_removed)
        self._vcard_editor.load(VCard(), "")
        self._profile_stack.add_named(self._vcard_editor, "profile")
        self._connect(self._avatar_cancel, "clicked", self._on_cancel_update_avatar)
        self._connect(self._avatar_update_button, "clicked", self._on_update_avatar)
        self._connect(self._back_button, "clicked", self._on_back_clicked)
        self._profile_stack.set_visible_child_name("profile")
        self._update_add_menu()

    def _update_save_button(self) -> None:
        has_changes = self.has_unsaved_changes()
        self._save_button.set_sensitive(
            self._editing and self._save_available and has_changes and not self._busy
        )
        if self._busy:
            tooltip = _("Please wait for the profile update to finish")
        elif not self._save_available:
            tooltip = self._save_unavailable_reason or _("Saving is unavailable")
        elif not has_changes:
            tooltip = _("No changes to save")
        else:
            tooltip = ""
        self._save_button.set_tooltip_text(tooltip)

    def _on_add_action(
        self, action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        if not self._editing or self._busy:
            return
        row = self._vcard_editor.add_field(action.get_name().removeprefix("add-"))
        GLib.idle_add(self._scroll_to_row, row)

    def _scroll_to_row(self, row: Gtk.ListBoxRow) -> bool:
        success, bounds = row.compute_bounds(self._scrolled)
        if not success:
            return row.get_root() is not None

        adjustment = self._scrolled.get_vadjustment()
        row_top = bounds.get_y()
        row_bottom = row_top + bounds.get_height()
        value = adjustment.get_value()
        if row_top < 0:
            value += row_top
        elif row_bottom > adjustment.get_page_size():
            value += row_bottom - adjustment.get_page_size()

        upper = adjustment.get_upper() - adjustment.get_page_size()
        adjustment.set_value(max(adjustment.get_lower(), min(value, upper)))
        row.grab_focus()
        return False

    def _on_property_removed(self, _editor: VCardEditor, removal: VCardRemoval) -> None:
        toast = Adw.Toast(
            title=_("Removed %(field)s") % {"field": removal.label},
            timeout=3,
            button_label=_("Undo"),
        )
        self._connect(toast, "button-clicked", self._on_removal_undo_clicked, removal)
        self._connect(toast, "dismissed", self._on_removal_dismissed, removal)
        self._toast_overlay.add_toast(toast)

    def _on_removal_undo_clicked(self, toast: Adw.Toast, removal: VCardRemoval) -> None:
        self._vcard_editor.undo_removal(removal)
        toast.dismiss()

    def _on_removal_dismissed(self, toast: Adw.Toast, removal: VCardRemoval) -> None:
        self._vcard_editor.finalize_removal(removal)
        self._disconnect_object(toast)

    def _on_vcard_editor_changed(self, *_args: object) -> None:
        self._update_save_button()
        self.emit("changed")

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        if self._editing and not self._busy:
            self.emit("cancel-requested")

    def _on_back_clicked(self, *_args: object) -> None:
        if self._busy:
            return
        self._show_profile_page()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        if (
            not self._editing
            or self._busy
            or not self._save_available
            or not self.has_unsaved_changes()
        ):
            return

        self._toast_overlay.dismiss_all()
        self._vcard_editor.validate()
        if not self.has_unsaved_changes():
            return
        vcard, nickname = self.get_draft()
        self.emit("save-requested", vcard, nickname)

    def _on_cancel_update_avatar(self, _button: Gtk.Button) -> None:
        if not self._busy:
            self.finish_avatar_editing()

    def _on_update_avatar(self, _button: Gtk.Button) -> None:
        if self._busy or self._avatar_selector is None:
            return
        success, data, width, height = self._avatar_selector.get_avatar_bytes()
        if not success or data is None:
            self._fail_avatar_update()
            return

        sha = app.app.avatar_storage.save_avatar(data)
        if sha is None:
            self._fail_avatar_update()
            return

        new_avatar = Avatar()
        new_avatar.add_image_source(data, "image/png", height, width)

        surface = app.app.avatar_storage.surface_from_filename(
            sha, AvatarSize.PUBLISH, self.get_scale_factor()
        )
        if surface is None:
            self._fail_avatar_update()
            return
        preview = convert_surface_to_texture(clip_circle(surface))
        self.emit(
            "avatar-update-requested",
            new_avatar,
            preview,
        )
        self.finish_avatar_editing()

    def _fail_avatar_update(self) -> None:
        self.finish_avatar_editing()
        self.emit(
            "error",
            _("Error while processing image"),
            _("Failed to generate avatar."),
        )

    def _show_profile_page(self) -> None:
        self._profile_stack.set_visible_child_name("profile")
        self._update_controls()
