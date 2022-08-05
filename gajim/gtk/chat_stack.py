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

import sys
import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties

from gajim.common import app
from gajim.common import helpers
from gajim.common.events import MucDiscoUpdate
from gajim.common.i18n import _
from gajim.common.const import CallType
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.structs import OutgoingMessage
from gajim.common.types import ChatContactT

from .chat_banner import ChatBanner
from .chat_function_page import ChatFunctionPage
from .const import TARGET_TYPE_URI_LIST
from .control_stack import ControlStack
from .controls.groupchat import GroupchatControl
from .message_actions_box import MessageActionsBox
from .util import EventHelper, open_window

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
        self._control_stack = ControlStack()
        self._message_action_box = MessageActionsBox()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(self._chat_banner)
        box.add(Gtk.Separator())
        box.add(self._control_stack)
        box.add(Gtk.Separator())
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
        self._drop_area.set_name('DropArea')
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

    def _get_current_contact(self) -> ChatContactT:
        assert self._current_contact is not None
        return self._current_contact

    def process_escape(self) -> bool:
        if self.get_visible_child_name() == 'function':
            self._chat_function_page.process_escape()
            return True
        return False

    def get_control_stack(self) -> ControlStack:
        return self._control_stack

    def get_message_action_box(self) -> MessageActionsBox:
        return self._message_action_box

    def show_chat(self, account: str, jid: JID) -> None:
        # Store (preserve) primary clipboard and restore it after switching
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        old_primary_clipboard = clipboard.wait_for_text()

        if self._current_contact is not None:
            self._current_contact.disconnect_all_from_obj(self)

        client = app.get_client(account)
        self._current_contact = client.get_module('Contacts').get_contact(jid)

        self._chat_banner.switch_contact(account, jid)
        self._control_stack.show_chat(account, jid)
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
                    self._show_chat_function_page('captcha-request')
                    return

                if muc_data.state.is_password_request:
                    self._show_chat_function_page('password-request')
                    return

                if not muc_data.state.is_joined:
                    if muc_data.error == 'captcha-failed':
                        self._show_chat_function_page(
                            'captcha-error', muc_data.error_text)
                        return
                    if muc_data.error in ('join-failed', 'creation-failed'):
                        self._show_chat_function_page(
                            muc_data.error, muc_data.error_text)
                        return

        self.set_transition_type(Gtk.StackTransitionType.NONE)
        self.set_visible_child_name('controls')

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
        self._show_chat_function_page('password-request')

    def _on_room_captcha_challenge(self,
                                   contact: GroupchatContact,
                                   _signal_name: str,
                                   properties: MessageProperties
                                   ) -> None:
        self._show_chat_function_page('captcha-request')

    def _on_room_captcha_error(self,
                               _contact: GroupchatContact,
                               _signal_name: str,
                               error: StanzaError
                               ) -> None:
        error_text = helpers.to_user_string(error)
        self._show_chat_function_page('captcha-error', error_text)

    def _on_room_creation_failed(self,
                                 _contact: GroupchatContact,
                                 _signal_name: str,
                                 properties: MessageProperties
                                 ) -> None:
        assert properties.error is not None
        error_text = helpers.to_user_string(properties.error)
        self._show_chat_function_page('creation-failed', error_text)

    def _on_room_join_failed(self,
                             _contact: GroupchatContact,
                             _signal_name: str,
                             error: StanzaError
                             ) -> None:
        self._show_chat_function_page(
            'join-failed', helpers.to_user_string(error))

    def _on_room_config_failed(self,
                               _contact: GroupchatContact,
                               _signal_name: str,
                               error: StanzaError
                               ) -> None:
        self._show_chat_function_page(
            'config-failed', helpers.to_user_string(error))

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:
        self._update_group_chat_actions(contact)

    def _on_user_joined(self,
                        contact: GroupchatContact,
                        _signal_name: str,
                        _user_contact: GroupchatParticipant,
                        _properties: PresenceProperties
                        ) -> None:
        self._update_group_chat_actions(contact)

    def _on_user_role_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str,
                              _user_contact: GroupchatParticipant,
                              _properties: PresenceProperties
                              ) -> None:
        self._update_group_chat_actions(contact)

    def _on_user_affiliation_changed(self,
                                     contact: GroupchatContact,
                                     _signal_name: str,
                                     _user_contact: GroupchatParticipant,
                                     _properties: PresenceProperties
                                     ) -> None:
        self._update_group_chat_actions(contact)

    def _on_muc_disco_update(self, event: MucDiscoUpdate) -> None:
        if self._current_contact is None:
            return

        if event.jid != self._current_contact.jid:
            return

        if isinstance(self._current_contact, GroupchatContact):
            self._update_group_chat_actions(self._current_contact)

    def _connect_actions(self) -> None:
        actions = [
            'add-to-roster',
            'clear-chat',
            'invite-contacts',
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

        app.window.get_action('input-bold').set_enabled(True)
        app.window.get_action('input-italic').set_enabled(True)
        app.window.get_action('input-strike').set_enabled(True)
        app.window.get_action('input-clear').set_enabled(True)
        app.window.get_action('clear-chat').set_enabled(True)

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
        current_control = self._control_stack.get_current_control()

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

        elif action_name == 'invite-contacts':
            open_window('AdhocMUC', account=account, contact=contact)

        elif action_name == 'add-to-roster':
            if (isinstance(contact, GroupchatParticipant) and
                    contact.real_jid is not None):
                jid = contact.real_jid
            open_window('AddContact', account=account, jid=jid)

        elif action_name == 'clear-chat':
            assert current_control is not None
            current_control.reset_view()

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
            self._show_chat_function_page('invite')

        elif action_name == 'muc-change-nickname':
            self._show_chat_function_page('change-nickname')

        elif action_name == 'muc-execute-command':
            assert isinstance(current_control, GroupchatControl)
            nick = None
            if param is not None:
                nick = param.get_string()
            if nick:
                assert isinstance(contact, GroupchatContact)
                resource_contact = contact.get_resource(nick)
                jid = resource_contact.jid
            open_window('AdHocCommands', account=account, jid=jid)

        elif action_name == 'muc-kick':
            assert isinstance(current_control, GroupchatControl)
            assert param is not None
            kick_nick = param.get_string()
            self._show_chat_function_page('kick', data=kick_nick)

        elif action_name == 'muc-ban':
            assert isinstance(current_control, GroupchatControl)
            assert param is not None
            ban_jid = param.get_string()
            self._show_chat_function_page('ban', data=ban_jid)

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
            control = app.window.get_active_control()
            if control is not None:
                control.drag_data_file_transfer(selection)

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
                                 function: str,
                                 data: Optional[str] = None
                                 ) -> None:
        assert self._current_contact is not None
        self._chat_function_page.set_mode(
            self._current_contact, function, data)
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
        control = self._control_stack.get_current_control()
        assert control is not None
        control.add_info_message(message)

    def _on_send_message(self) -> None:
        self._message_action_box.msg_textview.replace_emojis()
        message = self._message_action_box.msg_textview.get_text()

        control = self._control_stack.get_current_control()
        assert control is not None

        contact = self._current_contact
        assert contact is not None

        encryption = contact.settings.get('encryption')
        if encryption:
            self.sendmessage = True
            app.plugin_manager.extension_point(
                'send_message' + encryption,
                control)
            if not self.sendmessage:
                return

        client = app.get_client(contact.account)

        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return

        # if process_commands and self.process_as_command(message):
        #     return

        label = self._message_action_box.get_seclabel()

        correct_id = None
        if self._message_action_box.is_correcting:
            correct_id = self._message_action_box.last_message_id.get(
                (contact.account, contact.jid))
            self._message_action_box.is_correcting = False

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
                                   control=control,
                                   correct_id=correct_id)

        client.send_message(message_)

        self._message_action_box.msg_textview.clear()

    def get_last_message_id(self, account: str, jid: JID) -> Optional[str]:
        return self._message_action_box.last_message_id.get((account, jid))

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
        self._control_stack.clear()

    def process_event(self, event: Any) -> None:
        if isinstance(event, MucDiscoUpdate):
            self._on_muc_disco_update(event)
        self._control_stack.process_event(event)
        self._message_action_box.process_event(event)


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
        app.app.activate_action('start-chat', GLib.Variant('s', ''))
