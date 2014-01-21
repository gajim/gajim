# -*- coding:utf-8 -*-
## src/config.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
##                         Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
import os, sys
import common.config
import common.sleepy
from common.i18n import Q_

import gtkgui_helpers
import dialogs
import cell_renderer_image
import message_control
import chat_control
import dataforms_widget
import profile_window

try:
    import gtkspell
    HAS_GTK_SPELL = True
except ImportError:
    HAS_GTK_SPELL = False

from common import helpers
from common import gajim
from common import connection
from common import passwords
from common.zeroconf import connection_zeroconf
from common import dataforms
from common import gpg
from common import ged

try:
    from common.multimedia_helpers import AudioInputManager, AudioOutputManager
    from common.multimedia_helpers import VideoInputManager, VideoOutputManager
    HAS_GST = True
except ImportError:
    HAS_GST = False

from common.exceptions import GajimGeneralException
from common.connection_handlers_events import InformationEvent

#---------- PreferencesWindow class -------------#
class PreferencesWindow:
    """
    Class for Preferences window
    """

    def on_preferences_window_destroy(self, widget):
        """
        Close window
        """
        del gajim.interface.instances['preferences']

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self):
        """
        Initialize Preferences window
        """
        self.xml = gtkgui_helpers.get_gtk_builder('preferences_window.ui')
        self.window = self.xml.get_object('preferences_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        self.notebook = self.xml.get_object('preferences_notebook')
        self.one_window_type_combobox =\
                self.xml.get_object('one_window_type_combobox')
        self.iconset_combobox = self.xml.get_object('iconset_combobox')
        self.notify_on_signin_checkbutton = self.xml.get_object(
                'notify_on_signin_checkbutton')
        self.notify_on_signout_checkbutton = self.xml.get_object(
                'notify_on_signout_checkbutton')
        self.auto_popup_away_checkbutton = self.xml.get_object(
                'auto_popup_away_checkbutton')
        self.sound_dnd_checkbutton = self.xml.get_object('sound_dnd_checkbutton')
        self.auto_away_checkbutton = self.xml.get_object('auto_away_checkbutton')
        self.auto_away_time_spinbutton = self.xml.get_object(
                'auto_away_time_spinbutton')
        self.auto_away_message_entry = self.xml.get_object(
                'auto_away_message_entry')
        self.auto_xa_checkbutton = self.xml.get_object('auto_xa_checkbutton')
        self.auto_xa_time_spinbutton = self.xml.get_object(
                'auto_xa_time_spinbutton')
        self.auto_xa_message_entry = self.xml.get_object('auto_xa_message_entry')

        ### General tab ###
        # Display avatars in roster
        st = gajim.config.get('show_avatars_in_roster')
        self.xml.get_object('show_avatars_in_roster_checkbutton'). \
                set_active(st)

        # Display status msg under contact name in roster
        st = gajim.config.get('show_status_msgs_in_roster')
        self.xml.get_object('show_status_msgs_in_roster_checkbutton'). \
                set_active( st)

        # Display PEP in roster
        st1 = gajim.config.get('show_mood_in_roster')
        st2 = gajim.config.get('show_activity_in_roster')
        st3 = gajim.config.get('show_tunes_in_roster')
        st4 = gajim.config.get('show_location_in_roster')
        w = self.xml.get_object('show_pep_in_roster_checkbutton')
        if st1 == st2 == st3 == st4:
            w.set_active(st1)
        else:
            w.set_inconsistent(True)

        # Sort contacts by show
        st = gajim.config.get('sort_by_show_in_roster')
        self.xml.get_object('sort_by_show_in_roster_checkbutton').set_active(st)
        st = gajim.config.get('sort_by_show_in_muc')
        self.xml.get_object('sort_by_show_in_muc_checkbutton').set_active(st)

        # emoticons
        emoticons_combobox = self.xml.get_object('emoticons_combobox')
        emoticons_list = os.listdir(os.path.join(gajim.DATA_DIR, 'emoticons'))
        # user themes
        if os.path.isdir(gajim.MY_EMOTS_PATH):
            emoticons_list += os.listdir(gajim.MY_EMOTS_PATH)
        renderer_text = Gtk.CellRendererText()
        emoticons_combobox.pack_start(renderer_text, True)
        emoticons_combobox.add_attribute(renderer_text, 'text', 0)
        model = Gtk.ListStore(str)
        emoticons_combobox.set_model(model)
        l = []
        for dir_ in emoticons_list:
            if not os.path.isdir(os.path.join(gajim.DATA_DIR, 'emoticons', dir_)) \
            and not os.path.isdir(os.path.join(gajim.MY_EMOTS_PATH, dir_)) :
                continue
            if dir_ != '.svn':
                l.append(dir_)
        l.append(_('Disabled'))
        for i in range(len(l)):
            model.append([l[i]])
            if gajim.config.get('emoticons_theme') == l[i]:
                emoticons_combobox.set_active(i)
        if not gajim.config.get('emoticons_theme'):
            emoticons_combobox.set_active(len(l)-1)

        # Set default for single window type
        choices = common.config.opt_one_window_types
        type_ = gajim.config.get('one_message_window')
        if type_ in choices:
            self.one_window_type_combobox.set_active(choices.index(type_))
        else:
            self.one_window_type_combobox.set_active(0)

        # Show roster on startup
        show_roster_combobox = self.xml.get_object('show_roster_on_startup')
        choices = common.config.opt_show_roster_on_startup
        type_ = gajim.config.get('show_roster_on_startup')
        if type_ in choices:
            show_roster_combobox.set_active(choices.index(type_))
        else:
            show_roster_combobox.set_active(0)

        # Compact View
        st = gajim.config.get('compact_view')
        self.xml.get_object('compact_view_checkbutton').set_active(st)

        # Ignore XHTML
        st = gajim.config.get('ignore_incoming_xhtml')
        self.xml.get_object('xhtml_checkbutton').set_active(st)

        # use speller
        if HAS_GTK_SPELL:
            st = gajim.config.get('use_speller')
            self.xml.get_object('speller_checkbutton').set_active(st)
        else:
            self.xml.get_object('speller_checkbutton').set_sensitive(False)

        # XEP-0184 positive ack
        st = gajim.config.get('positive_184_ack')
        self.xml.get_object('positive_184_ack_checkbutton').set_active(st)

        ### Style tab ###
        # Themes
        theme_combobox = self.xml.get_object('theme_combobox')
        cell = Gtk.CellRendererText()
        theme_combobox.pack_start(cell, True)
        theme_combobox.add_attribute(cell, 'text', 0)
        self.update_theme_list()

        # iconset
        iconsets_list = os.listdir(os.path.join(gajim.DATA_DIR, 'iconsets'))
        if os.path.isdir(gajim.MY_ICONSETS_PATH):
            iconsets_list += os.listdir(gajim.MY_ICONSETS_PATH)
        # new model, image in 0, string in 1
        model = Gtk.ListStore(Gtk.Image, str)
        renderer_image = cell_renderer_image.CellRendererImage(0, 0)
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property('xpad', 5)
        self.iconset_combobox.pack_start(renderer_image, False)
        self.iconset_combobox.pack_start(renderer_text, True)
        self.iconset_combobox.add_attribute(renderer_text, 'text', 1)
        self.iconset_combobox.add_attribute(renderer_image, 'image', 0)
        self.iconset_combobox.set_model(model)
        l = []
        for dir in iconsets_list:
            if not os.path.isdir(os.path.join(gajim.DATA_DIR, 'iconsets', dir)) \
            and not os.path.isdir(os.path.join(gajim.MY_ICONSETS_PATH, dir)):
                continue
            if dir != '.svn' and dir != 'transports':
                l.append(dir)
        if l.count == 0:
            l.append(' ')
        for i in range(len(l)):
            preview = Gtk.Image()
            files = []
            files.append(os.path.join(helpers.get_iconset_path(l[i]), '16x16',
                    'online.png'))
            files.append(os.path.join(helpers.get_iconset_path(l[i]), '16x16',
                    'online.gif'))
            for file_ in files:
                if os.path.exists(file_):
                    preview.set_from_file(file_)
            model.append([preview, l[i]])
            if gajim.config.get('iconset') == l[i]:
                self.iconset_combobox.set_active(i)

        # Use transports iconsets
        st = gajim.config.get('use_transports_iconsets')
        self.xml.get_object('transports_iconsets_checkbutton').set_active(st)

        # Color widgets
        self.draw_color_widgets()

        # Font for messages
        font = gajim.config.get('conversation_font')
        # try to set default font for the current desktop env
        fontbutton = self.xml.get_object('conversation_fontbutton')
        if font == '':
            fontbutton.set_sensitive(False)
            self.xml.get_object('default_chat_font').set_active(True)
        else:
            fontbutton.set_font_name(font)

        ### Personal Events tab ###
        # outgoing send chat state notifications
        st = gajim.config.get('outgoing_chat_state_notifications')
        combo = self.xml.get_object('outgoing_chat_states_combobox')
        if st == 'all':
            combo.set_active(0)
        elif st == 'composing_only':
            combo.set_active(1)
        else: # disabled
            combo.set_active(2)

        # displayed send chat state notifications
        st = gajim.config.get('displayed_chat_state_notifications')
        combo = self.xml.get_object('displayed_chat_states_combobox')
        if st == 'all':
            combo.set_active(0)
        elif st == 'composing_only':
            combo.set_active(1)
        else: # disabled
            combo.set_active(2)


        ### Notifications tab ###
        # On new event
        on_event_combobox = self.xml.get_object('on_event_combobox')
        if gajim.config.get('autopopup'):
            on_event_combobox.set_active(0)
        elif gajim.config.get('notify_on_new_message'):
            on_event_combobox.set_active(1)
        else:
            on_event_combobox.set_active(2)

        # notify on online statuses
        st = gajim.config.get('notify_on_signin')
        self.notify_on_signin_checkbutton.set_active(st)

        # notify on offline statuses
        st = gajim.config.get('notify_on_signout')
        self.notify_on_signout_checkbutton.set_active(st)

        # autopopupaway
        st = gajim.config.get('autopopupaway')
        self.auto_popup_away_checkbutton.set_active(st)

        # sounddnd
        st = gajim.config.get('sounddnd')
        self.sound_dnd_checkbutton.set_active(st)

        # Systray
        systray_combobox = self.xml.get_object('systray_combobox')
        if gajim.config.get('trayicon') == 'never':
            systray_combobox.set_active(0)
        elif gajim.config.get('trayicon') == 'on_event':
            systray_combobox.set_active(1)
        else:
            systray_combobox.set_active(2)

        # sounds
        if gajim.config.get('sounds_on'):
            self.xml.get_object('play_sounds_checkbutton').set_active(True)
        else:
            self.xml.get_object('manage_sounds_button').set_sensitive(False)

        # Notify user of new gmail e-mail messages,
        # make checkbox sensitive if user has a gtalk account
        frame_gmail = self.xml.get_object('frame_gmail')
        notify_gmail_checkbutton = self.xml.get_object('notify_gmail_checkbutton')
        notify_gmail_extra_checkbutton = self.xml.get_object(
                'notify_gmail_extra_checkbutton')

        for account in gajim.config.get_per('accounts'):
            jid = gajim.get_jid_from_account(account)
            if gajim.get_server_from_jid(jid) in gajim.gmail_domains:
                frame_gmail.set_sensitive(True)
                st = gajim.config.get('notify_on_new_gmail_email')
                notify_gmail_checkbutton.set_active(st)
                st = gajim.config.get('notify_on_new_gmail_email_extra')
                notify_gmail_extra_checkbutton.set_active(st)
                break

        #### Status tab ###
        # Autoaway
        st = gajim.config.get('autoaway')
        self.auto_away_checkbutton.set_active(st)

        # Autoawaytime
        st = gajim.config.get('autoawaytime')
        self.auto_away_time_spinbutton.set_value(st)
        self.auto_away_time_spinbutton.set_sensitive(gajim.config.get('autoaway'))

        # autoaway message
        st = gajim.config.get('autoaway_message')
        self.auto_away_message_entry.set_text(st)
        self.auto_away_message_entry.set_sensitive(gajim.config.get('autoaway'))

        # Autoxa
        st = gajim.config.get('autoxa')
        self.auto_xa_checkbutton.set_active(st)

        # Autoxatime
        st = gajim.config.get('autoxatime')
        self.auto_xa_time_spinbutton.set_value(st)
        self.auto_xa_time_spinbutton.set_sensitive(gajim.config.get('autoxa'))

        # autoxa message
        st = gajim.config.get('autoxa_message')
        self.auto_xa_message_entry.set_text(st)
        self.auto_xa_message_entry.set_sensitive(gajim.config.get('autoxa'))

        from common import sleepy
        if not sleepy.SUPPORTED:
            self.xml.get_object('autoaway_table').set_sensitive(False)

        # ask_status when online / offline
        st = gajim.config.get('ask_online_status')
        self.xml.get_object('prompt_online_status_message_checkbutton').\
                set_active(st)
        st = gajim.config.get('ask_offline_status')
        self.xml.get_object('prompt_offline_status_message_checkbutton').\
                set_active(st)

        # Default Status messages
        self.default_msg_tree = self.xml.get_object('default_msg_treeview')

        #FIXME: That doesn't seem to work:
        context = self.default_msg_tree.get_style_context()
        col2 = context.get_background_color(Gtk.StateFlags.ACTIVE)

        # (status, translated_status, message, enabled)
        model = Gtk.ListStore(str, str, str, bool)
        self.default_msg_tree.set_model(model)
        col = Gtk.TreeViewColumn(_('Status'))
        col.set_resizable(True)
        self.default_msg_tree.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'text', 1)
        col = Gtk.TreeViewColumn(_('Default Message'))
        col.set_resizable(True)
        self.default_msg_tree.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 2)
        renderer.connect('edited', self.on_default_msg_cell_edited)
        renderer.set_property('editable', True)
        renderer.set_property('cell-background-rgba', col2)
        col = Gtk.TreeViewColumn(_('Enabled'))
        col.set_resizable(True)
        self.default_msg_tree.append_column(col)
        renderer = Gtk.CellRendererToggle()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'active', 3)
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.default_msg_toggled_cb)
        self.fill_default_msg_treeview()

        # Status messages
        self.msg_tree = self.xml.get_object('msg_treeview')
        renderer = Gtk.CellRendererText()
        renderer.connect('edited', self.on_msg_cell_edited)
        renderer.set_property('editable', True)
        col = Gtk.TreeViewColumn('name', renderer, text=0)
        self.msg_tree.append_column(col)
        self.fill_msg_treeview()

        buf = self.xml.get_object('msg_textview').get_buffer()
        buf.connect('end-user-action', self.on_msg_textview_changed)

        ### Audio / Video tab ###
        def create_av_combobox(opt_name, device_dict, config_name=None,
        key=None):
            combobox = self.xml.get_object(opt_name + '_combobox')
            cell = Gtk.CellRendererText()
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)
            cell.set_property('ellipsize-set', True)
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)
            model = Gtk.ListStore(str, str)
            combobox.set_model(model)
            if config_name:
                config = gajim.config.get(config_name)
            else:
                config = gajim.config.get(opt_name + '_device')

            for index, (name, value) in enumerate(sorted(device_dict.items(),
            key=key)):
                model.append((name, value))
                if config == value:
                    combobox.set_active(index)

        if HAS_GST:
            create_av_combobox('audio_input', AudioInputManager().get_devices())
            create_av_combobox('audio_output', AudioOutputManager().get_devices(
                ))
            create_av_combobox('video_input', VideoInputManager().get_devices())
            create_av_combobox('video_output', VideoOutputManager().get_devices(
                ))

            create_av_combobox('video_framerate', {_('Default'): '',
                '15fps': '15/1', '10fps': '10/1', '5fps': '5/1',
                '2.5fps': '5/2'}, 'video_framerate', key=lambda x: -1 if \
                not x[1] else float(x[0][:-3]))
            create_av_combobox('video_size', {_('Default'): '',
                '800x600': '800x600', '640x480': '640x480',
                '320x240': '320x240'}, 'video_size', key=lambda x: -1 if \
                not x[1] else int(x[0][:3]))
            st = gajim.config.get('video_see_self')
            self.xml.get_object('video_see_self_checkbutton').set_active(st)

        else:
            for opt_name in ('audio_input', 'audio_output', 'video_input',
            'video_output', 'video_framerate', 'video_size'):
                combobox = self.xml.get_object(opt_name + '_combobox')
                combobox.set_sensitive(False)

        # STUN
        cb = self.xml.get_object('stun_checkbutton')
        st = gajim.config.get('use_stun_server')
        cb.set_active(st)

        entry = self.xml.get_object('stun_server_entry')
        entry.set_text(gajim.config.get('stun_server'))
        if not st:
            entry.set_sensitive(False)

        ### Advanced tab ###
        # open links with
        if os.name == 'nt':
            applications_frame = self.xml.get_object('applications_frame')
            applications_frame.set_no_show_all(True)
            applications_frame.hide()
        else:
            self.applications_combobox = self.xml.get_object(
                    'applications_combobox')
            self.xml.get_object('custom_apps_frame').hide()
            self.xml.get_object('custom_apps_frame').set_no_show_all(True)

            if gajim.config.get('autodetect_browser_mailer'):
                self.applications_combobox.set_active(0)
            else:
                self.applications_combobox.set_active(1)
                self.xml.get_object('custom_apps_frame').show()

            self.xml.get_object('custom_browser_entry').set_text(
                    gajim.config.get('custombrowser'))
            self.xml.get_object('custom_mail_client_entry').set_text(
                    gajim.config.get('custommailapp'))
            self.xml.get_object('custom_file_manager_entry').set_text(
                    gajim.config.get('custom_file_manager'))

        # log status changes of contacts
        st = gajim.config.get('log_contact_status_changes')
        self.xml.get_object('log_show_changes_checkbutton').set_active(st)

        # log encrypted chat sessions
        w = self.xml.get_object('log_encrypted_chats_checkbutton')
        st = self.get_per_account_option('log_encrypted_sessions')
        if st == 'mixed':
            w.set_inconsistent(True)
        else:
            w.set_active(st)

        # send os info
        w = self.xml.get_object('send_os_info_checkbutton')
        st = self.get_per_account_option('send_os_info')
        if st == 'mixed':
            w.set_inconsistent(True)
        else:
            w.set_active(st)

        # send absolute time info
        w = self.xml.get_object('send_time_info_checkbutton')
        st = self.get_per_account_option('send_time_info')
        if st == 'mixed':
            w.set_inconsistent(True)
        else:
            w.set_active(st)

        # send idle time
        w = self.xml.get_object('send_idle_time_checkbutton')
        st = self.get_per_account_option('send_idle_time')
        if st == 'mixed':
            w.set_inconsistent(True)
        else:
            w.set_active(st)

        self.update_proxy_list()

        # check if gajm is default
        st = gajim.config.get('check_if_gajim_is_default')
        self.xml.get_object('check_default_client_checkbutton').set_active(st)

        # Ignore messages from unknown contacts
        w = self.xml.get_object('ignore_events_from_unknown_contacts_checkbutton')
        st = self.get_per_account_option('ignore_unknown_contacts')
        if st == 'mixed':
            w.set_inconsistent(True)
        else:
            w.set_active(st)

        self.xml.connect_signals(self)

        self.msg_tree.get_model().connect('row-changed',
                                self.on_msg_treemodel_row_changed)
        self.msg_tree.get_model().connect('row-deleted',
                                self.on_msg_treemodel_row_deleted)
        self.default_msg_tree.get_model().connect('row-changed',
                                self.on_default_msg_treemodel_row_changed)

        self.theme_preferences = None
        self.sounds_preferences = None

        self.notebook.set_current_page(0)
        self.xml.get_object('close_button').grab_focus()

        self.window.show_all()
        gtkgui_helpers.possibly_move_window_in_current_desktop(self.window)

    def on_preferences_notebook_switch_page(self, widget, page, page_num):
        GLib.idle_add(self.xml.get_object('close_button').grab_focus)

    def on_preferences_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.hide()

    def get_per_account_option(self, opt):
        """
        Return the value of the option opt if it's the same in all accounts else
        returns "mixed"
        """
        if len(gajim.connections) == 0:
            # a non existant key return default value
            return gajim.config.get_per('accounts', '__default__', opt)
        val = None
        for account in gajim.connections:
            v = gajim.config.get_per('accounts', account, opt)
            if val is None:
                val = v
            elif val != v:
                return 'mixed'
        return val

    def on_checkbutton_toggled(self, widget, config_name,
    change_sensitivity_widgets=None):
        gajim.config.set(config_name, widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def on_per_account_checkbutton_toggled(self, widget, config_name,
    change_sensitivity_widgets=None):
        for account in gajim.connections:
            gajim.config.set_per('accounts', account, config_name,
                    widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def _get_all_controls(self):
        for ctrl in gajim.interface.msg_win_mgr.get_controls():
            yield ctrl
        for account in gajim.connections:
            for ctrl in gajim.interface.minimized_controls[account].values():
                yield ctrl

    def _get_all_muc_controls(self):
        for ctrl in gajim.interface.msg_win_mgr.get_controls(
        message_control.TYPE_GC):
            yield ctrl
        for account in gajim.connections:
            for ctrl in gajim.interface.minimized_controls[account].values():
                yield ctrl

    def on_sort_by_show_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_roster')
        gajim.interface.roster.setup_and_draw_roster()

    def on_sort_by_show_in_muc_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_muc')
        # Redraw groupchats
        for ctrl in self._get_all_muc_controls():
            ctrl.draw_roster()

    def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
        gajim.interface.roster.setup_and_draw_roster()
        # Redraw groupchats (in an ugly way)
        for ctrl in self._get_all_muc_controls():
            ctrl.draw_roster()

    def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
        gajim.interface.roster.setup_and_draw_roster()
        for ctrl in self._get_all_muc_controls():
            ctrl.update_ui()

    def on_show_pep_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_mood_in_roster')
        self.on_checkbutton_toggled(widget, 'show_activity_in_roster')
        self.on_checkbutton_toggled(widget, 'show_tunes_in_roster')
        self.on_checkbutton_toggled(widget, 'show_location_in_roster')
        gajim.interface.roster.setup_and_draw_roster()

    def on_emoticons_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        emot_theme = model[active][0]
        if emot_theme == _('Disabled'):
            gajim.config.set('emoticons_theme', '')
        else:
            gajim.config.set('emoticons_theme', emot_theme)

        gajim.interface.init_emoticons(need_reload = True)
        gajim.interface.make_regexps()
        self.toggle_emoticons()

    def toggle_emoticons(self):
        """
        Update emoticons state in Opened Chat Windows
        """
        for ctrl in self._get_all_controls():
            ctrl.toggle_emoticons()

    def on_one_window_type_combo_changed(self, widget):
        active = widget.get_active()
        config_type = common.config.opt_one_window_types[active]
        gajim.config.set('one_message_window', config_type)
        gajim.interface.msg_win_mgr.reconfig()

    def on_show_roster_on_startup_changed(self, widget):
        active = widget.get_active()
        config_type = common.config.opt_show_roster_on_startup[active]
        gajim.config.set('show_roster_on_startup', config_type)

    def on_compact_view_checkbutton_toggled(self, widget):
        active = widget.get_active()
        for ctrl in self._get_all_controls():
            ctrl.chat_buttons_set_visible(active)
        gajim.config.set('compact_view', active)

    def on_xhtml_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ignore_incoming_xhtml')
        helpers.update_optional_features()

    def apply_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, chat_control.ChatControlBase):
                try:
                    spell_obj = gtkspell.get_from_text_view(ctrl.msg_textview)
                except (TypeError, RuntimeError, OSError):
                    spell_obj = None

                if not spell_obj:
                    ctrl.set_speller()

    def remove_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, chat_control.ChatControlBase):
                try:
                    spell_obj = gtkspell.get_from_text_view(ctrl.msg_textview)
                except (TypeError, RuntimeError):
                    spell_obj = None
                if spell_obj:
                    spell_obj.detach()

    def on_speller_checkbutton_toggled(self, widget):
        active = widget.get_active()
        gajim.config.set('use_speller', active)
        if active:
            lang = gajim.config.get('speller_language')
            if not lang:
                lang = gajim.LANG
            tv = Gtk.TextView()
            try:
                gtkspell.Spell(tv, lang)
            except (TypeError, RuntimeError, OSError):
                dialogs.ErrorDialog(
                        _('Dictionary for lang %s not available') % lang,
                        _('You have to install %s dictionary to use spellchecking, or '
                        'choose another language by setting the speller_language option.'
                        ) % lang)
                gajim.config.set('use_speller', False)
                widget.set_active(False)
            else:
                gajim.config.set('speller_language', lang)
                self.apply_speller()
        else:
            self.remove_speller()

    def on_positive_184_ack_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'positive_184_ack')

    def on_theme_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        config_theme = model[active][0].replace(' ', '_')

        gajim.config.set('roster_theme', config_theme)

        # begin repainting themed widgets throughout
        gajim.interface.roster.repaint_themed_widgets()
        gajim.interface.roster.change_roster_style(None)

    def update_theme_list(self):
        theme_combobox = self.xml.get_object('theme_combobox')
        model = Gtk.ListStore(str)
        theme_combobox.set_model(model)
        i = 0
        for config_theme in gajim.config.get_per('themes'):
            theme = config_theme.replace('_', ' ')
            model.append([theme])
            if gajim.config.get('roster_theme') == config_theme:
                theme_combobox.set_active(i)
            i += 1

    def on_manage_theme_button_clicked(self, widget):
        if self.theme_preferences is None:
            self.theme_preferences = dialogs.GajimThemesWindow()
        else:
            self.theme_preferences.window.present()
            self.theme_preferences.select_active_theme()

    def on_iconset_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        icon_string = model[active][1]
        gajim.config.set('iconset', icon_string)
        gtkgui_helpers.reload_jabber_state_images()

    def on_transports_iconsets_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_transports_iconsets')
        gtkgui_helpers.reload_jabber_state_images()

    def on_outgoing_chat_states_combobox_changed(self, widget):
        active = widget.get_active()
        old_value = gajim.config.get('outgoing_chat_state_notifications')
        if active == 0: # all
            gajim.config.set('outgoing_chat_state_notifications', 'all')
        elif active == 1: # only composing
            gajim.config.set('outgoing_chat_state_notifications', 'composing_only')
        else: # disabled
            gajim.config.set('outgoing_chat_state_notifications', 'disabled')
        new_value = gajim.config.get('outgoing_chat_state_notifications')
        if 'disabled' in (old_value, new_value):
            # we changed from disabled to sth else or vice versa
            helpers.update_optional_features()

    def on_displayed_chat_states_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0: # all
            gajim.config.set('displayed_chat_state_notifications', 'all')
        elif active == 1: # only composing
            gajim.config.set('displayed_chat_state_notifications',
                    'composing_only')
        else: # disabled
            gajim.config.set('displayed_chat_state_notifications', 'disabled')

    def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'ignore_unknown_contacts')

    def on_on_event_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            gajim.config.set('autopopup', True)
            gajim.config.set('notify_on_new_message', False)
        elif active == 1:
            gajim.config.set('autopopup', False)
            gajim.config.set('notify_on_new_message', True)
        else:
            gajim.config.set('autopopup', False)
            gajim.config.set('notify_on_new_message', False)

    def on_notify_on_signin_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signin')

    def on_notify_on_signout_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signout')

    def on_auto_popup_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autopopupaway')

    def on_sound_dnd_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounddnd')

    def on_systray_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            gajim.config.set('trayicon', 'never')
            gajim.interface.systray_enabled = False
            gajim.interface.systray.hide_icon()
        elif active == 1:
            gajim.config.set('trayicon', 'on_event')
            gajim.interface.systray_enabled = True
            gajim.interface.systray.show_icon()
        else:
            gajim.config.set('trayicon', 'always')
            gajim.interface.systray_enabled = True
            gajim.interface.systray.show_icon()

    def on_play_sounds_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounds_on',
                [self.xml.get_object('manage_sounds_button')])

    def on_manage_sounds_button_clicked(self, widget):
        if self.sounds_preferences is None:
            self.sounds_preferences = ManageSoundsWindow()
        else:
            self.sounds_preferences.window.present()

    def update_text_tags(self):
        """
        Update color tags in opened chat windows
        """
        for ctrl in self._get_all_controls():
            ctrl.update_tags()

    def on_preference_widget_color_set(self, widget, text):
        color = widget.get_color()
        color_string = gtkgui_helpers.make_color_string(color)
        gajim.config.set(text, color_string)
        self.update_text_tags()

    def on_preference_widget_font_set(self, widget, text):
        if widget:
            font = widget.get_font_name()
        else:
            font = ''
        gajim.config.set(text, font)
        self.update_text_font()

    def update_text_font(self):
        """
        Update text font in opened chat windows
        """
        for ctrl in self._get_all_controls():
            ctrl.update_font()

    def on_incoming_nick_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'inmsgcolor')

    def on_outgoing_nick_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'outmsgcolor')

    def on_incoming_msg_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'inmsgtxtcolor')

    def on_outgoing_msg_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'outmsgtxtcolor')

    def on_url_msg_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'urlmsgcolor')

    def on_status_msg_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'statusmsgcolor')

    def on_muc_highlight_colorbutton_color_set(self, widget):
        self.on_preference_widget_color_set(widget, 'markedmsgcolor')

    def on_conversation_fontbutton_font_set(self, widget):
        self.on_preference_widget_font_set(widget, 'conversation_font')

    def on_default_chat_font_toggled(self, widget):
        font_widget = self.xml.get_object('conversation_fontbutton')
        if widget.get_active():
            font_widget.set_sensitive(False)
            font_widget = None
        else:
            font_widget.set_sensitive(True)
        self.on_preference_widget_font_set(font_widget, 'conversation_font')

    def draw_color_widgets(self):
        col_to_widget = {'inmsgcolor': 'incoming_nick_colorbutton',
                        'outmsgcolor': 'outgoing_nick_colorbutton',
                        'inmsgtxtcolor': ['incoming_msg_colorbutton',
                                'incoming_msg_checkbutton'],
                        'outmsgtxtcolor': ['outgoing_msg_colorbutton',
                                'outgoing_msg_checkbutton'],
                        'statusmsgcolor': 'status_msg_colorbutton',
                        'urlmsgcolor': 'url_msg_colorbutton',
                        'markedmsgcolor': 'muc_highlight_colorbutton'}
        for c in col_to_widget:
            col = gajim.config.get(c)
            if col:
                if isinstance(col_to_widget[c], list):
                    self.xml.get_object(col_to_widget[c][0]).set_color(
                            Gdk.color_parse(col))
                    self.xml.get_object(col_to_widget[c][0]).set_sensitive(True)
                    self.xml.get_object(col_to_widget[c][1]).set_active(True)
                else:
                    self.xml.get_object(col_to_widget[c]).set_color(
                            Gdk.color_parse(col))
            else:
                if isinstance(col_to_widget[c], list):
                    self.xml.get_object(col_to_widget[c][0]).set_color(
                            Gdk.color_parse('#000000'))
                    self.xml.get_object(col_to_widget[c][0]).set_sensitive(False)
                    self.xml.get_object(col_to_widget[c][1]).set_active(False)
                else:
                    self.xml.get_object(col_to_widget[c]).set_color(
                            Gdk.color_parse('#000000'))

    def on_reset_colors_button_clicked(self, widget):
        col_to_widget = {'inmsgcolor': 'incoming_nick_colorbutton',
                        'outmsgcolor': 'outgoing_nick_colorbutton',
                        'inmsgtxtcolor': 'incoming_msg_colorbutton',
                        'outmsgtxtcolor': 'outgoing_msg_colorbutton',
                        'statusmsgcolor': 'status_msg_colorbutton',
                        'urlmsgcolor': 'url_msg_colorbutton',
                        'markedmsgcolor': 'muc_highlight_colorbutton'}
        for c in col_to_widget:
            gajim.config.set(c, gajim.interface.default_colors[c])
        self.draw_color_widgets()

        self.update_text_tags()

    def _set_color(self, state, widget_name, option):
        """
        Set color value in prefs and update the UI
        """
        if state:
            color = self.xml.get_object(widget_name).get_color()
            color_string = gtkgui_helpers.make_color_string(color)
        else:
            color_string = ''
        gajim.config.set(option, color_string)

    def on_incoming_msg_checkbutton_toggled(self, widget):
        state = widget.get_active()
        self.xml.get_object('incoming_msg_colorbutton').set_sensitive(state)
        self._set_color(state, 'incoming_msg_colorbutton', 'inmsgtxtcolor')

    def on_outgoing_msg_checkbutton_toggled(self, widget):
        state = widget.get_active()
        self.xml.get_object('outgoing_msg_colorbutton').set_sensitive(state)
        self._set_color(state, 'outgoing_msg_colorbutton', 'outmsgtxtcolor')

    def on_auto_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoaway',
                                [self.auto_away_time_spinbutton, self.auto_away_message_entry])

    def on_auto_away_time_spinbutton_value_changed(self, widget):
        aat = widget.get_value_as_int()
        gajim.config.set('autoawaytime', aat)
        gajim.interface.sleeper = common.sleepy.Sleepy(
                                gajim.config.get('autoawaytime') * 60,
                                gajim.config.get('autoxatime') * 60)

    def on_auto_away_message_entry_changed(self, widget):
        gajim.config.set('autoaway_message', widget.get_text())

    def on_auto_xa_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoxa',
                                [self.auto_xa_time_spinbutton, self.auto_xa_message_entry])

    def on_auto_xa_time_spinbutton_value_changed(self, widget):
        axt = widget.get_value_as_int()
        gajim.config.set('autoxatime', axt)
        gajim.interface.sleeper = common.sleepy.Sleepy(
                                gajim.config.get('autoawaytime') * 60,
                                gajim.config.get('autoxatime') * 60)

    def on_auto_xa_message_entry_changed(self, widget):
        gajim.config.set('autoxa_message', widget.get_text())

    def on_prompt_online_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_online_status')

    def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_offline_status')

    def fill_default_msg_treeview(self):
        model = self.default_msg_tree.get_model()
        model.clear()
        status = []
        for status_ in gajim.config.get_per('defaultstatusmsg'):
            status.append(status_)
        status.sort()
        for status_ in status:
            msg = gajim.config.get_per('defaultstatusmsg', status_, 'message')
            msg = helpers.from_one_line(msg)
            enabled = gajim.config.get_per('defaultstatusmsg', status_, 'enabled')
            iter_ = model.append()
            uf_show = helpers.get_uf_show(status_)
            model.set(iter_, 0, status_, 1, uf_show, 2, msg, 3, enabled)

    def on_default_msg_cell_edited(self, cell, row, new_text):
        model = self.default_msg_tree.get_model()
        iter_ = model.get_iter_from_string(row)
        model.set_value(iter_, 2, new_text)

    def default_msg_toggled_cb(self, cell, path):
        model = self.default_msg_tree.get_model()
        model[path][3] = not model[path][3]

    def on_default_msg_treemodel_row_changed(self, model, path, iter_):
        status = model[iter_][0]
        message = model[iter_][2]
        message = helpers.to_one_line(message)
        gajim.config.set_per('defaultstatusmsg', status, 'enabled',
                model[iter_][3])
        gajim.config.set_per('defaultstatusmsg', status, 'message', message)

    def on_default_status_expander_activate(self, expander):
        eventbox = self.xml.get_object('default_status_eventbox')
        vbox = self.xml.get_object('status_vbox')
        vbox.set_child_packing(eventbox, not expander.get_expanded(), True, 0,
                Gtk.PACK_START)

    def save_status_messages(self, model):
        for msg in gajim.config.get_per('statusmsg'):
            gajim.config.del_per('statusmsg', msg)
        iter_ = model.get_iter_first()
        while iter_:
            val = model[iter_][0]
            if model[iter_][1]: # we have a preset message
                if not val: # no title, use message text for title
                    val = model[iter_][1]
                gajim.config.add_per('statusmsg', val)
                msg = helpers.to_one_line(model[iter_][1])
                gajim.config.set_per('statusmsg', val, 'message', msg)
                i = 2
                # store mood / activity
                for subname in ('activity', 'subactivity', 'activity_text',
                'mood', 'mood_text'):
                    val2 = model[iter_][i]
                    if not val2:
                        val2 = ''
                    gajim.config.set_per('statusmsg', val, subname, val2)
                    i += 1
            iter_ = model.iter_next(iter_)

    def on_msg_treemodel_row_changed(self, model, path, iter_):
        self.save_status_messages(model)

    def on_msg_treemodel_row_deleted(self, model, path):
        self.save_status_messages(model)

    def on_av_combobox_changed(self, combobox, config_name):
        model = combobox.get_model()
        active = combobox.get_active()
        device = model[active][1]
        gajim.config.set(config_name, device)

    def on_audio_input_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_input_device')

    def on_audio_output_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_output_device')

    def on_video_input_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_input_device')

    def on_video_output_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_output_device')

    def on_video_framerate_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_framerate')

    def on_video_size_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_size')

    def on_video_see_self_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'video_see_self')

    def on_stun_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_stun_server',
                [self.xml.get_object('stun_server_entry')])

    def stun_server_entry_changed(self, widget):
        gajim.config.set('stun_server', widget.get_text())

    def on_applications_combobox_changed(self, widget):
        if widget.get_active() == 0:
            gajim.config.set('autodetect_browser_mailer', True)
            self.xml.get_object('custom_apps_frame').hide()
        elif widget.get_active() == 1:
            gajim.config.set('autodetect_browser_mailer', False)
            self.xml.get_object('custom_apps_frame').show()

    def on_custom_browser_entry_changed(self, widget):
        gajim.config.set('custombrowser', widget.get_text())

    def on_custom_mail_client_entry_changed(self, widget):
        gajim.config.set('custommailapp', widget.get_text())

    def on_custom_file_manager_entry_changed(self, widget):
        gajim.config.set('custom_file_manager', widget.get_text())

    def on_log_show_changes_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

    def on_log_encrypted_chats_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'log_encrypted_sessions')

    def on_send_os_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_os_info')

    def on_send_time_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_time_info')

    def on_send_idle_time_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_idle_time')

    def on_check_default_client_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'check_if_gajim_is_default')

    def on_notify_gmail_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_new_gmail_email')

    def on_notify_gmail_extra_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_new_gmail_email_extra')

    def fill_msg_treeview(self):
        self.xml.get_object('delete_msg_button').set_sensitive(False)
        model = self.msg_tree.get_model()
        model.clear()
        preset_status = []
        for msg_name in gajim.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            preset_status.append(msg_name)
        preset_status.sort()
        for msg_name in preset_status:
            msg_text = gajim.config.get_per('statusmsg', msg_name, 'message')
            msg_text = helpers.from_one_line(msg_text)
            activity = gajim.config.get_per('statusmsg', msg_name, 'activity')
            subactivity = gajim.config.get_per('statusmsg', msg_name,
                'subactivity')
            activity_text = gajim.config.get_per('statusmsg', msg_name,
                'activity_text')
            mood = gajim.config.get_per('statusmsg', msg_name, 'mood')
            mood_text = gajim.config.get_per('statusmsg', msg_name, 'mood_text')
            iter_ = model.append()
            model.set(iter_, 0, msg_name, 1, msg_text, 2, activity, 3,
                subactivity, 4, activity_text, 5, mood, 6, mood_text)

    def on_msg_cell_edited(self, cell, row, new_text):
        model = self.msg_tree.get_model()
        iter_ = model.get_iter_from_string(row)
        model.set_value(iter_, 0, new_text)

    def on_msg_treeview_cursor_changed(self, widget, data = None):
        sel = self.msg_tree.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        self.xml.get_object('delete_msg_button').set_sensitive(True)
        buf = self.xml.get_object('msg_textview').get_buffer()
        msg = model[iter_][1]
        buf.set_text(msg)

    def on_new_msg_button_clicked(self, widget, data = None):
        model = self.msg_tree.get_model()
        iter_ = model.append()
        model.set(iter_, 0, _('status message title'), 1,
            _('status message text'))
        self.msg_tree.set_cursor(model.get_path(iter_))

    def on_delete_msg_button_clicked(self, widget, data = None):
        sel = self.msg_tree.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self.xml.get_object('msg_textview').get_buffer()
        model.remove(iter_)
        buf.set_text('')
        self.xml.get_object('delete_msg_button').set_sensitive(False)

    def on_msg_textview_changed(self, widget, data = None):
        sel = self.msg_tree.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self.xml.get_object('msg_textview').get_buffer()
        first_iter, end_iter = buf.get_bounds()
        model.set_value(iter_, 1, buf.get_text(first_iter, end_iter, True))

    def on_msg_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_delete_msg_button_clicked(widget)

    def on_proxies_combobox_changed(self, widget):
        active = widget.get_active()
        proxy = widget.get_model()[active][0]
        if proxy == _('None'):
            proxy = ''

        gajim.config.set('global_proxy', proxy)

    def on_manage_proxies_button_clicked(self, widget):
        if 'manage_proxies' in gajim.interface.instances:
            gajim.interface.instances['manage_proxies'].window.present()
        else:
            gajim.interface.instances['manage_proxies'] = ManageProxiesWindow(
                self.window)

    def update_proxy_list(self):
        our_proxy = gajim.config.get('global_proxy')
        if not our_proxy:
            our_proxy = _('None')
        proxy_combobox = self.xml.get_object('proxies_combobox')
        model = proxy_combobox.get_model()
        model.clear()
        l = gajim.config.get_per('proxies')
        l.insert(0, _('None'))
        for i in range(len(l)):
            model.append([l[i]])
            if our_proxy == l[i]:
                proxy_combobox.set_active(i)

    def on_open_advanced_editor_button_clicked(self, widget, data = None):
        if 'advanced_config' in gajim.interface.instances:
            gajim.interface.instances['advanced_config'].window.present()
        else:
            gajim.interface.instances['advanced_config'] = \
                    dialogs.AdvancedConfigurationWindow()

