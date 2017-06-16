# -*- coding:utf-8 -*-
## src/chat_control.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import time
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GLib
import gtkgui_helpers
import gui_menu_builder
import message_control
import dialogs

from common import logger
from common import gajim
from common import helpers
from common import exceptions
from common import ged
from common import i18n
from common.stanza_session import EncryptedStanzaSession, ArchivingStanzaSession
from common.contacts import GC_Contact
from common.logger import KindConstant
from nbxmpp.protocol import NS_XHTML, NS_XHTML_IM, NS_FILE, NS_MUC
from nbxmpp.protocol import NS_ESESSION
from nbxmpp.protocol import NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO
from nbxmpp.protocol import NS_JINGLE_ICE_UDP, NS_JINGLE_FILE_TRANSFER_5
from nbxmpp.protocol import NS_CHATSTATES
from common.connection_handlers_events import MessageOutgoingEvent
from common.exceptions import GajimGeneralException

from command_system.implementation.hosts import ChatCommands

try:
    import gtkspell
    HAS_GTK_SPELL = True
except (ImportError, ValueError):
    HAS_GTK_SPELL = False

from chat_control_base import ChatControlBase

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
    COMMAND_HOST = ChatCommands

    def __init__(self, parent_win, contact, acct, session, resource=None):
        ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
            'chat_control', contact, acct, resource)

        self.last_recv_message_id = None
        self.last_recv_message_marks = None
        self.last_message_timestamp = None

        # for muc use:
        # widget = self.xml.get_object('muc_window_actions_button')
        self.actions_button = self.xml.get_object('message_window_actions_button')
        id_ = self.actions_button.connect('clicked',
            self.on_actions_button_clicked)
        self.handlers[id_] = self.actions_button

        self._formattings_button = self.xml.get_object('formattings_button')
        self.emoticons_button = self.xml.get_object('emoticons_button')
        self.toggle_emoticons()

        self._add_to_roster_button = self.xml.get_object(
            'add_to_roster_button')
        id_ = self._add_to_roster_button.connect('clicked',
            self._on_add_to_roster_menuitem_activate)
        self.handlers[id_] = self._add_to_roster_button

        self._audio_button = self.xml.get_object('audio_togglebutton')
        id_ = self._audio_button.connect('toggled', self.on_audio_button_toggled)
        self.handlers[id_] = self._audio_button
        # add a special img
        gtkgui_helpers.add_image_to_button(self._audio_button,
            'gajim-mic_inactive')

        self._video_button = self.xml.get_object('video_togglebutton')
        id_ = self._video_button.connect('toggled', self.on_video_button_toggled)
        self.handlers[id_] = self._video_button
        # add a special img
        gtkgui_helpers.add_image_to_button(self._video_button,
            'gajim-cam_inactive')

        self._send_file_button = self.xml.get_object('send_file_button')
        # add a special img for send file button
        pixbuf = gtkgui_helpers.get_icon_pixmap('document-send', quiet=True)
        img = Gtk.Image.new_from_pixbuf(pixbuf)
        self._send_file_button.set_image(img)
        id_ = self._send_file_button.connect('clicked',
            self._on_send_file_menuitem_activate)
        self.handlers[id_] = self._send_file_button

        self._convert_to_gc_button = self.xml.get_object(
            'convert_to_gc_button')
        id_ = self._convert_to_gc_button.connect('clicked',
            self._on_convert_to_gc_menuitem_activate)
        self.handlers[id_] = self._convert_to_gc_button

        self._contact_information_button = self.xml.get_object(
            'contact_information_button')
        id_ = self._contact_information_button.connect('clicked',
            self._on_contact_information_menuitem_activate)
        self.handlers[id_] = self._contact_information_button

        compact_view = gajim.config.get('compact_view')
        self.chat_buttons_set_visible(compact_view)
        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            gajim.config.get('hide_chat_banner'))

        self.authentication_button = self.xml.get_object(
            'authentication_button')
        id_ = self.authentication_button.connect('clicked',
            self._on_authentication_button_clicked)
        self.handlers[id_] = self.authentication_button

        # Add lock image to show chat encryption
        self.lock_image = self.xml.get_object('lock_image')

        # Convert to GC icon
        img = self.xml.get_object('convert_to_gc_button_image')
        img.set_from_pixbuf(gtkgui_helpers.load_icon(
                'muc_active').get_pixbuf())

        self._audio_banner_image = self.xml.get_object('audio_banner_image')
        self._video_banner_image = self.xml.get_object('video_banner_image')
        self.audio_sid = None
        self.audio_state = self.JINGLE_STATE_NULL
        self.audio_available = False
        self.video_sid = None
        self.video_state = self.JINGLE_STATE_NULL
        self.video_available = False

        self.update_toolbar()

        self._pep_images = {}
        self._pep_images['mood'] = self.xml.get_object('mood_image')
        self._pep_images['activity'] = self.xml.get_object('activity_image')
        self._pep_images['tune'] = self.xml.get_object('tune_image')
        self._pep_images['location'] = self.xml.get_object('location_image')
        self.update_all_pep_types()

        # keep timeout id and window obj for possible big avatar
        # it is on enter-notify and leave-notify so no need to be
        # per jid
        self.show_bigger_avatar_timeout_id = None
        self.bigger_avatar_window = None
        self.show_avatar()

        # Hook up signals
        message_tv_buffer = self.msg_textview.get_buffer()
        id_ = message_tv_buffer.connect('changed',
            self._on_message_tv_buffer_changed)
        self.handlers[id_] = message_tv_buffer

        widget = self.xml.get_object('avatar_eventbox')
        widget.set_property('height-request', gajim.config.get(
            'chat_avatar_height'))
        id_ = widget.connect('enter-notify-event',
            self.on_avatar_eventbox_enter_notify_event)
        self.handlers[id_] = widget

        id_ = widget.connect('leave-notify-event',
            self.on_avatar_eventbox_leave_notify_event)
        self.handlers[id_] = widget

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

        self.dtmf_window = self.xml.get_object('dtmf_window')
        self.dtmf_window.get_child().set_direction(Gtk.TextDirection.LTR)
        id_ = self.dtmf_window.connect('focus-out-event',
            self.on_dtmf_window_focus_out_event)
        self.handlers[id_] = self.dtmf_window

        widget = self.xml.get_object('dtmf_button')
        id_ = widget.connect('clicked', self.on_dtmf_button_clicked)
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
            session = gajim.connections[self.account].find_controlless_session(
                self.contact.jid, resource)

        self.setup_seclabel(self.xml.get_object('label_selector'))
        if session:
            session.control = self
            self.session = session

            if session.enable_encryption:
                self.print_esession_details()

        # Enable encryption if needed
        self.no_autonegotiation = False

        self.update_ui()
        self.set_lock_image()

        self.encryption_menu = self.xml.get_object('encryption_menu')
        self.encryption_menu.set_menu_model(
            gui_menu_builder.get_encryption_menu(self.contact, self.type_id))
        self.set_encryption_menu_icon()
        # restore previous conversation
        self.restore_conversation()
        self.msg_textview.grab_focus()

        gajim.ged.register_event_handler('pep-received', ged.GUI1,
            self._nec_pep_received)
        gajim.ged.register_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.register_event_handler('failed-decrypt', ged.GUI1,
            self._nec_failed_decrypt)
        gajim.ged.register_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        gajim.ged.register_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received)

        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        gajim.plugin_manager.gui_extension_point('chat_control', self)

    def subscribe_events(self):
        """
        Register listeners to the events class
        """
        gajim.events.event_added_subscribe(self.on_event_added)
        gajim.events.event_removed_subscribe(self.on_event_removed)

    def unsubscribe_events(self):
        """
        Unregister listeners to the events class
        """
        gajim.events.event_added_unsubscribe(self.on_event_added)
        gajim.events.event_removed_unsubscribe(self.on_event_removed)

    def _update_toolbar(self):
        if (gajim.connections[self.account].connected > 1 and not \
        self.TYPE_ID == 'pm') or (self.contact.show != 'offline' and \
        self.TYPE_ID == 'pm'):
            send_button = self.xml.get_object('send_button')
            send_button.set_sensitive(True)
        # Formatting
        # TODO: find out what encryption allows for xhtml and which not
        if self.contact.supports(NS_XHTML_IM):
            self._formattings_button.set_sensitive(True)
            self._formattings_button.set_tooltip_text(_(
                'Show a list of formattings'))
        else:
            self._formattings_button.set_sensitive(False)
            if self.contact.supports(NS_XHTML_IM):
                self._formattings_button.set_tooltip_text(_('Formatting is not '
                    'available so long as GPG is active'))
            else:
                self._formattings_button.set_tooltip_text(_('This contact does '
                    'not support HTML'))

        # Add to roster
        if not isinstance(self.contact, GC_Contact) \
        and _('Not in Roster') in self.contact.groups and \
        gajim.connections[self.account].roster_supported:
            self._add_to_roster_button.show()
        else:
            self._add_to_roster_button.hide()

        # Jingle detection
        if self.contact.supports(NS_JINGLE_ICE_UDP) and \
        gajim.HAVE_FARSTREAM and self.contact.resource:
            self.audio_available = self.contact.supports(NS_JINGLE_RTP_AUDIO)
            self.video_available = self.contact.supports(NS_JINGLE_RTP_VIDEO)
        else:
            if self.video_available or self.audio_available:
                self.stop_jingle()
            self.video_available = False
            self.audio_available = False

        # Audio buttons
        self._audio_button.set_sensitive(self.audio_available)

        # Video buttons
        self._video_button.set_sensitive(self.video_available)

        # change tooltip text for audio and video buttons if farstream is
        # not installed
        audio_tooltip_text = _('Toggle audio session') + '\n'
        video_tooltip_text = _('Toggle video session') + '\n'
        if not gajim.HAVE_FARSTREAM:
            ext_text = _('Feature not available, see Help->Features')
            self._audio_button.set_tooltip_text(audio_tooltip_text + ext_text)
            self._video_button.set_tooltip_text(video_tooltip_text + ext_text)
        elif not self.audio_available :
            ext_text =_('Feature not supported by remote client')
            self._audio_button.set_tooltip_text(audio_tooltip_text + ext_text)
            self._video_button.set_tooltip_text(video_tooltip_text + ext_text)
        else:
            self._audio_button.set_tooltip_text(audio_tooltip_text[:-1])
            self._video_button.set_tooltip_text(video_tooltip_text[:-1])

        # Send file
        if ((self.contact.supports(NS_FILE) or \
        self.contact.supports(NS_JINGLE_FILE_TRANSFER_5)) and \
        (self.type_id == 'chat' or self.gc_contact.resource)) and \
        self.contact.show != 'offline':
            self._send_file_button.set_sensitive(True)
            self._send_file_button.set_tooltip_text(_('Send files'))
        else:
            self._send_file_button.set_sensitive(False)
            if not (self.contact.supports(NS_FILE) or self.contact.supports(
            NS_JINGLE_FILE_TRANSFER_5)):
                self._send_file_button.set_tooltip_text(_(
                    "This contact does not support file transfer."))
            else:
                self._send_file_button.set_tooltip_text(
                    _("You need to know the real JID of the contact to send "
                    "them a file."))

        # Convert to GC
        if gajim.config.get_per('accounts', self.account, 'is_zeroconf'):
            self._convert_to_gc_button.set_no_show_all(True)
            self._convert_to_gc_button.hide()
        else:
            if self.contact.supports(NS_MUC):
                self._convert_to_gc_button.set_sensitive(True)
            else:
                self._convert_to_gc_button.set_sensitive(False)

        # Information
        if gajim.account_is_disconnected(self.account):
            self._contact_information_button.set_sensitive(False)
        else:
            self._contact_information_button.set_sensitive(True)


    def update_all_pep_types(self):
        for pep_type in self._pep_images:
            self.update_pep(pep_type)

    def update_pep(self, pep_type):
        if isinstance(self.contact, GC_Contact):
            return
        if pep_type not in self._pep_images:
            return
        pep = self.contact.pep
        img = self._pep_images[pep_type]
        if pep_type in pep:
            img.set_from_pixbuf(gtkgui_helpers.get_pep_as_pixbuf(pep[pep_type]))
            img.set_tooltip_markup(pep[pep_type].asMarkupText())
            img.show()
        else:
            img.hide()

    def _nec_pep_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.contact.jid:
            return

        if obj.pep_type == 'nickname':
            self.update_ui()
            self.parent_win.redraw_tab(self)
            self.parent_win.show_title()
        else:
            self.update_pep(obj.pep_type)

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
            banner_image.set_from_stock(
                    Gtk.STOCK_CONVERT, 1)
        elif state == self.JINGLE_STATE_CONNECTION_RECEIVED:
            banner_image.set_from_stock(
                    Gtk.STOCK_NETWORK, 1)
        elif state == self.JINGLE_STATE_CONNECTED:
            banner_image.set_from_stock(
                    Gtk.STOCK_CONNECT, 1)
        elif state == self.JINGLE_STATE_ERROR:
            banner_image.set_from_stock(
                    Gtk.STOCK_DIALOG_WARNING, 1)
        self.update_toolbar()

    def update_audio(self):
        self._update_jingle('audio')
        hbox = self.xml.get_object('audio_buttons_hbox')
        if self.audio_state == self.JINGLE_STATE_CONNECTED:
            # Set volume from config
            input_vol = gajim.config.get('audio_input_volume')
            output_vol = gajim.config.get('audio_output_volume')
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
        # update gajim.last_message_time
        if old_full_jid in gajim.last_message_time[self.account]:
            gajim.last_message_time[self.account][new_full_jid] = \
                    gajim.last_message_time[self.account][old_full_jid]
        # update events
        gajim.events.change_jid(self.account, old_full_jid, new_full_jid)
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
            str = _('%(type)s state : %(state)s, reason: %(reason)s') % {
                    'type': jingle_type.capitalize(), 'state': state, 'reason': reason}
            self.print_conversation(str, 'info')

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

        getattr(self, '_' + jingle_type + '_button').set_active(jingle_state != self.JINGLE_STATE_NULL)

        getattr(self, 'update_' + jingle_type)()

    def set_audio_state(self, state, sid=None, reason=None):
        self._set_jingle_state('audio', state, sid=sid, reason=reason)

    def set_video_state(self, state, sid=None, reason=None):
        self._set_jingle_state('video', state, sid=sid, reason=reason)

    def _get_audio_content(self):
        session = gajim.connections[self.account].get_jingle_session(
                self.contact.get_full_jid(), self.audio_sid)
        return session.get_content('audio')

    def on_num_button_pressed(self, widget, num):
        self._get_audio_content()._start_dtmf(num)

    def on_num_button_released(self, released):
        self._get_audio_content()._stop_dtmf()

    def on_dtmf_button_clicked(self, widget):
        self.dtmf_window.show_all()

    def on_dtmf_window_focus_out_event(self, widget, event):
        self.dtmf_window.hide()

    def on_mic_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_mic_volume(value / 100)
        # Save volume to config
        gajim.config.set('audio_input_volume', value)

    def on_sound_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_out_volume(value / 100)
        # Save volume to config
        gajim.config.set('audio_output_volume', value)

    def on_avatar_eventbox_enter_notify_event(self, widget, event):
        """
        Enter the eventbox area so we under conditions add a timeout to show a
        bigger avatar after 0.5 sec
        """
        jid = self.contact.jid
        avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
        if avatar_pixbuf in ('ask', None):
            return
        avatar_w = avatar_pixbuf.get_width()
        avatar_h = avatar_pixbuf.get_height()

        scaled_buf = self.xml.get_object('avatar_image').get_pixbuf()
        scaled_buf_w = scaled_buf.get_width()
        scaled_buf_h = scaled_buf.get_height()

        # do we have something bigger to show?
        if avatar_w > scaled_buf_w or avatar_h > scaled_buf_h:
            # wait for 0.5 sec in case we leave earlier
            if self.show_bigger_avatar_timeout_id is not None:
                GLib.source_remove(self.show_bigger_avatar_timeout_id)
            self.show_bigger_avatar_timeout_id = GLib.timeout_add(500,
                    self.show_bigger_avatar, widget)

    def on_avatar_eventbox_leave_notify_event(self, widget, event):
        """
        Left the eventbox area that holds the avatar img
        """
        # did we add a timeout? if yes remove it
        if self.show_bigger_avatar_timeout_id is not None:
            GLib.source_remove(self.show_bigger_avatar_timeout_id)
            self.show_bigger_avatar_timeout_id = None

    def on_avatar_eventbox_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3: # right click
            menu = Gtk.Menu()
            menuitem = Gtk.MenuItem.new_with_mnemonic(_('Save _As'))
            id_ = menuitem.connect('activate',
                gtkgui_helpers.on_avatar_save_as_menuitem_activate,
                self.contact.jid, self.contact.get_shown_name())
            self.handlers[id_] = menuitem
            menu.append(menuitem)
            menu.show_all()
            menu.connect('selection-done', lambda w: w.destroy())
            # show the menu
            menu.show_all()
            menu.attach_to_widget(widget, None)
            menu.popup(None, None, None, None, event.button, event.time)
        return True

    def on_location_eventbox_button_release_event(self, widget, event):
        if 'location' in self.contact.pep:
            location = self.contact.pep['location']._pep_specific_data
            if ('lat' in location) and ('lon' in location):
                uri = 'http://www.openstreetmap.org/?' + \
                        'mlat=%(lat)s&mlon=%(lon)s&zoom=16' % {'lat': location['lat'],
                        'lon': location['lon']}
                helpers.launch_browser_mailer('url', uri)

    def on_location_eventbox_leave_notify_event(self, widget, event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = gtkgui_helpers.get_cursor('LEFT_PTR')
        self.parent_win.window.get_window().set_cursor(cursor)

    def on_location_eventbox_enter_notify_event(self, widget, event):
        cursor = gtkgui_helpers.get_cursor('HAND2')
        self.parent_win.window.get_window().set_cursor(cursor)

    def update_ui(self):
        # The name banner is drawn here
        ChatControlBase.update_ui(self)
        self.update_toolbar()

    def _update_banner_state_image(self):
        contact = gajim.contacts.get_contact_with_highest_priority(self.account,
                self.contact.jid)
        if not contact or self.resource:
            # For transient contacts
            contact = self.contact
        show = contact.show
        jid = contact.jid

        # Set banner image
        img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
                size='32', icon_name=show)
        img_16 = gajim.interface.roster.get_appropriate_state_images(jid,
                icon_name=show)
        if show in img_32 and img_32[show].get_pixbuf():
            # we have 32x32! use it!
            banner_image = img_32[show]
            use_size_32 = True
        else:
            banner_image = img_16[show]
            use_size_32 = False

        banner_status_img = self.xml.get_object('banner_status_image')
        if banner_image.get_storage_type() == Gtk.ImageType.ANIMATION:
            banner_status_img.set_from_animation(banner_image.get_animation())
        else:
            pix = banner_image.get_pixbuf()
            if pix is not None:
                if use_size_32:
                    banner_status_img.set_from_pixbuf(pix)
                else: # we need to scale 16x16 to 32x32
                    scaled_pix = pix.scale_simple(32, 32,
                                                    GdkPixbuf.InterpType.BILINEAR)
                    banner_status_img.set_from_pixbuf(scaled_pix)

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
        for account in gajim.contacts.get_accounts():
            if account == self.account:
                continue
            if acct_info: # We already found a contact with same nick
                break
            for jid in gajim.contacts.get_jid_list(account):
                other_contact_ = \
                    gajim.contacts.get_first_contact_from_jid(account, jid)
                if other_contact_.get_shown_name() == \
                self.contact.get_shown_name():
                    acct_info = i18n.direction_mark + ' (%s)' % \
                        GLib.markup_escape_text(self.account)
                    break

        status = contact.status
        if status is not None:
            banner_name_label.set_ellipsize(Pango.EllipsizeMode.END)
            self.banner_status_label.set_ellipsize(Pango.EllipsizeMode.END)
            status_reduced = helpers.reduce_chars_newlines(status, max_lines=1)
        else:
            status_reduced = ''
        status_escaped = GLib.markup_escape_text(status_reduced)

        font_attrs, font_attrs_small = self.get_font_attrs()
        st = gajim.config.get('displayed_chat_state_notifications')
        cs = contact.chatstate
        if cs and st in ('composing_only', 'all'):
            if contact.show == 'offline':
                chatstate = ''
            elif st == 'all' or cs == 'composing':
                chatstate = helpers.get_uf_chatstate(cs)
            else:
                chatstate = ''

            label_text = '<span %s>%s</span><span %s>%s %s</span>' \
                % (font_attrs,  name, font_attrs_small, acct_info, chatstate)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s %s' % (name, acct_info, chatstate)
        else:
            # weight="heavy" size="x-large"
            label_text = '<span %s>%s</span><span %s>%s</span>' % \
                    (font_attrs, name, font_attrs_small, acct_info)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s' % (name, acct_info)

        if status_escaped:
            status_text = self.urlfinder.sub(self.make_href, status_escaped)
            status_text = '<span %s>%s</span>' % (font_attrs_small, status_text)
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
        session = gajim.connections[self.account].get_jingle_session(
                self.contact.get_full_jid(), sid)
        if session:
            content = session.get_content(jingle_type)
            if content:
                session.remove_content(content.creator, content.name)
        getattr(self, '_' + jingle_type + '_button').set_active(False)
        getattr(self, 'update_' + jingle_type)()

    def on_jingle_button_toggled(self, widget, jingle_type):
        img_name = 'gajim-%s_%s' % ({'audio': 'mic', 'video': 'cam'}[jingle_type],
                        {True: 'active', False: 'inactive'}[widget.get_active()])
        path_to_img = gtkgui_helpers.get_icon_path(img_name)

        if widget.get_active():
            if getattr(self, jingle_type + '_state') == \
            self.JINGLE_STATE_NULL:
                if jingle_type == 'video':
                    video_hbox = self.xml.get_object('video_hbox')
                    video_hbox.set_no_show_all(False)
                    if gajim.config.get('video_see_self'):
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
                    sid = gajim.connections[self.account].start_video(
                        self.contact.get_full_jid(), in_xid, out_xid)
                else:
                    sid = getattr(gajim.connections[self.account],
                        'start_' + jingle_type)(self.contact.get_full_jid())
                getattr(self, 'set_' + jingle_type + '_state')('connecting', sid)
        else:
            video_hbox = self.xml.get_object('video_hbox')
            video_hbox.set_no_show_all(True)
            video_hbox.hide()
            fixed = self.xml.get_object('outgoing_fixed')
            fixed.set_no_show_all(True)
            self.close_jingle_content(jingle_type)

        img = getattr(self, '_' + jingle_type + '_button').get_property('image')
        img.set_from_file(path_to_img)

    def on_audio_button_toggled(self, widget):
        self.on_jingle_button_toggled(widget, 'audio')

    def on_video_button_toggled(self, widget):
        self.on_jingle_button_toggled(widget, 'video')

    def set_lock_image(self):
        loggable = self.session and self.session.is_loggable()

        encryption_state = {'visible': self.encryption is not None,
                            'enc_type': self.encryption,
                            'authenticated': False}

        if self.encryption:
            gajim.plugin_manager.extension_point(
                'encryption_state' + self.encryption, self, encryption_state)

        self._show_lock_image(**encryption_state)

    def _show_lock_image(self, visible, enc_type='',
                         authenticated=False):
        """
        Set lock icon visibility and create tooltip
        """
        if authenticated:
            authenticated_string = _('and authenticated')
            img_path = gtkgui_helpers.get_icon_path('security-high')
        else:
            authenticated_string = _('and NOT authenticated')
            img_path = gtkgui_helpers.get_icon_path('security-low')
        self.lock_image.set_from_file(img_path)

        tooltip = _('%(type)s encryption is active %(authenticated)s.') % {'type': enc_type, 'authenticated': authenticated_string}

        self.authentication_button.set_tooltip_text(tooltip)
        self.widget_set_visible(self.authentication_button, not visible)
        self.lock_image.set_sensitive(visible)

    def _on_authentication_button_clicked(self, widget):
        if self.encryption:
            gajim.plugin_manager.extension_point(
                'encryption_dialog' + self.encryption, self)

    def send_message(self, message, keyID='', chatstate=None, xhtml=None,
    process_commands=True, attention=False):
        """
        Send a message to contact
        """

        if self.encryption:
            self.sendmessage = True
            gajim.plugin_manager.extension_point(
                    'send_message' + self.encryption, self)
            if not self.sendmessage:
                return

        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return None

        contact = self.contact
        keyID = contact.keyID

        chatstates_on = gajim.config.get('outgoing_chat_state_notifications') != \
                'disabled'

        chatstate_to_send = None
        if contact is not None:
            if contact.supports(NS_CHATSTATES):
                # send active chatstate on every message (as XEP says)
                chatstate_to_send = 'active'
                contact.our_chatstate = 'active'

                GLib.source_remove(self.possible_paused_timeout_id)
                GLib.source_remove(self.possible_inactive_timeout_id)
                self._schedule_activity_timers()

        def _on_sent(obj, msg_stanza, message, encrypted, xhtml, label):
            id_ = msg_stanza.getID()
            xep0184_id = None
            if self.contact.jid != gajim.get_jid_from_account(self.account):
                if gajim.config.get_per('accounts', self.account, 'request_receipt'):
                    xep0184_id = id_
            if label:
                displaymarking = label.getTag('displaymarking')
            else:
                displaymarking = None
            if self.correcting:
                self.correcting = False
                gtkgui_helpers.remove_css_class(
                    self.msg_textview, 'msgcorrectingcolor')

            self.print_conversation(message, self.contact.jid,
                encrypted=encrypted, xep0184_id=xep0184_id, xhtml=xhtml,
                displaymarking=displaymarking, msg_stanza_id=id_,
                correct_id=obj.correct_id,
                additional_data=obj.additional_data)

        ChatControlBase.send_message(self, message, keyID, type_='chat',
            chatstate=chatstate_to_send, xhtml=xhtml, callback=_on_sent,
            callback_args=[message, self.encryption, xhtml, self.get_seclabel()],
            process_commands=process_commands,
            attention=attention)

    def on_cancel_session_negotiation(self):
        msg = _('Session negotiation cancelled')
        ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

    def print_archiving_session_details(self):
        """
        Print esession settings to textview
        """
        archiving = bool(self.session) and isinstance(self.session,
                ArchivingStanzaSession) and self.session.archiving
        if archiving:
            msg = _('This session WILL be archived on server')
        else:
            msg = _('This session WILL NOT be archived on server')
        ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

    def print_esession_details(self):
        """
        Print esession settings to textview
        """
        e2e_is_active = bool(self.session) and self.session.enable_encryption
        if e2e_is_active:
            msg = _('This session is encrypted')

            if self.session.is_loggable():
                msg += _(' and WILL be logged')
            else:
                msg += _(' and WILL NOT be logged')

            ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

            if not self.session.verified_identity:
                ChatControlBase.print_conversation_line(self, _("Remote contact's identity not verified. Click the shield button for more details."), 'status', '', None)
        else:
            msg = _('E2E encryption disabled')
            ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

        self._show_lock_image(e2e_is_active, 'E2E',
                              self.session and self.session.verified_identity)

    def print_session_details(self, old_session=None):
        if isinstance(self.session, EncryptedStanzaSession) or \
        (old_session and isinstance(old_session, EncryptedStanzaSession)):
            self.print_esession_details()
        elif isinstance(self.session, ArchivingStanzaSession):
            self.print_archiving_session_details()

    def get_our_nick(self):
        return gajim.nicks[self.account]

    def print_conversation(self, text, frm='', tim=None, encrypted=None,
    subject=None, xhtml=None, simple=False, xep0184_id=None,
    displaymarking=None, msg_log_id=None, correct_id=None,
    msg_stanza_id=None, additional_data=None):
        """
        Print a line in the conversation

        If frm is set to status: it's a status message.
        if frm is set to error: it's an error message. The difference between
                status and error is mainly that with error, msg count as a new message
                (in systray and in control).
        If frm is set to info: it's a information message.
        If frm is set to print_queue: it is incomming from queue.
        If frm is set to another value: it's an outgoing message.
        If frm is not set: it's an incomming message.
        """
        contact = self.contact

        if additional_data is None:
            additional_data = {}

        if frm == 'status':
            if not gajim.config.get('print_status_in_chats'):
                return
            kind = 'status'
            name = ''
        elif frm == 'error':
            kind = 'error'
            name = ''
        elif frm == 'info':
            kind = 'info'
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
                gajim.config.get('rst_formatting_outgoing_messages'):
                    from common.rst_xhtml_generator import create_xhtml
                    xhtml = create_xhtml(text)
                    if xhtml:
                        xhtml = '<body xmlns="%s">%s</body>' % (NS_XHTML, xhtml)
        ChatControlBase.print_conversation_line(self, text, kind, name, tim,
            subject=subject, old_kind=self.old_msg_kind, xhtml=xhtml,
            simple=simple, xep0184_id=xep0184_id, displaymarking=displaymarking,
            msg_log_id=msg_log_id, msg_stanza_id=msg_stanza_id,
            correct_id=correct_id, additional_data=additional_data,
            encrypted=encrypted)
        if text.startswith('/me ') or text.startswith('/me\n'):
            self.old_msg_kind = None
        else:
            self.old_msg_kind = kind

    def get_tab_label(self):
        unread = ''
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid
        num_unread = len(gajim.events.get_events(self.account, jid,
                ['printed_' + self.type_id, self.type_id]))
        if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
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

        if gajim.config.get('show_avatar_in_tabs'):
            avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
            if avatar_pixbuf not in ('ask', None):
                avatar_pixbuf = gtkgui_helpers.get_scaled_pixbuf_by_size(
                    avatar_pixbuf, 16, 16)
                return avatar_pixbuf

        if count_unread:
            num_unread = len(gajim.events.get_events(self.account, jid,
                    ['printed_' + self.type_id, self.type_id]))
        else:
            num_unread = 0
        # Set tab image (always 16x16); unread messages show the 'event' image
        tab_img = None

        if num_unread and gajim.config.get('show_unread_tab_icon'):
            img_16 = gajim.interface.roster.get_appropriate_state_images(
                    self.contact.jid, icon_name='event')
            tab_img = img_16['event']
        else:
            contact = gajim.contacts.get_contact_with_highest_priority(
                    self.account, self.contact.jid)
            if not contact or self.resource:
                # For transient contacts
                contact = self.contact
            img_16 = gajim.interface.roster.get_appropriate_state_images(
                    self.contact.jid, icon_name=contact.show)
            tab_img = img_16[contact.show]

        return tab_img

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Set compact view menuitem active state sets active and sensitivity state
        for history_menuitem (False for tranasports) and file_transfer_menuitem 
        and hide()/show() for add_to_roster_menuitem
        """
        if gajim.jid_is_transport(self.contact.jid):
            menu = gui_menu_builder.get_transport_menu(self.contact,
                self.account)
        else:
            menu = gui_menu_builder.get_contact_menu(self.contact, self.account,
                use_multiple_contacts=False, show_start_chat=False,
                show_encryption=True, control=self,
                show_buttonbar_items=not hide_buttonbar_items)
        return menu

    def send_chatstate(self, state, contact=None):
        """
        Send OUR chatstate as STANDLONE chat state message (eg. no body)
        to contact only if new chatstate is different from the previous one
        if jid is not specified, send to active tab
        """
        # JEP 85 does not allow resending the same chatstate
        # this function checks for that and just returns so it's safe to call it
        # with same state.

        # This functions also checks for violation in state transitions
        # and raises RuntimeException with appropriate message
        # more on that http://xmpp.org/extensions/xep-0085.html#statechart

        # do not send if we have chat state notifications disabled
        # that means we won't reply to the <active/> from other peer
        # so we do not broadcast jep85 capabalities
        chatstate_setting = gajim.config.get('outgoing_chat_state_notifications')
        if chatstate_setting == 'disabled':
            return

        # Dont leak presence to contacts
        # which are not allowed to see our status
        if contact and contact.sub in ('to', 'none'):
            return

        if self.contact.jid == gajim.get_jid_from_account(self.account):
            return

        elif chatstate_setting == 'composing_only' and state != 'active' and\
                state != 'composing':
            return

        if contact is None:
            contact = self.parent_win.get_active_contact()
            if contact is None:
                # contact was from pm in MUC, and left the room so contact is None
                # so we cannot send chatstate anymore
                return

        # Don't send chatstates to offline contacts
        if contact.show == 'offline':
            return

        if not contact.supports(NS_CHATSTATES):
            return
        if contact.our_chatstate == False:
            return

        # if the new state we wanna send (state) equals
        # the current state (contact.our_chatstate) then return
        if contact.our_chatstate == state:
            return

        # if wel're inactive prevent composing (XEP violation)
        if contact.our_chatstate == 'inactive' and state == 'composing':
            # go active before
            gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
                account=self.account, jid=self.contact.jid, chatstate='active',
                control=self))
            contact.our_chatstate = 'active'
            self.reset_kbd_mouse_timeout_vars()

        gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
            account=self.account, jid=self.contact.jid, chatstate=state,
            msg_id=contact.msg_log_id, control=self))

        contact.our_chatstate = state
        if state == 'active':
            self.reset_kbd_mouse_timeout_vars()

    def shutdown(self):
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        gajim.plugin_manager.remove_gui_extension_point('chat_control', self)

        gajim.ged.remove_event_handler('pep-received', ged.GUI1,
            self._nec_pep_received)
        gajim.ged.remove_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.remove_event_handler('failed-decrypt', ged.GUI1,
            self._nec_failed_decrypt)
        gajim.ged.remove_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        gajim.ged.remove_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received)

        self.unsubscribe_events()

        # Send 'gone' chatstate
        self.send_chatstate('gone', self.contact)
        self.contact.chatstate = None
        self.contact.our_chatstate = None

        for jingle_type in ('audio', 'video'):
            self.close_jingle_content(jingle_type)

        # disconnect self from session
        if self.session:
            self.session.control = None

        # Remove bigger avatar window
        if self.bigger_avatar_window:
            self.bigger_avatar_window.destroy()
        # Clean events
        gajim.events.remove_events(self.account, self.get_full_jid(),
                types=['printed_' + self.type_id, self.type_id])
        # Remove contact instance if contact has been removed
        key = (self.contact.jid, self.account)
        roster = gajim.interface.roster
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
        if gajim.config.get('use_speller') and HAS_GTK_SPELL:
            spell_obj = gtkspell.get_from_text_view(self.msg_textview)
            if spell_obj:
                spell_obj.detach()
        self.msg_textview.destroy()
        # PluginSystem: calling shutdown of super class (ChatControlBase) to let
        # it remove it's GUI extension points
        super(ChatControl, self).shutdown()

    def minimizable(self):
        return False

    def safe_shutdown(self):
        return False

    def allow_shutdown(self, method, on_yes, on_no, on_minimize):
        if time.time() - gajim.last_message_time[self.account]\
        [self.get_full_jid()] < 2:
            # 2 seconds

            def on_ok():
                on_yes(self)

            def on_cancel():
                on_no(self)

            dialogs.ConfirmationDialog(
                #%s is being replaced in the code with JID
                _('You just received a new message from "%s"') % \
                self.contact.jid,
                _('If you close this tab and you have history disabled, '\
                'this message will be lost.'), on_response_ok=on_ok,
                on_response_cancel=on_cancel,
                transient_for=self.parent_win.window)
            return
        on_yes(self)

    def _nec_chatstate_received(self, obj):
        """
        Handle incoming chatstate that jid SENT TO us
        """
        self.draw_banner_text()
        # update chatstate in tab for this chat
        self.parent_win.redraw_tab(self, self.contact.chatstate)

    def _nec_caps_received(self, obj):
        if obj.conn.name != self.account:
            return
        if self.TYPE_ID == 'chat' and obj.jid != self.contact.jid:
            return
        if self.TYPE_ID == 'pm' and obj.fjid != self.contact.jid:
            return
        self.update_ui()

    def _nec_ping_reply(self, obj):
        if obj.control:
            if obj.control != self:
                return
        else:
            if self.contact != obj.contact:
                return
        self.print_conversation(_('Pong! (%s s.)') % obj.seconds, 'status')

    def set_control_active(self, state):
        ChatControlBase.set_control_active(self, state)
        # Hide bigger avatar window
        if self.bigger_avatar_window:
            self.bigger_avatar_window.destroy()
            self.bigger_avatar_window = None
            # Re-show the small avatar
            self.show_avatar()

    def show_avatar(self):
        if not gajim.config.get('show_avatar_in_chat'):
            return

        jid_with_resource = self.contact.get_full_jid()
        pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid_with_resource)
        if pixbuf == 'ask':
            # we don't have the vcard
            if self.TYPE_ID == message_control.TYPE_PM:
                if self.gc_contact.jid:
                    # We know the real jid of this contact
                    real_jid = self.gc_contact.jid
                    if self.gc_contact.resource:
                        real_jid += '/' + self.gc_contact.resource
                else:
                    real_jid = jid_with_resource
                gajim.connections[self.account].request_vcard(real_jid,
                        jid_with_resource)
            else:
                gajim.connections[self.account].request_vcard(jid_with_resource)
            return
        elif pixbuf:
            scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'chat')
        else:
            scaled_pixbuf = None

        image = self.xml.get_object('avatar_image')
        image.set_from_pixbuf(scaled_pixbuf)
        image.show_all()

    def _nec_vcard_received(self, obj):
        if obj.conn.name != self.account:
            return
        j = gajim.get_jid_without_resource(self.contact.jid)
        if obj.jid != j:
            return
        self.show_avatar()

    def _on_drag_data_received(self, widget, context, x, y, selection,
            target_type, timestamp):
        if not selection.get_data():
            return
        if self.TYPE_ID == message_control.TYPE_PM:
            c = self.gc_contact
        else:
            c = self.contact
        if target_type == self.TARGET_TYPE_URI_LIST:
            if not c.resource: # If no resource is known, we can't send a file
                return
            uri = selection.get_data().strip()
            uri_splitted = uri.split() # we may have more than one file dropped
            for uri in uri_splitted:
                path = helpers.get_file_path_from_dnd_dropped_uri(uri)
                if os.path.isfile(path): # is it file?
                    ft = gajim.interface.instances['file_transfers']
                    ft.send_file(self.account, c, path)
            return

        # chat2muc
        treeview = gajim.interface.roster.tree
        model = treeview.get_model()
        data = selection.get_data()
        path = treeview.get_selection().get_selected_rows()[1][0]
        iter_ = model.get_iter(path)
        type_ = model[iter_][2]
        if type_ != 'contact': # source is not a contact
            return
        dropped_jid = data

        dropped_transport = gajim.get_transport_name_from_jid(dropped_jid)
        c_transport = gajim.get_transport_name_from_jid(c.jid)
        if dropped_transport or c_transport:
            return # transport contacts cannot be invited

        dialogs.TransformChatToMUC(self.account, [c.jid], [dropped_jid])

    def _on_message_tv_buffer_changed(self, textbuffer):
        super()._on_message_tv_buffer_changed(textbuffer)
        if textbuffer.get_char_count() and self.encryption:
            gajim.plugin_manager.extension_point(
                'typing' + self.encryption, self)
            if (not self.session or not self.session.status) and \
            gajim.connections[self.account].archiving_136_supported:
                self.begin_archiving_negotiation()

    def restore_conversation(self):
        jid = self.contact.jid
        # don't restore lines if it's a transport
        if gajim.jid_is_transport(jid):
            return

        # How many lines to restore and when to time them out
        restore_how_many = gajim.config.get('restore_lines')
        if restore_how_many <= 0:
            return
        timeout = gajim.config.get('restore_timeout') # in minutes

        # number of messages that are in queue and are already logged, we want
        # to avoid duplication
        pending_how_many = len(gajim.events.get_events(self.account, jid,
                ['chat', 'pm']))
        if self.resource:
            pending_how_many += len(gajim.events.get_events(self.account,
                    self.contact.get_full_jid(), ['chat', 'pm']))

        rows = gajim.logger.get_last_conversation_lines(jid, restore_how_many,
                pending_how_many, timeout, self.account)

        local_old_kind = None
        self.conv_textview.just_cleared = True
        for row in rows: # row[0] time, row[1] has kind, row[2] the message, row[3] subject, row[4] additional_data
            msg = row[2]
            additional_data = row[4]
            if not msg: # message is empty, we don't print it
                continue
            if row[1] in (KindConstant.CHAT_MSG_SENT,
                            KindConstant.SINGLE_MSG_SENT):
                kind = 'outgoing'
                name = self.get_our_nick()
            elif row[1] in (KindConstant.SINGLE_MSG_RECV,
                            KindConstant.CHAT_MSG_RECV):
                kind = 'incoming'
                name = self.contact.get_shown_name()
            elif row[1] == KindConstant.ERROR:
                kind = 'status'
                name = self.contact.get_shown_name()

            tim = float(row[0])

            if gajim.config.get('restored_messages_small'):
                small_attr = ['small']
            else:
                small_attr = []
            xhtml = None
            if msg.startswith('<body '):
                xhtml = msg
            if row[3]:
                msg = _('Subject: %(subject)s\n%(message)s') % \
                    {'subject': row[3], 'message': msg}
            ChatControlBase.print_conversation_line(self, msg, kind, name,
                tim, small_attr, small_attr + ['restored_message'],
                small_attr + ['restored_message'], False,
                old_kind=local_old_kind, xhtml=xhtml, additional_data=additional_data)
            if row[2].startswith('/me ') or row[2].startswith('/me\n'):
                local_old_kind = None
            else:
                local_old_kind = kind
        if len(rows):
            self.conv_textview.print_empty_line()

    def read_queue(self):
        """
        Read queue and print messages containted in it
        """
        jid = self.contact.jid
        jid_with_resource = jid
        if self.resource:
            jid_with_resource += '/' + self.resource
        events = gajim.events.get_events(self.account, jid_with_resource)

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
            self.print_conversation(event.message, kind, tim=event.time,
                encrypted=event.encrypted, subject=event.subject,
                xhtml=event.xhtml, displaymarking=event.displaymarking,
                correct_id=event.correct_id)
            if isinstance(event.msg_log_id, int):
                message_ids.append(event.msg_log_id)

            if event.session and not self.session:
                self.set_session(event.session)
        if message_ids:
            gajim.logger.set_read_messages(message_ids)
        gajim.events.remove_events(self.account, jid_with_resource,
                types=[self.type_id])

        typ = 'chat' # Is it a normal chat or a pm ?

        # reset to status image in gc if it is a pm
        # Is it a pm ?
        room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
        control = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
                self.account)
        if control and control.type_id == message_control.TYPE_GC:
            control.update_ui()
            control.parent_win.show_title()
            typ = 'pm'

        self.redraw_after_event_removed(jid)
        if (self.contact.show in ('offline', 'error')):
            show_offline = gajim.config.get('showoffline')
            show_transports = gajim.config.get('show_transports_group')
            if (not show_transports and gajim.jid_is_transport(jid)) or \
            (not show_offline and typ == 'chat' and \
            len(gajim.contacts.get_contacts(self.account, jid)) < 2):
                gajim.interface.roster.remove_to_be_removed(self.contact.jid,
                        self.account)
            elif typ == 'pm':
                control.remove_contact(nick)

    def show_bigger_avatar(self, small_avatar):
        """
        Resize the avatar, if needed, so it has at max half the screen size and
        shows it
        """
        #if not small_avatar.window:
            ### Tab has been closed since we hovered the avatar
            #return
        avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(
                self.contact.jid)
        if avatar_pixbuf in ('ask', None):
            return
        # Hide the small avatar
        # this code hides the small avatar when we show a bigger one in case
        # the avatar has a transparency hole in the middle
        # so when we show the big one we avoid seeing the small one behind.
        # It's why I set it transparent.
        image = self.xml.get_object('avatar_image')
        pixbuf = image.get_pixbuf()
        pixbuf.fill(0xffffff00) # RGBA
        image.set_from_pixbuf(pixbuf)
        #image.queue_draw()

        screen_w = Gdk.Screen.width()
        screen_h = Gdk.Screen.height()
        avatar_w = avatar_pixbuf.get_width()
        avatar_h = avatar_pixbuf.get_height()
        half_scr_w = screen_w / 2
        half_scr_h = screen_h / 2
        if avatar_w > half_scr_w:
            avatar_w = half_scr_w
        if avatar_h > half_scr_h:
            avatar_h = half_scr_h
        # we should make the cursor visible
        # gtk+ doesn't make use of the motion notify on gtkwindow by default
        # so this line adds that

        alloc = small_avatar.get_allocation()
        # make the bigger avatar window show up centered
        small_avatar_x, small_avatar_y = alloc.x, alloc.y
        translated_coordinates = small_avatar.translate_coordinates(
            gajim.interface.roster.window, 0, 0)
        if translated_coordinates:
            small_avatar_x, small_avatar_y = translated_coordinates
        roster_x, roster_y  = self.parent_win.window.get_window().get_origin()[1:]
        center_x = roster_x + small_avatar_x + (alloc.width / 2)
        center_y = roster_y + small_avatar_y + (alloc.height / 2)
        pos_x, pos_y = center_x - (avatar_w / 2), center_y - (avatar_h / 2)

        dialogs.BigAvatarWindow(avatar_pixbuf, pos_x, pos_y, avatar_w,
            avatar_h, self.show_avatar)

        self.show_bigger_avatar_timeout_id = None

    def _on_send_file_menuitem_activate(self, widget):
        self._on_send_file()

    def _on_add_to_roster_menuitem_activate(self, widget):
        dialogs.AddNewContactWindow(self.account, self.contact.jid)

    def _on_contact_information_menuitem_activate(self, widget):
        gajim.interface.roster.on_info(widget, self.contact, self.account)

    def _on_convert_to_gc_menuitem_activate(self, widget):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

    def activate_esessions(self):
        if not (self.session and self.session.enable_encryption):
            self.begin_e2e_negotiation()

    def terminate_esessions(self):
        if not (self.session and self.session.enable_encryption):
            return
        # e2e was enabled, disable it
        jid = str(self.session.jid)
        thread_id = self.session.thread_id

        self.session.terminate_e2e()

        gajim.connections[self.account].delete_session(jid, thread_id)

        # presumably the user had a good reason to shut it off, so
        # disable autonegotiation too
        self.no_autonegotiation = True

    def begin_negotiation(self):
        self.no_autonegotiation = True

        if not self.session:
            fjid = self.contact.get_full_jid()
            new_sess = gajim.connections[self.account].make_new_session(fjid, type_=self.type_id)
            self.set_session(new_sess)

    def begin_e2e_negotiation(self):
        self.begin_negotiation()
        self.session.resource = self.contact.resource
        self.session.negotiate_e2e(False)

    def begin_archiving_negotiation(self):
        self.begin_negotiation()
        self.session.negotiate_archiving()

    def _nec_failed_decrypt(self, obj):
        if obj.session != self.session:
            return

        details = _('Unable to decrypt message from %s\nIt may have been '
            'tampered with.') % obj.fjid
        self.print_conversation_line(details, 'status', '', obj.timestamp)

        # terminate the session
        thread_id = self.session.thread_id
        self.session.terminate_e2e()
        obj.conn.delete_session(obj.fjid, thread_id)

        # restart the session
        self.begin_e2e_negotiation()

        # Stop emission so it doesn't go to gui_interface
        return True

    def got_connected(self):
        ChatControlBase.got_connected(self)
        # Refreshing contact
        contact = gajim.contacts.get_contact_with_highest_priority(
                self.account, self.contact.jid)
        if isinstance(contact, GC_Contact):
            contact = contact.as_contact()
        if contact:
            self.contact = contact
        self.draw_banner()
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(True)

    def got_disconnected(self):
        # Emoticons button
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(False)
        # Add to roster
        self._add_to_roster_button.hide()
        # Audio button
        self._audio_button.set_sensitive(False)
        # Video button
        self._video_button.set_sensitive(False)
        # Send file button
        self._send_file_button.set_tooltip_text('')
        self._send_file_button.set_sensitive(False)
        # Convert to GC button
        self._convert_to_gc_button.set_sensitive(False)

        ChatControlBase.got_disconnected(self)

    def update_status_display(self, name, uf_show, status):
        """
        Print the contact's status and update the status/GPG image
        """
        self.update_ui()
        self.parent_win.redraw_tab(self)

        self.print_conversation(_('%(name)s is now %(status)s') % {'name': name,
                'status': uf_show}, 'status')

        if status:
            self.print_conversation(' (', 'status', simple=True)
            self.print_conversation('%s' % (status), 'status', simple=True)
            self.print_conversation(')', 'status', simple=True)

    def _info_bar_show_message(self):
        if self.info_bar.get_visible():
            # A message is already shown
            return
        if not self.info_bar_queue:
            return
        markup, buttons, args, type_ = self.info_bar_queue[0]
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
        evs = gajim.events.get_events(self.account, self.contact.jid, [type_])
        for ev in evs:
            if ev.file_props == file_props:
                return ev
        return None

    def _on_accept_file_request(self, widget, file_props):
        gajim.interface.instances['file_transfers'].on_file_request_accepted(
            self.account, self.contact, file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_cancel_file_request(self, widget, file_props):
        gajim.connections[self.account].send_file_rejection(file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_request(self, file_props):
        """
        Show an InfoBar on top of control
        """
        markup = '<b>%s:</b> %s' % (_('File transfer'), file_props.name)
        if file_props.desc:
            markup += ' (%s)' % file_props.desc
        markup += '\n%s: %s' % (_('Size'), helpers.convert_bytes(
            file_props.size))
        b1 = Gtk.Button(_('_Accept'))
        b1.connect('clicked', self._on_accept_file_request, file_props)
        b2 = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b2.connect('clicked', self._on_cancel_file_request, file_props)
        self._add_info_bar_message(markup, [b1, b2], file_props,
            Gtk.MessageType.QUESTION)

    def _on_open_ft_folder(self, widget, file_props):
        path = os.path.split(file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            helpers.launch_file_manager(path)
        ev = self._get_file_props_event(file_props, 'file-completed')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_ok(self, widget, file_props, type_):
        ev = self._get_file_props_event(file_props, type_)
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_completed(self, file_props):
        markup = '<b>%s:</b> %s' % (_('File transfer completed'),
            file_props.name)
        if file_props.desc:
            markup += ' (%s)' % file_props.desc
        b1 = Gtk.Button.new_with_mnemonic(_('Open _Containing Folder'))
        b1.connect('clicked', self._on_open_ft_folder, file_props)
        b2 = Gtk.Button(stock=Gtk.STOCK_OK)
        b2.connect('clicked', self._on_ok, file_props, 'file-completed')
        self._add_info_bar_message(markup, [b1, b2], file_props)

    def _got_file_error(self, file_props, type_, pri_txt, sec_txt):
        markup = '<b>%s:</b> %s' % (pri_txt, sec_txt)
        b = Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', self._on_ok, file_props, type_)
        self._add_info_bar_message(markup, [b], file_props, Gtk.MessageType.ERROR)

    def _on_accept_gc_invitation(self, widget, event):
        try:
            if event.is_continued:
                gajim.interface.join_gc_room(self.account, event.room_jid,
                    gajim.nicks[self.account], event.password,
                    is_continued=True)
            else:
                dialogs.JoinGroupchatWindow(self.account, event.room_jid)
        except GajimGeneralException:
            pass
        gajim.events.remove_events(self.account, self.contact.jid, event=event)

    def _on_cancel_gc_invitation(self, widget, event):
        gajim.events.remove_events(self.account, self.contact.jid, event=event)

    def _get_gc_invitation(self, event):
        markup = '<b>%s:</b> %s' % (_('Groupchat Invitation'), event.room_jid)
        if event.comment:
            markup += ' (%s)' % event.comment
        b1 = Gtk.Button(_('_Join'))
        b1.connect('clicked', self._on_accept_gc_invitation, event)
        b2 = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b2.connect('clicked', self._on_cancel_gc_invitation, event)
        self._add_info_bar_message(markup, [b1, b2], (event.room_jid,
            event.comment), Gtk.MessageType.QUESTION)

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
                    if ev.room_jid == ib_msg[2][0]:
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
