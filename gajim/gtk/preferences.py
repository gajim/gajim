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

import logging
import os
import sys

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

try:
    from gi.repository import Gst
except Exception:
    pass

from gajim.common import app
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common import idle
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.i18n import ngettext
from gajim.common.helpers import open_file
from gajim.common.multimedia_helpers import AudioInputManager
from gajim.common.multimedia_helpers import AudioOutputManager
from gajim.common.multimedia_helpers import VideoInputManager

from gajim.chat_control_base import ChatControlBase

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_available_iconsets
from gajim.gtk.util import open_window
from gajim.gtk.sounds import ManageSounds
from gajim.gtk.const import ControlType
from gajim.gtk import gstreamer

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

log = logging.getLogger('gajim.gtk.preferences')


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
        self._ui.one_window_type_combobox.set_active_id(
            app.settings.get('one_message_window'))

        # Show roster on startup
        self._ui.show_roster_on_startup.set_active_id(
            app.settings.get('show_roster_on_startup'))

        # Quit on roster x
        st = app.settings.get('quit_on_roster_x_button')
        self._ui.quit_on_roster_x_checkbutton.set_active(st)

        # Tab placement
        st = app.settings.get('tabs_position')
        if st == 'top':
            self._ui.tabs_placement.set_active(0)
        elif st == 'bottom':
            self._ui.tabs_placement.set_active(1)
        elif st == 'left':
            self._ui.tabs_placement.set_active(2)
        else: # right
            self._ui.tabs_placement.set_active(3)

        ## Contact List Appearance
        # Merge accounts
        st = app.settings.get('mergeaccounts')
        self._ui.merge_accounts_checkbutton.set_active(st)

        # Display avatars in roster
        st = app.settings.get('show_avatars_in_roster')
        self._ui.show_avatars_in_roster_checkbutton.set_active(st)

        # Display status msg under contact name in roster
        st = app.settings.get('show_status_msgs_in_roster')
        self._ui.show_status_msgs_in_roster_checkbutton.set_active(st)

        # Display PEP in roster
        st1 = app.settings.get('show_mood_in_roster')
        st2 = app.settings.get('show_activity_in_roster')
        st3 = app.settings.get('show_tunes_in_roster')
        st4 = app.settings.get('show_location_in_roster')
        if st1 == st2 == st3 == st4:
            self._ui.show_pep_in_roster_checkbutton.set_active(st1)
        else:
            self._ui.show_pep_in_roster_checkbutton.set_inconsistent(True)

        # Sort contacts by show
        st = app.settings.get('sort_by_show_in_roster')
        self._ui.sort_by_show_in_roster_checkbutton.set_active(st)
        st = app.settings.get('sort_by_show_in_muc')
        self._ui.sort_by_show_in_muc_checkbutton.set_active(st)

        ### Chat tab ###
        ## General Settings

        # Enable auto copy
        st = app.settings.get('auto_copy')
        self._ui.auto_copy.set_active(st)

        ## Chat Settings
        # Use speller
        if app.is_installed('GSPELL'):
            st = app.settings.get('use_speller')
            self._ui.speller_checkbutton.set_active(st)
        else:
            self._ui.speller_checkbutton.set_sensitive(False)

        # XEP-0184 positive ack
        st = app.settings.get('positive_184_ack')
        self._ui.positive_184_ack_checkbutton.set_active(st)

        # Ignore XHTML
        st = app.settings.get('show_xhtml')
        self._ui.xhtml_checkbutton.set_active(st)

        # Print status messages in single chats
        st = app.settings.get('print_status_in_chats')
        self._ui.print_status_in_chats_checkbutton.set_active(st)

        # Show subject on join
        st = app.settings.get('show_subject_on_join')
        self._ui.subject_on_join_checkbutton.set_active(st)

        # Group chat settings
        threshold_model = self._ui.sync_threshold_combobox.get_model()
        options = app.settings.get('threshold_options').split(',')
        days = [int(option.strip()) for option in options]
        for day in days:
            if day == 0:
                label = _('No threshold')
            else:
                label = ngettext('%i day', '%i days', day, day, day)
            threshold_model.append([str(day), label])
        public_threshold = app.settings.get('public_room_sync_threshold')
        self._ui.sync_threshold_combobox.set_id_column(0)
        self._ui.sync_threshold_combobox.set_active_id(str(public_threshold))

        st = app.settings.get('gc_print_join_left_default')
        self._ui.join_leave_checkbutton.set_active(st)

        st = app.settings.get('gc_print_status_default')
        self._ui.show_status_change_checkbutton.set_active(st)

        # Displayed chat state notifications
        st = app.settings.get('show_chatstate_in_tabs')
        self._ui.show_chatstate_in_tabs.set_active(st)

        st = app.settings.get('show_chatstate_in_roster')
        self._ui.show_chatstate_in_roster.set_active(st)

        st = app.settings.get('show_chatstate_in_banner')
        self._ui.show_chatstate_in_banner.set_active(st)

        ### Notifications tab ###
        ## Visual Notifications
        # Systray icon
        if app.settings.get('trayicon') == 'never':
            self._ui.systray_combobox.set_active(0)
        elif app.settings.get('trayicon') == 'on_event':
            self._ui.systray_combobox.set_active(1)
        else: # always
            self._ui.systray_combobox.set_active(2)

        # Notify on new event
        if app.settings.get('autopopup'):
            self._ui.on_event_received_combobox.set_active(0)
        elif app.settings.get('notify_on_new_message'):
            self._ui.on_event_received_combobox.set_active(1)
        else: # only show in roster
            self._ui.on_event_received_combobox.set_active(2)

        # Notify on online statuses
        st = app.settings.get('notify_on_signin')
        self._ui.notify_on_signin_checkbutton.set_active(st)

        # Notify on offline statuses
        st = app.settings.get('notify_on_signout')
        self._ui.notify_on_signout_checkbutton.set_active(st)

        # Auto popup when away
        st = app.settings.get('autopopupaway')
        self._ui.auto_popup_away_checkbutton.set_active(st)

        # Auto popup when chat already open
        st = app.settings.get('autopopup_chat_opened')
        self._ui.auto_popup_chat_opened_checkbutton.set_active(st)

        ## Sounds
        # Sounds
        if app.settings.get('sounds_on'):
            self._ui.play_sounds_checkbutton.set_active(True)
        else:
            self._ui.manage_sounds_button.set_sensitive(False)

        # Allow sounds when dnd
        st = app.settings.get('sounddnd')
        self._ui.sound_dnd_checkbutton.set_active(st)

        #### Status tab ###
        # Auto away
        st = app.settings.get('autoaway')
        self._ui.auto_away_checkbutton.set_active(st)

        # Auto away time
        st = app.settings.get('autoawaytime')
        self._ui.auto_away_time_spinbutton.set_value(st)
        self._ui.auto_away_time_spinbutton.set_sensitive(app.settings.get('autoaway'))

        # Auto away message
        st = app.settings.get('autoaway_message')
        self._ui.auto_away_message_entry.set_text(st)
        self._ui.auto_away_message_entry.set_sensitive(app.settings.get('autoaway'))

        # Auto xa
        st = app.settings.get('autoxa')
        self._ui.auto_xa_checkbutton.set_active(st)

        # Auto xa time
        st = app.settings.get('autoxatime')
        self._ui.auto_xa_time_spinbutton.set_value(st)
        self._ui.auto_xa_time_spinbutton.set_sensitive(app.settings.get('autoxa'))

        # Auto xa message
        st = app.settings.get('autoxa_message')
        self._ui.auto_xa_message_entry.set_text(st)
        self._ui.auto_xa_message_entry.set_sensitive(app.settings.get('autoxa'))

        if not idle.Monitor.is_available():
            self._ui.autoaway_table.set_sensitive(False)

        # Ask for status when online/offline
        st = app.settings.get('ask_online_status')
        self._ui.sign_in_status_checkbutton.set_active(st)
        st = app.settings.get('ask_offline_status')
        self._ui.sign_out_status_checkbutton.set_active(st)
        st = app.settings.get('always_ask_for_status_message')
        self._ui.status_change_checkbutton.set_active(st)

        ### Style tab ###
        # Themes
        self.changed_id = self._ui.theme_combobox.connect(
            'changed', self.on_theme_combobox_changed)
        self.update_theme_list()

        # Dark theme
        self._ui.dark_theme_combobox.set_active_id(str(app.settings.get('dark_theme')))

        # Emoticons
        emoticon_themes = helpers.get_available_emoticon_themes()

        for theme in emoticon_themes:
            self._ui.emoticons_combobox.append_text(theme)

        config_theme = app.settings.get('emoticons_theme')
        if config_theme not in emoticon_themes:
            config_theme = 'font'
        self._ui.emoticons_combobox.set_id_column(0)
        self._ui.emoticons_combobox.set_active_id(config_theme)

        self._ui.ascii_emoticons.set_active(app.settings.get('ascii_emoticons'))

        # Iconset
        model = Gtk.ListStore(str, str)
        renderer_image = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property('xpad', 5)
        self._ui.iconset_combobox.pack_start(renderer_image, False)
        self._ui.iconset_combobox.pack_start(renderer_text, True)
        self._ui.iconset_combobox.add_attribute(renderer_text, 'text', 1)
        self._ui.iconset_combobox.add_attribute(renderer_image, 'icon_name', 0)
        self._ui.iconset_combobox.set_model(model)

        for index, iconset_name in enumerate(get_available_iconsets()):
            icon_name = get_icon_name('online', iconset=iconset_name)
            model.append([icon_name, iconset_name])
            if app.settings.get('iconset') == iconset_name:
                self._ui.iconset_combobox.set_active(index)

        # Use transports iconsets
        st = app.settings.get('use_transports_iconsets')
        self._ui.transports_iconsets_checkbutton.set_active(st)

        ### Audio/Video tab ###
        def create_av_combobox(opt_name, device_dict, config_name=None,
                               # This key is there to give the first index to autovideosrc and co.
                               key=lambda x: '' if x[1].startswith('auto') else x[0].lower()):
            combobox = self._ui.get_object(opt_name + '_combobox')
            cell = Gtk.CellRendererText()
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)
            cell.set_property('ellipsize-set', True)
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)
            model = Gtk.ListStore(str, str)
            combobox.set_model(model)
            if config_name:
                config = app.settings.get(config_name)
            else:
                config = app.settings.get(opt_name + '_device')

            for index, (name, value) in enumerate(sorted(device_dict.items(),
                                                         key=key)):
                model.append((name, value))
                if config == value:
                    combobox.set_active(index)

        if os.name == 'nt':
            self._ui.av_dependencies_label.set_text(
                _('Feature not available under Windows'))
        else:
            self._ui.av_dependencies_label.set_text(
                _('Missing dependencies for Audio/Video'))

        if app.is_installed('AV'):
            self._ui.av_dependencies_infobar.set_no_show_all(True)
            self._ui.av_dependencies_infobar.hide()

            create_av_combobox(
                'audio_input', AudioInputManager().get_devices())
            create_av_combobox(
                'audio_output', AudioOutputManager().get_devices())
            create_av_combobox(
                'video_input', VideoInputManager().get_devices())

            create_av_combobox(
                'video_framerate',
                {_('Default'): '',
                 '15fps': '15/1',
                 '10fps': '10/1',
                 '5fps': '5/1',
                 '2.5fps': '5/2'},
                'video_framerate',
                key=lambda x: -1 if not x[1] else float(x[0][:-3]))
            create_av_combobox(
                'video_size',
                {_('Default'): '',
                 '800x600': '800x600',
                 '640x480': '640x480',
                 '320x240': '320x240'},
                'video_size',
                key=lambda x: -1 if not x[1] else int(x[0][:3]))
            st = app.settings.get('video_see_self')
            self._ui.video_see_self_checkbutton.set_active(st)

            self.av_pipeline = None
            self.av_src = None
            self.av_sink = None
            self.av_widget = None
        else:
            for opt_name in ('audio_input', 'audio_output', 'video_input',
                             'video_framerate', 'video_size'):
                combobox = self._ui.get_object(opt_name + '_combobox')
                combobox.set_sensitive(False)
            self._ui.live_preview_checkbutton.set_sensitive(False)

        # STUN
        st = app.settings.get('use_stun_server')
        self._ui.stun_checkbutton.set_active(st)
        self._ui.stun_server_entry.set_sensitive(st)
        self._ui.stun_server_entry.set_text(app.settings.get('stun_server'))

        ### Advanced tab ###

        ## Miscellaneous
        # Proxy
        self.update_proxy_list()

        # Log status changes of contacts
        st = app.settings.get('log_contact_status_changes')
        self._ui.log_show_changes_checkbutton.set_active(st)

        st = app.settings.get('use_keyring')
        self._ui.use_keyring_checkbutton.set_active(st)

        self._ui.enable_logging.set_active(app.get_debug_mode())
        self._ui.enable_logging.show()

        if sys.platform in ('win32', 'darwin'):
            st = app.settings.get('check_for_update')
            self._ui.update_check.set_active(st)
            self._ui.update_check.show()

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)

        self.sounds_preferences = None
        self.theme_preferences = None

        self.show_all()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def on_checkbutton_toggled(self, widget, config_name,
                               change_sensitivity_widgets=None):
        app.settings.set(config_name, widget.get_active())
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
                ControlType.GROUPCHAT):
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    ### General tab ###
    def on_one_window_type_combo_changed(self, combobox):
        app.settings.set('one_message_window', combobox.get_active_id())
        app.interface.msg_win_mgr.reconfig()

    def on_show_roster_on_startup_changed(self, combobox):
        app.settings.set('show_roster_on_startup', combobox.get_active_id())

    def on_quit_on_roster_x_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'quit_on_roster_x_button')

    def on_tab_placement_changed(self, widget):
        active = widget.get_active()
        if active == 0: # top
            app.settings.set('tabs_position', 'top')
        elif active == 1: # bottom
            app.settings.set('tabs_position', 'bottom')
        elif active == 2: # left
            app.settings.set('tabs_position', 'left')
        else: # right
            app.settings.set('tabs_position', 'right')

    def on_merge_accounts_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'mergeaccounts')
        app.app.activate_action('merge')

    def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
        app.interface.roster.setup_and_draw_roster()
        for ctrl in self._get_all_muc_controls():
            ctrl.roster.draw_contacts()

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
            ctrl.roster.invalidate_sort()

    ### Chat tab ###
    def on_auto_copy_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'auto_copy')

    def on_speller_checkbutton_toggled(self, widget):
        active = widget.get_active()
        app.settings.set('use_speller', active)
        if not active:
            return
        lang = app.settings.get('speller_language')
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        app.settings.set('speller_language', gspell_lang.get_code())
        self.apply_speller()

    def apply_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, ChatControlBase):
                ctrl.set_speller()

    def on_positive_184_ack_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'positive_184_ack')

    def on_xhtml_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_xhtml')

    def on_print_status_in_chats_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'print_status_in_chats')

    def on_subject_on_join_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_subject_on_join')

    def _on_sync_threshold_changed(self, widget):
        active = widget.get_active_id()
        app.settings.set('public_room_sync_threshold', int(active))

    def _on_join_leave_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'gc_print_join_left_default')
        for control in self._get_all_muc_controls():
            control.update_actions()

    def _on_show_status_change_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'gc_print_status_default')
        for control in self._get_all_muc_controls():
            control.update_actions()

    def on_show_chatstate_in_tabs_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_tabs')

    def on_show_chatstate_in_roster_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_roster')

    def on_show_chatstate_in_banner_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_banner')

    ### Notifications tab ###
    def on_systray_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.settings.set('trayicon', 'never')
            app.interface.hide_systray()
        elif active == 1:
            app.settings.set('trayicon', 'on_event')
            app.interface.show_systray()
        else:
            app.settings.set('trayicon', 'always')
            app.interface.show_systray()

    def on_event_received_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.settings.set('autopopup', True)
            app.settings.set('notify_on_new_message', False)
        elif active == 1:
            app.settings.set('autopopup', False)
            app.settings.set('notify_on_new_message', True)
        else:
            app.settings.set('autopopup', False)
            app.settings.set('notify_on_new_message', False)

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
        app.settings.set('autoawaytime', aat)
        idle.Monitor.set_interval(app.settings.get('autoawaytime') * 60,
                                  app.settings.get('autoxatime') * 60)

    def on_auto_away_message_entry_changed(self, widget):
        app.settings.set('autoaway_message', widget.get_text())

    def on_auto_xa_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoxa',
                                [self._ui.auto_xa_time_spinbutton,
                                 self._ui.auto_xa_message_entry])

    def on_auto_xa_time_spinbutton_value_changed(self, widget):
        axt = widget.get_value_as_int()
        app.settings.set('autoxatime', axt)
        idle.Monitor.set_interval(app.settings.get('autoawaytime') * 60,
                                  app.settings.get('autoxatime') * 60)

    def on_auto_xa_message_entry_changed(self, widget):
        app.settings.set('autoxa_message', widget.get_text())

    def on_sign_in_status_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_online_status')

    def on_sign_out_status_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_offline_status')

    def on_status_change_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'always_ask_for_status_message')

    ### Style ###
    @staticmethod
    def on_theme_combobox_changed(combobox):
        theme = combobox.get_active_id()
        app.settings.set('roster_theme', theme)
        app.css_config.change_theme(theme)
        app.nec.push_incoming_event(NetworkEvent('theme-update'))

        # Begin repainting themed widgets throughout
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)

    def update_theme_list(self):
        with self._ui.theme_combobox.handler_block(self.changed_id):
            self._ui.theme_combobox.remove_all()
            self._ui.theme_combobox.append('default', 'default')
            for config_theme in app.css_config.themes:
                self._ui.theme_combobox.append(config_theme, config_theme)

        self._ui.theme_combobox.set_active_id(app.settings.get('roster_theme'))

    def on_manage_theme_button_clicked(self, widget):
        open_window('Themes', transient=self)

    def on_dark_theme_changed(self, widget):
        app.css_config.set_dark_theme(int(widget.get_active_id()))

    def on_emoticons_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        emot_theme = model[active][0]
        app.settings.set('emoticons_theme', emot_theme)
        from gajim.gtk.emoji_chooser import emoji_chooser
        emoji_chooser.load()
        self.toggle_emoticons()

    def on_convert_ascii_toggle(self, widget):
        app.settings.set('ascii_emoticons', widget.get_active())
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
        app.settings.set('iconset', icon_string)
        app.interface.roster.update_icons()

    def on_transports_iconsets_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_transports_iconsets')

    ### Audio/Video tab ###
    def _on_features_button_clicked(self, _button):
        open_window('Features')

    def on_av_combobox_changed(self, combobox, config_name):
        model = combobox.get_model()
        active = combobox.get_active()
        device = model[active][1]
        app.settings.set(config_name, device)
        return device

    def on_audio_input_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_input_device')

    def on_audio_output_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_output_device')

    def on_video_input_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        device = model[active][1]

        try:
            src = Gst.parse_bin_from_description(device, True)
        except GLib.Error:
            # TODO: disable the entry instead of just selecting the default.
            log.error('Failed to parse "%s" as Gstreamer element,'
                      ' falling back to autovideosrc', device)
            widget.set_active(0)
            return

        if self._ui.live_preview_checkbutton.get_active():
            self.av_pipeline.set_state(Gst.State.NULL)
            if self.av_src is not None:
                self.av_pipeline.remove(self.av_src)
            self.av_pipeline.add(src)
            src.link(self.av_sink)
            self.av_src = src
            self.av_pipeline.set_state(Gst.State.PLAYING)
        app.settings.set('video_input_device', device)

    def _on_live_preview_toggled(self, widget):
        if widget.get_active():
            sink, widget, name = gstreamer.create_gtk_widget()
            if sink is None:
                log.error('Failed to obtain a working Gstreamer GTK+ sink, '
                          'video support will be disabled')
                self._ui.video_input_combobox.set_sensitive(False)
                self._ui.selected_video_output.set_markup(
                    _('<span color="red" font-weight="bold">'
                      'Unavailable</span>, video support will be disabled'))
                return

            text = ''
            if name == 'gtkglsink':
                text = _('<span color="green" font-weight="bold">'
                         'OpenGL</span> accelerated')
            elif name == 'gtksink':
                text = _('<span color="yellow" font-weight="bold">'
                         'Unaccelerated</span>')
            self._ui.selected_video_output.set_markup(text)
            if self.av_pipeline is None:
                self.av_pipeline = Gst.Pipeline.new('preferences-pipeline')
            else:
                self.av_pipeline.set_state(Gst.State.NULL)
            self.av_pipeline.add(sink)
            self.av_sink = sink

            if self.av_widget is not None:
                self._ui.av_preview_box.remove(self.av_widget)
            self._ui.av_preview_placeholder.set_visible(False)
            self._ui.av_preview_box.add(widget)
            self.av_widget = widget

            src_name = app.settings.get('video_input_device')
            try:
                self.av_src = Gst.parse_bin_from_description(src_name, True)
            except GLib.Error:
                log.error('Failed to parse "%s" as Gstreamer element, '
                          'falling back to autovideosrc', src_name)
                self.av_src = None
            if self.av_src is not None:
                self.av_pipeline.add(self.av_src)
                self.av_src.link(self.av_sink)
                self.av_pipeline.set_state(Gst.State.PLAYING)
            else:
                # Parsing the pipeline stored in video_input_device failed,
                # let’s try the default one.
                self.av_src = Gst.ElementFactory.make('autovideosrc', None)
                if self.av_src is None:
                    log.error('Failed to obtain a working Gstreamer source, '
                              'video will be disabled.')
                    self._ui.video_input_combobox.set_sensitive(False)
                    return
                # Great, this succeeded, let’s store it back into the
                # config and use it. We’ve made autovideosrc the first
                # element in the combobox so we can pick index 0 without
                # worry.
                self._ui.video_input_combobox.set_active(0)
        else:
            if self.av_pipeline is not None:
                self.av_pipeline.set_state(Gst.State.NULL)
            if self.av_src is not None:
                self.av_pipeline.remove(self.av_src)
                self.av_src = None
            if self.av_sink is not None:
                self.av_pipeline.remove(self.av_sink)
                self.av_sink = None
            if self.av_widget is not None:
                self._ui.av_preview_box.remove(self.av_widget)
                self._ui.av_preview_placeholder.set_visible(True)
                self.av_widget = None
            self.av_pipeline = None

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
        app.settings.set('stun_server', widget.get_text())

    ### Advanced tab ###
    # Proxies
    def on_proxies_combobox_changed(self, widget):
        active = widget.get_active()
        if active == -1:
            return
        proxy = widget.get_model()[active][0]
        if proxy == _('No Proxy'):
            proxy = ''
        app.settings.set('global_proxy', proxy)

    def on_manage_proxies_button_clicked(self, _widget):
        app.app.activate_action('manage-proxies')

    def update_proxy_list(self):
        our_proxy = app.settings.get('global_proxy')
        if not our_proxy:
            our_proxy = _('No Proxy')
        model = self._ui.proxies_combobox.get_model()
        model.clear()
        proxies = app.settings.get_proxies()
        proxies.insert(0, _('No Proxy'))
        for index, proxy in enumerate(proxies):
            model.append([proxy])
            if our_proxy == proxy:
                self._ui.proxies_combobox.set_active(index)
        if our_proxy not in proxies:
            self._ui.proxies_combobox.set_active(0)

    # Log status changes of contacts
    def on_log_show_changes_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

    # Use system’s keyring
    def _on_use_keyring_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_keyring')

    # Enable debug logging
    def on_enable_logging_toggled(self, widget):
        app.set_debug_mode(widget.get_active())

    def _on_debug_folder_clicked(self, _widget):
        open_file(configpaths.get('DEBUG'))

    def _on_update_check_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'check_for_update')

    def _on_reset_help_clicked(self, widget):
        widget.set_sensitive(False)
        helping_hints = [
            'start_chat',
        ]
        for hint in helping_hints:
            app.settings.set('show_help_%s' % hint, True)

    def on_open_advanced_editor_button_clicked(self, _widget):
        open_window('AdvancedConfig')
