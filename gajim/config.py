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

import os

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib

from gajim.common import config as c_config
from gajim.common import idle
from gajim.common.i18n import Q_

from gajim import gtkgui_helpers
from gajim import dialogs
from gajim import cell_renderer_image
from gajim import message_control
from gajim.chat_control_base import ChatControlBase
from gajim.gajim_themes_window import GajimThemesWindow
from gajim.advanced_configuration_window import AdvancedConfigurationWindow
from gajim import dataforms_widget
from gajim import gui_menu_builder
from gajim.gtk import AspellDictError
from gajim.gtk import ConfirmationDialog
from gajim.gtk import ConfirmationDialogDoubleRadio
from gajim.gtk import ErrorDialog
from gajim.gtk import InputDialog
from gajim.gtk import WarningDialog

from gajim.common import helpers
from gajim.common import app
from gajim.common import connection
from gajim.common.modules import dataforms
from gajim.common import ged
from gajim.common import configpaths
from gajim.accounts_window import AccountsWindow

try:
    from gajim.common.multimedia_helpers import AudioInputManager, AudioOutputManager
    from gajim.common.multimedia_helpers import VideoInputManager, VideoOutputManager
    HAS_GST = True
except (ImportError, ValueError):
    HAS_GST = False

if app.is_installed('GSPELL'):
    from gi.repository import Gspell

