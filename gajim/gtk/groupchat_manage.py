#
# SPDX-License-Identifier: GPL-3.0-only

import logging
from pathlib import Path

from gi.repository import Gtk
from nbxmpp.const import Affiliation
from nbxmpp.errors import StanzaError
from nbxmpp.modules.vcard_temp import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MucSubject
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.util.jid import validate_jid

from gajim.gtk.avatar_selector import AvatarSelector
from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.filechoosers import AvatarFileChooserButton
from gajim.gtk.util import get_app_window
from gajim.gtk.util import SignalManager

log = logging.getLogger("gajim.gtk.groupchat_manage")


class GroupchatManage(Gtk.Box, SignalManager):
    def __init__(
        self,
        account: str,
        contact: GroupchatContact,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)
        self._contact = contact
        self._contact.connect("room-subject", self._on_room_subject)

        self._room_config_form = None

        self._ui = get_builder("groupchat_manage.ui")
        self.append(self._ui.stack)

        self._avatar_chooser_button = AvatarFileChooserButton(
            tooltip=_("Change your profile picture"),
            icon_name="document-edit-symbolic",
        )
        self._avatar_chooser_button.set_halign(Gtk.Align.END)
        self._avatar_chooser_button.set_valign(Gtk.Align.END)
        self._avatar_chooser_button.set_visible(False)

        self._ui.avatar_overlay.add_overlay(self._avatar_chooser_button)

        self._connect(self._ui.remove_avatar_button, "clicked", self._on_remove_avatar)
        self._connect(
            self._ui.muc_description_entry, "changed", self._on_name_desc_changed
        )
        self._connect(self._ui.muc_name_entry, "changed", self._on_name_desc_changed)
        self._connect(self._ui.destroy_muc_button, "clicked", self._on_destroy_clicked)
        self._connect(
            self._ui.manage_save_button, "clicked", self._on_manage_save_clicked
        )
        self._connect(
            self._ui.subject_change_button, "clicked", self._on_subject_change_clicked
        )
        self._connect(
            self._ui.avatar_update_button, "clicked", self._on_avatar_update_clicked
        )
        self._connect(
            self._ui.avatar_cancel_button, "clicked", self._on_avatar_cancel_clicked
        )
        self._connect(
            self._ui.destroy_alternate_entry,
            "changed",
            self._on_destroy_alternate_changed,
        )
        self._connect(
            self._ui.destroy_cancel_button, "clicked", self._on_destroy_cancelled
        )
        self._connect(self._ui.destroy_button, "clicked", self._on_destroy_confirmed)
        self._connect(
            self._ui.subject_textview.get_buffer(),
            "changed",
            self._on_subject_text_changed,
        )
        self._connect(
            self._avatar_chooser_button, "path-picked", self._on_avatar_picked
        )

        self._avatar_selector = AvatarSelector()
        self._avatar_selector.set_size_request(500, 500)
        self._ui.avatar_selector_grid.attach(self._avatar_selector, 0, 1, 1, 1)

        self._prepare_subject()
        self._prepare_manage()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        del self._avatar_selector
        del self._avatar_chooser_button
        del self._room_config_form
        app.check_finalize(self)

    @property
    def disco_info(self):
        return app.storage.cache.get_last_disco_info(self._contact.jid)

    def _prepare_subject(self) -> None:
        text = ""
        if self._contact.subject is not None:
            text = self._contact.subject.text

        self._ui.subject_textview.get_buffer().set_text(text)
        self._ui.subject_textview.set_sensitive(self._is_subject_change_allowed())

    def _is_subject_change_allowed(self) -> bool:
        if not self._contact.is_joined:
            return False

        self_contact = self._contact.get_self()
        if self_contact is None:
            return False

        if self_contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
            return True

        if self.disco_info is None:
            return False
        return self.disco_info.muc_subjectmod or False

    def _on_subject_text_changed(self, buffer_: Gtk.TextBuffer) -> None:
        text = buffer_.get_text(buffer_.get_start_iter(), buffer_.get_end_iter(), False)

        assert self._contact.subject is not None

        self._ui.subject_change_button.set_sensitive(text != self._contact.subject.text)

    def _on_subject_change_clicked(self, _button: Gtk.Button) -> None:
        buffer_ = self._ui.subject_textview.get_buffer()
        subject = buffer_.get_text(
            buffer_.get_start_iter(), buffer_.get_end_iter(), False
        )
        self._client.get_module("MUC").set_subject(self._contact.jid, subject)

    def _on_room_subject(
        self, _contact: GroupchatContact, _signal_name: str, subject: MucSubject
    ) -> None:

        self._ui.subject_textview.get_buffer().set_text(subject.text)

        assert self._contact.subject is not None
        self._ui.subject_change_button.set_sensitive(
            subject.text != self._contact.subject.text
        )

    def _prepare_manage(self) -> None:
        joined = self._contact.is_joined
        vcard_support = False

        if self.disco_info is not None:
            vcard_support = self.disco_info.supports(Namespace.VCARD)

            self._ui.muc_name_entry.set_text(self.disco_info.muc_name or "")
            self._ui.muc_description_entry.set_text(
                self.disco_info.muc_description or ""
            )

        self.update_avatar()

        self_contact = self._contact.get_self()
        if not joined or self_contact is None:
            return

        if vcard_support and self_contact.affiliation.is_owner:
            self._avatar_chooser_button.show()
            self._ui.remove_avatar_button.show()

        if self_contact.affiliation.is_owner:
            self._client.get_module("MUC").request_config(
                self._contact.jid, callback=self._on_manage_form_received
            )
            self._ui.destroy_muc_button.set_sensitive(True)

    def _on_manage_form_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            log.info(error)
            return

        self._ui.muc_name_entry.set_sensitive(True)
        self._ui.muc_description_entry.set_sensitive(True)
        self._room_config_form = result.form

    def _on_name_desc_changed(self, _entry: Gtk.Entry) -> None:
        if self.disco_info is not None:
            disco_name = self.disco_info.muc_name or ""
            disco_desc = self.disco_info.muc_description or ""
            name = self._ui.muc_name_entry.get_text()
            desc = self._ui.muc_description_entry.get_text()

            self._ui.manage_save_button.set_sensitive(
                desc != disco_desc or name != disco_name
            )

    def _on_manage_save_clicked(self, _button: Gtk.Button) -> None:
        if self._room_config_form is not None:
            name = self._ui.muc_name_entry.get_text()
            desc = self._ui.muc_description_entry.get_text()
            try:
                name_field = self._room_config_form["muc#roomconfig_roomname"]
                desc_field = self._room_config_form["muc#roomconfig_roomdesc"]
            except KeyError:
                pass
            else:
                name_field.value = name
                desc_field.value = desc

            self._client.get_module("MUC").set_config(
                self._contact.jid, self._room_config_form
            )

    def _on_avatar_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_name("manage")

    def _on_remove_avatar(self, _button: Gtk.Button) -> None:
        vcard = VCard()
        self._client.get_module("VCardTemp").set_vcard(
            vcard, jid=self._contact.jid, callback=self._on_upload_avatar_result
        )

    def _on_avatar_picked(
        self, _button: AvatarFileChooserButton, paths: list[Path]
    ) -> None:
        self._avatar_selector.prepare_crop_area(str(paths[0]))
        self._ui.avatar_update_button.set_sensitive(
            self._avatar_selector.get_prepared()
        )
        self._ui.stack.set_visible_child_name("avatar")

    def _on_upload_avatar_result(self, task: Task) -> None:
        try:
            task.finish()
        except Exception as error:
            SimpleDialog(
                _("Uploading Avatar Failed"),
                _("Uploading avatar image failed: %s") % error,
            )

    def _on_avatar_update_clicked(self, _button: Gtk.Button) -> None:
        success, data, _w, _h = self._avatar_selector.get_avatar_bytes()
        if not success:
            SimpleDialog(_("Loading Avatar Failed"), _("Loading avatar image failed"))
            return

        assert data
        sha = app.app.avatar_storage.save_avatar(data)
        if sha is None:
            SimpleDialog(_("Saving Avatar Failed"), _("Saving avatar image failed"))
            return

        vcard = VCard()
        vcard.set_avatar(data, "image/png")  # pyright: ignore

        self._client.get_module("VCardTemp").set_vcard(
            vcard, jid=self._contact.jid, callback=self._on_upload_avatar_result
        )
        self._ui.stack.set_visible_child_name("manage")

    def update_avatar(self):
        texture = app.app.avatar_storage.get_muc_texture(
            self._account,
            self._contact.jid,
            AvatarSize.GROUP_INFO,
            self.get_scale_factor(),
        )

        self._ui.avatar_button_image.set_pixel_size(AvatarSize.GROUP_INFO)
        self._ui.avatar_button_image.set_from_paintable(texture)

    def _on_destroy_clicked(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_name("destroy")
        self._ui.destroy_reason_entry.grab_focus()

    def _on_destroy_alternate_changed(self, entry: Gtk.Entry) -> None:
        jid = entry.get_text()
        if jid:
            try:
                jid = validate_jid(jid)
            except Exception:
                icon = "dialog-warning-symbolic"
                text = _("Invalid XMPP Address")
                self._ui.destroy_alternate_entry.set_icon_from_icon_name(
                    Gtk.EntryIconPosition.SECONDARY, icon
                )
                self._ui.destroy_alternate_entry.set_icon_tooltip_text(
                    Gtk.EntryIconPosition.SECONDARY, text
                )
                self._ui.destroy_button.set_sensitive(False)
                return
        self._ui.destroy_alternate_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, None
        )
        self._ui.destroy_button.set_sensitive(True)

    def _on_destroy_confirmed(self, _button: Gtk.Button) -> None:
        reason = self._ui.destroy_reason_entry.get_text()
        alternate_jid = self._ui.destroy_alternate_entry.get_text()
        self._client.get_module("MUC").destroy(self._contact.jid, reason, alternate_jid)

        window = get_app_window("GroupchatDetails")
        assert window is not None
        window.close()

    def _on_destroy_cancelled(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_name("manage")
