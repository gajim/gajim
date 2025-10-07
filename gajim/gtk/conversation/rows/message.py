# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import textwrap
from datetime import datetime
from datetime import timedelta

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Trust
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.i18n import _
from gajim.common.i18n import is_rtl_text
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.types import ChatContactT
from gajim.common.util.muc import message_needs_highlight
from gajim.common.util.preview import GeoPreview
from gajim.common.util.preview import get_preview_data
from gajim.common.util.preview import UrlPreview
from gajim.common.util.text import format_fingerprint
from gajim.common.util.user_strings import get_moderation_text
from gajim.common.util.user_strings import get_retraction_text

from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.conversation.reactions_bar import ReactionsBar
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import AvatarBox
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import MessageIcons
from gajim.gtk.conversation.rows.widgets import NicknameLabel
from gajim.gtk.menus import GajimMenu
from gajim.gtk.menus import get_chat_row_menu
from gajim.gtk.preview.geo import GeoPreviewWidget
from gajim.gtk.preview.open_graph import OpenGraphPreviewWidget
from gajim.gtk.preview.preview import PreviewWidget
from gajim.gtk.referenced_message import ReferencedMessageNotFoundWidget
from gajim.gtk.referenced_message import ReferencedMessageWidget
from gajim.gtk.util.misc import container_remove_all
from gajim.gtk.util.misc import get_avatar_for_message
from gajim.gtk.util.misc import get_contact_name_for_message

log = logging.getLogger("gajim.gtk.conversation.rows.message")

MERGE_TIMEFRAME = timedelta(seconds=120)