#---------- PreferencesWindow class -------------#
class PreferencesWindow:
    """
    Class for Preferences window
    """

    def on_preferences_window_destroy(self, widget):
        """
        Close window
        """
        del app.interface.instances['preferences']

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self):
        """
        Initialize Preferences window
        """
        self.xml = gtkgui_helpers.get_gtk_builder('preferences_window.ui')
        self.window = self.xml.get_object('preferences_window')
        self.window.set_transient_for(app.interface.roster.window)
        self.notebook = self.xml.get_object('preferences_notebook')
        self.one_window_type_combobox = self.xml.get_object(
            'one_window_type_combobox')
        self.iconset_combobox = self.xml.get_object('iconset_combobox')
        self.notify_on_signin_checkbutton = self.xml.get_object(
            'notify_on_signin_checkbutton')
        self.notify_on_signout_checkbutton = self.xml.get_object(
            'notify_on_signout_checkbutton')
        self.auto_popup_away_checkbutton = self.xml.get_object(
            'auto_popup_away_checkbutton')
        self.auto_popup_chat_opened_checkbutton = self.xml.get_object(
            'auto_popup_chat_opened_checkbutton')
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
        st = app.config.get('show_avatars_in_roster')
        self.xml.get_object('show_avatars_in_roster_checkbutton'). \
            set_active(st)

        # Display status msg under contact name in roster
        st = app.config.get('show_status_msgs_in_roster')
        self.xml.get_object('show_status_msgs_in_roster_checkbutton'). \
            set_active( st)

        # Display PEP in roster
        st1 = app.config.get('show_mood_in_roster')
        st2 = app.config.get('show_activity_in_roster')
        st3 = app.config.get('show_tunes_in_roster')
        st4 = app.config.get('show_location_in_roster')
        w = self.xml.get_object('show_pep_in_roster_checkbutton')
        if st1 == st2 == st3 == st4:
            w.set_active(st1)
        else:
            w.set_inconsistent(True)

        # Sort contacts by show
        st = app.config.get('sort_by_show_in_roster')
        self.xml.get_object('sort_by_show_in_roster_checkbutton').set_active(st)
        st = app.config.get('sort_by_show_in_muc')
        self.xml.get_object('sort_by_show_in_muc_checkbutton').set_active(st)

        # emoticons
        emoticons_combobox = self.xml.get_object('emoticons_combobox')
        emoticon_themes = helpers.get_available_emoticon_themes()

        emoticons_combobox.append_text(_('Disabled'))
        for theme in emoticon_themes:
            emoticons_combobox.append_text(theme)

        config_theme = app.config.get('emoticons_theme')
        if config_theme not in emoticon_themes:
            config_theme = _('Disabled')
        emoticons_combobox.set_id_column(0)
        emoticons_combobox.set_active_id(config_theme)

        # Set default for single window type
        choices = c_config.opt_one_window_types
        type_ = app.config.get('one_message_window')
        if type_ in choices:
            self.one_window_type_combobox.set_active(choices.index(type_))
        else:
            self.one_window_type_combobox.set_active(0)

        # Show roster on startup
        show_roster_combobox = self.xml.get_object('show_roster_on_startup')
        choices = c_config.opt_show_roster_on_startup
        type_ = app.config.get('show_roster_on_startup')
        if type_ in choices:
            show_roster_combobox.set_active(choices.index(type_))
        else:
            show_roster_combobox.set_active(0)

        # Ignore XHTML
        st = app.config.get('ignore_incoming_xhtml')
        self.xml.get_object('xhtml_checkbutton').set_active(st)

        # use speller
        if app.is_installed('GSPELL'):
            st = app.config.get('use_speller')
            self.xml.get_object('speller_checkbutton').set_active(st)
        else:
            self.xml.get_object('speller_checkbutton').set_sensitive(False)

        # XEP-0184 positive ack
        st = app.config.get('positive_184_ack')
        self.xml.get_object('positive_184_ack_checkbutton').set_active(st)

        # Show avatar in tabs
        st = app.config.get('show_avatar_in_tabs')
        self.xml.get_object('show_avatar_in_tabs_checkbutton').set_active(st)

        ### Style tab ###
        # Themes
        theme_combobox = self.xml.get_object('theme_combobox')
        cell = Gtk.CellRendererText()
        theme_combobox.pack_start(cell, True)
        theme_combobox.add_attribute(cell, 'text', 0)
        self.update_theme_list()

        # iconset
        iconsets_list = os.listdir(
            os.path.join(configpaths.get('DATA'), 'iconsets'))
        if os.path.isdir(configpaths.get('MY_ICONSETS')):
            iconsets_list += os.listdir(configpaths.get('MY_ICONSETS'))
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
            if not os.path.isdir(os.path.join(configpaths.get('DATA'), 'iconsets', dir)) \
            and not os.path.isdir(os.path.join(configpaths.get('MY_ICONSETS'), dir)):
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
            if app.config.get('iconset') == l[i]:
                self.iconset_combobox.set_active(i)

        # Use transports iconsets
        st = app.config.get('use_transports_iconsets')
        self.xml.get_object('transports_iconsets_checkbutton').set_active(st)

        # Color widgets
        self.draw_color_widgets()

        # Font for messages
        font = app.config.get('conversation_font')
        # try to set default font for the current desktop env
        fontbutton = self.xml.get_object('conversation_fontbutton')
        if font == '':
            fontbutton.set_sensitive(False)
            self.xml.get_object('default_chat_font').set_active(True)
        else:
            fontbutton.set_font_name(font)

        ### Personal Events tab ###
        # outgoing send chat state notifications
        st = app.config.get('outgoing_chat_state_notifications')
        combo = self.xml.get_object('outgoing_chat_states_combobox')
        if st == 'all':
            combo.set_active(0)
        elif st == 'composing_only':
            combo.set_active(1)
        else: # disabled
            combo.set_active(2)

        # displayed send chat state notifications
        st = app.config.get('displayed_chat_state_notifications')
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
        if app.config.get('autopopup'):
            on_event_combobox.set_active(0)
        elif app.config.get('notify_on_new_message'):
            on_event_combobox.set_active(1)
        else:
            on_event_combobox.set_active(2)

        # notify on online statuses
        st = app.config.get('notify_on_signin')
        self.notify_on_signin_checkbutton.set_active(st)

        # notify on offline statuses
        st = app.config.get('notify_on_signout')
        self.notify_on_signout_checkbutton.set_active(st)

        # autopopupaway
        st = app.config.get('autopopupaway')
        self.auto_popup_away_checkbutton.set_active(st)

        # autopopup_chat_opened
        st = app.config.get('autopopup_chat_opened')
        self.auto_popup_chat_opened_checkbutton.set_active(st)

        # sounddnd
        st = app.config.get('sounddnd')
        self.sound_dnd_checkbutton.set_active(st)

        # Systray
        systray_combobox = self.xml.get_object('systray_combobox')
        if app.config.get('trayicon') == 'never':
            systray_combobox.set_active(0)
        elif app.config.get('trayicon') == 'on_event':
            systray_combobox.set_active(1)
        else:
            systray_combobox.set_active(2)

        # sounds
        if app.config.get('sounds_on'):
            self.xml.get_object('play_sounds_checkbutton').set_active(True)
        else:
            self.xml.get_object('manage_sounds_button').set_sensitive(False)

        #### Status tab ###
        # Autoaway
        st = app.config.get('autoaway')
        self.auto_away_checkbutton.set_active(st)

        # Autoawaytime
        st = app.config.get('autoawaytime')
        self.auto_away_time_spinbutton.set_value(st)
        self.auto_away_time_spinbutton.set_sensitive(app.config.get('autoaway'))

        # autoaway message
        st = app.config.get('autoaway_message')
        self.auto_away_message_entry.set_text(st)
        self.auto_away_message_entry.set_sensitive(app.config.get('autoaway'))

        # Autoxa
        st = app.config.get('autoxa')
        self.auto_xa_checkbutton.set_active(st)

        # Autoxatime
        st = app.config.get('autoxatime')
        self.auto_xa_time_spinbutton.set_value(st)
        self.auto_xa_time_spinbutton.set_sensitive(app.config.get('autoxa'))

        # autoxa message
        st = app.config.get('autoxa_message')
        self.auto_xa_message_entry.set_text(st)
        self.auto_xa_message_entry.set_sensitive(app.config.get('autoxa'))

        if not idle.Monitor.is_available():
            self.xml.get_object('autoaway_table').set_sensitive(False)

        # ask_status when online / offline
        st = app.config.get('ask_online_status')
        self.xml.get_object('prompt_online_status_message_checkbutton').\
                set_active(st)
        st = app.config.get('ask_offline_status')
        self.xml.get_object('prompt_offline_status_message_checkbutton').\
                set_active(st)

        # Default Status messages
        self.default_msg_tree = self.xml.get_object('default_msg_treeview')
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
                config = app.config.get(config_name)
            else:
                config = app.config.get(opt_name + '_device')

            for index, (name, value) in enumerate(sorted(device_dict.items(),
            key=key)):
                model.append((name, value))
                if config == value:
                    combobox.set_active(index)

        if HAS_GST and app.is_installed('FARSTREAM'):
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
            st = app.config.get('video_see_self')
            self.xml.get_object('video_see_self_checkbutton').set_active(st)

        else:
            for opt_name in ('audio_input', 'audio_output', 'video_input',
            'video_output', 'video_framerate', 'video_size'):
                combobox = self.xml.get_object(opt_name + '_combobox')
                combobox.set_sensitive(False)

        # STUN
        cb = self.xml.get_object('stun_checkbutton')
        st = app.config.get('use_stun_server')
        cb.set_active(st)

        entry = self.xml.get_object('stun_server_entry')
        entry.set_text(app.config.get('stun_server'))
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

            if app.config.get('autodetect_browser_mailer'):
                self.applications_combobox.set_active(0)
            else:
                self.applications_combobox.set_active(1)
                self.xml.get_object('custom_apps_frame').show()

            self.xml.get_object('custom_browser_entry').set_text(
                    app.config.get('custombrowser'))
            self.xml.get_object('custom_mail_client_entry').set_text(
                    app.config.get('custommailapp'))
            self.xml.get_object('custom_file_manager_entry').set_text(
                    app.config.get('custom_file_manager'))

        # log status changes of contacts
        st = app.config.get('log_contact_status_changes')
        self.xml.get_object('log_show_changes_checkbutton').set_active(st)

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
        if len(app.connections) == 0:
            # a non existent key return default value
            return app.config.get_per('accounts', '__default__', opt)
        val = None
        for account in app.connections:
            v = app.config.get_per('accounts', account, opt)
            if val is None:
                val = v
            elif val != v:
                return 'mixed'
        return val

    def on_checkbutton_toggled(self, widget, config_name,
    change_sensitivity_widgets=None):
        app.config.set(config_name, widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def on_per_account_checkbutton_toggled(self, widget, config_name,
    change_sensitivity_widgets=None):
        for account in app.connections:
            app.config.set_per('accounts', account, config_name,
                    widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def _get_all_controls(self):
        for ctrl in app.interface.msg_win_mgr.get_controls():
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    def _get_all_muc_controls(self):
        for ctrl in app.interface.msg_win_mgr.get_controls(
        message_control.TYPE_GC):
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    def on_sort_by_show_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_sort_by_show_in_muc_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_muc')
        # Redraw groupchats
        for ctrl in self._get_all_muc_controls():
            ctrl.draw_roster()

    def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
        app.interface.roster.setup_and_draw_roster()
        # Redraw groupchats (in an ugly way)
        for ctrl in self._get_all_muc_controls():
            ctrl.draw_roster()

    def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
        app.interface.roster.setup_and_draw_roster()
        for ctrl in self._get_all_muc_controls():
            ctrl.update_ui()

    def on_show_pep_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_mood_in_roster')
        self.on_checkbutton_toggled(widget, 'show_activity_in_roster')
        self.on_checkbutton_toggled(widget, 'show_tunes_in_roster')
        self.on_checkbutton_toggled(widget, 'show_location_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_emoticons_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        emot_theme = model[active][0]
        if emot_theme == _('Disabled'):
            app.config.set('emoticons_theme', '')
        else:
            app.config.set('emoticons_theme', emot_theme)

        app.interface.init_emoticons()
        app.interface.make_regexps()
        self.toggle_emoticons()

    def toggle_emoticons(self):
        """
        Update emoticons state in Opened Chat Windows
        """
        for ctrl in self._get_all_controls():
            ctrl.toggle_emoticons()

    def on_one_window_type_combo_changed(self, widget):
        active = widget.get_active()
        config_type = c_config.opt_one_window_types[active]
        app.config.set('one_message_window', config_type)
        app.interface.msg_win_mgr.reconfig()

    def on_show_roster_on_startup_changed(self, widget):
        active = widget.get_active()
        config_type = c_config.opt_show_roster_on_startup[active]
        app.config.set('show_roster_on_startup', config_type)

    def on_xhtml_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ignore_incoming_xhtml')
        helpers.update_optional_features()

    def apply_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, ChatControlBase):
                ctrl.set_speller()

    def on_speller_checkbutton_toggled(self, widget):
        active = widget.get_active()
        app.config.set('use_speller', active)
        if not active:
            return
        lang = app.config.get('speller_language')
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        if gspell_lang is None:
            AspellDictError(lang)
            app.config.set('use_speller', False)
            widget.set_active(False)
        else:
            app.config.set('speller_language', gspell_lang.get_code())
            self.apply_speller()

    def on_positive_184_ack_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'positive_184_ack')

    def on_show_avatar_in_tabs_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatar_in_tabs')

    def on_theme_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        config_theme = model[active][0].replace(' ', '_')

        app.config.set('roster_theme', config_theme)

        # begin repainting themed widgets throughout
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)
        gtkgui_helpers.load_css()

    def update_theme_list(self):
        theme_combobox = self.xml.get_object('theme_combobox')
        model = Gtk.ListStore(str)
        theme_combobox.set_model(model)
        i = 0
        for config_theme in app.config.get_per('themes'):
            theme = config_theme.replace('_', ' ')
            model.append([theme])
            if app.config.get('roster_theme') == config_theme:
                theme_combobox.set_active(i)
            i += 1

    def on_manage_theme_button_clicked(self, widget):
        if self.theme_preferences is None:
            self.theme_preferences = GajimThemesWindow()
        else:
            self.theme_preferences.window.present()
            self.theme_preferences.select_active_theme()

    def on_iconset_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        icon_string = model[active][1]
        app.config.set('iconset', icon_string)
        gtkgui_helpers.reload_jabber_state_images()

    def on_transports_iconsets_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_transports_iconsets')
        gtkgui_helpers.reload_jabber_state_images()

    def on_outgoing_chat_states_combobox_changed(self, widget):
        active = widget.get_active()
        old_value = app.config.get('outgoing_chat_state_notifications')
        if active == 0: # all
            app.config.set('outgoing_chat_state_notifications', 'all')
        elif active == 1: # only composing
            app.config.set('outgoing_chat_state_notifications', 'composing_only')
        else: # disabled
            app.config.set('outgoing_chat_state_notifications', 'disabled')
        new_value = app.config.get('outgoing_chat_state_notifications')
        if 'disabled' in (old_value, new_value):
            # we changed from disabled to sth else or vice versa
            helpers.update_optional_features()

    def on_displayed_chat_states_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0: # all
            app.config.set('displayed_chat_state_notifications', 'all')
        elif active == 1: # only composing
            app.config.set('displayed_chat_state_notifications',
                    'composing_only')
        else: # disabled
            app.config.set('displayed_chat_state_notifications', 'disabled')

    def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'ignore_unknown_contacts')

    def on_on_event_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.config.set('autopopup', True)
            app.config.set('notify_on_new_message', False)
        elif active == 1:
            app.config.set('autopopup', False)
            app.config.set('notify_on_new_message', True)
        else:
            app.config.set('autopopup', False)
            app.config.set('notify_on_new_message', False)

    def on_notify_on_signin_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signin')

    def on_notify_on_signout_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signout')

    def on_auto_popup_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autopopupaway')

    def on_auto_popup_chat_opened_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autopopup_chat_opened')

    def on_sound_dnd_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounddnd')

    def on_systray_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.config.set('trayicon', 'never')
            app.interface.systray_enabled = False
            app.interface.systray.hide_icon()
        elif active == 1:
            app.config.set('trayicon', 'on_event')
            app.interface.systray_enabled = True
            app.interface.systray.show_icon()
        else:
            app.config.set('trayicon', 'always')
            app.interface.systray_enabled = True
            app.interface.systray.show_icon()

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
        color_string = color.to_string()
        app.config.set(text, color_string)
        self.update_text_tags()

    def on_preference_widget_font_set(self, widget, text):
        if widget:
            font = widget.get_font_name()
        else:
            font = ''
        app.config.set(text, font)
        gtkgui_helpers.load_css()

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
            col = app.config.get(c)
            if col:
                if isinstance(col_to_widget[c], list):
                    rgba = Gdk.RGBA()
                    rgba.parse(col)
                    self.xml.get_object(col_to_widget[c][0]).set_rgba(rgba)
                    self.xml.get_object(col_to_widget[c][0]).set_sensitive(True)
                    self.xml.get_object(col_to_widget[c][1]).set_active(True)
                else:
                    rgba = Gdk.RGBA()
                    rgba.parse(col)
                    self.xml.get_object(col_to_widget[c]).set_rgba(rgba)
            else:
                rgba = Gdk.RGBA()
                rgba.parse('#000000')
                if isinstance(col_to_widget[c], list):
                    self.xml.get_object(col_to_widget[c][0]).set_rgba(rgba)
                    self.xml.get_object(col_to_widget[c][0]).set_sensitive(False)
                    self.xml.get_object(col_to_widget[c][1]).set_active(False)
                else:
                    self.xml.get_object(col_to_widget[c]).set_rgba(rgba)

    def on_reset_colors_button_clicked(self, widget):
        col_to_widget = {'inmsgcolor': 'incoming_nick_colorbutton',
                        'outmsgcolor': 'outgoing_nick_colorbutton',
                        'inmsgtxtcolor': 'incoming_msg_colorbutton',
                        'outmsgtxtcolor': 'outgoing_msg_colorbutton',
                        'statusmsgcolor': 'status_msg_colorbutton',
                        'urlmsgcolor': 'url_msg_colorbutton',
                        'markedmsgcolor': 'muc_highlight_colorbutton'}
        for c in col_to_widget:
            app.config.set(c, app.interface.default_colors[c])
        self.draw_color_widgets()

        self.update_text_tags()

    def _set_color(self, state, widget_name, option):
        """
        Set color value in prefs and update the UI
        """
        if state:
            color = self.xml.get_object(widget_name).get_rgba()
            color_string = color.to_string()
        else:
            color_string = ''
        app.config.set(option, color_string)

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
        app.config.set('autoawaytime', aat)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_away_message_entry_changed(self, widget):
        app.config.set('autoaway_message', widget.get_text())

    def on_auto_xa_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoxa',
                                [self.auto_xa_time_spinbutton, self.auto_xa_message_entry])

    def on_auto_xa_time_spinbutton_value_changed(self, widget):
        axt = widget.get_value_as_int()
        app.config.set('autoxatime', axt)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_xa_message_entry_changed(self, widget):
        app.config.set('autoxa_message', widget.get_text())

    def on_prompt_online_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_online_status')

    def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_offline_status')

    def fill_default_msg_treeview(self):
        model = self.default_msg_tree.get_model()
        model.clear()
        status = []
        for status_ in app.config.get_per('defaultstatusmsg'):
            status.append(status_)
        status.sort()
        for status_ in status:
            msg = app.config.get_per('defaultstatusmsg', status_, 'message')
            msg = helpers.from_one_line(msg)
            enabled = app.config.get_per('defaultstatusmsg', status_, 'enabled')
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
        app.config.set_per('defaultstatusmsg', status, 'enabled',
                model[iter_][3])
        app.config.set_per('defaultstatusmsg', status, 'message', message)

    def save_status_messages(self, model):
        for msg in app.config.get_per('statusmsg'):
            app.config.del_per('statusmsg', msg)
        iter_ = model.get_iter_first()
        while iter_:
            val = model[iter_][0]
            if model[iter_][1]: # we have a preset message
                if not val: # no title, use message text for title
                    val = model[iter_][1]
                app.config.add_per('statusmsg', val)
                msg = helpers.to_one_line(model[iter_][1])
                app.config.set_per('statusmsg', val, 'message', msg)
                i = 2
                # store mood / activity
                for subname in ('activity', 'subactivity', 'activity_text',
                'mood', 'mood_text'):
                    val2 = model[iter_][i]
                    if not val2:
                        val2 = ''
                    app.config.set_per('statusmsg', val, subname, val2)
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
        app.config.set(config_name, device)

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
        app.config.set('stun_server', widget.get_text())

    def on_applications_combobox_changed(self, widget):
        if widget.get_active() == 0:
            app.config.set('autodetect_browser_mailer', True)
            self.xml.get_object('custom_apps_frame').hide()
        elif widget.get_active() == 1:
            app.config.set('autodetect_browser_mailer', False)
            self.xml.get_object('custom_apps_frame').show()

    def on_custom_browser_entry_changed(self, widget):
        app.config.set('custombrowser', widget.get_text())

    def on_custom_mail_client_entry_changed(self, widget):
        app.config.set('custommailapp', widget.get_text())

    def on_custom_file_manager_entry_changed(self, widget):
        app.config.set('custom_file_manager', widget.get_text())

    def on_log_show_changes_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

    def on_send_os_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_os_info')

    def on_send_time_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_time_info')

    def on_send_idle_time_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_idle_time')

    def fill_msg_treeview(self):
        self.xml.get_object('delete_msg_button').set_sensitive(False)
        model = self.msg_tree.get_model()
        model.clear()
        preset_status = []
        for msg_name in app.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            preset_status.append(msg_name)
        preset_status.sort()
        for msg_name in preset_status:
            msg_text = app.config.get_per('statusmsg', msg_name, 'message')
            msg_text = helpers.from_one_line(msg_text)
            activity = app.config.get_per('statusmsg', msg_name, 'activity')
            subactivity = app.config.get_per('statusmsg', msg_name,
                'subactivity')
            activity_text = app.config.get_per('statusmsg', msg_name,
                'activity_text')
            mood = app.config.get_per('statusmsg', msg_name, 'mood')
            mood_text = app.config.get_per('statusmsg', msg_name, 'mood_text')
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

        app.config.set('global_proxy', proxy)

    def on_manage_proxies_button_clicked(self, widget):
        if 'manage_proxies' in app.interface.instances:
            app.interface.instances['manage_proxies'].window.present()
        else:
            app.interface.instances['manage_proxies'] = ManageProxiesWindow(
                self.window)

    def update_proxy_list(self):
        our_proxy = app.config.get('global_proxy')
        if not our_proxy:
            our_proxy = _('None')
        proxy_combobox = self.xml.get_object('proxies_combobox')
        model = proxy_combobox.get_model()
        model.clear()
        l = app.config.get_per('proxies')
        l.insert(0, _('None'))
        for i in range(len(l)):
            model.append([l[i]])
            if our_proxy == l[i]:
                proxy_combobox.set_active(i)

    def on_open_advanced_editor_button_clicked(self, widget, data = None):
        if 'advanced_config' in app.interface.instances:
            app.interface.instances['advanced_config'].window.present()
        else:
            app.interface.instances['advanced_config'] = \
                    AdvancedConfigurationWindow()

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
        for p in app.config.get_per('proxies'):
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
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].\
                    update_proxy_list()
        del app.interface.instances['manage_proxies']

    def on_add_proxy_button_clicked(self, widget):
        model = self.proxies_treeview.get_model()
        proxies = app.config.get_per('proxies')
        i = 1
        while ('proxy' + str(i)) in proxies:
            i += 1
        iter_ = model.append()
        model.set(iter_, 0, 'proxy' + str(i))
        app.config.add_per('proxies', 'proxy' + str(i))
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
        app.config.del_per('proxies', proxy)
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
        app.config.set_per('proxies', proxy, 'useauth', act)
        self.xml.get_object('proxyuser_entry').set_sensitive(act)
        self.xml.get_object('proxypass_entry').set_sensitive(act)

    def on_boshuseproxy_checkbutton_toggled(self, widget):
        if self.block_signal:
            return
        act = widget.get_active()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_useproxy', act)
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
            proxytype = app.config.get_per('proxies', proxy, 'type')

            self.show_bosh_fields(proxytype=='bosh')

            self.proxyname_entry.set_editable(True)
            self.xml.get_object('remove_proxy_button').set_sensitive(True)
            self.xml.get_object('proxytype_combobox').set_sensitive(True)
            self.xml.get_object('proxy_table').set_sensitive(True)
            proxyhost_entry.set_text(app.config.get_per('proxies', proxy,
                    'host'))
            proxyport_entry.set_text(str(app.config.get_per('proxies',
                    proxy, 'port')))
            proxyuser_entry.set_text(app.config.get_per('proxies', proxy,
                    'user'))
            proxypass_entry.set_text(app.config.get_per('proxies', proxy,
                    'pass'))
            boshuri_entry.set_text(app.config.get_per('proxies', proxy,
                    'bosh_uri'))
            types = ['http', 'socks5', 'bosh']
            self.proxytype_combobox.set_active(types.index(proxytype))
            boshuseproxy_checkbutton.set_active(
                    app.config.get_per('proxies', proxy, 'bosh_useproxy'))
            useauth_checkbutton.set_active(
                    app.config.get_per('proxies', proxy, 'useauth'))
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
        config = app.config.get_per('proxies', old_name)
        app.config.del_per('proxies', old_name)
        app.config.add_per('proxies', new_name)
        for option in config:
            app.config.set_per('proxies', new_name, option, config[option])
        model.set_value(iter_, 0, new_name)

    def on_proxytype_combobox_changed(self, widget):
        if self.block_signal:
            return
        types = ['http', 'socks5', 'bosh']
        type_ = self.proxytype_combobox.get_active()
        self.show_bosh_fields(types[type_]=='bosh')
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'type', types[type_])

    def on_proxyhost_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'host', value)

    def on_proxyport_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'port', value)

    def on_proxyuser_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'user', value)

    def on_boshuri_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'bosh_uri', value)

    def on_proxypass_entry_changed(self, widget):
        if self.block_signal:
            return
        value = widget.get_text()
        proxy = self.proxyname_entry.get_text()
        app.config.set_per('proxies', proxy, 'pass', value)


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
        self.window.set_transient_for(app.interface.roster.window)
        if self.is_form:
            dataform = dataforms.ExtendForm(node = infos)
            self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
            if self.data_form_widget.title:
                self.window.set_title('%s - Gajim' % self.data_form_widget.title)
            grid = self.xml.get_object('grid')
            grid.attach(self.data_form_widget, 0, 0, 2, 1)
        else:
            if 'registered' in infos:
                self.window.set_title(_('Edit %s') % service)
            else:
                self.window.set_title(_('Register to %s') % service)
            self.data_form_widget = FakeDataForm(infos)
            grid = self.xml.get_object('grid')
            grid.attach(self.data_form_widget, 0, 0, 2, 1)

        self.xml.connect_signals(self)
        self.window.show_all()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def on_ok_button_clicked(self, widget):
        # send registration info to the core
        if self.is_form:
            form = self.data_form_widget.data_form
            app.connections[self.account].register_agent(self.service,
                    form, True) # True is for is_form
        else:
            infos = self.data_form_widget.get_infos()
            if 'instructions' in infos:
                del infos['instructions']
            if 'registered' in infos:
                del infos['registered']
            app.connections[self.account].register_agent(self.service, infos)

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
        self.window.set_transient_for(app.interface.roster.window)

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
            sw.add(self.affiliation_treeview[affiliation])
            add_on_vbox.pack_start(sw, True, True, 0)
            con = app.connections[self.account]
            con.get_module('MUC').get_affiliation(self.room_jid, affiliation)

        self.xml.connect_signals(self)
        self.window.connect('delete-event', self.on_cancel_button_clicked)
        self.window.show_all()

    def on_cancel_button_clicked(self, *args):
        if self.form:
            con = app.connections[self.account]
            con.get_module('MUC').cancel_config(self.room_jid)
        self.window.destroy()

    def on_cell_edited(self, cell, path, new_text):
        model = self.affiliation_treeview['outcast'].get_model()
        new_text = new_text
        iter_ = model.get_iter(path)
        model[iter_][1] = new_text

    def on_add_button_clicked(self, widget, affiliation):
        if affiliation == 'outcast':
            title = _('Banning…')
            #You can move '\n' before user@domain if that line is TOO BIG
            prompt = _('<b>Whom do you want to ban?</b>\n\n')
        elif affiliation == 'member':
            title = _('Adding Member…')
            prompt = _('<b>Whom do you want to make a member?</b>\n\n')
        elif affiliation == 'owner':
            title = _('Adding Owner…')
            prompt = _('<b>Whom do you want to make an owner?</b>\n\n')
        else:
            title = _('Adding Administrator…')
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
        InputDialog(title, prompt, ok_handler=on_ok)

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
        del app.interface.instances[self.account]['gc_config'][self.room_jid]

    def on_ok_button_clicked(self, widget):
        if self.form:
            form = self.data_form_widget.data_form
            con = app.connections[self.account]
            con.get_module('MUC').set_config(self.room_jid, form)
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
                con = app.connections[self.account]
                con.get_module('MUC').set_affiliation(
                    self.room_jid, users_dict)
        self.window.destroy()

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
    """
    Ask for removing from gajim only or from gajim and server too and do
    removing of the account given
    """

    def on_remove_account_window_destroy(self, widget):
        if self.account in app.interface.instances:
            del app.interface.instances[self.account]['remove_account']

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self, account):
        self.account = account
        xml = gtkgui_helpers.get_gtk_builder('remove_account_window.ui')
        self.window = xml.get_object('remove_account_window')
        active_window = app.app.get_active_window()
        self.window.set_transient_for(active_window)
        self.remove_and_unregister_radiobutton = xml.get_object(
                'remove_and_unregister_radiobutton')
        self.window.set_title(_('Removing %s account') % self.account)
        xml.connect_signals(self)
        self.window.show_all()

    def on_remove_button_clicked(self, widget):
        def remove():
            if self.account in app.connections and \
            app.connections[self.account].connected and \
            not self.remove_and_unregister_radiobutton.get_active():
                # change status to offline only if we will not remove this JID from
                # server
                app.connections[self.account].change_status('offline', 'offline')
            if self.remove_and_unregister_radiobutton.get_active():
                if not self.account in app.connections:
                    ErrorDialog(
                        _('Account is disabled'),
                        _('To unregister from a server, account must be '
                        'enabled.'),
                        transient_for=self.window)
                    return
                if not app.connections[self.account].password:
                    def on_ok(passphrase, checked):
                        if passphrase == -1:
                            # We don't remove account cause we canceled pw window
                            return
                        app.connections[self.account].password = passphrase
                        app.connections[self.account].unregister_account(
                                self._on_remove_success)

                    dialogs.PassphraseDialog(
                            _('Password Required'),
                            _('Enter your password for account %s') % self.account,
                            _('Save password'), ok_handler=on_ok,
                            transient_for=self.window)
                    return
                app.connections[self.account].unregister_account(
                        self._on_remove_success)
            else:
                self._on_remove_success(True)

        if self.account in app.connections and \
        app.connections[self.account].connected:
            ConfirmationDialog(
                _('Account "%s" is connected to the server') % self.account,
                _('If you remove it, the connection will be lost.'),
                on_response_ok=remove,
                transient_for=self.window)
        else:
            remove()

    def on_remove_responce_ok(self, is_checked):
        if is_checked[0]:
            self._on_remove_success(True)

    def _on_remove_success(self, res):
        # action of unregistration has failed, we don't remove the account
        # Error message is send by connect_and_auth()
        if not res:
            ConfirmationDialogDoubleRadio(
                    _('Connection to server %s failed') % self.account,
                    _('What would you like to do?'),
                    _('Remove only from Gajim'),
                    _('Don\'t remove anything. I\'ll try again later'),
                    on_response_ok=self.on_remove_responce_ok, is_modal=False,
                    transient_for=self.window)
            return
        # Close all opened windows
        app.interface.roster.close_all(self.account, force=True)
        if self.account in app.connections:
            app.connections[self.account].disconnect(on_purpose=True)
            app.connections[self.account].cleanup()
            del app.connections[self.account]
        app.logger.remove_roster(app.get_jid_from_account(self.account))
        app.config.del_per('accounts', self.account)
        del app.interface.instances[self.account]
        if self.account in app.nicks:
            del app.interface.minimized_controls[self.account]
            del app.nicks[self.account]
            del app.block_signed_in_notifications[self.account]
            del app.groups[self.account]
            app.contacts.remove_account(self.account)
            del app.gc_connected[self.account]
            del app.automatic_rooms[self.account]
            del app.to_be_removed[self.account]
            del app.newly_added[self.account]
            del app.sleeper_state[self.account]
            del app.encrypted_chats[self.account]
            del app.last_message_time[self.account]
            del app.status_before_autoaway[self.account]
            del app.transport_avatar[self.account]
            del app.gajim_optional_features[self.account]
            del app.caps_hash[self.account]
        if len(app.connections) >= 2: # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        app.app.remove_account_actions(self.account)
        gui_menu_builder.build_accounts_menu()
        if 'accounts' in app.interface.instances:
            app.interface.instances['accounts'].remove_account(self.account)
        self.window.destroy()