#---------- ManageProxiesWindow class -------------#
class ManageProxiesWindow:
    def __init__(self, transient_for=None):
        self.xml = gtkgui_helpers.get_gtk_builder('manage_proxies_window.ui')
        self.window = self.xml.get_object('manage_proxies_window')
        self.window.set_transient_for(transient_for)
        self.proxies_treeview = self.xml.get_object('proxies_treeview')
        self.proxyname_entry = self.xml.get_object('proxyname_entry')
        self.proxytype_combobox = self.xml.get_object('proxytype_combobox')

        self.init_list()
        self.block_signal = False
        self.xml.connect_signals(self)
        self.window.show_all()
        # hide the BOSH fields by default
        self.show_bosh_fields()

    def show_bosh_fields(self, show=True):
        if show:
            self.xml.get_object('boshuri_entry').show()
            self.xml.get_object('boshuri_label').show()
            self.xml.get_object('boshuseproxy_checkbutton').show()
        else:
            cb = self.xml.get_object('boshuseproxy_checkbutton')
            cb.hide()
            cb.set_active(True)
            self.on_boshuseproxy_checkbutton_toggled(cb)
            self.xml.get_object('boshuri_entry').hide()
            self.xml.get_object('boshuri_label').hide()


    def fill_proxies_treeview(self):
        model = self.proxies_treeview.get_model()
        model.clear()
        iter_ = model.append()
        model.set(iter_, 0, _('None'))
        for p in gajim.config.get_per('proxies'):
            iter_ = model.append()
            model.set(iter_, 0, p)

    def init_list(self):
        self.xml.get_object('remove_proxy_button').set_sensitive(False)
        self.proxytype_combobox.set_sensitive(False)
        self.xml.get_object('proxy_table').set_sensitive(False)
        model = Gtk.ListStore(str)
        self.proxies_treeview.set_model(model)
        col = Gtk.TreeViewColumn('Proxies')
        self.proxies_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 0)
        self.fill_proxies_treeview()
        self.xml.get_object('proxytype_combobox').set_active(0)

    def on_manage_proxies_window_destroy(self, widget):
        if 'accounts' in gajim.interface.instances:
            gajim.interface.instances['accounts'].\
                    update_proxy_list()
        del gajim.interface.instances['manage_proxies']

    def on_add_proxy_button_clicked(self, widget):
        model = self.proxies_treeview.get_model()
        proxies = gajim.config.get_per('proxies')
        i = 1
        while ('proxy' + str(i)) in proxies:
            i += 1
        iter_ = model.append()
        model.set(iter_, 0, 'proxy' + str(i))
        gajim.config.add_per('proxies', 'proxy' + str(i))
        self.proxies_treeview.set_cursor(model.get_path(iter_))

    def on_remove_proxy_button_clicked(self, widget):
        sel = self.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        proxy = model[iter_][0]
        model.remove(iter_)
        gajim.config.del_per('proxies', proxy)
        self.xml.get_object('remove_proxy_button').set_sensitive(False)
        self.block_signal = True
        self.on_proxies_treeview_cursor_changed(self.proxies_treeview)
        self.block_signal = False

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_useauth_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'useauth', act)
        self.xml.get_object('proxyuser_entry').set_sensitive(act)
        self.xml.get_object('proxypass_entry').set_sensitive(act)

    def on_boshuseproxy_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'bosh_useproxy', act)
        self.xml.get_object('proxyhost_entry').set_sensitive(act)
        self.xml.get_object('proxyport_entry').set_sensitive(act)

    def on_proxies_treeview_cursor_changed(self, widget):
        #FIXME: check if off proxy settings are correct (see
        # http://trac.gajim.org/changeset/1921#file2 line 1221
        proxyhost_entry = self.xml.get_object('proxyhost_entry')
        proxyport_entry = self.xml.get_object('proxyport_entry')
        proxyuser_entry = self.xml.get_object('proxyuser_entry')
        proxypass_entry = self.xml.get_object('proxypass_entry')
        boshuri_entry = self.xml.get_object('boshuri_entry')
        useauth_checkbutton = self.xml.get_object('useauth_checkbutton')
        boshuseproxy_checkbutton = self.xml.get_object('boshuseproxy_checkbutton')
        self.block_signal = True
        proxyhost_entry.set_text('')
        proxyport_entry.set_text('')
        proxyuser_entry.set_text('')
        proxypass_entry.set_text('')
        boshuri_entry.set_text('')

        #boshuseproxy_checkbutton.set_active(False)
        #self.on_boshuseproxy_checkbutton_toggled(boshuseproxy_checkbutton)

        #useauth_checkbutton.set_active(False)
        #self.on_useauth_checkbutton_toggled(useauth_checkbutton)

        sel = widget.get_selection()
        if sel:
            (model, iter_) = sel.get_selected()
        else:
            iter_ = None
        if not iter_:
            self.xml.get_object('proxyname_entry').set_text('')
            self.xml.get_object('proxytype_combobox').set_sensitive(False)
            self.xml.get_object('proxy_table').set_sensitive(False)
            self.block_signal = False
            return

        proxy = model[iter_][0]
        self.xml.get_object('proxyname_entry').set_text(proxy)

        if proxy == _('None'): # special proxy None
            self.show_bosh_fields(False)
            self.proxyname_entry.set_editable(False)
            self.xml.get_object('remove_proxy_button').set_sensitive(False)
            self.xml.get_object('proxytype_combobox').set_sensitive(False)
            self.xml.get_object('proxy_table').set_sensitive(False)
        else:
            proxytype = gajim.config.get_per('proxies', proxy, 'type')

            self.show_bosh_fields(proxytype=='bosh')

            self.proxyname_entry.set_editable(True)
            self.xml.get_object('remove_proxy_button').set_sensitive(True)
            self.xml.get_object('proxytype_combobox').set_sensitive(True)
            self.xml.get_object('proxy_table').set_sensitive(True)
            proxyhost_entry.set_text(gajim.config.get_per('proxies', proxy,
                    'host'))
            proxyport_entry.set_text(str(gajim.config.get_per('proxies',
                    proxy, 'port')))
            proxyuser_entry.set_text(gajim.config.get_per('proxies', proxy,
                    'user'))
            proxypass_entry.set_text(gajim.config.get_per('proxies', proxy,
                    'pass'))
            boshuri_entry.set_text(gajim.config.get_per('proxies', proxy,
                    'bosh_uri'))
            types = ['http', 'socks5', 'bosh']
            self.proxytype_combobox.set_active(types.index(proxytype))
            boshuseproxy_checkbutton.set_active(
                    gajim.config.get_per('proxies', proxy, 'bosh_useproxy'))
            useauth_checkbutton.set_active(
                    gajim.config.get_per('proxies', proxy, 'useauth'))
        self.block_signal = False

    def on_proxies_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_remove_proxy_button_clicked(widget)

    def on_proxyname_entry_changed(self, widget):
        if self.block_signal:
            return
        sel = self.proxies_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        old_name = model.get_value(iter_, 0)
        new_name = widget.get_text()
        if new_name == '':
            return
        if new_name == old_name:
            return
        config = gajim.config.get_per('proxies', old_name)
        gajim.config.del_per('proxies', old_name)
        gajim.config.add_per('proxies', new_name)
        for option in config:
            gajim.config.set_per('proxies', new_name, option, config[option])
        model.set_value(iter_, 0, new_name)

    def on_proxytype_combobox_changed(self, widget):
        if self.block_signal:
            return
        types = ['http', 'socks5', 'bosh']
        type_ = self.proxytype_combobox.get_active()
        self.show_bosh_fields(types[type_]=='bosh')
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'type', types[type_])

    def on_proxyhost_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'host', value)

    def on_proxyport_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'port', value)

    def on_proxyuser_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'user', value)

    def on_boshuri_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'bosh_uri', value)

    def on_proxypass_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        gajim.config.set_per('proxies', proxy, 'pass', value)


