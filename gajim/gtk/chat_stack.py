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

import sys
import logging
import time

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import events
from gajim.common import helpers
from gajim.common import preview_helpers
from gajim.common.commands import ChatCommands
from gajim.common.i18n import _
from gajim.common.const import CallType
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.structs import OutgoingMessage
from gajim.common.types import ChatContactT
from gajim.gui.dialogs import ErrorDialog

from .chat_banner import ChatBanner
from .chat_function_page import ChatFunctionPage
from .chat_function_page import FunctionMode
from .const import TARGET_TYPE_URI_LIST
from .control import ChatControl
from .message_actions_box import MessageActionsBox
from .message_input import MessageInputTextView
from .util import EventHelper
from .util import open_window
from .util import set_urgency_hint

log = logging.getLogger('gajim.gui.chatstack')


class ChatStack(Gtk.Stack, EventHelper):
    def __init__(self):
        Gtk.Stack.__init__(self)
        EventHelper.__init__(self)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self._current_contact: Optional[ChatContactT] = None

        self.add_named(ChatPlaceholderBox(), 'empty')

        self._chat_function_page = ChatFunctionPage()
        self._chat_function_page.connect('finish', self._on_function_finished)
        self._chat_function_page.connect('message', self._on_function_message)
        self.add_named(self._chat_function_page, 'function')

        self._chat_banner = ChatBanner()
        self._chat_control = ChatControl()
        self._message_action_box = MessageActionsBox()

        app.commands.connect('command-error', self._on_command_signal)
        app.commands.connect('command-not-found', self._on_command_signal)
        app.commands.connect('command-result', self._on_command_signal)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(self._chat_banner)
        separator1 = Gtk.Separator()
        separator1.set_margin_start(6)
        separator1.set_margin_end(6)
        box.add(separator1)
        box.add(self._chat_control.widget)
        separator2 = Gtk.Separator()
        separator2.set_margin_start(6)
        separator2.set_margin_end(6)
        box.add(separator2)
        box.add(self._message_action_box)

        dnd_icon = Gtk.Image.new_from_icon_name(
            'mail-attachment-symbolic', Gtk.IconSize.DIALOG)
        dnd_icon.set_vexpand(True)
        dnd_icon.set_valign(Gtk.Align.END)
        dnd_label = Gtk.Label(label=_('Drop files or contacts'))
        dnd_label.set_max_width_chars(40)
        dnd_label.set_vexpand(True)
        dnd_label.set_valign(Gtk.Align.START)
        dnd_label.get_style_context().add_class('bold16')

        self._drop_area = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._drop_area.set_no_show_all(True)
        self._drop_area.set_hexpand(True)
        self._drop_area.set_vexpand(True)
        self._drop_area.get_style_context().add_class('solid-background')
        self._drop_area.add(dnd_icon)
        self._drop_area.add(dnd_label)

        overlay = Gtk.Overlay()
        overlay.add_overlay(self._drop_area)
        overlay.add(box)
        overlay.connect('drag-data-received', self._on_drag_data_received)
        overlay.connect('drag-motion', self._on_drag_motion)
        overlay.connect('drag-leave', self._on_drag_leave)

        uri_entry = Gtk.TargetEntry.new(
            'text/uri-list',
            Gtk.TargetFlags.OTHER_APP,
            TARGET_TYPE_URI_LIST)
        dnd_list = [uri_entry,
                    Gtk.TargetEntry.new(
                        'OBJECT_DROP',
                        Gtk.TargetFlags.SAME_APP,
                        0)]
        dst_targets = Gtk.TargetList.new([uri_entry])
        dst_targets.add_text_targets(0)

        overlay.drag_dest_set(
            Gtk.DestDefaults.ALL,
            dnd_list,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        overlay.drag_dest_set_target_list(dst_targets)

        self.add_named(overlay, 'controls')

        self._connect_actions()
        self.show_all()

        self.register_events([
            ('message-received', 85, self._on_message_received),
            ('gc-message-received', 85, self._on_message_received),
            ('muc-disco-update', 85, self._on_muc_disco_update),
            ('account-connected', 85, self._on_account_state),
            ('account-disconnected', 85, self._on_account_state),
        ])

    def _get_current_contact(self) -> ChatContactT:
        assert self._current_contact is not None
        return self._current_contact

    def process_escape(self) -> bool:
        if self.get_visible_child_name() == 'function':
            self._chat_function_page.process_escape()
            return True

        if self._message_action_box.is_correcting:
            self._message_action_box.toggle_message_correction()
            return True

        return False

    def get_chat_control(self) -> ChatControl:
        return self._chat_control

    def get_message_action_box(self) -> MessageActionsBox:
        return self._message_action_box

    def get_message_input(self) -> MessageInputTextView:
        return self._message_action_box.msg_textview

    def show_chat(self, account: str, jid: JID) -> None:
        # Store (preserve) primary clipboard and restore it after switching
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        old_primary_clipboard = clipboard.wait_for_text()

        if self._current_contact is not None:
            self._current_contact.disconnect_all_from_obj(self)

        client = app.get_client(account)
        self._current_contact = client.get_module('Contacts').get_contact(jid)

        self._chat_banner.switch_contact(self._current_contact)
        self._chat_control.switch_contact(self._current_contact)
        self._message_action_box.switch_contact(self._current_contact)

        self._update_base_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            self._current_contact.multi_connect({
                'user-joined': self._on_user_joined,
                'user-role-changed': self._on_user_role_changed,
                'user-affiliation-changed': self._on_user_affiliation_changed,
                'state-changed': self._on_muc_state_changed,
                'room-password-required': self._on_room_password_required,
                'room-captcha-challenge': self._on_room_captcha_challenge,
                'room-captcha-error': self._on_room_captcha_error,
                'room-creation-failed': self._on_room_creation_failed,
                'room-join-failed': self._on_room_join_failed,
                'room-config-failed': self._on_room_config_failed,
            })
            self._update_group_chat_actions(self._current_contact)

        elif isinstance(self._current_contact, GroupchatParticipant):
            self._update_participant_actions(self._current_contact)

        else:
            self._update_chat_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            muc_data = client.get_module('MUC').get_muc_data(
                str(self._current_contact.jid))
            if muc_data is not None:
                if muc_data.state.is_captcha_request:
                    self._show_chat_function_page(FunctionMode.CAPTCHA_REQUEST)
                    return

                if muc_data.state.is_password_request:
                    self._show_chat_function_page(FunctionMode.PASSWORD_REQUEST)
                    return

                if not muc_data.state.is_joined:
                    if muc_data.error == 'captcha-failed':
                        self._show_chat_function_page(
                            FunctionMode.CAPTCHA_ERROR, muc_data.error_text)
                        return
                    if muc_data.error == 'join-failed':
                        self._show_chat_function_page(
                            FunctionMode.JOIN_FAILED, muc_data.error_text)
                        return
                    if muc_data.error == 'creation-failed':
                        self._show_chat_function_page(
                            FunctionMode.CREATION_FAILED, muc_data.error_text)
                        return

        self.set_transition_type(Gtk.StackTransitionType.NONE)
        self.set_visible_child_name('controls')

        app.plugin_manager.extension_point(
            'switch_contact', self._current_contact)

        if old_primary_clipboard is not None:
            GLib.idle_add(clipboard.set_text,  # pyright: ignore
                          old_primary_clipboard,
                          -1)

        GLib.idle_add(self._message_action_box.msg_textview.grab_focus)

    def _on_room_password_required(self,
                                   _contact: GroupchatContact,
                                   _signal_name: str,
                                   _properties: MessageProperties
                                   ) -> None:

        self._show_chat_function_page(FunctionMode.PASSWORD_REQUEST)

    def _on_room_captcha_challenge(self,
                                   contact: GroupchatContact,
                                   _signal_name: str,
                                   _properties: MessageProperties
                                   ) -> None:

        self._show_chat_function_page(FunctionMode.CAPTCHA_REQUEST)

    def _on_room_captcha_error(self,
                               _contact: GroupchatContact,
                               _signal_name: str,
                               error: StanzaError
                               ) -> None:

        error_text = helpers.to_user_string(error)
        self._show_chat_function_page(FunctionMode.CAPTCHA_ERROR, error_text)

    def _on_room_creation_failed(self,
                                 _contact: GroupchatContact,
                                 _signal_name: str,
                                 properties: MessageProperties
                                 ) -> None:

        assert properties.error is not None
        error_text = helpers.to_user_string(properties.error)
        self._show_chat_function_page(FunctionMode.CREATION_FAILED, error_text)

    def _on_room_join_failed(self,
                             _contact: GroupchatContact,
                             _signal_name: str,
                             error: StanzaError
                             ) -> None:

        self._show_chat_function_page(
            FunctionMode.JOIN_FAILED, helpers.to_user_string(error))

    def _on_room_config_failed(self,
                               _contact: GroupchatContact,
                               _signal_name: str,
                               error: StanzaError
                               ) -> None:

        self._show_chat_function_page(
            FunctionMode.CONFIG_FAILED, helpers.to_user_string(error))

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:
        self._update_group_chat_actions(contact)

    def _on_user_joined(self,
                        contact: GroupchatContact,
                        _signal_name: str,
                        _user_contact: GroupchatParticipant,
                        _event: events.MUCUserJoined
                        ) -> None:

        self._update_group_chat_actions(contact)

    def _on_user_role_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str,
                              _user_contact: GroupchatParticipant,
                              _event: events.MUCUserRoleChanged
                              ) -> None:

        self._update_group_chat_actions(contact)

    def _on_user_affiliation_changed(self,
                                     contact: GroupchatContact,
                                     _signal_name: str,
                                     _user_contact: GroupchatParticipant,
                                     _event: events.MUCUserAffiliationChanged
                                     ) -> None:
        self._update_group_chat_actions(contact)

    def _on_muc_disco_update(self, event: events.MucDiscoUpdate) -> None:
        if not isinstance(self._current_contact, GroupchatContact):
            return

        if event.jid != self._current_contact.jid:
            return

        self._update_group_chat_actions(self._current_contact)

    def _on_account_state(self,
                          event: Union[events.AccountConnected,
                                       events.AccountDisconnected]
                          ) -> None:

        if self._current_contact is None:
            return

        if event.account != self._current_contact.account:
            return

        self._update_base_actions(self._current_contact)

        if isinstance(self._current_contact, GroupchatContact):
            self._update_group_chat_actions(self._current_contact)
        elif isinstance(self._current_contact, GroupchatParticipant):
            self._update_participant_actions(self._current_contact)
        else:
            self._update_chat_actions(self._current_contact)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        if not event.msgtxt or event.properties.is_sent_carbon:
            return

        if app.window.is_chat_active(event.account, event.jid):
            return

        self._issue_notification(event)

    def _issue_notification(self, event: events.MessageReceived) -> None:
        text = event.msgtxt
        tim = event.properties.timestamp
        additional_data = event.additional_data
        client = app.get_client(event.account)
        contact = client.get_module('Contacts').get_contact(event.jid)

        title = _('New message from')

        is_previewable = app.preview_manager.is_previewable(
            text, additional_data)
        if is_previewable:
            if text.startswith('geo:'):
                text = _('Location')
            else:
                file_name = preview_helpers.filename_from_uri(text)
                _icon, file_type = preview_helpers.guess_simple_file_type(text)
                text = f'{file_type} ({file_name})'

        sound: Optional[str] = None
        msg_type = 'chat-message'
        if isinstance(contact, BareContact):
            msg_type = 'chat-message'
            title += f' {contact.name}'
            sound = 'first_message_received'
            set_urgency_hint(app.window, True)

        if isinstance(contact, GroupchatContact):
            msg_type = 'group-chat-message'
            title += f' {event.resource} ({contact.name})'
            assert contact.nickname is not None
            needs_highlight = helpers.message_needs_highlight(
                text, contact.nickname, client.get_own_jid().bare)
            if needs_highlight:
                sound = 'muc_message_highlight'
            else:
                sound = 'muc_message_received'

            if not contact.can_notify() and not needs_highlight:
                return

            if contact.can_notify() or needs_highlight:
                set_urgency_hint(app.window, True)

        if isinstance(contact, GroupchatParticipant):
            msg_type = 'private-chat-message'
            title += f' {contact.name} (private in {contact.room.name})'
            sound = 'first_message_received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim is not None and time.mktime(time.localtime()) - tim > 1:
            sound = None

        if app.settings.get('notification_preview_message'):
            if text.startswith('/me') or text.startswith('/me\n'):
                name = contact.name
                if isinstance(contact, GroupchatContact):
                    name = contact.nickname
                text = f'* {name} {text[3:]}'

        app.ged.raise_event(
            events.Notification(account=contact.account,
                                jid=contact.jid,
                                type='incoming-message',
                                sub_type=msg_type,
                                title=title,
                                text=text,
                                sound=sound))

    def _connect_actions(self) -> None:
        actions = [
            'add-to-roster',
            'send-file',
            'send-file-httpupload',
            'send-file-jingle',
            'show-contact-info',
            'start-video-call',
            'start-voice-call',
            'send-message',
            'muc-change-nickname',
            'muc-invite',
            'muc-contact-info',
            'muc-execute-command',
            'muc-ban',
            'muc-kick',
            'muc-change-role',
            'muc-change-affiliation',
            'muc-request-voice',
        ]

        for action in actions:
            action = app.window.lookup_action(action)
            assert action is not None
            action.connect('activate', self._on_action)

    def _update_base_actions(self, contact: ChatContactT) -> None:
        client = app.get_client(contact.account)
        online = app.account_is_connected(contact.account)

        has_text = self._message_action_box.msg_textview.has_text
        app.window.get_action('send-message').set_enabled(
            online and has_text)

        httpupload = app.window.get_action('send-file-httpupload')
        httpupload.set_enabled(online and
                               client.get_module('HTTPUpload').available)

        jingle = app.window.get_action('send-file-jingle')
        jingle.set_enabled(online and contact.is_jingle_available)

        app.window.get_action('send-file').set_enabled(
            jingle.get_enabled() or
            httpupload.get_enabled())

        app.window.get_action('show-contact-info').set_enabled(online)
        app.window.get_action('correct-message').set_enabled(online)

    def _update_chat_actions(self, contact: BareContact) -> None:
        account = contact.account
        online = app.account_is_connected(account)

        app.window.get_action('start-voice-call').set_enabled(
            online and contact.supports_audio() and
            sys.platform != 'win32')
        app.window.get_action('start-video-call').set_enabled(
            online and contact.supports_video() and
            sys.platform != 'win32')

        app.window.get_action('quote').set_enabled(online)
        app.window.get_action('mention').set_enabled(online)

    def _update_group_chat_actions(self, contact: GroupchatContact) -> None:
        joined = contact.is_joined
        is_visitor = False
        if joined:
            self_contact = contact.get_self()
            assert self_contact
            is_visitor = self_contact.role.is_visitor

        app.window.get_action('muc-change-nickname').set_enabled(
            joined and not contact.is_irc)

        app.window.get_action('muc-contact-info').set_enabled(joined)
        app.window.get_action('muc-execute-command').set_enabled(joined)
        app.window.get_action('muc-ban').set_enabled(joined)
        app.window.get_action('muc-kick').set_enabled(joined)
        app.window.get_action('muc-change-role').set_enabled(joined)
        app.window.get_action('muc-change-affiliation').set_enabled(joined)
        app.window.get_action('muc-invite').set_enabled(joined)

        app.window.get_action('muc-request-voice').set_enabled(is_visitor)

        app.window.get_action('quote').set_enabled(joined)
        app.window.get_action('mention').set_enabled(joined)

    def _update_participant_actions(self,
                                    contact: GroupchatParticipant) -> None:
        pass

    def _on_action(self,
                   action: Gio.SimpleAction,
                   param: Optional[GLib.Variant]) -> None:

        action_name = action.get_name()
        contact = self._current_contact
        assert contact is not None
        account = contact.account
        client = app.get_client(account)
        jid = contact.jid

        if action_name == 'send-message':
            self._on_send_message()

        elif action_name == 'start-voice-call':
            app.call_manager.start_call(account, jid, CallType.AUDIO)

        elif action_name == 'start-video-call':
            app.call_manager.start_call(account, jid, CallType.VIDEO)

        elif action_name.startswith('send-file'):
            name = action.get_name()
            if 'httpupload' in name:
                app.interface.start_file_transfer(contact, method='httpupload')
                return

            if 'jingle' in name:
                app.interface.start_file_transfer(contact, method='jingle')
                return

            app.interface.start_file_transfer(contact)

        elif action_name == 'add-to-roster':
            if (isinstance(contact, GroupchatParticipant) and
                    contact.real_jid is not None):
                jid = contact.real_jid
            open_window('AddContact', account=account, jid=jid)

        elif action_name == 'show-contact-info':
            if isinstance(contact, GroupchatContact):
                open_window('GroupchatDetails', contact=contact)
            else:
                app.window.contact_info(account, str(jid))

        elif action_name == 'muc-contact-info':
            assert param is not None
            nick = param.get_string()
            assert isinstance(contact, GroupchatContact)
            resource_contact = contact.get_resource(nick)
            open_window(
                'ContactInfo', account=account, contact=resource_contact)

        elif action_name == 'muc-invite':
            self._show_chat_function_page(FunctionMode.INVITE)

        elif action_name == 'muc-change-nickname':
            self._show_chat_function_page(FunctionMode.CHANGE_NICKNAME)

        elif action_name == 'muc-execute-command':
            nick = None
            if param is not None:
                nick = param.get_string()
            if nick:
                assert isinstance(contact, GroupchatContact)
                resource_contact = contact.get_resource(nick)
                jid = resource_contact.jid
            open_window('AdHocCommands', account=account, jid=jid)

        elif action_name == 'muc-kick':
            assert param is not None
            kick_nick = param.get_string()
            self._show_chat_function_page(FunctionMode.KICK, data=kick_nick)

        elif action_name == 'muc-ban':
            assert param is not None
            ban_jid = param.get_string()
            self._show_chat_function_page(FunctionMode.BAN, data=ban_jid)

        elif action_name == 'muc-change-role':
            assert param is not None
            nick, role = param.get_strv()
            client.get_module('MUC').set_role(contact.jid, nick, role)

        elif action_name == 'muc-change-affiliation':
            assert param is not None
            jid, affiliation = param.get_strv()
            client.get_module('MUC').set_affiliation(
                contact.jid,
                {jid: {'affiliation': affiliation}})

        elif action_name == 'muc-request-voice':
            client.get_module('MUC').request_voice(contact.jid)

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _context: Gdk.DragContext,
                               _x_coord: int,
                               _y_coord: int,
                               selection: Gtk.SelectionData,
                               target_type: int,
                               _timestamp: int
                               ) -> None:
        if not selection.get_data():
            return

        log.debug('Drop received: %s, %s', selection.get_data(), target_type)

        # TODO: Contact drag and drop for invitations (AdHoc MUC/MUC)
        if target_type == TARGET_TYPE_URI_LIST:
            if self._chat_control.has_active_chat():
                self._chat_control.drag_data_file_transfer(selection)

    def _on_drag_leave(self,
                       _widget: Gtk.Widget,
                       _context: Gdk.DragContext,
                       _time: int
                       ) -> None:
        self._drop_area.set_no_show_all(True)
        self._drop_area.hide()

    def _on_drag_motion(self,
                        _widget: Gtk.Widget,
                        _context: Gdk.DragContext,
                        _x_coord: int,
                        _y_coord: int,
                        _time: int
                        ) -> bool:
        self._drop_area.set_no_show_all(False)
        self._drop_area.show_all()
        return True

    def _show_chat_function_page(self,
                                 function_mode: FunctionMode,
                                 data: Optional[str] = None
                                 ) -> None:

        assert self._current_contact is not None
        self._chat_function_page.set_mode(
            self._current_contact, function_mode, data)
        self.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.set_visible_child_name('function')

    def _on_function_finished(self,
                              _function_page: ChatFunctionPage,
                              close_control: bool
                              ) -> None:
        if close_control:
            self._close_control()
            self.set_visible_child_name('empty')
            self.set_transition_type(Gtk.StackTransitionType.NONE)
            return

        self.set_visible_child_name('controls')
        self.set_transition_type(Gtk.StackTransitionType.NONE)

    def _on_function_message(self,
                             _function_page: ChatFunctionPage,
                             message: str
                             ) -> None:

        self._chat_control.add_info_message(message)

    def _on_send_message(self) -> None:
        self._message_action_box.msg_textview.replace_emojis()
        message = self._message_action_box.msg_textview.get_text()
        if message.startswith('//'):
            # Escape sequence for chat commands
            message = message[1:]

        contact = self._current_contact
        assert contact is not None

        encryption = contact.settings.get('encryption')
        if encryption:
            if encryption not in app.plugin_manager.encryption_plugins:
                ErrorDialog(_('Encryption error'),
                            _('Missing necessary encryption plugin'))
                return

            self._chat_control.sendmessage = True
            app.plugin_manager.extension_point(
                'send_message' + encryption,
                self._chat_control)
            if not self._chat_control.sendmessage:
                return

        client = app.get_client(contact.account)

        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return

        label = self._message_action_box.get_seclabel()

        correct_id = None
        if self._message_action_box.is_correcting:
            correct_id = self._message_action_box.try_message_correction(
                message)
            if correct_id is None:
                return

        chatstate = client.get_module('Chatstate').get_active_chatstate(
            contact)

        type_ = 'chat'
        if isinstance(contact, GroupchatContact):
            type_ = 'groupchat'

        message_ = OutgoingMessage(account=contact.account,
                                   contact=contact,
                                   message=message,
                                   type_=type_,
                                   chatstate=chatstate,
                                   label=label,
                                   control=self._chat_control,
                                   correct_id=correct_id)

        client.send_message(message_)

        self._message_action_box.msg_textview.clear()
        app.storage.drafts.set(contact, '')

    def get_last_message_id(self, contact: ChatContactT) -> Optional[str]:
        return self._message_action_box.get_last_message_id(contact)

    def _close_control(self) -> None:
        assert self._current_contact is not None
        app.window.activate_action(
            'remove-chat',
            GLib.Variant('as',
                         [self._current_contact.account,
                          str(self._current_contact.jid)]))

    def clear(self) -> None:
        if self._current_contact is not None:
            self._current_contact.disconnect_all_from_obj(self)

        self.set_visible_child_name('empty')
        self._chat_banner.clear()
        self._message_action_box.clear()
        self._chat_control.clear()

    def _on_command_signal(self,
                           chat_commands: ChatCommands,
                           signal_name: str,
                           text: str
                           ) -> None:

        is_error = signal_name != 'command-result'
        self._chat_control.add_command_output(text, is_error)


class ChatPlaceholderBox(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_valign(Gtk.Align.CENTER)
        pixbuf = Gtk.IconTheme.load_icon_for_scale(
            Gtk.IconTheme.get_default(),
            'org.gajim.Gajim-symbolic',
            100,
            self.get_scale_factor(),
            Gtk.IconLookupFlags.FORCE_SIZE)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.get_style_context().add_class('dim-label')
        self.add(image)

        button = Gtk.Button(label=_('Start Chatting…'))
        button.set_halign(Gtk.Align.CENTER)
        button.connect('clicked', self._on_start_chatting)
        self.add(button)

    def _on_start_chatting(self, _button: Gtk.Button) -> None:
        app.app.activate_action('start-chat', GLib.Variant('as', ['', '']))
