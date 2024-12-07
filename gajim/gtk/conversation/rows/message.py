# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import textwrap
from datetime import timedelta

from gi.repository import GLib
from gi.repository import Gtk

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
from gajim.common.util.user_strings import get_moderation_text

from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.conversation.reactions_bar import ReactionsBar
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import AvatarBox
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import MessageIcons
from gajim.gtk.conversation.rows.widgets import MessageRowActions
from gajim.gtk.conversation.rows.widgets import NicknameLabel
from gajim.gtk.menus import get_chat_row_menu
from gajim.gtk.preview import PreviewWidget
from gajim.gtk.referenced_message import ReferencedMessageNotFoundWidget
from gajim.gtk.referenced_message import ReferencedMessageWidget
from gajim.gtk.util import container_remove_all
from gajim.gtk.util import format_fingerprint
from gajim.gtk.util import GajimMenu
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import get_avatar_for_message
from gajim.gtk.util import get_contact_name_for_message

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
        self.stanza_id = message.stanza_id
        self.direction = ChatDirection(message.direction)
        self._is_outgoing = self.direction == ChatDirection.OUTGOING

        self.orig_pk = message.pk

        assert message.text is not None
        self._original_text = message.text
        self._original_message = message

        self._is_moderated = message.moderation is not None
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

        self._set_content(message)

    @classmethod
    def from_db_row(cls, contact: ChatContactT, message: Message) -> MessageRow:

        return cls(contact, message)

    @property
    def last_message_id(self) -> str | None:
        if self._corr_message is None:
            return self._original_message.id
        return self._corr_message.id

    @property
    def message_id(self) -> str | None:
        return self._original_message.id

    @property
    def has_receipt(self) -> bool:
        return self._has_receipt

    @property
    def is_merged(self) -> bool:
        return self._merged

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)

    def refresh(self, *, complete: bool = True) -> None:
        original_message = app.storage.archive.get_message_with_pk(self.orig_pk)
        assert original_message is not None
        self._original_message = original_message
        if complete:
            self._set_content(original_message)

    def _set_content(self, message: Message) -> None:
        self.set_merged(False)
        self.remove_css_class("moderated-message")
        self.remove_css_class("gajim-mention-highlight")

        container_remove_all(self._meta_box)
        container_remove_all(self._bottom_box)

        self._corr_message = None

        # From here on, if this is a correction all data must
        # be taken from the correction
        if message.corrections:
            message = message.get_last_correction()
            self._corr_message = message

        self.pk = message.pk

        self.encryption = message.encryption
        self.securitylabel = message.security_label

        assert message.text is not None
        self.text = message.text

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

        if app.preview_manager.is_previewable(self.text, message.oob):
            self._message_widget = PreviewWidget(self._contact.account)
            app.preview_manager.create_preview(
                self.text, self._message_widget, self._is_outgoing, self._muc_context
            )
        else:
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

        if self._ref_message_widget is not None:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.append(self._ref_message_widget)
            box.append(self._message_widget)
            self._bottom_box.append(box)
        else:
            self._bottom_box.append(self._message_widget)

        self._set_text_direction(self.text)

        if self._original_message.corrections:
            self._set_correction()

        if message.moderation is not None:
            self.set_moderated(
                get_moderation_text(message.moderation.by, message.moderation.reason)
            )

        reactions = self._original_message.reactions
        if reactions:
            self._reactions_bar.update_from_reactions(reactions)

        encryption_data = self._get_encryption_data(message.encryption)
        if encryption_data is not None:
            self._message_icons.set_encrytion_icon_data(*encryption_data)
            self._message_icons.set_encryption_icon_visible(True)

        sec_label_data = self._get_security_labels_data(message.security_label)
        if sec_label_data is not None:
            self._message_icons.set_security_label_data(*sec_label_data)
            self._message_icons.set_security_label_visible(True)

        self.set_receipt(message.receipt is not None)

        self.state = MessageState(message.state)

        if self._contact.is_groupchat and self.direction == ChatDirection.OUTGOING:
            self._message_icons.set_message_state_icon(self.state)

        if message.error is not None:
            if message.error.text is not None:
                error_text = f"{message.error.text} ({message.error.condition})"
            else:
                error_text = message.error.condition
            self.show_error(error_text)

    def _set_text_direction(self, text: str) -> None:
        if is_rtl_text(text):
            self._bottom_box.set_halign(Gtk.Align.END)
            self._message_widget.set_direction(Gtk.TextDirection.RTL)
        else:
            self._bottom_box.set_halign(Gtk.Align.FILL)
            self._message_widget.set_direction(Gtk.TextDirection.LTR)

    @property
    def _muc_context(self) -> str | None:
        if isinstance(self._contact, GroupchatContact | GroupchatParticipant):
            return self._contact.muc_context
        return None

    def get_chat_row_menu(
        self,
    ) -> GajimMenu:
        occupant_id = None
        if self._message.occupant is not None:
            occupant_id = self._message.occupant.id

        return get_chat_row_menu(
            contact=self._contact,
            name=self.name,
            text=self.get_text(),
            timestamp=self.timestamp,
            message_id=self._original_message.id,
            stanza_id=self.stanza_id,
            pk=self.orig_pk,
            corrected_pk=self.pk,
            state=self.state,
            is_moderated=self._is_moderated,
            occupant_id=occupant_id,
        )

    def _on_more_menu_popover_closed(
        self, _popover: GajimPopover, message_row_actions: MessageRowActions
    ) -> None:
        message_row_actions.hide_actions()

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
        return message.state == self.state

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
        if self._original_message.corrections:
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

    def set_acknowledged(self, stanza_id: str | None) -> None:
        self.state = MessageState.ACKNOWLEDGED
        self.stanza_id = stanza_id
        self._message_icons.set_message_state_icon(self.state)

    def set_receipt(self, value: bool) -> None:
        self._has_receipt = value
        self._message_icons.set_receipt_icon_visible(value)

    def show_error(self, tooltip: str) -> None:
        self._message_icons.hide_message_state_icon()
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)

    def update_reactions(self) -> None:
        self.refresh(complete=False)
        self._reactions_bar.update_from_reactions(self._original_message.reactions)

    def send_reaction(self, emoji: str, toggle: bool = True) -> None:
        """Adds or removes 'emoji' from this message's reactions and sends the result.

        Args:
          emoji: Reaction emoji to add or remove
          toggle: Whether an existing emoji should be removed from the set
        """
        reaction_id = self.message_id
        if self._original_message.type == MessageType.GROUPCHAT:
            reaction_id = self.stanza_id

        if reaction_id is None:
            log.warning("No reaction id")
            return

        our_reactions = self._reactions_bar.get_our_reactions()
        if emoji in our_reactions and not toggle:
            log.info("Not toggling reaction <%s>", emoji)
            return

        if emoji in our_reactions:
            our_reactions.discard(emoji)
        else:
            our_reactions.add(emoji)

        client = app.get_client(self._contact.account)
        client.get_module("Reactions").send_reaction(
            contact=self._contact, reaction_id=reaction_id, reactions=our_reactions
        )

    def set_moderated(self, text: str) -> None:
        self.text = text

        if isinstance(self._message_widget, PreviewWidget):
            self._bottom_box.remove(self._message_widget)

            self._message_widget = MessageWidget(self._account)
            self._bottom_box.append(self._message_widget)
            self._set_text_direction(text)

        self._message_widget.add_with_styling(text)
        self.add_css_class("moderated-message")

        self._is_moderated = True

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
            self._message, self._contact, self.get_scale_factor(), AvatarSize.ROSTER
        )
        self._avatar_box.set_from_paintable(avatar)

    def set_merged(self, merged: bool) -> None:
        self._merged = merged
        if merged:
            self.add_css_class("merged")
            self._meta_box.set_visible(False)
            self._meta_box.hide()
        else:
            self.remove_css_class("merged")
            self._meta_box.show()

        self._avatar_box.set_merged(merged)
