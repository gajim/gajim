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

import os
import sys

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from gajim.common import app
from gajim.common import helpers
from gajim.common import configpaths
from gajim.common import config as c_config
from gajim.common import idle
from gajim.common.i18n import _

from gajim import message_control
from gajim import gtkgui_helpers

from gajim.chat_control_base import ChatControlBase

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.dialogs import AspellDictError
from gajim.gtk.themes import Themes
from gajim.gtk.advanced_config import AdvancedConfig
from gajim.gtk.proxies import ManageProxies
from gajim.gtk.sounds import ManageSounds

try:
    from gajim.common.multimedia_helpers import AudioInputManager, AudioOutputManager
    from gajim.common.multimedia_helpers import VideoInputManager, VideoOutputManager
    HAS_GST = True
except (ImportError, ValueError):
    HAS_GST = False

if app.is_installed('GSPELL'):
    from gi.repository import Gspell


class Preferences(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Preferences'))

        self._ui = get_builder('preferences_window.ui')
        self.add(self._ui.preferences_window)

        ### General tab ###
        ## Behavior of Windows and Tabs
        # Set default for single window type
        choices = c_config.opt_one_window_types
        type_ = app.config.get('one_message_window')
        if type_ in choices:
            self._ui.one_window_type_combobox.set_active(choices.index(type_))
        else:
            self._ui.one_window_type_combobox.set_active(0)

        # Show roster on startup
        choices = c_config.opt_show_roster_on_startup
        type_ = app.config.get('show_roster_on_startup')
        if type_ in choices:
            self._ui.show_roster_on_startup.set_active(choices.index(type_))
        else:
            self._ui.show_roster_on_startup.set_active(0)

        # Quit on roster x
        st = app.config.get('quit_on_roster_x_button')
        self._ui.quit_on_roster_x_checkbutton.set_active(st)

        # Tab placement
        st = app.config.get('tabs_position')
        if st == 'top':
            self._ui.tabs_placement.set_active(0)
        elif st == 'bottom':
            self._ui.tabs_placement.set_active(1)
        elif st == 'left':
            self._ui.tabs_placement.set_active(2)
        else: # right
            self._ui.tabs_placement.set_active(3)

        # Show avatar in tabs
        st = app.config.get('show_avatar_in_tabs')
        self._ui.show_avatar_in_tabs_checkbutton.set_active(st)

        ## Roster Appearance
        # Display avatars in roster
        st = app.config.get('show_avatars_in_roster')
        self._ui.show_avatars_in_roster_checkbutton.set_active(st)

        # Display status msg under contact name in roster
        st = app.config.get('show_status_msgs_in_roster')
        self._ui.show_status_msgs_in_roster_checkbutton.set_active(st)

        # Display PEP in roster
        st1 = app.config.get('show_mood_in_roster')
        st2 = app.config.get('show_activity_in_roster')
        st3 = app.config.get('show_tunes_in_roster')
        st4 = app.config.get('show_location_in_roster')
        if st1 == st2 == st3 == st4:
            self._ui.show_pep_in_roster_checkbutton.set_active(st1)
        else:
            self._ui.show_pep_in_roster_checkbutton.set_inconsistent(True)

        # Sort contacts by show
        st = app.config.get('sort_by_show_in_roster')
        self._ui.sort_by_show_in_roster_checkbutton.set_active(st)
        st = app.config.get('sort_by_show_in_muc')
        self._ui.sort_by_show_in_muc_checkbutton.set_active(st)

        ### Chat tab ###
        ## Chat Settings
        # Use speller
        if app.is_installed('GSPELL'):
            st = app.config.get('use_speller')
            self._ui.speller_checkbutton.set_active(st)
        else:
            self._ui.speller_checkbutton.set_sensitive(False)

        # XEP-0184 positive ack
        st = app.config.get('positive_184_ack')
        self._ui.positive_184_ack_checkbutton.set_active(st)

        # Ignore XHTML
        st = app.config.get('ignore_incoming_xhtml')
        self._ui.xhtml_checkbutton.set_active(st)

        # Print status messages in single chats
        st = app.config.get('print_status_in_chats')
        self._ui.print_status_in_chats_checkbutton.set_active(st)

        # Show subject on join
        st = app.config.get('show_subject_on_join')
        self._ui.subject_on_join_checkbutton.set_active(st)

        # Print status in MUC
        st = app.config.get('print_status_in_muc')
        if st == 'none':
            self._ui.print_status_in_muc_combobox.set_active(0)
        elif st == 'all':
            self._ui.print_status_in_muc_combobox.set_active(1)
        else: # in_and_out
            self._ui.print_status_in_muc_combobox.set_active(2)

        # Displayed chat state notifications
        st = app.config.get('displayed_chat_state_notifications')
        if st == 'all':
            self._ui.displayed_chat_states_combobox.set_active(0)
        elif st == 'composing_only':
            self._ui.displayed_chat_states_combobox.set_active(1)
        else: # disabled
            self._ui.displayed_chat_states_combobox.set_active(2)

        ### Notifications tab ###
        ## Visual Notifications
        # Systray icon
        if app.config.get('trayicon') == 'never':
            self._ui.systray_combobox.set_active(0)
        elif app.config.get('trayicon') == 'on_event':
            self._ui.systray_combobox.set_active(1)
        else: # always
            self._ui.systray_combobox.set_active(2)

        # Notify on new event
        if app.config.get('autopopup'):
            self._ui.on_event_received_combobox.set_active(0)
        elif app.config.get('notify_on_new_message'):
            self._ui.on_event_received_combobox.set_active(1)
        else: # only show in roster
            self._ui.on_event_received_combobox.set_active(2)

        # Notify on online statuses
        st = app.config.get('notify_on_signin')
        self._ui.notify_on_signin_checkbutton.set_active(st)

        # Notify on offline statuses
        st = app.config.get('notify_on_signout')
        self._ui.notify_on_signout_checkbutton.set_active(st)

        # Auto popup when away
        st = app.config.get('autopopupaway')
        self._ui.auto_popup_away_checkbutton.set_active(st)

        # Auto popup when chat already open
        st = app.config.get('autopopup_chat_opened')
        self._ui.auto_popup_chat_opened_checkbutton.set_active(st)

        ## Sounds
        # Sounds
        if app.config.get('sounds_on'):
            self._ui.play_sounds_checkbutton.set_active(True)
        else:
            self._ui.manage_sounds_button.set_sensitive(False)

        # Allow sounds when dnd
        st = app.config.get('sounddnd')
        self._ui.sound_dnd_checkbutton.set_active(st)

        #### Status tab ###
        # Auto away
        st = app.config.get('autoaway')
        self._ui.auto_away_checkbutton.set_active(st)

        # Auto away time
        st = app.config.get('autoawaytime')
        self._ui.auto_away_time_spinbutton.set_value(st)
        self._ui.auto_away_time_spinbutton.set_sensitive(app.config.get('autoaway'))

        # Auto away message
        st = app.config.get('autoaway_message')
        self._ui.auto_away_message_entry.set_text(st)
        self._ui.auto_away_message_entry.set_sensitive(app.config.get('autoaway'))

        # Auto xa
        st = app.config.get('autoxa')
        self._ui.auto_xa_checkbutton.set_active(st)

        # Auto xa time
        st = app.config.get('autoxatime')
        self._ui.auto_xa_time_spinbutton.set_value(st)
        self._ui.auto_xa_time_spinbutton.set_sensitive(app.config.get('autoxa'))

        # Auto xa message
        st = app.config.get('autoxa_message')
        self._ui.auto_xa_message_entry.set_text(st)
        self._ui.auto_xa_message_entry.set_sensitive(app.config.get('autoxa'))

        if not idle.Monitor.is_available():
            self._ui.autoaway_table.set_sensitive(False)

        # Restore last status
        st = self.get_per_account_option('restore_last_status')
        if st == 'mixed':
            self._ui.restore_last_status_checkbutton.set_inconsistent(True)
        else:
            self._ui.restore_last_status_checkbutton.set_active(st)

        # Ask for status when online/offline
        st = app.config.get('ask_online_status')
        self._ui.prompt_online_status_message_checkbutton.set_active(st)
        st = app.config.get('ask_offline_status')
        self._ui.prompt_offline_status_message_checkbutton.set_active(st)

        # Default status messages
        self.fill_default_msg_treeview()

        # Status messages
        renderer = Gtk.CellRendererText()
        renderer.connect('edited', self.on_msg_cell_edited)
        renderer.set_property('editable', True)
        col = Gtk.TreeViewColumn('name', renderer, text=0)
        self._ui.msg_treeview.append_column(col)
        self.fill_msg_treeview()

        buf = self._ui.msg_textview.get_buffer()
        buf.connect('end-user-action', self.on_msg_textview_changed)

        ### Privacy tab ###
        # Send idle time
        st = self.get_per_account_option('send_idle_time')
        if st == 'mixed':
            self._ui.send_idle_time_checkbutton.set_inconsistent(True)
        else:
            self._ui.send_idle_time_checkbutton.set_active(st)

        # Send absolute time info
        st = self.get_per_account_option('send_time_info')
        if st == 'mixed':
            self._ui.send_time_info_checkbutton.set_inconsistent(True)
        else:
            self._ui.send_time_info_checkbutton.set_active(st)

        # Send OS info
        st = self.get_per_account_option('send_os_info')
        if st == 'mixed':
            self._ui.send_os_info_checkbutton.set_inconsistent(True)
        else:
            self._ui.send_os_info_checkbutton.set_active(st)

        # Ignore messages from unknown contacts
        st = self.get_per_account_option('ignore_unknown_contacts')
        if st == 'mixed':
            self._ui.ignore_events_from_unknown_contacts_checkbutton.set_inconsistent(True)
        else:
            self._ui.ignore_events_from_unknown_contacts_checkbutton.set_active(st)

        # Outgoing chat state notifications
        st = app.config.get('outgoing_chat_state_notifications')
        if st == 'all':
            self._ui.outgoing_chat_states_combobox.set_active(0)
        elif st == 'composing_only':
            self._ui.outgoing_chat_states_combobox.set_active(1)
        else: # disabled
            self._ui.outgoing_chat_states_combobox.set_active(2)

        ### Style tab ###
        # Themes
        self.changed_id = self._ui.theme_combobox.connect(
            'changed', self.on_theme_combobox_changed)
        self.update_theme_list()

        # Dark theme
        self._ui.dark_theme_combobox.set_active_id(str(app.config.get('dark_theme')))

        # Emoticons
        emoticon_themes = helpers.get_available_emoticon_themes()

        for theme in emoticon_themes:
            self._ui.emoticons_combobox.append_text(theme)

        config_theme = app.config.get('emoticons_theme')
        if config_theme not in emoticon_themes:
            config_theme = 'font'
        self._ui.emoticons_combobox.set_id_column(0)
        self._ui.emoticons_combobox.set_active_id(config_theme)

        self._ui.ascii_emoticons.set_active(app.config.get('ascii_emoticons'))

        # Iconset
        iconsets_list = os.listdir(
            os.path.join(configpaths.get('DATA'), 'iconsets'))
        if os.path.isdir(configpaths.get('MY_ICONSETS')):
            iconsets_list += os.listdir(configpaths.get('MY_ICONSETS'))

        model = Gtk.ListStore(str, str)
        renderer_image = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property('xpad', 5)
        self._ui.iconset_combobox.pack_start(renderer_image, False)
        self._ui.iconset_combobox.pack_start(renderer_text, True)
        self._ui.iconset_combobox.add_attribute(renderer_text, 'text', 1)
        self._ui.iconset_combobox.add_attribute(renderer_image, 'icon_name', 0)
        self._ui.iconset_combobox.set_model(model)
        dirlist = []
        for dir_ in iconsets_list:
            if not os.path.isdir(os.path.join(configpaths.get('DATA'), 'iconsets', dir_)) \
            and not os.path.isdir(os.path.join(configpaths.get('MY_ICONSETS'), dir_)):
                continue
            if dir_ not in ('.svn', 'transports'):
                dirlist.append(dir_)
        if not dirlist:
            dirlist.append(' ')
        for index, dir_ in enumerate(dirlist):
            icon_name = get_icon_name('online', iconset=dir_)
            model.append([icon_name, dir_])
            if app.config.get('iconset') == dir_:
                self._ui.iconset_combobox.set_active(index)

        # Use transports iconsets
        st = app.config.get('use_transports_iconsets')
        self._ui.transports_iconsets_checkbutton.set_active(st)

        ### Audio/Video tab ###
        def create_av_combobox(opt_name, device_dict, config_name=None,
        key=None):
            combobox = self._ui.get_object(opt_name + '_combobox')
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
            self._ui.video_see_self_checkbutton.set_active(st)

        else:
            for opt_name in ('audio_input', 'audio_output', 'video_input',
            'video_output', 'video_framerate', 'video_size'):
                combobox = self._ui.get_object(opt_name + '_combobox')
                combobox.set_sensitive(False)

        # STUN
        st = app.config.get('use_stun_server')
        self._ui.stun_checkbutton.set_active(st)

        self._ui.stun_server_entry.set_text(app.config.get('stun_server'))
        if not st:
            self._ui.stun_server_entry.set_sensitive(False)

        ### Advanced tab ###
        ## Applications (open links with)
        if os.name == 'nt':
            self._ui.custom_apps_frame.set_no_show_all(True)
            self._ui.custom_apps_frame.hide()
        else:
            self._ui.custom_apps_frame.hide()
            self._ui.custom_apps_frame.set_no_show_all(True)

            if app.config.get('autodetect_browser_mailer'):
                self._ui.applications_combobox.set_active(0)
            else:
                self._ui.applications_combobox.set_active(1)
                self._ui.custom_apps_frame.show()

            self._ui.custom_browser_entry.set_text(
                app.config.get('custombrowser'))
            self._ui.custom_mail_client_entry.set_text(
                app.config.get('custommailapp'))
            self._ui.custom_file_manager_entry.set_text(
                app.config.get('custom_file_manager'))

        ## Miscellaneous
        # Proxy
        self.update_proxy_list()

        # Log status changes of contacts
        st = app.config.get('log_contact_status_changes')
        self._ui.log_show_changes_checkbutton.set_active(st)

        # Enable debug logging
        if sys.platform == 'win32':
            self._ui.enable_logging.set_active(app.get_win_debug_mode())
            self._ui.enable_logging.show()

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)

        self._ui.msg_treeview.get_model().connect('row-changed',
                                self.on_msg_treemodel_row_changed)
        self._ui.msg_treeview.get_model().connect('row-deleted',
                                self.on_msg_treemodel_row_deleted)
        self._ui.default_msg_treeview.get_model().connect('row-changed',
                                self.on_default_msg_treemodel_row_changed)

        self.sounds_preferences = None
        self.theme_preferences = None

        self.show_all()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_per_account_option(self, opt):
        """
        Return the value of the option opt if it's the same in all accounts else
        returns "mixed"
        """
        if not app.connections:
            # A non existent key return default value
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

    ### General tab ###
    def on_one_window_type_combo_changed(self, widget):
        active = widget.get_active()
        config_type = c_config.opt_one_window_types[active]
        app.config.set('one_message_window', config_type)
        app.interface.msg_win_mgr.reconfig()

    def on_show_roster_on_startup_changed(self, widget):
        active = widget.get_active()
        config_type = c_config.opt_show_roster_on_startup[active]
        app.config.set('show_roster_on_startup', config_type)

    def on_quit_on_roster_x_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'quit_on_roster_x_button')

    def on_tab_placement_changed(self, widget):
        active = widget.get_active()
        if active == 0: # top
            app.config.set('tabs_position', 'top')
        elif active == 1: # bottom
            app.config.set('tabs_position', 'bottom')
        elif active == 2: # left
            app.config.set('tabs_position', 'left')
        else: # right
            app.config.set('tabs_position', 'right')

    def on_show_avatar_in_tabs_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatar_in_tabs')

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

    def on_sort_by_show_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_sort_by_show_in_muc_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_muc')
        # Redraw groupchats
        for ctrl in self._get_all_muc_controls():
            ctrl.draw_roster()

    ### Chat tab ###
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

    def apply_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, ChatControlBase):
                ctrl.set_speller()

    def on_positive_184_ack_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'positive_184_ack')

    def on_xhtml_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ignore_incoming_xhtml')
        helpers.update_optional_features()

    def on_print_status_in_chats_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'print_status_in_chats')

    def on_subject_on_join_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_subject_on_join')

    def print_status_in_muc_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0: # none
            app.config.set('print_status_in_muc', 'none')
        elif active == 1: # all
            app.config.set('print_status_in_muc', 'all')
        else: # in_and_out
            app.config.set('print_status_in_muc', 'in_and_out')

    def on_displayed_chat_states_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0: # all
            app.config.set('displayed_chat_state_notifications', 'all')
        elif active == 1: # only composing
            app.config.set('displayed_chat_state_notifications',
                    'composing_only')
        else: # disabled
            app.config.set('displayed_chat_state_notifications', 'disabled')

    ### Notifications tab ###
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

    def on_event_received_combobox_changed(self, widget):
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

    def on_play_sounds_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounds_on',
                [self._ui.manage_sounds_button])

    def on_manage_sounds_button_clicked(self, widget):
        if self.sounds_preferences is None:
            self.sounds_preferences = ManageSounds()
        else:
            self.sounds_preferences.window.present()

    def on_sound_dnd_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounddnd')

    ### Status tab ###
    def on_auto_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoaway',
                                [self._ui.auto_away_time_spinbutton,
                                 self._ui.auto_away_message_entry])

    def on_auto_away_time_spinbutton_value_changed(self, widget):
        aat = widget.get_value_as_int()
        app.config.set('autoawaytime', aat)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_away_message_entry_changed(self, widget):
        app.config.set('autoaway_message', widget.get_text())

    def on_auto_xa_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoxa',
                                [self._ui.auto_xa_time_spinbutton,
                                 self._ui.auto_xa_message_entry])

    def on_auto_xa_time_spinbutton_value_changed(self, widget):
        axt = widget.get_value_as_int()
        app.config.set('autoxatime', axt)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_xa_message_entry_changed(self, widget):
        app.config.set('autoxa_message', widget.get_text())

    def on_restore_last_status_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'restore_last_status')

    def on_prompt_online_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_online_status')

    def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_offline_status')

    def fill_default_msg_treeview(self):
        model = self._ui.default_msg_treeview.get_model()
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
        model = self._ui.default_msg_treeview.get_model()
        iter_ = model.get_iter_from_string(row)
        model.set_value(iter_, 2, new_text)

    def default_msg_toggled_cb(self, cell, path):
        model = self._ui.default_msg_treeview.get_model()
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
            if model[iter_][1]: # We have a preset message
                if not val: # No title, use message text for title
                    val = model[iter_][1]
                app.config.add_per('statusmsg', val)
                msg = helpers.to_one_line(model[iter_][1])
                app.config.set_per('statusmsg', val, 'message', msg)
                i = 2
                # Store mood / activity
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

    def fill_msg_treeview(self):
        self._ui.delete_msg_button.set_sensitive(False)
        model = self._ui.msg_treeview.get_model()
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
        model = self._ui.msg_treeview.get_model()
        iter_ = model.get_iter_from_string(row)
        model.set_value(iter_, 0, new_text)

    def on_msg_treeview_cursor_changed(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        self._ui.delete_msg_button.set_sensitive(True)
        buf = self._ui.msg_textview.get_buffer()
        msg = model[iter_][1]
        buf.set_text(msg)

    def on_new_msg_button_clicked(self, widget, data=None):
        model = self._ui.msg_treeview.get_model()
        iter_ = model.append()
        model.set(
            iter_, 0, _('status message title'), 1,
            _('status message text'))
        self._ui.msg_treeview.set_cursor(model.get_path(iter_))

    def on_delete_msg_button_clicked(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self._ui.msg_textview.get_buffer()
        model.remove(iter_)
        buf.set_text('')
        self._ui.delete_msg_button.set_sensitive(False)

    def on_msg_textview_changed(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self._ui.msg_textview.get_buffer()
        first_iter, end_iter = buf.get_bounds()
        model.set_value(iter_, 1, buf.get_text(first_iter, end_iter, True))

    def on_msg_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_delete_msg_button_clicked(widget)

    ### Privacy tab ###
    def on_send_idle_time_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_idle_time')

    def on_send_time_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_time_info')

    def on_send_os_info_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'send_os_info')

    def on_ignore_events_from_unknown_contacts_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'ignore_unknown_contacts')

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
            # We changed from disabled to sth else or vice versa
            helpers.update_optional_features()

    ### Style ###
    @staticmethod
    def on_theme_combobox_changed(combobox):
        theme = combobox.get_active_id()
        app.config.set('roster_theme', theme)
        app.css_config.change_theme(theme)

        # Begin repainting themed widgets throughout
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)

    def update_theme_list(self):
        with self._ui.theme_combobox.handler_block(self.changed_id):
            self._ui.theme_combobox.remove_all()
            self._ui.theme_combobox.append('default', 'default')
            for config_theme in app.css_config.themes:
                self._ui.theme_combobox.append(config_theme, config_theme)

        self._ui.theme_combobox.set_active_id(app.config.get('roster_theme'))

    def on_manage_theme_button_clicked(self, widget):
        window = app.get_app_window(Themes)
        if window is None:
            Themes(self)
        else:
            window.present()

    def on_dark_theme_changed(self, widget):
        app.css_config.set_dark_theme(int(widget.get_active_id()))

    def on_emoticons_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        emot_theme = model[active][0]
        app.config.set('emoticons_theme', emot_theme)
        from gajim.gtk.emoji_chooser import emoji_chooser
        emoji_chooser.load()
        self.toggle_emoticons()

    def on_convert_ascii_toggle(self, widget):
        app.config.set('ascii_emoticons', widget.get_active())
        app.interface.make_regexps()

    def toggle_emoticons(self):
        """
        Update emoticons state in Opened Chat Windows
        """
        for ctrl in self._get_all_controls():
            ctrl.toggle_emoticons()

    def on_iconset_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        icon_string = model[active][1]
        app.config.set('iconset', icon_string)
        gtkgui_helpers.reload_jabber_state_images()

    def on_transports_iconsets_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_transports_iconsets')
        gtkgui_helpers.reload_jabber_state_images()

    ### Audio/Video tab ###
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
        self.on_checkbutton_toggled(widget, 'use_stun_server', [
            self._ui.stun_server_entry])

    def stun_server_entry_changed(self, widget):
        app.config.set('stun_server', widget.get_text())

    ### Advanced tab ###
    # Applications
    def on_applications_combobox_changed(self, widget):
        if widget.get_active() == 0:
            app.config.set('autodetect_browser_mailer', True)
            self._ui.custom_apps_frame.hide()
        elif widget.get_active() == 1:
            app.config.set('autodetect_browser_mailer', False)
            self._ui.custom_apps_frame.show()

    def on_custom_browser_entry_changed(self, widget):
        app.config.set('custombrowser', widget.get_text())

    def on_custom_mail_client_entry_changed(self, widget):
        app.config.set('custommailapp', widget.get_text())

    def on_custom_file_manager_entry_changed(self, widget):
        app.config.set('custom_file_manager', widget.get_text())

    # Proxies
    def on_proxies_combobox_changed(self, widget):
        active = widget.get_active()
        if active == -1:
            return
        proxy = widget.get_model()[active][0]
        if proxy == _('None'):
            proxy = ''
        app.config.set('global_proxy', proxy)

    def on_manage_proxies_button_clicked(self, widget):
        if 'manage_proxies' in app.interface.instances:
            app.interface.instances['manage_proxies'].window.present()
        else:
            app.interface.instances['manage_proxies'] = ManageProxies()

    def update_proxy_list(self):
        our_proxy = app.config.get('global_proxy')
        if not our_proxy:
            our_proxy = _('None')
        model = self._ui.proxies_combobox.get_model()
        model.clear()
        proxies = app.config.get_per('proxies')
        proxies.insert(0, _('None'))
        for index, proxy in enumerate(proxies):
            model.append([proxy])
            if our_proxy == proxy:
                self._ui.proxies_combobox.set_active(index)
        if not our_proxy in proxies:
            self._ui.proxies_combobox.set_active(0)

    # Log status changes of contacts
    def on_log_show_changes_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

    # Enable debug logging
    def on_enable_logging_toggled(self, widget):
        app.set_win_debug_mode(widget.get_active())

    # Advanced Config Editor (ACE)
    def on_open_advanced_editor_button_clicked(self, widget, data=None):
        if 'advanced_config' in app.interface.instances:
            app.interface.instances['advanced_config'].window.present()
        else:
            app.interface.instances['advanced_config'] = AdvancedConfig(self)
