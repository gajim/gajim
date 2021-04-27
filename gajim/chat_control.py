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
from typing import Optional  # pylint: disable=unused-import

import os
import time
import logging

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import Gdk

from nbxmpp.namespaces import Namespace
from nbxmpp.const import Chatstate

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import open_uri
from gajim.common.helpers import geo_provider_from_location
from gajim.common.helpers import open_file
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import PEPEventType
from gajim.common.const import JingleState

from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import dialogs

from gajim.gui.gstreamer import create_gtk_widget
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.add_contact import AddNewContactWindow
from gajim.gui.util import get_cursor
from gajim.gui.util import format_mood
from gajim.gui.util import format_activity
from gajim.gui.util import format_tune
from gajim.gui.util import format_location
from gajim.gui.util import get_activity_icon_name
from gajim.gui.const import ControlType

from gajim.command_system.implementation.hosts import ChatCommands
from gajim.command_system.framework import CommandHost  # pylint: disable=unused-import
from gajim.chat_control_base import ChatControlBase

log = logging.getLogger('gajim.chat_control')


class JingleObject:
    __slots__ = ('sid', 'state', 'available', 'update')

    def __init__(self, state, update):
        self.sid = None
        self.state = state
        self.available = False
        self.update = update


################################################################################
class ChatControl(ChatControlBase):
    """
    A control for standard 1-1 chat
    """
    _type = ControlType.CHAT
    old_msg_kind = None # last kind of the printed message

    # Set a command host to bound to. Every command given through a chat will be
    # processed with this command host.
    COMMAND_HOST = ChatCommands  # type: ClassVar[Type[CommandHost]]

    def __init__(self, account, jid):
        ChatControlBase.__init__(self,
                                 'chat_control',
                                 account,
                                 jid)

        self.last_recv_message_id = None
        self.last_recv_message_marks = None
        self.last_message_timestamp = None

        self.toggle_emoticons()

        if self._type == ControlType.CHAT:
            self._client.connect_signal('state-changed',
                                        self._on_client_state_changed)

        if not app.settings.get('hide_chat_banner'):
            self.xml.banner_eventbox.set_no_show_all(False)

        self.xml.sendfile_button.set_action_name(
            'win.send-file-%s' % self.control_id)

        # Menu for the HeaderBar
        self.control_menu = gui_menu_builder.get_singlechat_menu(
            self.control_id, self.account, self.contact.jid, self._type)

        # Settings menu
        self.xml.settings_menu.set_menu_model(self.control_menu)

        self.jingle = {
            'audio': JingleObject(
                JingleState.NULL,
                self.update_audio),
            'video': JingleObject(
                JingleState.NULL,
                self.update_video),
        }
        self._video_widget_other = None
        self._video_widget_self = None

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

        for key in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'):
            widget = self.xml.get_object(key + '_button')
            id_ = widget.connect('pressed', self.on_num_button_pressed, key)
            self.handlers[id_] = widget
            id_ = widget.connect('released', self.on_num_button_released)
            self.handlers[id_] = widget

        widget = self.xml.mic_hscale
        id_ = widget.connect('value_changed', self.on_mic_hscale_value_changed)
        self.handlers[id_] = widget

        widget = self.xml.sound_hscale
        id_ = widget.connect('value_changed',
                             self.on_sound_hscale_value_changed)
        self.handlers[id_] = widget

        self.info_bar = Gtk.InfoBar()
        content_area = self.info_bar.get_content_area()
        self.info_bar_label = Gtk.Label()
        self.info_bar_label.set_use_markup(True)
        self.info_bar_label.set_halign(Gtk.Align.START)
        self.info_bar_label.set_valign(Gtk.Align.START)
        self.info_bar_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_area.add(self.info_bar_label)
        self.info_bar.set_no_show_all(True)

        self.xml.textview_box.pack_start(self.info_bar, False, True, 5)
        self.xml.textview_box.reorder_child(self.info_bar, 1)

        # List of waiting infobar messages
        self.info_bar_queue = []

        self.setup_seclabel()
        self.add_actions()
        self.update_ui()
        self.set_lock_image()

        self.xml.encryption_menu.set_menu_model(
            gui_menu_builder.get_encryption_menu(
                self.control_id, self._type, self.account == 'Local'))
        self.set_encryption_menu_icon()
        self.msg_textview.grab_focus()

        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        app.plugin_manager.gui_extension_point('chat_control', self)
        self.update_actions()

    def _connect_contact_signals(self):
        self.contact.multi_connect({
            'presence-update': self._on_presence_update,
            'chatstate-update': self._on_chatstate_update,
            'nickname-update': self._on_nickname_update,
            'avatar-update': self._on_avatar_update,
        })

    @property
    def jid(self):
        return self.contact.jid

    def add_actions(self):
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

    def update_actions(self):
        online = app.account_is_connected(self.account)

        if self.type.is_chat:
            self._get_action('add-to-roster-').set_enabled(
                not self.contact.is_in_roster)

        # Block contact
        self._get_action('block-contact-').set_enabled(
            online and self._client.get_module('Blocking').supported)

        # Jingle AV detection
        if (self.contact.supports(Namespace.JINGLE_ICE_UDP) and
                app.is_installed('FARSTREAM') and self.contact.jid.resource):
            self.jingle['audio'].available = self.contact.supports(
                Namespace.JINGLE_RTP_AUDIO)
            self.jingle['video'].available = self.contact.supports(
                Namespace.JINGLE_RTP_VIDEO)
        else:
            if (self.jingle['audio'].available or
                    self.jingle['video'].available):
                self.stop_jingle()
            self.jingle['audio'].available = False
            self.jingle['video'].available = False

        self._get_action(f'start-call-').set_enabled(
            online and (self.jingle['audio'].available or
                        self.jingle['video'].available))

        # Send message
        has_text = self.msg_textview.has_text()
        self._get_action('send-message-').set_enabled(online and has_text)

        # Send file (HTTP File Upload)
        httpupload = self._get_action('send-file-httpupload-')
        httpupload.set_enabled(online and
                               self._client.get_module('HTTPUpload').available)

        # Send file (Jingle)
        jingle_support = self.contact.supports(Namespace.JINGLE_FILE_TRANSFER_5)
        jingle_conditions = jingle_support and self.contact.is_available
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

    def remove_actions(self):
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

    def focus(self):
        self.msg_textview.grab_focus()

    def delegate_action(self, action):
        res = super().delegate_action(action)
        if res == Gdk.EVENT_STOP:
            return res

        if action == 'show-contact-info':
            self._get_action('information-').activate()
            return Gdk.EVENT_STOP

        if action == 'send-file':
            if app.interface.msg_win_mgr.mode == \
            app.interface.msg_win_mgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
                app.interface.roster.tree.grab_focus()
                return Gdk.EVENT_PROPAGATE

            self._get_action('send-file-').activate()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_add_to_roster(self, _action, _param):
        AddNewContactWindow(self.account, self.contact.jid)

    def _on_block_contact(self, _action, _param):
        app.window.block_contact(self.account, self.contact.jid)

    def _on_information(self, _action, _param):
        app.window.contact_info(self.account, self.contact.jid)

    def _on_invite_contacts(self, _action, _param):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

    def _on_send_chatstate(self, action, param):
        action.set_state(param)
        self.contact.settings.set('send_chatstate', param.get_string())

    def _on_send_marker(self, action, param):
        action.set_state(param)
        self.contact.settings.set('send_marker', param.get_boolean())

    def _update_toolbar(self):
        # Formatting
        # TODO: find out what encryption allows for xhtml and which not
        if self.contact.supports(Namespace.XHTML_IM):
            self.xml.formattings_button.set_sensitive(True)
            self.xml.formattings_button.set_tooltip_text(_(
                'Show a list of formattings'))
        else:
            self.xml.formattings_button.set_sensitive(False)
            self.xml.formattings_button.set_tooltip_text(
                _('This contact does not support HTML'))

    def update_all_pep_types(self):
        self._update_pep(PEPEventType.LOCATION)
        self._update_pep(PEPEventType.MOOD)
        self._update_pep(PEPEventType.ACTIVITY)
        self._update_pep(PEPEventType.TUNE)

    def _update_pep(self, type_):
        return
        # TODO
        image = self._get_pep_widget(type_)
        data = self.contact.pep.get(type_)
        if data is None:
            image.hide()
            return

        if type_ == PEPEventType.MOOD:
            icon = 'mood-%s' % data.mood
            formated_text = format_mood(*data)
        elif type_ == PEPEventType.ACTIVITY:
            icon = get_activity_icon_name(data.activity, data.subactivity)
            formated_text = format_activity(*data)
        elif type_ == PEPEventType.TUNE:
            icon = 'audio-x-generic'
            formated_text = format_tune(*data)
        elif type_ == PEPEventType.LOCATION:
            icon = 'applications-internet'
            formated_text = format_location(data)

        image.set_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_tooltip_markup(formated_text)
        image.show()

    def _get_pep_widget(self, type_):
        if type_ == PEPEventType.MOOD:
            return self.xml.mood_image
        if type_ == PEPEventType.ACTIVITY:
            return self.xml.activity_image
        if type_ == PEPEventType.TUNE:
            return self.xml.tune_image
        if type_ == PEPEventType.LOCATION:
            return self.xml.location_image
        return None

    def _on_mood_received(self, _event):
        self._update_pep(PEPEventType.MOOD)

    def _on_activity_received(self, _event):
        self._update_pep(PEPEventType.ACTIVITY)

    def _on_tune_received(self, _event):
        self._update_pep(PEPEventType.TUNE)

    def _on_location_received(self, _event):
        self._update_pep(PEPEventType.LOCATION)

    def _on_nickname_received(self, _event):
        self.update_ui()

    def _on_update_client_info(self, event):
        contact = app.contacts.get_contact(
            self.account, event.jid, event.resource)
        if contact is None:
            return
        self.xml.phone_image.set_visible(contact.uses_phone)

    def _on_chatstate_update(self, *args):
        self.draw_banner_text()

    def _on_nickname_update(self, _contact, _signal_name):
        self.draw_banner_text()

    def _on_presence_update(self, _contact, _signal_name):
        self._update_avatar()

    def _on_caps_update(self, event):
        if self._type.is_chat and event.jid != self.contact.jid:
            return
        if self._type.is_privatechat and event.fjid != self.contact.jid:
            return
        self.update_ui()

    def _on_mam_message_received(self, event):
        if event.properties.is_muc_pm:
            if not event.properties.jid == self.contact.jid:
                return
        else:
            if not event.properties.jid.bare_match(self.contact.jid):
                return

        kind = '' # incoming
        if event.kind == KindConstant.CHAT_MSG_SENT:
            kind = 'outgoing'

        self.add_message(event.msgtxt,
                         kind,
                         tim=event.properties.mam.timestamp,
                         correct_id=event.correct_id,
                         message_id=event.properties.id,
                         additional_data=event.additional_data)

    def _on_message_received(self, event):
        if not event.msgtxt:
            return

        typ = ''
        if event.properties.is_sent_carbon:
            typ = 'out'

        self.add_message(event.msgtxt,
                         typ,
                         tim=event.properties.timestamp,
                         subject=event.properties.subject,
                         displaymarking=event.displaymarking,
                         msg_log_id=event.msg_log_id,
                         message_id=event.properties.id,
                         correct_id=event.correct_id,
                         additional_data=event.additional_data)

        self.conversation_view.set_read_marker(event.properties.id)

    def _on_message_error(self, event):
        self.conversation_view.show_error(event.message_id, event.error)

    def _on_message_sent(self, event):
        if not event.message:
            return

        self.last_sent_msg = event.message_id
        message_id = event.message_id

        if event.label:
            displaymarking = event.label.displaymarking
        else:
            displaymarking = None
        if self.correcting:
            self.correcting = False
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'gajim-msg-correcting')

        self.add_message(event.message,
                         self.contact.jid,
                         tim=event.timestamp,
                         displaymarking=displaymarking,
                         message_id=message_id,
                         correct_id=event.correct_id,
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

    # Jingle AV
    def _on_start_call(self, *args):
        audio_state = self.jingle['audio'].state
        video_state = self.jingle['video'].state
        if audio_state == JingleState.NULL and video_state == JingleState.NULL:
            self.xml.av_box.set_no_show_all(False)
            self.xml.av_box.show_all()
            self.xml.jingle_audio_state.hide()
            self.xml.av_start_box.show()
            self.xml.av_start_mic_cam_button.set_sensitive(
                self.jingle['video'].available)
            self.xml.av_cam_button.set_sensitive(False)

    def _on_call_with_mic(self, _button):
        self._on_jingle_button_toggled(['audio'])
        self.xml.av_start_box.hide()

    def _on_call_with_mic_and_cam(self, _button):
        self._on_jingle_button_toggled(['audio', 'video'])
        self.xml.av_start_box.hide()

    def _on_video(self, *args):
        self._on_jingle_button_toggled(['video'])

    def update_audio(self):
        self.update_actions()

        audio_state = self.jingle['audio'].state
        video_state = self.jingle['video'].state
        if self.jingle['video'].available:
            self.xml.av_cam_button.set_sensitive(
                video_state not in (
                    JingleState.CONNECTING,
                    JingleState.CONNECTED))

        if audio_state == JingleState.NULL:
            self.xml.audio_buttons_box.set_sensitive(False)
            self.xml.jingle_audio_state.set_no_show_all(True)
            self.xml.jingle_audio_state.hide()
            self.xml.jingle_connection_state.set_text('')
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()

            if video_state == JingleState.NULL:
                self.xml.av_box.set_no_show_all(True)
                self.xml.av_box.hide()
        else:
            self.xml.jingle_connection_spinner.show()
            self.xml.jingle_connection_spinner.start()

        if audio_state == JingleState.CONNECTING:
            self.xml.av_box.set_no_show_all(False)
            self.xml.av_box.show_all()
            self.xml.jingle_connection_state.set_text(
                _('Calling…'))
            self.xml.av_cam_button.set_sensitive(False)

        elif audio_state == JingleState.CONNECTION_RECEIVED:
            self.xml.jingle_connection_state.set_text(
                _('Incoming Call'))

        elif audio_state == JingleState.CONNECTED:
            self.xml.jingle_audio_state.set_no_show_all(False)
            self.xml.jingle_audio_state.show()
            self.xml.jingle_connection_state.set_text('')
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()
            if self.jingle['video'].available:
                self.xml.av_cam_button.set_sensitive(True)

            input_vol = app.settings.get('audio_input_volume')
            output_vol = app.settings.get('audio_output_volume')
            self.xml.mic_hscale.set_value(max(min(input_vol, 100), 0))
            self.xml.sound_hscale.set_value(max(min(output_vol, 100), 0))
            self.xml.audio_buttons_box.set_sensitive(True)

        elif audio_state == JingleState.ERROR:
            self.xml.jingle_audio_state.hide()
            self.xml.jingle_connection_state.set_text(
                _('Connection Error'))
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()

        if not self.jingle['audio'].sid:
            self.xml.audio_buttons_box.set_sensitive(False)

    def update_video(self):
        self.update_actions()

        audio_state = self.jingle['audio'].state
        video_state = self.jingle['video'].state

        if video_state == JingleState.NULL:
            self.xml.video_box.set_no_show_all(True)
            self.xml.video_box.hide()
            self.xml.outgoing_viewport.set_no_show_all(True)
            self.xml.outgoing_viewport.hide()
            if self._video_widget_other:
                self._video_widget_other.destroy()
            if self._video_widget_self:
                self._video_widget_self.destroy()

            if audio_state != JingleState.CONNECTED:
                self.xml.jingle_connection_state.set_text('')
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()
            self.xml.av_cam_button.set_sensitive(True)
            self.xml.av_cam_button.set_tooltip_text(_('Turn Camera on'))
            self.xml.av_cam_image.set_from_icon_name(
                'feather-camera-symbolic', Gtk.IconSize.BUTTON)
            if audio_state == JingleState.NULL:
                self.xml.av_box.set_no_show_all(True)
                self.xml.av_box.hide()
        else:
            self.xml.jingle_connection_spinner.show()
            self.xml.jingle_connection_spinner.start()

        if video_state == JingleState.CONNECTING:
            self.xml.jingle_connection_state.set_text(_('Calling (Video)…'))
            self.xml.av_box.set_no_show_all(False)
            self.xml.av_box.show_all()
            self.xml.av_cam_button.set_sensitive(False)
            self.xml.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self.xml.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.CONNECTION_RECEIVED:
            self.xml.jingle_connection_state.set_text(
                _('Incoming Call (Video)'))
            self.xml.av_cam_button.set_sensitive(False)
            self.xml.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self.xml.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.CONNECTED:
            self.xml.video_box.set_no_show_all(False)
            self.xml.video_box.show_all()
            if app.settings.get('video_see_self'):
                self.xml.outgoing_viewport.set_no_show_all(False)
                self.xml.outgoing_viewport.show()
            else:
                self.xml.outgoing_viewport.set_no_show_all(True)
                self.xml.outgoing_viewport.hide()

            sink_other, self._video_widget_other, _name = create_gtk_widget()
            sink_self, self._video_widget_self, _name = create_gtk_widget()
            self.xml.incoming_viewport.add(self._video_widget_other)
            self.xml.outgoing_viewport.add(self._video_widget_self)

            session = self._client.get_module('Jingle').get_jingle_session(
                self.contact.jid, self.jingle['video'].sid)
            content = session.get_content('video')
            content.do_setup(sink_self, sink_other)

            self.xml.jingle_connection_state.set_text('')
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()

            self.xml.av_cam_button.set_sensitive(True)
            self.xml.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self.xml.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.ERROR:
            self.xml.jingle_connection_state.set_text(
                _('Connection Error'))
            self.xml.jingle_connection_spinner.stop()
            self.xml.jingle_connection_spinner.hide()

    def set_jingle_state(self, jingle_type: str, state: str, sid: str = None,
                         reason: str = None) -> None:
        jingle = self.jingle[jingle_type]
        if state in (
                JingleState.CONNECTING,
                JingleState.CONNECTED,
                JingleState.NULL,
                JingleState.ERROR) and reason:
            log.info('%s state: %s, reason: %s', jingle_type, state, reason)

        if state in (jingle.state, JingleState.ERROR):
            return

        if (state == JingleState.NULL and jingle.sid not in (None, sid)):
            return

        new_sid = None
        if state == JingleState.NULL:
            new_sid = None
        if state in (
                JingleState.CONNECTION_RECEIVED,
                JingleState.CONNECTING,
                JingleState.CONNECTED):
            new_sid = sid

        jingle.state = state
        jingle.sid = new_sid
        jingle.update()

    def stop_jingle(self, sid=None, reason=None):
        audio_sid = self.jingle['audio'].sid
        video_sid = self.jingle['video'].sid
        if audio_sid and sid in (audio_sid, None):
            self.close_jingle_content('audio')
        if video_sid and sid in (video_sid, None):
            self.close_jingle_content('video')

    def close_jingle_content(self, jingle_type: str,
                             shutdown: Optional[bool] = False) -> None:
        jingle = self.jingle[jingle_type]
        if not jingle.sid:
            return

        session = self._client.get_module('Jingle').get_jingle_session(
            self.contact.jid, jingle.sid)
        if session:
            content = session.get_content(jingle_type)
            if content:
                session.remove_content(content.creator, content.name)

        if not shutdown:
            jingle.sid = None
            jingle.state = JingleState.NULL
            jingle.update()

    def _on_end_call_clicked(self, _widget):
        self.close_jingle_content('audio')
        self.close_jingle_content('video')
        self.xml.jingle_audio_state.set_no_show_all(True)
        self.xml.jingle_audio_state.hide()
        self.xml.av_box.set_no_show_all(True)
        self.xml.av_box.hide()

    def _on_jingle_button_toggled(self, jingle_types):
        if all(item in jingle_types for item in ['audio', 'video']):
            # Both 'audio' and 'video' in jingle_types
            sid = self._client.get_module('Jingle').start_audio_video(
                self.contact.jid)
            self.set_jingle_state('audio', JingleState.CONNECTING, sid)
            self.set_jingle_state('video', JingleState.CONNECTING, sid)
            return

        if 'audio' in jingle_types:
            if self.jingle['audio'].state != JingleState.NULL:
                self.close_jingle_content('audio')
            else:
                sid = self._client.get_module('Jingle').start_audio(
                    self.contact.jid)
                self.set_jingle_state('audio', JingleState.CONNECTING, sid)

        if 'video' in jingle_types:
            if self.jingle['video'].state != JingleState.NULL:
                self.close_jingle_content('video')
            else:
                sid = self._client.get_module('Jingle').start_video(
                    self.contact.jid)
                self.set_jingle_state('video', JingleState.CONNECTING, sid)

    def _get_audio_content(self):
        session = self._client.get_module('Jingle').get_jingle_session(
            self.contact.jid, self.jingle['audio'].sid)
        return session.get_content('audio')

    def on_num_button_pressed(self, _widget, num):
        self._get_audio_content().start_dtmf(num)

    def on_num_button_released(self, _released):
        self._get_audio_content().stop_dtmf()

    def on_mic_hscale_value_changed(self, _widget, value):
        self._get_audio_content().set_mic_volume(value / 100)
        app.settings.set('audio_input_volume', int(value))

    def on_sound_hscale_value_changed(self, _widget, value):
        self._get_audio_content().set_out_volume(value / 100)
        app.settings.set('audio_output_volume', int(value))

    def on_location_eventbox_button_release_event(self, _widget, _event):
        return
        # TODO
        if 'geoloc' in self.contact.pep:
            location = self.contact.pep['geoloc'].data
            if 'lat' in location and 'lon' in location:
                uri = geo_provider_from_location(location['lat'],
                                                 location['lon'])
                open_uri(uri)

    def on_location_eventbox_leave_notify_event(self, _widget, _event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = get_cursor('default')
        app.window.get_window().set_cursor(cursor)

    def on_location_eventbox_enter_notify_event(self, _widget, _event):
        cursor = get_cursor('pointer')
        app.window.get_window().set_cursor(cursor)

    def update_ui(self):
        # The name banner is drawn here
        ChatControlBase.update_ui(self)
        self.update_toolbar()
        self._update_avatar()
        self.update_actions()

    def draw_banner_text(self):
        """
        Draw the text in the fat line at the top of the window that houses the
        name, jid
        """
        contact = self.contact
        name = contact.name
        # if self.resource:
        #     name += '/' + self.resource
        # if self._type.is_privatechat:
        #     name = i18n.direction_mark + _(
        #         '%(nickname)s from group chat %(room_name)s') % \
        #         {'nickname': name, 'room_name': self.room_name}

        # name = i18n.direction_mark + GLib.markup_escape_text(name)

        cs = self.contact.chatstate
        if cs is not None:
            cs = cs.value

        if app.settings.get('show_chatstate_in_banner'):
            chatstate = helpers.get_uf_chatstate(cs)

            label_text = '<span>%s</span><span size="x-small" weight="light"> %s</span>' % \
                (name, chatstate)
            label_tooltip = '%s %s' % (name, chatstate)
        else:
            label_text = '<span>%s</span>' % name
            label_tooltip = name

        status_text = ''
        self.xml.banner_label.hide()
        self.xml.banner_label.set_no_show_all(True)

        self.xml.banner_label.set_markup(status_text)
        # setup the label that holds name and jid
        self.xml.banner_name_label.set_markup(label_text)
        self.xml.banner_name_label.set_tooltip_text(label_tooltip)

    def send_message(self,
                     message,
                     xhtml=None,
                     process_commands=True,
                     attention=False):
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

        ChatControlBase.send_message(self,
                                     message,
                                     type_='chat',
                                     xhtml=xhtml,
                                     process_commands=process_commands,
                                     attention=attention)

    def get_our_nick(self):
        return app.nicks[self.account]

    def add_message(self,
                    text,
                    frm='',
                    tim=None,
                    subject=None,
                    displaymarking=None,
                    msg_log_id=None,
                    correct_id=None,
                    message_id=None,
                    additional_data=None):
        """
        Print a line in the conversation

        If frm is set to status: it's a status message.
        if frm is set to error: it's an error message. The difference between
            status and error is mainly that with error, msg count as a new
            message (in systray and in control).
        If frm is set to info: it's a information message.
        If frm is set to print_queue: it is incoming from queue.
        If frm is set to another value: it's an outgoing message.
        If frm is not set: it's an incoming message.
        """
        contact = self.contact

        if additional_data is None:
            additional_data = AdditionalDataDict()

        if frm == 'error':
            kind = 'error'
            name = ''
        else:
            if not frm:
                kind = 'incoming'
                name = contact.name
            elif frm == 'print_queue':
                kind = 'incoming_queue'
                name = contact.name
            else:
                kind = 'outgoing'
                name = self.get_our_nick()

        ChatControlBase.add_message(self,
                                    text,
                                    kind,
                                    name,
                                    tim,
                                    displaymarking=displaymarking,
                                    msg_log_id=msg_log_id,
                                    message_id=message_id,
                                    correct_id=correct_id,
                                    additional_data=additional_data)

        if text.startswith('/me ') or text.startswith('/me\n'):
            self.old_msg_kind = None
        else:
            self.old_msg_kind = kind

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Set compact view menuitem active state sets active and sensitivity state
        for history_menuitem (False for tranasports) and file_transfer_menuitem
        and hide()/show() for add_to_roster_menuitem
        """
        if app.jid_is_transport(self.contact.jid):
            menu = gui_menu_builder.get_transport_menu(self.contact,
                                                       self.account)
        else:
            menu = gui_menu_builder.get_contact_menu(
                self.contact,
                self.account,
                use_multiple_contacts=False,
                show_start_chat=False,
                show_encryption=True,
                control=self,
                show_buttonbar_items=not hide_buttonbar_items)
        return menu

    def shutdown(self):
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        app.plugin_manager.remove_gui_extension_point('chat_control', self)

        self.remove_actions()

        # Send 'gone' chatstate
        self._client.get_module('Chatstate').set_chatstate(
            self.contact, Chatstate.GONE)

        for jingle_type in ('audio', 'video'):
            self.close_jingle_content(jingle_type, shutdown=True)
        self.jingle.clear()

        super(ChatControl, self).shutdown()
        app.check_finalize(self)

    def allow_shutdown(self, method, on_yes, on_no, _on_minimize):
        time_ = app.last_message_time[self.account][self.contact.jid]
        # 2 seconds
        if time.time() - time_ < 2:
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

    def _update_avatar(self):
        scale = app.window.get_scale_factor()
        surface = self.contact.get_avatar(AvatarSize.CHAT, scale)
        self.xml.avatar_image.set_from_surface(surface)

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        if not selection.get_data():
            return

        if target_type == self.TARGET_TYPE_URI_LIST:
            # File drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(selection)
        else:
            # Convert single chat to MUC
            treeview = app.interface.roster.tree
            model = treeview.get_model()
            data = selection.get_data().decode()
            tree_selection = treeview.get_selection()
            if tree_selection.count_selected_rows() == 0:
                return
            path = tree_selection.get_selected_rows()[1][0]
            iter_ = model.get_iter(path)
            type_ = model[iter_][2]
            if type_ != 'contact':  # Source is not a contact
                return
            dropped_jid = data

            dropped_transport = app.get_transport_name_from_jid(dropped_jid)
            c_transport = app.get_transport_name_from_jid(self.contact.jid)
            if dropped_transport or c_transport:
                return # transport contacts cannot be invited

            dialogs.TransformChatToMUC(self.account,
                                       [self.contact.jid],
                                       [dropped_jid])

    def _on_convert_to_gc_menuitem_activate(self, _widget):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

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

        status = '- %s' % event.status if event.status else ''
        status_line = _('%(name)s is now %(show)s %(status)s') % {
            'name': name, 'show': uf_show, 'status': status}
        self.add_status_message(status_line)

    def _info_bar_show_message(self):
        if self.info_bar.get_visible():
            # A message is already shown
            return
        if not self.info_bar_queue:
            return
        markup, buttons, _args, type_ = self.info_bar_queue[0]
        self.info_bar_label.set_markup(markup)

        # Remove old buttons
        area = self.info_bar.get_action_area()
        for button in area.get_children():
            area.remove(button)

        # Add new buttons
        for button in buttons:
            self.info_bar.add_action_widget(button, 0)

        self.info_bar.set_message_type(type_)
        self.info_bar.set_no_show_all(False)
        self.info_bar.show_all()

    def _add_info_bar_message(self, markup, buttons, args,
                              type_=Gtk.MessageType.INFO):
        self.info_bar_queue.append((markup, buttons, args, type_))
        self._info_bar_show_message()

    def _get_file_props_event(self, file_props, type_):
        evs = app.events.get_events(self.account, self.contact.jid, [type_])
        for ev in evs:
            if ev.file_props == file_props:
                return ev
        return None

    def _on_accept_file_request(self, _widget, file_props):
        app.interface.instances['file_transfers'].on_file_request_accepted(
            self.account, self.contact, file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_cancel_file_request(self, _widget, file_props):
        self._client.get_module('Bytestream').send_file_rejection(file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_request(self, file_props):
        """
        Show an InfoBar on top of control
        """
        if app.settings.get('use_kib_mib'):
            units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            units = GLib.FormatSizeFlags.DEFAULT

        markup = '<b>%s</b>\n%s' % (_('File Transfer'), file_props.name)
        if file_props.desc:
            markup += '\n(%s)' % file_props.desc
        markup += '\n%s: %s' % (
            _('Size'),
            GLib.format_size_full(file_props.size, units))
        button_decline = Gtk.Button.new_with_mnemonic(_('_Decline'))
        button_decline.connect(
            'clicked', self._on_cancel_file_request, file_props)
        button_accept = Gtk.Button.new_with_mnemonic(_('_Accept'))
        button_accept.connect(
            'clicked', self._on_accept_file_request, file_props)
        self._add_info_bar_message(
            markup,
            [button_decline, button_accept],
            file_props,
            Gtk.MessageType.QUESTION)

    def _on_open_ft_folder(self, _widget, file_props):
        path = os.path.split(file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            open_file(path)
        ev = self._get_file_props_event(file_props, 'file-completed')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_ok(self, _widget, file_props, type_):
        ev = self._get_file_props_event(file_props, type_)
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_completed(self, file_props):
        markup = '<b>%s</b>\n%s' % (_('File Transfer Completed'),
                                    file_props.name)
        if file_props.desc:
            markup += '\n(%s)' % file_props.desc
        b1 = Gtk.Button.new_with_mnemonic(_('Open _Folder'))
        b1.connect('clicked', self._on_open_ft_folder, file_props)
        b2 = Gtk.Button.new_with_mnemonic(_('_Close'))
        b2.connect('clicked', self._on_ok, file_props, 'file-completed')
        self._add_info_bar_message(
            markup,
            [b1, b2],
            file_props)

    def _got_file_error(self, file_props, type_, pri_txt, sec_txt):
        markup = '<b>%s</b>\n%s' % (pri_txt, sec_txt)
        button = Gtk.Button.new_with_mnemonic(_('_Close'))
        button.connect('clicked', self._on_ok, file_props, type_)
        self._add_info_bar_message(
            markup,
            [button],
            file_props,
            Gtk.MessageType.ERROR)

    def _on_accept_gc_invitation(self, _widget, event):
        app.interface.show_or_join_groupchat(self.account,
                                             str(event.muc),
                                             password=event.password)
        app.events.remove_events(self.account, self.contact.jid, event=event)

    def _on_cancel_gc_invitation(self, _widget, event):
        app.events.remove_events(self.account, self.contact.jid, event=event)

    def _get_gc_invitation(self, event):
        markup = '<b>%s</b>\n%s' % (_('Group Chat Invitation'), event.muc)
        if event.reason:
            markup += '\n(%s)' % event.reason
        button_decline = Gtk.Button.new_with_mnemonic(_('_Decline'))
        button_decline.connect('clicked', self._on_cancel_gc_invitation, event)
        button_accept = Gtk.Button.new_with_mnemonic(_('_Accept'))
        button_accept.connect('clicked', self._on_accept_gc_invitation, event)
        self._add_info_bar_message(
            markup,
            [button_decline, button_accept],
            (event.muc, event.reason),
            Gtk.MessageType.QUESTION)

    def _on_reject_call(self, _button, event):
        app.events.remove_events(
            self.account, self.contact.jid, types='jingle-incoming')

        session = self._client.get_module('Jingle').get_jingle_session(
            event.peerjid, event.sid)
        if not session:
            return

        if not session.accepted:
            session.decline_session()
        else:
            for content in event.content_types:
                session.reject_content(content)

    def _on_accept_call(self, _button, event):
        app.events.remove_events(
            self.account, self.contact.jid, types='jingle-incoming')

        session = self._client.get_module('Jingle').get_jingle_session(
            event.peerjid, event.sid)
        if not session:
            return

        audio = session.get_content('audio')
        video = session.get_content('video')

        if audio and not audio.negotiated:
            self.set_jingle_state('audio', JingleState.CONNECTING, event.sid)
        if video and not video.negotiated:
            self.set_jingle_state('video', JingleState.CONNECTING, event.sid)

        if not session.accepted:
            session.approve_session()

        for content in event.content_types:
            session.approve_content(content)

    def add_call_received_message(self, event):
        markup = '<b>%s</b>' % (_('Incoming Call'))
        if 'video' in event.content_types:
            markup += _('\nVideo Call')
        else:
            markup += _('\nVoice Call')

        button_reject = Gtk.Button.new_with_mnemonic(_('_Reject'))
        button_reject.connect('clicked', self._on_reject_call, event)
        button_accept = Gtk.Button.new_with_mnemonic(_('_Accept'))
        button_accept.connect('clicked', self._on_accept_call, event)
        self._add_info_bar_message(
            markup,
            [button_reject, button_accept],
            event,
            Gtk.MessageType.QUESTION)

    def on_event_added(self, event):
        if event.account != self.account:
            return
        if event.jid != self.contact.jid:
            return
        if event.type_ == 'file-request':
            self._got_file_request(event.file_props)
        elif event.type_ == 'file-completed':
            self._got_file_completed(event.file_props)
        elif event.type_ in ('file-error', 'file-stopped'):
            msg_err = ''
            if event.file_props.error == -1:
                msg_err = _('Remote contact stopped transfer')
            elif event.file_props.error == -6:
                msg_err = _('Error opening file')
            self._got_file_error(event.file_props, event.type_,
                                 _('File transfer stopped'), msg_err)
        elif event.type_ in ('file-request-error', 'file-send-error'):
            self._got_file_error(
                event.file_props,
                event.type_,
                _('File transfer cancelled'),
                _('Connection with peer cannot be established.'))
        elif event.type_ == 'gc-invitation':
            self._get_gc_invitation(event)
