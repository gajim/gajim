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

from typing import Any
from typing import Optional

import pickle
from datetime import datetime
from urllib.parse import urlparse

import cairo
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import RowHeaderType
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_retraction_text
from gajim.common.helpers import get_uf_relative_time
from gajim.common.helpers import message_needs_highlight
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import format_geo_coords
from gajim.common.preview_helpers import guess_simple_file_type
from gajim.common.preview_helpers import split_geo_uri
from gajim.common.storage.draft import DraftStorage
from gajim.common.types import ChatContactT
from gajim.common.types import OneOnOneContactT

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_chat_list_row_menu
from gajim.gtk.util import GajimPopover


class ChatListRow(Gtk.ListBoxRow):

    __gsignals__ = {
        'unread-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            ()),
        'context-menu-state-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool,)),
    }

    def __init__(self,
                 workspace_id: str,
                 account: str,
                 jid: JID,
                 type_: str,
                 pinned: bool,
                 position: int
                 ) -> None:

        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid
        self.workspace_id = workspace_id
        self.type = type_
        self.position = position

        self._conversations_header = RowHeader(RowHeaderType.CONVERSATIONS)
        self._pinned_header = RowHeader(RowHeaderType.PINNED)

        self._client = app.get_client(account)

        self.contact = self._client.get_module('Contacts').get_contact(jid)
        self._connect_contact_signals()

        self.contact_name: str = self.contact.name
        self.timestamp: float = 0
        self.stanza_id: Optional[str] = None
        self.message_id: Optional[str] = None

        self._unread_count: int = 0
        self._needs_muc_highlight: bool = False
        self._pinned: bool = pinned

        self.get_style_context().add_class('chatlist-row')

        self._ui = get_builder('chat_list_row.ui')
        self._ui.connect_signals(self)
        self.add(self._ui.eventbox)

        self.connect('state-flags-changed', self._on_state_flags_changed)
        self.connect('destroy', self._on_destroy)

        app.settings.connect_signal(
            'mute_until',
            self._on_mute_setting_changed,
            self.contact.account,
            self.contact.jid)
        self._on_mute_setting_changed()

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'CHAT_LIST_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        self.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            entries,
            Gdk.DragAction.MOVE)
        self.connect('drag-begin', self._on_drag_begin)
        self.connect('drag-end', self._on_drag_end)
        self.connect('drag-data-get', self._on_drag_data_get)

        if self.type == 'groupchat':
            self._ui.group_chat_indicator.show()

        self.update_avatar()
        self.update_name()
        self.update_account_identifier()

        app.storage.drafts.connect('draft-update', self._on_draft_update)

        if (isinstance(self.contact, GroupchatContact) and
                not self.contact.can_notify()):
            self._ui.unread_label.get_style_context().add_class(
                'unread-counter-silent')

        self._display_last_conversation_line()

    def _display_last_conversation_line(self) -> None:
        line = app.storage.archive.get_last_conversation_line(
            self.contact.account, self.contact.jid)
        if line is None:
            self.show_all()
            return

        if line.message is not None:
            message_text = line.message

            if line.additional_data is not None:
                retracted_by = line.additional_data.get_value(
                    'retracted', 'by')
                if retracted_by is not None:
                    reason = line.additional_data.get_value(
                        'retracted', 'reason')
                    message_text = get_retraction_text(
                        self.account, retracted_by, reason)

            me_nickname = None
            if line.kind in (KindConstant.CHAT_MSG_SENT,
                             KindConstant.SINGLE_MSG_SENT):
                self.set_nick(_('Me'))
                me_nickname = app.nicks[self.contact.account]

            if line.kind == KindConstant.GC_MSG:
                our_nick = get_group_chat_nick(
                    self.contact.account, self.contact.jid)
                if line.contact_name == our_nick:
                    self.set_nick(_('Me'))
                    me_nickname = our_nick
                else:
                    self.set_nick(line.contact_name)
                    me_nickname = line.contact_name

            self.set_message_text(
                message_text,
                nickname=me_nickname,
                additional_data=line.additional_data)

            self.set_timestamp(line.time)

            self.stanza_id = line.stanza_id
            self.message_id = line.message_id

        if line.kind in (KindConstant.FILE_TRANSFER_INCOMING,
                         KindConstant.FILE_TRANSFER_OUTGOING):
            self.set_message_text(
                _('File'), icon_name='text-x-generic-symbolic')
            self.set_timestamp(line.time)

        if line.kind in (KindConstant.CALL_INCOMING,
                         KindConstant.CALL_OUTGOING):
            self.set_message_text(
                _('Call'), icon_name='call-start-symbolic')
            self.set_timestamp(line.time)

        self.show_all()

    @property
    def is_pinned(self) -> bool:
        return self._pinned

    @property
    def unread_count(self) -> int:
        if (self.contact.is_groupchat and not self.contact.can_notify() and
                not self._needs_muc_highlight):
            return 0
        return self._unread_count

    @unread_count.setter
    def unread_count(self, value: int) -> None:
        self._unread_count = value
        self._update_unread()
        self.emit('unread-changed')

    def get_header_type(self) -> Optional[RowHeaderType]:
        header = self.get_header()
        if header is None:
            return None
        assert isinstance(header, RowHeader)
        return header.type

    def set_header_type(self, header_type: Optional[RowHeaderType]) -> None:
        if header_type == self.get_header_type():
            return

        if header_type is None:
            self.set_header(None)

        elif header_type == RowHeaderType.PINNED:
            self.set_header(self._pinned_header)

        else:
            self.set_header(self._conversations_header)

    def set_message_id(self, message_id: str) -> None:
        self.message_id = message_id

    def set_message_text(self,
                         text: str,
                         nickname: Optional[str] = None,
                         icon_name: Optional[str] = None,
                         additional_data: Optional[AdditionalDataDict] = None
                         ) -> None:

        draft = app.storage.drafts.get(self.contact)
        if draft is not None:
            self._show_draft(draft)
            return

        self._ui.message_label.get_style_context().remove_class('draft')

        icon = None
        if icon_name is not None:
            icon = Gio.Icon.new_for_string(icon_name)
        if additional_data is not None:
            if app.preview_manager.is_previewable(text, additional_data):
                scheme = urlparse(text).scheme
                if scheme == 'geo':
                    location = split_geo_uri(text)
                    icon = Gio.Icon.new_for_string('mark-location')
                    text = format_geo_coords(
                        float(location.lat), float(location.lon))
                else:
                    file_name = filename_from_uri(text)
                    icon, file_type = guess_simple_file_type(text)
                    text = f'{file_type} ({file_name})'

        text = GLib.markup_escape_text(text)
        if text.startswith('/me') and nickname is not None:
            nickname = GLib.markup_escape_text(nickname)
            text = text.replace('/me', f'* {nickname}', 1)
            text = f'<i>{text}</i>'

        # Split by newline and display last line (or first, if last is newline)
        lines = text.split('\n')
        text = lines[-1] or lines[0]
        self._ui.message_label.set_markup(text)

        if icon is None:
            self._ui.message_icon.hide()
        else:
            self._ui.message_icon.set_from_gicon(icon, Gtk.IconSize.MENU)
            self._ui.message_icon.show()

    def set_nick(self, nickname: str) -> None:
        self._ui.nick_label.set_visible(bool(nickname))
        self._ui.nick_label.set_text(
            _('%(nickname)s:') % {'nickname': nickname})

    def get_real_unread_count(self) -> int:
        return self._unread_count

    def set_stanza_id(self, stanza_id: str) -> None:
        self.stanza_id = stanza_id

    def set_timestamp(self, timestamp: float) -> None:
        self.timestamp = timestamp
        self.update_time()

    def update_account_identifier(self) -> None:
        account_class = app.css_config.get_dynamic_class(self.account)
        self._ui.account_identifier.get_style_context().add_class(account_class)
        show = len(app.settings.get_active_accounts()) > 1
        self._ui.account_identifier.set_visible(show)

    def update_avatar(self) -> None:
        scale = self.get_scale_factor()
        surface = self.contact.get_avatar(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_from_surface(surface)

    def update_name(self) -> None:
        if self.type == 'pm':
            client = app.get_client(self.account)
            muc_name = get_groupchat_name(client, self.jid.new_as_bare())
            self._ui.name_label.set_text(f'{self.contact.name} ({muc_name})')
            return

        self.contact_name = self.contact.name
        if self.jid == self._client.get_own_jid().bare:
            self.contact_name = _('Note to myself')
        self._ui.name_label.set_text(self.contact_name)

    def update_time(self) -> None:
        if self.timestamp == 0:
            return
        self._ui.timestamp_label.set_text(
            get_uf_relative_time(datetime.fromtimestamp(self.timestamp)))

    def add_unread(self, text: str) -> None:
        self._unread_count += 1
        self._update_unread()
        app.storage.cache.set_unread_count(
            self.account,
            self.jid,
            self.get_real_unread_count(),
            self.message_id,
            self.timestamp)

        if self.contact.is_groupchat:
            needs_highlight = message_needs_highlight(
                text,
                self.contact.nickname,
                self._client.get_own_jid().bare)
            if needs_highlight:
                self._needs_muc_highlight = True
                self._ui.unread_label.get_style_context().remove_class(
                    'unread-counter-silent')

        self.emit('unread-changed')

    def reset_unread(self) -> None:
        self._needs_muc_highlight = False
        self._unread_count = 0
        self._update_unread()
        self.emit('unread-changed')

        app.storage.cache.reset_unread_count(self.account, self.jid)

        # Add class again in case we were mentioned previously
        if self.contact.is_groupchat and not self.contact.can_notify():
            self._ui.unread_label.get_style_context().add_class(
                'unread-counter-silent')

    def toggle_pinned(self) -> None:
        self._pinned = not self._pinned

    def _update_unread(self) -> None:
        unread_count = self._get_unread_string(self._unread_count)
        self._ui.unread_label.set_text(unread_count)
        self._ui.unread_label.set_visible(bool(self._unread_count))

    @staticmethod
    def _get_unread_string(count: int) -> str:
        if count < 1000:
            return str(count)
        return '999+'

    def _on_mute_setting_changed(self, *args: Any) -> None:
        self._ui.mute_image.set_visible(self.contact.is_muted)

    def _on_draft_update(self,
                         _draft_storage: DraftStorage,
                         _signal_name: str,
                         contact: ChatContactT,
                         draft: str
                         ) -> None:

        if contact != self.contact:
            return

        self._show_draft(draft)

    def _show_draft(self, draft: str) -> None:
        if not draft:
            self._ui.message_label.get_style_context().remove_class('draft')
            self._display_last_conversation_line()
            return

        self.set_nick('')
        self._ui.message_label.set_text(_('Draft: %s') % draft)
        self._ui.message_label.get_style_context().add_class('draft')

    def _on_state_flags_changed(self,
                                _row: ChatListRow,
                                _flags: Gtk.StateFlags
                                ) -> None:
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def _on_destroy(self, _row: ChatListRow) -> None:
        app.settings.disconnect_signals(self)
        self.contact.disconnect_all_from_obj(self)
        if isinstance(self.contact, GroupchatParticipant):
            self.contact.room.disconnect_all_from_obj(self)

        app.check_finalize(self)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        app.window.activate_action(
            'remove-chat',
            GLib.Variant('as', [self.account, str(self.jid)]))

    def _on_row_button_press_event(self,
                                   _widget: Gtk.EventBox,
                                   event: Gdk.EventButton
                                   ) -> None:

        if event.button == Gdk.BUTTON_SECONDARY:
            self._raise_context_popover(event)

        elif event.button == Gdk.BUTTON_MIDDLE:
            app.window.activate_action(
                'remove-chat',
                GLib.Variant('as', [self.account, str(self.jid)]))

    def _raise_context_popover(self, event: Gdk.EventButton):
        menu = get_chat_list_row_menu(
            self.workspace_id, self.account, self.jid, self._pinned)

        event_widget = Gtk.get_event_widget(event)
        x = event.x
        if isinstance(event_widget, Gtk.Button):
            # When the event is triggered by pressing the close button we get
            # a x coordinate relative to the window of the close button, which
            # would be a very low x integer as the close button is small, this
            # leads to opening the menu far away from the mouse. We overwrite
            # the x coordinate with an approx. position of the close button.
            x = self.get_allocated_width() - 10

        popover = GajimPopover(menu, relative_to=self)
        popover.set_pointing_to_coord(x=x, y=event.y)
        popover.connect('closed', self._on_context_popover_closed)
        self.emit('context-menu-state-changed', True)
        popover.popup()

    def _on_context_popover_closed(self, _popover: Gtk.Popover) -> None:
        self.emit('context-menu-state-changed', False)

    def _on_drag_begin(self,
                       row: ChatListRow,
                       drag_context: Gdk.DragContext
                       ) -> None:

        # Use rendered ChatListRow as drag icon
        alloc = self.get_allocation()
        surface = cairo.ImageSurface(
            cairo.Format.ARGB32, alloc.width, alloc.height)
        context = cairo.Context(surface)
        self.draw(context)
        Gtk.drag_set_icon_surface(drag_context, surface)

        app.window.highlight_dnd_targets(row, True)

    def _on_drag_end(self,
                     row: ChatListRow,
                     _drag_context: Gdk.DragContext
                     ) -> None:

        app.window.highlight_dnd_targets(row, False)

    def _on_drag_data_get(self,
                          row: ChatListRow,
                          _drag_context: Gdk.DragContext,
                          selection_data: Gtk.SelectionData,
                          _info: int,
                          _time: int
                          ) -> None:

        app.window.highlight_dnd_targets(row, False)
        drop_type = Gdk.Atom.intern_static_string('CHAT_LIST_ITEM')
        byte_data = pickle.dumps((self.account, self.jid, self.workspace_id))
        selection_data.set(drop_type, 8, byte_data)

    def _connect_contact_signals(self) -> None:
        if isinstance(self.contact, BareContact):
            self.contact.connect('presence-update', self._on_presence_update)
            self.contact.connect('chatstate-update', self._on_chatstate_update)
            self.contact.connect('nickname-update', self._on_nickname_update)
            self.contact.connect('caps-update', self._on_avatar_update)
            self.contact.connect('avatar-update', self._on_avatar_update)

        elif isinstance(self.contact, GroupchatContact):
            self.contact.connect('avatar-update', self._on_avatar_update)
            self.contact.connect('state-changed', self._on_muc_state_changed)

            self._client.connect_signal('state-changed',
                                        self._on_client_state_changed)

        elif isinstance(self.contact, GroupchatParticipant):
            self.contact.connect('chatstate-update', self._on_chatstate_update)
            self.contact.connect('user-joined', self._on_muc_user_update)
            self.contact.connect('user-left', self._on_muc_user_update)
            self.contact.connect('user-avatar-update', self._on_muc_user_update)
            self.contact.connect('user-status-show-changed',
                                 self._on_muc_user_update)

            self.contact.room.connect('room-left', self._on_muc_update)
            self.contact.room.connect('room-destroyed', self._on_muc_update)
            self.contact.room.connect('room-kicked', self._on_muc_update)

        else:
            raise TypeError('Unkown contact type: %s' % type(self.contact))

    def _on_presence_update(self,
                            _contact: ChatContactT,
                            _signal_name: str
                            ) -> None:
        self.update_avatar()

    def _on_avatar_update(self,
                          _contact: ChatContactT,
                          _signal_name: str
                          ) -> None:
        self.update_avatar()

    def _on_client_state_changed(self, *args: Any) -> None:
        self._update_joined_state()

    def _on_muc_state_changed(self, *args: Any) -> None:
        self._update_joined_state()

    def _update_joined_state(self) -> None:
        self._ui.connection_icon.get_style_context().remove_class('spin')
        self._ui.connection_icon.get_style_context().remove_class(
            'warning-color')
        self._ui.connection_icon.get_style_context().remove_class(
            'dim-label')

        if self.contact.is_joining:
            self._ui.connection_icon.set_from_icon_name(
                'feather-refresh-cw-symbolic', Gtk.IconSize.MENU)
            self._ui.connection_icon.get_style_context().add_class('spin')
            self._ui.connection_icon.get_style_context().add_class('dim-label')
            self._ui.connection_icon.set_tooltip_text(_('Joining Group Chat…'))
            self._ui.connection_icon.show()
        elif (self.contact.is_not_joined or
                not self._client.state.is_available):
            self._ui.connection_icon.set_from_icon_name(
                'feather-zap-symbolic', Gtk.IconSize.MENU)
            self._ui.connection_icon.get_style_context().add_class(
                'warning-color')
            self._ui.connection_icon.set_tooltip_text(_('Not connected'))
            self._ui.connection_icon.show()
        else:
            self._ui.connection_icon.hide()

    def _on_muc_user_update(self,
                            _contact: GroupchatParticipant,
                            _signal_name: str,
                            *args: Any
                            ) -> None:
        self.update_avatar()

    def _on_muc_update(self,
                       _contact: GroupchatContact,
                       _signal_name: str,
                       *args: Any
                       ) -> None:
        self.update_avatar()

    def _on_chatstate_update(self,
                             contact: OneOnOneContactT,
                             _signal_name: str
                             ) -> None:
        if contact.chatstate is None:
            self._ui.chatstate_image.hide()
        else:
            self._ui.chatstate_image.set_visible(contact.chatstate.is_composing)

    def _on_nickname_update(self,
                            _contact: ChatContactT,
                            _signal_name: str
                            ) -> None:
        self.update_name()


class RowHeader(Gtk.Box):
    def __init__(self, header_type: RowHeaderType) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.type = header_type

        if header_type == RowHeaderType.CONVERSATIONS:
            text = _('Conversations')
        else:
            text = _('Pinned')

        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)

        self.add(label)

        self.get_style_context().add_class('header-box')
        if header_type == RowHeaderType.PINNED:
            self.get_style_context().add_class('header-box-first')

        self.show_all()