#---------- AccountsWindow class -------------#
class AccountsWindow:
    """
    Class for accounts window: list of accounts
    """

    def on_accounts_window_destroy(self, widget):
        del gajim.interface.instances['accounts']

    def on_close_button_clicked(self, widget):
        self.check_resend_relog()
        self.window.destroy()

    def __init__(self):
        self.xml = gtkgui_helpers.get_gtk_builder('accounts_window.ui')
        self.window = self.xml.get_object('accounts_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        self.accounts_treeview = self.xml.get_object('accounts_treeview')
        self.remove_button = self.xml.get_object('remove_button')
        self.rename_button = self.xml.get_object('rename_button')
        path_to_kbd_input_img = gtkgui_helpers.get_icon_path('gajim-kbd_input')
        img = self.xml.get_object('rename_image')
        img.set_from_file(path_to_kbd_input_img)
        self.notebook = self.xml.get_object('notebook')
        # Name
        model = Gtk.ListStore(str)
        self.accounts_treeview.set_model(model)
        # column
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn()
        col.set_title(_('Name'))
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'text', 0)
        self.accounts_treeview.insert_column(col, -1)

        self.current_account = None
        # When we fill info, we don't want to handle the changed signals
        self.ignore_events = False
        self.need_relogin = False
        self.resend_presence = False

        self.update_proxy_list()
        self.xml.connect_signals(self)
        self.init_accounts()
        self.window.show_all()

        # Merge accounts
        st = gajim.config.get('mergeaccounts')
        checkbutton = self.xml.get_object('merge_checkbutton')
        checkbutton.set_active(st)
        # prevent roster redraws by connecting the signal after button state is
        # set
        checkbutton.connect('toggled', self.on_merge_checkbutton_toggled)

        self.avahi_available = True
        try:
            import avahi
        except ImportError:
            self.avahi_available = False

        self.xml.get_object('close_button').grab_focus()

    def on_accounts_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.check_resend_relog()
            self.window.destroy()

    def select_account(self, account):
        model = self.accounts_treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            acct = model[iter_][0]
            if account == acct:
                self.accounts_treeview.set_cursor(model.get_path(iter_))
                return
            iter_ = model.iter_next(iter_)

    def init_accounts(self):
        """
        Initialize listStore with existing accounts
        """
        self.remove_button.set_sensitive(False)
        self.rename_button.set_sensitive(False)
        self.current_account = None
        model = self.accounts_treeview.get_model()
        model.clear()
        for account in gajim.config.get_per('accounts'):
            iter_ = model.append()
            model.set(iter_, 0, account)

        self.selection = self.accounts_treeview.get_selection()
        self.selection.select_iter(model.get_iter_first())

    def resend(self, account):
        if not account in gajim.connections:
            return
        show = gajim.SHOW_LIST[gajim.connections[account].connected]
        status = gajim.connections[account].status
        gajim.connections[account].change_status(show, status)

    def check_resend_relog(self):
        if self.need_relogin and self.current_account == \
        gajim.ZEROCONF_ACC_NAME:
            if gajim.ZEROCONF_ACC_NAME in gajim.connections:
                gajim.connections[gajim.ZEROCONF_ACC_NAME].update_details()
                return

        elif self.need_relogin and self.current_account and \
        gajim.connections[self.current_account].connected > 0:
            def login(account, show_before, status_before):
                """
                Login with previous status
                """
                # first make sure connection is really closed,
                # 0.5 may not be enough
                gajim.connections[account].disconnect(True)
                gajim.interface.roster.send_status(account, show_before,
                        status_before)

            def relog(account):
                self.dialog.destroy()
                show_before = gajim.SHOW_LIST[gajim.connections[account].\
                    connected]
                status_before = gajim.connections[account].status
                gajim.interface.roster.send_status(account, 'offline',
                    _('Be right back.'))
                GLib.timeout_add(500, login, account, show_before,
                    status_before)

            def on_yes(checked, account):
                relog(account)
            def on_no(account):
                if self.resend_presence:
                    self.resend(account)
            if self.current_account in gajim.connections:
                self.dialog = dialogs.YesNoDialog(_('Relogin now?'),
                    _('If you want all the changes to apply instantly, '
                    'you must relogin.'), on_response_yes=(on_yes,
                    self.current_account), on_response_no=(on_no,
                    self.current_account))
        elif self.resend_presence:
            self.resend(self.current_account)

        self.need_relogin = False
        self.resend_presence = False

    def on_accounts_treeview_cursor_changed(self, widget):
        """
        Activate modify buttons when a row is selected, update accounts info
        """
        sel = self.accounts_treeview.get_selection()
        if sel:
            (model, iter_) = sel.get_selected()
            if iter_:
                account = model[iter_][0]
            else:
                account = None
        else:
            iter_ = account = None
        if self.current_account and self.current_account == account:
            # We're comming back to our current account, no need to update
            # widgets
            return
        # Save config for previous account if needed cause focus_out event is
        # called after the changed event
        if self.current_account and self.window.get_focus():
            focused_widget = self.window.get_focus()
            focused_widget_name = focused_widget.get_name()
            if focused_widget_name in ('jid_entry1', 'resource_entry1',
            'custom_port_entry', 'cert_entry1'):
                if focused_widget_name == 'jid_entry1':
                    func = self.on_jid_entry1_focus_out_event
                elif focused_widget_name == 'resource_entry1':
                    func = self.on_resource_entry1_focus_out_event
                elif focused_widget_name == 'custom_port_entry':
                    func = self.on_custom_port_entry_focus_out_event
                elif focused_widget_name == 'cert_entry1':
                    func = self.on_cert_entry1_focus_out_event
                if func(focused_widget, None):
                    # Error detected in entry, don't change account,
                    # re-put cursor on previous row
                    self.select_account(self.current_account)
                    return True
                self.window.set_focus(widget)

        self.check_resend_relog()

        if account:
            self.remove_button.set_sensitive(True)
            self.rename_button.set_sensitive(True)
        else:
            self.remove_button.set_sensitive(False)
            self.rename_button.set_sensitive(False)
        if iter_:
            self.current_account = account
            if account == gajim.ZEROCONF_ACC_NAME:
                self.remove_button.set_sensitive(False)
        self.init_account()
        self.update_proxy_list()

    def on_browse_for_client_cert_button_clicked(self, widget, data=None):
        def on_ok(widget, path_to_clientcert_file):
            self.dialog.destroy()
            if not path_to_clientcert_file:
                return
            self.xml.get_object('cert_entry1').set_text(path_to_clientcert_file)
            gajim.config.set_per('accounts', self.current_account,
                'client_cert', path_to_clientcert_file)

        def on_cancel(widget):
            self.dialog.destroy()

        path_to_clientcert_file = self.xml.get_object('cert_entry1').get_text()
        self.dialog = dialogs.ClientCertChooserDialog(path_to_clientcert_file,
            on_ok, on_cancel)

    def update_proxy_list(self):
        if self.current_account:
            our_proxy = gajim.config.get_per('accounts', self.current_account,
                'proxy')
        else:
            our_proxy = ''

        if not our_proxy:
            our_proxy = _('None')
        proxy_combobox = self.xml.get_object('proxies_combobox1')
        model = Gtk.ListStore(str)
        proxy_combobox.set_model(model)
        l = gajim.config.get_per('proxies')
        l.insert(0, _('None'))
        for i in range(len(l)):
            model.append([l[i]])
            if our_proxy == l[i]:
                proxy_combobox.set_active(i)

    def init_account(self):
        if not self.current_account:
            self.notebook.set_current_page(0)
            return
        if gajim.config.get_per('accounts', self.current_account,
        'is_zeroconf'):
            self.ignore_events = True
            self.init_zeroconf_account()
            self.ignore_events = False
            self.notebook.set_current_page(2)
            return
        self.ignore_events = True
        self.init_normal_account()
        self.ignore_events = False
        self.notebook.set_current_page(1)

    def init_zeroconf_account(self):
        active = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
            'active')
        self.xml.get_object('enable_zeroconf_checkbutton2').set_active(active)
        if not gajim.HAVE_ZEROCONF:
            self.xml.get_object('enable_zeroconf_checkbutton2').set_sensitive(
                False)
        self.xml.get_object('zeroconf_notebook').set_sensitive(active)
        # General tab
        st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
            'autoconnect')
        self.xml.get_object('autoconnect_checkbutton2').set_active(st)

        list_no_log_for = gajim.config.get_per('accounts',
            gajim.ZEROCONF_ACC_NAME, 'no_log_for').split()
        if gajim.ZEROCONF_ACC_NAME in list_no_log_for:
            self.xml.get_object('log_history_checkbutton2').set_active(0)
        else:
            self.xml.get_object('log_history_checkbutton2').set_active(1)

        st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
            'sync_with_global_status')
        self.xml.get_object('sync_with_global_status_checkbutton2').set_active(
            st)

        st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
            'use_custom_host')
        self.xml.get_object('custom_port_checkbutton2').set_active(st)
        self.xml.get_object('custom_port_entry2').set_sensitive(st)

        st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
            'custom_port')
        if not st:
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'custom_port', '5298')
            st = '5298'
        self.xml.get_object('custom_port_entry2').set_text(str(st))

        # Personal tab
        gpg_key_label = self.xml.get_object('gpg_key_label2')
        if gajim.ZEROCONF_ACC_NAME in gajim.connections and \
        gajim.connections[gajim.ZEROCONF_ACC_NAME].gpg:
            self.xml.get_object('gpg_choose_button2').set_sensitive(True)
            self.init_account_gpg()
        else:
            gpg_key_label.set_text(_('OpenPGP is not usable on this computer'))
            self.xml.get_object('gpg_choose_button2').set_sensitive(False)

        for opt in ('first_name', 'last_name', 'jabber_id', 'email'):
            st = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'zeroconf_' + opt)
            self.xml.get_object(opt + '_entry2').set_text(st)

    def init_account_gpg(self):
        account = self.current_account
        keyid = gajim.config.get_per('accounts', account, 'keyid')
        keyname = gajim.config.get_per('accounts', account, 'keyname')
        use_gpg_agent = gajim.config.get('use_gpg_agent')

        if account == gajim.ZEROCONF_ACC_NAME:
            widget_name_add = '2'
        else:
            widget_name_add = '1'

        gpg_key_label = self.xml.get_object('gpg_key_label' + widget_name_add)
        gpg_name_label = self.xml.get_object('gpg_name_label' + widget_name_add)
        use_gpg_agent_checkbutton = self.xml.get_object(
            'use_gpg_agent_checkbutton' + widget_name_add)

        if not keyid:
            use_gpg_agent_checkbutton.set_sensitive(False)
            gpg_key_label.set_text(_('No key selected'))
            gpg_name_label.set_text('')
            return

        gpg_key_label.set_text(keyid)
        gpg_name_label.set_text(keyname)
        use_gpg_agent_checkbutton.set_sensitive(True)
        use_gpg_agent_checkbutton.set_active(use_gpg_agent)

    def draw_normal_jid(self):
        account = self.current_account
        self.ignore_events = True
        active = gajim.config.get_per('accounts', account, 'active')
        self.xml.get_object('enable_checkbutton1').set_active(active)
        self.xml.get_object('normal_notebook1').set_sensitive(active)
        if gajim.config.get_per('accounts', account, 'anonymous_auth'):
            self.xml.get_object('anonymous_checkbutton1').set_active(True)
            self.xml.get_object('jid_label1').set_text(_('Server:'))
            save_password = self.xml.get_object('save_password_checkbutton1')
            save_password.set_active(False)
            save_password.set_sensitive(False)
            password_entry = self.xml.get_object('password_entry1')
            password_entry.set_text('')
            password_entry.set_sensitive(False)
            jid = gajim.config.get_per('accounts', account, 'hostname')
        else:
            self.xml.get_object('anonymous_checkbutton1').set_active(False)
            self.xml.get_object('jid_label1').set_text(_('Jabber ID:'))
            savepass = gajim.config.get_per('accounts', account, 'savepass')
            save_password = self.xml.get_object('save_password_checkbutton1')
            save_password.set_sensitive(True)
            save_password.set_active(savepass)
            password_entry = self.xml.get_object('password_entry1')
            if savepass:
                passstr = passwords.get_password(account) or ''
                password_entry.set_sensitive(True)
            else:
                passstr = ''
                password_entry.set_sensitive(False)
            password_entry.set_text(passstr)

            jid = gajim.config.get_per('accounts', account, 'name') \
                + '@' + gajim.config.get_per('accounts', account, 'hostname')
        self.xml.get_object('jid_entry1').set_text(jid)
        self.ignore_events = False

    def init_normal_account(self):
        account = self.current_account
        # Account tab
        self.draw_normal_jid()
        self.xml.get_object('resource_entry1').set_text(gajim.config.get_per(
            'accounts', account, 'resource'))

        client_cert = gajim.config.get_per('accounts', account, 'client_cert')
        self.xml.get_object('cert_entry1').set_text(client_cert)
        client_cert_encrypted = gajim.config.get_per('accounts', account,
            'client_cert_encrypted')
        self.xml.get_object('client_cert_encrypted_checkbutton1').\
            set_active(client_cert_encrypted)

        self.xml.get_object('adjust_priority_with_status_checkbutton1').\
            set_active(gajim.config.get_per('accounts', account,
            'adjust_priority_with_status'))
        spinbutton = self.xml.get_object('priority_spinbutton1')
        if gajim.config.get('enable_negative_priority'):
            spinbutton.set_range(-128, 127)
        else:
            spinbutton.set_range(0, 127)
        spinbutton.set_value(gajim.config.get_per('accounts', account,
            'priority'))

        # Connection tab
        use_env_http_proxy = gajim.config.get_per('accounts', account,
            'use_env_http_proxy')
        self.xml.get_object('use_env_http_proxy_checkbutton1').set_active(
            use_env_http_proxy)
        self.xml.get_object('proxy_hbox1').set_sensitive(not use_env_http_proxy)

        warn_when_insecure_ssl = gajim.config.get_per('accounts', account,
            'warn_when_insecure_ssl_connection')
        self.xml.get_object('warn_when_insecure_connection_checkbutton1').\
            set_active(warn_when_insecure_ssl)

        self.xml.get_object('send_keepalive_checkbutton1').set_active(
            gajim.config.get_per('accounts', account, 'keep_alives_enabled'))

        use_custom_host = gajim.config.get_per('accounts', account,
            'use_custom_host')
        self.xml.get_object('custom_host_port_checkbutton1').set_active(
            use_custom_host)
        custom_host = gajim.config.get_per('accounts', account, 'custom_host')
        if not custom_host:
            custom_host = gajim.config.get_per('accounts', account, 'hostname')
            gajim.config.set_per('accounts', account, 'custom_host',
                custom_host)
        self.xml.get_object('custom_host_entry1').set_text(custom_host)
        custom_port = gajim.config.get_per('accounts', account, 'custom_port')
        if not custom_port:
            custom_port = 5222
            gajim.config.set_per('accounts', account, 'custom_port',
                custom_port)
        self.xml.get_object('custom_port_entry1').set_text(str(custom_port))

        # Personal tab
        gpg_key_label = self.xml.get_object('gpg_key_label1')
        if gajim.HAVE_GPG:
            self.xml.get_object('gpg_choose_button1').set_sensitive(True)
            self.init_account_gpg()
        else:
            gpg_key_label.set_text(_('OpenPGP is not usable on this computer'))
            self.xml.get_object('gpg_choose_button1').set_sensitive(False)

        # General tab
        self.xml.get_object('autoconnect_checkbutton1').set_active(
            gajim.config.get_per('accounts', account, 'autoconnect'))
        self.xml.get_object('autoreconnect_checkbutton1').set_active(gajim.
            config.get_per('accounts', account, 'autoreconnect'))

        list_no_log_for = gajim.config.get_per('accounts', account,
            'no_log_for').split()
        if account in list_no_log_for:
            self.xml.get_object('log_history_checkbutton1').set_active(False)
        else:
            self.xml.get_object('log_history_checkbutton1').set_active(True)

        self.xml.get_object('sync_with_global_status_checkbutton1').set_active(
            gajim.config.get_per('accounts', account,
            'sync_with_global_status'))
        self.xml.get_object('use_ft_proxies_checkbutton1').set_active(
            gajim.config.get_per('accounts', account, 'use_ft_proxies'))

    def on_add_button_clicked(self, widget):
        """
        When add button is clicked: open an account information window
        """
        if 'account_creation_wizard' in gajim.interface.instances:
            gajim.interface.instances['account_creation_wizard'].window.present()
        else:
            gajim.interface.instances['account_creation_wizard'] = \
                AccountCreationWizardWindow()

    def on_remove_button_clicked(self, widget):
        """
        When delete button is clicked: Remove an account from the listStore and
        from the config file
        """
        if not self.current_account:
            return
        account = self.current_account
        if len(gajim.events.get_events(account)):
            dialogs.ErrorDialog(_('Unread events'),
                _('Read all pending events before removing this account.'),
                transient_for=self.window)
            return

        if gajim.config.get_per('accounts', account, 'is_zeroconf'):
            # Should never happen as button is insensitive
            return

        win_opened = False
        if gajim.interface.msg_win_mgr.get_controls(acct=account):
            win_opened = True
        elif account in gajim.interface.instances:
            for key in gajim.interface.instances[account]:
                if gajim.interface.instances[account][key] and key != \
                'remove_account':
                    win_opened = True
                    break
        # Detect if we have opened windows for this account
        def remove(account):
            if account in gajim.interface.instances and \
            'remove_account' in gajim.interface.instances[account]:
                gajim.interface.instances[account]['remove_account'].window.\
                    present()
            else:
                if not account in gajim.interface.instances:
                    gajim.interface.instances[account] = {}
                gajim.interface.instances[account]['remove_account'] = \
                    RemoveAccountWindow(account)
        if win_opened:
            dialogs.ConfirmationDialog(
                _('You have opened chat in account %s') % account,
                _('All chat and groupchat windows will be closed. Do you want to '
                'continue?'),
                on_response_ok = (remove, account))
        else:
            remove(account)

    def on_rename_button_clicked(self, widget):
        if not self.current_account:
            return
        active = gajim.config.get_per('accounts', self.current_account,
            'active') and self.current_account in gajim.connections
        if active and gajim.connections[self.current_account].connected != 0:
            dialogs.ErrorDialog(
                _('You are currently connected to the server'),
                _('To change the account name, you must be disconnected.'),
                transient_for=self.window)
            return
        if len(gajim.events.get_events(self.current_account)):
            dialogs.ErrorDialog(_('Unread events'),
                _('To change the account name, you must read all pending '
                'events.'), transient_for=self.window)
            return
        # Get the new name
        def on_renamed(new_name, old_name):
            if new_name in gajim.connections:
                dialogs.ErrorDialog(_('Account Name Already Used'),
                    _('This name is already used by another of your accounts. '
                    'Please choose another name.'), transient_for=self.window)
                return
            if (new_name == ''):
                dialogs.ErrorDialog(_('Invalid account name'),
                    _('Account name cannot be empty.'),
                    transient_for=self.window)
                return
            if new_name.find(' ') != -1:
                dialogs.ErrorDialog(_('Invalid account name'),
                    _('Account name cannot contain spaces.'),
                    transient_for=self.window)
                return
            if active:
                # update variables
                gajim.interface.instances[new_name] = gajim.interface.instances[
                    old_name]
                gajim.interface.minimized_controls[new_name] = \
                    gajim.interface.minimized_controls[old_name]
                gajim.nicks[new_name] = gajim.nicks[old_name]
                gajim.block_signed_in_notifications[new_name] = \
                    gajim.block_signed_in_notifications[old_name]
                gajim.groups[new_name] = gajim.groups[old_name]
                gajim.gc_connected[new_name] = gajim.gc_connected[old_name]
                gajim.automatic_rooms[new_name] = gajim.automatic_rooms[
                    old_name]
                gajim.newly_added[new_name] = gajim.newly_added[old_name]
                gajim.to_be_removed[new_name] = gajim.to_be_removed[old_name]
                gajim.sleeper_state[new_name] = gajim.sleeper_state[old_name]
                gajim.encrypted_chats[new_name] = gajim.encrypted_chats[
                    old_name]
                gajim.last_message_time[new_name] = \
                    gajim.last_message_time[old_name]
                gajim.status_before_autoaway[new_name] = \
                    gajim.status_before_autoaway[old_name]
                gajim.transport_avatar[new_name] = gajim.transport_avatar[old_name]
                gajim.gajim_optional_features[new_name] = \
                    gajim.gajim_optional_features[old_name]
                gajim.caps_hash[new_name] = gajim.caps_hash[old_name]

                gajim.contacts.change_account_name(old_name, new_name)
                gajim.events.change_account_name(old_name, new_name)

                # change account variable for chat / gc controls
                gajim.interface.msg_win_mgr.change_account_name(old_name, new_name)
                # upgrade account variable in opened windows
                for kind in ('infos', 'disco', 'gc_config', 'search',
                'online_dialog', 'sub_request'):
                    for j in gajim.interface.instances[new_name][kind]:
                        gajim.interface.instances[new_name][kind][j].account = \
                            new_name

                # ServiceCache object keep old property account
                if hasattr(gajim.connections[old_name], 'services_cache'):
                    gajim.connections[old_name].services_cache.account = \
                        new_name
                del gajim.interface.instances[old_name]
                del gajim.interface.minimized_controls[old_name]
                del gajim.nicks[old_name]
                del gajim.block_signed_in_notifications[old_name]
                del gajim.groups[old_name]
                del gajim.gc_connected[old_name]
                del gajim.automatic_rooms[old_name]
                del gajim.newly_added[old_name]
                del gajim.to_be_removed[old_name]
                del gajim.sleeper_state[old_name]
                del gajim.encrypted_chats[old_name]
                del gajim.last_message_time[old_name]
                del gajim.status_before_autoaway[old_name]
                del gajim.transport_avatar[old_name]
                del gajim.gajim_optional_features[old_name]
                del gajim.caps_hash[old_name]
                gajim.connections[old_name].name = new_name
                gajim.connections[old_name].pep_change_account_name(new_name)
                gajim.connections[old_name].caps_change_account_name(new_name)
                gajim.connections[new_name] = gajim.connections[old_name]
                del gajim.connections[old_name]
            gajim.config.add_per('accounts', new_name)
            old_config = gajim.config.get_per('accounts', old_name)
            for opt in old_config:
                gajim.config.set_per('accounts', new_name, opt, old_config[opt])
            gajim.config.del_per('accounts', old_name)
            if self.current_account == old_name:
                self.current_account = new_name
            if old_name == gajim.ZEROCONF_ACC_NAME:
                gajim.ZEROCONF_ACC_NAME = new_name
            # refresh roster
            gajim.interface.roster.setup_and_draw_roster()
            self.init_accounts()
            self.select_account(new_name)

        title = _('Rename Account')
        message = _('Enter a new name for account %s') % self.current_account
        old_text = self.current_account
        dialogs.InputDialog(title, message, old_text, is_modal=False,
            ok_handler=(on_renamed, self.current_account),
            transient_for=self.window)

    def option_changed(self, option, value):
        return gajim.config.get_per('accounts', self.current_account, option) \
            != value

    def on_jid_entry1_focus_out_event(self, widget, event):
        if self.ignore_events:
            return
        jid = widget.get_text()
        # check if jid is conform to RFC and stringprep it
        try:
            jid = helpers.parse_jid(jid)
        except helpers.InvalidFormat as s:
            if not widget.is_focus():
                pritext = _('Invalid Jabber ID')
                dialogs.ErrorDialog(pritext, str(s), transient_for=self.window)
                GLib.idle_add(lambda: widget.grab_focus())
            return True

        jid_splited = jid.split('@', 1)
        if len(jid_splited) != 2 and not gajim.config.get_per('accounts',
        self.current_account, 'anonymous_auth'):
            if not widget.is_focus():
                pritext = _('Invalid Jabber ID')
                sectext = \
                    _('A Jabber ID must be in the form "user@servername".')
                dialogs.ErrorDialog(pritext, sectext, transient_for=self.window)
                GLib.idle_add(lambda: widget.grab_focus())
            return True


        if gajim.config.get_per('accounts', self.current_account,
        'anonymous_auth'):
            gajim.config.set_per('accounts', self.current_account, 'hostname',
                jid_splited[0])
            if self.option_changed('hostname', jid_splited[0]):
                self.need_relogin = True
        else:
            if self.option_changed('name', jid_splited[0]) or \
            self.option_changed('hostname', jid_splited[1]):
                self.need_relogin = True

            gajim.config.set_per('accounts', self.current_account, 'name',
                jid_splited[0])
            gajim.config.set_per('accounts', self.current_account, 'hostname',
                jid_splited[1])

    def on_cert_entry1_focus_out_event(self, widget, event):
        if self.ignore_events:
            return
        client_cert = widget.get_text()
        if self.option_changed('client_cert', client_cert):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account, 'client_cert',
            client_cert)

    def on_anonymous_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        active = widget.get_active()
        gajim.config.set_per('accounts', self.current_account, 'anonymous_auth',
            active)
        self.draw_normal_jid()

    def on_password_entry1_changed(self, widget):
        if self.ignore_events:
            return
        passwords.save_password(self.current_account, widget.get_text())

    def on_save_password_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        active = widget.get_active()
        password_entry = self.xml.get_object('password_entry1')
        password_entry.set_sensitive(active)
        gajim.config.set_per('accounts', self.current_account, 'savepass',
            active)
        if active:
            password = password_entry.get_text()
            passwords.save_password(self.current_account, password)
        else:
            passwords.save_password(self.current_account, '')

    def on_resource_entry1_focus_out_event(self, widget, event):
        if self.ignore_events:
            return
        resource = self.xml.get_object('resource_entry1').get_text()
        try:
            resource = helpers.parse_resource(resource)
        except helpers.InvalidFormat as s:
            if not widget.is_focus():
                pritext = _('Invalid Jabber ID')
                dialogs.ErrorDialog(pritext, str(s), transient_for=self.window)
                GLib.idle_add(lambda: widget.grab_focus())
            return True

        if self.option_changed('resource', resource):
            self.need_relogin = True

        gajim.config.set_per('accounts', self.current_account, 'resource',
            resource)

    def on_adjust_priority_with_status_checkbutton1_toggled(self, widget):
        self.xml.get_object('priority_spinbutton1').set_sensitive(
            not widget.get_active())
        self.on_checkbutton_toggled(widget, 'adjust_priority_with_status',
            account = self.current_account)

    def on_priority_spinbutton1_value_changed(self, widget):
        prio = widget.get_value_as_int()

        if self.option_changed('priority', prio):
            self.resend_presence = True

        gajim.config.set_per('accounts', self.current_account, 'priority', prio)

    def on_synchronise_contacts_button1_clicked(self, widget):
        try:
            dialogs.SynchroniseSelectAccountDialog(self.current_account)
        except GajimGeneralException:
            # If we showed ErrorDialog, there will not be dialog instance
            return

    def on_change_password_button1_clicked(self, widget):
        def on_changed(new_password):
            if new_password is not None:
                gajim.connections[self.current_account].change_password(
                    new_password)
                if self.xml.get_object('save_password_checkbutton1').\
                get_active():
                    self.xml.get_object('password_entry1').set_text(
                        new_password)

        try:
            dialogs.ChangePasswordDialog(self.current_account, on_changed,
                self.window)
        except GajimGeneralException:
            # if we showed ErrorDialog, there will not be dialog instance
            return

    def on_client_cert_encrypted_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'client_cert_encrypted',
            account=self.current_account)

    def on_autoconnect_checkbutton_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'autoconnect',
            account=self.current_account)

    def on_autoreconnect_checkbutton_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'autoreconnect',
            account=self.current_account)

    def on_log_history_checkbutton_toggled(self, widget):
        if self.ignore_events:
            return
        list_no_log_for = gajim.config.get_per('accounts', self.current_account,
            'no_log_for').split()
        if self.current_account in list_no_log_for:
            list_no_log_for.remove(self.current_account)

        if not widget.get_active():
            list_no_log_for.append(self.current_account)
        gajim.config.set_per('accounts', self.current_account, 'no_log_for',
            ' '.join(list_no_log_for))

    def on_sync_with_global_status_checkbutton_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'sync_with_global_status',
            account=self.current_account)
        gajim.interface.roster.update_status_combobox()

    def on_use_ft_proxies_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'use_ft_proxies',
            account=self.current_account)

    def on_use_env_http_proxy_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'use_env_http_proxy',
            account=self.current_account)
        hbox = self.xml.get_object('proxy_hbox1')
        hbox.set_sensitive(not widget.get_active())

    def on_proxies_combobox1_changed(self, widget):
        active = widget.get_active()
        proxy = widget.get_model()[active][0]
        if proxy == _('None'):
            proxy = ''

        if self.option_changed('proxy', proxy):
            self.need_relogin = True

        gajim.config.set_per('accounts', self.current_account, 'proxy', proxy)

    def on_manage_proxies_button1_clicked(self, widget):
        if 'manage_proxies' in gajim.interface.instances:
            gajim.interface.instances['manage_proxies'].window.present()
        else:
            gajim.interface.instances['manage_proxies'] = ManageProxiesWindow(
                self.window)

    def on_warn_when_insecure_connection_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return

        self.on_checkbutton_toggled(widget, 'warn_when_insecure_ssl_connection',
            account=self.current_account)

    def on_send_keepalive_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        self.on_checkbutton_toggled(widget, 'keep_alives_enabled',
            account=self.current_account)
        gajim.config.set_per('accounts', self.current_account,
            'ping_alives_enabled', widget.get_active())

    def on_custom_host_port_checkbutton1_toggled(self, widget):
        if self.option_changed('use_custom_host', widget.get_active()):
            self.need_relogin = True

        self.on_checkbutton_toggled(widget, 'use_custom_host',
            account=self.current_account)
        active = widget.get_active()
        self.xml.get_object('custom_host_port_hbox1').set_sensitive(active)

    def on_custom_host_entry1_changed(self, widget):
        if self.ignore_events:
            return
        host = widget.get_text()
        if self.option_changed('custom_host', host):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account, 'custom_host',
            host)

    def on_custom_port_entry_focus_out_event(self, widget, event):
        if self.ignore_events:
            return
        custom_port = widget.get_text()
        try:
            custom_port = int(custom_port)
        except Exception:
            if not widget.is_focus():
                dialogs.ErrorDialog(_('Invalid entry'),
                    _('Custom port must be a port number.'),
                    transient_for=self.window)
                GLib.idle_add(lambda: widget.grab_focus())
            return True
        if self.option_changed('custom_port', custom_port):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account, 'custom_port',
            custom_port)

    def on_gpg_choose_button_clicked(self, widget, data = None):
        if self.current_account in gajim.connections and \
        gajim.connections[self.current_account].gpg:
            secret_keys = gajim.connections[self.current_account].\
                    ask_gpg_secrete_keys()

        # self.current_account is None and/or gajim.connections is {}
        else:
            if gajim.HAVE_GPG:
                secret_keys = gpg.GnuPG().get_secret_keys()
            else:
                secret_keys = []
        if not secret_keys:
            dialogs.ErrorDialog(_('Failed to get secret keys'),
                _('There is no OpenPGP secret key available.'),
                transient_for=self.window)
        secret_keys[_('None')] = _('None')

        def on_key_selected(keyID):
            if keyID is None:
                return
            if self.current_account == gajim.ZEROCONF_ACC_NAME:
                wiget_name_ext = '2'
            else:
                wiget_name_ext = '1'
            gpg_key_label = self.xml.get_object('gpg_key_label' + \
                wiget_name_ext)
            gpg_name_label = self.xml.get_object('gpg_name_label' + \
                wiget_name_ext)
            use_gpg_agent_checkbutton = self.xml.get_object(
                'use_gpg_agent_checkbutton' + wiget_name_ext)
            if keyID[0] == _('None'):
                gpg_key_label.set_text(_('No key selected'))
                gpg_name_label.set_text('')
                use_gpg_agent_checkbutton.set_sensitive(False)
                if self.option_changed('keyid', ''):
                    self.need_relogin = True
                gajim.config.set_per('accounts', self.current_account,
                    'keyname', '')
                gajim.config.set_per('accounts', self.current_account, 'keyid',
                    '')
            else:
                gpg_key_label.set_text(keyID[0])
                gpg_name_label.set_text(keyID[1])
                use_gpg_agent_checkbutton.set_sensitive(True)
                if self.option_changed('keyid', keyID[0]):
                    self.need_relogin = True
                gajim.config.set_per('accounts', self.current_account,
                    'keyname', keyID[1])
                gajim.config.set_per('accounts', self.current_account, 'keyid',
                    keyID[0])

        dialogs.ChooseGPGKeyDialog(_('OpenPGP Key Selection'),
            _('Choose your OpenPGP key'), secret_keys, on_key_selected,
            transient_for=self.window)

    def on_use_gpg_agent_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_gpg_agent')

    def on_edit_details_button1_clicked(self, widget):
        if self.current_account not in gajim.interface.instances:
            dlg = dialogs.ErrorDialog(_('No such account available'),
                _('You must create your account before editing your personal '
                'information.'), transient_for=self.window)
            return

        # show error dialog if account is newly created (not in gajim.connections)
        if self.current_account not in gajim.connections or \
        gajim.connections[self.current_account].connected < 2:
            dialogs.ErrorDialog(_('You are not connected to the server'),
                _('Without a connection, you can not edit your personal '
                'information.'), transient_for=self.window)
            return

        if not gajim.connections[self.current_account].vcard_supported:
            dialogs.ErrorDialog(_("Your server doesn't support vCard"),
                _("Your server can't save your personal information."),
                transient_for=self.window)
            return

        jid = gajim.get_jid_from_account(self.current_account)
        if 'profile' not in gajim.interface.instances[self.current_account]:
            gajim.interface.instances[self.current_account]['profile'] = \
                profile_window.ProfileWindow(self.current_account, transient_for=self.window)
            gajim.connections[self.current_account].request_vcard(jid)

    def on_checkbutton_toggled(self, widget, config_name,
            change_sensitivity_widgets = None, account = None):
        if account:
            gajim.config.set_per('accounts', account, config_name,
                widget.get_active())
        else:
            gajim.config.set(config_name, widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def on_merge_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'mergeaccounts')
        if len(gajim.connections) >= 2: # Do not merge accounts if only one active
            gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
        else:
            gajim.interface.roster.regroup = False
        gajim.interface.roster.setup_and_draw_roster()

    def _disable_account(self, account):
        gajim.interface.roster.close_all(account)
        if account == gajim.ZEROCONF_ACC_NAME:
            gajim.connections[account].disable_account()
        del gajim.connections[account]
        del gajim.interface.instances[account]
        del gajim.interface.minimized_controls[account]
        del gajim.nicks[account]
        del gajim.block_signed_in_notifications[account]
        del gajim.groups[account]
        gajim.contacts.remove_account(account)
        del gajim.gc_connected[account]
        del gajim.automatic_rooms[account]
        del gajim.to_be_removed[account]
        del gajim.newly_added[account]
        del gajim.sleeper_state[account]
        del gajim.encrypted_chats[account]
        del gajim.last_message_time[account]
        del gajim.status_before_autoaway[account]
        del gajim.transport_avatar[account]
        del gajim.gajim_optional_features[account]
        del gajim.caps_hash[account]
        if len(gajim.connections) >= 2:
            # Do not merge accounts if only one exists
            gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
        else:
            gajim.interface.roster.regroup = False
        gajim.interface.roster.setup_and_draw_roster()
        gajim.interface.roster.set_actions_menu_needs_rebuild()

    def _enable_account(self, account):
        if account == gajim.ZEROCONF_ACC_NAME:
            gajim.connections[account] = connection_zeroconf.ConnectionZeroconf(
                account)
            if gajim.connections[account].gpg:
                self.xml.get_object('gpg_choose_button2').set_sensitive(True)
        else:
            gajim.connections[account] = common.connection.Connection(account)
            if gajim.connections[account].gpg:
                self.xml.get_object('gpg_choose_button1').set_sensitive(True)
        self.init_account_gpg()
        # update variables
        gajim.interface.instances[account] = {'infos': {},
            'disco': {}, 'gc_config': {}, 'search': {}, 'online_dialog': {},
            'sub_request': {}}
        gajim.interface.minimized_controls[account] = {}
        gajim.connections[account].connected = 0
        gajim.groups[account] = {}
        gajim.contacts.add_account(account)
        gajim.gc_connected[account] = {}
        gajim.automatic_rooms[account] = {}
        gajim.newly_added[account] = []
        gajim.to_be_removed[account] = []
        if account == gajim.ZEROCONF_ACC_NAME:
            gajim.nicks[account] = gajim.ZEROCONF_ACC_NAME
        else:
            gajim.nicks[account] = gajim.config.get_per('accounts', account,
                'name')
        gajim.block_signed_in_notifications[account] = True
        gajim.sleeper_state[account] = 'off'
        gajim.encrypted_chats[account] = []
        gajim.last_message_time[account] = {}
        gajim.status_before_autoaway[account] = ''
        gajim.transport_avatar[account] = {}
        gajim.gajim_optional_features[account] = []
        gajim.caps_hash[account] = ''
        helpers.update_optional_features(account)
        # refresh roster
        if len(gajim.connections) >= 2:
            # Do not merge accounts if only one exists
            gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
        else:
            gajim.interface.roster.regroup = False
        gajim.interface.roster.setup_and_draw_roster()
        gajim.interface.roster.set_actions_menu_needs_rebuild()

    def on_enable_zeroconf_checkbutton2_toggled(self, widget):
        # don't do anything if there is an account with the local name but is a
        # normal account
        if self.ignore_events:
            return
        if self.current_account in gajim.connections and \
        gajim.connections[self.current_account].connected > 0:
            self.ignore_events = True
            self.xml.get_object('enable_zeroconf_checkbutton2').set_active(True)
            self.ignore_events = False
            dialogs.ErrorDialog(
                _('You are currently connected to the server'),
                _('To disable the account, you must be disconnected.'),
                transient_for=self.window)
            return
        if gajim.ZEROCONF_ACC_NAME in gajim.connections and not \
        gajim.connections[gajim.ZEROCONF_ACC_NAME].is_zeroconf:
            gajim.nec.push_incoming_event(InformationEvent(None,
                conn=gajim.connections[gajim.ZEROCONF_ACC_NAME],
                level='error', pri_txt=_('Account Local already exists.'),
                sec_txt=_('Please rename or remove it before enabling '
                'link-local messaging.')))
            return

        if gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'active') \
        and not widget.get_active():
            self.xml.get_object('zeroconf_notebook').set_sensitive(False)
            # disable
            self._disable_account(gajim.ZEROCONF_ACC_NAME)

        elif not gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
        'active') and widget.get_active():
            self.xml.get_object('zeroconf_notebook').set_sensitive(True)
            # enable (will create new account if not present)
            self._enable_account(gajim.ZEROCONF_ACC_NAME)

        self.on_checkbutton_toggled(widget, 'active',
            account=gajim.ZEROCONF_ACC_NAME)

    def on_enable_checkbutton1_toggled(self, widget):
        if self.ignore_events:
            return
        if self.current_account in gajim.connections and \
        gajim.connections[self.current_account].connected > 0:
            # connecting or connected
            self.ignore_events = True
            self.xml.get_object('enable_checkbutton1').set_active(True)
            self.ignore_events = False
            dialogs.ErrorDialog(
                _('You are currently connected to the server'),
                _('To disable the account, you must be disconnected.'),
                transient_for=self.window)
            return
        # add/remove account in roster and all variables
        if widget.get_active():
            # enable
            self._enable_account(self.current_account)
        else:
            # disable
            self._disable_account(self.current_account)
        self.on_checkbutton_toggled(widget, 'active',
            account=self.current_account, change_sensitivity_widgets=[
            self.xml.get_object('normal_notebook1')])

    def on_custom_port_checkbutton2_toggled(self, widget):
        self.xml.get_object('custom_port_entry2').set_sensitive(
            widget.get_active())
        self.on_checkbutton_toggled(widget, 'use_custom_host',
            account=self.current_account)
        if not widget.get_active():
            self.xml.get_object('custom_port_entry2').set_text('5298')

    def on_first_name_entry2_changed(self, widget):
        if self.ignore_events:
            return
        name = widget.get_text()
        if self.option_changed('zeroconf_first_name', name):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account,
            'zeroconf_first_name', name)

    def on_last_name_entry2_changed(self, widget):
        if self.ignore_events:
            return
        name = widget.get_text()
        if self.option_changed('zeroconf_last_name', name):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account,
            'zeroconf_last_name', name)

    def on_jabber_id_entry2_changed(self, widget):
        if self.ignore_events:
            return
        id_ = widget.get_text()
        if self.option_changed('zeroconf_jabber_id', id_):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account,
            'zeroconf_jabber_id', id_)

    def on_email_entry2_changed(self, widget):
        if self.ignore_events:
            return
        email = widget.get_text()
        if self.option_changed('zeroconf_email', email):
            self.need_relogin = True
        gajim.config.set_per('accounts', self.current_account,
            'zeroconf_email', email)

