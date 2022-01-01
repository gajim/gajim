# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Nikos Kouremenos <kourem AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

from typing import ClassVar  # pylint: disable=unused-import
from typing import Type  # pylint: disable=unused-import
from typing import Optional

import time
import logging

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gdk

from nbxmpp import JID
from nbxmpp.const import Chatstate
from nbxmpp.modules.security_labels import Displaymarking
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import PEPEventType

from gajim.gui.call_widget import CallWidget
from gajim.gui.const import TARGET_TYPE_URI_LIST
from gajim.gui.const import ControlType
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.util import get_cursor
from gajim.gui.util import open_window

from gajim.command_system.implementation.hosts import ChatCommands
from gajim.command_system.framework import CommandHost  # pylint: disable=unused-import
from gajim.gui.controls.base import BaseControl

from ..menus import get_encryption_menu
from ..menus import get_singlechat_menu

log = logging.getLogger('gajim.gui.controls.chat')


class ChatControl(BaseControl):
    """
    A control for standard 1-1 chat
    """
    _type = ControlType.CHAT

    # Set a command host to bound to. Every command given through a chat will be
    # processed with this command host.
    COMMAND_HOST = ChatCommands  # type: ClassVar[Type[CommandHost]]

    def __init__(self, account: str, jid: JID) -> None:
        BaseControl.__init__(self,
                             'chat_control',
                             account,
                             jid)

        self.sendmessage: bool = True

        # XEP-0308 Message Correction
        self.correcting: bool = False
        self.last_sent_msg: Optional[str] = None

        self.toggle_emoticons()

        if self._type == ControlType.CHAT:
            self._client.connect_signal('state-changed',
                                        self._on_client_state_changed)

        if not app.settings.get('hide_chat_banner'):
            self.xml.banner_eventbox.set_no_show_all(False)

        self.xml.sendfile_button.set_action_name(
            f'win.send-file-{self.control_id}')

        self._call_widget = CallWidget(self.account, self.contact)
        self._call_widget.connect('incoming-call', self._add_incoming_call)
        self._call_widget.connect('call-ended', self._on_call_ended)
        self.xml.paned1.add2(self._call_widget)

        self.conversation_view.connect('accept-call', self._on_accept_call)
        self.conversation_view.connect('decline-call', self._on_decline_call)

        # Menu for the HeaderBar
        self.control_menu = get_singlechat_menu(
            self.control_id, self.account, self.contact.jid, self._type)

        # Settings menu
        self.xml.settings_menu.set_menu_model(self.control_menu)

        self.update_toolbar()
        self.update_all_pep_types()
        self._update_avatar()

        # Hook up signals
        widget = self.xml.location_eventbox
        id_ = widget.connect('button-release-event',
                             self.on_location_eventbox_button_release_event)
        self.handlers[id_] = widget
        id_ = widget.connect('enter-notify-event',
                             self.on_location_eventbox_enter_notify_event)
        self.handlers[id_] = widget
        id_ = widget.connect('leave-notify-event',
                             self.on_location_eventbox_leave_notify_event)
        self.handlers[id_] = widget

        self.setup_seclabel()
        self.add_actions()
        self.update_ui()
        self.set_lock_image()

        self.xml.encryption_menu.set_menu_model(get_encryption_menu(
            self.control_id, self._type, self.account == 'Local'))
        self.set_encryption_menu_icon()
        self.msg_textview.grab_focus()

        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        app.plugin_manager.gui_extension_point('chat_control', self)
        self.update_actions()

    def _connect_contact_signals(self) -> None:
        self.contact.multi_connect({
            'presence-update': self._on_presence_update,
            'chatstate-update': self._on_chatstate_update,
            'nickname-update': self._on_nickname_update,
            'avatar-update': self._on_avatar_update,
            'caps-update': self._on_caps_update,
        })

    @property
    def jid(self) -> JID:
        return self.contact.jid

    def add_actions(self) -> None:
        super().add_actions()
        actions = [
            ('invite-contacts-', self._on_invite_contacts),
            ('add-to-roster-', self._on_add_to_roster),
            ('block-contact-', self._on_block_contact),
            ('information-', self._on_information),
            ('start-call-', self._on_start_call),
        ]

        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(action_name + self.control_id, None)
            act.connect('activate', func)
            app.window.add_action(act)

        chatstate = self.contact.settings.get('send_chatstate')

        act = Gio.SimpleAction.new_stateful(
            'send-chatstate-' + self.control_id,
            GLib.VariantType.new("s"),
            GLib.Variant("s", chatstate))
        act.connect('change-state', self._on_send_chatstate)
        app.window.add_action(act)

        marker = self.contact.settings.get('send_marker')

        act = Gio.SimpleAction.new_stateful(
            f'send-marker-{self.control_id}',
            None,
            GLib.Variant.new_boolean(marker))
        act.connect('change-state', self._on_send_marker)
        app.window.add_action(act)

    def update_actions(self) -> None:
        online = app.account_is_connected(self.account)

        if self.type.is_chat:
            self._get_action('add-to-roster-').set_enabled(
                not self.contact.is_in_roster)

        # Block contact
        self._get_action('block-contact-').set_enabled(
            online and self._client.get_module('Blocking').supported)

        # Jingle AV
        self._call_widget.detect_av()
        audio_available = self._call_widget.get_jingle_available('audio')
        video_available = self._call_widget.get_jingle_available('video')
        self._get_action('start-call-').set_enabled(
            online and (audio_available or video_available))

        # Send message
        has_text = self.msg_textview.has_text()
        self._get_action('send-message-').set_enabled(online and has_text)

        # Send file (HTTP File Upload)
        httpupload = self._get_action('send-file-httpupload-')
        httpupload.set_enabled(online and
                               self._client.get_module('HTTPUpload').available)

        # Send file (Jingle)
        jingle_support = self.contact.supports(Namespace.JINGLE_FILE_TRANSFER_5)
        jingle_conditions = bool(jingle_support and
                                 self.contact.is_available and
                                 not self.contact.is_pm_contact)
        jingle = self._get_action('send-file-jingle-')
        jingle.set_enabled(online and jingle_conditions)

        # Send file
        self._get_action('send-file-').set_enabled(jingle.get_enabled() or
                                                   httpupload.get_enabled())

        # Set File Transfer Button tooltip
        if online and (httpupload.get_enabled() or jingle.get_enabled()):
            tooltip_text = _('Send File…')
        else:
            tooltip_text = _('No File Transfer available')
        self.xml.sendfile_button.set_tooltip_text(tooltip_text)

        # Chat markers
        state = GLib.Variant.new_boolean(
            self.contact.settings.get('send_marker'))
        self._get_action('send-marker-').change_state(state)

        # Convert to GC
        if app.settings.get_account_setting(self.account, 'is_zeroconf'):
            self._get_action('invite-contacts-').set_enabled(False)
        else:
            enabled = self.contact.supports(Namespace.MUC) and online
            self._get_action('invite-contacts-').set_enabled(enabled)

        # Information
        self._get_action('information-').set_enabled(online)

    def remove_actions(self) -> None:
        super().remove_actions()
        actions = [
            'invite-contacts-',
            'add-to-roster-',
            'block-contact-',
            'information-',
            'start-call-',
            'send-chatstate-',
            'send-marker-',
        ]
        for action in actions:
            app.window.remove_action(f'{action}{self.control_id}')

    def focus(self) -> None:
        self.msg_textview.grab_focus()

    def delegate_action(self, action: str) -> int:
        res = super().delegate_action(action)
        if res == Gdk.EVENT_STOP:
            return res

        if action == 'show-contact-info':
            self._get_action('information-').activate()
            return Gdk.EVENT_STOP

        if action == 'send-file':
            self._get_action('send-file-').activate()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_add_to_roster(self, _action, _param):
        open_window('AddContact', account=self.account,
                    jid=self.contact.jid)

    def _on_block_contact(self, _action, _param):
        app.window.block_contact(self.account, self.contact.jid)

    def _on_information(self, _action, _param):
        app.window.contact_info(self.account, self.contact.jid)

    def _on_invite_contacts(self, _action, _param):
        open_window('AdhocMUC', account=self.account, contact=self.contact)

    def _on_send_chatstate(self, action, param):
        action.set_state(param)
        self.contact.settings.set('send_chatstate', param.get_string())

    def _on_send_marker(self, action, param):
        action.set_state(param)
        self.contact.settings.set('send_marker', param.get_boolean())

    def update_all_pep_types(self) -> None:
        self._update_pep(PEPEventType.LOCATION)
        self._update_pep(PEPEventType.TUNE)

    def _update_pep(self, type_: PEPEventType) -> None:
        return
        # TODO
        # image = self._get_pep_widget(type_)
        # data = self.contact.pep.get(type_)
        # if data is None:
        #     image.hide()
        #     return

        # if type_ == PEPEventType.TUNE:
        #     icon = 'audio-x-generic'
        #     formated_text = format_tune(*data)
        # elif type_ == PEPEventType.LOCATION:
        #     icon = 'applications-internet'
        #     formated_text = format_location(data)

        # image.set_from_icon_name(icon, Gtk.IconSize.MENU)
        # image.set_tooltip_markup(formated_text)
        # image.show()

    def _get_pep_widget(self, type_: PEPEventType) -> Optional[Gtk.Image]:
        if type_ == PEPEventType.TUNE:
            return self.xml.tune_image
        if type_ == PEPEventType.LOCATION:
            return self.xml.location_image
        return None

    def _on_tune_received(self, _event):
        self._update_pep(PEPEventType.TUNE)

    def _on_location_received(self, _event):
        self._update_pep(PEPEventType.LOCATION)

    def _on_nickname_received(self, _event):
        self.update_ui()

    def _on_update_client_info(self, event):
        # TODO: Test if this works
        contact = self._client.get_module('Contacts').get_contact(event.jid)
        if contact is None:
            return
        self.xml.phone_image.set_visible(contact.uses_phone)

    def _on_chatstate_update(self, *args):
        self.draw_banner_text()

    def _on_nickname_update(self, _contact, _signal_name):
        self.draw_banner_text()

    def _on_presence_update(self, _contact, _signal_name):
        self._update_avatar()

    def _on_caps_update(self, _contact, _signal_name):
        self.update_ui()

    def _on_mam_message_received(self, event):
        if event.properties.is_muc_pm:
            if not event.properties.jid == self.contact.jid:
                return
        else:
            if not event.properties.jid.bare_match(self.contact.jid):
                return

        kind = 'incoming'
        if event.kind == KindConstant.CHAT_MSG_SENT:
            kind = 'outgoing'

        self.add_message(event.msgtxt,
                         kind,
                         tim=event.properties.mam.timestamp,
                         message_id=event.properties.id,
                         stanza_id=event.stanza_id,
                         additional_data=event.additional_data,
                         notify=False)

    def _on_message_received(self, event):
        if not event.msgtxt:
            return

        kind = 'incoming'
        if event.properties.is_sent_carbon:
            kind = 'outgoing'

        self.add_message(event.msgtxt,
                         kind,
                         tim=event.properties.timestamp,
                         displaymarking=event.displaymarking,
                         msg_log_id=event.msg_log_id,
                         message_id=event.properties.id,
                         stanza_id=event.stanza_id,
                         additional_data=event.additional_data)

        if kind == 'outgoing':
            self.conversation_view.set_read_marker(event.properties.id)

    def _on_message_error(self, event):
        self.conversation_view.show_error(event.message_id, event.error)

    def _on_message_sent(self, event):
        if not event.message:
            return

        if event.correct_id is None:
            oob_url = event.additional_data.get_value('gajim', 'oob_url')
            if oob_url == event.message:
                self.last_sent_msg = None
            else:
                self.last_sent_msg = event.message_id

        message_id = event.message_id

        if event.label:
            displaymarking = event.label.displaymarking
        else:
            displaymarking = None
        if self.correcting:
            self.correcting = False
            self.msg_textview.get_style_context().remove_class(
                'gajim-msg-correcting')

        if event.correct_id:
            self.conversation_view.correct_message(
                event.correct_id, event.message)
            return

        self.add_message(event.message,
                         'outgoing',
                         tim=event.timestamp,
                         displaymarking=displaymarking,
                         message_id=message_id,
                         additional_data=event.additional_data)

    def _on_receipt_received(self, event):
        self.conversation_view.show_receipt(event.receipt_id)

    def _on_displayed_received(self, event):
        self.conversation_view.set_read_marker(event.marker_id)

    def _nec_ping(self, event):
        if self.contact != event.contact:
            return
        if event.name == 'ping-sent':
            self.add_info_message(_('Ping?'))
        elif event.name == 'ping-reply':
            self.add_info_message(
                _('Pong! (%s seconds)') % event.seconds)
        elif event.name == 'ping-error':
            self.add_info_message(event.error)

    # Jingle AV calls
    def _on_start_call(self,
                       _action: Gio.SimpleAction,
                       _param: Optional[GLib.Variant]
                       ) -> None:
        self._call_widget.start_call()

    def _process_jingle_av_event(self, event):
        self._call_widget.process_event(event)

    def _on_accept_call(self, _view, session):
        self._call_widget.accept_call(session)

    def _on_decline_call(self, _view, session):
        self._call_widget.decline_call(session)

    def _on_call_ended(self, _call_widget):
        self.conversation_view.update_call_rows()

    def _add_incoming_call(self, _call_widget, event):
        self.add_call_message(event)

    def on_location_eventbox_button_release_event(self, _widget, _event):
        return
        # TODO
        # if 'geoloc' in self.contact.pep:
        #     location = self.contact.pep['geoloc'].data
        #     if 'lat' in location and 'lon' in location:
        #         uri = geo_provider_from_location(location['lat'],
        #                                          location['lon'])
        #         open_uri(uri)

    def on_location_eventbox_leave_notify_event(self, _widget, _event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = get_cursor('default')
        app.window.get_window().set_cursor(cursor)

    def on_location_eventbox_enter_notify_event(self, _widget, _event):
        cursor = get_cursor('pointer')
        app.window.get_window().set_cursor(cursor)

    def update_ui(self) -> None:
        # The name banner is drawn here
        BaseControl.update_ui(self)
        self.update_toolbar()
        self._update_avatar()
        self.update_actions()

    def draw_banner_text(self) -> None:
        """
        Draws the chat banner's text (e.g. name, chat state) in the top of the
        chat window
        """
        contact = self.contact
        name = contact.name

        if self.jid == self._client.get_own_jid().bare:
            name = _('Note to myself')

        if self._type.is_privatechat:
            name = f'{name} ({self.room_name})'

        chatstate = self.contact.chatstate
        if chatstate is not None:
            chatstate = chatstate.value

        if app.settings.get('show_chatstate_in_banner'):
            chatstate = helpers.get_uf_chatstate(chatstate)

            label_text = f'<span>{name}</span>' \
                         f'<span size="x-small" weight="light">' \
                         f' {chatstate}</span>'
            label_tooltip = f'{name} {chatstate}'
        else:
            label_text = f'<span>{name}</span>'
            label_tooltip = name

        status_text = ''
        self.xml.banner_label.hide()
        self.xml.banner_label.set_no_show_all(True)
        self.xml.banner_label.set_markup(status_text)

        self.xml.banner_name_label.set_markup(label_text)
        self.xml.banner_name_label.set_tooltip_text(label_tooltip)

    def send_message(self,
                     message: str,
                     process_commands: bool = True,
                     attention: bool = False
                     ) -> None:
        """
        Send a message to contact
        """

        if self.encryption:
            self.sendmessage = True
            app.plugin_manager.extension_point('send_message' + self.encryption,
                                               self)
            if not self.sendmessage:
                return

        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return

        BaseControl.send_message(self,
                                 message,
                                 type_='chat',
                                 process_commands=process_commands,
                                 attention=attention)

    def add_message(self,
                    text: str,
                    kind: str,
                    tim: Optional[float] = None,
                    displaymarking: Optional[Displaymarking] = None,
                    msg_log_id: Optional[str] = None,
                    stanza_id: Optional[str] = None,
                    message_id: Optional[str] = None,
                    additional_data: Optional[AdditionalDataDict] = None,
                    notify: bool = True
                    ) -> None:

        if additional_data is None:
            additional_data = AdditionalDataDict()

        if kind == 'incoming':
            name = self.contact.name
        else:
            name = self.get_our_nick()

        BaseControl.add_message(self,
                                text,
                                kind,
                                name,
                                tim,
                                notify,
                                displaymarking=displaymarking,
                                msg_log_id=msg_log_id,
                                message_id=message_id,
                                stanza_id=stanza_id,
                                additional_data=additional_data)

    def shutdown(self) -> None:
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        app.plugin_manager.remove_gui_extension_point('chat_control', self)

        self.remove_actions()

        # Send 'gone' chatstate
        self._client.get_module('Chatstate').set_chatstate(
            self.contact, Chatstate.GONE)

        super(ChatControl, self).shutdown()
        app.check_finalize(self)

    def allow_shutdown(self, _method, on_yes, on_no):
        row = self.conversation_view.get_last_message_row()
        if row is None:
            on_yes(self)
            return

        if time.time() - row.timestamp < 2:
            # Under 2 seconds since last message
            no_log_for = app.settings.get_account_setting(
                self.account, 'no_log_for').split()
            more = ''
            if self.contact.jid in no_log_for:
                more = _('Note: Chat history is disabled for this contact.')
            if self.account in no_log_for:
                more = _('Note: Chat history is disabled for this account.')
            text = _('You just received a new message from %s.\n'
                     'Do you want to close this tab?') % self.contact.name
            if more:
                text += '\n' + more

            ConfirmationDialog(
                _('Close'),
                _('New Message'),
                text,
                [DialogButton.make('Cancel',
                                   callback=lambda: on_no(self)),
                 DialogButton.make('Remove',
                                   text=_('_Close'),
                                   callback=lambda: on_yes(self))],
                transient_for=app.window).show()
            return
        on_yes(self)

    def _on_avatar_update(self, _contact, _signal_name):
        self._update_avatar()

    def _update_avatar(self) -> None:
        scale = app.window.get_scale_factor()
        surface = self.contact.get_avatar(AvatarSize.CHAT, scale)
        self.xml.avatar_image.set_from_surface(surface)

    def _on_drag_data_received(self, _widget, _context, _x_coord, _y_coord,
                               selection, target_type, _timestamp):
        if not selection.get_data():
            return

        log.debug('Drop received: %s, %s', selection.get_data(), target_type)

        # TODO: Contact drag and drop for AdHocMUC
        if target_type == TARGET_TYPE_URI_LIST:
            # File drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(selection)

    def _on_client_state_changed(self, _client, _signal_name, state):
        self.msg_textview.set_sensitive(state.is_connected)
        self.msg_textview.set_editable(state.is_connected)

        self._update_avatar()
        self.update_toolbar()
        self.draw_banner()
        self.update_actions()

    def _on_presence_received(self, event):
        uf_show = helpers.get_uf_show(event.show)
        name = self.contact.name

        self.update_ui()

        if not app.settings.get('print_status_in_chats'):
            return

        status = f'- {event.status}' if event.status else ''
        status_line = _('%(name)s is now %(show)s %(status)s') % {
            'name': name, 'show': uf_show, 'status': status}
        self.add_info_message(status_line)
