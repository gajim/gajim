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

import os
import time

from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import Gdk
from nbxmpp.protocol import NS_XHTML, NS_XHTML_IM, NS_FILE, NS_MUC
from nbxmpp.protocol import NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO
from nbxmpp.protocol import NS_JINGLE_ICE_UDP, NS_JINGLE_FILE_TRANSFER_5

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import open_uri
from gajim.common.helpers import geo_provider_from_location
from gajim.common.contacts import GC_Contact
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import Chatstate
from gajim.common.const import PEPEventType

from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import message_control
from gajim import dialogs

from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.add_contact import AddNewContactWindow
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_cursor
from gajim.gtk.util import ensure_proper_control
from gajim.gtk.util import format_mood
from gajim.gtk.util import format_activity
from gajim.gtk.util import format_tune
from gajim.gtk.util import format_location
from gajim.gtk.util import get_activity_icon_name

from gajim.command_system.implementation.hosts import ChatCommands
from gajim.command_system.framework import CommandHost  # pylint: disable=unused-import
from gajim.chat_control_base import ChatControlBase

################################################################################
class ChatControl(ChatControlBase):
    """
    A control for standard 1-1 chat
    """
    (
            JINGLE_STATE_NULL,
            JINGLE_STATE_CONNECTING,
            JINGLE_STATE_CONNECTION_RECEIVED,
            JINGLE_STATE_CONNECTED,
            JINGLE_STATE_ERROR
    ) = range(5)

    TYPE_ID = message_control.TYPE_CHAT
    old_msg_kind = None # last kind of the printed message

    # Set a command host to bound to. Every command given through a chat will be
    # processed with this command host.
    COMMAND_HOST = ChatCommands  # type: ClassVar[Type[CommandHost]]

    def __init__(self, parent_win, contact, acct, session, resource=None):
        ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
            'chat_control', contact, acct, resource)

        self.last_recv_message_id = None
        self.last_recv_message_marks = None
        self.last_message_timestamp = None

        self._formattings_button = self.xml.get_object('formattings_button')
        self.emoticons_button = self.xml.get_object('emoticons_button')
        self.toggle_emoticons()

        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            app.config.get('hide_chat_banner'))

        self.authentication_button = self.xml.get_object(
            'authentication_button')
        id_ = self.authentication_button.connect('clicked',
            self._on_authentication_button_clicked)
        self.handlers[id_] = self.authentication_button

        self.sendfile_button = self.xml.get_object('sendfile_button')
        self.sendfile_button.set_action_name('win.send-file-' + \
                                             self.control_id)

        # Add lock image to show chat encryption
        self.lock_image = self.xml.get_object('lock_image')

        # Menu for the HeaderBar
        self.control_menu = gui_menu_builder.get_singlechat_menu(
            self.control_id, self.account, self.contact.jid)
        settings_menu = self.xml.get_object('settings_menu')
        settings_menu.set_menu_model(self.control_menu)

        self._audio_banner_image = self.xml.get_object('audio_banner_image')
        self._video_banner_image = self.xml.get_object('video_banner_image')
        self.audio_sid = None
        self.audio_state = self.JINGLE_STATE_NULL
        self.audio_available = False
        self.video_sid = None
        self.video_state = self.JINGLE_STATE_NULL
        self.video_available = False

        self.update_toolbar()
        self.update_all_pep_types()
        self.show_avatar()

        # Hook up signals
        widget = self.xml.get_object('avatar_eventbox')
        widget.set_property('height-request', AvatarSize.CHAT)

        id_ = widget.connect('button-press-event',
            self.on_avatar_eventbox_button_press_event)
        self.handlers[id_] = widget

        widget = self.xml.get_object('location_eventbox')
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

        widget = self.xml.get_object('mic_hscale')
        id_ = widget.connect('value_changed', self.on_mic_hscale_value_changed)
        self.handlers[id_] = widget

        widget = self.xml.get_object('sound_hscale')
        id_ = widget.connect('value_changed', self.on_sound_hscale_value_changed)
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
        widget = self.xml.get_object('vbox2')
        widget.pack_start(self.info_bar, False, True, 5)
        widget.reorder_child(self.info_bar, 1)

        # List of waiting infobar messages
        self.info_bar_queue = []

        self.subscribe_events()

        if not session:
            # Don't use previous session if we want to a specific resource
            # and it's not the same
            if not resource:
                resource = contact.resource
            session = app.connections[self.account].find_controlless_session(
                self.contact.jid, resource)

        self.setup_seclabel()
        if session:
            session.control = self
            self.session = session

        # Enable encryption if needed
        self.no_autonegotiation = False
        self.add_actions()
        self.update_ui()
        self.set_lock_image()

        self.encryption_menu = self.xml.get_object('encryption_menu')
        self.encryption_menu.set_menu_model(
            gui_menu_builder.get_encryption_menu(
                self.control_id, self.type_id, self.account == 'Local'))
        self.set_encryption_menu_icon()
        # restore previous conversation
        self.restore_conversation()
        self.msg_textview.grab_focus()

        app.ged.register_event_handler('nickname-received', ged.GUI1,
            self._on_nickname_received)
        app.ged.register_event_handler('mood-received', ged.GUI1,
            self._on_mood_received)
        app.ged.register_event_handler('activity-received', ged.GUI1,
            self._on_activity_received)
        app.ged.register_event_handler('tune-received', ged.GUI1,
            self._on_tune_received)
        app.ged.register_event_handler('location-received', ged.GUI1,
            self._on_location_received)
        app.ged.register_event_handler('update-client-info', ged.GUI1,
            self._on_update_client_info)
        if self.TYPE_ID == message_control.TYPE_CHAT:
            # Dont connect this when PrivateChatControl is used
            app.ged.register_event_handler('update-roster-avatar', ged.GUI1,
                self._nec_update_avatar)
        app.ged.register_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        app.ged.register_event_handler('caps-update', ged.GUI1,
            self._nec_caps_received)
        app.ged.register_event_handler('message-sent', ged.OUT_POSTCORE,
            self._message_sent)
        app.ged.register_event_handler(
            'mam-decrypted-message-received',
            ged.GUI1, self._nec_mam_decrypted_message_received)
        app.ged.register_event_handler(
            'decrypted-message-received',
            ged.GUI1, self._nec_decrypted_message_received)
        app.ged.register_event_handler(
            'receipt-received',
            ged.GUI1, self._receipt_received)

        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        app.plugin_manager.gui_extension_point('chat_control', self)
        self.update_actions()

    def add_actions(self):
        super().add_actions()
        actions = [
            ('invite-contacts-', self._on_invite_contacts),
            ('add-to-roster-', self._on_add_to_roster),
            ('information-', self._on_information),
            ]

        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(action_name + self.control_id, None)
            act.connect("activate", func)
            self.parent_win.window.add_action(act)

        self.audio_action = Gio.SimpleAction.new_stateful(
            'toggle-audio-' + self.control_id, None,
            GLib.Variant.new_boolean(False))
        self.audio_action.connect('change-state', self._on_audio)
        self.parent_win.window.add_action(self.audio_action)

        self.video_action = Gio.SimpleAction.new_stateful(
            'toggle-video-' + self.control_id,
            None, GLib.Variant.new_boolean(False))
        self.video_action.connect('change-state', self._on_video)
        self.parent_win.window.add_action(self.video_action)

        default_chatstate = app.config.get('send_chatstate_default')
        chatstate = app.config.get_per(
            'contacts', self.contact.jid, 'send_chatstate', default_chatstate)

        act = Gio.SimpleAction.new_stateful(
            'send-chatstate-' + self.control_id,
            GLib.VariantType.new("s"),
            GLib.Variant("s", chatstate))
        act.connect('change-state', self._on_send_chatstate)
        self.parent_win.window.add_action(act)

    def update_actions(self):
        win = self.parent_win.window
        online = app.account_is_connected(self.account)
        con = app.connections[self.account]

        # Add to roster
        if not isinstance(self.contact, GC_Contact) \
        and _('Not in Roster') in self.contact.groups and \
        app.connections[self.account].roster_supported and online:
            win.lookup_action(
                'add-to-roster-' + self.control_id).set_enabled(True)
        else:
            win.lookup_action(
                'add-to-roster-' + self.control_id).set_enabled(False)

        # Audio
        win.lookup_action('toggle-audio-' + self.control_id).set_enabled(
            online and self.audio_available)

        # Video
        win.lookup_action('toggle-video-' + self.control_id).set_enabled(
            online and self.video_available)

        # Send file (HTTP File Upload)
        httpupload = win.lookup_action(
            'send-file-httpupload-' + self.control_id)
        httpupload.set_enabled(
            online and con.get_module('HTTPUpload').available)

        # Send file (Jingle)
        jingle_conditions = (
            (self.contact.supports(NS_FILE) or
             self.contact.supports(NS_JINGLE_FILE_TRANSFER_5)) and
             self.contact.show != 'offline')
        jingle = win.lookup_action('send-file-jingle-' + self.control_id)
        jingle.set_enabled(online and jingle_conditions)

        # Send file
        win.lookup_action(
            'send-file-' + self.control_id).set_enabled(
            jingle.get_enabled() or httpupload.get_enabled())

        # Set File Transfer Button tooltip
        if online and (httpupload.get_enabled() or jingle.get_enabled()):
            tooltip_text = _('Send File…')
        else:
            tooltip_text = _('No File Transfer available')
        self.sendfile_button.set_tooltip_text(tooltip_text)

        # Convert to GC
        if app.config.get_per('accounts', self.account, 'is_zeroconf'):
            win.lookup_action(
                'invite-contacts-' + self.control_id).set_enabled(False)
        else:
            if self.contact.supports(NS_MUC) and online:
                win.lookup_action(
                    'invite-contacts-' + self.control_id).set_enabled(True)
            else:
                win.lookup_action(
                    'invite-contacts-' + self.control_id).set_enabled(False)

        # Information
        win.lookup_action(
            'information-' + self.control_id).set_enabled(online)

    def delegate_action(self, action):
        res = super().delegate_action(action)
        if res == Gdk.EVENT_STOP:
            return res

        if action == 'show-contact-info':
            self.parent_win.window.lookup_action(
                'information-%s' % self.control_id).activate()
            return Gdk.EVENT_STOP

        if action == 'send-file':
            if app.interface.msg_win_mgr.mode == \
            app.interface.msg_win_mgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
                app.interface.roster.tree.grab_focus()
                return Gdk.EVENT_PROPAGATE

            self.parent_win.window.lookup_action(
                'send-file-%s' % self.control_id).activate()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_add_to_roster(self, action, param):
        AddNewContactWindow(self.account, self.contact.jid)

    def _on_information(self, action, param):
        app.interface.roster.on_info(None, self.contact, self.account)

    def _on_invite_contacts(self, action, param):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

    def _on_audio(self, action, param):
        action.set_state(param)
        state = param.get_boolean()
        self.on_jingle_button_toggled(state, 'audio')

    def _on_video(self, action, param):
        action.set_state(param)
        state = param.get_boolean()
        self.on_jingle_button_toggled(state, 'video')

    def _on_send_chatstate(self, action, param):
        action.set_state(param)
        app.config.set_per('contacts', self.contact.jid,
                           'send_chatstate', param.get_string())

    def subscribe_events(self):
        """
        Register listeners to the events class
        """
        app.events.event_added_subscribe(self.on_event_added)
        app.events.event_removed_subscribe(self.on_event_removed)

    def unsubscribe_events(self):
        """
        Unregister listeners to the events class
        """
        app.events.event_added_unsubscribe(self.on_event_added)
        app.events.event_removed_unsubscribe(self.on_event_removed)

    def _update_toolbar(self):
        # Formatting
        # TODO: find out what encryption allows for xhtml and which not
        if self.contact.supports(NS_XHTML_IM):
            self._formattings_button.set_sensitive(True)
            self._formattings_button.set_tooltip_text(_(
                'Show a list of formattings'))
        else:
            self._formattings_button.set_sensitive(False)
            self._formattings_button.set_tooltip_text(
                _('This contact does not support HTML'))

        # Jingle detection
        if self.contact.supports(NS_JINGLE_ICE_UDP) and \
        app.is_installed('FARSTREAM') and self.contact.resource:
            self.audio_available = self.contact.supports(NS_JINGLE_RTP_AUDIO)
            self.video_available = self.contact.supports(NS_JINGLE_RTP_VIDEO)
        else:
            if self.video_available or self.audio_available:
                self.stop_jingle()
            self.video_available = False
            self.audio_available = False

    def update_all_pep_types(self):
        self._update_pep(PEPEventType.LOCATION)
        self._update_pep(PEPEventType.MOOD)
        self._update_pep(PEPEventType.ACTIVITY)
        self._update_pep(PEPEventType.TUNE)

    def _update_pep(self, type_):
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
            return self.xml.get_object('mood_image')
        if type_ == PEPEventType.ACTIVITY:
            return self.xml.get_object('activity_image')
        if type_ == PEPEventType.TUNE:
            return self.xml.get_object('tune_image')
        if type_ == PEPEventType.LOCATION:
            return self.xml.get_object('location_image')

    @ensure_proper_control
    def _on_mood_received(self, _event):
        self._update_pep(PEPEventType.MOOD)

    @ensure_proper_control
    def _on_activity_received(self, _event):
        self._update_pep(PEPEventType.ACTIVITY)

    @ensure_proper_control
    def _on_tune_received(self, _event):
        self._update_pep(PEPEventType.TUNE)

    @ensure_proper_control
    def _on_location_received(self, _event):
        self._update_pep(PEPEventType.LOCATION)

    @ensure_proper_control
    def _on_nickname_received(self, _event):
        self.update_ui()
        self.parent_win.redraw_tab(self)
        self.parent_win.show_title()

    @ensure_proper_control
    def _on_update_client_info(self, event):
        contact = app.contacts.get_contact(
            self.account, event.jid, event.resource)
        if contact is None:
            return
        self.xml.get_object('phone_image').set_visible(contact.uses_phone)

    def _update_jingle(self, jingle_type):
        if jingle_type not in ('audio', 'video'):
            return
        banner_image = getattr(self, '_' + jingle_type + '_banner_image')
        state = getattr(self, jingle_type + '_state')
        if state == self.JINGLE_STATE_NULL:
            banner_image.hide()
        else:
            banner_image.show()
        if state == self.JINGLE_STATE_CONNECTING:
            banner_image.set_from_icon_name(
                    'network-transmit-symbolic', Gtk.IconSize.MENU)
        elif state == self.JINGLE_STATE_CONNECTION_RECEIVED:
            banner_image.set_from_icon_name(
                    'network-receive-symbolic', Gtk.IconSize.MENU)
        elif state == self.JINGLE_STATE_CONNECTED:
            banner_image.set_from_icon_name(
                    'network-transmit-receive-symbolic', Gtk.IconSize.MENU)
        elif state == self.JINGLE_STATE_ERROR:
            banner_image.set_from_icon_name(
                    'network-error-symbolic', Gtk.IconSize.MENU)
        self.update_toolbar()

    def update_audio(self):
        self._update_jingle('audio')
        hbox = self.xml.get_object('audio_buttons_hbox')
        if self.audio_state == self.JINGLE_STATE_CONNECTED:
            # Set volume from config
            input_vol = app.config.get('audio_input_volume')
            output_vol = app.config.get('audio_output_volume')
            input_vol = max(min(input_vol, 100), 0)
            output_vol = max(min(output_vol, 100), 0)
            self.xml.get_object('mic_hscale').set_value(input_vol)
            self.xml.get_object('sound_hscale').set_value(output_vol)
            # Show vbox
            hbox.set_no_show_all(False)
            hbox.show_all()
        elif not self.audio_sid:
            hbox.set_no_show_all(True)
            hbox.hide()

    def update_video(self):
        self._update_jingle('video')

    def change_resource(self, resource):
        old_full_jid = self.get_full_jid()
        self.resource = resource
        new_full_jid = self.get_full_jid()
        # update app.last_message_time
        if old_full_jid in app.last_message_time[self.account]:
            app.last_message_time[self.account][new_full_jid] = \
                    app.last_message_time[self.account][old_full_jid]
        # update events
        app.events.change_jid(self.account, old_full_jid, new_full_jid)
        # update MessageWindow._controls
        self.parent_win.change_jid(self.account, old_full_jid, new_full_jid)

    def stop_jingle(self, sid=None, reason=None):
        if self.audio_sid and sid in (self.audio_sid, None):
            self.close_jingle_content('audio')
        if self.video_sid and sid in (self.video_sid, None):
            self.close_jingle_content('video')

    def _set_jingle_state(self, jingle_type, state, sid=None, reason=None):
        if jingle_type not in ('audio', 'video'):
            return
        if state in ('connecting', 'connected', 'stop', 'error') and reason:
            info = _('%(type)s state : %(state)s, reason: %(reason)s') % {
                    'type': jingle_type.capitalize(), 'state': state, 'reason': reason}
            self.add_info_message(info)

        states = {'connecting': self.JINGLE_STATE_CONNECTING,
                'connection_received': self.JINGLE_STATE_CONNECTION_RECEIVED,
                'connected': self.JINGLE_STATE_CONNECTED,
                'stop': self.JINGLE_STATE_NULL,
                'error': self.JINGLE_STATE_ERROR}

        jingle_state = states[state]
        if getattr(self, jingle_type + '_state') == jingle_state or state == 'error':
            return

        if state == 'stop' and getattr(self, jingle_type + '_sid') not in (None, sid):
            return

        setattr(self, jingle_type + '_state', jingle_state)

        if jingle_state == self.JINGLE_STATE_NULL:
            setattr(self, jingle_type + '_sid', None)
        if state in ('connection_received', 'connecting'):
            setattr(self, jingle_type + '_sid', sid)

        v = GLib.Variant.new_boolean(jingle_state != self.JINGLE_STATE_NULL)
        getattr(self, jingle_type + '_action').change_state(v)

        getattr(self, 'update_' + jingle_type)()

    def set_audio_state(self, state, sid=None, reason=None):
        self._set_jingle_state('audio', state, sid=sid, reason=reason)

    def set_video_state(self, state, sid=None, reason=None):
        self._set_jingle_state('video', state, sid=sid, reason=reason)

    def _get_audio_content(self):
        session = app.connections[self.account].get_module('Jingle').get_jingle_session(
                self.contact.get_full_jid(), self.audio_sid)
        return session.get_content('audio')

    def on_num_button_pressed(self, widget, num):
        self._get_audio_content()._start_dtmf(num)

    def on_num_button_released(self, released):
        self._get_audio_content()._stop_dtmf()

    def on_mic_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_mic_volume(value / 100)
        # Save volume to config
        app.config.set('audio_input_volume', value)

    def on_sound_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_out_volume(value / 100)
        # Save volume to config
        app.config.set('audio_output_volume', value)

    def on_avatar_eventbox_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3: # right click
            if self.TYPE_ID == message_control.TYPE_CHAT:
                sha = app.contacts.get_avatar_sha(
                    self.account, self.contact.jid)
                name = self.contact.get_shown_name()
            else:
                sha = self.gc_contact.avatar_sha
                name = self.gc_contact.get_shown_name()
            if sha is not None:
                gui_menu_builder.show_save_as_menu(sha, name)
        return True

    def on_location_eventbox_button_release_event(self, widget, event):
        if 'geoloc' in self.contact.pep:
            location = self.contact.pep['geoloc'].data
            if 'lat' in location and 'lon' in location:
                uri = geo_provider_from_location(location['lat'],
                                                 location['lon'])
                open_uri(uri)

    def on_location_eventbox_leave_notify_event(self, widget, event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = get_cursor('LEFT_PTR')
        self.parent_win.window.get_window().set_cursor(cursor)

    def on_location_eventbox_enter_notify_event(self, widget, event):
        cursor = get_cursor('HAND2')
        self.parent_win.window.get_window().set_cursor(cursor)

    def update_ui(self):
        # The name banner is drawn here
        ChatControlBase.update_ui(self)
        self.update_toolbar()

    def _update_banner_state_image(self):
        contact = app.contacts.get_contact_with_highest_priority(
            self.account, self.contact.jid)
        if not contact or self.resource:
            # For transient contacts
            contact = self.contact
        show = contact.show

        # Set banner image
        icon = get_icon_name(show)
        banner_status_img = self.xml.get_object('banner_status_image')
        banner_status_img.set_from_icon_name(icon, Gtk.IconSize.DND)

    def draw_banner_text(self):
        """
        Draw the text in the fat line at the top of the window that houses the
        name, jid
        """
        contact = self.contact
        jid = contact.jid

        banner_name_label = self.xml.get_object('banner_name_label')

        name = contact.get_shown_name()
        if self.resource:
            name += '/' + self.resource
        if self.TYPE_ID == message_control.TYPE_PM:
            name = i18n.direction_mark +  _(
                '%(nickname)s from group chat %(room_name)s') % \
                {'nickname': name, 'room_name': self.room_name}
        name = i18n.direction_mark + GLib.markup_escape_text(name)

        # We know our contacts nick, but if another contact has the same nick
        # in another account we need to also display the account.
        # except if we are talking to two different resources of the same contact
        acct_info = ''
        for account in app.contacts.get_accounts():
            if account == self.account:
                continue
            if acct_info: # We already found a contact with same nick
                break
            for jid in app.contacts.get_jid_list(account):
                other_contact_ = \
                    app.contacts.get_first_contact_from_jid(account, jid)
                if other_contact_.get_shown_name() == \
                self.contact.get_shown_name():
                    acct_info = i18n.direction_mark + ' (%s)' % \
                        GLib.markup_escape_text(
                            app.get_account_label(self.account))
                    break

        status = contact.status
        if status is not None:
            banner_name_label.set_ellipsize(Pango.EllipsizeMode.END)
            self.banner_status_label.set_ellipsize(Pango.EllipsizeMode.END)
            status_reduced = helpers.reduce_chars_newlines(status, max_lines=1)
        else:
            status_reduced = ''
        status_escaped = GLib.markup_escape_text(status_reduced)

        if self.TYPE_ID == 'pm':
            cs = self.gc_contact.chatstate
        else:
            cs = app.contacts.get_combined_chatstate(
                self.account, self.contact.jid)

        if app.config.get('show_chatstate_in_banner'):
            chatstate = helpers.get_uf_chatstate(cs)

            label_text = '<span>%s</span><span size="x-small" weight="light">%s %s</span>' \
                % (name, acct_info, chatstate)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s %s' % (name, acct_info, chatstate)
        else:
            label_text = '<span>%s</span><span size="x-small" weight="light">%s</span>' % \
                    (name, acct_info)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s' % (name, acct_info)

        if status_escaped:
            status_text = self.urlfinder.sub(self.make_href, status_escaped)
            status_text = '<span size="x-small" weight="light">%s</span>' % status_text
            self.banner_status_label.set_tooltip_text(status)
            self.banner_status_label.set_no_show_all(False)
            self.banner_status_label.show()
        else:
            status_text = ''
            self.banner_status_label.hide()
            self.banner_status_label.set_no_show_all(True)

        self.banner_status_label.set_markup(status_text)
        # setup the label that holds name and jid
        banner_name_label.set_markup(label_text)
        banner_name_label.set_tooltip_text(label_tooltip)

    def close_jingle_content(self, jingle_type):
        sid = getattr(self, jingle_type + '_sid')
        if not sid:
            return
        setattr(self, jingle_type + '_sid', None)
        setattr(self, jingle_type + '_state', self.JINGLE_STATE_NULL)
        session = app.connections[self.account].get_module('Jingle').get_jingle_session(
            self.contact.get_full_jid(), sid)
        if session:
            content = session.get_content(jingle_type)
            if content:
                session.remove_content(content.creator, content.name)
        v = GLib.Variant.new_boolean(False)
        getattr(self, jingle_type + '_action').change_state(v)
        getattr(self, 'update_' + jingle_type)()

    def on_jingle_button_toggled(self, state, jingle_type):
        if state:
            if getattr(self, jingle_type + '_state') == \
            self.JINGLE_STATE_NULL:
                if jingle_type == 'video':
                    video_hbox = self.xml.get_object('video_hbox')
                    video_hbox.set_no_show_all(False)
                    if app.config.get('video_see_self'):
                        fixed = self.xml.get_object('outgoing_fixed')
                        fixed.set_no_show_all(False)
                        video_hbox.show_all()
                        out_da = self.xml.get_object('outgoing_drawingarea')
                        out_da.realize()
                        if os.name == 'nt':
                            out_xid = out_da.get_window().handle
                        else:
                            out_xid = out_da.get_window().get_xid()
                    else:
                        out_xid = None
                    video_hbox.show_all()
                    in_da = self.xml.get_object('incoming_drawingarea')
                    in_da.realize()
                    in_xid = in_da.get_window().get_xid()
                    sid = app.connections[self.account].get_module('Jingle').start_video(
                        self.contact.get_full_jid(), in_xid, out_xid)
                else:
                    sid = getattr(app.connections[self.account],
                        'start_' + jingle_type)(self.contact.get_full_jid())
                getattr(self, 'set_' + jingle_type + '_state')('connecting', sid)
        else:
            video_hbox = self.xml.get_object('video_hbox')
            video_hbox.set_no_show_all(True)
            video_hbox.hide()
            fixed = self.xml.get_object('outgoing_fixed')
            fixed.set_no_show_all(True)
            self.close_jingle_content(jingle_type)

    def set_lock_image(self):
        encryption_state = {'visible': self.encryption is not None,
                            'enc_type': self.encryption,
                            'authenticated': False}

        if self.encryption:
            app.plugin_manager.extension_point(
                'encryption_state' + self.encryption, self, encryption_state)

        self._show_lock_image(**encryption_state)

    def _show_lock_image(self, visible, enc_type='', authenticated=False):
        """
        Set lock icon visibility and create tooltip
        """
        if authenticated:
            authenticated_string = _('and authenticated')
            self.lock_image.set_from_icon_name(
                'security-high-symbolic', Gtk.IconSize.MENU)
        else:
            authenticated_string = _('and NOT authenticated')
            self.lock_image.set_from_icon_name(
                'security-low-symbolic', Gtk.IconSize.MENU)

        tooltip = _('%(type)s encryption is active %(authenticated)s') % \
            {'type': enc_type, 'authenticated': authenticated_string}

        self.authentication_button.set_tooltip_text(tooltip)
        self.widget_set_visible(self.authentication_button, not visible)
        self.lock_image.set_sensitive(visible)

    def _on_authentication_button_clicked(self, widget):
        if self.encryption:
            app.plugin_manager.extension_point(
                'encryption_dialog' + self.encryption, self)

    def _nec_mam_decrypted_message_received(self, obj):
        if obj.conn.name != self.account:
            return

        if obj.muc_pm:
            if not obj.with_ == self.contact.get_full_jid():
                return
        else:
            if not obj.with_.bareMatch(self.contact.jid):
                return

        kind = '' # incoming
        if obj.kind == KindConstant.CHAT_MSG_SENT:
            kind = 'outgoing'

        self.add_message(
            obj.msgtxt, kind, tim=obj.timestamp,
            encrypted=obj.encrypted, correct_id=obj.correct_id,
            message_id=obj.message_id, additional_data=obj.additional_data)

    def _nec_decrypted_message_received(self, obj):
        if not obj.msgtxt:
            return True
        if obj.conn.name != self.account:
            return
        if obj.mtype != 'chat':
            return
        if obj.session.control != self:
            return

        typ = ''
        if obj.mtype == 'error':
            typ = 'error'
        if obj.forwarded and obj.sent:
            typ = 'out'

        self.add_message(obj.msgtxt, typ,
            tim=obj.timestamp, encrypted=obj.encrypted, subject=obj.subject,
            xhtml=obj.xhtml, displaymarking=obj.displaymarking,
            msg_log_id=obj.msg_log_id, message_id=obj.message_id, correct_id=obj.correct_id,
            additional_data=obj.additional_data)
        if obj.msg_log_id:
            pw = self.parent_win
            end = self.conv_textview.autoscroll
            if not pw or (pw.get_active_control() and self \
            == pw.get_active_control() and pw.is_active() and end):
                app.logger.set_read_messages([obj.msg_log_id])

    def _message_sent(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.contact.jid:
            return
        if not obj.message:
            return

        self.last_sent_msg = obj.stanza_id
        message_id = obj.msg_iq.getID()

        if obj.label:
            displaymarking = obj.label.getTag('displaymarking')
        else:
            displaymarking = None
        if self.correcting:
            self.correcting = False
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'gajim-msg-correcting')

        self.add_message(obj.message, self.contact.jid, tim=obj.timestamp,
            encrypted=obj.encrypted, xhtml=obj.xhtml,
            displaymarking=displaymarking, message_id=message_id,
            correct_id=obj.correct_id,
            additional_data=obj.additional_data)

    def send_message(self, message, xhtml=None,
                     process_commands=True, attention=False):
        """
        Send a message to contact
        """

        if self.encryption:
            self.sendmessage = True
            app.plugin_manager.extension_point(
                    'send_message' + self.encryption, self)
            if not self.sendmessage:
                return

        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return None

        ChatControlBase.send_message(self,
                                     message,
                                     type_='chat',
                                     xhtml=xhtml,
                                     process_commands=process_commands,
                                     attention=attention)

    def get_our_nick(self):
        return app.nicks[self.account]

    def add_message(self, text, frm='', tim=None, encrypted=None,
                    subject=None, xhtml=None,
                    displaymarking=None, msg_log_id=None, correct_id=None,
                    message_id=None, additional_data=None):
        """
        Print a line in the conversation

        If frm is set to status: it's a status message.
        if frm is set to error: it's an error message. The difference between
                status and error is mainly that with error, msg count as a new message
                (in systray and in control).
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
                name = contact.get_shown_name()
            elif frm == 'print_queue': # incoming message, but do not update time
                kind = 'incoming_queue'
                name = contact.get_shown_name()
            else:
                kind = 'outgoing'
                name = self.get_our_nick()
                if not xhtml and not encrypted and \
                app.config.get('rst_formatting_outgoing_messages'):
                    from gajim.common.rst_xhtml_generator import create_xhtml
                    xhtml = create_xhtml(text)
                    if xhtml:
                        xhtml = '<body xmlns="%s">%s</body>' % (NS_XHTML, xhtml)
        ChatControlBase.add_message(self, text, kind, name, tim,
            subject=subject, old_kind=self.old_msg_kind, xhtml=xhtml,
            displaymarking=displaymarking,
            msg_log_id=msg_log_id, message_id=message_id,
            correct_id=correct_id, additional_data=additional_data,
            encrypted=encrypted)
        if text.startswith('/me ') or text.startswith('/me\n'):
            self.old_msg_kind = None
        else:
            self.old_msg_kind = kind

    def _receipt_received(self, event):
        if event.conn.name != self.account:
            return
        if event.jid != self.contact.jid:
            return

        self.conv_textview.show_xep0184_ack(event.receipt_id)

    def get_tab_label(self):
        unread = ''
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid
        num_unread = len(app.events.get_events(self.account, jid,
                ['printed_' + self.type_id, self.type_id]))
        if num_unread == 1 and not app.config.get('show_unread_tab_icon'):
            unread = '*'
        elif num_unread > 1:
            unread = '[' + str(num_unread) + ']'

        name = self.contact.get_shown_name()
        if self.resource:
            name += '/' + self.resource
        label_str = GLib.markup_escape_text(name)
        if num_unread: # if unread, text in the label becomes bold
            label_str = '<b>' + unread + label_str + '</b>'
        return label_str

    def get_tab_image(self, count_unread=True):
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid

        if app.config.get('show_avatar_in_tabs'):
            scale = self.parent_win.window.get_scale_factor()
            surface = app.contacts.get_avatar(
                self.account, jid, AvatarSize.TAB, scale)
            if surface is not None:
                return surface

        if count_unread:
            num_unread = len(app.events.get_events(self.account, jid,
                    ['printed_' + self.type_id, self.type_id]))
        else:
            num_unread = 0

        transport = None
        if app.jid_is_transport(jid):
            transport = app.get_transport_name_from_jid(jid)

        if num_unread and app.config.get('show_unread_tab_icon'):
            icon_name = get_icon_name('event', transport=transport)
        else:
            contact = app.contacts.get_contact_with_highest_priority(
                    self.account, self.contact.jid)
            if not contact or self.resource:
                # For transient contacts
                contact = self.contact
            icon_name = get_icon_name(contact.show, transport=transport)

        return icon_name

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
            menu = gui_menu_builder.get_contact_menu(self.contact, self.account,
                use_multiple_contacts=False, show_start_chat=False,
                show_encryption=True, control=self,
                show_buttonbar_items=not hide_buttonbar_items)
        return menu

    def shutdown(self):
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        app.plugin_manager.remove_gui_extension_point('chat_control', self)
        app.ged.remove_event_handler('nickname-received', ged.GUI1,
            self._on_nickname_received)
        app.ged.remove_event_handler('mood-received', ged.GUI1,
            self._on_mood_received)
        app.ged.remove_event_handler('activity-received', ged.GUI1,
            self._on_activity_received)
        app.ged.remove_event_handler('tune-received', ged.GUI1,
            self._on_tune_received)
        app.ged.remove_event_handler('location-received', ged.GUI1,
            self._on_location_received)
        app.ged.remove_event_handler('update-client-info', ged.GUI1,
            self._on_update_client_info)
        if self.TYPE_ID == message_control.TYPE_CHAT:
            app.ged.remove_event_handler('update-roster-avatar', ged.GUI1,
                self._nec_update_avatar)
        app.ged.remove_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        app.ged.remove_event_handler('caps-update', ged.GUI1,
            self._nec_caps_received)
        app.ged.remove_event_handler('message-sent', ged.OUT_POSTCORE,
            self._message_sent)
        app.ged.remove_event_handler(
            'mam-decrypted-message-received',
            ged.GUI1, self._nec_mam_decrypted_message_received)
        app.ged.remove_event_handler(
            'decrypted-message-received',
            ged.GUI1, self._nec_decrypted_message_received)
        app.ged.remove_event_handler(
            'receipt-received',
            ged.GUI1, self._receipt_received)

        self.unsubscribe_events()

        # Send 'gone' chatstate
        con = app.connections[self.account]
        con.get_module('Chatstate').set_chatstate(self.contact, Chatstate.GONE)

        for jingle_type in ('audio', 'video'):
            self.close_jingle_content(jingle_type)

        # disconnect self from session
        if self.session:
            self.session.control = None

        # Clean events
        app.events.remove_events(self.account, self.get_full_jid(),
                types=['printed_' + self.type_id, self.type_id])
        # Remove contact instance if contact has been removed
        key = (self.contact.jid, self.account)
        roster = app.interface.roster
        if key in roster.contacts_to_be_removed.keys() and \
        not roster.contact_has_pending_roster_events(self.contact,
        self.account):
            backend = roster.contacts_to_be_removed[key]['backend']
            del roster.contacts_to_be_removed[key]
            roster.remove_contact(self.contact.jid, self.account, force=True,
                backend=backend)
        # remove all register handlers on widgets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]
        self.conv_textview.del_handlers()
        self.msg_textview.destroy()
        # PluginSystem: calling shutdown of super class (ChatControlBase) to let
        # it remove it's GUI extension points
        super(ChatControl, self).shutdown()

    def minimizable(self):
        return False

    def safe_shutdown(self):
        return False

    def allow_shutdown(self, method, on_yes, on_no, _on_minimize):
        time_ = app.last_message_time[self.account][self.get_full_jid()]
        if time.time() - time_ < 2:
            # 2 seconds
            NewConfirmationDialog(
                _('Close'),
                _('You just received a new message '
                  'from %s') % self.contact.jid,
                _('If you close this tab while having chat history disabled, '
                  'this message will be lost.'),
                [DialogButton.make('Cancel',
                                   callback=lambda: on_no(self)),
                 DialogButton.make('Remove',
                                   text=_('Close'),
                                   callback=lambda: on_yes(self))],
                transient_for=self.parent_win.window).show()
            return
        on_yes(self)

    def _nec_chatstate_received(self, event):
        if event.account != self.account:
            return

        if self.TYPE_ID == 'pm':
            if event.contact != self.gc_contact:
                return
        else:
            if event.contact.jid != self.contact.jid:
                return

        self.draw_banner_text()

        # update chatstate in tab for this chat
        if event.contact.is_gc_contact:
            chatstate = event.contact.chatstate
        else:
            chatstate = app.contacts.get_combined_chatstate(
                self.account, self.contact.jid)
        self.parent_win.redraw_tab(self, chatstate)

    def _nec_caps_received(self, obj):
        if obj.conn.name != self.account:
            return
        if self.TYPE_ID == 'chat' and obj.jid != self.contact.jid:
            return
        if self.TYPE_ID == 'pm' and obj.fjid != self.contact.jid:
            return
        self.update_ui()

    def _nec_ping(self, obj):
        if self.contact != obj.contact:
            return
        if obj.name == 'ping-sent':
            self.add_info_message(_('Ping?'))
        elif obj.name == 'ping-reply':
            self.add_info_message(
                _('Pong! (%s seconds)') % obj.seconds)
        elif obj.name == 'ping-error':
            self.add_info_message(_('Error.'))

    def show_avatar(self):
        if not app.config.get('show_avatar_in_chat'):
            return

        scale = self.parent_win.window.get_scale_factor()
        surface = app.contacts.get_avatar(
            self.account, self.contact.jid, AvatarSize.CHAT, scale)

        image = self.xml.get_object('avatar_image')
        image.set_from_surface(surface)

    def _nec_update_avatar(self, obj):
        if obj.account != self.account:
            return
        if obj.jid != self.contact.jid:
            return
        self.show_avatar()

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        if not selection.get_data():
            return

        # get contact info (check for PM = private chat)
        if self.TYPE_ID == message_control.TYPE_PM:
            c = self.gc_contact.as_contact()
        else:
            c = self.contact

        if target_type == self.TARGET_TYPE_URI_LIST:
            # File drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(c, selection, self)
        else:
            # Convert single chat to MUC
            treeview = app.interface.roster.tree
            model = treeview.get_model()
            data = selection.get_data().decode()
            path = treeview.get_selection().get_selected_rows()[1][0]
            iter_ = model.get_iter(path)
            type_ = model[iter_][2]
            if type_ != 'contact':  # Source is not a contact
                return
            dropped_jid = data

            dropped_transport = app.get_transport_name_from_jid(dropped_jid)
            c_transport = app.get_transport_name_from_jid(c.jid)
            if dropped_transport or c_transport:
                return # transport contacts cannot be invited

            dialogs.TransformChatToMUC(self.account, [c.jid], [dropped_jid])

    def restore_conversation(self):
        jid = self.contact.jid
        # don't restore lines if it's a transport
        if app.jid_is_transport(jid):
            return

        # number of messages that are in queue and are already logged, we want
        # to avoid duplication
        pending = len(app.events.get_events(self.account, jid,
                ['chat', 'pm']))
        if self.resource:
            pending += len(app.events.get_events(self.account,
                    self.contact.get_full_jid(), ['chat', 'pm']))

        rows = app.logger.get_last_conversation_lines(
            self.account, jid, pending)

        local_old_kind = None
        self.conv_textview.just_cleared = True
        for row in rows: # time, kind, message, subject, additional_data
            msg = row.message
            additional_data = row.additional_data
            if not msg: # message is empty, we don't print it
                continue
            if row.kind in (KindConstant.CHAT_MSG_SENT,
                            KindConstant.SINGLE_MSG_SENT):
                kind = 'outgoing'
                name = self.get_our_nick()
            elif row.kind in (KindConstant.SINGLE_MSG_RECV,
                            KindConstant.CHAT_MSG_RECV):
                kind = 'incoming'
                name = self.contact.get_shown_name()
            elif row.kind == KindConstant.ERROR:
                kind = 'status'
                name = self.contact.get_shown_name()

            tim = float(row.time)

            xhtml = None
            if msg.startswith('<body '):
                xhtml = msg
            if row.subject:
                msg = _('Subject: %(subject)s\n%(message)s') % \
                    {'subject': row.subject, 'message': msg}
            ChatControlBase.add_message(self,
                                        msg,
                                        kind,
                                        name,
                                        tim,
                                        restored=True,
                                        old_kind=local_old_kind,
                                        xhtml=xhtml,
                                        additional_data=additional_data)
            if row.message.startswith('/me ') or row.message.startswith('/me\n'):
                local_old_kind = None
            else:
                local_old_kind = kind
        if rows:
            self.conv_textview.print_empty_line()

    def read_queue(self):
        """
        Read queue and print messages containted in it
        """
        jid = self.contact.jid
        jid_with_resource = jid
        if self.resource:
            jid_with_resource += '/' + self.resource
        events = app.events.get_events(self.account, jid_with_resource)

        # list of message ids which should be marked as read
        message_ids = []
        for event in events:
            if event.type_ != self.type_id:
                continue
            if event.kind == 'error':
                kind = 'info'
            else:
                kind = 'print_queue'
            if event.sent_forwarded:
                kind = 'out'
            self.add_message(event.message, kind, tim=event.time,
                encrypted=event.encrypted, subject=event.subject,
                xhtml=event.xhtml, displaymarking=event.displaymarking,
                correct_id=event.correct_id, additional_data=event.additional_data)
            if isinstance(event.msg_log_id, int):
                message_ids.append(event.msg_log_id)

            if event.session and not self.session:
                self.set_session(event.session)
        if message_ids:
            app.logger.set_read_messages(message_ids)
        app.events.remove_events(self.account, jid_with_resource,
                types=[self.type_id])

        typ = 'chat' # Is it a normal chat or a pm ?

        # reset to status image in gc if it is a pm
        # Is it a pm ?
        room_jid, nick = app.get_room_and_nick_from_fjid(jid)
        control = app.interface.msg_win_mgr.get_gc_control(room_jid,
                self.account)
        if control and control.type_id == message_control.TYPE_GC:
            control.update_ui()
            control.parent_win.show_title()
            typ = 'pm'

        self.redraw_after_event_removed(jid)
        if self.contact.show in ('offline', 'error'):
            show_offline = app.config.get('showoffline')
            show_transports = app.config.get('show_transports_group')
            if (not show_transports and app.jid_is_transport(jid)) or \
            (not show_offline and typ == 'chat' and \
            len(app.contacts.get_contacts(self.account, jid)) < 2):
                app.interface.roster.remove_to_be_removed(self.contact.jid,
                        self.account)
            elif typ == 'pm':
                control.remove_contact(nick)

    def _on_convert_to_gc_menuitem_activate(self, widget):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

    def got_connected(self):
        ChatControlBase.got_connected(self)
        # Refreshing contact
        contact = app.contacts.get_contact_with_highest_priority(
                self.account, self.contact.jid)
        if isinstance(contact, GC_Contact):
            contact = contact.as_contact()
        if contact:
            self.contact = contact
        self.draw_banner()
        self.update_actions()

    def got_disconnected(self):
        ChatControlBase.got_disconnected(self)
        self.update_actions()

    def update_status_display(self, name, uf_show, status):
        self.update_ui()
        self.parent_win.redraw_tab(self)

        if not app.config.get('print_status_in_chats'):
            return

        if status:
            status = '- %s' % status
        status_line = _('%(name)s is now %(show)s %(status)s') % {
            'name': name, 'show': uf_show, 'status': status or ''}
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
        for b in area.get_children():
            area.remove(b)

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

    def _on_accept_file_request(self, widget, file_props):
        app.interface.instances['file_transfers'].on_file_request_accepted(
            self.account, self.contact, file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_cancel_file_request(self, widget, file_props):
        app.connections[self.account].get_module('Bytestream').send_file_rejection(file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_request(self, file_props):
        """
        Show an InfoBar on top of control
        """
        if app.config.get('use_kib_mib'):
            units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            units = GLib.FormatSizeFlags.DEFAULT

        markup = '<b>%s</b>\n%s' % (_('File Transfer'), file_props.name)
        if file_props.desc:
            markup += '\n(%s)' % file_props.desc
        markup += '\n%s: %s' % (
            _('Size'),
            GLib.format_size_full(file_props.size, units))
        b1 = Gtk.Button.new_with_mnemonic(_('_Accept'))
        b1.connect('clicked', self._on_accept_file_request, file_props)
        b2 = Gtk.Button.new_with_mnemonic(_('_Decline'))
        b2.connect('clicked', self._on_cancel_file_request, file_props)
        self._add_info_bar_message(
            markup,
            [b1, b2],
            file_props,
            Gtk.MessageType.QUESTION)

    def _on_open_ft_folder(self, widget, file_props):
        path = os.path.split(file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            helpers.launch_file_manager(path)
        ev = self._get_file_props_event(file_props, 'file-completed')
        if ev:
            app.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_ok(self, widget, file_props, type_):
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
        b = Gtk.Button.new_with_mnemonic(_('_Close'))
        b.connect('clicked', self._on_ok, file_props, type_)
        self._add_info_bar_message(
            markup,
            [b],
            file_props,
            Gtk.MessageType.ERROR)

    def _on_accept_gc_invitation(self, widget, event):
        if event.continued:
            app.interface.join_gc_room(self.account, str(event.muc),
                app.nicks[self.account], event.password,
                is_continued=True)
        else:
            app.interface.join_gc_minimal(self.account, str(event.muc))

        app.events.remove_events(self.account, self.contact.jid, event=event)

    def _on_cancel_gc_invitation(self, widget, event):
        app.events.remove_events(self.account, self.contact.jid, event=event)

    def _get_gc_invitation(self, event):
        markup = '<b>%s</b>\n%s' % (_('Group Chat Invitation'), event.muc)
        if event.reason:
            markup += '\n(%s)' % event.reason
        b1 = Gtk.Button.new_with_mnemonic(_('_Accept'))
        b1.connect('clicked', self._on_accept_gc_invitation, event)
        b2 = Gtk.Button.new_with_mnemonic(_('_Decline'))
        b2.connect('clicked', self._on_cancel_gc_invitation, event)
        self._add_info_bar_message(
            markup,
            [b1, b2],
            (event.muc, event.reason),
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
            self._got_file_error(event.file_props, event.type_,
                _('File transfer cancelled'),
                _('Connection with peer cannot be established.'))
        elif event.type_ == 'gc-invitation':
            self._get_gc_invitation(event)

    def on_event_removed(self, event_list):
        """
        Called when one or more events are removed from the event list
        """
        for ev in event_list:
            if ev.account != self.account:
                continue
            if ev.jid != self.contact.jid:
                continue
            if ev.type_ not in ('file-request', 'file-completed', 'file-error',
            'file-stopped', 'file-request-error', 'file-send-error',
            'gc-invitation'):
                continue
            i = 0
            removed = False
            for ib_msg in self.info_bar_queue:
                if ev.type_ == 'gc-invitation':
                    if ev.muc == ib_msg[2][0]:
                        self.info_bar_queue.remove(ib_msg)
                        removed = True
                else: # file-*
                    if ib_msg[2] == ev.file_props:
                        self.info_bar_queue.remove(ib_msg)
                        removed = True
                if removed:
                    if i == 0:
                        # We are removing the one currently displayed
                        self.info_bar.set_no_show_all(True)
                        self.info_bar.hide()
                        # show next one?
                        GLib.idle_add(self._info_bar_show_message)
                    break
                i += 1