class FakeDataForm(Gtk.Table, object):
    """
    Class for forms that are in XML format <entry1>value1</entry1> infos in a
    table {entry1: value1}
    """

    def __init__(self, infos, selectable=False):
        GObject.GObject.__init__(self)
        self.infos = infos
        self.selectable = selectable
        self.entries = {}
        self._draw_table()

    def _draw_table(self):
        """
        Draw the table
        """
        nbrow = 0
        if 'instructions' in self.infos:
            nbrow = 1
            self.resize(rows = nbrow, columns = 2)
            label = Gtk.Label(label=self.infos['instructions'])
            if self.selectable:
                label.set_selectable(True)
            self.attach(label, 0, 2, 0, 1, 0, 0, 0, 0)
        for name in self.infos.keys():
            if name in ('key', 'instructions', 'x', 'registered'):
                continue
            if not name:
                continue

            nbrow = nbrow + 1
            self.resize(rows = nbrow, columns = 2)
            label = Gtk.Label(label=name.capitalize() + ':')
            self.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
            entry = Gtk.Entry()
            entry.set_activates_default(True)
            if self.infos[name]:
                entry.set_text(self.infos[name])
            if name == 'password':
                entry.set_visibility(False)
            self.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
            self.entries[name] = entry
            if nbrow == 1:
                entry.grab_focus()

    def get_infos(self):
        for name in self.entries.keys():
            self.infos[name] = self.entries[name].get_text()
        return self.infos

