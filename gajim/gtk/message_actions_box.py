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

import os
import sys
import tempfile
import logging
import uuid

from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import GObject

from nbxmpp.const import Chatstate
from nbxmpp.modules.security_labels import SecurityLabel

from gajim.common import app
from gajim.common.commands import CommandFailed
from gajim.common.i18n import _
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.const import Direction
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.types import ChatContactT
from gajim.gui.security_label_selector import SecurityLabelSelector

from .builder import get_builder
from .dialogs import DialogButton
from .dialogs import ErrorDialog
from .dialogs import PastePreviewDialog
from .emoji_chooser import emoji_chooser
from .menus import get_encryption_menu
from .menus import get_format_menu
from .menus import get_groupchat_menu
from .menus import get_private_chat_menu
from .menus import get_self_contact_menu
from .menus import get_singlechat_menu
from .message_input import MessageInputTextView

log = logging.getLogger('gajim.gui.messageactionsbox')


class MessageActionsBox(Gtk.Grid):
    def __init__(self) -> None:
        Gtk.Grid.__init__(self)

        self._client: Optional[Client] = None
        self._contact: Optional[ChatContactT] = None

        self._ui = get_builder('message_actions_box.ui')
        self.get_style_context().add_class('message-actions-box')

        self.attach(self._ui.box, 0, 0, 1, 1)

        # For undo
        self.space_pressed = False

        self._ui.send_message_button.set_visible(
            app.settings.get('show_send_message_button'))
        app.settings.bind_signal('show_send_message_button',
                                 self._ui.send_message_button,
                                 'set_visible')

        self._security_label_selector = SecurityLabelSelector()
        self._ui.box.pack_start(self._security_label_selector, False, True, 0)

        self.msg_textview = MessageInputTextView()
        self.msg_textview.get_buffer().connect('changed',
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

        self._ui.quick_invite_button.set_action_name('win.muc-invite')

        self._init_emoticon_popover()

        self.show_all()
        self._ui.connect_signals(self)

        self._connect_actions()

        app.plugin_manager.gui_extension_point(
            'message_actions_box', self, self._ui.box)

    def get_current_contact(self) -> ChatContactT:
        assert self._contact is not None
        return self._contact

    def get_seclabel(self) -> Optional[SecurityLabel]:
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
                   param: Optional[GLib.Variant]) -> Optional[int]:

        if self._contact is None:
            return

        action_name = action.get_name()
        log.info('Activate action: %s', action_name)

        if action_name == 'input-clear':
            self._on_clear()

        elif action_name.startswith('input-'):
            self._on_format(action_name)

        elif action_name == 'show-emoji-chooser':
            self._on_show_emoji_chooser()

        elif action_name == 'quote':
            assert param
            self.msg_textview.insert_as_quote(param.get_string())

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

        self._contact = contact

        if isinstance(self._contact, GroupchatContact):
            self._ui.quick_invite_button.show()
            self._contact.multi_connect({
                'state-changed': self._on_muc_state_changed,
                'user-role-changed': self._on_muc_state_changed,
            })
        elif isinstance(self._contact, GroupchatParticipant):
            self._ui.quick_invite_button.hide()
            self._contact.multi_connect({
                'user-joined': self._on_user_state_changed,
                'user-left': self._on_user_state_changed,
                'room-joined': self._on_user_state_changed,
                'room-left': self._on_user_state_changed,
            })
        else:
            self._ui.quick_invite_button.hide()

        self._set_settings_menu(contact)

        self._update_encryption_button()
        self._update_encryption_details_button()

        self._set_chatstate(True)

        self.msg_textview.switch_contact(contact)
        self._security_label_selector.switch_contact(contact)

        self._update_message_input_state()

    def clear(self) -> None:
        if self._client is not None and not self._client.is_destroyed():
            self._set_chatstate(False)
            self._client.disconnect_all_from_obj(self)

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = None
        self._client = None

    @property
    def is_correcting(self) -> bool:
        return self.msg_textview.is_correcting

    def toggle_message_correction(self) -> None:
        self.msg_textview.toggle_message_correction()

    def try_message_correction(self, message: str) -> Optional[str]:
        return self.msg_textview.try_message_correction(message)

    def get_last_message_id(self, contact: ChatContactT) -> Optional[str]:
        return self.msg_textview.get_last_message_id(contact)

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

        if isinstance(self._contact, GroupchatContact):
            state = self._contact.is_joined
            if self._contact.is_joined:
                self_contact = self._contact.get_self()
                assert self_contact
                state = not self_contact.role.is_visitor

        if isinstance(self._contact, GroupchatParticipant):
            state = self._contact.is_available

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

        if new_state:
            plugin = app.plugin_manager.encryption_plugins.get(new_state)
            if plugin is None:
                # TODO: Add GUI error here
                return

            if not plugin.activate_encryption(app.window.get_control()):
                return

        contact = self.get_current_contact()
        contact.settings.set('encryption', new_state)

        self._update_encryption_button()
        self._update_encryption_details_button()

    def _update_encryption_button(self) -> None:
        contact = self.get_current_contact()
        state = contact.settings.get('encryption')

        action = app.window.get_action('set-encryption')
        action.set_state(GLib.Variant('s', state))

        sensitive = True
        tooltip = _('Choose encryption')

        if state in ('OMEMO', 'OpenPGP', 'PGP'):
            icon_name = 'channel-secure-symbolic'
        else:
            icon_name = 'channel-insecure-symbolic'

        if isinstance(self._contact, GroupchatContact):
            if not self._contact.encryption_available:
                sensitive = False
                tooltip = _('This is a public group chat. '
                            'Encryption is not available.')
                icon_name = 'channel-insecure-symbolic'

        self._ui.encryption_menu_button.set_sensitive(sensitive)
        self._ui.encryption_menu_button.set_tooltip_text(tooltip)
        self._ui.encryption_image.set_from_icon_name(
            icon_name, Gtk.IconSize.MENU)

    def _update_encryption_details_button(self) -> None:
        contact = self.get_current_contact()
        state = contact.settings.get('encryption')

        encryption_state = {'visible': bool(state),
                            'enc_type': state,
                            'authenticated': False}

        if state:
            app.plugin_manager.extension_point(
                f'encryption_state{state}',
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
        app.plugin_manager.extension_point(
            f'encryption_dialog{encryption}', app.window.get_control())

    def _set_settings_menu(self, contact: ChatContactT) -> None:
        if isinstance(contact, GroupchatContact):
            menu = get_groupchat_menu(contact)
        elif isinstance(contact, GroupchatParticipant):
            menu = get_private_chat_menu(contact)
        elif contact.is_self:
            menu = get_self_contact_menu(contact)
        else:
            menu = get_singlechat_menu(contact)
        self._ui.settings_menu.set_menu_model(menu)

    def _init_emoticon_popover(self) -> None:
        if not app.settings.get('emoticons_theme'):
            return

        if sys.platform == 'darwin':
            emoji_chooser.text_widget = self.msg_textview
            self._ui.emoticons_button.set_popover(emoji_chooser)
            return

        self._ui.emoticons_button.set_sensitive(True)
        self._ui.emoticons_button.connect('clicked',
                                          self._on_emoticon_button_clicked)

    def toggle_emoticons(self) -> None:
        if app.settings.get('emoticons_theme'):
            self._ui.emoticons_button.set_no_show_all(False)
            self._ui.emoticons_button.show()
        else:
            self._ui.emoticons_button.set_no_show_all(True)
            self._ui.emoticons_button.hide()

    def _on_emoticon_button_clicked(self, _widget: Gtk.Button) -> None:
        self.msg_textview.emit('insert-emoji')
        self._ui.emoticons_button.set_active(False)

    def _on_format(self, name: str) -> None:
        name = name.removeprefix('input-')
        self.msg_textview.apply_formatting(name)

    def _on_clear(self) -> None:
        self.msg_textview.clear()

    def _on_show_emoji_chooser(self) -> None:
        if sys.platform == 'darwin':
            popover = self._ui.emoticons_button.get_popover()
            assert popover
            popover.show()
        else:
            self.msg_textview.emit('insert-emoji')

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
                max_file_size = GLib.format_size_full(max_file_size, units)
                tooltip_text = _('Send File (max. %s)…') % max_file_size

        self._ui.sendfile_button.set_tooltip_text(tooltip_text)

    def _on_buffer_changed(self, textbuffer: Gtk.TextBuffer) -> None:
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
        if event.keyval == Gdk.KEY_space:
            self.space_pressed = True

        elif ((self.space_pressed or self.msg_textview.undo_pressed) and
                event.keyval not in (Gdk.KEY_Control_L, Gdk.KEY_Control_R) and
                not (event.keyval == Gdk.KEY_z and
                     event.get_state() & Gdk.ModifierType.CONTROL_MASK)):
            # If the space key has been pressed and now it hasn't,
            # we save the buffer into the undo list. But be careful we're not
            # pressing Control again (as in ctrl+z)
            _buffer = textview.get_buffer()
            start_iter, end_iter = _buffer.get_bounds()
            self.msg_textview.save_undo(_buffer.get_text(start_iter,
                                                         end_iter,
                                                         True))
            self.space_pressed = False

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

            message = self.msg_textview.get_text()
            if (message.startswith('/') and
                    not message.startswith('//') and
                    not message.startswith('/me ')):
                try:
                    app.commands.parse(self._contact.type_string, message)
                except CommandFailed:
                    pass
                else:
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

    def _on_paste_clipboard(self,
                            _texview: MessageInputTextView
                            ) -> None:

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        image = clipboard.wait_for_image()
        if image is None:
            return

        PastePreviewDialog(
            _('Paste Image'),
            _('You are trying to paste an image'),
            _('Are you sure you want to paste your '
              "clipboard's image into the chat window?"),
            _('_Do not ask me again'),
            image,
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Paste'),
                               callback=self._paste_event_confirmed,
                               args=[image])]).show()

    def _paste_event_confirmed(self,
                               image: GdkPixbuf.Pixbuf
                               ) -> None:

        dir_ = tempfile.gettempdir()
        path = os.path.join(dir_, f'{uuid.uuid4()}.png')
        if image is None:
            log.error('Could not process pasted image')
            return

        image.savev(path, 'png', [], [])

        assert self._contact is not None
        app.interface.start_file_transfer(self._contact, path)
