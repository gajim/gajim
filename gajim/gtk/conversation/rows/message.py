# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Optional
from typing import Union

from datetime import datetime
from datetime import timedelta
import textwrap

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

import cairo

from nbxmpp.errors import StanzaError
from nbxmpp.modules.security_labels import Displaymarking
from nbxmpp.structs import CommonError

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Trust
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import message_needs_highlight
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.i18n import is_rtl_text
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.types import ChatContactT

from .base import BaseRow
from .widgets import AvatarBox
from .widgets import DateTimeLabel
from .widgets import NicknameLabel
from .widgets import MessageIcons
from .widgets import MoreMenuButton
from ..message_widget import MessageWidget
from ...preview import PreviewWidget
from ...util import format_fingerprint


MERGE_TIMEFRAME = timedelta(seconds=120)


class MessageRow(BaseRow):
    def __init__(self,
                 account: str,
                 contact: ChatContactT,
                 message_id: Optional[str],
                 stanza_id: Optional[str],
                 timestamp: float,
                 kind: str,
                 name: str,
                 text: str,
                 additional_data: Optional[AdditionalDataDict] = None,
                 display_marking: Optional[Displaymarking] = None,
                 marker: Optional[str] = None,
                 error: Union[CommonError, StanzaError, None] = None,
                 log_line_id: Optional[int] = None) -> None:

        BaseRow.__init__(self, account)
        self.type = 'chat'
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp
        self.message_id = message_id
        self.stanza_id = stanza_id
        self.log_line_id = log_line_id
        self.kind = kind
        self.name = name
        self.text = text
        self.additional_data = additional_data
        self.display_marking = display_marking

        self.set_selectable(True)

        self._account = account
        self._contact = contact

        self._is_groupchat: bool = False
        if contact is not None and contact.is_groupchat:
            self._is_groupchat = True

        self._has_receipt: bool = marker == 'received'
        self._has_displayed: bool = marker == 'displayed'

        # Keep original text for message correction
        self._original_text: str = text

        if self._is_groupchat:
            our_nick = get_group_chat_nick(self._account, self._contact.jid)
            from_us = name == our_nick
        else:
            from_us = kind == 'outgoing'

        is_previewable = False
        preview_enabled = app.settings.get('enable_file_preview')
        if additional_data is not None and preview_enabled:
            is_previewable = app.preview_manager.is_previewable(
                text, additional_data)

        if is_previewable:
            muc_context = None
            if isinstance(self._contact,
                          (GroupchatContact, GroupchatParticipant)):
                muc_context = self._contact.muc_context
            self._message_widget = PreviewWidget(account)
            app.preview_manager.create_preview(
                text, self._message_widget, from_us, muc_context)
        else:
            self._message_widget = MessageWidget(account)
            self._message_widget.add_with_styling(text, nickname=name)
            if self._is_groupchat:
                our_nick = get_group_chat_nick(
                    self._account, self._contact.jid)
                if name != our_nick:
                    self._check_for_highlight(text)

        if self._contact.jid == self._client.get_own_jid().bare:
            name = _('Me')

        name_widget = NicknameLabel(name, from_us)

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.set_hexpand(True)
        self._meta_box.pack_start(name_widget, False, True, 0)
        timestamp_label = DateTimeLabel(self.timestamp)
        self._meta_box.pack_start(timestamp_label, False, True, 0)

        if additional_data is not None:
            encryption_img = self._get_encryption_image(additional_data)
            if encryption_img:
                self._meta_box.pack_start(encryption_img, False, True, 0)

        self._add_security_label(display_marking)

        self._message_icons = MessageIcons()

        if additional_data is not None:
            if additional_data.get_value('retracted', 'by') is not None:
                self.get_style_context().add_class('retracted-message')

            correction_original = additional_data.get_value(
                'corrected', 'original_text')
            if correction_original is not None:
                self._original_text = correction_original
                self._message_icons.set_correction_icon_visible(True)
                original_text = textwrap.fill(correction_original,
                                              width=150,
                                              max_lines=10,
                                              placeholder='…')
                self._message_icons.set_correction_tooltip(
                    _('Message corrected. Original message:'
                      '\n%s') % original_text)

        if error is not None:
            self.set_error(to_user_string(error))

        if marker is not None:
            if marker in ('received', 'displayed'):
                self.set_receipt()

        self._meta_box.pack_start(self._message_icons, False, True, 0)

        avatar = self._get_avatar(kind, name)
        self._avatar_box = AvatarBox(self._contact, name, avatar)

        self._bottom_box = Gtk.Box(spacing=6)
        self._bottom_box.add(self._message_widget)

        if is_rtl_text(text):
            self._bottom_box.set_halign(Gtk.Align.END)
            self._message_widget.set_direction(Gtk.TextDirection.RTL)

        more_menu_button = MoreMenuButton(self, self._contact, name)
        self._bottom_box.pack_end(more_menu_button, False, True, 0)

        self.grid.attach(self._avatar_box, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(self._bottom_box, 1, 1, 1, 1)

        self.show_all()

    def enable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(False)

    def disable_selection_mode(self) -> None:
        if isinstance(self._message_widget, MessageWidget):
            self._message_widget.set_selectable(True)

    def _add_security_label(self,
                            display_marking: Optional[Displaymarking]
                            ) -> None:

        if display_marking is None:
            return

        if not app.settings.get_account_setting(self._account,
                                                'enable_security_labels'):
            return

        label_text = GLib.markup_escape_text(display_marking.name)
        if label_text:
            display_marking_label = Gtk.Label()
            display_marking_label.set_ellipsize(Pango.EllipsizeMode.END)
            display_marking_label.set_max_width_chars(30)
            display_marking_label.set_tooltip_text(label_text)
            bgcolor = display_marking.bgcolor
            fgcolor = display_marking.fgcolor
            label_text = (
                f'<span size="small" bgcolor="{bgcolor}" '
                f'fgcolor="{fgcolor}"><tt>{label_text}</tt></span>')
            display_marking_label.set_markup(label_text)
            self._meta_box.add(display_marking_label)

    def _check_for_highlight(self, text: str) -> None:
        assert isinstance(self._contact, GroupchatContact)
        if self._contact.nickname is None:
            return

        needs_highlight = message_needs_highlight(
            text,
            self._contact.nickname,
            self._client.get_own_jid().bare)
        if needs_highlight:
            self.get_style_context().add_class(
                'gajim-mention-highlight')

    def _get_avatar(self, kind: str, name: str) -> Optional[cairo.ImageSurface]:
        if self._contact is None:
            return None

        scale = self.get_scale_factor()
        if isinstance(self._contact, GroupchatContact):
            contact = self._contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self._contact

        avatar = contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
        assert not isinstance(avatar, GdkPixbuf.Pixbuf)
        return avatar

    def is_same_sender(self, message: MessageRow) -> bool:
        return message.name == self.name

    def is_same_encryption(self, message: MessageRow) -> bool:
        m_add_data = message.additional_data
        if m_add_data is None:
            m_add_data = AdditionalDataDict()
        s_add_data = self.additional_data
        if s_add_data is None:
            s_add_data = AdditionalDataDict()

        message_details = self._get_encryption_details(m_add_data)
        own_details = self._get_encryption_details(s_add_data)
        if message_details is None and own_details is None:
            return True

        if message_details is not None and own_details is not None:
            # *_details contains encryption method's name, fingerprint, trust
            m_name, _, m_trust = message_details
            o_name, _, o_trust = own_details
            if m_name == o_name and m_trust == o_trust:
                return True
        return False

    def is_same_display_marking(self, message: MessageRow) -> bool:
        if message.display_marking == self.display_marking:
            return True
        if (message.display_marking is not None and
                self.display_marking is not None):
            if message.display_marking.name == self.display_marking.name:
                return True
        return False

    def is_mergeable(self, message: MessageRow) -> bool:
        if message.type != self.type:
            return False
        if not self.is_same_sender(message):
            return False
        if not self.is_same_encryption(message):
            return False
        if not self.is_same_display_marking(message):
            return False
        return abs(message.timestamp - self.timestamp) < MERGE_TIMEFRAME

    def get_text(self) -> str:
        return self._message_widget.get_text()

    def _get_encryption_image(self,
                              additional_data: AdditionalDataDict,
                              ) -> Optional[Gtk.Image]:

        details = self._get_encryption_details(additional_data)
        if details is None:
            # Message was not encrypted
            if not self._contact.settings.get('encryption'):
                return None
            icon = 'channel-insecure-symbolic'
            color = 'unencrypted-color'
            tooltip = _('Not encrypted')
        else:
            name, fingerprint, trust = details
            tooltip = _('Encrypted (%s)') % (name)
            if trust is None:
                # The encryption plugin did not pass trust information
                icon = 'channel-secure-symbolic'
                color = 'encrypted-color'
            else:
                icon, trust_tooltip, color = TRUST_SYMBOL_DATA[Trust(trust)]
                tooltip = f'{tooltip}\n{trust_tooltip}'
            if fingerprint is not None:
                fingerprint = format_fingerprint(fingerprint)
                tooltip = f'{tooltip}\n<tt>{fingerprint}</tt>'

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_tooltip_markup(tooltip)
        image.get_style_context().add_class(color)
        image.show()
        return image

    @staticmethod
    def _get_encryption_details(additional_data: AdditionalDataDict
                                ) -> Optional[tuple[
                                    str, Optional[str], Optional[Trust]]]:
        name = additional_data.get_value('encrypted', 'name')
        if name is None:
            return None

        fingerprint = additional_data.get_value('encrypted', 'fingerprint')
        trust_data = additional_data.get_value('encrypted', 'trust')

        if trust_data is not None:
            trust_data = Trust(trust_data)
        return name, fingerprint, trust_data

    @property
    def has_receipt(self) -> bool:
        return self._has_receipt

    @property
    def has_displayed(self) -> bool:
        return self._has_displayed

    def set_receipt(self) -> None:
        self._has_receipt = True
        self._message_icons.set_receipt_icon_visible(True)

    def set_displayed(self) -> None:
        self._has_displayed = True

    def set_retracted(self, text: str) -> None:
        if isinstance(self._message_widget, PreviewWidget):
            self._message_widget.destroy()
            self._message_widget = MessageWidget(self._account)
            self._bottom_box.pack_start(self._message_widget, True, True, 0)
            if is_rtl_text(text):
                self._bottom_box.set_halign(Gtk.Align.END)
                self._message_widget.set_direction(Gtk.TextDirection.RTL)
            else:
                self._bottom_box.set_halign(Gtk.Align.FILL)
                self._message_widget.set_direction(Gtk.TextDirection.LTR)

        self._message_widget.add_with_styling(text)
        self.get_style_context().add_class('retracted-message')

    def set_correction(self, text: str, nickname: Optional[str]) -> None:
        if not isinstance(self._message_widget, PreviewWidget):
            self._message_widget.add_with_styling(text, nickname)

            if is_rtl_text(text):
                self._bottom_box.set_halign(Gtk.Align.END)
                self._message_widget.set_direction(Gtk.TextDirection.RTL)
            else:
                self._bottom_box.set_halign(Gtk.Align.FILL)
                self._message_widget.set_direction(Gtk.TextDirection.LTR)

        self._has_receipt = False
        self._message_icons.set_receipt_icon_visible(False)
        self._message_icons.set_correction_icon_visible(True)

        original_text = textwrap.fill(self._original_text,
                                      width=150,
                                      max_lines=10,
                                      placeholder='…')
        self._message_icons.set_correction_tooltip(
            _('Message corrected. Original message:\n%s') % original_text)

    def set_error(self, tooltip: str) -> None:
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)

    def update_avatar(self) -> None:
        avatar = self._get_avatar(self.kind, self.name)
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
