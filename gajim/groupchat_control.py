# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Marcin Mielniczuk <marmistrz dot dev at zoho dot eu>
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

import time
import logging

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import validate_resourcepart
from nbxmpp.const import StatusCode
from nbxmpp.const import Affiliation
from nbxmpp.errors import StanzaError
from nbxmpp.modules.vcard_temp import VCard

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio

from gajim import gtkgui_helpers
from gajim import gui_menu_builder

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.common.helpers import event_filter
from gajim.common.helpers import to_user_string
from gajim.common.const import AvatarSize

from gajim.common.i18n import _
from gajim.common.const import MUCJoinedState
from gajim.common.structs import OutgoingMessage

from gajim.chat_control_base import ChatControlBase

from gajim.command_system.implementation.hosts import GroupChatCommands

from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationCheckDialog
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.filechoosers import AvatarChooserDialog
from gajim.gui.groupchat_config import GroupchatConfig
from gajim.gui.adhoc import AdHocCommand
from gajim.gui.avatar_selector import AvatarSelector
from gajim.gui.dataform import DataFormWidget
from gajim.gui.groupchat_info import GroupChatInfoScrolled
from gajim.gui.groupchat_invite import GroupChatInvite
from gajim.gui.groupchat_settings import GroupChatSettings
from gajim.gui.groupchat_roster import GroupchatRoster
from gajim.gui.groupchat_state import GroupchatState
from gajim.gui.util import NickCompletionGenerator
from gajim.gui.util import get_app_window
from gajim.gui.util import open_window
from gajim.gui.const import ControlType

log = logging.getLogger('gajim.groupchat_control')