class ServiceRegistrationWindow:
    """
    Class for Service registration window. Window that appears when we want to
    subscribe to a service if is_form we use dataforms_widget else we use
    service_registarion_window
    """
    def __init__(self, service, infos, account, is_form):
        self.service = service
        self.account = account
        self.is_form = is_form
        self.xml = gtkgui_helpers.get_gtk_builder('service_registration_window.ui')
        self.window = self.xml.get_object('service_registration_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        if self.is_form:
            dataform = dataforms.ExtendForm(node = infos)
            self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
            if self.data_form_widget.title:
                self.window.set_title('%s - Gajim' % self.data_form_widget.title)
            table = self.xml.get_object('table')
            table.attach(self.data_form_widget, 0, 2, 0, 1)
        else:
            if 'registered' in infos:
                self.window.set_title(_('Edit %s') % service)
            else:
                self.window.set_title(_('Register to %s') % service)
            self.data_form_widget = FakeDataForm(infos)
            table = self.xml.get_object('table')
            table.attach(self.data_form_widget, 0, 2, 0, 1)

        self.xml.connect_signals(self)
        self.window.show_all()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_ok_button_clicked(self, widget):
        # send registration info to the core
        if self.is_form:
            form = self.data_form_widget.data_form
            gajim.connections[self.account].register_agent(self.service,
                    form, True) # True is for is_form
        else:
            infos = self.data_form_widget.get_infos()
            if 'instructions' in infos:
                del infos['instructions']
            if 'registered' in infos:
                del infos['registered']
            gajim.connections[self.account].register_agent(self.service, infos)

        self.window.destroy()

class GroupchatConfigWindow:

    def __init__(self, account, room_jid, form=None):
        self.account = account
        self.room_jid = room_jid
        self.form = form
        self.remove_button = {}
        self.affiliation_treeview = {}
        self.start_users_dict = {} # list at the beginning
        self.affiliation_labels = {'outcast': _('Ban List'),
            'member': _('Member List'), 'owner': _('Owner List'),
            'admin':_('Administrator List')}

        self.xml = gtkgui_helpers.get_gtk_builder('data_form_window.ui',
            'data_form_window')
        self.window = self.xml.get_object('data_form_window')
        self.window.set_transient_for(gajim.interface.roster.window)

        if self.form:
            config_vbox = self.xml.get_object('config_vbox')
            self.data_form_widget = dataforms_widget.DataFormWidget(self.form)
            # hide scrollbar of this data_form_widget, we already have in this
            # widget
            sw = self.data_form_widget.xml.get_object(
                'single_form_scrolledwindow')
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
            if self.form.title:
                self.xml.get_object('title_label').set_text(self.form.title)
            else:
                self.xml.get_object('title_hseparator').set_no_show_all(True)
                self.xml.get_object('title_hseparator').hide()

            self.data_form_widget.show()
            config_vbox.pack_start(self.data_form_widget, True, True, 0)
        else:
            self.xml.get_object('title_label').set_no_show_all(True)
            self.xml.get_object('title_label').hide()
            self.xml.get_object('title_hseparator').set_no_show_all(True)
            self.xml.get_object('title_hseparator').hide()
            self.xml.get_object('config_hseparator').set_no_show_all(True)
            self.xml.get_object('config_hseparator').hide()

        # Draw the edit affiliation list things
        add_on_vbox = self.xml.get_object('add_on_vbox')

        for affiliation in self.affiliation_labels.keys():
            self.start_users_dict[affiliation] = {}
            hbox = Gtk.HBox(spacing=5)
            add_on_vbox.pack_start(hbox, False, True, 0)

            label = Gtk.Label(label=self.affiliation_labels[affiliation])
            hbox.pack_start(label, False, True, 0)

            bb = Gtk.HButtonBox()
            bb.set_layout(Gtk.ButtonBoxStyle.END)
            bb.set_spacing(5)
            hbox.pack_start(bb, True, True, 0)
            add_button = Gtk.Button(stock=Gtk.STOCK_ADD)
            add_button.connect('clicked', self.on_add_button_clicked,
                affiliation)
            bb.pack_start(add_button, True, True, 0)
            self.remove_button[affiliation] = Gtk.Button(stock=Gtk.STOCK_REMOVE)
            self.remove_button[affiliation].set_sensitive(False)
            self.remove_button[affiliation].connect('clicked',
                    self.on_remove_button_clicked, affiliation)
            bb.pack_start(self.remove_button[affiliation], True, True, 0)

            # jid, reason, nick, role
            liststore = Gtk.ListStore(str, str, str, str)
            self.affiliation_treeview[affiliation] = Gtk.TreeView(liststore)
            self.affiliation_treeview[affiliation].get_selection().set_mode(
                Gtk.SelectionMode.MULTIPLE)
            self.affiliation_treeview[affiliation].connect('cursor-changed',
                self.on_affiliation_treeview_cursor_changed, affiliation)
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(_('JID'), renderer)
            col.add_attribute(renderer, 'text', 0)
            col.set_resizable(True)
            col.set_sort_column_id(0)
            self.affiliation_treeview[affiliation].append_column(col)

            if affiliation == 'outcast':
                renderer = Gtk.CellRendererText()
                renderer.set_property('editable', True)
                renderer.connect('edited', self.on_cell_edited)
                col = Gtk.TreeViewColumn(_('Reason'), renderer)
                col.add_attribute(renderer, 'text', 1)
                col.set_resizable(True)
                col.set_sort_column_id(1)
                self.affiliation_treeview[affiliation].append_column(col)
            elif affiliation == 'member':
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(_('Nick'), renderer)
                col.add_attribute(renderer, 'text', 2)
                col.set_resizable(True)
                col.set_sort_column_id(2)
                self.affiliation_treeview[affiliation].append_column(col)
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(_('Role'), renderer)
                col.add_attribute(renderer, 'text', 3)
                col.set_resizable(True)
                col.set_sort_column_id(3)
                self.affiliation_treeview[affiliation].append_column(col)

            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            sw.add(self.affiliation_treeview[affiliation])
            add_on_vbox.pack_start(sw, True, True, 0)
            gajim.connections[self.account].get_affiliation_list(self.room_jid,
                affiliation)

        self.xml.connect_signals(self)
        self.window.show_all()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_cell_edited(self, cell, path, new_text):
        model = self.affiliation_treeview['outcast'].get_model()
        new_text = new_text
        iter_ = model.get_iter(path)
        model[iter_][1] = new_text

    def on_add_button_clicked(self, widget, affiliation):
        if affiliation == 'outcast':
            title = _('Banning...')
            #You can move '\n' before user@domain if that line is TOO BIG
            prompt = _('<b>Whom do you want to ban?</b>\n\n')
        elif affiliation == 'member':
            title = _('Adding Member...')
            prompt = _('<b>Whom do you want to make a member?</b>\n\n')
        elif affiliation == 'owner':
            title = _('Adding Owner...')
            prompt = _('<b>Whom do you want to make an owner?</b>\n\n')
        else:
            title = _('Adding Administrator...')
            prompt = _('<b>Whom do you want to make an administrator?</b>\n\n')
        prompt += _('Can be one of the following:\n'
            '1. user@domain/resource (only that resource matches).\n'
            '2. user@domain (any resource matches).\n'
            '3. domain/resource (only that resource matches).\n'
            '4. domain (the domain itself matches, as does any user@domain,\n'
            'domain/resource, or address containing a subdomain).')

        def on_ok(jid):
            if not jid:
                return
            model = self.affiliation_treeview[affiliation].get_model()
            model.append((jid, '', '', ''))
        dialogs.InputDialog(title, prompt, ok_handler=on_ok)

    def on_remove_button_clicked(self, widget, affiliation):
        selection = self.affiliation_treeview[affiliation].get_selection()
        model, paths = selection.get_selected_rows()
        row_refs = []
        for path in paths:
            row_refs.append(Gtk.TreeRowReference.new(model, path))
        for row_ref in row_refs:
            path = row_ref.get_path()
            iter_ = model.get_iter(path)
            model.remove(iter_)
        self.remove_button[affiliation].set_sensitive(False)

    def on_affiliation_treeview_cursor_changed(self, widget, affiliation):
        self.remove_button[affiliation].set_sensitive(True)

    def affiliation_list_received(self, users_dict):
        """
        Fill the affiliation treeview
        """
        for jid in users_dict:
            affiliation = users_dict[jid]['affiliation']
            if affiliation not in self.affiliation_labels.keys():
                # Unknown affiliation or 'none' affiliation, do not show it
                continue
            self.start_users_dict[affiliation][jid] = users_dict[jid]
            tv = self.affiliation_treeview[affiliation]
            model = tv.get_model()
            reason = users_dict[jid].get('reason', '')
            nick = users_dict[jid].get('nick', '')
            role = users_dict[jid].get('role', '')
            model.append((jid, reason, nick, role))

    def on_data_form_window_destroy(self, widget):
        del gajim.interface.instances[self.account]['gc_config'][self.room_jid]

    def on_ok_button_clicked(self, widget):
        if self.form:
            form = self.data_form_widget.data_form
            gajim.connections[self.account].send_gc_config(self.room_jid, form)
        for affiliation in self.affiliation_labels.keys():
            users_dict = {}
            actual_jid_list = []
            model = self.affiliation_treeview[affiliation].get_model()
            iter_ = model.get_iter_first()
            # add new jid
            while iter_:
                jid = model[iter_][0]
                actual_jid_list.append(jid)
                if jid not in self.start_users_dict[affiliation] or \
                (affiliation == 'outcast' and 'reason' in self.start_users_dict[
                affiliation][jid] and self.start_users_dict[affiliation][jid]\
                ['reason'] != model[iter_][1]):
                    users_dict[jid] = {'affiliation': affiliation}
                    if affiliation == 'outcast':
                        users_dict[jid]['reason'] = model[iter_][1]
                iter_ = model.iter_next(iter_)
            # remove removed one
            for jid in self.start_users_dict[affiliation]:
                if jid not in actual_jid_list:
                    users_dict[jid] = {'affiliation': 'none'}
            if users_dict:
                gajim.connections[self.account].send_gc_affiliation_list(
                    self.room_jid, users_dict)
        self.window.destroy()

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
    """
    Ask for removing from gajim only or from gajim and server too and do
    removing of the account given
    """

    def on_remove_account_window_destroy(self, widget):
        if self.account in gajim.interface.instances:
            del gajim.interface.instances[self.account]['remove_account']

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self, account):
        self.account = account
        xml = gtkgui_helpers.get_gtk_builder('remove_account_window.ui')
        self.window = xml.get_object('remove_account_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        self.remove_and_unregister_radiobutton = xml.get_object(
                'remove_and_unregister_radiobutton')
        self.window.set_title(_('Removing %s account') % self.account)
        xml.connect_signals(self)
        self.window.show_all()

    def on_remove_button_clicked(self, widget):
        def remove():
            if self.account in gajim.connections and \
            gajim.connections[self.account].connected and \
            not self.remove_and_unregister_radiobutton.get_active():
                # change status to offline only if we will not remove this JID from
                # server
                gajim.connections[self.account].change_status('offline', 'offline')
            if self.remove_and_unregister_radiobutton.get_active():
                if not self.account in gajim.connections:
                    dialogs.ErrorDialog(
                        _('Account is disabled'),
                        _('To unregister from a server, account must be '
                        'enabled.'))
                    return
                if not gajim.connections[self.account].password:
                    def on_ok(passphrase, checked):
                        if passphrase == -1:
                            # We don't remove account cause we canceled pw window
                            return
                        gajim.connections[self.account].password = passphrase
                        gajim.connections[self.account].unregister_account(
                                self._on_remove_success)

                    dialogs.PassphraseDialog(
                            _('Password Required'),
                            _('Enter your password for account %s') % self.account,
                            _('Save password'), ok_handler=on_ok)
                    return
                gajim.connections[self.account].unregister_account(
                        self._on_remove_success)
            else:
                self._on_remove_success(True)

        if self.account in gajim.connections and \
        gajim.connections[self.account].connected:
            dialogs.ConfirmationDialog(
                _('Account "%s" is connected to the server') % self.account,
                _('If you remove it, the connection will be lost.'),
                on_response_ok=remove)
        else:
            remove()

    def on_remove_responce_ok(self, is_checked):
        if is_checked[0]:
            self._on_remove_success(True)

    def _on_remove_success(self, res):
        # action of unregistration has failed, we don't remove the account
        # Error message is send by connect_and_auth()
        if not res:
            dialogs.ConfirmationDialogDoubleRadio(
                    _('Connection to server %s failed') % self.account,
                    _('What would you like to do?'),
                    _('Remove only from Gajim'),
                    _('Don\'t remove anything. I\'ll try again later'),
                    on_response_ok=self.on_remove_responce_ok, is_modal=False)
            return
        # Close all opened windows
        gajim.interface.roster.close_all(self.account, force=True)
        if self.account in gajim.connections:
            gajim.connections[self.account].disconnect(on_purpose=True)
            gajim.connections[self.account].cleanup()
            del gajim.connections[self.account]
        gajim.logger.remove_roster(gajim.get_jid_from_account(self.account))
        gajim.config.del_per('accounts', self.account)
        del gajim.interface.instances[self.account]
        if self.account in gajim.nicks:
            del gajim.interface.minimized_controls[self.account]
            del gajim.nicks[self.account]
            del gajim.block_signed_in_notifications[self.account]
            del gajim.groups[self.account]
            gajim.contacts.remove_account(self.account)
            del gajim.gc_connected[self.account]
            del gajim.automatic_rooms[self.account]
            del gajim.to_be_removed[self.account]
            del gajim.newly_added[self.account]
            del gajim.sleeper_state[self.account]
            del gajim.encrypted_chats[self.account]
            del gajim.last_message_time[self.account]
            del gajim.status_before_autoaway[self.account]
            del gajim.transport_avatar[self.account]
            del gajim.gajim_optional_features[self.account]
            del gajim.caps_hash[self.account]
        if len(gajim.connections) >= 2: # Do not merge accounts if only one exists
            gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
        else:
            gajim.interface.roster.regroup = False
        gajim.interface.roster.setup_and_draw_roster()
        gajim.interface.roster.set_actions_menu_needs_rebuild()
        if 'accounts' in gajim.interface.instances:
            gajim.interface.instances['accounts'].init_accounts()
            gajim.interface.instances['accounts'].init_account()
        self.window.destroy()