class ManageSoundsWindow:
    def __init__(self):
        self._builder = gtkgui_helpers.get_gtk_builder(
            'manage_sounds_window.ui')
        self.window = self._builder.get_object('manage_sounds_window')
        self.window.set_transient_for(
            app.interface.instances['preferences'].window)

        self.sound_button = self._builder.get_object('filechooser')

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.sound_button.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Wav Sounds'))
        filter_.add_pattern('*.wav')
        self.sound_button.add_filter(filter_)
        self.sound_button.set_filter(filter_)

        self.sound_tree = self._builder.get_object('sounds_treeview')

        self._fill_sound_treeview()

        self._builder.connect_signals(self)

        self.window.show_all()

    def _on_row_changed(self, model, path, iter_):
        sound_event = model[iter_][3]
        app.config.set_per('soundevents', sound_event,
                           'enabled', bool(model[path][0]))
        app.config.set_per('soundevents', sound_event,
                           'path', model[iter_][2])

    def _on_toggle(self, cell, path):
        if self.sound_button.get_filename() is None:
            return
        model = self.sound_tree.get_model()
        model[path][0] = not model[path][0]

    def _fill_sound_treeview(self):
        model = self.sound_tree.get_model()
        model.clear()

        # NOTE: sounds_ui_names MUST have all items of
        # sounds = app.config.get_per('soundevents') as keys
        sounds_dict = {
            'attention_received': _('Attention Message Received'),
            'first_message_received': _('First Message Received'),
            'next_message_received_focused': _('Next Message Received Focused'),
            'next_message_received_unfocused': _('Next Message Received Unfocused'),
            'contact_connected': _('Contact Connected'),
            'contact_disconnected': _('Contact Disconnected'),
            'message_sent': _('Message Sent'),
            'muc_message_highlight': _('Group Chat Message Highlight'),
            'muc_message_received': _('Group Chat Message Received'),
        }

        for config_name, sound_name in sounds_dict.items():
            enabled = app.config.get_per('soundevents', config_name, 'enabled')
            path = app.config.get_per('soundevents', config_name, 'path')
            model.append((enabled, sound_name, path, config_name))

    def _on_cursor_changed(self, treeview):
        model, iter_ = treeview.get_selection().get_selected()
        path_to_snd_file = helpers.check_soundfile_path(model[iter_][2])
        if path_to_snd_file is None:
            self.sound_button.unselect_all()
        else:
            self.sound_button.set_filename(path_to_snd_file)

    def _on_file_set(self, button):
        model, iter_ = self.sound_tree.get_selection().get_selected()

        filename = button.get_filename()
        directory = os.path.dirname(filename)
        app.config.set('last_sounds_dir', directory)
        path_to_snd_file = helpers.strip_soundfile_path(filename)

        # set new path to sounds_model
        model[iter_][2] = path_to_snd_file
        # set the sound to enabled
        model[iter_][0] = True

    def _on_clear(self, *args):
        self.sound_button.unselect_all()
        model, iter_ = self.sound_tree.get_selection().get_selected()
        model[iter_][2] = ''
        model[iter_][0] = False

    def _on_play(self, *args):
        model, iter_ = self.sound_tree.get_selection().get_selected()
        snd_event_config_name = model[iter_][3]
        helpers.play_sound(snd_event_config_name)

    def _on_destroy(self, *args):
        self.window.destroy()
        app.interface.instances['preferences'].sounds_preferences = None
