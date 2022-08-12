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

from gi.repository import Gdk
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
from gajim.common.helpers import from_one_line
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_muc_context
from gajim.common.helpers import message_needs_highlight
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

from .base import BaseRow
from .widgets import MoreMenuButton
from ..message_widget import MessageWidget
from ...dialogs import InputDialog
from ...dialogs import DialogButton
from ...preview import PreviewWidget
from ...util import format_fingerprint
from ...util import get_cursor

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
            context = None
            if self._is_groupchat:
                context = get_muc_context(self._contact.jid)
            self._message_widget = PreviewWidget(account)
            app.preview_manager.create_preview(
                text, self._message_widget, from_us, context)
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

        name_widget = self.create_name_widget(name, from_us)

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.set_hexpand(True)
        self._meta_box.pack_start(name_widget, False, True, 0)
        timestamp_label = self.create_timestamp_widget(self.timestamp)
        self._meta_box.pack_start(timestamp_label, False, True, 0)

        if kind in ('incoming', 'incoming_queue', 'outgoing'):
            if additional_data is not None:
                encryption_img = self._get_encryption_image(additional_data)
                if encryption_img:
                    self._meta_box.pack_start(encryption_img, False, True, 0)

        if display_marking and app.settings.get_account_setting(
                account, 'enable_security_labels'):
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
        self._avatar_image = Gtk.Image.new_from_surface(avatar)

        if self._is_groupchat:
            avatar_placeholder = Gtk.EventBox()
            avatar_placeholder.connect(
                'button-press-event', self._on_avatar_clicked, name)
            avatar_placeholder.connect('realize', self._on_realize)
        else:
            avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        avatar_placeholder.set_valign(Gtk.Align.START)
        avatar_placeholder.add(self._avatar_image)

        self._bottom_box = Gtk.Box(spacing=6)
        self._bottom_box.add(self._message_widget)

        more_menu_button = MoreMenuButton(self, self._contact, name)
        more_menu_button.set_hexpand(True)
        more_menu_button.set_halign(Gtk.Align.END)
        self._bottom_box.pack_end(more_menu_button, False, True, 0)

        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(self._bottom_box, 1, 1, 1, 1)

        self.show_all()

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

    def _on_avatar_clicked(self,
                           _widget: Gtk.Widget,
                           event: Gdk.EventButton,
                           name: str
                           ) -> int:
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            app.window.activate_action('mention', GLib.Variant('s', name))
        return Gdk.EVENT_STOP

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        if window is not None:
            window.set_cursor(get_cursor('pointer'))

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

    def on_copy_message(self, _widget: Gtk.Widget) -> None:
        time_format = from_one_line(app.settings.get('chat_timestamp_format'))
        timestamp_formatted = self.timestamp.strftime(time_format)

        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = self._message_widget.get_text()
        clip.set_text(f'{timestamp_formatted} - {self.name}: {text}', -1)

    def on_quote_message(self, _widget: Gtk.Widget) -> None:
        app.window.activate_action(
            'quote', GLib.Variant('s', self._message_widget.get_text()))

    def on_correct_message(self, _widget: Gtk.Widget) -> None:
        app.window.activate_action('correct-message', None)

    def on_retract_message(self, _widget: Gtk.Widget) -> None:
        def _on_retract(reason: str) -> None:
            self._client.get_module('MUC').retract_message(
                self._contact.jid, self.stanza_id, reason or None)

        InputDialog(
            _('Retract Message'),
            _('Retract message?'),
            _('Why do you want to retract this message?'),
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               text=_('_Retract'),
                               callback=_on_retract)],
            input_str=_('Spam'),
            transient_for=app.window).show()

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
        self._message_widget.add_with_styling(text)
        self.get_style_context().add_class('retracted-message')

    def set_correction(self, text: str, nickname: Optional[str]) -> None:
        if not isinstance(self._message_widget, PreviewWidget):
            self._message_widget.add_with_styling(text, nickname)

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
        self._avatar_image.set_from_surface(avatar)

    def set_merged(self, merged: bool) -> None:
        self._merged = merged
        if merged:
            self.get_style_context().add_class('merged')
            self._avatar_image.set_no_show_all(True)
            self._avatar_image.hide()
            self._meta_box.set_no_show_all(True)
            self._meta_box.hide()
        else:
            self.get_style_context().remove_class('merged')
            self._avatar_image.set_no_show_all(False)
            self._avatar_image.show()
            self._meta_box.set_no_show_all(False)
            self._meta_box.show()


class MessageIcons(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU)
        self._correction_image.set_no_show_all(True)
        self._correction_image.get_style_context().add_class('dim-label')

        self._marker_image = Gtk.Image()
        self._marker_image.set_no_show_all(True)
        self._marker_image.get_style_context().add_class('dim-label')

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._correction_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_receipt_icon_visible(self, visible: bool) -> None:
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)
        self._marker_image.set_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_tooltip_text(Q_('?Message state:Received'))

    def set_correction_icon_visible(self, visible: bool) -> None:
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text: str) -> None:
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible: bool) -> None:
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text: str) -> None:
        self._error_image.set_tooltip_markup(text)