#---------- ManageBookmarksWindow class -------------#
class ManageBookmarksWindow:
    def __init__(self):
        self.xml = gtkgui_helpers.get_gtk_builder('manage_bookmarks_window.ui')
        self.window = self.xml.get_object('manage_bookmarks_window')
        self.window.set_transient_for(gajim.interface.roster.window)

        # Account-JID, RoomName, Room-JID, Autojoin, Minimize, Passowrd, Nick,
        # Show_Status
        self.treestore = Gtk.TreeStore(str, str, str, bool, bool, str, str, str)
        self.treestore.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        # Store bookmarks in treeview.
        for account in gajim.connections:
            if gajim.connections[account].connected <= 1:
                continue
            if gajim.connections[account].is_zeroconf:
                continue
            if not gajim.connections[account].private_storage_supported:
                continue
            iter_ = self.treestore.append(None, [None, account, None, None,
                    None, None, None, None])

            for bookmark in gajim.connections[account].bookmarks:
                if bookmark['name'] == '':
                    # No name was given for this bookmark.
                    # Use the first part of JID instead...
                    name = bookmark['jid'].split("@")[0]
                    bookmark['name'] = name

                # make '1', '0', 'true', 'false' (or other) to True/False
                autojoin = helpers.from_xs_boolean_to_python_boolean(
                        bookmark['autojoin'])

                minimize = helpers.from_xs_boolean_to_python_boolean(
                        bookmark['minimize'])

                print_status = bookmark.get('print_status', '')
                if print_status not in ('', 'all', 'in_and_out', 'none'):
                    print_status = ''
                self.treestore.append(iter_, [
                                account,
                                bookmark['name'],
                                bookmark['jid'],
                                autojoin,
                                minimize,
                                bookmark['password'],
                                bookmark['nick'],
                                print_status ])

        self.print_status_combobox = self.xml.get_object('print_status_combobox')
        model = Gtk.ListStore(str, str)

        self.option_list = {'': _('Default'), 'all': Q_('?print_status:All'),
                'in_and_out': _('Enter and leave only'),
                'none': Q_('?print_status:None')}
        opts = sorted(self.option_list.keys())
        for opt in opts:
            model.append([self.option_list[opt], opt])

        self.print_status_combobox.set_model(model)
        self.print_status_combobox.set_active(1)

        self.view = self.xml.get_object('bookmarks_treeview')
        self.view.set_model(self.treestore)
        self.view.expand_all()

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Bookmarks', renderer, text=1)
        self.view.append_column(column)

        self.selection = self.view.get_selection()
        self.selection.connect('changed', self.bookmark_selected)

        #Prepare input fields
        self.title_entry = self.xml.get_object('title_entry')
        self.title_entry.connect('changed', self.on_title_entry_changed)
        self.nick_entry = self.xml.get_object('nick_entry')
        self.nick_entry.connect('changed', self.on_nick_entry_changed)
        self.server_entry = self.xml.get_object('server_entry')
        self.server_entry.connect('changed', self.on_server_entry_changed)
        self.room_entry = self.xml.get_object('room_entry')
        self.room_entry_changed_id = self.room_entry.connect('changed',
            self.on_room_entry_changed)
        self.pass_entry = self.xml.get_object('pass_entry')
        self.pass_entry.connect('changed', self.on_pass_entry_changed)
        self.autojoin_checkbutton = self.xml.get_object('autojoin_checkbutton')
        self.minimize_checkbutton = self.xml.get_object('minimize_checkbutton')

        self.xml.connect_signals(self)
        self.window.show_all()
        # select root iter
        self.selection.select_iter(self.treestore.get_iter_first())

    def on_add_bookmark_button_clicked(self, widget):
        """
        Add a new bookmark
        """
        # Get the account that is currently used
        # (the parent of the currently selected item)
        (model, iter_) = self.selection.get_selected()
        if not iter_: # Nothing selected, do nothing
            return

        parent = model.iter_parent(iter_)

        if parent:
            # We got a bookmark selected, so we add_to the parent
            add_to = parent
        else:
            # No parent, so we got an account -> add to this.
            add_to = iter_

        account = model[add_to][1]
        nick = gajim.nicks[account]
        iter_ = self.treestore.append(add_to, [account, _('New Group Chat'),
            '@', False, False, '', nick, 'in_and_out'])

        self.view.expand_row(model.get_path(add_to), True)
        self.view.set_cursor(model.get_path(iter_))

    def on_remove_bookmark_button_clicked(self, widget):
        """
        Remove selected bookmark
        """
        (model, iter_) = self.selection.get_selected()
        if not iter_: # Nothing selected
            return

        if not model.iter_parent(iter_):
            # Don't remove account iters
            return

        model.remove(iter_)
        self.clear_fields()

    def check_valid_bookmark(self):
        """
        Check if all neccessary fields are entered correctly
        """
        (model, iter_) = self.selection.get_selected()

        if not model.iter_parent(iter_):
            #Account data can't be changed
            return

        if self.server_entry.get_text() == '' or \
        self.room_entry.get_text() == '':
            dialogs.ErrorDialog(_('This bookmark has invalid data'),
                    _('Please be sure to fill out server and room fields or remove this'
                    ' bookmark.'))
            return False

        return True

    def on_ok_button_clicked(self, widget):
        """
        Parse the treestore data into our new bookmarks array, then send the new
        bookmarks to the server.
        """
        (model, iter_) = self.selection.get_selected()
        if iter_ and model.iter_parent(iter_):
            #bookmark selected, check it
            if not self.check_valid_bookmark():
                return

        for account in self.treestore:
            acct = account[1]
            gajim.connections[acct].bookmarks = []

            for bm in account.iterchildren():
                # Convert True/False/None to '1' or '0'
                autojoin = str(int(bm[3]))
                minimize = str(int(bm[4]))
                name = bm[1]
                jid = bm[2]
                pw = bm[5]
                nick = bm[6]

                # create the bookmark-dict
                bmdict = { 'name': name, 'jid': jid, 'autojoin': autojoin,
                    'minimize': minimize, 'password': pw, 'nick': nick,
                    'print_status': bm[7]}

                gajim.connections[acct].bookmarks.append(bmdict)

            gajim.connections[acct].store_bookmarks()
        gajim.interface.roster.set_actions_menu_needs_rebuild()
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def bookmark_selected(self, selection):
        """
        Fill in the bookmark's data into the fields.
        """
        (model, iter_) = selection.get_selected()

        if not iter_:
            # After removing the last bookmark for one account
            # this will be None, so we will just:
            return

        widgets = [ self.title_entry, self.nick_entry, self.room_entry,
                self.server_entry, self.pass_entry, self.autojoin_checkbutton,
                self.minimize_checkbutton, self.print_status_combobox]

        if model.iter_parent(iter_):
            # make the fields sensitive
            for field in widgets:
                field.set_sensitive(True)
        else:
            # Top-level has no data (it's the account fields)
            # clear fields & make them insensitive
            self.clear_fields()
            for field in widgets:
                field.set_sensitive(False)
            return

        # Fill in the data for childs
        self.title_entry.set_text(model[iter_][1])
        room_jid = model[iter_][2]
        (room, server) = room_jid.split('@')
        self.room_entry.handler_block(self.room_entry_changed_id)
        self.room_entry.set_text(room)
        self.room_entry.handler_unblock(self.room_entry_changed_id)
        self.server_entry.set_text(server)

        self.autojoin_checkbutton.set_active(model[iter_][3])
        self.minimize_checkbutton.set_active(model[iter_][4])
        # sensitive only if auto join is checked
        self.minimize_checkbutton.set_sensitive(model[iter_][3])

        if model[iter_][5] is not None:
            password = model[iter_][5]
        else:
            password = None

        if password:
            self.pass_entry.set_text(password)
        else:
            self.pass_entry.set_text('')
        nick = model[iter_][6]
        if nick:
            self.nick_entry.set_text(nick)
        else:
            self.nick_entry.set_text('')

        print_status = model[iter_][7]
        opts = sorted(self.option_list.keys())
        self.print_status_combobox.set_active(opts.index(print_status))

    def on_title_entry_changed(self, widget):
        (model, iter_) = self.selection.get_selected()
        if iter_: # After removing a bookmark, we got nothing selected
            if model.iter_parent(iter_):
                # Don't clear the title field for account nodes
                model[iter_][1] = self.title_entry.get_text()

    def on_nick_entry_changed(self, widget):
        (model, iter_) = self.selection.get_selected()
        if iter_:
            nick = self.nick_entry.get_text()
            try:
                nick = helpers.parse_resource(nick)
            except helpers.InvalidFormat:
                dialogs.ErrorDialog(_('Invalid nickname'),
                    _('Character not allowed'), transient_for=self.window)
                self.nick_entry.set_text(model[iter_][6])
                return True
            model[iter_][6] = nick

    def on_server_entry_changed(self, widget):
        (model, iter_) = self.selection.get_selected()
        if not iter_:
            return
        server = widget.get_text()
        if not server:
            return
        if '@' in server:
            dialogs.ErrorDialog(_('Invalid server'),
                _('Character not allowed'), transient_for=self.window)
            widget.set_text(server.replace('@', ''))

        room = self.room_entry.get_text().strip()
        if not room:
            return
        room_jid = room + '@' + server.strip()
        try:
            room_jid = helpers.parse_jid(room_jid)
        except helpers.InvalidFormat as e:
            dialogs.ErrorDialog(_('Invalid server'),
                _('Character not allowed'), transient_for=self.window)
            self.server_entry.set_text(model[iter_][2].split('@')[1])
            return True
        model[iter_][2] = room_jid

    def on_room_entry_changed(self, widget):
        (model, iter_) = self.selection.get_selected()
        if not iter_:
            return
        room = widget.get_text()
        if not room:
            return
        if '@' in room:
            room, server = room.split('@', 1)
            widget.set_text(room)
            if server:
                self.server_entry.set_text(server)
            self.server_entry.grab_focus()
        server = self.server_entry.get_text().strip()
        if not server:
            return
        room_jid = room.strip() + '@' + server
        try:
            room_jid = helpers.parse_jid(room_jid)
        except helpers.InvalidFormat:
            dialogs.ErrorDialog(_('Invalid room'),
                _('Character not allowed'), transient_for=self.window)
            return True
        model[iter_][2] = room_jid

    def on_pass_entry_changed(self, widget):
        (model, iter_) = self.selection.get_selected()
        if iter_:
            model[iter_][5] = self.pass_entry.get_text()

    def on_autojoin_checkbutton_toggled(self, widget):
        (model, iter_) = self.selection.get_selected()
        if iter_:
            model[iter_][3] = self.autojoin_checkbutton.get_active()
            self.minimize_checkbutton.set_sensitive(model[iter_][3])

    def on_minimize_checkbutton_toggled(self, widget):
        (model, iter_) = self.selection.get_selected()
        if iter_:
            model[iter_][4] = self.minimize_checkbutton.get_active()

    def on_print_status_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        print_status = model[active][1]
        (model2, iter_) = self.selection.get_selected()
        if iter_:
            model2[iter_][7] = print_status

    def clear_fields(self):
        widgets = [ self.title_entry, self.nick_entry, self.room_entry,
                self.server_entry, self.pass_entry ]
        for field in widgets:
            field.set_text('')
        self.autojoin_checkbutton.set_active(False)
        self.minimize_checkbutton.set_active(False)
        self.print_status_combobox.set_active(1)

