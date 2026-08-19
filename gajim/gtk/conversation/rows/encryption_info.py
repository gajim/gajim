# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast
from typing import Literal

from gi.repository import Gtk
from nbxmpp.task import Task

from gajim.common.const import AvatarSize
from gajim.common.const import EncryptionInfoMsg
from gajim.common.events import EncryptionInfo
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.omemo import SessionRefreshResult
from gajim.common.modules.omemo import SessionRefreshStatus
from gajim.common.util.datetime import utc_now

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel
from gajim.gtk.util.window import open_window


class EncryptionInfoRow(BaseRow):
    def __init__(self, event: EncryptionInfo) -> None:
        BaseRow.__init__(self, event.account)

        self.type = "encryption_info"
        timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self._event = event
        self._refresh_button: Gtk.Button | None = None

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)

        icon = Gtk.Image.new_from_icon_name("lucide-lock-symbolic")
        icon.set_pixel_size(AvatarSize.ROSTER)
        icon.add_css_class("dimmed")
        avatar_placeholder.append(icon)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        timestamp_widget.set_margin_start(0)
        self.grid.attach(timestamp_widget, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.set_text(event.message)
        self.grid.attach(self._label, 1, 1, 1, 1)

        if event.type in (
            EncryptionInfoMsg.BROKEN_SESSION,
            EncryptionInfoMsg.NO_FINGERPRINTS,
            EncryptionInfoMsg.UNDECIDED_FINGERPRINTS,
        ):
            if event.type == EncryptionInfoMsg.BROKEN_SESSION:
                button_box = Gtk.Box(spacing=6)
                self._refresh_button = Gtk.Button(label=_("Refresh Encryption"))
                self._connect(
                    self._refresh_button,
                    "clicked",
                    self._on_refresh_encryption_clicked,
                )
                button_box.append(self._refresh_button)

                settings_button = Gtk.Button(label=_("Open Encryption Settings"))
                self._connect(settings_button, "clicked", self._on_manage_trust_clicked)
                button_box.append(settings_button)
                button_box.set_halign(Gtk.Align.START)
                self.grid.attach(button_box, 1, 2, 1, 1)
                return
            else:
                label = _("Manage Trust")
            button = Gtk.Button(label=label)
            button.set_halign(Gtk.Align.START)
            self._connect(button, "clicked", self._on_manage_trust_clicked)
            self.grid.attach(button, 1, 2, 1, 1)

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        jid = self._event.repair_jid or self._event.jid
        contact = self._client.get_module("Contacts").get_contact(jid)
        if contact.is_groupchat:
            open_window("GroupchatDetails", contact=contact, page="encryption-omemo")
            return

        if isinstance(contact, BareContact) and contact.is_self:
            window = open_window("Preferences")
            window.show_page(f"{contact.account}-encryption-omemo")
            return

        open_window(
            "ContactInfo",
            account=contact.account,
            contact=contact,
            page="encryption-omemo",
        )

    def _on_refresh_encryption_clicked(self, _button: Gtk.Button) -> None:
        repair_jid = self._event.repair_jid
        device_id = self._event.device_id
        assert repair_jid is not None
        assert device_id is not None

        def _on_response() -> None:
            contact = self._client.get_module("Contacts").get_contact(self._event.jid)
            destination = None
            message_type: Literal["chat", "groupchat"] = "chat"
            if contact.is_groupchat:
                destination = str(contact.jid)
                message_type = "groupchat"

            module = self._client.get_module("OMEMO")
            assert self._refresh_button is not None
            self._refresh_button.set_sensitive(False)
            task = module.refresh_session(
                str(repair_jid),
                device_id,
                destination=destination,
                message_type=message_type,
            )
            task.add_done_callback(self._on_refresh_finished)

        ConfirmationAlertDialog(
            _("Refresh Encryption?"),
            _(
                "This creates new encryption state for future messages. Messages "
                "that could not be read before stay unreadable."
            ),
            confirm_label=_("_Refresh Encryption"),
            callback=_on_response,
        )

    def _on_refresh_finished(self, task: Task) -> None:
        assert self._refresh_button is not None
        self._refresh_button.set_sensitive(True)
        try:
            result = cast(SessionRefreshResult, task.finish())
        except Exception:
            result = SessionRefreshResult(
                SessionRefreshStatus.BUILD_FAILED,
                str(self._event.repair_jid),
                self._event.device_id or 0,
            )

        if result.status == SessionRefreshStatus.SUCCESS:
            InformationAlertDialog(
                _("Encryption Refresh Sent"),
                _(
                    "A new encryption handshake was sent. Future messages will "
                    "confirm whether encryption works again."
                ),
            )
            return

        InformationAlertDialog(
            _("Encryption Refresh Failed"),
            _("Gajim could not refresh encryption for this device."),
        )
