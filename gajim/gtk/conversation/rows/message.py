# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import textwrap
from datetime import timedelta

import cairo
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Trust
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.helpers import get_retraction_text
from gajim.common.helpers import message_needs_highlight
from gajim.common.i18n import _
from gajim.common.i18n import is_rtl_text
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.modules.message_util import get_nickname_from_message
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.types import ChatContactT

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
from gajim.gtk.referenced_message import ReferencedMessageWidget
from gajim.gtk.util import format_fingerprint
from gajim.gtk.util import GajimPopover

MERGE_TIMEFRAME = timedelta(seconds=120)


class MessageRow(BaseRow):
    def __init__(self,
                 contact: ChatContactT,
                 message: Message
                 ) -> None:

        BaseRow.__init__(self, contact.account)
        self.set_selectable(True)
        self.type = 'chat'
        self._contact = contact

        self.timestamp = message.timestamp.astimezone()
        self.db_timestamp = message.timestamp.timestamp()
        self.stanza_id = message.stanza_id
        self.direction = ChatDirection(message.direction)
        self._is_outgoing = self.direction == ChatDirection.OUTGOING

        self.orig_pk = message.pk

        assert message.text is not None
        self._original_text = message.text
        self._original_message = message

        self._is_retracted = message.moderation is not None
        self._has_receipt = False

        self._avatar_box = AvatarBox(contact)

        self._ref_message_widget = None

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.set_hexpand(True)

        self._bottom_box = Gtk.Box(spacing=6)

        self.grid.attach(self._avatar_box, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(self._bottom_box, 1, 1, 1, 1)

        self._set_content(message)

    @classmethod
    def from_db_row(cls,
        contact: ChatContactT,
        message: Message
    ) -> MessageRow:

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

    def refresh(self) -> None:
        original_message = app.storage.archive.get_message_with_pk(
            self.orig_pk)
        assert original_message is not None
        self._original_message = original_message
        self._set_content(original_message)

    def _set_content(self, message: Message) -> None:
        self.set_merged(False)
        self.get_style_context().remove_class('retracted-message')
        self.get_style_context().remove_class('gajim-mention-highlight')

        for widget in self._meta_box.get_children():
            widget.destroy()

        for widget in self._bottom_box.get_children():
            widget.destroy()

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

        self.name = self._get_contact_name(message, self._contact)

        avatar = self._get_avatar(self.direction, self.name)
        self._avatar_box.set_from_surface(avatar)
        self._avatar_box.set_name(self.name)

        self._meta_box.pack_start(
            NicknameLabel(
                self.name,
                self._is_outgoing
            ), False, True, 0)
        self._meta_box.pack_start(
            DateTimeLabel(self.timestamp), False, True, 0)

        self._message_icons = MessageIcons()
        self._meta_box.pack_start(self._message_icons, False, True, 0)

        if app.preview_manager.is_previewable(self.text, message.oob):
            self._message_widget = PreviewWidget(self._contact.account)
            app.preview_manager.create_preview(
                self.text,
                self._message_widget,
                self._is_outgoing,
                self._muc_context)
        else:
            referenced_message = message.get_referenced_message()
            if referenced_message is not None:
                self._ref_message_widget = ReferencedMessageWidget(
                    self._contact, referenced_message)

            self._message_widget = MessageWidget(self._contact.account)
            self._message_widget.add_with_styling(self.text, nickname=self.name)
            if self._contact.is_groupchat and not self._is_outgoing:
                self._apply_highlight(self.text)

        if self._ref_message_widget is not None:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.add(self._ref_message_widget)
            box.add(self._message_widget)
            self._bottom_box.add(box)
        else:
            self._bottom_box.add(self._message_widget)

        self._set_text_direction(self.text)

        if self._original_message.corrections:
            self._set_correction()

        if message.moderation is not None:
            self.set_retracted(get_retraction_text(
                message.moderation.by, message.moderation.reason))

        # Reactions
        reaction_id = message.id
        if isinstance(self._contact, GroupchatContact):
            reaction_id = message.stanza_id

        self._reactions_bar = ReactionsBar(self._contact, reaction_id)
        self.grid.attach(self._reactions_bar, 1, 2, 1, 1)
        if message.reactions:
            self._reactions_bar.update_from_reactions(message.reactions)

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

        if (self._contact.is_groupchat and
                self.direction == ChatDirection.OUTGOING):
            self._message_icons.set_message_state_icon(self.state)

        if message.error is not None:
            if message.error.text is not None:
                error_text = f'{message.error.text} ({message.error.condition})'
            else:
                error_text = message.error.condition
            self.show_error(error_text)

        self.show_all()

    def _set_text_direction(self, text: str) -> None:
        if is_rtl_text(text):
            self._bottom_box.set_halign(Gtk.Align.END)
            self._message_widget.set_direction(Gtk.TextDirection.RTL)
        else:
            self._bottom_box.set_halign(Gtk.Align.FILL)
            self._message_widget.set_direction(Gtk.TextDirection.LTR)

    @staticmethod
    def _get_contact_name(
        db_row: Message,
        contact: ChatContactT
    ) -> str:

        if isinstance(contact, BareContact) and contact.is_self:
            return _('Me')

        if db_row.type == MessageType.CHAT:
            if db_row.direction == ChatDirection.INCOMING:
                return contact.name
            return app.nicks[contact.account]

        if db_row.type in (MessageType.GROUPCHAT, MessageType.PM):
            return get_nickname_from_message(db_row)

        raise ValueError

    @property
    def _muc_context(self) -> str | None:
        if isinstance(self._contact,
                      GroupchatContact | GroupchatParticipant):
            return self._contact.muc_context
        return None

    def show_chat_row_menu(
        self,
        message_row_actions: MessageRowActions,
        button: Gtk.Button
    ) -> None:
        menu = get_chat_row_menu(
            contact=self._contact,
            name=self.name,
            text=self.get_text(),
            timestamp=self.timestamp,
            message_id=self._original_message.id,
            stanza_id=self.stanza_id,
            pk=self.orig_pk,
            corrected_pk=self.pk,
            state=self.state,
            is_retracted=self._is_retracted,
        )

        popover = GajimPopover(menu, relative_to=button)
        popover.connect(
            'closed',
            self._on_more_menu_popover_closed,
            message_row_actions
        )
        popover.popup()

    def _on_more_menu_popover_closed(
        self,
        _popover: GajimPopover,
        message_row_actions: MessageRowActions
    ) -> None:
        message_row_actions.hide_actions()

    def enable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(False)

    def disable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(True)

    def _get_security_labels_data(
            self,
            security_labels: mod.SecurityLabel | None
            ) -> tuple[str, str] | None:

        if security_labels is None:
            return None

        if not app.settings.get_account_setting(self._account,
                                                'enable_security_labels'):
            return None

        displaymarking = GLib.markup_escape_text(security_labels.displaymarking)
        if displaymarking:
            bgcolor = security_labels.bgcolor
            fgcolor = security_labels.fgcolor
            markup = (
                f'<span size="small" bgcolor="{bgcolor}" '
                f'fgcolor="{fgcolor}"><tt>{displaymarking}</tt></span>')
            return displaymarking, markup
        return None

    def _apply_highlight(self, text: str) -> None:
        assert isinstance(self._contact, GroupchatContact)
        if self._contact.nickname is None:
            return

        if message_needs_highlight(
                text, self._contact.nickname, self._client.get_own_jid().bare):
            self.get_style_context().add_class(
                'gajim-mention-highlight')

    def _get_avatar(self,
                    direction: ChatDirection,
                    name: str
                    ) -> cairo.ImageSurface | None:

        scale = self.get_scale_factor()
        if isinstance(self._contact, GroupchatContact):
            contact = self._contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if direction == ChatDirection.OUTGOING:
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self._contact

        assert not isinstance(contact, GroupchatContact | ResourceContact)
        avatar = contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
        return avatar

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
        if message.securitylabel == self.securitylabel:
            return True
        if (message.securitylabel is not None and
                self.securitylabel is not None):
            if (message.securitylabel.displaymarking ==
                    self.securitylabel.displaymarking):
                return True
        return False

    def is_same_state(self, message: MessageRow) -> bool:
        return message.state == self.state

    def has_same_receipt_status(self, message: MessageRow) -> bool:
        if not app.settings.get('positive_184_ack'):
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

    def _get_encryption_data(self,
                             encryption_data: mod.Encryption | None,
                             ) -> tuple[str, str, str] | None:

        contact_encryption = self._contact.settings.get('encryption')
        if encryption_data is None:
            if not contact_encryption:
                return None

            icon = 'channel-insecure-symbolic'
            color = 'unencrypted-color'
            tooltip = _('Not encrypted')
        else:
            tooltip = _('Encrypted (%s)') % (encryption_data.protocol)
            icon, trust_tooltip, color = TRUST_SYMBOL_DATA[
                Trust(encryption_data.trust)]
            tooltip = f'{tooltip}\n{trust_tooltip}'
            if encryption_data.key != 'Unknown':
                fingerprint = format_fingerprint(encryption_data.key)
                tooltip = f'{tooltip}\n<tt>{fingerprint}</tt>'

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

    def show_reactions(self) -> None:
        self._reactions_bar.update_from_reactions(self._original_message.reactions)

    def set_retracted(self, text: str) -> None:
        self.text = text

        if isinstance(self._message_widget, PreviewWidget):
            self._message_widget.destroy()
            self._message_widget = MessageWidget(self._account)
            self._bottom_box.pack_start(self._message_widget, True, True, 0)
            self._set_text_direction(text)

        self._message_widget.add_with_styling(text)
        self.get_style_context().add_class('retracted-message')

        self._is_retracted = True

    def _set_correction(self) -> None:
        original_text = textwrap.fill(self._original_text,
                                      width=150,
                                      max_lines=10,
                                      placeholder='…')
        self._message_icons.set_correction_tooltip(
            _('Message corrected. Original message:\n%s') % original_text)
        self._message_icons.set_correction_icon_visible(True)

    def update_avatar(self) -> None:
        avatar = self._get_avatar(self.direction, self.name)
        self._avatar_box.set_from_surface(avatar)

    def set_merged(self, merged: bool) -> None:
        self._merged = merged
        if merged:
            self.get_style_context().add_class('merged')
            self._meta_box.set_no_show_all(True)
            self._meta_box.hide()
        else:
            self.get_style_context().remove_class('merged')
            self._meta_box.set_no_show_all(False)
            self._meta_box.show()

        self._avatar_box.set_merged(merged)