class AccountCreationWizardWindow:
    def __init__(self):
        self.xml = gtkgui_helpers.get_gtk_builder(
                'account_creation_wizard_window.ui')
        self.window = self.xml.get_object('account_creation_wizard_window')
        self.window.set_transient_for(gajim.interface.roster.window)

        # Connect events from comboboxentry.get_child()
        server_comboboxentry = self.xml.get_object('server_comboboxentry')
        entry = server_comboboxentry.get_child()
        entry.connect('key_press_event',
            self.on_server_comboboxentry_key_press_event, server_comboboxentry)
        # Do the same for the other server comboboxentry
        server_comboboxentry1 = self.xml.get_object('server_comboboxentry1')

        self.update_proxy_list()

        # parse servers.xml
        servers_xml = os.path.join(gajim.DATA_DIR, 'other', 'servers.xml')
        servers = gtkgui_helpers.parse_server_xml(servers_xml)
        servers_model = self.xml.get_object('server_liststore')
        for server in servers:
            servers_model.append((server,))

        # Generic widgets
        self.notebook = self.xml.get_object('notebook')
        self.cancel_button = self.xml.get_object('cancel_button')
        self.back_button = self.xml.get_object('back_button')
        self.forward_button = self.xml.get_object('forward_button')
        self.finish_button = self.xml.get_object('finish_button')
        self.advanced_button = self.xml.get_object('advanced_button')
        self.finish_label = self.xml.get_object('finish_label')
        self.go_online_checkbutton = self.xml.get_object(
            'go_online_checkbutton')
        self.show_vcard_checkbutton = self.xml.get_object(
            'show_vcard_checkbutton')
        self.progressbar = self.xml.get_object('progressbar')

        # some vars
        self.update_progressbar_timeout_id = None

        self.notebook.set_current_page(0)
        self.xml.connect_signals(self)
        self.window.show_all()
        gajim.ged.register_event_handler('new-account-connected', ged.GUI1,
            self._nec_new_acc_connected)
        gajim.ged.register_event_handler('new-account-not-connected', ged.GUI1,
            self._nec_new_acc_not_connected)
        gajim.ged.register_event_handler('account-created', ged.GUI1,
            self._nec_acc_is_ok)
        gajim.ged.register_event_handler('account-not-created', ged.GUI1,
            self._nec_acc_is_not_ok)

    def on_wizard_window_destroy(self, widget):
        page = self.notebook.get_current_page()
        if page in (4, 5) and self.account in gajim.connections:
            # connection instance is saved in gajim.connections and we canceled
            # the addition of the account
            del gajim.connections[self.account]
            if self.account in gajim.config.get_per('accounts'):
                gajim.config.del_per('accounts', self.account)
        gajim.ged.remove_event_handler('new-account-connected', ged.GUI1,
            self._nec_new_acc_connected)
        gajim.ged.remove_event_handler('new-account-not-connected', ged.GUI1,
            self._nec_new_acc_not_connected)
        gajim.ged.remove_event_handler('account-created', ged.GUI1,
            self._nec_acc_is_ok)
        gajim.ged.remove_event_handler('account-not-created', ged.GUI1,
            self._nec_acc_is_not_ok)
        del gajim.interface.instances['account_creation_wizard']

    def on_register_server_features_button_clicked(self, widget):
        helpers.launch_browser_mailer('url',
            'http://www.jabber.org/network/oldnetwork.shtml')

    def on_save_password_checkbutton_toggled(self, widget):
        self.xml.get_object('password_entry').grab_focus()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_back_button_clicked(self, widget):
        cur_page = self.notebook.get_current_page()
        self.forward_button.set_sensitive(True)
        if cur_page in (1, 2):
            self.notebook.set_current_page(0)
            self.back_button.set_sensitive(False)
        elif cur_page == 3:
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
            self.notebook.set_current_page(2) # show server page
        elif cur_page == 4:
            if self.account in gajim.connections:
                del gajim.connections[self.account]
            self.notebook.set_current_page(2)
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
        elif cur_page == 6: # finish page
            self.forward_button.show()
            if self.modify:
                self.notebook.set_current_page(1) # Go to parameters page
            else:
                self.notebook.set_current_page(2) # Go to server page

    def on_anonymous_checkbutton1_toggled(self, widget):
        active = widget.get_active()
        self.xml.get_object('username_entry').set_sensitive(not active)
        self.xml.get_object('password_entry').set_sensitive(not active)
        self.xml.get_object('save_password_checkbutton').set_sensitive(
            not active)

    def show_finish_page(self):
        self.cancel_button.hide()
        self.back_button.hide()
        self.forward_button.hide()
        if self.modify:
            finish_text = '<big><b>%s</b></big>\n\n%s' % (
                _('Account has been added successfully'),
                _('You can set advanced account options by pressing the '
                'Advanced button, or later by choosing the Accounts menu item '
                'under the Edit menu from the main window.'))
        else:
            finish_text = '<big><b>%s</b></big>\n\n%s' % (
                _('Your new account has been created successfully'),
                _('You can set advanced account options by pressing the '
                'Advanced button, or later by choosing the Accounts menu item '
                'under the Edit menu from the main window.'))
        self.finish_label.set_markup(finish_text)
        self.finish_button.show()
        self.finish_button.set_property('has-default', True)
        self.advanced_button.show()
        self.go_online_checkbutton.show()
        img = self.xml.get_object('finish_image')
        if self.modify:
            img.set_from_stock(Gtk.STOCK_APPLY, Gtk.IconSize.DIALOG)
        else:
            path_to_file = gtkgui_helpers.get_icon_path('gajim', 48)
            img.set_from_file(path_to_file)
        self.show_vcard_checkbutton.set_active(not self.modify)
        self.notebook.set_current_page(6) # show finish page

    def on_forward_button_clicked(self, widget):
        cur_page = self.notebook.get_current_page()

        if cur_page == 0:
            widget = self.xml.get_object('use_existing_account_radiobutton')
            if widget.get_active():
                self.modify = True
                self.notebook.set_current_page(1)
            else:
                self.modify = False
                self.notebook.set_current_page(2)
            self.back_button.set_sensitive(True)
            return

        elif cur_page == 1:
            # We are adding an existing account
            anonymous = self.xml.get_object('anonymous_checkbutton1').\
                get_active()
            username = self.xml.get_object('username_entry').get_text().strip()
            if not username and not anonymous:
                pritext = _('Invalid username')
                sectext = _(
                    'You must provide a username to configure this account.')
                dialogs.ErrorDialog(pritext, sectext)
                return
            server = self.xml.get_object('server_comboboxentry').get_child().\
                get_text().strip()
            savepass = self.xml.get_object('save_password_checkbutton').\
                get_active()
            password = self.xml.get_object('password_entry').get_text()

            if anonymous:
                jid = ''
            else:
                jid = username + '@'
            jid += server
            # check if jid is conform to RFC and stringprep it
            try:
                jid = helpers.parse_jid(jid)
            except helpers.InvalidFormat as s:
                pritext = _('Invalid Jabber ID')
                dialogs.ErrorDialog(pritext, str(s))
                return

            self.account = server
            i = 1
            while self.account in gajim.connections:
                self.account = server + str(i)
                i += 1

            username, server = gajim.get_name_and_server_from_jid(jid)
            if self.xml.get_object('anonymous_checkbutton1').get_active():
                self.save_account('', server, False, '', anonymous=True)
            else:
                self.save_account(username, server, savepass, password)
            self.show_finish_page()
        elif cur_page == 2:
            # We are creating a new account
            server = self.xml.get_object('server_comboboxentry1').get_child().\
                get_text()

            if not server:
                dialogs.ErrorDialog(_('Invalid server'),
                    _('Please provide a server on which you want to register.'))
                return
            self.account = server
            i = 1
            while self.account in gajim.connections:
                self.account = server + str(i)
                i += 1

            config = self.get_config('', server, '', '')
            # Get advanced options
            proxies_combobox = self.xml.get_object('proxies_combobox')
            active = proxies_combobox.get_active()
            proxy = proxies_combobox.get_model()[active][0]
            if proxy == _('None'):
                proxy = ''
            config['proxy'] = proxy

            config['use_custom_host'] = self.xml.get_object(
                'custom_host_port_checkbutton').get_active()
            custom_port = self.xml.get_object('custom_port_entry').get_text()
            try:
                custom_port = int(custom_port)
            except Exception:
                dialogs.ErrorDialog(_('Invalid entry'),
                    _('Custom port must be a port number.'))
                return
            config['custom_port'] = custom_port
            config['custom_host'] = self.xml.get_object(
                'custom_host_entry').get_text()

            if self.xml.get_object('anonymous_checkbutton2').get_active():
                self.modify = True
                self.save_account('', server, False, '', anonymous=True)
                self.show_finish_page()
            else:
                self.notebook.set_current_page(5) # show creating page
                self.back_button.hide()
                self.forward_button.hide()
                self.update_progressbar_timeout_id = GLib.timeout_add(100,
                    self.update_progressbar)
                # Get form from serveur
                con = connection.Connection(self.account)
                gajim.connections[self.account] = con
                con.new_account(self.account, config)
        elif cur_page == 3:
            checked = self.xml.get_object('ssl_checkbutton').get_active()
            if checked:
                hostname = gajim.connections[self.account].new_account_info[
                    'hostname']
                # Check if cert is already in file
                certs = ''
                if os.path.isfile(gajim.MY_CACERTS):
                    f = open(gajim.MY_CACERTS)
                    certs = f.read()
                    f.close()
                if self.ssl_cert in certs:
                    dialogs.ErrorDialog(_('Certificate Already in File'),
                        _('This certificate is already in file %s, so it\'s '
                        'not added again.') % gajim.MY_CACERTS)
                else:
                    f = open(gajim.MY_CACERTS, 'a')
                    f.write(hostname + '\n')
                    f.write(self.ssl_cert + '\n\n')
                    f.close()
                    gajim.connections[self.account].new_account_info[
                        'ssl_fingerprint_sha1'] = self.ssl_fingerprint_sha1
                    gajim.connections[self.account].new_account_info[
                        'ssl_fingerprint_sha256'] = self.ssl_fingerprint_sha256
            self.notebook.set_current_page(4) # show fom page
        elif cur_page == 4:
            if self.is_form:
                form = self.data_form_widget.data_form
            else:
                form = self.data_form_widget.get_infos()
            gajim.connections[self.account].send_new_account_infos(form,
                self.is_form)
            self.xml.get_object('form_vbox').remove(self.data_form_widget)
            self.xml.get_object('progressbar_label').set_markup(
                '<b>Account is being created</b>\n\nPlease wait...')
            self.notebook.set_current_page(5) # show creating page
            self.back_button.hide()
            self.forward_button.hide()
            self.update_progressbar_timeout_id = GLib.timeout_add(100,
                self.update_progressbar)

    def update_proxy_list(self):
        proxies_combobox = self.xml.get_object('proxies_combobox')
        model = Gtk.ListStore(str)
        proxies_combobox.set_model(model)
        l = gajim.config.get_per('proxies')
        l.insert(0, _('None'))
        for i in range(len(l)):
            model.append([l[i]])
        proxies_combobox.set_active(0)

    def on_manage_proxies_button_clicked(self, widget):
        if 'manage_proxies' in gajim.interface.instances:
            gajim.interface.instances['manage_proxies'].window.present()
        else:
            gajim.interface.instances['manage_proxies'] = \
                ManageProxiesWindow()

    def on_custom_host_port_checkbutton_toggled(self, widget):
        self.xml.get_object('custom_host_hbox').set_sensitive(widget.\
            get_active())

    def update_progressbar(self):
        self.progressbar.pulse()
        return True # loop forever

    def _nec_new_acc_connected(self, obj):
        """
        Connection to server succeded, present the form to the user
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        self.back_button.show()
        self.forward_button.show()
        self.is_form = obj.is_form
        empty_config = True
        if obj.is_form:
            dataform = dataforms.ExtendForm(node=obj.config)
            self.data_form_widget = dataforms_widget.DataFormWidget()
            self.data_form_widget.selectable = True
            self.data_form_widget.set_data_form(dataform)
            empty_config = False
        else:
            self.data_form_widget = FakeDataForm(obj.config, selectable=True)
            for field in obj.config:
                if field in ('key', 'instructions', 'x', 'registered'):
                    continue
                empty_config = False
                break
        self.data_form_widget.show_all()
        self.xml.get_object('form_vbox').pack_start(self.data_form_widget, True, True, 0)
        if empty_config:
            self.forward_button.set_sensitive(False)
            self.notebook.set_current_page(4) # show form page
            return
        self.ssl_fingerprint_sha1 = obj.ssl_fingerprint_sha1
        self.ssl_fingerprint_sha256 = obj.ssl_fingerprint_sha256
        self.ssl_cert = obj.ssl_cert
        if obj.ssl_msg:
            # An SSL warning occured, show it
            hostname = gajim.connections[self.account].new_account_info[
                'hostname']
            self.xml.get_object('ssl_label').set_markup(_(
                '<b>Security Warning</b>'
                '\n\nThe authenticity of the %(hostname)s SSL certificate could'
                ' be invalid.\nSSL Error: %(error)s\n'
                'Do you still want to connect to this server?') % {
                'hostname': hostname, 'error': obj.ssl_msg})
            if obj.errnum in (18, 27):
                text = _('Add this certificate to the list of trusted '
                    'certificates.\nSHA1 fingerprint of the certificate:\n%s'
                    '\nSHA256 fingerprint of the certificate:\n%s') \
                    % (obj.ssl_fingerprint_sha1, obj.ssl_fingerprint_sha256)
                self.xml.get_object('ssl_checkbutton').set_label(text)
            else:
                self.xml.get_object('ssl_checkbutton').set_no_show_all(True)
                self.xml.get_object('ssl_checkbutton').hide()
            self.notebook.set_current_page(3) # show SSL page
        else:
            self.notebook.set_current_page(4) # show form page

    def _nec_new_acc_not_connected(self, obj):
        """
        Account creation failed: connection to server failed
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        if self.account not in gajim.connections:
            return
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        del gajim.connections[self.account]
        if self.account in gajim.config.get_per('accounts'):
            gajim.config.del_per('accounts', self.account)
        self.back_button.show()
        self.cancel_button.show()
        self.go_online_checkbutton.hide()
        self.show_vcard_checkbutton.hide()
        img = self.xml.get_object('finish_image')
        img.set_from_stock(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.DIALOG)
        finish_text = '<big><b>%s</b></big>\n\n%s' % (
            _('An error occurred during account creation'), obj.reason)
        self.finish_label.set_markup(finish_text)
        self.notebook.set_current_page(6) # show finish page

    def _nec_acc_is_ok(self, obj):
        """
        Account creation succeeded
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        self.create_vars(obj.account_info)
        self.show_finish_page()

        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)

    def _nec_acc_is_not_ok(self, obj):
        """
        Account creation failed
        """
        # We receive events from all accounts from GED
        if obj.conn.name != self.account:
            return
        self.back_button.show()
        self.cancel_button.show()
        self.go_online_checkbutton.hide()
        self.show_vcard_checkbutton.hide()
        del gajim.connections[self.account]
        if self.account in gajim.config.get_per('accounts'):
            gajim.config.del_per('accounts', self.account)
        img = self.xml.get_object('finish_image')
        img.set_from_stock(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.DIALOG)
        finish_text = '<big><b>%s</b></big>\n\n%s' % (_(
            'An error occurred during account creation'), obj.reason)
        self.finish_label.set_markup(finish_text)
        self.notebook.set_current_page(6) # show finish page

        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)

    def on_advanced_button_clicked(self, widget):
        if 'accounts' in gajim.interface.instances:
            gajim.interface.instances['accounts'].window.present()
        else:
            gajim.interface.instances['accounts'] = AccountsWindow()
        gajim.interface.instances['accounts'].select_account(self.account)
        self.window.destroy()

    def on_finish_button_clicked(self, widget):
        go_online = self.xml.get_object('go_online_checkbutton').get_active()
        show_vcard = self.xml.get_object('show_vcard_checkbutton').get_active()
        self.window.destroy()
        if show_vcard:
            gajim.interface.show_vcard_when_connect.append(self.account)
        if go_online:
            gajim.interface.roster.send_status(self.account, 'online', '')

    def on_username_entry_key_press_event(self, widget, event):
        # Check for pressed @ and jump to combobox if found
        if event.keyval == Gdk.KEY_at:
            combobox = self.xml.get_object('server_comboboxentry')
            combobox.grab_focus()
            combobox.get_child().set_position(-1)
            return True

    def on_server_comboboxentry_key_press_event(self, widget, event, combobox):
        # If backspace is pressed in empty field, return to the nick entry field
        backspace = event.keyval == Gdk.KEY_BackSpace
        empty = len(combobox.get_active_text()) == 0
        if backspace and empty and self.modify:
            username_entry = self.xml.get_object('username_entry')
            username_entry.grab_focus()
            username_entry.set_position(-1)
            return True

    def get_config(self, login, server, savepass, password, anonymous=False):
        config = {}
        config['name'] = login
        config['hostname'] = server
        config['savepass'] = savepass
        config['password'] = password
        config['resource'] = 'Gajim'
        config['anonymous_auth'] = anonymous
        config['priority'] = 5
        config['autoconnect'] = True
        config['no_log_for'] = ''
        config['sync_with_global_status'] = True
        config['proxy'] = ''
        config['usessl'] = False
        config['use_custom_host'] = False
        config['custom_port'] = 0
        config['custom_host'] = ''
        config['keyname'] = ''
        config['keyid'] = ''
        return config

    def save_account(self, login, server, savepass, password, anonymous=False):
        if self.account in gajim.connections:
            dialogs.ErrorDialog(_('Account name is in use'),
                _('You already have an account using this name.'))
            return
        con = connection.Connection(self.account)
        con.password = password

        config = self.get_config(login, server, savepass, password, anonymous)

        if not self.modify:
            con.new_account(self.account, config)
            return
        gajim.connections[self.account] = con
        self.create_vars(config)

    def create_vars(self, config):
        gajim.config.add_per('accounts', self.account)

        if not config['savepass']:
            config['password'] = ''

        for opt in config:
            gajim.config.set_per('accounts', self.account, opt, config[opt])

        # update variables
        gajim.interface.instances[self.account] = {'infos': {}, 'disco': {},
            'gc_config': {}, 'search': {}, 'online_dialog': {},
            'sub_request': {}}
        gajim.interface.minimized_controls[self.account] = {}
        gajim.connections[self.account].connected = 0
        gajim.connections[self.account].keepalives = gajim.config.get_per(
            'accounts', self.account, 'keep_alive_every_foo_secs')
        gajim.groups[self.account] = {}
        gajim.contacts.add_account(self.account)
        gajim.gc_connected[self.account] = {}
        gajim.automatic_rooms[self.account] = {}
        gajim.newly_added[self.account] = []
        gajim.to_be_removed[self.account] = []
        gajim.nicks[self.account] = config['name']
        gajim.block_signed_in_notifications[self.account] = True
        gajim.sleeper_state[self.account] = 'off'
        gajim.encrypted_chats[self.account] = []
        gajim.last_message_time[self.account] = {}
        gajim.status_before_autoaway[self.account] = ''
        gajim.transport_avatar[self.account] = {}
        gajim.gajim_optional_features[self.account] = []
        gajim.caps_hash[self.account] = ''
        helpers.update_optional_features(self.account)
        # refresh accounts window
        if 'accounts' in gajim.interface.instances:
            gajim.interface.instances['accounts'].init_accounts()
        # refresh roster
        if len(gajim.connections) >= 2:
            # Do not merge accounts if only one exists
            gajim.interface.roster.regroup = gajim.config.get('mergeaccounts')
        else:
            gajim.interface.roster.regroup = False
        gajim.interface.roster.setup_and_draw_roster()
        gajim.interface.roster.set_actions_menu_needs_rebuild()

class ManagePEPServicesWindow:
    def __init__(self, account):
        self.xml = gtkgui_helpers.get_gtk_builder('manage_pep_services_window.ui')
        self.window = self.xml.get_object('manage_pep_services_window')
        self.window.set_transient_for(gajim.interface.roster.window)
        self.xml.get_object('configure_button').set_sensitive(False)
        self.xml.get_object('delete_button').set_sensitive(False)
        self.xml.connect_signals(self)
        self.account = account

        self.init_services()
        self.xml.get_object('services_treeview').get_selection().connect(
                'changed', self.on_services_selection_changed)

        gajim.ged.register_event_handler('pep-config-received', ged.GUI1,
            self._nec_pep_config_received)
        gajim.ged.register_event_handler('agent-items-received', ged.GUI1,
            self._nec_agent_items_received)

        self.window.show_all()

    def on_manage_pep_services_window_destroy(self, widget):
        '''close window'''
        del gajim.interface.instances[self.account]['pep_services']
        gajim.ged.remove_event_handler('pep-config-received', ged.GUI1,
            self._nec_pep_config_received)
        gajim.ged.remove_event_handler('agent-items-received', ged.GUI1,
            self._nec_agent_items_received)

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_services_selection_changed(self, sel):
        self.xml.get_object('configure_button').set_sensitive(True)
        self.xml.get_object('delete_button').set_sensitive(True)

    def init_services(self):
        self.treeview = self.xml.get_object('services_treeview')
        # service, access_model, group
        self.treestore = Gtk.ListStore(str)
        self.treeview.set_model(self.treestore)

        col = Gtk.TreeViewColumn('Service')
        self.treeview.append_column(col)

        cellrenderer_text = Gtk.CellRendererText()
        col.pack_start(cellrenderer_text, True, True, 0)
        col.add_attribute(cellrenderer_text, 'text', 0)

        our_jid = gajim.get_jid_from_account(self.account)
        gajim.connections[self.account].discoverItems(our_jid)

    def _nec_agent_items_received(self, obj):
        our_jid = gajim.get_jid_from_account(self.account)
        for item in obj.items:
            if 'jid' in item and item['jid'] == our_jid and 'node' in item:
                self.treestore.append([item['node']])

    def node_removed(self, jid, node):
        if jid != gajim.get_jid_from_account(self.account):
            return
        model = self.treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0] == node:
                model.remove(iter_)
                break
            iter_ = model.iter_next(iter_)

    def node_not_removed(self, jid, node, msg):
        if jid != gajim.get_jid_from_account(self.account):
            return
        dialogs.WarningDialog(_('PEP node was not removed'),
            _('PEP node %(node)s was not removed: %(message)s') % {'node': node,
            'message': msg})

    def on_delete_button_clicked(self, widget):
        selection = self.treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = gajim.get_jid_from_account(self.account)
        gajim.connections[self.account].send_pb_delete(our_jid, node,
            on_ok=self.node_removed, on_fail=self.node_not_removed)

    def on_configure_button_clicked(self, widget):
        selection = self.treeview.get_selection()
        if not selection:
            return
        model, iter_ = selection.get_selected()
        node = model[iter_][0]
        our_jid = gajim.get_jid_from_account(self.account)
        gajim.connections[self.account].request_pb_configuration(our_jid, node)

    def _nec_pep_config_received(self, obj):
        def on_ok(form, node):
            form.type_ = 'submit'
            our_jid = gajim.get_jid_from_account(self.account)
            gajim.connections[self.account].send_pb_configure(our_jid, node, form)
        window = dialogs.DataFormWindow(obj.form, (on_ok, obj.node))
        title = _('Configure %s') % obj.node
        window.set_title(title)
        window.show_all()

class ManageSoundsWindow:
    def __init__(self):
        self.xml = gtkgui_helpers.get_gtk_builder('manage_sounds_window.ui')
        self.window = self.xml.get_object('manage_sounds_window')
        self.window.set_transient_for(
            gajim.interface.instances['preferences'].window)
        # sounds treeview
        self.sound_tree = self.xml.get_object('sounds_treeview')

        # active, event ui name, path to sound file, event_config_name
        model = Gtk.ListStore(bool, str, str, str)
        self.sound_tree.set_model(model)

        col = Gtk.TreeViewColumn(_('Active'))
        self.sound_tree.append_column(col)
        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.sound_toggled_cb)
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'active', 0)

        col = Gtk.TreeViewColumn(_('Event'))
        self.sound_tree.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', 1)

        self.fill_sound_treeview()

        self.xml.connect_signals(self)

        self.sound_tree.get_model().connect('row-changed',
            self.on_sounds_treemodel_row_changed)

        self.window.show_all()

    def on_sounds_treemodel_row_changed(self, model, path, iter_):
        sound_event = model[iter_][3]
        gajim.config.set_per('soundevents', sound_event, 'enabled',
            bool(model[path][0]))
        gajim.config.set_per('soundevents', sound_event, 'path',
            model[iter_][2])

    def sound_toggled_cb(self, cell, path):
        model = self.sound_tree.get_model()
        model[path][0] = not model[path][0]

    def fill_sound_treeview(self):
        model = self.sound_tree.get_model()
        model.clear()
        model.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        # NOTE: sounds_ui_names MUST have all items of
        # sounds = gajim.config.get_per('soundevents') as keys
        sounds_dict = {
                'attention_received': _('Attention Message Received'),
                'first_message_received': _('First Message Received'),
                'next_message_received_focused': _('Next Message Received Focused'),
                'next_message_received_unfocused':
                        _('Next Message Received Unfocused'),
                'contact_connected': _('Contact Connected'),
                'contact_disconnected': _('Contact Disconnected'),
                'message_sent': _('Message Sent'),
                'muc_message_highlight': _('Group Chat Message Highlight'),
                'muc_message_received': _('Group Chat Message Received'),
                'gmail_received': _('GMail Email Received')
        }

        for sound_event_config_name, sound_ui_name in sounds_dict.items():
            enabled = gajim.config.get_per('soundevents',
                    sound_event_config_name, 'enabled')
            path = gajim.config.get_per('soundevents',
                    sound_event_config_name, 'path')
            model.append((enabled, sound_ui_name, path, sound_event_config_name))

    def on_treeview_sounds_cursor_changed(self, widget, data = None):
        sounds_entry = self.xml.get_object('sounds_entry')
        sel = self.sound_tree.get_selection()
        if not sel:
            sounds_entry.set_text('')
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            sounds_entry.set_text('')
            return
        path_to_snd_file = model[iter_][2]
        sounds_entry.set_text(path_to_snd_file)

    def on_browse_for_sounds_button_clicked(self, widget, data = None):
        sel = self.sound_tree.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        def on_ok(widget, path_to_snd_file):
            self.dialog.destroy()
            model, iter_ = self.sound_tree.get_selection().get_selected()
            if not path_to_snd_file:
                model[iter_][2] = ''
                self.xml.get_object('sounds_entry').set_text('')
                model[iter_][0] = False
                return
            directory = os.path.dirname(path_to_snd_file)
            gajim.config.set('last_sounds_dir', directory)
            path_to_snd_file = helpers.strip_soundfile_path(path_to_snd_file)
            self.xml.get_object('sounds_entry').set_text(path_to_snd_file)

            model[iter_][2] = path_to_snd_file # set new path to sounds_model
            model[iter_][0] = True # set the sound to enabled

        def on_cancel(widget):
            self.dialog.destroy()

        path_to_snd_file = model[iter_][2]
        self.dialog = dialogs.SoundChooserDialog(path_to_snd_file, on_ok,
                on_cancel)

    def on_sounds_entry_changed(self, widget):
        path_to_snd_file = widget.get_text()
        model, iter_ = self.sound_tree.get_selection().get_selected()
        model[iter_][2] = path_to_snd_file # set new path to sounds_model

    def on_play_button_clicked(self, widget):
        sel = self.sound_tree.get_selection()
        if not sel:
            return
        model, iter_ = sel.get_selected()
        if not iter_:
            return
        snd_event_config_name = model[iter_][3]
        helpers.play_sound(snd_event_config_name)

    def on_close_button_clicked(self, widget):
        self.window.hide()

    def on_manage_sounds_window_delete_event(self, widget, event):
        self.window.hide()
        return True # do NOT destroy the window
