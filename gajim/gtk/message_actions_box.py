# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.const import Chatstate
from nbxmpp.modules.security_labels import SecurityLabel

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.commands import CommandFailed
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.const import Draft
from gajim.common.const import SimpleClientState
from gajim.common.events import MessageSent
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.storage.archive import models as mod
from gajim.common.structs import ReplyData
from gajim.common.types import ChatContactT

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.menus import get_encryption_menu
from gajim.gtk.menus import get_format_menu
from gajim.gtk.message_input import MessageInputTextView
from gajim.gtk.referenced_message import ReplyBox
from gajim.gtk.security_label_selector import SecurityLabelSelector
from gajim.gtk.util import open_window

log = logging.getLogger('gajim.gtk.messageactionsbox')


class MessageActionsBox(Gtk.Grid, EventHelper):
    def __init__(self) -> None:
        Gtk.Grid.__init__(self)
        EventHelper.__init__(self)

        self._client: Client | None = None
        self._contact: ChatContactT | None = None
        # XEP-0308 Message Correction
        self._correcting: dict[ChatContactT, str | None] = defaultdict(lambda: None)
        self._last_message_id: dict[ChatContactT, str | None] = {}

        self._ui = get_builder('message_actions_box.ui')
        self.get_style_context().add_class('message-actions-box')

        self.attach(self._ui.box, 0, 0, 1, 1)

        self._ui.state_box_image.set_size_request(AvatarSize.CHAT, -1)
        self._ui.edit_box_image.set_size_request(AvatarSize.CHAT, -1)

        # For message replies
        self._reply_box = ReplyBox()
        self._ui.box.pack_start(self._reply_box, True, True, 0)

        self._ui.send_message_button.set_visible(
            app.settings.get('show_send_message_button'))
        app.settings.bind_signal('show_send_message_button',
                                 self._ui.send_message_button,
                                 'set_visible')

        self._security_label_selector = SecurityLabelSelector()
        self._ui.action_box.pack_start(
            self._security_label_selector, False, True, 0)

        self.msg_textview = MessageInputTextView()
        self.msg_textview.connect('buffer-changed',
                                  self._on_buffer_changed)
        self.msg_textview.connect('key-press-event',
                                  self._on_msg_textview_key_press_event)
        self.msg_textview.connect('paste-clipboard',
                                  self._on_paste_clipboard)

        self._ui.input_scrolled.add(self.msg_textview)

        self._ui.sendfile_button.set_tooltip_text(
            _('No File Transfer available'))
        self._ui.formattings_button.set_menu_model(get_format_menu())
        self._ui.encryption_menu_button.set_menu_model(get_encryption_menu())

        self.show_all()
        self._ui.connect_signals(self)

        self._connect_actions()

        app.plugin_manager.gui_extension_point(
            'message_actions_box', self, self._ui.action_box)

        self.register_events([
            ('message-sent', ged.GUI2, self._on_message_sent)
        ])

    def get_current_contact(self) -> ChatContactT:
        assert self._contact is not None
        return self._contact

    def get_seclabel(self) -> SecurityLabel | None:
        return self._security_label_selector.get_seclabel()

    def _connect_actions(self) -> None:
        actions = [
            'input-bold',
            'input-italic',
            'input-strike',
            'input-clear',
            'show-emoji-chooser',
            'quote',
            'mention',
            'reply',
            'correct-message',
        ]

        for action in actions:
            action = app.window.get_action(action)
            action.connect('activate', self._on_action)

        action = app.window.get_action('set-encryption')
        action.connect('change-state', self._change_encryption)

        action = app.window.get_action('send-file-jingle')
        action.connect('notify::enabled', self._on_send_file_enabled_changed)

        action = app.window.get_action('send-file-httpupload')
        action.connect('notify::enabled', self._on_send_file_enabled_changed)

    def _on_action(self,
                   action: Gio.SimpleAction,
                   param: GLib.Variant | None) -> int | None:

        if self._contact is None:
            return

        action_name = action.get_name()
        log.info('Activate action: %s', action_name)

        if not self.msg_textview.is_sensitive():
            log.info('Action dismissed, input is not enabled')
            return

        if action_name == 'input-clear':
            self._on_clear()

        elif action_name.startswith('input-'):
            self._on_format(action_name)

        elif action_name == 'show-emoji-chooser':
            self.msg_textview.emit('insert-emoji')
            self._ui.emoticons_button.set_active(False)

        elif action_name == 'quote':
            assert param
            self.msg_textview.insert_as_quote(param.get_string())

        elif action_name == 'reply':
            assert param
            pk = param.get_uint32()
            original_message = app.storage.archive.get_message_with_pk(pk)
            if original_message is None:
                return
            self._enable_reply_mode(original_message)

        elif action_name == 'mention':
            assert param
            self.msg_textview.mention_participant(param.get_string())

        elif action_name == 'correct-message':
            self.toggle_message_correction()

    def switch_contact(self, contact: ChatContactT) -> None:
        if self._client is not None:
            self._set_chatstate(False)
            self._client.disconnect_all_from_obj(self)

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._client = app.get_client(contact.account)
        self._client.connect_signal(
            'state-changed', self._on_client_state_changed)

        self._store_draft()
        self.disable_reply_mode()

        self._contact = contact

        if isinstance(self._contact, GroupchatContact):
            self._contact.multi_connect({
                'state-changed': self._on_muc_state_changed,
                'user-role-changed': self._on_muc_state_changed,
            })
        elif isinstance(self._contact, GroupchatParticipant):
            self._contact.multi_connect({
                'user-joined': self._on_user_state_changed,
                'user-left': self._on_user_state_changed,
                'room-joined': self._on_user_state_changed,
                'room-left': self._on_user_state_changed,
            })

        encryption = contact.settings.get('encryption')
        encryption_available = self._is_encryption_available(contact)
        if not encryption_available and encryption:
            # Disable encryption if chat was encrypted before, but due to
            # changed circumstances, encryption is not applicable anymore
            # (i.e. group chat configuration changed).
            contact.settings.set('encryption', '')
            encryption = ''

        action = app.window.get_action('set-encryption')
        action.set_state(GLib.Variant('s', encryption))
        self._update_encryption_button(
            encryption, is_available=encryption_available)
        self._update_encryption_details_button(encryption)
        self._update_send_file_button_tooltip()

        self._set_chatstate(True)

        self.msg_textview.switch_contact(contact)

        self._ui.edit_box.set_visible(self._is_correcting)
        self._restore_draft()

        self._security_label_selector.switch_contact(contact)

        self._update_message_input_state()

    def _store_draft(self) -> None:
        if self._contact is None:
            return

        text = self.msg_textview.get_text()

        reply_pk = None
        reply_data = self._reply_box.get_message_reply()
        if reply_data is not None:
            reply_pk = reply_data.pk

        draft = None
        if text or reply_pk is not None:
            draft = Draft(text, reply_pk)

        app.storage.drafts.set(self._contact, draft)

    def _restore_draft(self) -> None:
        assert self._contact is not None
        draft = app.storage.drafts.get(self._contact)
        if draft is None:
            return

        self.msg_textview.insert_text(draft.text)

        if draft.reply_pk is None:
            return

        message = app.storage.archive.get_message_with_pk(draft.reply_pk)
        if message is None:
            return

        self._enable_reply_mode(message)

    def clear(self) -> None:
        if self._client is not None and not self._client.is_destroyed():
            self._set_chatstate(False)
            self._client.disconnect_all_from_obj(self)

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = None
        self._client = None

    def get_text(self) -> str:
        return self.msg_textview.get_text()

    @property
    def _is_correcting(self) -> bool:
        if self._contact is None:
            return False

        return self._correcting[self._contact] is not None

    def _set_correcting(self, message_id: str | None) -> None:
        assert self._contact is not None
        self._correcting[self._contact] = message_id

    def _on_cancel_correction_clicked(self, _button: Gtk.Button) -> None:
        self._cancel_action()

    def insert_as_quote(self, text: str, *, clear: bool = False) -> None:
        if self._contact is None:
            return

        if not self.msg_textview.is_sensitive():
            return

        if clear:
            self.msg_textview.clear()
        self.msg_textview.insert_as_quote(text)

    def process_escape(self) -> bool:
        if not self._is_correcting and not self._reply_box.is_in_reply_mode:
            return False
        self._cancel_action()
        return True

    def _cancel_action(self) -> None:
        if self._is_correcting:
            self.toggle_message_correction()
        self.disable_reply_mode()

    def reset_state_after_send(self) -> None:
        self.msg_textview.clear()
        self._cancel_action()
        assert self._contact is not None
        app.storage.drafts.set(self._contact, None)

    def toggle_message_correction(self) -> None:
        assert self._contact is not None

        if self._is_correcting:
            self._set_correcting(None)
            self.msg_textview.end_correction()
            self._ui.edit_box.hide()
            return

        last_message_id = self._last_message_id.get(self._contact)
        if last_message_id is None:
            return

        assert self._contact is not None
        message = app.storage.archive.get_last_correctable_message(
            self._contact.account, self._contact.jid, last_message_id)
        if message is None or message.text is None:
            return

        self._set_correcting(last_message_id)

        if message.corrections:
            message = message.get_last_correction()

        self.msg_textview.start_correction(message)
        self._ui.edit_box.show()

        referenced_message = message.get_referenced_message()
        if referenced_message is not None:
            self._enable_reply_mode(referenced_message)

        #TODO: Set seclabel

    def get_last_message_id(self, contact: ChatContactT) -> str | None:
        return self._last_message_id.get(contact)

    def get_correction_id(self) -> str | None:
        assert self._contact is not None
        return self._correcting.get(self._contact)

    def _on_message_sent(self, event: MessageSent) -> None:
        message = event.message

        assert self._contact is not None

        if (message.oob and
                message.oob[0].url == message.text):
            # Don't allow to correct HTTP Upload file transfer URLs
            self._last_message_id[self._contact] = None
        else:
            self._last_message_id[self._contact] = message.id

    def _on_client_state_changed(self,
                                 _client: Client,
                                 _signal_name: str,
                                 state: SimpleClientState
                                 ) -> None:
        self._update_message_input_state()

    def _on_muc_state_changed(self, *args: Any) -> None:
        self._update_message_input_state()

    def _on_user_state_changed(self, *args: Any) -> None:
        self._update_message_input_state()

    def _update_message_input_state(self) -> None:
        assert self._client
        state = self._client.state.is_available

        self._ui.visitor_menu_button.hide()

        if not state:
            self._ui.state_box_label.set_text(
                _('You are offline. Go online to send messages…'))
            self._ui.state_box_image.set_from_icon_name(
                'network-offline-symbolic', Gtk.IconSize.BUTTON)

        if isinstance(self._contact, GroupchatContact):
            state = self._contact.is_joined
            if self._contact.is_joined:
                self_contact = self._contact.get_self()
                assert self_contact
                state = not self_contact.role.is_visitor

                if self_contact.role.is_visitor:
                    self._ui.visitor_menu_button.show()
                    self._ui.state_box_label.set_text(
                        _('You are a visitor.'))
                    self._ui.state_box_image.set_from_icon_name(
                        'feather-mic-off-symbolic', Gtk.IconSize.BUTTON)

        if isinstance(self._contact, GroupchatParticipant):
            state = self._contact.is_available
            self._ui.state_box_label.set_text(
                _('You can’t send private messages to contacts if they are offline.'))
            self._ui.state_box_image.set_from_icon_name(
                'network-offline-symbolic', Gtk.IconSize.BUTTON)

        self._ui.state_box.set_visible(not state)

        self._ui.emoticons_button.set_sensitive(state)
        self._ui.formattings_button.set_sensitive(state)
        self.msg_textview.set_sensitive(state)
        self.msg_textview.set_editable(state)

    def _set_chatstate(self, state: bool) -> None:
        assert self._client is not None
        if state:
            if self.msg_textview.has_text:
                self._client.get_module('Chatstate').set_chatstate(
                    self._contact, Chatstate.PAUSED)
            else:
                self._client.get_module('Chatstate').set_chatstate(
                    self._contact, Chatstate.ACTIVE)
        else:
            self._client.get_module('Chatstate').set_chatstate(
                self._contact, Chatstate.INACTIVE)

    def _change_encryption(self,
                           action: Gio.SimpleAction,
                           param: GLib.Variant
                           ) -> None:

        new_state = param.get_string()
        action_state = action.get_state()
        assert action_state is not None
        current_state = action_state.get_string()
        if current_state == new_state:
            return

        if new_state and new_state != 'OMEMO':
            plugin = app.plugin_manager.encryption_plugins.get(new_state)
            if plugin is None:
                # TODO: Add GUI error here
                return

            if not plugin.activate_encryption(app.window.get_control()):
                return

        contact = self.get_current_contact()
        contact.settings.set('encryption', new_state)
        action.set_state(GLib.Variant('s', new_state))

        self._update_encryption_button(new_state, is_available=True)
        self._update_encryption_details_button(new_state)

    def _update_encryption_button(
        self,
        encryption: str,
        *,
        is_available: bool
    ) -> None:

        contact = self.get_current_contact()

        if is_available:
            tooltip = _('Choose encryption')

            if encryption in ('OMEMO', 'OpenPGP', 'PGP'):
                icon_name = 'channel-secure-symbolic'
            else:
                icon_name = 'channel-insecure-symbolic'

        else:
            icon_name = 'channel-insecure-symbolic'
            if isinstance(contact, GroupchatContact):
                tooltip = _('This is a public group chat. '
                            'Encryption is not available.')
            elif isinstance(contact, GroupchatParticipant):
                tooltip = _('Encryption is not available in private chats')
            else:
                raise ValueError('Unexpected contact type: %s', type(contact))

        self._ui.encryption_menu_button.set_sensitive(is_available)
        self._ui.encryption_menu_button.set_tooltip_text(tooltip)
        self._ui.encryption_image.set_from_icon_name(
            icon_name, Gtk.IconSize.MENU)

    @staticmethod
    def _is_encryption_available(contact: ChatContactT) -> bool:
        if isinstance(contact, GroupchatContact):
            return contact.encryption_available
        elif isinstance(contact, GroupchatParticipant):
            return False
        return True

    def _update_encryption_details_button(self, encryption: str) -> None:
        encryption_state = {'visible': bool(encryption),
                            'enc_type': encryption,
                            'authenticated': False}

        if encryption:
            if encryption == 'OMEMO':
                encryption_state['authenticated'] = True
            else:
                # Only fire extension_point for plugins (i.e. not OMEMO)
                app.plugin_manager.extension_point(
                    f'encryption_state{encryption}',
                    app.window.get_control(),
                    encryption_state)

        visible, enc_type, authenticated = encryption_state.values()
        assert isinstance(visible, bool)

        if authenticated:
            authenticated_string = _('and authenticated')
            icon_name = 'security-high-symbolic'
        else:
            authenticated_string = _('and NOT authenticated')
            icon_name = 'security-low-symbolic'

        tooltip = _('%(type)s encryption is active %(authenticated)s.') % {
            'type': enc_type,
            'authenticated': authenticated_string}

        if isinstance(self._contact, GroupchatContact) and visible:
            visible = self._contact.encryption_available

        self._ui.encryption_details_button.set_visible(visible)
        self._ui.encryption_details_button.set_tooltip_text(tooltip)
        self._ui.encryption_details_image.set_from_icon_name(
            icon_name, Gtk.IconSize.MENU)

    def _on_encryption_details_clicked(self, _button: Gtk.Button) -> None:
        contact = self.get_current_contact()
        encryption = contact.settings.get('encryption')
        if encryption == 'OMEMO':
            if contact.is_groupchat:
                open_window('GroupchatDetails',
                            contact=contact,
                            page='encryption-omemo')
                return

            if isinstance(contact, BareContact) and contact.is_self:
                window = open_window('AccountsWindow')
                window.select_account(contact.account, page='encryption-omemo')
                return

            open_window('ContactInfo',
                        account=contact.account,
                        contact=contact,
                        page='encryption-omemo')
            return

        app.plugin_manager.extension_point(
            f'encryption_dialog{encryption}', app.window.get_control())

    def _on_format(self, name: str) -> None:
        name = name.removeprefix('input-')
        self.msg_textview.apply_formatting(name)

    def _on_clear(self) -> None:
        self.msg_textview.clear()

    def _on_send_file_enabled_changed(self,
                                      action: Gio.SimpleAction,
                                      _param: GObject.ParamSpec) -> None:

        self._update_send_file_button_tooltip()

    def _update_send_file_button_tooltip(self):
        httpupload = app.window.get_action_enabled('send-file-httpupload')
        jingle = app.window.get_action_enabled('send-file-jingle')

        if not httpupload and not jingle:
            tooltip_text = _('No File Transfer available')
            self._ui.sendfile_button.set_tooltip_text(tooltip_text)
            return

        if self._contact is None:
            return

        client = app.get_client(self._contact.account)

        tooltip_text = _('Send File…')
        if httpupload and not jingle:
            max_file_size = client.get_module('HTTPUpload').max_file_size
            if max_file_size is not None:
                if app.settings.get('use_kib_mib'):
                    units = GLib.FormatSizeFlags.IEC_UNITS
                else:
                    units = GLib.FormatSizeFlags.DEFAULT
                max_file_size = GLib.format_size_full(
                    int(max_file_size), units)
                tooltip_text = _('Send File (max. %s)…') % max_file_size

        self._ui.sendfile_button.set_tooltip_text(tooltip_text)

    def _on_buffer_changed(self, _message_input: MessageInputTextView) -> None:
        has_text = self.msg_textview.has_text
        send_message_action = app.window.get_action('send-message')
        send_message_action.set_enabled(has_text)

        assert self._contact is not None
        encryption_name = self._contact.settings.get('encryption')

        if has_text and encryption_name:
            app.plugin_manager.extension_point('typing' + encryption_name, self)

        assert self._contact
        client = app.get_client(self._contact.account)
        client.get_module('Chatstate').set_keyboard_activity(self._contact)
        if not has_text:
            client.get_module('Chatstate').set_chatstate_delayed(
                self._contact, Chatstate.ACTIVE)
            return

        client.get_module('Chatstate').set_chatstate(
            self._contact, Chatstate.COMPOSING)

    def _on_msg_textview_key_press_event(self,
                                         textview: MessageInputTextView,
                                         event: Gdk.EventKey
                                         ) -> bool:
        # pylint: disable=too-many-nested-blocks
        event_state = event.get_state()
        if event_state & Gdk.ModifierType.SHIFT_MASK:
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if event.keyval == Gdk.KEY_ISO_Left_Tab:
                    app.window.select_next_chat(
                        Direction.PREV, unread_first=True)
                    return True

        if event_state & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Tab:
                app.window.select_next_chat(Direction.NEXT, unread_first=True)
                return True

            if event.keyval == Gdk.KEY_z:
                self.msg_textview.undo()
                return True

            if event.keyval == Gdk.KEY_y:
                self.msg_textview.redo()
                return True

            if event.keyval == Gdk.KEY_Up:
                self.toggle_message_correction()
                return True

        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if event_state & Gdk.ModifierType.SHIFT_MASK:
                textview.insert_newline()
                return True

            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if not app.settings.get('send_on_ctrl_enter'):
                    textview.insert_newline()
                    return True
            else:
                if app.settings.get('send_on_ctrl_enter'):
                    textview.insert_newline()
                    return True

            assert self._contact is not None

            # Reset IMContext to clear preedit state
            self.msg_textview.reset_im_context()

            message = self.msg_textview.get_text()

            try:
                handled = app.commands.parse(self._contact.type_string, message)
            except CommandFailed:
                return True

            if handled:
                self.msg_textview.clear()
                return True

            if not app.account_is_available(self._contact.account):
                # we are not connected
                ErrorDialog(
                    _('No Connection Available'),
                    _('Your message can not be sent until you are connected.'))
                return True

            app.window.activate_action('send-message', None)
            return True

        return False

    def _on_request_voice_clicked(self, _button: Gtk.Button) -> None:
        self._ui.visitor_popover.popdown()
        app.window.activate_action('muc-request-voice', None)

    def _enable_reply_mode(self, original_message: mod.Message) -> None:
        assert self._contact is not None
        self._reply_box.enable_reply_mode(self._contact, original_message)
        self.msg_textview.grab_focus()

    def disable_reply_mode(self, *args: Any) -> None:
        self._reply_box.disable_reply_mode()

    def get_message_reply(self) -> ReplyData | None:
        message_reply = self._reply_box.get_message_reply()
        if message_reply is None:
            return None

        return message_reply

    def _on_paste_clipboard(self,
                            texview: MessageInputTextView
                            ) -> None:

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        uris = clipboard.wait_for_uris()
        if uris:
            app.window.activate_action('send-file', GLib.Variant('as', uris))
            # prevent TextView from pasting the URIs as text:
            texview.stop_emission_by_name('paste-clipboard')
            return

        log.info('No URIs pasted')

        image = clipboard.wait_for_image()
        if image is None:
            log.info('No image pasted')
            return

        temp_dir = Path(tempfile.gettempdir())
        image_path = temp_dir / f'{uuid.uuid4()}.png'

        try:
            success = image.savev(str(image_path), 'png', [], [])
            if not success:
                log.error('Could not process pasted image')
                return
        except GLib.Error as e:
            log.error('Error while trying to store pasted image: %s', e)
            return

        app.window.activate_action(
            'send-file', GLib.Variant('as', [image_path.as_uri()]))
