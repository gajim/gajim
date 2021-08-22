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

from datetime import datetime
from datetime import timedelta

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_muc_context
from gajim.common.helpers import message_needs_highlight
from gajim.common.helpers import reduce_chars_newlines
from gajim.common.helpers import to_user_string
from gajim.common.styling import process
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from .base import BaseRow
from .base import MoreMenuButton
from ..message_widget import MessageWidget
from ...preview import PreviewWidget
from ...util import format_fingerprint

MERGE_TIMEFRAME = timedelta(seconds=120)


class MessageRow(BaseRow):
    def __init__(self,
                 account,
                 contact,
                 message_id,
                 timestamp,
                 kind,
                 name,
                 text,
                 additional_data=None,
                 display_marking=None,
                 marker=None,
                 error=None,
                 encryption_enabled=False,
                 log_line_id=None):

        BaseRow.__init__(self, account)
        self.type = 'chat'
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp
        self.message_id = message_id
        self.log_line_id = log_line_id
        self.kind = kind
        self.name = name or ''
        self.text = text

        self._contact = contact
        self._is_groupchat = False
        if contact is not None and contact.is_groupchat:
            self._is_groupchat = True

        self._corrections = []
        self._has_receipt = marker == 'received'
        self._has_displayed = marker == 'displayed'

        is_previewable = app.interface.preview_manager.get_previewable(
            text, additional_data)
        if is_previewable:
            context = None
            if self._is_groupchat:
                context = get_muc_context(self._contact.jid)
            self._message_widget = PreviewWidget(account)
            app.interface.preview_manager.create_preview(
                text, self._message_widget, context)
        else:
            result = process(text)
            self._message_widget = MessageWidget(account)
            self._message_widget.add_content(result)
            if self._is_groupchat:
                our_nick = get_group_chat_nick(
                    self._account, self._contact.jid)
                if name != our_nick:
                    self._check_for_highlight(result)

        if self._is_groupchat:
            our_nick = get_group_chat_nick(self._account, self._contact.jid)
            is_self = name == our_nick
        else:
            is_self = kind == 'outgoing'
        name_widget = self.create_name_widget(name, is_self)

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.set_hexpand(True)
        self._meta_box.pack_start(name_widget, False, True, 0)
        timestamp_label = self.create_timestamp_widget(self.timestamp)
        timestamp_label.set_margin_start(6)
        self._meta_box.pack_end(timestamp_label, False, True, 0)

        if kind in ('incoming', 'incoming_queue', 'outgoing'):
            encryption_img = self._get_encryption_image(
                additional_data, encryption_enabled)
            if encryption_img:
                self._meta_box.pack_end(encryption_img, False, True, 0)

        if display_marking:
            label_text = GLib.markup_escape_text(display_marking.name)
            if label_text:
                bgcolor = display_marking.bgcolor
                fgcolor = display_marking.fgcolor
                label_text = (
                    f'<span size="small" bgcolor="{bgcolor}" '
                    f'fgcolor="{fgcolor}"><tt>[{label_text}]</tt></span>')
                display_marking_label = Gtk.Label()
                display_marking_label.set_markup(label_text)
                self._meta_box.add(display_marking_label)

        self._message_icons = MessageIcons()

        if error is not None:
            self.set_error(to_user_string(error))

        if marker is not None:
            if marker in ('received', 'displayed'):
                self.set_receipt()

        self._meta_box.pack_end(self._message_icons, False, True, 0)
        avatar = self._get_avatar(kind, name)
        self._avatar_image = Gtk.Image.new_from_surface(avatar)
        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        avatar_placeholder.set_valign(Gtk.Align.START)
        avatar_placeholder.add(self._avatar_image)

        bottom_box = Gtk.Box(spacing=6)
        bottom_box.add(self._message_widget)
        more_menu_button = MoreMenuButton(self)
        more_menu_button.set_hexpand(True)
        more_menu_button.set_halign(Gtk.Align.END)
        bottom_box.pack_end(more_menu_button, False, True, 0)

        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(bottom_box, 1, 1, 1, 1)

        self.show_all()

    def _check_for_highlight(self, content):
        needs_highlight = message_needs_highlight(
            content.text,
            self._contact.nickname,
            self._client.get_own_jid().bare)
        if needs_highlight:
            self.get_style_context().add_class(
                'conversation-mention-highlight')

    def _get_avatar(self, kind, name):
        if self._contact is None:
            return None

        scale = self.get_scale_factor()
        if self._is_groupchat:
            contact = self._contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self._contact

        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

    def is_same_sender(self, message):
        return message.name == self.name

    def is_mergeable(self, message):
        if message.type != self.type:
            return False
        if not self.is_same_sender(message):
            return False
        return abs(message.timestamp - self.timestamp) < MERGE_TIMEFRAME

    def on_copy_message(self, _widget):
        timestamp = self.timestamp.strftime('%x, %X')
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = self._message_widget.get_text()
        clip.set_text(f'{timestamp} - {self.name}: {text}', -1)

    def on_quote_message(self, _widget):
        self.get_parent().on_quote(self._message_widget.get_text())

    def _get_encryption_image(self, additional_data, encryption_enabled=None):
        details = self._get_encryption_details(additional_data)
        if details is None:
            # Message was not encrypted
            if not encryption_enabled:
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
                icon, trust_tooltip, color = TRUST_SYMBOL_DATA[trust]
                tooltip = '%s\n%s' % (tooltip, trust_tooltip)
            if fingerprint is not None:
                fingerprint = format_fingerprint(fingerprint)
                tooltip = '%s\n<tt>%s</tt>' % (tooltip, fingerprint)

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_tooltip_markup(tooltip)
        image.get_style_context().add_class(color)
        image.show()
        return image

    @staticmethod
    def _get_encryption_details(additional_data):
        name = additional_data.get_value('encrypted', 'name')
        if name is None:
            return None

        fingerprint = additional_data.get_value('encrypted', 'fingerprint')
        trust = additional_data.get_value('encrypted', 'trust')
        return name, fingerprint, trust

    def _on_quote_selection(self, _widget, text):
        self.get_parent().on_quote(text)

    @property
    def has_receipt(self):
        return self._has_receipt

    @property
    def has_displayed(self):
        return self._has_displayed

    def set_receipt(self):
        self._has_receipt = True
        self._message_icons.set_receipt_icon_visible(True)

    def set_displayed(self):
        self._has_displayed = True

    def set_correction(self, text, message_id):
        self._corrections.append(self._message_widget.get_text())
        result = process(text)
        self._message_widget.add_content(result)

        self._has_receipt = False
        self._message_icons.set_receipt_icon_visible(False)
        self._message_icons.set_correction_icon_visible(True)

        corrections = '\n'.join(line for line in self._corrections)
        corrections = reduce_chars_newlines(
            corrections, max_chars=150, max_lines=10)
        self._message_icons.set_correction_tooltip(
            _('Message corrected. Original message:\n%s') % corrections)
        # Update message_id for this row
        self.message_id = message_id

    def set_error(self, tooltip):
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)

    def update_avatar(self):
        avatar = self._get_avatar(self.kind, self.name)
        self._avatar_image.set_from_surface(avatar)

    def set_merged(self, merged):
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
    def __init__(self):
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

    def set_receipt_icon_visible(self, visible):
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)
        self._marker_image.set_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_tooltip_text(Q_('?Message state:Received'))

    def set_correction_icon_visible(self, visible):
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text):
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible):
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text):
        self._error_image.set_tooltip_markup(text)