class GroupchatControl(ChatControlBase):

    _type = ControlType.GROUPCHAT

    # Set a command host to bound to. Every command given through a group chat
    # will be processed with this command host.
    COMMAND_HOST = GroupChatCommands

    def __init__(self, parent_win, jid, muc_data, acct):
        ChatControlBase.__init__(self,
                                 parent_win,
                                 'groupchat_control',
                                 jid,
                                 acct)

        self._client.connect_signal('state-changed',
                                    self._on_client_state_changed)

        self.force_non_minimizable = False
        self.is_anonymous = True

        self.toggle_emoticons()

        self.room_jid = str(self.contact.jid)

        # Stores nickname we want to kick
        self._kick_nick = None

        # Stores nickname we want to ban
        self._ban_jid = None

        # Last sent message text
        self.last_sent_txt = ''

        # Attribute, encryption plugins use to signal the message can be sent
        self.sendmessage = False

        self.roster = GroupchatRoster(self.account, self.room_jid, self)
        self.xml.roster_revealer.add(self.roster)
        self.roster.connect('row-activated', self._on_roster_row_activated)

        if parent_win is not None:
            self.add_actions()
            GLib.idle_add(self.update_actions)
            self.scale_factor = parent_win.window.get_scale_factor()
        else:
            self.scale_factor = app.interface.roster.scale_factor

        if not app.settings.get('hide_groupchat_banner'):
            self.xml.banner_eventbox.set_no_show_all(False)

        # muc attention flag (when we are mentioned in a muc)
        # if True, the room has mentioned us
        self.attention_flag = False

        # True if we initiated room destruction
        self._wait_for_destruction = False

        # sorted list of nicks who mentioned us (last at the end)
        self.attention_list = []
        self.nick_hits = []
        self.__nick_completion = None
        self.last_key_tabs = False

        self.setup_seclabel()

        # Send file
        self.xml.sendfile_button.set_action_name(
            'win.send-file-%s' % self.control_id)

        # Encryption
        self.set_lock_image()

        self.xml.encryption_menu.set_menu_model(
            gui_menu_builder.get_encryption_menu(self.control_id, self._type))
        self.set_encryption_menu_icon()

        # Banner
        self.hide_roster_button = Gtk.Button.new_from_icon_name(
            'go-previous-symbolic', Gtk.IconSize.MENU)
        self.hide_roster_button.set_valign(Gtk.Align.CENTER)
        self.hide_roster_button.connect('clicked',
                                        lambda *args: self.show_roster())
        self.xml.banner_actionbar.pack_end(self.hide_roster_button)

        self._update_avatar()

        # Holds CaptchaRequest widget
        self._captcha_request = None

        # MUC Info
        self._subject_data = None
        self._muc_info_box = GroupChatInfoScrolled(self.account, {'width': 600})
        self.xml.info_box.add(self._muc_info_box)

        # Groupchat settings
        self._groupchat_settings_box = None

        # Holds the room’s config form, which is requested when managing
        # the room
        self._room_config_form = None

        # Groupchat invite
        self.xml.quick_invite_button.set_action_name(
            'win.invite-%s' % self.control_id)

        self._invite_box = GroupChatInvite(self.room_jid)
        self.xml.invite_grid.attach(self._invite_box, 0, 0, 1, 1)
        self._invite_box.connect('listbox-changed', self._on_invite_ready)

        # Avatar selector
        self._avatar_selector = AvatarSelector()
        self._avatar_selector.set_size_request(400, 400)
        self.xml.avatar_selector_grid.attach(self._avatar_selector, 0, 1, 1, 1)

        self.control_menu = gui_menu_builder.get_groupchat_menu(self.control_id,
                                                                self.account,
                                                                self.room_jid)

        self.xml.settings_menu.set_menu_model(self.control_menu)

        app.settings.connect_signal('gc_print_join_left_default',
                                    self.update_actions)
        app.settings.connect_signal('gc_print_status_default',
                                    self.update_actions)

        self.register_events([
            ('bookmarks-received', ged.GUI1, self._on_bookmarks_received),
        ])

        self._set_control_inactive()

        self._groupchat_state = GroupchatState()
        self._groupchat_state.connect('join-clicked',
                                      self._on_groupchat_state_join_clicked)
        self._groupchat_state.connect('abort-clicked',
                                      self._on_groupchat_state_abort_clicked)
        self.xml.conv_view_overlay.add_overlay(self._groupchat_state)

        # Stack
        self.xml.stack.show_all()
        self.xml.stack.set_visible_child_name('groupchat')

        self.update_ui()
        self.widget.show_all()

        # PluginSystem: adding GUI extension point for this GroupchatControl
        # instance object
        app.plugin_manager.gui_extension_point('groupchat_control', self)

    def _connect_contact_signals(self):
        self.contact.multi_connect({
            'state-changed': self._on_muc_state_changed,
            'avatar-update': self._on_avatar_update,
            'user-joined': self._on_user_joined,
            'user-left': self._on_user_left,
            'user-affiliation-changed': self._on_user_affiliation_changed,
            'user-role-changed': self._on_user_role_changed,
            'user-status-show-changed': self._on_user_status_show_changed,
            'user-nickname-changed': self._on_user_nickname_changed,
            'room-kicked': self._on_room_kicked,
            'room-destroyed': self._on_room_destroyed,
            'room-config-finished': self._on_room_config_finished,
            'room-config-failed': self._on_room_config_failed,
            'room-config-changed': self._on_room_config_changed,
            'room-password-required': self._on_room_password_required,
            'room-creation-failed': self._on_room_creation_failed,
            'room-presence-error': self._on_room_presence_error,
            'room-voice-request': self._on_room_voice_request,
            'room-captcha-challenge': self._on_room_captcha_challenge,
            'room-captcha-error': self._on_room_captcha_error,
            'room-subject': self._on_room_subject,
            'room-joined': self._on_room_joined,
            'room-join-failed': self._on_room_join_failed,
        })

    def _on_muc_state_changed(self, _contact, _signal_name):
        state = self.contact.state
        if state == MUCJoinedState.JOINING:
            self._groupchat_state.set_joining()

        if state == MUCJoinedState.JOINED:
            self._set_control_active()
            self.show_roster()
            self._groupchat_state.set_joined()

        elif state == MUCJoinedState.NOT_JOINED:
            self._set_control_inactive()

    def _on_client_state_changed(self, _client, _signal_name, state):
        pass

    @property
    def _muc_data(self):
        return self._client.get_module('MUC').get_muc_data(self.room_jid)

    @property
    def _nick_completion(self):
        if self.__nick_completion is None:
            self.__nick_completion = NickCompletionGenerator(self._muc_data.nick)
        return self.__nick_completion

    @property
    def nick(self):
        return self._muc_data.nick

    @property
    def subject(self):
        if self._subject_data is None:
            return ''
        return self._subject_data.subject

    @property
    def room_name(self):
        return self.contact.get_shown_name()

    @property
    def disco_info(self):
        return app.storage.cache.get_last_disco_info(self.contact.jid)

    def add_actions(self):
        super().add_actions()
        actions = [
            ('groupchat-settings-', None, self._on_groupchat_settings),
            ('groupchat-manage-', None, self._on_groupchat_manage),
            ('rename-groupchat-', None, self._on_rename_groupchat),
            ('change-nickname-', None, self._on_change_nick),
            ('destroy-', None, self._on_destroy_room),
            ('configure-', None, self._on_configure_room),
            ('request-voice-', None, self._on_request_voice),
            ('information-', None, self._on_information),
            ('invite-', None, self._on_invite),
            ('contact-information-', 's', self._on_contact_information),
            ('execute-command-', 's', self._on_execute_command),
            ('ban-', 's', self._on_ban),
            ('kick-', 's', self._on_kick),
            ('change-role-', 'as', self._on_change_role),
            ('change-affiliation-', 'as', self._on_change_affiliation),
        ]

        for action in actions:
            action_name, variant, func = action
            if variant is not None:
                variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name + self.control_id, variant)
            act.connect("activate", func)
            self.parent_win.window.add_action(act)

    def update_actions(self, *args):
        if self._muc_data is None:
            return

        contact = self.contact.get_resource(self.nick)

        self._get_action('request-voice-').set_enabled(
            self.is_connected and contact.role.is_visitor)

        # Change Nick
        self._get_action('change-nickname-').set_enabled(self.is_connected)

        # Execute command
        self._get_action('execute-command-').set_enabled(self.is_connected)

        # Send message
        has_text = self.msg_textview.has_text()
        self._get_action('send-message-').set_enabled(
            self.is_connected and has_text)

        # Send file (HTTP File Upload)
        httpupload = self._get_action(
            'send-file-httpupload-')
        httpupload.set_enabled(self.is_connected and
                               self._client.get_module('HTTPUpload').available)
        self._get_action('send-file-').set_enabled(httpupload.get_enabled())

        if self.is_connected and httpupload.get_enabled():
            tooltip_text = _('Send File…')
            max_file_size = self._client.get_module('HTTPUpload').max_file_size
            if max_file_size is not None:
                max_file_size = max_file_size / (1024 * 1024)
                tooltip_text = _('Send File (max. %s MiB)…') % max_file_size
        else:
            tooltip_text = _('No File Transfer available')
        self.xml.sendfile_button.set_tooltip_text(tooltip_text)

        # Manage chat
        self._get_action('groupchat-manage-').set_enabled(
            self.is_connected and contact.affiliation in (Affiliation.ADMIN,
                                                          Affiliation.OWNER))

        vcard_support = False
        if self.disco_info is not None:
            vcard_support = self.disco_info.supports(Namespace.VCARD)
            self.xml.muc_name_entry.set_text(self.disco_info.muc_name or '')
            self.xml.muc_description_entry.set_text(
                self.disco_info.muc_description or '')

        if (self.is_connected and vcard_support and
                contact.affiliation.is_owner):
            self.xml.avatar_select_button.show()

        self.xml.manage_change_subject_button.set_sensitive(
            self.is_connected and self._is_subject_change_allowed())

        self.xml.manage_advanced_button.set_sensitive(
            self.is_connected and contact.affiliation in (Affiliation.ADMIN,
                                                          Affiliation.OWNER))

        self.xml.manage_destroy_button.set_sensitive(
            self.is_connected and contact.affiliation.is_owner)

        self._get_action('contact-information-').set_enabled(self.is_connected)

        self._get_action('execute-command-').set_enabled(self.is_connected)

        self._get_action('ban-').set_enabled(self.is_connected)

        self._get_action('kick-').set_enabled(self.is_connected)

    def remove_actions(self):
        super().remove_actions()
        actions = [
            'groupchat-settings-',
            'groupchat-manage-',
            'rename-groupchat-',
            'change-nickname-',
            'disconnect-',
            'request-voice-',
            'information-',
            'invite-',
            'contact-information-',
            'execute-command-',
            'ban-',
            'kick-',
            'change-role-',
            'change-affiliation-',
        ]

        for action in actions:
            self.parent_win.window.remove_action(f'{action}{self.control_id}')

    def _is_subject_change_allowed(self):
        contact = self.contact.get_resource(self.nick)
        if contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
            return True

        if self.disco_info is None:
            return False
        return self.disco_info.muc_subjectmod or False

    def _get_action(self, name):
        win = self.parent_win.window
        return win.lookup_action(name + self.control_id)

    def _show_page(self, name):
        transition = Gtk.StackTransitionType.SLIDE_DOWN
        if name == 'groupchat':
            transition = Gtk.StackTransitionType.SLIDE_UP
            self.msg_textview.grab_focus()
        if name == 'muc-info':
            # Set focus on the close button, otherwise one of
            # the selectable labels of the GroupchatInfo box gets focus,
            # which means it is fully selected
            self.xml.info_close_button.grab_focus()
        self.xml.stack.set_visible_child_full(name, transition)

    def _get_current_page(self):
        return self.xml.stack.get_visible_child_name()

    def _on_muc_disco_update(self, _event):
        self.update_actions()
        self.draw_banner_text()

    # Actions
    def _on_information(self, _action, _param):
        self._muc_info_box.set_from_disco_info(self.disco_info)
        if self._subject_data is not None:
            self._muc_info_box.set_subject(self._subject_data.subject)
            self._muc_info_box.set_author(self._subject_data.muc_nickname,
                                          self._subject_data.user_timestamp)
        self._show_page('muc-info')

    def _on_groupchat_settings(self, _action, _param):
        if self._groupchat_settings_box is not None:
            self.xml.settings_scrolled_box.remove(self._groupchat_settings_box)
            self._groupchat_settings_box.destroy()

        self._groupchat_settings_box = GroupChatSettings(
            self.account, self.room_jid)
        self._groupchat_settings_box.show_all()
        self.xml.settings_scrolled_box.add(self._groupchat_settings_box)
        self._show_page('muc-settings')

    def _on_groupchat_manage(self, _action, _param):
        surface = app.interface.avatar_storage.get_muc_surface(
            self.account,
            self.contact.jid,
            AvatarSize.GROUP_INFO,
            self.scale_factor)
        self.xml.avatar_button_image.set_from_surface(surface)

        self._show_page('muc-manage')
        self.xml.manage_save_button.grab_default()

        contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, self.nick)
        if contact.affiliation.is_owner:
            con = app.connections[self.account]
            con.get_module('MUC').request_config(
                self.room_jid, callback=self._on_manage_form_received)

    def _on_manage_form_received(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            log.info(error)
            return

        self.xml.muc_name_entry.set_sensitive(True)
        self.xml.muc_description_entry.set_sensitive(True)
        self.xml.manage_save_button.set_sensitive(True)
        self._room_config_form = result.form

    def _on_invite(self, _action, _param):
        self._invite_box.load_contacts()
        self._show_page('invite')

    def _on_invite_ready(self, _, invitable):
        self.xml.invite_button.set_sensitive(invitable)

    def _on_invite_clicked(self, _button):
        invitees = self._invite_box.get_invitees()
        for jid in invitees:
            self.invite(jid)
        self._show_page('groupchat')

    def invite(self, contact_jid):
        message_id = self._client.get_module('MUC').invite(
            self.room_jid, contact_jid)
        self.add_info_message(
            _('%s has been invited to this group chat') % contact_jid,
            message_id=message_id)

    def _on_destroy_room(self, _button):
        self.xml.destroy_reason_entry.grab_focus()
        self.xml.destroy_button.grab_default()
        self._show_page('destroy')

    def _on_destroy_alternate_changed(self, entry, _param):
        jid = entry.get_text()
        if jid:
            try:
                jid = helpers.validate_jid(jid)
            except Exception:
                icon = 'dialog-warning-symbolic'
                text = _('Invalid XMPP Address')
                self.xml.destroy_alternate_entry.set_icon_from_icon_name(
                    Gtk.EntryIconPosition.SECONDARY, icon)
                self.xml.destroy_alternate_entry.set_icon_tooltip_text(
                    Gtk.EntryIconPosition.SECONDARY, text)
                self.xml.destroy_button.set_sensitive(False)
                return
        self.xml.destroy_alternate_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, None)
        self.xml.destroy_button.set_sensitive(True)

    def _on_destroy_confirm(self, _button):
        reason = self.xml.destroy_reason_entry.get_text()
        jid = self.xml.destroy_alternate_entry.get_text()
        self._wait_for_destruction = True
        self._client.get_module('MUC').destroy(self.room_jid, reason, jid)
        self._show_page('groupchat')

    def _on_configure_room(self, _button):
        self.xml.manage_popover.popdown()

        win = get_app_window('GroupchatConfig', self.account, self.room_jid)
        if win is not None:
            win.present()
            return

        contact = self.contact.get_resource(self.nick)
        if contact.affiliation.is_owner:
            self._client.get_module('MUC').request_config(
                self.room_jid, callback=self._on_configure_form_received)

        elif contact.affiliation.is_admin:
            GroupchatConfig(self.account,
                            self.room_jid,
                            contact.affiliation.value)

    def _on_configure_form_received(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            log.info(error)
            return
        GroupchatConfig(self.account, result.jid, 'owner', result.form)

    def _on_request_voice(self, _action, _param):
        """
        Request voice in the current room
        """
        self._client.get_module('MUC').request_voice(self.room_jid)

    def _on_execute_command(self, _action, param):
        jid = self.room_jid
        nick = param.get_string()
        if nick:
            jid += '/' + nick
        AdHocCommand(self.account, jid)

    def _on_change_avatar(self, _button):
        def _on_accept(path):
            self._avatar_selector.prepare_crop_area(path)
            self.xml.avatar_update_button.set_sensitive(
                self._avatar_selector.get_prepared())
            self._show_page('avatar-selector')
            self.xml.avatar_update_button.grab_default()

        AvatarChooserDialog(_on_accept,
                            transient_for=self.parent_win.window,
                            modal=True)

    def _on_avatar_select_file_clicked(self, _button):
        def _on_accept(path):
            self._avatar_selector.prepare_crop_area(path)
            self.xml.avatar_update_button.set_sensitive(
                self._avatar_selector.get_prepared())

        AvatarChooserDialog(_on_accept,
                            transient_for=self.parent_win.window,
                            modal=True)

    def _on_upload_avatar_result(self, task):
        try:
            task.finish()
        except Exception as error:
            self.add_info_message(_('Avatar upload failed: %s') % error)

        else:
            self.add_info_message(_('Avatar upload successful'))

    def _on_avatar_update_clicked(self, _button):
        success, data, _, _ = self._avatar_selector.get_avatar_bytes()
        if not success:
            self.add_info_message(_('Loading avatar failed'))
            return

        sha = app.interface.avatar_storage.save_avatar(data)
        if sha is None:
            self.add_info_message(_('Loading avatar failed'))
            return

        vcard = VCard()
        vcard.set_avatar(data, 'image/png')

        client = app.get_client(self.account)
        client.get_module('VCardTemp').set_vcard(
            vcard,
            jid=self.room_jid,
            callback=self._on_upload_avatar_result)
        self._show_page('groupchat')

    def _on_contact_information(self, _action, param):
        nick = param.get_string()
        contact = self.contact.get_resource(nick)
        open_window('ContactInfo', account=self.account, contact=contact)

    def _on_kick(self, _action, param):
        nick = param.get_string()
        self._kick_nick = nick
        self.xml.kick_label.set_text(_('Kick %s') % nick)
        self.xml.kick_reason_entry.grab_focus()
        self.xml.kick_participant_button.grab_default()
        self._show_page('kick')

    def _on_ban(self, _action, param):
        jid = param.get_string()
        self._ban_jid = jid
        nick = app.get_nick_from_jid(jid)
        self.xml.ban_label.set_text(_('Ban %s') % nick)
        self.xml.ban_reason_entry.grab_focus()
        self.xml.ban_participant_button.grab_default()
        self._show_page('ban')

    def _on_change_role(self, _action, param):
        nick, role = param.get_strv()
        self._client.get_module('MUC').set_role(self.room_jid, nick, role)

    def _on_change_affiliation(self, _action, param):
        jid, affiliation = param.get_strv()
        self._client.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': affiliation}})

    def show_roster(self):
        show = not self.xml.roster_revealer.get_reveal_child()
        icon = 'go-next-symbolic' if show else 'go-previous-symbolic'
        image = self.hide_roster_button.get_image()
        image.set_from_icon_name(icon, Gtk.IconSize.MENU)

        transition = Gtk.RevealerTransitionType.SLIDE_RIGHT
        if show:
            transition = Gtk.RevealerTransitionType.SLIDE_LEFT
        self.xml.roster_revealer.set_transition_type(transition)
        self.xml.roster_revealer.set_reveal_child(show)

    def on_groupchat_maximize(self):
        self.roster.enable_tooltips()
        self.add_actions()
        self.update_actions()
        self.set_lock_image()
        self.draw_banner_text()
        type_ = ['printed_gc_msg', 'printed_marked_gc_msg']
        if not app.events.remove_events(self.account,
                                        self.get_full_jid(),
                                        types=type_):
            # XEP-0333 Send <displayed> marker
            self._client.get_module('ChatMarkers').send_displayed_marker(
                self.contact,
                self.last_msg_id,
                self._type)
            self.last_msg_id = None

    def _on_roster_row_activated(self, _roster, nick):
        muc_prefer_direct_msg = app.settings.get('muc_prefer_direct_msg')
        if not self.is_anonymous and muc_prefer_direct_msg:
            app.window.add_chat(self.account,
                                self.contact.jid,
                                'contact',
                                select=True)
        else:
            contact = self.contact.get_resource(nick)
            app.window.add_private_chat(self.account, contact.jid)

    def _on_avatar_update(self, _contact, _signal_name):
        self._update_avatar()

    def _update_avatar(self):
        surface = self.contact.get_avatar(AvatarSize.CHAT, self.scale_factor)
        self.xml.avatar_image.set_from_surface(surface)

    def draw_banner_text(self):
        """
        Draw the text in the fat line at the top of the window that houses the
        room jid
        """
        self.xml.banner_name_label.set_text(self.contact.name)

    def _on_update_gc_avatar(self, event):
        self.roster.process_avatar_update(event)

    def _on_bookmarks_received(self, _event):
        self.draw_banner_text()

    def _on_room_voice_request(self, _contact, _signal_name, properties):
        voice_request = properties.voice_request

        def on_approve():
            self._client.get_module('MUC').approve_voice_request(
                self.room_jid, voice_request)

        ConfirmationDialog(
            _('Voice Request'),
            _('Voice Request'),
            _('<b>%(nick)s</b> from <b>%(room_name)s</b> requests voice') % {
                'nick': voice_request.nick, 'room_name': self.room_name},
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Approve'),
                               callback=on_approve)],
            modal=False).show()

    def _on_mam_message_received(self, event):
        if not event.properties.type.is_groupchat:
            return
        if event.archive_jid != self.room_jid:
            return
        self.add_message(event.msgtxt,
                         contact=event.properties.muc_nickname,
                         tim=event.properties.mam.timestamp,
                         correct_id=event.correct_id,
                         message_id=event.properties.id,
                         additional_data=event.additional_data)

    def _on_gc_message_received(self, event):
        if event.properties.muc_nickname is None:
            # message from server
            self.add_message(event.msgtxt,
                             tim=event.properties.timestamp,
                             displaymarking=event.displaymarking,
                             additional_data=event.additional_data)
        else:
            if event.properties.muc_nickname == self.nick:
                self.last_sent_txt = event.msgtxt
            stanza_id = None
            if event.properties.stanza_id:
                stanza_id = event.properties.stanza_id.id
            self.add_message(event.msgtxt,
                             contact=event.properties.muc_nickname,
                             tim=event.properties.timestamp,
                             displaymarking=event.displaymarking,
                             correct_id=event.correct_id,
                             message_id=event.properties.id,
                             stanza_id=stanza_id,
                             additional_data=event.additional_data)
        event.needs_highlight = self.needs_visual_notification(event.msgtxt)

    def add_message(self, text, contact='', tim=None,
                    displaymarking=None, correct_id=None, message_id=None,
                    stanza_id=None, additional_data=None):
        """
        Add message to the ConversationsTextview

        If contact is set: it's a message from someone
        If contact is not set: it's a message from the server or help.
        """

        other_tags_for_name = []
        other_tags_for_text = []

        if not contact:
            # Message from the server
            kind = 'status'
        elif contact == self.nick: # it's us
            kind = 'outgoing'
        else:
            kind = 'incoming'
            # muc-specific chatstate
            if self.parent_win:
                self.parent_win.redraw_tab(self, 'newmsg')

        if kind == 'incoming': # it's a message NOT from us
            # highlighting and sounds
            highlight, _sound = self.highlighting_for_message(text, tim)
            other_tags_for_name.append('muc_nickname_color_%s' % contact)
            if highlight:
                # muc-specific chatstate
                if self.parent_win:
                    self.parent_win.redraw_tab(self, 'attention')
                else:
                    self.attention_flag = True
                other_tags_for_name.append('bold')
                other_tags_for_text.append('marked')

            self._nick_completion.record_message(contact, highlight)

            # self.check_focus_out_line()

        ChatControlBase.add_message(self,
                                    text,
                                    kind,
                                    contact,
                                    tim,
                                    other_tags_for_name,
                                    [],
                                    other_tags_for_text,
                                    displaymarking=displaymarking,
                                    correct_id=correct_id,
                                    message_id=message_id,
                                    stanza_id=stanza_id,
                                    additional_data=additional_data)

    def highlighting_for_message(self, text, tim):
        """
        Returns a 2-Tuple. The first says whether or not to highlight the text,
        the second, what sound to play
        """
        highlight, sound = None, None

        # notify = self.contact.can_notify()
        # TODO
        notify = False
        sound_enabled = app.settings.get_soundevent_settings(
            'muc_message_received')['enabled']

        # Are any of the defined highlighting words in the text?
        if self.needs_visual_notification(text):
            highlight = True
            sound_settings = app.settings.get_soundevent_settings(
                'muc_message_highlight')
            if sound_settings['enabled']:
                sound = 'highlight'

        # Do we play a sound on every muc message?
        elif notify and sound_enabled:
            sound = 'received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim is not None and time.mktime(time.localtime()) - tim > 1:
            sound = None

        return highlight, sound

    def check_focus_out_line(self):
        """
        Check and possibly add focus out line for room_jid if it needs it and
        does not already have it as last event. If it goes to add this line
        - remove previous line first
        """

        if app.window.is_chat_active(self.account, self.room_jid):
            return

        # self.conv_textview.show_focus_out_line()

    def needs_visual_notification(self, text):
        """
        Check text to see whether any of the words in (muc_highlight_words and
        nick) appear
        """
        special_words = app.settings.get('muc_highlight_words').split(';')
        special_words.append(self.nick)
        special_words.append(self._client.get_own_jid().bare)
        # Strip empties: ''.split(';') == [''] and would highlight everything.
        # Also lowercase everything for case insensitive compare.
        special_words = [word.lower() for word in special_words if word]
        text = text.lower()

        for special_word in special_words:
            found_here = text.find(special_word)
            while found_here > -1:
                end_here = found_here + len(special_word)
                if (found_here == 0 or not text[found_here - 1].isalpha()) and \
                (end_here == len(text) or not text[end_here].isalpha()):
                    # It is beginning of text or char before is not alpha AND
                    # it is end of text or char after is not alpha
                    return True
                # continue searching
                start = found_here + 1
                found_here = text.find(special_word, start)
        return False

    def _on_room_subject(self, _contact, _signal_name, properties):
        if self.subject == properties.subject:
            # Probably a rejoin, we already showed that subject
            return

        self._subject_data = properties

        text = _('%(nick)s has set the subject to %(subject)s') % {
            'nick': properties.muc_nickname, 'subject': properties.subject}

        if properties.user_timestamp:
            date = time.strftime('%c',
                                 time.localtime(properties.user_timestamp))
            text = '%s - %s' % (text, date)

        if (app.settings.get('show_subject_on_join') or
                self._muc_data.state != MUCJoinedState.JOINING):
            self.add_info_message(text)

    def _on_room_config_changed(self, _contact, _signal_name, properties):
        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify

        status_codes = properties.muc_status_codes

        changes = []
        if StatusCode.SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now shows unavailable members'))

        if StatusCode.NOT_SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now does not show '
                             'unavailable members'))

        if StatusCode.CONFIG_NON_PRIVACY_RELATED in status_codes:
            changes.append(_('A setting not related to privacy has been '
                             'changed'))
            self._client.get_module('Discovery').disco_muc(self.room_jid)

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            # Can be a presence (see chg_contact_status in groupchat_control.py)
            changes.append(_('Conversations are stored on the server'))

        if StatusCode.CONFIG_NO_ROOM_LOGGING in status_codes:
            changes.append(_('Conversations are not stored on the server'))

        if StatusCode.CONFIG_NON_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now non-anonymous'))
            self.is_anonymous = False

        if StatusCode.CONFIG_SEMI_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now semi-anonymous'))
            self.is_anonymous = True

        if StatusCode.CONFIG_FULL_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now fully anonymous'))
            self.is_anonymous = True

        for change in changes:
            self.add_info_message(change)

    @event_filter(['account'])
    def _nec_ping(self, event):
        if not event.contact.is_groupchat:
            return

        if self.contact.jid != event.contact.room_jid:
            return

        nick = event.contact.get_shown_name()
        if event.name == 'ping-sent':
            self.add_info_message(_('Ping? (%s)') % nick)
        elif event.name == 'ping-reply':
            self.add_info_message(
                _('Pong! (%(nick)s %(delay)s s.)') % {'nick': nick,
                                                      'delay': event.seconds})
        elif event.name == 'ping-error':
            self.add_info_message(event.error)

    @property
    def is_connected(self) -> bool:
        return app.gc_connected[self.account][self.room_jid]

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        app.gc_connected[self.account][self.room_jid] = value

    def _set_control_active(self):
        self.xml.formattings_button.set_sensitive(True)
        self.msg_textview.set_sensitive(True)
        self.msg_textview.set_editable(True)

        self.roster.initial_draw()

        self.is_connected = True

        self.xml.formattings_button.set_sensitive(True)

        self.conversation_view.update_avatars()

        self.update_actions()

    def _set_control_inactive(self):
        self.xml.formattings_button.set_sensitive(False)
        self.msg_textview.set_sensitive(False)
        self.msg_textview.set_editable(False)

        self.roster.enable_sort(False)
        self.roster.clear()

        self.is_connected = False

        self._client.get_module('Chatstate').remove_delay_timeout(self.contact)

        self.update_actions()

    def rejoin(self):
        self._client.get_module('MUC').join(self.room_jid)

    # def send_pm(self, nick, message=None):
    #     ctrl = self._start_private_message(nick)
    #     if message is not None:
    #         ctrl.send_message(message)

    def _on_user_joined(self, _contact, _signal_name, user_contact, properties):
        nick = user_contact.name
        if not properties.is_muc_self_presence:

            if self.is_connected and self.contact.settings.get('print_join_left'):
                self.add_info_message(_('%s has joined the group chat') % nick)
            return

        status_codes = properties.muc_status_codes or []

        if not self.is_connected:
            # We just joined the room
            self.add_info_message(_('You (%s) joined the group chat') % nick)

        if StatusCode.NON_ANONYMOUS in status_codes:
            self.add_info_message(
                _('Any participant is allowed to see your full XMPP Address'))
            self.is_anonymous = False

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            self.add_info_message(_('Conversations are stored on the server'))

        if StatusCode.NICKNAME_MODIFIED in status_codes:
            self.add_info_message(
                _('The server has assigned or modified your nickname in this '
                  'group chat'))

        # Update Actions
        self.update_actions()

    def _on_room_config_finished(self, _contact, _signal_name):
        self._show_page('groupchat')
        self.add_info_message(_('A new group chat has been created'))

    def _on_room_config_failed(self, _contact, _signal_name, error):
        self.xml.error_heading.set_text(_('Failed to Configure Group Chat'))
        self.xml.error_label.set_text(to_user_string(error))
        self._show_page('error')

    def _on_user_nickname_changed(self, _contact, _signal_name, user_contact, properties):
        nick = user_contact.name
        new_nick = properties.muc_user.nick
        if properties.is_muc_self_presence:
            self._nick_completion.change_nick(new_nick)
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)
            self._nick_completion.contact_renamed(nick, new_nick)

        self.add_info_message(message)

        # TODO: What to do with this?
        # tv = self.conv_textview
        # if nick in tv.last_received_message_id:
        #     tv.last_received_message_id[new_nick] = \
        #         tv.last_received_message_id[nick]
        #     del tv.last_received_message_id[nick]


    def _on_user_status_show_changed(self,
                                     _contact,
                                     _signal_name,
                                     user_contact,
                                     properties):

        if not self.contact.settings.get('print_status'):
            return

        nick = user_contact.name
        status = user_contact.status
        status = '' if status is None else ' - %s' % status
        show = helpers.get_uf_show(user_contact.show.value)

        if properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
        self.add_status_message(message)

    def _on_user_affiliation_changed(self,
                                     _contact,
                                     _signal_name,
                                     user_contact,
                                     properties):
        affiliation = helpers.get_uf_affiliation(user_contact.affiliation)
        nick = user_contact.name
        reason = properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if properties.is_muc_self_presence:
            message = _('** Your Affiliation has been set to '
                        '{affiliation}{actor}{reason}').format(
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)
        else:
            message = _('** Affiliation of {nick} has been set to '
                        '{affiliation}{actor}{reason}').format(
                            nick=nick,
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)

        self.add_info_message(message)
        self.update_actions()

    def _on_user_role_changed(self,
                              _contact,
                              _signal_name,
                              user_contact,
                              properties):
        role = helpers.get_uf_role(user_contact.role)
        nick = user_contact.name
        reason = properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if properties.is_muc_self_presence:
            message = _('** Your Role has been set to '
                        '{role}{actor}{reason}').format(role=role,
                                                        actor=actor,
                                                        reason=reason)
        else:
            message = _('** Role of {nick} has been set to '
                        '{role}{actor}{reason}').format(nick=nick,
                                                        role=role,
                                                        actor=actor,
                                                        reason=reason)

        self.add_info_message(message)
        self.update_actions()

    def _on_room_kicked(self, _contact, _signal_name, properties):
        status_codes = properties.muc_status_codes or []

        reason = properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        #Group Chat: We have been removed from the room by Alice: reason
        message = _('You have been removed from the group chat{actor}{reason}')

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            #Group Chat: Server kicked us because of an server error
            message = _('You have left due '
                        'to an error{reason}').format(reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_KICKED in status_codes:
            #Group Chat: We have been kicked by Alice: reason
            message = _('You have been '
                        'kicked{actor}{reason}').format(actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_BANNED in status_codes:
            #Group Chat: We have been banned by Alice: reason
            message = _('You have been '
                        'banned{actor}{reason}').format(actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            #Group Chat: We were removed because of an affiliation change
            reason = _(': Affiliation changed')
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            #Group Chat: Room configuration changed
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
            #Group Chat: Kicked because of server shutdown
            reason = ': System shutdown'
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

    def _on_user_left(self, _contact, _signal_name, user_contact, properties):
        status_codes = properties.muc_status_codes or []
        nick = user_contact.name

        reason = properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        #Group Chat: We have been removed from the room
        message = _('{nick} has been removed from the group chat{by}{reason}')

        print_join_left = self.contact.settings.get('print_join_left')

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            if print_join_left:
                #Group Chat: User was kicked because of an server error: reason
                message = _('{nick} has left due to '
                            'an error{reason}').format(nick=nick, reason=reason)
                self.add_info_message(message)

        elif StatusCode.REMOVED_KICKED in status_codes:
            #Group Chat: User was kicked by Alice: reason
            message = _('{nick} has been '
                        'kicked{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_BANNED in status_codes:
            #Group Chat: User was banned by Alice: reason
            message = _('{nick} has been '
                        'banned{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            reason = _(': Affiliation changed')
            message = message.format(nick=nick, by=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(nick=nick, by=actor, reason=reason)
            self.add_info_message(message)

        elif print_join_left:
            message = _('{nick} has left{reason}').format(nick=nick,
                                                          reason=reason)
            self.add_info_message(message)

    def _on_room_joined(self, _contact, _signal_name):
        self._show_page('groupchat')

    def _on_room_password_required(self, _contact, _signal_name, _properties):
        self._show_page('password')

    def _on_room_join_failed(self, _contact, _signal_name, error):
        if self._client.get_module('Bookmarks').is_bookmark(self.room_jid):
            self.xml.remove_bookmark_button.show()

        self.xml.error_heading.set_text(_('Failed to Join Group Chat'))
        self.xml.error_label.set_text(to_user_string(error))
        self._show_page('error')

    def _on_room_creation_failed(self, _contact, _signal_name, properties):
        self.xml.error_heading.set_text(_('Failed to Create Group Chat'))
        self.xml.error_label.set_text(to_user_string(properties.error))
        self._show_page('error')

    def _on_room_presence_error(self, _contact, _signal_name, properties):
        error_message = to_user_string(properties.error)
        self.add_info_message('Error: %s' % error_message)

    def _on_room_destroyed(self, _contact, _signal_name, properties):
        destroyed = properties.muc_destroyed

        reason = destroyed.reason
        reason = '' if reason is None else ': %s' % reason

        message = _('Group chat has been destroyed')
        self.add_info_message(message)

        alternate = destroyed.alternate
        if alternate is not None:
            join_message = _('You can join this group chat '
                             'instead: xmpp:%s?join') % str(alternate)
            self.add_info_message(join_message)

        self._client.get_module('Bookmarks').remove(self.room_jid)

        if self._wait_for_destruction:
            self._close_control()

    def _on_message_sent(self, event):
        if not event.message:
            return
        # we'll save sent message text when we'll receive it in
        # _nec_gc_message_received
        self.last_sent_msg = event.message_id
        if self.correcting:
            self.correcting = False
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'gajim-msg-correcting')

    def send_message(self, message, xhtml=None, process_commands=True):
        """
        Call this function to send our message
        """
        if not message:
            return

        if self.encryption:
            self.sendmessage = True
            app.plugin_manager.extension_point(
                'send_message' + self.encryption, self)
            if not self.sendmessage:
                return

        if process_commands and self.process_as_command(message):
            return

        message = helpers.remove_invalid_xml_chars(message)

        if not message:
            return

        label = self.get_seclabel()
        if message != '' or message != '\n':
            self.save_message(message, 'sent')

            if self.correcting and self.last_sent_msg:
                correct_id = self.last_sent_msg
            else:
                correct_id = None
            chatstate = self._client.get_module('Chatstate').get_active_chatstate(
                self.contact)

            # Send the message
            message_ = OutgoingMessage(account=self.account,
                                       contact=self.contact,
                                       message=message,
                                       type_='groupchat',
                                       label=label,
                                       chatstate=chatstate,
                                       correct_id=correct_id)
            message_.additional_data.set_value('gajim', 'xhtml', xhtml)
            self._client.send_message(message_)

            self.msg_textview.get_buffer().set_text('')
            self.msg_textview.grab_focus()

    def _on_message_error(self, event):
        self.conversation_view.show_error(event.message_id, event.error)

    def shutdown(self, reason=None):
        app.settings.disconnect_signals(self)
        self.contact.disconnect(self)

        # PluginSystem: removing GUI extension points connected with
        # GrouphatControl instance object
        app.plugin_manager.remove_gui_extension_point(
            'groupchat_control', self)

        # They can already be removed by the destroy function
        # TODO remove
        if self.room_jid in app.contacts.get_gc_list(self.account):
            app.contacts.remove_room(self.account, self.room_jid)
            del app.gc_connected[self.account][self.room_jid]

        self.roster.destroy()
        self.roster = None

        # Remove unread events from systray
        app.events.remove_events(self.account, self.room_jid)

        if self.parent_win is not None:
            self.remove_actions()

        super(GroupchatControl, self).shutdown()
        app.check_finalize(self)

    def safe_shutdown(self):
        # whether to ask for confirmation before closing muc
        if app.settings.get('confirm_close_muc') and self.is_connected:
            return False
        return True

    def allow_shutdown(self, method, on_yes, on_no):
        # whether to ask for confirmation before closing muc
        if app.settings.get('confirm_close_muc') and self.is_connected:
            def on_ok(is_checked):
                if is_checked:
                    # User does not want to be asked again
                    app.settings.set('confirm_close_muc', False)
                on_yes(self)

            def on_cancel(is_checked):
                if is_checked:
                    # User does not want to be asked again
                    app.settings.set('confirm_close_muc', False)
                on_no(self)

            ConfirmationCheckDialog(
                _('Leave Group Chat'),
                _('Are you sure you want to leave this group chat?'),
                _('If you close this window, you will leave '
                  '\'%s\'.') % self.room_name,
                _('_Do not ask me again'),
                [DialogButton.make('Cancel',
                                   callback=on_cancel),
                 DialogButton.make('Accept',
                                   text=_('_Leave'),
                                   callback=on_ok)],
                transient_for=self.parent_win.window).show()
            return

        on_yes(self)

    def _close_control(self, reason=None):
        # if self.parent_win is None:
        self.shutdown(reason)
        # else:
            # self.parent_win.remove_tab(self, None, reason=reason, force=True)

    def set_control_active(self, state):
        # self.conv_textview.allow_focus_out_line = True
        self.attention_flag = False
        ChatControlBase.set_control_active(self, state)
        # if not state:
        #    # add the focus-out line to the tab we are leaving
        #    self.check_focus_out_line()
        # Sending active to undo unread state
        self.parent_win.redraw_tab(self, 'active')

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        if not selection.get_data():
            return

        if target_type == self.TARGET_TYPE_URI_LIST:
            # File drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(selection)
        else:
            # Invite contact to groupchat
            treeview = app.interface.roster.tree
            model = treeview.get_model()
            data = selection.get_data().decode()
            path = treeview.get_selection().get_selected_rows()[1][0]
            iter_ = model.get_iter(path)
            type_ = model[iter_][2]
            if type_ != 'contact':  # Source is not a contact
                return
            contact_jid = data

            self.invite(contact_jid)

    def _jid_not_blocked(self, bare_jid: str) -> bool:
        fjid = self.room_jid + '/' + bare_jid
        return not helpers.jid_is_blocked(self.account, fjid)

    def _on_message_textview_key_press_event(self, widget, event):
        res = ChatControlBase._on_message_textview_key_press_event(
            self, widget, event)
        if res:
            return True

        if event.keyval == Gdk.KEY_Tab: # TAB
            message_buffer = widget.get_buffer()
            start_iter, end_iter = message_buffer.get_bounds()
            cursor_position = message_buffer.get_insert()
            end_iter = message_buffer.get_iter_at_mark(cursor_position)
            text = message_buffer.get_text(start_iter, end_iter, False)

            splitted_text = text.split()

            # nick completion
            # check if tab is pressed with empty message
            if splitted_text:  # if there are any words
                begin = splitted_text[-1] # last word we typed
            else:
                begin = ''

            gc_refer_to_nick_char = app.settings.get('gc_refer_to_nick_char')
            with_refer_to_nick_char = False
            after_nick_len = 1 # the space that is printed after we type [Tab]

            # first part of this if : works fine even if refer_to_nick_char
            if (gc_refer_to_nick_char and
                    text.endswith(gc_refer_to_nick_char + ' ')):
                with_refer_to_nick_char = True
                after_nick_len = len(gc_refer_to_nick_char + ' ')
            if self.nick_hits and self.last_key_tabs and \
               text[:-after_nick_len].endswith(self.nick_hits[0]):
                # we should cycle
                # Previous nick in list may had a space inside, so we check text
                # and not splitted_text and store it into 'begin' var
                self.nick_hits.append(self.nick_hits[0])
                begin = self.nick_hits.pop(0)
            else:
                list_nick = self.contact.get_user_nicknames()
                list_nick = list(filter(self._jid_not_blocked, list_nick))

                log.debug("Nicks to be considered for autosuggestions: %s",
                          list_nick)
                self.nick_hits = self._nick_completion.generate_suggestions(
                    nicks=list_nick, beginning=begin)
                log.debug("Nicks filtered for autosuggestions: %s",
                          self.nick_hits)

            if self.nick_hits:
                if len(splitted_text) < 2 or with_refer_to_nick_char:
                    # This is the 1st word of the line or no word or we are
                    # cycling at the beginning, possibly with a space in
                    # one nick
                    add = gc_refer_to_nick_char + ' '
                else:
                    add = ' '
                start_iter = end_iter.copy()
                if (self.last_key_tabs and
                        with_refer_to_nick_char or (text and text[-1] == ' ')):
                    # have to accommodate for the added space from last
                    # completion
                    # gc_refer_to_nick_char may be more than one char!
                    start_iter.backward_chars(len(begin) + len(add))
                elif (self.last_key_tabs and
                      not app.settings.get('shell_like_completion')):
                    # have to accommodate for the added space from last
                    # completion
                    start_iter.backward_chars(len(begin) + \
                                              len(gc_refer_to_nick_char))
                else:
                    start_iter.backward_chars(len(begin))

                self._client.get_module('Chatstate').block_chatstates(
                    self.contact, True)

                message_buffer.delete(start_iter, end_iter)
                # get a shell-like completion
                # if there's more than one nick for this completion, complete
                # only the part that all these nicks have in common
                if app.settings.get('shell_like_completion') and \
                len(self.nick_hits) > 1:
                    end = False
                    completion = ''
                    add = "" # if nick is not complete, don't add anything
                    while not end and len(completion) < len(self.nick_hits[0]):
                        completion = self.nick_hits[0][:len(completion)+1]
                        for nick in self.nick_hits:
                            if completion.lower() not in nick.lower():
                                end = True
                                completion = completion[:-1]
                                break
                    # if the current nick matches a COMPLETE existing nick,
                    # and if the user tab TWICE, complete that nick (with the
                    # "add")
                    if self.last_key_tabs:
                        for nick in self.nick_hits:
                            if nick == completion:
                                # The user seems to want this nick, so
                                # complete it as if it were the only nick
                                # available
                                add = gc_refer_to_nick_char + ' '
                else:
                    completion = self.nick_hits[0]
                message_buffer.insert_at_cursor(completion + add)

                self._client.get_module('Chatstate').block_chatstates(
                    self.contact, False)

                self.last_key_tabs = True
                return True
            self.last_key_tabs = False
        return None

    def delegate_action(self, action):
        res = super().delegate_action(action)
        if res == Gdk.EVENT_STOP:
            return res

        if action == 'change-nickname':
            control_action = '%s-%s' % (action, self.control_id)
            self.parent_win.window.lookup_action(control_action).activate()
            return Gdk.EVENT_STOP

        if action == 'escape':
            if self._get_current_page() == 'groupchat':
                return Gdk.EVENT_PROPAGATE

            if self._get_current_page() == 'password':
                self._on_password_cancel_clicked()
            elif self._get_current_page() == 'captcha':
                self._on_captcha_cancel_clicked()
            elif self._get_current_page() == 'muc-info':
                self._on_page_cancel_clicked()
            elif self._get_current_page() in ('error', 'captcha-error'):
                self._on_page_close_clicked()
            else:
                self._show_page('groupchat')
            return Gdk.EVENT_STOP

        if action == 'change-subject':
            control_action = '%s-%s' % (action, self.control_id)
            self.parent_win.window.lookup_action(control_action).activate()
            return Gdk.EVENT_STOP

        if action == 'show-contact-info':
            self.parent_win.window.lookup_action(
                'information-%s' % self.control_id).activate()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def focus(self):
        page_name = self._get_current_page()
        if page_name == 'groupchat':
            self.msg_textview.grab_focus()
        elif page_name == 'password':
            self.xml.password_entry.grab_focus_without_selecting()
        elif page_name == 'nickname':
            self.xml.nickname_entry.grab_focus_without_selecting()
        elif page_name == 'rename':
            self.xml.name_entry.grab_focus_without_selecting()
        elif page_name == 'subject':
            self.xml.subject_textview.grab_focus()
        elif page_name == 'captcha':
            self._captcha_request.focus_first_entry()
        elif page_name == 'invite':
            self._invite_box.focus_search_entry()
        elif page_name == 'destroy':
            self.xml.destroy_reason_entry.grab_focus_without_selecting()

    def append_nick_in_msg_textview(self, _widget, nick):
        message_buffer = self.msg_textview.get_buffer()
        start_iter, end_iter = message_buffer.get_bounds()
        cursor_position = message_buffer.get_insert()
        end_iter = message_buffer.get_iter_at_mark(cursor_position)
        text = message_buffer.get_text(start_iter, end_iter, False)
        start = ''
        if text: # Cursor is not at first position
            if not text[-1] in (' ', '\n', '\t'):
                start = ' '
            add = ' '
        else:
            gc_refer_to_nick_char = app.settings.get('gc_refer_to_nick_char')
            add = gc_refer_to_nick_char + ' '
        message_buffer.insert_at_cursor(start + nick + add)

    def _on_kick_participant_clicked(self, _button):
        reason = self.xml.kick_reason_entry.get_text()
        self._client.get_module('MUC').set_role(
            self.room_jid, self._kick_nick, 'none', reason)
        self._show_page('groupchat')

    def _on_ban_participant_clicked(self, _button):
        reason = self.xml.ban_reason_entry.get_text()
        self._client.get_module('MUC').set_affiliation(
            self.room_jid,
            {self._ban_jid: {'affiliation': 'outcast', 'reason': reason}})
        self._show_page('groupchat')

    def _on_page_change(self, stack, _param):
        page_name = stack.get_visible_child_name()
        if page_name == 'groupchat':
            pass
        elif page_name == 'muc-info':
            self.xml.info_close_button.grab_default()
        elif page_name == 'password':
            self.xml.password_entry.set_text('')
            self.xml.password_entry.grab_focus()
            self.xml.password_set_button.grab_default()
        elif page_name == 'captcha':
            self.xml.captcha_set_button.grab_default()
        elif page_name == 'captcha-error':
            self.xml.captcha_try_again_button.grab_default()
        elif page_name == 'error':
            self.xml.close_button.grab_default()

    def _on_change_nick(self, _action, _param):
        if self._get_current_page() != 'groupchat':
            return
        self.xml.nickname_entry.set_text(self.nick)
        self.xml.nickname_entry.grab_focus()
        self.xml.nickname_change_button.grab_default()
        self._show_page('nickname')

    def _on_nickname_text_changed(self, entry, _param):
        text = entry.get_text()
        if not text or text == self.nick:
            self.xml.nickname_change_button.set_sensitive(False)
        else:
            try:
                validate_resourcepart(text)
            except InvalidJid:
                self.xml.nickname_change_button.set_sensitive(False)
            else:
                self.xml.nickname_change_button.set_sensitive(True)

    def _on_nickname_change_clicked(self, _button):
        new_nick = self.xml.nickname_entry.get_text()
        self._client.get_module('MUC').change_nick(self.room_jid, new_nick)
        self._show_page('groupchat')

    def _on_rename_groupchat(self, _action, _param):
        if self._get_current_page() != 'groupchat':
            return
        self.xml.name_entry.set_text(self.room_name)
        self.xml.name_entry.grab_focus()
        self.xml.rename_button.grab_default()
        self._show_page('rename')

    def _on_rename_clicked(self, _button):
        new_name = self.xml.name_entry.get_text()
        self._client.get_module('Bookmarks').modify(
            self.room_jid, name=new_name)
        self._show_page('groupchat')

    def _on_manage_save_clicked(self, _button):
        if self._room_config_form is not None:
            name = self.xml.muc_name_entry.get_text()
            desc = self.xml.muc_description_entry.get_text()
            try:
                name_field = self._room_config_form['muc#roomconfig_roomname']
                desc_field = self._room_config_form['muc#roomconfig_roomdesc']
            except KeyError:
                pass
            else:
                name_field.value = name
                desc_field.value = desc

            con = app.connections[self.account]
            con.get_module('MUC').set_config(
                self.room_jid, self._room_config_form)

        self._show_page('groupchat')

    def _on_change_subject(self, _button):
        if self._get_current_page() not in ('groupchat', 'muc-manage'):
            return
        self.xml.subject_textview.get_buffer().set_text(self.subject)
        self.xml.subject_textview.grab_focus()
        self._show_page('subject')

    def _on_subject_change_clicked(self, _button):
        buffer_ = self.xml.subject_textview.get_buffer()
        subject = buffer_.get_text(buffer_.get_start_iter(),
                                   buffer_.get_end_iter(),
                                   False)
        self._client.get_module('MUC').set_subject(self.room_jid, subject)
        self._show_page('groupchat')

    def _on_password_set_clicked(self, _button):
        password = self.xml.password_entry.get_text()
        self._muc_data.password = password
        self._client.get_module('MUC').join(self.room_jid)
        self._show_page('groupchat')

    def _on_password_changed(self, entry, _param):
        self.xml.password_set_button.set_sensitive(bool(entry.get_text()))

    def _on_password_cancel_clicked(self, _button=None):
        self._close_control()

    def _on_room_captcha_challenge(self, _contact, _signal_name, properties):
        self._remove_captcha_request()
        form = properties.captcha.form

        options = {'no-scrolling': True,
                   'entry-activates-default': True}
        self._captcha_request = DataFormWidget(form, options=options)
        self._captcha_request.connect('is-valid', self._on_captcha_changed)
        self._captcha_request.set_valign(Gtk.Align.START)
        self._captcha_request.show_all()
        self.xml.captcha_box.add(self._captcha_request)

        if self.parent_win:
            self.parent_win.redraw_tab(self, 'attention')
        else:
            self.attention_flag = True

        self._show_page('captcha')
        self._captcha_request.focus_first_entry()

    def _on_room_captcha_error(self, _contact, _signal_name, error):
        error_text = to_user_string(error)
        self.xml.captcha_error_label.set_text(error_text)
        self._show_page('captcha-error')

    def _remove_captcha_request(self):
        if self._captcha_request is None:
            return
        if self._captcha_request in self.xml.captcha_box.get_children():
            self.xml.captcha_box.remove(self._captcha_request)
        self._captcha_request.destroy()
        self._captcha_request = None

    def _on_captcha_changed(self, _widget, is_valid):
        self.xml.captcha_set_button.set_sensitive(is_valid)

    def _on_captcha_set_clicked(self, _button):
        form_node = self._captcha_request.get_submit_form()
        self._client.get_module('MUC').send_captcha(self.room_jid, form_node)
        self._remove_captcha_request()
        self._show_page('groupchat')

    def _on_captcha_cancel_clicked(self, _button=None):
        self._client.get_module('MUC').cancel_captcha(self.room_jid)
        self._remove_captcha_request()
        self._close_control()

    def _on_captcha_try_again_clicked(self, _button=None):
        self._client.get_module('MUC').join(self.room_jid)
        self._show_page('groupchat')

    def _on_remove_bookmark_button_clicked(self, _button=None):
        self._client.get_module('Bookmarks').remove(self.room_jid)
        self._close_control()

    def _on_retry_join_clicked(self, _button=None):
        self._client.get_module('MUC').join(self.room_jid)
        self._show_page('groupchat')

    def _on_page_cancel_clicked(self, _button=None):
        self._show_page('groupchat')

    def _on_page_close_clicked(self, _button=None):
        self._close_control()

    def _on_groupchat_state_abort_clicked(self, _button):
        app.window.lookup_action('disconnect-%s' % self.control_id).activate()

    def _on_groupchat_state_join_clicked(self, _groupchat_state):
        self._client.get_module('MUC').join(self.room_jid)
