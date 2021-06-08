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
import sys

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.helpers import open_file
from gajim.common.multimedia_helpers import AudioInputManager
from gajim.common.multimedia_helpers import AudioOutputManager
from gajim.common.multimedia_helpers import VideoInputManager

from gajim.gui.controls.base import BaseControl

from .const import Setting
from .const import SettingKind
from .const import SettingType
from .const import ControlType
from .emoji_chooser import emoji_chooser
from .settings import SettingsBox
from .settings import SettingsDialog
from .sidebar_switcher import SideBarSwitcher
from .video_preview import VideoPreview
from .util import get_available_iconsets
from .util import open_window
from .util import get_app_window
from .util import get_builder

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

log = logging.getLogger('gajim.gui.preferences')


class Preferences(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('PreferencesWindow')
        self.set_default_size(900, 650)
        self.set_resizable(True)
        self.set_title(_('Preferences'))

        self._ui = get_builder('preferences.ui')

        self._video_preview = None
        self._prefs = {}

        side_bar_switcher = SideBarSwitcher()
        side_bar_switcher.set_stack(self._ui.stack)
        self._ui.grid.attach(side_bar_switcher, 0, 0, 1, 1)

        self.add(self._ui.grid)

        self._check_emoji_theme()

        prefs = [
            ('window_behaviour', WindowBehaviour),
            ('contact_list', ContactList),
            ('chats', Chats),
            ('group_chats', GroupChats),
            ('file_preview', FilePreview),
            ('visual_notifications', VisualNotifications),
            ('sounds', Sounds),
            ('status_message', StatusMessage),
            ('automatic_status', AutomaticStatus),
            ('themes', Themes),
            ('emoji', Emoji),
            ('status_icon', StatusIcon),
            ('server', Server),
            ('audio', Audio),
            ('video', Video),
            ('miscellaneous', Miscellaneous),
            ('advanced', Advanced),
        ]

        self._add_prefs(prefs)
        self._add_video_preview()

        self._ui.audio_video_info_bar.set_revealed(not app.is_installed('AV'))

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()
        if sys.platform not in ('win32', 'darwin'):
            self._ui.emoji.hide()

    def get_ui(self):
        return self._ui

    def _add_prefs(self, prefs):
        for ui_name, klass in prefs:
            pref_box = getattr(self._ui, ui_name)
            if ui_name == 'video' and sys.platform == 'win32':
                continue

            pref = klass(self)
            pref_box.add(pref)
            self._prefs[ui_name] = pref

    def _add_video_preview(self):
        if sys.platform == 'win32':
            return
        self._video_preview = VideoPreview()
        self._ui.video.add(self._video_preview.widget)

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_video_preview(self):
        return self._video_preview

    @staticmethod
    def _on_features_clicked(_widget, _response):
        open_window('Features')

    def update_theme_list(self):
        self._prefs['themes'].update_theme_list()

    def update_proxy_list(self):
        self._prefs['miscellaneous'].update_proxy_list()

    @staticmethod
    def get_all_controls():
        for ctrl in app.interface.msg_win_mgr.get_controls():
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    @staticmethod
    def get_all_muc_controls():
        for ctrl in app.interface.msg_win_mgr.get_controls(
                ControlType.GROUPCHAT):
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    @staticmethod
    def _check_emoji_theme():
        # Ensure selected emoji theme is valid
        emoji_themes = helpers.get_available_emoticon_themes()
        settings_theme = app.settings.get('emoticons_theme')
        if settings_theme not in emoji_themes:
            app.settings.set('emoticons_theme', 'font')


class PreferenceBox(SettingsBox):
    def __init__(self, settings):
        SettingsBox.__init__(self, None)
        self.get_style_context().add_class('settings-border')
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_vexpand(False)
        self.set_valign(Gtk.Align.END)

        for setting in settings:
            self.add_setting(setting)
        self.update_states()


class WindowBehaviour(PreferenceBox):
    def __init__(self, *args):
        win_layout_items = {
            'never': _('Detached contact list with detached chats'),
            'always': _('Detached contact list with single chat'),
            'always_with_roster': _('Single window for everything'),
            'peracct': _('Detached contact list with chats grouped by account'),
            'pertype': _('Detached contact list with chats grouped by type'),
        }

        roster_on_startup_items = {
            'always': _('Always'),
            'never': _('Never'),
            'last_state': _('Restore last state'),
        }

        tab_position_items = {
            'top': _('Top'),
            'bottom': _('Bottom'),
            'left': _('Left'),
            'Right': _('Right'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Window Layout'),
                    SettingType.CONFIG,
                    'one_message_window',
                    props={'entries': win_layout_items},
                    callback=self._on_win_layout_changed),

            Setting(SettingKind.POPOVER,
                    _('Contact List on Startup'),
                    SettingType.CONFIG,
                    'show_roster_on_startup',
                    props={'entries': roster_on_startup_items},
                    desc=_('Show contact list when starting Gajim')),

            Setting(SettingKind.SWITCH,
                    _('Quit on Close'),
                    SettingType.CONFIG,
                    'quit_on_roster_x_button',
                    desc=_('Quit when closing contact list')),

            Setting(SettingKind.POPOVER,
                    _('Tab Position'),
                    SettingType.CONFIG,
                    'tabs_position',
                    props={'entries': tab_position_items},
                    desc=_('Placement of chat window tabs'),
                    callback=self._on_win_layout_changed),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_win_layout_changed(*args):
        app.interface.msg_win_mgr.reconfig()


class ContactList(PreferenceBox):
    def __init__(self, *args):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Merge Accounts'),
                    SettingType.CONFIG,
                    'mergeaccounts',
                    callback=self._on_merge_accounts),

            Setting(SettingKind.SWITCH,
                    _('Enable Metacontacts'),
                    SettingType.CONFIG,
                    'metacontacts_enabled'),

            Setting(SettingKind.SWITCH,
                    _('Show Avatars'),
                    SettingType.CONFIG,
                    'show_avatars_in_roster',
                    callback=self._on_show_avatar_in_roster_changed),

            Setting(SettingKind.SWITCH,
                    _('Show Status Message'),
                    SettingType.CONFIG,
                    'show_status_msgs_in_roster',
                    callback=self._on_show_status_in_roster),

            Setting(SettingKind.SWITCH,
                    _('Sort Contacts by Status'),
                    SettingType.CONFIG,
                    'sort_by_show_in_roster',
                    callback=self._on_sort_by_show_in_roster),

            Setting(SettingKind.SWITCH,
                    _('Show Mood'),
                    SettingType.CONFIG,
                    'show_mood_in_roster'),

            Setting(SettingKind.SWITCH,
                    _('Show Activity'),
                    SettingType.CONFIG,
                    'show_activity_in_roster'),

            Setting(SettingKind.SWITCH,
                    _('Show Tune'),
                    SettingType.CONFIG,
                    'show_tunes_in_roster'),

            Setting(SettingKind.SWITCH,
                    _('Show Location'),
                    SettingType.CONFIG,
                    'show_location_in_roster'),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_merge_accounts(*args):
        app.app.activate_action('merge')

    @staticmethod
    def _on_show_avatar_in_roster_changed(*args):
        app.interface.roster.setup_and_draw_roster()

    @staticmethod
    def _on_show_status_in_roster(*args):
        app.interface.roster.setup_and_draw_roster()
        controls = get_app_window('Preferences').get_all_muc_controls()
        for ctrl in controls:
            ctrl.roster.draw_contacts()

    @staticmethod
    def _on_sort_by_show_in_roster(*args):
        app.interface.roster.setup_and_draw_roster()


class Chats(PreferenceBox):
    def __init__(self, *args):

        speller_desc = None
        if not app.is_installed('GSPELL'):
            speller_desc = _('Needs gspell to be installed')

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Spell Checking'),
                    SettingType.CONFIG,
                    'use_speller',
                    desc=speller_desc,
                    enabled_func=self._speller_available,
                    callback=self._on_use_speller),

            Setting(SettingKind.SWITCH,
                    _('Message Receipts (✔)'),
                    SettingType.CONFIG,
                    'positive_184_ack',
                    desc=_('Add a checkmark to received messages')),

            Setting(SettingKind.SWITCH,
                    _('XHTML Formatting'),
                    SettingType.CONFIG,
                    'show_xhtml',
                    desc=_('Render XHTML styles (colors, etc.) of incoming '
                           'messages')),

            Setting(SettingKind.SWITCH,
                    _('Show Send Message Button'),
                    SettingType.CONFIG,
                    'show_send_message_button'),

            Setting(SettingKind.SWITCH,
                    _('Show Status Message'),
                    SettingType.CONFIG,
                    'print_status_in_chats'),

            Setting(SettingKind.SWITCH,
                    _('Show Chat State In Tabs'),
                    SettingType.CONFIG,
                    'show_chatstate_in_tabs',
                    desc=_('Show the contact’s chat state (e.g. typing) in '
                           'the chat’s tab')),

            Setting(SettingKind.SWITCH,
                    _('Show Chat State In Banner'),
                    SettingType.CONFIG,
                    'show_chatstate_in_banner',
                    desc=_('Show the contact’s chat state (e.g. typing) in '
                           'the chats tab’s banner')),

            Setting(SettingKind.SWITCH,
                    _('Display Chat State In Contact List'),
                    SettingType.CONFIG,
                    'show_chatstate_in_roster',
                    desc=_('Show the contact’s chat state (e.g. typing) in '
                           'the contact list')),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _speller_available():
        return app.is_installed('GSPELL')

    @staticmethod
    def _on_use_speller(value, *args):
        if not value:
            return

        lang = app.settings.get('speller_language')
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        app.settings.set('speller_language', gspell_lang.get_code())
        for ctrl in get_app_window('Preferences').get_all_controls():
            if isinstance(ctrl, BaseControl):
                ctrl.set_speller()


