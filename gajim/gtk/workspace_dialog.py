# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.avatar import make_workspace_avatar
from gajim.gtk.avatar_selector import AvatarSelector
from gajim.gtk.builder import get_builder
from gajim.gtk.const import DEFAULT_WORKSPACE_COLOR
from gajim.gtk.util.styling import make_rgba
from gajim.gtk.util.styling import rgba_to_float
from gajim.gtk.window import GajimAppWindow


class WorkspaceDialog(GajimAppWindow):
    def __init__(self, workspace_id: str | None = None) -> None:
        GajimAppWindow.__init__(
            self,
            name="WorkspaceDialog",
            title=_("Workspace Settings"),
            default_width=500,
            default_height=600,
            add_window_padding=True,
            header_bar=True,
        )

        self._workspace_id = workspace_id

        self._ui = get_builder("workspace_dialog.ui")
        self.set_child(self._ui.box)

        self._avatar_selector = AvatarSelector()
        self._avatar_selector.set_size_request(400, 300)
        self._ui.image_box.append(self._avatar_selector)

        name: str = _("My Workspace")
        color: str | None = None
        self._avatar_sha: str | None = None

        if app.settings.get_workspace_count() == 1:
            # Don't allow to remove last workspace
            self._ui.remove_workspace_button.set_sensitive(False)

        if workspace_id is None:
            # This is a new workspace
            self._ui.remove_workspace_button.set_sensitive(False)
        else:
            name = app.settings.get_workspace_setting(workspace_id, "name")
            color = app.settings.get_workspace_setting(workspace_id, "color")
            self._avatar_sha = app.settings.get_workspace_setting(
                workspace_id, "avatar_sha"
            )
            if self._avatar_sha == "":
                self._avatar_sha = None

        rgba = make_rgba(color or DEFAULT_WORKSPACE_COLOR)
        if self._avatar_sha is not None:
            self._ui.image_switch.set_active(True)
            self._ui.style_stack.set_visible_child_name("image")

        self._ui.entry.set_text(name)

        self._ui.color_dialog_button.set_dialog(Gtk.ColorDialog())
        self._ui.color_dialog_button.set_rgba(rgba)

        self._update_avatar()

        self._connect(self._ui.entry, "notify::text", self._on_text_changed)
        self._connect(
            self._ui.remove_workspace_button, "clicked", self._on_remove_workspace
        )
        self._connect(
            self._ui.image_switch, "notify::active", self._on_image_switch_toggled
        )
        self._connect(self._ui.color_dialog_button, "notify::rgba", self._on_color_set)
        self._connect(self._ui.cancel_button, "clicked", self._on_cancel)
        self._connect(self._ui.save_button, "clicked", self._on_save)
        self._connect(self._ui.entry, "notify::text", self._on_text_changed)

        self.set_default_widget(self._ui.save_button)

    def _on_remove_workspace(self, _button: Gtk.Button) -> None:
        assert self._workspace_id is not None
        app.window.remove_workspace(self._workspace_id)
        self.close()

    def _on_cancel(self, _button: Gtk.Button) -> None:
        self.close()

    def _on_color_set(self, _button: Gtk.ColorDialogButton, *args: Any) -> None:
        self._update_avatar()

    def _on_text_changed(self, entry: Gtk.Entry, _param: Any) -> None:
        self._ui.save_button.set_sensitive(bool(entry.get_text()))
        self._update_avatar()

    def _on_image_switch_toggled(self, switch: Gtk.Switch, *args: Any) -> None:
        self._avatar_selector.reset()
        if switch.get_active():
            self._ui.style_stack.set_visible_child_name("image")
            if self._workspace_id is not None:
                self._avatar_sha = app.settings.get_workspace_setting(
                    self._workspace_id, "avatar_sha"
                )
                if self._avatar_sha == "":
                    self._avatar_sha = None
        else:
            self._ui.style_stack.set_visible_child_name("color")
            self._avatar_sha = None

        self._update_avatar()

    def _update_avatar(self) -> None:
        name = self._ui.entry.get_text()
        rgba = self._ui.color_dialog_button.get_rgba()
        scale = self.get_scale_factor()
        if self._avatar_sha is not None:
            assert self._workspace_id is not None
            texture = app.app.avatar_storage.get_workspace_texture(
                self._workspace_id, AvatarSize.WORKSPACE_EDIT, scale
            )
        else:
            texture = make_workspace_avatar(
                name, rgba_to_float(rgba), AvatarSize.WORKSPACE_EDIT, scale
            )

        self._ui.preview.set_pixel_size(AvatarSize.WORKSPACE_EDIT)
        self._ui.preview.set_from_paintable(texture)

    def _get_avatar_data(self) -> bytes | None:
        if not self._avatar_selector.get_prepared():
            return None

        success, data, _wid, _hei = self._avatar_selector.get_avatar_bytes()
        if not success:
            return None

        return data

    def _on_save(self, _button: Gtk.Button) -> None:
        name = self._ui.entry.get_text()
        rgba = self._ui.color_dialog_button.get_rgba()
        use_image = self._ui.image_switch.get_active()
        if use_image:
            data = self._get_avatar_data()
            if data is not None:
                self._avatar_sha = app.app.avatar_storage.save_avatar(data)

        if self._workspace_id is not None:
            app.settings.set_workspace_setting(self._workspace_id, "name", name)
            app.settings.set_workspace_setting(
                self._workspace_id, "color", rgba.to_string()
            )
            if self._avatar_sha is None:
                app.settings.set_workspace_setting(self._workspace_id, "avatar_sha", "")
            else:
                app.settings.set_workspace_setting(
                    self._workspace_id, "avatar_sha", self._avatar_sha
                )

            app.window.update_workspace(self._workspace_id)
            self.close()
            return

        workspace_id = app.settings.add_workspace(name)
        app.settings.set_workspace_setting(workspace_id, "color", rgba.to_string())
        if self._avatar_sha is not None:
            app.settings.set_workspace_setting(
                workspace_id, "avatar_sha", self._avatar_sha
            )

        app.window.add_workspace(workspace_id)
        self.close()

    def _cleanup(self) -> None:
        pass
