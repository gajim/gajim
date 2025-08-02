#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import logging
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.modules.user_avatar import Avatar
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import BareContact

from gajim.gtk.avatar import clip_circle
from gajim.gtk.avatar_selector import AvatarSelector
from gajim.gtk.builder import get_builder
from gajim.gtk.filechoosers import AvatarFileChooserButton
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.util.misc import scroll_to_end
from gajim.gtk.vcard_grid import VCardGrid
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.profile")

MENU_DICT = {
    "fn": p_("Profile", "Full Name"),
    "bday": _("Birthday"),
    "gender": p_("Profile", "Gender"),
    "adr": p_("Profile", "Address"),
    "email": _("Email"),
    "impp": p_("Profile", "IM Address"),
    "tel": _("Phone No."),
    "org": p_("Profile", "Organisation"),
    "title": p_("Profile", "Title"),
    "role": p_("Profile", "Role"),
    "url": _("URL"),
    "key": p_("Profile", "Public Encryption Key"),
    "note": p_("Profile", "Note"),
}


class ProfileWindow(GajimAppWindow):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="ProfileWindow",
            title=_("Profile"),
            default_width=700,
            default_height=600,
        )

        self.account = account
        self._jid = app.get_jid_from_account(account)
        self._running_tasks: list[Task] = []
        self._destroyed = False

        self._client = app.get_client(self.account)
        self._client.connect_signal("state-changed", self._on_client_state_changed)

        self._contact = self._client.get_module("Contacts").get_contact(self._jid)

        self._ui = get_builder("profile.ui")

        menu = Gio.Menu()
        for action, label in MENU_DICT.items():
            menu.append(label, f"win.add-{action.lower()}")

        self._ui.add_entry_button.set_menu_model(menu)
        self._add_actions()

        self._connect(self._ui.back_button, "clicked", self._on_back_clicked)
        self._connect(self._ui.avatar_update_button, "clicked", self._on_update_avatar)
        self._connect(self._ui.edit_button, "clicked", self._on_edit_clicked)
        self._connect(self._ui.avatar_cancel, "clicked", self._on_cancel_update_avatar)
        self._connect(self._ui.save_button, "clicked", self._on_save_clicked)
        self._connect(self._ui.cancel_button, "clicked", self._on_cancel_clicked)
        self._connect(
            self._ui.avatar_nick_access, "notify::active", self._access_switch_toggled
        )
        self._connect(self._ui.remove_avatar_button, "clicked", self._on_remove_avatar)
        self._connect(
            self._ui.vcard_access, "notify::active", self._access_switch_toggled
        )

        self._avatar_edit_button = AvatarFileChooserButton(
            tooltip=_("Change your profile picture"),
            icon_name="document-edit-symbolic",
        )
        self._connect(self._avatar_edit_button, "path-picked", self._on_edit_avatar)

        self._avatar_edit_button.set_halign(Gtk.Align.END)
        self._avatar_edit_button.set_valign(Gtk.Align.END)
        self._avatar_edit_button.set_visible(False)
        self._ui.avatar_overlay.add_overlay(self._avatar_edit_button)

        self._avatar_selector: AvatarSelector | None = None
        self._current_avatar: Gdk.Texture | None = None
        self._current_vcard: VCard | None = None
        self._avatar_nick_public: bool | None = None

        # False  - no change to avatar
        # None   - we want to delete the avatar
        # Avatar - upload new avatar
        self._new_avatar: None | bool | Avatar = False

        self._ui.avatar_image.set_pixel_size(AvatarSize.VCARD)
        self._ui.nickname_entry.set_text(app.nicks[account])

        self._vcard_grid = VCardGrid(self.account)
        self._ui.profile_box.append(self._vcard_grid)

        self.set_child(self._ui.profile_stack)

        self._load_avatar()

        client = app.get_client(account)
        own_jid = client.get_own_jid().new_as_bare()
        client.get_module("VCard4").request_vcard(
            own_jid, callback=self._on_vcard_received
        )

        client.get_module("PubSub").get_access_model(
            Namespace.VCARD4_PUBSUB,
            callback=self._on_access_model_received,
            user_data=Namespace.VCARD4_PUBSUB,
        )

        client.get_module("PubSub").get_access_model(
            Namespace.AVATAR_METADATA,
            callback=self._on_access_model_received,
            user_data=Namespace.AVATAR_METADATA,
        )

        client.get_module("PubSub").get_access_model(
            Namespace.AVATAR_DATA,
            callback=self._on_access_model_received,
            user_data=Namespace.AVATAR_DATA,
        )

        client.get_module("PubSub").get_access_model(
            Namespace.NICK,
            callback=self._on_access_model_received,
            user_data=Namespace.NICK,
        )

    def _cleanup(self) -> None:
        self._destroyed = True
        del self._avatar_edit_button
        self._running_tasks.clear()
        self._avatar_selector = None
        self._client.disconnect_all_from_obj(self)

    def _on_client_state_changed(
        self, _client: Client, _signal_name: str, state: SimpleClientState
    ) -> None:

        self._ui.save_button.set_sensitive(state.is_connected)
        self._ui.save_button.set_tooltip_text(
            _("Not connected") if not state.is_connected else ""
        )

    @ensure_not_destroyed
    def _on_access_model_received(self, task: Task) -> None:
        namespace = task.get_user_data()

        try:
            result = task.finish()
        except StanzaError as error:
            log.warning("Unable to get access model for %s: %s", namespace, error)
            return

        access_model = result == "open"

        if namespace == Namespace.VCARD4_PUBSUB:
            self._set_vcard_access_switch(access_model)
        else:
            if self._avatar_nick_public is None:
                self._avatar_nick_public = access_model
            else:
                self._avatar_nick_public = self._avatar_nick_public or access_model
            assert self._avatar_nick_public is not None
            self._set_avatar_nick_access_switch(self._avatar_nick_public)

    @ensure_not_destroyed
    def _on_vcard_received(self, jid: JID, vcard: VCard):
        self._current_vcard = vcard

        self._load_avatar()
        self._vcard_grid.set_vcard(self._current_vcard.copy())
        self._show_profile_page()

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        assert isinstance(self._contact, BareContact)
        self._current_avatar = self._contact.get_avatar(
            AvatarSize.VCARD, scale, add_show=False
        )
        self._ui.avatar_image.set_from_paintable(self._current_avatar)
        self._ui.avatar_image.set_visible(True)

    def _add_actions(self) -> None:
        for action in MENU_DICT:
            action_name = f"add-{action.lower()}"
            act = Gio.SimpleAction.new(action_name, None)
            self._connect(act, "activate", self._on_action)
            self.window.add_action(act)

    def _on_action(self, action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        name = action.get_name()
        key = name.split("-")[1]
        self._vcard_grid.add_new_property(key)
        GLib.idle_add(scroll_to_end, self._ui.scrolled)

    def _on_edit_clicked(self, *args: Any) -> None:
        self._vcard_grid.set_editable(True)
        self._ui.edit_button.set_visible(False)

        self._ui.add_entry_button.set_visible(True)
        self._ui.cancel_button.set_visible(True)
        self._ui.save_button.set_visible(True)
        self._ui.remove_avatar_button.set_visible(True)
        self._avatar_edit_button.set_visible(True)
        self._ui.nickname_entry.set_sensitive(True)
        self._ui.privacy_button.set_visible(True)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._vcard_grid.set_editable(False)
        self._ui.edit_button.set_visible(True)
        self._ui.add_entry_button.set_visible(False)
        self._ui.cancel_button.set_visible(False)
        self._ui.save_button.set_visible(False)
        self._ui.remove_avatar_button.set_visible(False)
        self._ui.privacy_button.set_visible(False)
        self._ui.nickname_entry.set_sensitive(False)
        self._ui.avatar_image.set_from_paintable(self._current_avatar)
        self._ui.nickname_entry.set_text(app.nicks[self.account])
        self._vcard_grid.set_vcard(self._current_vcard.copy())  # pyright: ignore
        self._new_avatar = False

    def _on_back_clicked(self, *args: Any) -> None:
        self._show_profile_page()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        self._ui.add_entry_button.set_visible(False)
        self._ui.cancel_button.set_visible(False)
        self._ui.save_button.set_visible(False)
        self._ui.edit_button.set_visible(True)
        self._ui.remove_avatar_button.set_visible(False)
        self._ui.privacy_button.set_visible(False)
        self._ui.nickname_entry.set_sensitive(False)

        # Switch page after setting other widget's visibility
        # This avoids a leak caused by switching stack pages
        self._ui.profile_stack.set_visible_child_name("spinner")

        self._vcard_grid.validate()
        self._vcard_grid.sort()

        vcard = self._vcard_grid.get_vcard()
        self._current_vcard = vcard.copy()  # pyright: ignore

        client = app.get_client(self.account)
        task = client.get_module("VCard4").set_vcard(
            self._current_vcard,
            public=self._ui.vcard_access.get_active(),
            callback=self._on_set_vcard_result,
        )
        self._running_tasks.append(task)

        public = self._ui.avatar_nick_access.get_active()

        if self._new_avatar is False:
            if self._avatar_nick_public != public:
                client.get_module("UserAvatar").set_access_model(public)

        else:
            # Only update avatar if it changed
            task = client.get_module("UserAvatar").set_avatar(
                self._new_avatar, public=public, callback=self._on_set_avatar_result
            )
            self._running_tasks.append(task)

        self._avatar_nick_public = public

        nick = GLib.markup_escape_text(self._ui.nickname_entry.get_text())
        client.get_module("UserNickname").set_nickname(nick, public=public)

        if not nick:
            nick = app.get_default_nick(self.account)
        app.nicks[self.account] = nick

    @ensure_not_destroyed
    def _on_set_avatar_result(self, task: Task) -> None:
        self._running_tasks.remove(task)
        try:
            task.finish()
        except StanzaError as error:
            if self._new_avatar is None:
                # Trying to remove the avatar but the node does not exist
                if error.condition == "item-not-found":
                    return

            title = _("Error while uploading avatar")
            text = error.get_text()

            if (
                error.condition == "not-acceptable"
                and error.app_condition == "payload-too-big"
            ):
                text = _("Avatar file size too big")

            self._ui.avatar_image.set_from_paintable(self._current_avatar)
            self._new_avatar = False

            self._show_error_page(title, text)
            return

        self._client.update_presence(include_muc=True)
        if not self._running_tasks:
            self._show_profile_page()

    @ensure_not_destroyed
    def _on_set_vcard_result(self, task: Task) -> None:
        self._running_tasks.remove(task)
        try:
            task.finish()
        except StanzaError as error:
            log.error("Could not publish VCard: %s", error)
            self._show_error_page(_("Unable to save profile"), error.get_text())
            return

        self._vcard_grid.set_editable(False)
        if not self._running_tasks:
            self._show_profile_page()

    def _on_remove_avatar(self, _button: Gtk.Button) -> None:
        scale = self.get_scale_factor()
        assert isinstance(self._contact, BareContact)
        texture = self._contact.get_avatar(
            AvatarSize.VCARD, scale, add_show=False, default=True
        )

        self._ui.avatar_image.set_from_paintable(texture)
        self._ui.remove_avatar_button.set_visible(False)
        self._new_avatar = None

    def _on_edit_avatar(
        self, _button: AvatarFileChooserButton, paths: list[Path]
    ) -> None:
        if self._avatar_selector is None:
            self._avatar_selector = AvatarSelector()
            self._ui.avatar_selector_box.prepend(self._avatar_selector)

        self._avatar_selector.prepare_crop_area(str(paths[0]))
        self._ui.avatar_update_button.set_sensitive(
            self._avatar_selector.get_prepared()
        )
        self._ui.profile_stack.set_visible_child_name("avatar_selector")

    def _on_cancel_update_avatar(self, _button: Gtk.Button) -> None:
        self._show_profile_page()

    def _on_update_avatar(self, _button: Gtk.Button) -> None:
        error_title = _("Error while processing image")
        error_text = _("Failed to generate avatar.")

        assert self._avatar_selector
        success, data, width, height = self._avatar_selector.get_avatar_bytes()
        if not success:
            self._show_error_page(error_title, error_text)
            return

        assert data
        assert height
        assert width
        sha = app.app.avatar_storage.save_avatar(data)
        if sha is None:
            self._show_error_page(error_title, error_text)
            return

        self._new_avatar = Avatar()
        self._new_avatar.add_image_source(data, "image/png", height, width)

        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.surface_from_filename(
            sha, AvatarSize.VCARD, scale
        )
        if surface is None:
            return

        self._ui.avatar_image.set_from_paintable(
            convert_surface_to_texture(clip_circle(surface))
        )
        self._ui.remove_avatar_button.set_visible(True)
        self._show_profile_page()

    def _set_vcard_access_switch(self, state: bool) -> None:
        self._ui.vcard_access.set_active(state)
        self._ui.vcard_access_label.set_text(_("Everyone") if state else _("Contacts"))

    def _set_avatar_nick_access_switch(self, state: bool) -> None:
        self._ui.avatar_nick_access.set_active(state)
        self._ui.avatar_nick_access_label.set_text(
            _("Everyone") if state else _("Contacts")
        )

    def _access_switch_toggled(self, *args: Any) -> None:
        state = self._ui.vcard_access.get_active()
        self._set_vcard_access_switch(state)

        state = self._ui.avatar_nick_access.get_active()
        self._set_avatar_nick_access_switch(state)

    def _show_error_page(self, title: str, text: str) -> None:
        self._ui.error_title_label.set_text(title)
        self._ui.error_label.set_text(text)
        self._ui.profile_stack.set_visible_child_name("error")

    def _show_profile_page(self) -> None:
        self._running_tasks.clear()
        self._ui.profile_stack.set_visible_child_name("profile")