class GroupChats(PreferenceBox):
    def __init__(self, *args):

        settings = [

            Setting(SettingKind.SWITCH,
                    _('Show Subject'),
                    SettingType.CONFIG,
                    'show_subject_on_join'),

            Setting(SettingKind.SWITCH,
                    _('Sort Contacts by Status'),
                    SettingType.CONFIG,
                    'sort_by_show_in_muc',
                    callback=self._on_sort_by_show_in_muc),

            Setting(SettingKind.POPOVER,
                    _('Default Sync Threshold'),
                    SettingType.CONFIG,
                    'gc_sync_threshold_public_default',
                    desc=_('Default for new public group chats'),
                    props={'entries': THRESHOLD_OPTIONS}),

            Setting(SettingKind.SWITCH,
                    _('Direct Messages'),
                    SettingType.CONFIG,
                    'muc_prefer_direct_msg',
                    desc=_('Prefer direct messages in private group chats ')),

            Setting(SettingKind.SWITCH,
                    _('Show Joined / Left'),
                    SettingType.CONFIG,
                    'gc_print_join_left_default',
                    desc=_('Default for new group chats'),
                    props={'button-text':_('Reset'),
                           'button-tooltip': _('Reset all group chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_join_left}),

            Setting(SettingKind.SWITCH,
                    _('Show Status Changes'),
                    SettingType.CONFIG,
                    'gc_print_status_default',
                    desc=_('Default for new group chats'),
                    props={'button-text':_('Reset'),
                           'button-tooltip': _('Reset all group chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_print_status}),

        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_sort_by_show_in_muc(*args):
        for ctrl in get_app_window('Preferences').get_all_muc_controls():
            ctrl.roster.invalidate_sort()

    @staticmethod
    def _reset_join_left(button):
        button.set_sensitive(False)
        app.settings.set_group_chat_settings('print_join_left', None)

    @staticmethod
    def _reset_print_status(button):
        button.set_sensitive(False)
        app.settings.set_group_chat_settings('print_status', None)


class FilePreview(PreferenceBox):
    def __init__(self, *args):
        sizes = {
            262144: '256 KiB',
            524288: '512 KiB',
            1048576: '1 MiB',
            5242880: '5 MiB',
            10485760: '10 MiB',
        }

        actions = {
            'open': _('Open'),
            'save_as': _('Save As…'),
            'open_folder': _('Open Folder'),
            'copy_link_location': _('Copy Link Location'),
            'open_link_in_browser': _('Open Link in Browser'),
        }

        settings = [
            Setting(SettingKind.SPIN,
                    _('Preview Size'),
                    SettingType.CONFIG,
                    'preview_size',
                    desc=_('Size of preview image'),
                    props={'range_': (100, 1000)}),

            Setting(SettingKind.POPOVER,
                    _('Allowed File Size'),
                    SettingType.CONFIG,
                    'preview_max_file_size',
                    desc=_('Maximum file size for preview generation'),
                    props={'entries': sizes}),

            Setting(SettingKind.SWITCH,
                    _('Preview in Public Group Chats'),
                    SettingType.CONFIG,
                    'preview_anonymous_muc',
                    desc=_('Generate preview automatically in public '
                           'group chats (may disclose your data)')),

            Setting(SettingKind.SWITCH,
                    _('Preview all Image URLs'),
                    SettingType.CONFIG,
                    'preview_allow_all_images',
                    desc=_('Generate preview for any URLs containing images '
                           '(may be unsafe)')),

            Setting(SettingKind.POPOVER,
                    _('Left Click Action'),
                    SettingType.CONFIG,
                    'preview_leftclick_action',
                    desc=_('Action when left-clicking a preview'),
                    props={'entries': actions}),

            Setting(SettingKind.SWITCH,
                    _('HTTPS Verification'),
                    SettingType.CONFIG,
                    'preview_verify_https',
                    desc=_('Whether to check for a valid certificate')),
        ]

        PreferenceBox.__init__(self, settings)


class VisualNotifications(PreferenceBox):
    def __init__(self, *args):
        trayicon_items = {
            'never': _('Hide icon'),
            'on_event': _('Only show for pending events'),
            'always': _('Always show icon'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Notification Area Icon'),
                    SettingType.CONFIG,
                    'trayicon',
                    props={'entries': trayicon_items},
                    callback=self._on_trayicon),

            Setting(SettingKind.SWITCH,
                    _('Open Events'),
                    SettingType.CONFIG,
                    'autopopup',
                    desc=_('Open events instead of showing a notification '
                           'in the contact list')),

            Setting(SettingKind.NOTIFICATIONS,
                    _('Show Notifications'),
                    SettingType.DIALOG,
                    props={'dialog': NotificationsDialog}),

        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_trayicon(value, *args):
        if value == 'never':
            app.interface.hide_systray()
        elif value == 'on_event':
            app.interface.show_systray()
        else:
            app.interface.show_systray()


class NotificationsDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Show Notifications'),
                    SettingType.CONFIG,
                    'show_notifications'),

            Setting(SettingKind.SWITCH,
                    _('Notifications When Away'),
                    SettingType.CONFIG,
                    'autopopupaway',
                    desc=_('Show notifications even if you are Away, '
                           'Busy, etc.'),
                    bind='show_notifications'),
            ]

        SettingsDialog.__init__(self, parent, _('Notifications'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Sounds(PreferenceBox):
    def __init__(self, *args):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Play Sounds'),
                    SettingType.CONFIG,
                    'sounds_on',
                    desc=_('Play sounds to notify about events'),
                    props={'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_manage_sounds}),

            Setting(SettingKind.SWITCH,
                    _('Sounds When Away'),
                    SettingType.CONFIG,
                    'sounddnd',
                    desc=_('Play sounds even when you are Away, Busy, etc.'),
                    bind='sounds_on'),
        ]

        PreferenceBox.__init__(self, settings)

    def _on_manage_sounds(self, *args):
        open_window('ManageSounds', transient_for=self.get_toplevel())


class StatusMessage(PreferenceBox):
    def __init__(self, *args):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Sign In'),
                    SettingType.CONFIG,
                    'ask_online_status'),

            Setting(SettingKind.SWITCH,
                    _('Sign Out'),
                    SettingType.CONFIG,
                    'ask_offline_status'),

            Setting(SettingKind.SWITCH,
                    _('Status Change'),
                    SettingType.CONFIG,
                    'always_ask_for_status_message'),
        ]

        PreferenceBox.__init__(self, settings)


class AutomaticStatus(PreferenceBox):
    def __init__(self, *args):

        settings = [
            Setting(SettingKind.AUTO_AWAY,
                    _('Auto Away'),
                    SettingType.DIALOG,
                    desc=_('Change your status to \'Away\' after a certain '
                           'amount of time'),
                    props={'dialog': AutoAwayDialog}),

            Setting(SettingKind.AUTO_EXTENDED_AWAY,
                    _('Auto Not Available'),
                    SettingType.DIALOG,
                    desc=_('Change your status to \'Not Available\' after a '
                           'certain amount of time'),
                    props={'dialog': AutoExtendedAwayDialog}),

        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_auto_away():
        return app.settings.get('autoaway')

    @staticmethod
    def _get_auto_xa():
        return app.settings.get('autoxa')


class AutoAwayDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Auto Away'),
                    SettingType.CONFIG,
                    'autoaway'),

            Setting(SettingKind.SPIN,
                    _('Time Until Away'),
                    SettingType.CONFIG,
                    'autoawaytime',
                    desc=_('Minutes until your status gets changed'),
                    props={'range_': (1, 720)},
                    bind='autoaway'),

            Setting(SettingKind.ENTRY,
                    _('Status Message'),
                    SettingType.CONFIG,
                    'autoaway_message',
                    bind='autoaway'),
            ]

        SettingsDialog.__init__(self, parent, _('Auto Away Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class AutoExtendedAwayDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Auto Not Available'),
                    SettingType.CONFIG,
                    'autoxa'),

            Setting(SettingKind.SPIN,
                    _('Time Until Not Available'),
                    SettingType.CONFIG,
                    'autoxatime',
                    desc=_('Minutes until your status gets changed'),
                    props={'range_': (1, 720)},
                    bind='autoxa'),

            Setting(SettingKind.ENTRY,
                    _('Status Message'),
                    SettingType.CONFIG,
                    'autoxa_message',
                    bind='autoxa'),
            ]

        SettingsDialog.__init__(self, parent, _('Auto Extended Away Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Themes(PreferenceBox):
    def __init__(self, *args):

        theme_items = self._get_theme_items()

        dark_theme_items = {
            0: _('Disabled'),
            1: _('Enabled'),
            2: _('System'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Dark Theme'),
                    SettingType.CONFIG,
                    'dark_theme',
                    props={'entries': dark_theme_items},
                    callback=self._on_dark_theme),

            Setting(SettingKind.POPOVER,
                    _('Theme'),
                    SettingType.CONFIG,
                    'roster_theme',
                    name='roster_theme',
                    props={'entries': theme_items,
                           'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_edit_themes},
                    callback=self._on_theme_changed),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_theme_items():
        theme_items = ['default']
        for settings_theme in app.css_config.themes:
            theme_items.append(settings_theme)
        return theme_items

    def update_theme_list(self):
        self.get_setting('roster_theme').update_entries(self._get_theme_items())

    def _on_edit_themes(self, *args):
        open_window('Themes', transient=self.get_toplevel())

    @staticmethod
    def _on_theme_changed(value, *args):
        app.css_config.change_theme(value)
        app.nec.push_incoming_event(NetworkEvent('theme-update'))
        app.nec.push_incoming_event(NetworkEvent('style-changed'))
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)

    @staticmethod
    def _on_dark_theme(value, *args):
        app.css_config.set_dark_theme(int(value))
        app.nec.push_incoming_event(NetworkEvent('style-changed'))


class Emoji(PreferenceBox):
    def __init__(self, *args):
        if sys.platform not in ('win32', 'darwin'):
            PreferenceBox.__init__(self, [])
            return

        emoji_themes_items = []
        for theme in helpers.get_available_emoticon_themes():
            emoji_themes_items.append(theme)

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Emoji Theme'),
                    SettingType.CONFIG,
                    'emoticons_theme',
                    desc=_('Choose from various emoji styles'),
                    props={'entries': emoji_themes_items},
                    callback=self._on_emoticons_theme)
        ]

        PreferenceBox.__init__(self, settings)

    def _on_emoticons_theme(self, *args):
        emoji_chooser.load()
        self._toggle_emoticons()

    @staticmethod
    def _toggle_emoticons():
        controls = get_app_window('Preferences').get_all_controls()
        for ctrl in controls:
            ctrl.toggle_emoticons()


class StatusIcon(PreferenceBox):
    def __init__(self, *args):

        iconset_items = []
        for _index, iconset_name in enumerate(get_available_iconsets()):
            iconset_items.append(iconset_name)

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Status Icon Set'),
                    SettingType.CONFIG,
                    'iconset',
                    props={'entries': iconset_items},
                    callback=self._on_iconset_changed),

            Setting(SettingKind.SWITCH,
                    _('Use Transport Icons'),
                    SettingType.CONFIG,
                    'use_transports_iconsets',
                    desc=_('Display protocol-specific status icons '
                           '(ICQ, ..)')),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_iconset_changed(*args):
        app.interface.roster.update_icons()


class Server(PreferenceBox):
    def __init__(self, *args):

        settings = [

            Setting(SettingKind.USE_STUN_SERVER,
                    _('Use STUN Server'),
                    SettingType.DIALOG,
                    desc=_('Helps to establish calls through firewalls'),
                    props={'dialog': StunServerDialog}),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(app.is_installed('AV'))


class StunServerDialog(SettingsDialog):
    def __init__(self, account, parent):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Use STUN Server'),
                    SettingType.CONFIG,
                    'use_stun_server'),

            Setting(SettingKind.ENTRY,
                    _('STUN Server'),
                    SettingType.CONFIG,
                    'stun_server',
                    bind='use_stun_server')
            ]

        SettingsDialog.__init__(self, parent, _('STUN Server Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Audio(PreferenceBox):
    def __init__(self, *args):

        deps_installed = app.is_installed('AV')

        audio_input_devices = {}
        audio_output_devices = {}
        if deps_installed:
            audio_input_devices = AudioInputManager().get_devices()
            audio_output_devices = AudioOutputManager().get_devices()

        audio_input_items = self._create_av_combo_items(audio_input_devices)
        audio_output_items = self._create_av_combo_items(audio_output_devices)

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Audio Input Device'),
                    SettingType.CONFIG,
                    'audio_input_device',
                    desc=_('Select your audio input (e.g. microphone)'),
                    props={'entries': audio_input_items}),

            Setting(SettingKind.POPOVER,
                    _('Audio Output Device'),
                    SettingType.CONFIG,
                    'audio_output_device',
                    desc=_('Select an audio output (e.g. speakers, '
                           'headphones)'),
                    props={'entries': audio_output_items}),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(deps_installed)

    @staticmethod
    def _create_av_combo_items(items_dict):
        items = enumerate(sorted(
            items_dict.items(),
            key=lambda x: '' if x[1].startswith('auto') else x[0].lower()))
        combo_items = {}
        for _index, (name, value) in items:
            combo_items[value] = name
        return combo_items


class Video(PreferenceBox):
    def __init__(self, *args):

        deps_installed = app.is_installed('AV')

        video_input_devices = {}
        if deps_installed:
            video_input_devices = VideoInputManager().get_devices()

        video_input_items = self._create_av_combo_items(video_input_devices)

        video_framerates = {
            '': _('Default'),
            '15/1': '15 fps',
            '10/1': '10 fps',
            '5/1': '5 fps',
            '5/2': '2.5 fps',
        }

        video_sizes = {
            '': _('Default'),
            '800x600': '800x600',
            '640x480': '640x480',
            '320x240': '320x240',
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Video Input Device'),
                    SettingType.CONFIG,
                    'video_input_device',
                    props={'entries': video_input_items},
                    desc=_('Select your video input device (e.g. webcam, '
                           'screen capture)'),
                    callback=self._on_video_input_changed),

            Setting(SettingKind.POPOVER,
                    _('Video Framerate'),
                    SettingType.CONFIG,
                    'video_framerate',
                    props={'entries': video_framerates}),

            Setting(SettingKind.POPOVER,
                    _('Video Resolution'),
                    SettingType.CONFIG,
                    'video_size',
                    props={'entries': video_sizes}),

            Setting(SettingKind.SWITCH,
                    _('Show My Video Stream'),
                    SettingType.CONFIG,
                    'video_see_self',
                    desc=_('Show your own video stream in calls')),

            Setting(SettingKind.SWITCH,
                    _('Live Preview'),
                    SettingType.VALUE,
                    desc=_('Show a live preview to test your video source'),
                    callback=self._toggle_live_preview),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(deps_installed)

    @staticmethod
    def _on_video_input_changed(value, *args):
        preview = get_app_window('Preferences').get_video_preview()
        if preview is None or not preview.is_active:
            # changed signal gets triggered when we fill the combobox
            return
        preview.refresh()

    @staticmethod
    def _toggle_live_preview(value, *args):
        preview = get_app_window('Preferences').get_video_preview()
        preview.toggle_preview(value)

    @staticmethod
    def _create_av_combo_items(items_dict):
        items = enumerate(sorted(
            items_dict.items(),
            key=lambda x: '' if x[1].startswith('auto') else x[0].lower()))
        combo_items = {}
        for _index, (name, value) in items:
            combo_items[value] = name
        return combo_items


class Miscellaneous(PreferenceBox):
    def __init__(self, pref_window):
        self._hints_list = [
            'start_chat',
        ]

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Global Proxy'),
                    SettingType.CONFIG,
                    'global_proxy',
                    name='global_proxy',
                    props={'entries': self._get_proxies(),
                           'default-text': _('System'),
                           'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_proxy_edit}),

            Setting(SettingKind.SWITCH,
                    _('Use System Keyring'),
                    SettingType.CONFIG,
                    'use_keyring',
                    desc=_('Use your system’s keyring to store passwords')),
        ]

        if sys.platform in ('win32', 'darwin'):
            settings.append(
                Setting(SettingKind.SWITCH,
                        _('Check For Updates'),
                        SettingType.CONFIG,
                        'check_for_update',
                        desc=_('Check for Gajim updates periodically')))

        PreferenceBox.__init__(self, settings)

        reset_button = pref_window.get_ui().reset_button
        reset_button.connect('clicked', self._on_reset_hints)
        reset_button.set_sensitive(self._check_hints_reset)

    @staticmethod
    def _get_proxies():
        return {proxy: proxy for proxy in app.settings.get_proxies()}

    @staticmethod
    def _on_proxy_edit(*args):
        open_window('ManageProxies')

    def update_proxy_list(self):
        self.get_setting('global_proxy').update_entries(self._get_proxies())

    def _check_hints_reset(self):
        for hint in self._hints_list:
            if app.settings.get('show_help_%s' % hint) is False:
                return True
        return False

    def _on_reset_hints(self, button):
        for hint in self._hints_list:
            app.settings.set('show_help_%s' % hint, True)
        button.set_sensitive(False)


class Advanced(PreferenceBox):
    def __init__(self, pref_window):

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Debug Logging'),
                    SettingType.VALUE,
                    app.get_debug_mode(),
                    props={'button-icon-name': 'folder-symbolic',
                           'button-callback': self._on_open_debug_logs},
                    callback=self._on_debug_logging),
        ]

        PreferenceBox.__init__(self, settings)

        pref_window.get_ui().ace_button.connect(
            'clicked', self._on_advanced_config_editor)

    @staticmethod
    def _on_debug_logging(value, *args):
        app.set_debug_mode(value)

    @staticmethod
    def _on_open_debug_logs(*args):
        open_file(configpaths.get('DEBUG'))

    @staticmethod
    def _on_advanced_config_editor(*args):
        open_window('AdvancedConfig')