class MessageRow(BaseRow):
    def __init__(self, contact: ChatContactT, message: Message) -> None:

        BaseRow.__init__(self, contact.account)
        self.set_selectable(True)
        self.type = "chat"
        self._contact = contact
        self._message = message

        self.timestamp = message.timestamp.astimezone()
        self.db_timestamp = message.timestamp.timestamp()
        self.direction = ChatDirection(message.direction)
        self._is_outgoing = self.direction == ChatDirection.OUTGOING

        # Classes for identifying message direction via CSS
        if self._is_outgoing:
            self.add_css_class("outgoing-message")
        else:
            self.add_css_class("incoming-message")

        self.orig_pk = message.pk
        self.pk = self.orig_pk

        self.encryption = None
        self.securitylabel = None

        assert message.text is not None
        self._original_text = message.text
        self._original_message = message

        self._is_retracted = bool(message.moderation or message.retraction)
        self._is_blocked = False
        self._has_receipt = False

        self._avatar_box = AvatarBox(contact)

        self._ref_message_widget = None

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.set_hexpand(True)

        self._bottom_box = Gtk.Box(spacing=6)

        self.grid.attach(self._avatar_box, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(self._bottom_box, 1, 1, 1, 1)

        self._reactions_bar = ReactionsBar(self, self._contact)
        self.grid.attach(self._reactions_bar, 1, 2, 1, 1)

        self._redraw_content()

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)

    @classmethod
    def from_db_row(cls, contact: ChatContactT, message: Message) -> MessageRow:
        return cls(contact, message)

    @property
    def state(self) -> int:
        return self._message.state

    @property
    def has_receipt(self) -> bool:
        return self._has_receipt

    @property
    def is_merged(self) -> bool:
        return self._merged

    @property
    def occupant_id(self) -> str | None:
        if self._message.occupant is None:
            return None
        return self._message.occupant.id

    def _redraw_content(self) -> None:
        self.set_merged(False)
        self.remove_css_class("retracted-message")
        self.remove_css_class("gajim-mention-highlight")

        container_remove_all(self._meta_box)
        container_remove_all(self._bottom_box)

        message = self._original_message

        self.name = get_contact_name_for_message(message, self._contact)

        avatar = get_avatar_for_message(
            message, self._contact, self.get_scale_factor(), AvatarSize.ROSTER
        )
        self._avatar_box.set_from_paintable(avatar)
        self._avatar_box.set_name(self.name)

        self._meta_box.append(NicknameLabel(self.name, self._is_outgoing))
        self._meta_box.append(DateTimeLabel(self.timestamp))

        self._message_icons = MessageIcons()
        self._meta_box.append(self._message_icons)

        self._is_blocked = False
        if message.occupant is not None and message.occupant.blocked:
            self._set_blocked()
            return

        if message.is_retracted():
            self._set_retracted(message)
            return

        # From here on, if this is a correction all data must
        # be taken from the correction
        if corrected_message := message.get_last_correction():
            message = corrected_message
            self._message = corrected_message

        self.pk = message.pk

        self.encryption = message.encryption
        self.securitylabel = message.security_label

        assert message.text is not None
        self.text = message.text

        match preview := get_preview_data(self.text, message.oob):
            case UrlPreview():
                self._message_widget = PreviewWidget(
                    self._contact.account, preview, self._is_outgoing, self._muc_context
                )

            case GeoPreview():
                self._message_widget = GeoPreviewWidget(preview)

            case _:
                if message.reply is not None:
                    referenced_message = message.get_referenced_message()
                    if referenced_message is None:
                        self._ref_message_widget = ReferencedMessageNotFoundWidget()
                    else:
                        self._ref_message_widget = ReferencedMessageWidget(
                            self._contact, referenced_message
                        )

                self._message_widget = MessageWidget(self._contact.account)
                self._message_widget.add_with_styling(self.text, nickname=self.name)
                if self._contact.is_groupchat and not self._is_outgoing:
                    self._apply_highlight(self.text)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        if self._ref_message_widget is not None:
            box.append(self._ref_message_widget)

        box.append(self._message_widget)

        for og in message.og:
            box.append(OpenGraphPreviewWidget(og))

        self._bottom_box.append(box)

        self._set_text_direction(self.text)

        if corrected_message:
            self._set_correction()

        self._reactions_bar.update_from_reactions(
            self._original_message.get_reactions()
        )

        encryption_data = self._get_encryption_data(message.encryption)
        if encryption_data is not None:
            self._message_icons.set_encrytion_icon_data(*encryption_data)
            self._message_icons.set_encryption_icon_visible(True)

        sec_label_data = self._get_security_labels_data(message.security_label)
        if sec_label_data is not None:
            self._message_icons.set_security_label_data(*sec_label_data)
            self._message_icons.set_security_label_visible(True)

        self._set_receipt(message.receipt is not None)

        if self._contact.is_groupchat and self.direction == ChatDirection.OUTGOING:
            self._message_icons.set_message_state_icon(MessageState(message.state))

        if message.error is not None:
            if message.error.text is not None:
                error_text = f"{message.error.text} ({message.error.condition})"
            else:
                error_text = message.error.condition
            self._set_error(error_text)

    def _set_text_direction(self, text: str) -> None:
        global_rtl = self._message_widget.get_direction() == Gtk.TextDirection.RTL
        message_rtl = is_rtl_text(text)

        if (global_rtl and not message_rtl) or (not global_rtl and message_rtl):
            # LTR message in an RTL environment (align to the left) or
            # RTL message in an LTR environment (align to the right)
            self._bottom_box.set_halign(Gtk.Align.END)

    @property
    def _muc_context(self) -> str | None:
        if isinstance(self._contact, GroupchatContact | GroupchatParticipant):
            return self._contact.muc_context
        return None

    def get_chat_row_menu(
        self,
    ) -> GajimMenu:

        copy_text = self._get_copy_text(self.get_text(), self.name, self.timestamp)

        return get_chat_row_menu(
            contact=self._contact,
            copy_text=copy_text,
            message=self._message,
            original_message=self._original_message,
        )

    @staticmethod
    def _get_copy_text(text: str, name: str, timestamp: datetime) -> str | None:
        # Text can be an empty string
        # e.g. if a preview has not been loaded yet
        if not text:
            return None

        timestamp_formatted = timestamp.strftime(app.settings.get("date_time_format"))

        copy_text = f"{timestamp_formatted} - {name}: "
        if text.startswith(("```", "> ")):
            # Prepend a line break in order to keep code block/quotes rendering
            copy_text += "\n"
        copy_text += text
        return copy_text

    def enable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(False)

    def disable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(True)

    def _get_security_labels_data(
        self, security_labels: mod.SecurityLabel | None
    ) -> tuple[str, str] | None:

        if security_labels is None:
            return None

        if not app.settings.get_account_setting(
            self._account, "enable_security_labels"
        ):
            return None

        displaymarking = GLib.markup_escape_text(security_labels.displaymarking)
        if displaymarking:
            bgcolor = security_labels.bgcolor
            fgcolor = security_labels.fgcolor
            markup = (
                f'<span size="small" bgcolor="{bgcolor}" '
                f'fgcolor="{fgcolor}"><tt>{displaymarking}</tt></span>'
            )
            return displaymarking, markup
        return None

    def _apply_highlight(self, text: str) -> None:
        assert isinstance(self._contact, GroupchatContact)
        if self._contact.nickname is None:
            return

        if message_needs_highlight(
            text, self._contact.nickname, self._client.get_own_jid().bare
        ):
            self.add_css_class("gajim-mention-highlight")

    def is_same_sender(self, message: MessageRow) -> bool:
        return message.name == self.name

    def is_same_encryption(self, message: MessageRow) -> bool:
        c_enc = message.encryption
        o_enc = self.encryption
        if c_enc is None and o_enc is None:
            return True

        if c_enc is not None and o_enc is not None:
            if c_enc.protocol == o_enc.protocol and c_enc.trust == o_enc.trust:
                return True

        return False

    def is_same_securitylabels(self, message: MessageRow) -> bool:
        sec1 = message.securitylabel
        sec2 = self.securitylabel

        if sec1 is None and sec2 is None:
            return True

        if sec1 is None or sec2 is None:
            return False

        return sec1.label_hash == sec2.label_hash

    def is_same_state(self, message: MessageRow) -> bool:
        return message.state == self._message.state

    def has_same_receipt_status(self, message: MessageRow) -> bool:
        if not app.settings.get("positive_184_ack"):
            return True
        return self._has_receipt == message.has_receipt

    def is_mergeable(self, message: MessageRow) -> bool:
        if message.type != self.type:
            return False
        if not self.is_same_state(message):
            return False
        if message.direction != self.direction:
            return False
        if self._message.correction_id is not None:
            return False
        if not self.is_same_sender(message):
            return False
        if not self.is_same_encryption(message):
            return False
        if not self.is_same_securitylabels(message):
            return False
        if not self.has_same_receipt_status(message):
            return False
        return abs(message.timestamp - self.timestamp) < MERGE_TIMEFRAME

    def get_text(self) -> str:
        return self._message_widget.get_text()

    def _get_encryption_data(
        self,
        encryption_data: mod.Encryption | None,
    ) -> tuple[str, str, str] | None:

        contact_encryption = self._contact.settings.get("encryption")
        if encryption_data is None:
            if not contact_encryption:
                return None

            icon = "channel-insecure-symbolic"
            color = "unencrypted-color"
            tooltip = _("Not encrypted")
        else:
            tooltip = _("Encrypted (%s)") % (encryption_data.protocol)
            icon, trust_tooltip, color = TRUST_SYMBOL_DATA[Trust(encryption_data.trust)]
            tooltip = f"{tooltip}\n{trust_tooltip}"
            if encryption_data.key != "Unknown":
                fingerprint = format_fingerprint(encryption_data.key)
                tooltip = f"{tooltip}\n<tt>{fingerprint}</tt>"

        return icon, color, tooltip

    def set_acknowledged(self, pk: int) -> None:
        if self._original_message.pk == pk:
            message = self._original_message
        elif self._message.pk == pk:
            message = self._message
        else:
            raise ValueError("Acknowledged unknown message")

        app.storage.archive.refresh(message, ["stanza_id", "state"])

        if self._is_retracted:
            return

        self._message_icons.set_message_state_icon(MessageState(message.state))

    def set_blocked(self, blocked: bool) -> None:
        if blocked != self._is_blocked:
            app.storage.archive.refresh(self._original_message, ["occupant"])
            self._redraw_content()

    def _set_receipt(self, value: bool) -> None:
        if self._is_retracted:
            return

        self._has_receipt = value
        self._message_icons.set_receipt_icon_visible(value)

    def set_receipt(self, receipt_id: str) -> None:
        if self._message.id == receipt_id:
            self._set_receipt(True)

    def _set_error(self, tooltip: str) -> None:
        if self._is_retracted:
            return

        self._message_icons.hide_message_state_icon()
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)

    def set_error(self, error_id: str, text: str) -> None:
        if self._message.id == error_id:
            self._set_error(text)
            self.set_merged(False)

    def update_reactions(self) -> None:
        app.storage.archive.refresh(
            self._original_message, ["corrections", "reactions"]
        )
        if self._is_retracted:
            return

        self._reactions_bar.update_from_reactions(
            self._original_message.get_reactions()
        )

    def update_retractions(self) -> None:
        app.storage.archive.refresh(
            self._original_message, ["corrections", "retraction", "moderation"]
        )
        self._redraw_content()

    def update_corrections(self) -> None:
        app.storage.archive.refresh(self._original_message, ["corrections"])
        self._redraw_content()

    def send_reaction(self, emoji: str, toggle: bool = True) -> None:
        """Adds or removes 'emoji' from this message's reactions and sends the result.

        Args:
          emoji: Reaction emoji to add or remove
          toggle: Whether an existing emoji should be removed from the set
        """
        reaction_id = self._original_message.id
        if self._original_message.type == MessageType.GROUPCHAT:
            reaction_id = self._original_message.stanza_id

        if reaction_id is None:
            log.warning("No reaction id")
            return

        our_reactions = self._reactions_bar.get_our_reactions()
        if emoji in our_reactions and not toggle:
            log.info("Not toggling reaction <%s>", emoji)
            return

        if emoji in our_reactions:
            our_reactions.discard(emoji)
        elif self._contact.reactions_per_user == 1:
            our_reactions = {emoji}
        else:
            our_reactions.add(emoji)

        client = app.get_client(self._contact.account)
        client.get_module("Reactions").send_reaction(
            contact=self._contact, reaction_id=reaction_id, reactions=our_reactions
        )

    def _set_retracted(self, message: Message) -> None:
        if message.moderation is not None:
            text = get_moderation_text(message.moderation.by, message.moderation.reason)

        elif message.retraction is not None:
            text = get_retraction_text(message.retraction.timestamp)

        else:
            raise ValueError("Unable to determine retraction text")

        self._set_disabled(text)
        self._is_retracted = True

    def _set_blocked(self) -> None:
        self._set_disabled(_("Messages from this users are blocked"))
        self._is_blocked = True

    def _set_disabled(self, text: str) -> None:
        self.text = text

        self._message_widget = MessageWidget(self._account)
        self._message_widget.add_with_styling(text)
        self._set_text_direction(text)
        self._bottom_box.append(self._message_widget)

        self._reactions_bar.set_visible(False)

        self.add_css_class("retracted-message")

    def _set_correction(self) -> None:
        original_text = textwrap.fill(
            self._original_text, width=150, max_lines=10, placeholder="…"
        )
        self._message_icons.set_correction_tooltip(
            _("Message corrected. Original message:\n%s") % original_text
        )
        self._message_icons.set_correction_icon_visible(True)

    def update_avatar(self) -> None:
        avatar = get_avatar_for_message(
            self._original_message,
            self._contact,
            self.get_scale_factor(),
            AvatarSize.ROSTER,
        )
        self._avatar_box.set_from_paintable(avatar)

    def set_merged(self, merged: bool) -> None:
        self._merged = merged
        if merged:
            self.add_css_class("merged")
            self._meta_box.set_visible(False)
            self._meta_box.set_visible(False)
        else:
            self.remove_css_class("merged")
            self._meta_box.set_visible(True)

        self._avatar_box.set_merged(merged)

    def can_reply(self) -> bool:
        if self._is_retracted:
            return False

        if isinstance(self._contact, GroupchatContact):
            if self._message.stanza_id is None:
                return False

            if not self._contact.is_joined:
                return False

            self_contact = self._contact.get_self()
            assert self_contact is not None
            return not self_contact.role.is_visitor

        return self._original_message.id is not None

    def can_react(self) -> bool:
        if self._is_retracted:
            return False

        if not app.account_is_connected(self._contact.account):
            return False

        if isinstance(self._contact, GroupchatContact):
            if not self._contact.is_joined:
                return False

            self_contact = self._contact.get_self()
            assert self_contact is not None
            if self_contact.role.is_visitor:
                return False

            if self._message.stanza_id is None:
                return False

            if self._contact.muc_context == "public":
                return self._contact.supports(Namespace.OCCUPANT_ID)

            return True

        return self._original_message.id is not None
