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

from typing import Optional

import time
import locale
import base64
import logging
from enum import IntEnum, unique

import nbxmpp
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import validate_resourcepart
from nbxmpp.const import StatusCode
from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.const import PresenceType
from nbxmpp.util import is_error_result

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import Gio

from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import message_control
from gajim import vcard

from gajim.common.const import AvatarSize
from gajim.common.caps_cache import muc_caps_cache
from gajim.common import events
from gajim.common import app
from gajim.common import helpers
from gajim.common.helpers import open_uri
from gajim.common.helpers import event_filter
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common import contacts
from gajim.common.const import StyleAttr
from gajim.common.const import Chatstate
from gajim.common.const import MUCJoinedState

from gajim.chat_control_base import ChatControlBase

from gajim.command_system.implementation.hosts import GroupChatCommands
from gajim.common.connection_handlers_events import GcMessageOutgoingEvent

from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationCheckDialog
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import DestroyMucDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.single_message import SingleMessageWindow
from gajim.gtk.filechoosers import AvatarChooserDialog
from gajim.gtk.add_contact import AddNewContactWindow
from gajim.gtk.tooltips import GCTooltip
from gajim.gtk.groupchat_config import GroupchatConfig
from gajim.gtk.adhoc import AdHocCommand
from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.util import NickCompletionGenerator
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_affiliation_surface
from gajim.gtk.util import get_builder


log = logging.getLogger('gajim.groupchat_control')

@unique
class Column(IntEnum):
    IMG = 0 # image to show state (online, new message etc)
    NICK = 1 # contact nickname or ROLE name
    TYPE = 2 # type of the row ('contact' or 'role')
    TEXT = 3 # text shown in the cellrenderer
    AVATAR_IMG = 4 # avatar of the contact


class GroupchatControl(ChatControlBase):
    TYPE_ID = message_control.TYPE_GC

    # Set a command host to bound to. Every command given through a group chat
    # will be processed with this command host.
    COMMAND_HOST = GroupChatCommands

    def __init__(self, parent_win, contact, muc_data, acct, is_continued=False):
        ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
            'groupchat_control', contact, acct)

        self.force_non_minimizable = False
        self.is_continued = is_continued
        self.is_anonymous = True

        # Controls the state of autorejoin.
        # None - autorejoin is neutral.
        # False - autorejoin is to be prevented (gets reset to initial state in
        #         got_connected()).
        # int - autorejoin is being active and working (gets reset to initial
        #       state in got_connected()).
        self.autorejoin = None

        # Keep error dialog instance to be sure to have only once at a time
        self.error_dialog = None

        # Source id for saving the handle position
        self._handle_timeout_id = None

        self.emoticons_button = self.xml.get_object('emoticons_button')
        self.toggle_emoticons()

        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(False)

        self._state_change_handler_id = None
        if parent_win is not None:
            # On AutoJoin with minimize Groupchats are created without parent
            # Tooltip Window and Actions have to be created with parent
            self.set_tooltip()
            self.add_actions()
            GLib.idle_add(self.update_actions)
            self.scale_factor = parent_win.window.get_scale_factor()
            self._connect_window_state_change(parent_win)
        else:
            self.scale_factor = app.interface.roster.scale_factor

        widget = self.xml.get_object('list_treeview')
        id_ = widget.connect('row_expanded', self.on_list_treeview_row_expanded)
        self.handlers[id_] = widget

        id_ = widget.connect('row_collapsed',
            self.on_list_treeview_row_collapsed)
        self.handlers[id_] = widget

        id_ = widget.connect('row_activated',
            self.on_list_treeview_row_activated)
        self.handlers[id_] = widget

        id_ = widget.connect('button_press_event',
            self.on_list_treeview_button_press_event)
        self.handlers[id_] = widget

        id_ = widget.connect('key_press_event',
            self.on_list_treeview_key_press_event)
        self.handlers[id_] = widget

        self.room_jid = self.contact.jid
        self._muc_data = muc_data

        bm_module = app.connections[self.account].get_module('Bookmarks')
        self.name = bm_module.get_name_from_bookmark(self.room_jid)

        self.contact.name = self.name

        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            app.config.get('hide_groupchat_banner'))

        # muc attention flag (when we are mentioned in a muc)
        # if True, the room has mentioned us
        self.attention_flag = False

        # True if we initiated room destruction
        self._wait_for_destruction = False

        # sorted list of nicks who mentioned us (last at the end)
        self.attention_list = []
        self.nick_hits = []
        self._nick_completion = NickCompletionGenerator(muc_data.nick)
        self.last_key_tabs = False

        self.subject = ''

        self.name_label = self.xml.get_object('banner_name_label')
        self.event_box = self.xml.get_object('banner_eventbox')

        self.list_treeview = self.xml.get_object('list_treeview')
        id_ = self.list_treeview.connect('style-set',
                                         self.on_list_treeview_style_set)
        self.handlers[id_] = self.list_treeview

        # flag that stops hpaned position event
        # when the handle gets resized in another control
        self._resize_from_another_muc = False

        self.hpaned = self.xml.get_object('hpaned')

        # set the position of the current hpaned
        hpaned_position = app.config.get('gc-hpaned-position')
        self.hpaned.set_position(hpaned_position)

        # Holds the Gtk.TreeRowReference for each contact
        self._contact_refs = {}
        # Holds the Gtk.TreeRowReference for each role
        self._role_refs = {}

        #status_image, shown_nick, type, nickname, avatar
        self.columns = [str, str, str, str, Gtk.Image]
        self.model = Gtk.TreeStore(*self.columns)
        self.model.set_sort_func(Column.NICK, self.tree_compare_iters)

        # columns
        column = Gtk.TreeViewColumn()
        # list of renderers with attributes / properties in the form:
        # (name, renderer_object, expand?, attribute_name, attribute_value,
        # cell_data_func, func_arg)
        self.renderers_list = []
        # Number of renderers plugins added
        self.nb_ext_renderers = 0
        self.renderers_propertys = {}
        renderer_text = Gtk.CellRendererText()
        self.renderers_propertys[renderer_text] = ('ellipsize',
            Pango.EllipsizeMode.END)

        self.renderers_list += (
            # status img
            ('icon', Gtk.CellRendererPixbuf(), False,
            'icon_name', Column.IMG, self._cell_data_func, 'status'),
            # contact name
            ('name', renderer_text, True,
            'markup', Column.TEXT, self._cell_data_func, 'name'))

        # avatar img
        avatar_renderer = ('avatar', Gtk.CellRendererPixbuf(),
            False, None, Column.AVATAR_IMG,
            self._cell_data_func, 'avatar')

        if app.config.get('avatar_position_in_roster') == 'right':
            self.renderers_list.append(avatar_renderer)
        else:
            self.renderers_list.insert(0, avatar_renderer)

        self.fill_column(column)
        self.list_treeview.append_column(column)

        # workaround to avoid gtk arrows to be shown
        column = Gtk.TreeViewColumn() # 2nd COLUMN
        renderer = Gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        self.list_treeview.append_column(column)
        column.set_visible(False)
        self.list_treeview.set_expander_column(column)

        self.setup_seclabel()

        # Send file
        self.sendfile_button = self.xml.get_object('sendfile_button')
        self.sendfile_button.set_action_name('win.send-file-' + \
                                             self.control_id)

        # Encryption
        self.lock_image = self.xml.get_object('lock_image')
        self.authentication_button = self.xml.get_object(
            'authentication_button')
        id_ = self.authentication_button.connect('clicked',
            self._on_authentication_button_clicked)
        self.handlers[id_] = self.authentication_button
        self.set_lock_image()

        self.encryption_menu = self.xml.get_object('encryption_menu')
        self.encryption_menu.set_menu_model(
            gui_menu_builder.get_encryption_menu(self.control_id, self.type_id))
        self.set_encryption_menu_icon()

        # Banner
        self.banner_actionbar = self.xml.get_object('banner_actionbar')
        self.hide_roster_button = Gtk.Button.new_from_icon_name(
            'go-next-symbolic', Gtk.IconSize.MENU)
        self.hide_roster_button.connect('clicked',
                                        lambda *args: self.show_roster())
        self.subject_button = Gtk.MenuButton()
        self.subject_button.set_image(Gtk.Image.new_from_icon_name(
            'go-down-symbolic', Gtk.IconSize.MENU))
        self.subject_button.set_popover(SubjectPopover())
        self.subject_button.set_no_show_all(True)
        self.banner_actionbar.pack_end(self.hide_roster_button)
        self.banner_actionbar.pack_start(self.subject_button)

        # Holds CaptchaRequest widget
        self._captcha_request = None

        # GC Roster tooltip
        self.gc_tooltip = GCTooltip()

        self.control_menu = gui_menu_builder.get_groupchat_menu(self.control_id,
                                                                self.account,
                                                                self.room_jid)
        settings_menu = self.xml.get_object('settings_menu')
        settings_menu.set_menu_model(self.control_menu)

        self._event_handlers = [
            ('muc-joined', ged.GUI1, self._on_muc_joined),
            ('muc-join-failed', ged.GUI1, self._on_muc_join_failed),
            ('muc-user-joined', ged.GUI1, self._on_user_joined),
            ('muc-user-left', ged.GUI1, self._on_user_left),
            ('muc-nickname-changed', ged.GUI1, self._on_nickname_changed),
            ('muc-self-presence', ged.GUI1, self._on_self_presence),
            ('muc-self-kicked', ged.GUI1, self._on_self_kicked),
            ('muc-user-affiliation-changed', ged.GUI1, self._on_affiliation_changed),
            ('muc-user-status-show-changed', ged.GUI1, self._on_status_show_changed),
            ('muc-user-role-changed', ged.GUI1, self._on_role_changed),
            ('muc-destroyed', ged.GUI1, self._on_destroyed),
            ('muc-presence-error', ged.GUI1, self._on_presence_error),
            ('muc-password-required', ged.GUI1, self._on_password_required),
            ('muc-config-changed', ged.GUI1, self._on_config_changed),
            ('muc-subject', ged.GUI1, self._on_subject),
            ('muc-captcha-challenge', ged.GUI1, self._on_captcha_challenge),
            ('muc-captcha-error', ged.GUI1, self._on_captcha_error),
            ('muc-voice-approval', ged.GUI1, self._on_voice_approval),
            ('muc-disco-update', ged.GUI1, self._on_disco_update),
            ('muc-configuration-finished', ged.GUI1, self._on_configuration_finished),
            ('gc-message-received', ged.GUI1, self._nec_gc_message_received),
            ('mam-decrypted-message-received', ged.GUI1, self._nec_mam_decrypted_message_received),
            ('update-gc-avatar', ged.GUI1, self._nec_update_avatar),
            ('update-room-avatar', ged.GUI1, self._nec_update_room_avatar),
            ('signed-in', ged.GUI1, self._nec_signed_in),
            ('decrypted-message-received', ged.GUI2, self._nec_decrypted_message_received),
            ('gc-stanza-message-outgoing', ged.OUT_POSTCORE, self._message_sent),
        ]

        for handler in self._event_handlers:
            app.ged.register_event_handler(*handler)

        self.is_connected = False
        # disable win, we are not connected yet
        ChatControlBase.got_disconnected(self)

        # Stack
        self.xml.stack.show_all()
        self.xml.stack.set_visible_child_name('progress')
        self.xml.progress_spinner.start()

        self.update_ui()
        self.widget.show_all()

        if app.config.get('hide_groupchat_occupants_list'):
            # Roster is shown by default, so toggle the roster button to hide it
            self.show_roster()

        # PluginSystem: adding GUI extension point for this GroupchatControl
        # instance object
        app.plugin_manager.gui_extension_point('groupchat_control', self)

    @property
    def nick(self):
        return self._muc_data.nick

    def add_actions(self):
        super().add_actions()
        actions = [
            ('change-subject-', self._on_change_subject),
            ('change-nickname-', self._on_change_nick),
            ('disconnect-', self._on_disconnect),
            ('destroy-', self._on_destroy_room),
            ('configure-', self._on_configure_room),
            ('request-voice-', self._on_request_voice),
            ('execute-command-', self._on_execute_command),
            ('upload-avatar-', self._on_upload_avatar),
        ]

        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(action_name + self.control_id, None)
            act.connect("activate", func)
            self.parent_win.window.add_action(act)

        minimize = app.config.get_per(
            'rooms', self.contact.jid, 'minimize_on_close', True)

        act = Gio.SimpleAction.new_stateful(
            'minimize-on-close-' + self.control_id, None,
            GLib.Variant.new_boolean(minimize))
        act.connect('change-state', self._on_minimize_on_close)
        self.parent_win.window.add_action(act)

        minimize = app.config.get_per(
            'rooms', self.contact.jid, 'minimize_on_autojoin', True)

        act = Gio.SimpleAction.new_stateful(
            'minimize-on-autojoin-' + self.control_id, None,
            GLib.Variant.new_boolean(minimize))
        act.connect('change-state', self._on_minimize_on_autojoin)
        self.parent_win.window.add_action(act)

        default_muc_chatstate = app.config.get('send_chatstate_muc_default')
        chatstate = app.config.get_per(
            'rooms', self.contact.jid, 'send_chatstate', default_muc_chatstate)

        act = Gio.SimpleAction.new_stateful(
            'send-chatstate-' + self.control_id,
            GLib.VariantType.new("s"),
            GLib.Variant("s", chatstate))
        act.connect('change-state', self._on_send_chatstate)
        self.parent_win.window.add_action(act)

        # Enable notify on all for private rooms
        members_only = muc_caps_cache.supports(self.contact.jid,
                                               'muc#roomconfig_membersonly')
        value = app.config.get_per(
            'rooms', self.contact.jid, 'notify_on_all_messages', members_only)

        act = Gio.SimpleAction.new_stateful(
            'notify-on-message-' + self.control_id,
            None, GLib.Variant.new_boolean(value))
        act.connect('change-state', self._on_notify_on_all_messages)
        self.parent_win.window.add_action(act)

        status_default = app.config.get('print_status_muc_default')
        value = app.config.get_per('rooms', self.contact.jid,
                                   'print_status', status_default)

        act = Gio.SimpleAction.new_stateful(
            'print-status-' + self.control_id,
            None, GLib.Variant.new_boolean(value))
        act.connect('change-state', self._on_print_status)
        self.parent_win.window.add_action(act)

        join_default = app.config.get('print_join_left_default')
        value = app.config.get_per('rooms', self.contact.jid,
                                   'print_join_left', join_default)

        act = Gio.SimpleAction.new_stateful(
            'print-join-left-' + self.control_id,
            None, GLib.Variant.new_boolean(value))
        act.connect('change-state', self._on_print_join_left)
        self.parent_win.window.add_action(act)

        archive_info = app.logger.get_archive_infos(self.contact.jid)
        threshold = helpers.get_sync_threshold(self.contact.jid,
                                               archive_info)

        inital = GLib.Variant.new_string(str(threshold))
        act = Gio.SimpleAction.new_stateful(
            'choose-sync-' + self.control_id,
            inital.get_type(), inital)
        act.connect('change-state', self._on_sync_threshold)
        self.parent_win.window.add_action(act)

    def update_actions(self):
        if self.parent_win is None:
            return

        contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, self.nick)
        con = app.connections[self.account]

        # Destroy Room
        self._get_action('destroy-').set_enabled(self.is_connected and
                                                 contact.affiliation.is_owner)

        # Configure Room
        self._get_action('configure-').set_enabled(
            self.is_connected and contact.affiliation in (Affiliation.ADMIN,
                                                          Affiliation.OWNER))

        # Request Voice
        role = self.get_role(self.nick)
        self._get_action('request-voice-').set_enabled(self.is_connected and
                                                       role.is_visitor)

        # Change Subject
        subject = False
        if contact is not None:
            subject = muc_caps_cache.is_subject_change_allowed(
                self.room_jid, contact.affiliation)
        self._get_action('change-subject-').set_enabled(self.is_connected and
                                                        subject)

        # Change Nick
        self._get_action('change-nickname-').set_enabled(self.is_connected)

        # Execute command
        self._get_action('execute-command-').set_enabled(self.is_connected)

        # Send file (HTTP File Upload)
        httpupload = self._get_action(
            'send-file-httpupload-')
        httpupload.set_enabled(self.is_connected and
                               con.get_module('HTTPUpload').available)
        self._get_action('send-file-').set_enabled(httpupload.get_enabled())

        if self.is_connected and httpupload.get_enabled():
            tooltip_text = _('Send File…')
            max_file_size = con.get_module('HTTPUpload').max_file_size
            if max_file_size is not None:
                max_file_size = max_file_size / (1024 * 1024)
                tooltip_text = _('Send File (max. %s MiB)…') % max_file_size
        else:
            tooltip_text = _('No File Transfer available')
        self.sendfile_button.set_tooltip_text(tooltip_text)

        # Upload Avatar
        vcard_support = muc_caps_cache.supports(self.room_jid, nbxmpp.NS_VCARD)
        self._get_action('upload-avatar-').set_enabled(
            self.is_connected and
            vcard_support and
            contact.affiliation.is_owner)

        # Print join/left
        join_default = app.config.get('print_join_left_default')
        value = app.config.get_per('rooms', self.contact.jid,
                                   'print_join_left', join_default)
        self._get_action('print-join-left-').set_state(
            GLib.Variant.new_boolean(value))

        # Print join/left
        status_default = app.config.get('print_status_muc_default')
        value = app.config.get_per('rooms', self.contact.jid,
                                   'print_status', status_default)
        self._get_action('print-status-').set_state(
            GLib.Variant.new_boolean(value))

    def _get_action(self, name):
        win = self.parent_win.window
        return win.lookup_action(name + self.control_id)

    def _show_page(self, name):
        transition = Gtk.StackTransitionType.SLIDE_DOWN
        if name == 'groupchat':
            transition = Gtk.StackTransitionType.SLIDE_UP
            self.msg_textview.grab_focus()
        self.xml.stack.set_visible_child_full(name, transition)

    def _get_current_page(self):
        return self.xml.stack.get_visible_child_name()

    def _cell_data_func(self, column, renderer, model, iter_, user_data):
        # Background color has to be rendered for all cells
        theme = app.config.get('roster_theme')
        has_parent = bool(model.iter_parent(iter_))
        if has_parent:
            bgcolor = app.css_config.get_value('.gajim-contact-row', StyleAttr.BACKGROUND)
            renderer.set_property('cell-background', bgcolor)
        else:
            bgcolor = app.css_config.get_value('.gajim-group-row', StyleAttr.BACKGROUND)
            renderer.set_property('cell-background', bgcolor)

        if user_data == 'status':
            self._status_cell_data_func(column, renderer, model, iter_, has_parent)
        elif user_data == 'name':
            self._text_cell_data_func(column, renderer, model, iter_, has_parent, theme)
        elif user_data == 'avatar':
            self._avatar_cell_data_func(column, renderer, model, iter_, has_parent)

    def _status_cell_data_func(self, column, renderer, model, iter_, has_parent):
        renderer.set_property('width', 26)
        icon_name = model[iter_][Column.IMG]
        if ':' in icon_name:
            icon_name, affiliation = icon_name.split(':')
            surface = get_affiliation_surface(
                icon_name, affiliation, self.scale_factor)
            renderer.set_property('icon_name', None)
            renderer.set_property('surface', surface)
        else:
            renderer.set_property('surface', None)
            renderer.set_property('icon_name', icon_name)

    def _avatar_cell_data_func(self, column, renderer, model, iter_, has_parent):
        image = model[iter_][Column.AVATAR_IMG]
        if image is None:
            renderer.set_property('surface', None)
        else:
            surface = image.get_property('surface')
            renderer.set_property('surface', surface)

        renderer.set_property('xalign', 0.5)
        if has_parent:
            renderer.set_property('visible', True)
            renderer.set_property('width', AvatarSize.ROSTER)
        else:
            renderer.set_property('visible', False)

    def _text_cell_data_func(self, column, renderer, model, iter_, has_parent, theme):
        # cell data func is global, because we don't want it to keep
        # reference to GroupchatControl instance (self)
        if has_parent:
            color = app.css_config.get_value('.gajim-contact-row', StyleAttr.COLOR)
            renderer.set_property('foreground', color)
            desc = app.css_config.get_font('.gajim-contact-row')
            renderer.set_property('font-desc', desc)
        else:
            color = app.css_config.get_value('.gajim-group-row', StyleAttr.COLOR)
            renderer.set_property('foreground', color)
            desc = app.css_config.get_font('.gajim-group-row')
            renderer.set_property('font-desc', desc)

    @event_filter(['account', 'room_jid'])
    def _on_disco_update(self, _event):
        if self.parent_win is None:
            return
        win = self.parent_win.window
        self.update_actions()

        # After the room has been created, reevaluate threshold
        if muc_caps_cache.has_mam(self.contact.jid):
            archive_info = app.logger.get_archive_infos(self.contact.jid)
            threshold = helpers.get_sync_threshold(self.contact.jid,
                                                   archive_info)
            win.change_action_state('choose-sync-%s' % self.control_id,
                                    GLib.Variant('s', str(threshold)))


    def _connect_window_state_change(self, parent_win):
        if self._state_change_handler_id is None:
            id_ = parent_win.window.connect('notify::is-maximized',
                                            self._on_window_state_change)
            self._state_change_handler_id = id_

    # Actions

    def _on_disconnect(self, action, param):
        self.leave()

    def _on_destroy_room(self, action, param):
        def _on_confirm(reason, jid):
            if jid:
                # Test jid
                try:
                    jid = helpers.parse_jid(jid)
                except Exception:
                    ErrorDialog(
                        _('Invalid group chat XMPP Address'),
                        _('The group chat XMPP Address has not allowed characters.'))
                    return

            self._wait_for_destruction = True
            con = app.connections[self.account]
            con.get_module('MUC').destroy(self.room_jid, reason, jid)

        # Ask for a reason (and an alternate venue)
        DestroyMucDialog(self.room_jid, destroy_handler=_on_confirm)

    def _on_configure_room(self, _action, _param):
        win = app.get_app_window('GroupchatConfig', self.account, self.room_jid)
        if win is not None:
            win.present()
            return

        contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, self.nick)
        if contact.affiliation.is_owner:
            con = app.connections[self.account]
            con.get_module('MUC').request_config(
                self.room_jid, callback=self._on_configure_form_received)
        elif contact.affiliation.is_admin:
            GroupchatConfig(self.account,
                            self.room_jid,
                            contact.affiliation.value)

    def _on_configure_form_received(self, result):
        if is_error_result(result):
            log.info('Error %s %s', result.jid, result)
            return
        GroupchatConfig(self.account, result.jid, 'owner', result.form)

    def _on_print_join_left(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'print_join_left', param.get_boolean())

    def _on_print_status(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'print_status', param.get_boolean())

    def _on_request_voice(self, action, param):
        """
        Request voice in the current room
        """
        con = app.connections[self.account]
        con.get_module('MUC').request_voice(self.room_jid)

    def _on_minimize_on_close(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'minimize_on_close', param.get_boolean())

    def _on_minimize_on_autojoin(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'minimize_on_autojoin', param.get_boolean())

    def _on_send_chatstate(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'send_chatstate', param.get_string())

    def _on_notify_on_all_messages(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'notify_on_all_messages', param.get_boolean())

    def _on_sync_threshold(self, action, param):
        threshold = param.get_string()
        action.set_state(param)
        app.logger.set_archive_infos(self.contact.jid, sync_threshold=threshold)

    def _on_execute_command(self, action, param):
        """
        Execute AdHoc commands on the current room
        """
        AdHocCommand(self.account, self.room_jid)

    def _on_upload_avatar(self, action, param):
        def _on_accept(filename):
            data, sha = app.interface.avatar_storage.prepare_for_publish(
                filename)
            if sha is None:
                ErrorDialog(
                    _('Could not load image'),
                    transient_for=self.parent_win.window)
                return

            avatar = base64.b64encode(data).decode('utf-8')
            con = app.connections[self.account]
            con.get_module('VCardTemp').upload_room_avatar(
                self.room_jid, avatar)

        AvatarChooserDialog(_on_accept,
                            transient_for=self.parent_win.window,
                            modal=True)

    def show_roster(self):
        new_state = not self.hpaned.get_child2().is_visible()
        image = self.hide_roster_button.get_image()
        if new_state:
            self.hpaned.get_child2().show()
            image.set_from_icon_name('go-next-symbolic', Gtk.IconSize.MENU)
        else:
            self.hpaned.get_child2().hide()
            image.set_from_icon_name('go-previous-symbolic', Gtk.IconSize.MENU)

    def on_groupchat_maximize(self):
        self.set_tooltip()
        self.add_actions()
        self.update_actions()
        self.set_lock_image()
        self._connect_window_state_change(self.parent_win)

    def set_tooltip(self):
        widget = self.xml.get_object('list_treeview')
        if widget.get_tooltip_window():
            return
        widget.set_has_tooltip(True)
        id_ = widget.connect('query-tooltip', self.query_tooltip)
        self.handlers[id_] = widget

    def query_tooltip(self, widget, x_pos, y_pos, keyboard_mode, tooltip):
        try:
            row = self.list_treeview.get_path_at_pos(x_pos, y_pos)[0]
        except TypeError:
            self.gc_tooltip.clear_tooltip()
            return False
        if not row:
            self.gc_tooltip.clear_tooltip()
            return False

        iter_ = None
        try:
            iter_ = self.model.get_iter(row)
        except Exception:
            self.gc_tooltip.clear_tooltip()
            return False

        typ = self.model[iter_][Column.TYPE]
        nick = self.model[iter_][Column.NICK]

        if typ != 'contact':
            self.gc_tooltip.clear_tooltip()
            return False

        contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, nick)
        if not contact:
            self.gc_tooltip.clear_tooltip()
            return False

        value, widget = self.gc_tooltip.get_tooltip(contact)
        tooltip.set_custom(widget)
        return value

    def fill_column(self, col):
        for rend in self.renderers_list:
            col.pack_start(rend[1], rend[2])
            if rend[0] not in ('avatar', 'icon'):
                col.add_attribute(rend[1], rend[3], rend[4])
            col.set_cell_data_func(rend[1], rend[5], rend[6])
        # set renderers properties
        for renderer in self.renderers_propertys:
            renderer.set_property(self.renderers_propertys[renderer][0],
                self.renderers_propertys[renderer][1])

    def tree_compare_iters(self, model, iter1, iter2, data=None):
        """
        Compare two iterators to sort them
        """
        type1 = model[iter1][Column.TYPE]
        type2 = model[iter2][Column.TYPE]
        if not type1 or not type2:
            return 0
        nick1 = model[iter1][Column.NICK]
        nick2 = model[iter2][Column.NICK]
        if not nick1 or not nick2:
            return 0
        if type1 == 'role':
            return locale.strcoll(nick1, nick2)
        if type1 == 'contact':
            gc_contact1 = app.contacts.get_gc_contact(self.account,
                    self.room_jid, nick1)
            if not gc_contact1:
                return 0
        if type2 == 'contact':
            gc_contact2 = app.contacts.get_gc_contact(self.account,
                    self.room_jid, nick2)
            if not gc_contact2:
                return 0
        if type1 == 'contact' and type2 == 'contact' and \
        app.config.get('sort_by_show_in_muc'):
            cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4}
            show1 = cshow[gc_contact1.show.value]
            show2 = cshow[gc_contact2.show.value]
            if show1 < show2:
                return -1
            if show1 > show2:
                return 1
        # We compare names
        name1 = gc_contact1.get_shown_name()
        name2 = gc_contact2.get_shown_name()
        return locale.strcoll(name1.lower(), name2.lower())

    def on_msg_textview_populate_popup(self, textview, menu):
        """
        Override the default context menu and we prepend Clear
        and the ability to insert a nick
        """
        ChatControlBase.on_msg_textview_populate_popup(self, textview, menu)
        item = Gtk.SeparatorMenuItem.new()
        menu.prepend(item)

        item = Gtk.MenuItem.new_with_label(_('Insert Nickname'))
        menu.prepend(item)
        submenu = Gtk.Menu()
        item.set_submenu(submenu)

        for nick in sorted(app.contacts.get_nick_list(self.account,
        self.room_jid)):
            item = Gtk.MenuItem.new_with_label(nick)
            item.set_use_underline(False)
            submenu.append(item)
            id_ = item.connect('activate', self.append_nick_in_msg_textview,
                nick)
            self.handlers[id_] = item

        menu.show_all()

    def resize_occupant_treeview(self, position):
        if self.hpaned.get_position() == position:
            return
        self._resize_from_another_muc = True
        self.hpaned.set_position(position)
        def _reset_flag():
            self._resize_from_another_muc = False
        # Reset the flag when everything will be redrawn, and in particular when
        # on_treeview_size_allocate will have been called.
        GLib.timeout_add(500, _reset_flag)

    def _on_window_state_change(self, win, param):
        # Add with timeout, because state change happens before
        # the hpaned notifys us about a new handle position
        GLib.timeout_add(100, self._check_for_resize)

    def _on_hpaned_release_button(self, hpaned, event):
        if event.get_button()[1] != 1:
            # We want only to catch the left mouse button
            return
        self._check_for_resize()

    def _check_for_resize(self):
        # Check if we have a new position
        pos = self.hpaned.get_position()
        if pos == app.config.get('gc-hpaned-position'):
            return

        # Save new position
        self._remove_handle_timeout()
        app.config.set('gc-hpaned-position', pos)
        # Resize other MUC rosters
        for account in app.gc_connected:
            for room_jid in [i for i in app.gc_connected[account] if \
            app.gc_connected[account][i] and i != self.room_jid]:
                ctrl = app.interface.msg_win_mgr.get_gc_control(room_jid,
                    account)
                if not ctrl and room_jid in \
                app.interface.minimized_controls[account]:
                    ctrl = app.interface.minimized_controls[account][room_jid]
                if ctrl and app.config.get('one_message_window') != 'never':
                    ctrl.resize_occupant_treeview(pos)

    def _on_hpaned_handle_change(self, hpaned, param):
        if self._resize_from_another_muc:
            return
        # Window was resized, save new handle pos
        pos = hpaned.get_position()
        if pos != app.config.get('gc-hpaned-position'):
            self._remove_handle_timeout(renew=True)

    def _remove_handle_timeout(self, renew=False):
        if self._handle_timeout_id is not None:
            GLib.source_remove(self._handle_timeout_id)
            self._handle_timeout_id = None
        if renew:
            pos = self.hpaned.get_position()
            self._handle_timeout_id = GLib.timeout_add_seconds(
                2, self._save_handle_position, pos)

    def _save_handle_position(self, pos):
        self._handle_timeout_id = None
        app.config.set('gc-hpaned-position', pos)

    def iter_contact_rows(self):
        """
        Iterate over all contact rows in the tree model
        """
        role_iter = self.model.get_iter_first()
        while role_iter:
            contact_iter = self.model.iter_children(role_iter)
            while contact_iter:
                yield self.model[contact_iter]
                contact_iter = self.model.iter_next(contact_iter)
            role_iter = self.model.iter_next(role_iter)

    def on_list_treeview_style_set(self, treeview, style):
        """
        When style (theme) changes, redraw all contacts
        """
        # Get the room_jid from treeview
        for contact in self.iter_contact_rows():
            nick = contact[Column.NICK]
            self.draw_contact(nick)

    def get_tab_label(self, chatstate):
        """
        Markup the label if necessary. Returns a tuple such as: (new_label_str,
        color) either of which can be None if chatstate is given that means we
        have HE SENT US a chatstate
        """

        has_focus = self.parent_win.window.get_property('has-toplevel-focus')
        current_tab = self.parent_win.get_active_control() == self
        color = None
        if chatstate == 'attention' and (not has_focus or not current_tab):
            self.attention_flag = True
            color = 'tab-muc-directed-msg'
        elif chatstate == 'active' or (current_tab and has_focus):
            self.attention_flag = False
            # get active color from gtk
            color = 'active'
        elif chatstate == 'newmsg' and (not has_focus or not current_tab) \
        and not self.attention_flag:
            color = 'tab-muc-msg'

        if self.is_continued:
            # if this is a continued conversation
            label_str = self.get_continued_conversation_name()
        else:
            label_str = self.name
        label_str = GLib.markup_escape_text(label_str)

        # count waiting highlighted messages
        unread = ''
        num_unread = self.get_nb_unread()
        if num_unread == 1:
            unread = '*'
        elif num_unread > 1:
            unread = '[' + str(num_unread) + ']'
        label_str = unread + label_str
        return (label_str, color)

    def get_tab_image(self, count_unread=True):
        tab_image = None
        if self.is_connected:
            tab_image = get_icon_name('muc-active')
        else:
            tab_image = get_icon_name('muc-inactive')
        return tab_image

    def update_ui(self):
        ChatControlBase.update_ui(self)
        for nick in app.contacts.get_nick_list(self.account, self.room_jid):
            self.draw_contact(nick)

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

        tooltip = _('%(type)s encryption is active %(authenticated)s.') % {
            'type': enc_type, 'authenticated': authenticated_string}

        self.authentication_button.set_tooltip_text(tooltip)
        self.widget_set_visible(self.authentication_button, not visible)
        self.lock_image.set_sensitive(visible)

    def _on_authentication_button_clicked(self, widget):
        app.plugin_manager.extension_point(
            'encryption_dialog' + self.encryption, self)

    def _change_style(self, model, path, iter_, option):
        model[iter_][Column.NICK] = model[iter_][Column.NICK]

    def change_roster_style(self):
        self.model.foreach(self._change_style, None)

    def repaint_themed_widgets(self):
        ChatControlBase.repaint_themed_widgets(self)
        self.change_roster_style()

    def _update_banner_state_image(self):
        banner_status_img = self.xml.get_object('gc_banner_status_image')
        if self.is_connected:
            if self.contact.avatar_sha:
                surface = app.interface.get_avatar(self.contact,
                                                   AvatarSize.ROSTER,
                                                   self.scale_factor)
                banner_status_img.set_from_surface(surface)
                return
            icon = get_icon_name('muc-active')
        else:
            icon = get_icon_name('muc-inactive')
        banner_status_img.set_from_icon_name(icon, Gtk.IconSize.DND)

    def get_continued_conversation_name(self):
        """
        Get the name of a continued conversation.  Will return Continued
        Conversation if there isn't any other contact in the room
        """
        nicks = []
        for nick in app.contacts.get_nick_list(self.account,
        self.room_jid):
            if nick != self.nick:
                nicks.append(nick)
        if nicks != []:
            title = ', '
            title = _('Conversation with ') + title.join(nicks)
        else:
            title = _('Continued conversation')
        return title

    def draw_banner_text(self):
        """
        Draw the text in the fat line at the top of the window that houses the
        room jid, subject
        """
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        if self.is_continued:
            name = self.get_continued_conversation_name()
        else:
            name = self.room_jid

        self.name_label.set_text(name)

        if self.subject:
            subject = GLib.markup_escape_text(self.subject)
            subject_text = self.urlfinder.sub(self.make_href, subject)
            self.subject_button.get_popover().set_text(subject_text)

    def _nec_update_avatar(self, obj):
        if obj.contact.room_jid != self.room_jid:
            return
        app.log('avatar').debug('Draw Groupchat Avatar: %s %s',
                                obj.contact.name, obj.contact.avatar_sha)
        self.draw_avatar(obj.contact)

    def _nec_update_room_avatar(self, obj):
        if obj.jid != self.room_jid:
            return
        self._update_banner_state_image()

    @event_filter(['account', 'room_jid'])
    def _on_voice_approval(self, event):
        SingleMessageWindow(self.account,
                            self.room_jid,
                            action='receive',
                            from_whom=self.room_jid,
                            form_node=event.form)

    @event_filter(['account'])
    def _nec_mam_decrypted_message_received(self, obj):
        if not obj.groupchat:
            return
        if obj.archive_jid != self.room_jid:
            return
        self.add_message(
            obj.msgtxt, contact=obj.nick,
            tim=obj.timestamp, correct_id=obj.correct_id,
            encrypted=obj.encrypted,
            message_id=obj.message_id,
            additional_data=obj.additional_data)

    @event_filter(['account', 'room_jid'])
    def _nec_gc_message_received(self, obj):
        if not obj.nick:
            # message from server
            self.add_message(
                obj.msgtxt, tim=obj.timestamp,
                xhtml=obj.xhtml_msgtxt, displaymarking=obj.displaymarking,
                additional_data=obj.additional_data)
        else:
            if obj.nick == self.nick:
                self.last_sent_txt = obj.msgtxt
            self.add_message(
                obj.msgtxt, contact=obj.nick,
                tim=obj.timestamp, xhtml=obj.xhtml_msgtxt,
                displaymarking=obj.displaymarking, encrypted=obj.encrypted,
                correct_id=obj.correct_id, message_id=obj.message_id,
                additional_data=obj.additional_data)
        obj.needs_highlight = self.needs_visual_notification(obj.msgtxt)

    def on_private_message(self, nick, sent, msg, tim, xhtml, session, msg_log_id=None,
    encrypted=False, displaymarking=None):
        # Do we have a queue?
        fjid = self.room_jid + '/' + nick
        no_queue = len(app.events.get_events(self.account, fjid)) == 0

        event = events.PmEvent(msg, '', 'incoming', tim, encrypted, '',
            msg_log_id, xhtml=xhtml, session=session, form_node=None,
            displaymarking=displaymarking, sent_forwarded=sent)
        app.events.add_event(self.account, fjid, event)

        autopopup = app.config.get('autopopup')
        autopopupaway = app.config.get('autopopupaway')
        iter_ = self.get_contact_iter(nick)
        path = self.model.get_path(iter_)
        if not autopopup or (not autopopupaway and \
        app.connections[self.account].connected > 2):
            if no_queue: # We didn't have a queue: we change icons
                transport = None
                if app.jid_is_transport(self.room_jid):
                    transport = app.get_transport_name_from_jid(self.room_jid)
                self.model[iter_][Column.IMG] = get_icon_name(
                    'event', transport=transport)
            if self.parent_win:
                self.parent_win.show_title()
                self.parent_win.redraw_tab(self)
        else:
            self._start_private_message(nick)
        # Scroll to line
        path_ = path.copy()
        path_.up()
        self.list_treeview.expand_row(path_, False)
        self.list_treeview.scroll_to_cell(path)
        self.list_treeview.set_cursor(path)
        contact = app.contacts.get_contact_with_highest_priority(
            self.account, self.room_jid)
        if contact:
            app.interface.roster.draw_contact(self.room_jid, self.account)

    def get_contact_iter(self, nick: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._contact_refs[nick]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self.model.get_iter(path)

    def add_message(self, text, contact='', tim=None, xhtml=None,
                    displaymarking=None, correct_id=None, message_id=None,
                    encrypted=None, additional_data=None):
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

            self.check_and_possibly_add_focus_out_line()

        ChatControlBase.add_message(self, text, kind, contact, tim,
            other_tags_for_name, [], other_tags_for_text, xhtml=xhtml,
            displaymarking=displaymarking,
            correct_id=correct_id, message_id=message_id, encrypted=encrypted,
            additional_data=additional_data)

    def get_nb_unread(self):
        type_events = ['printed_marked_gc_msg']
        if app.config.notify_for_muc(self.room_jid):
            type_events.append('printed_gc_msg')
        nb = len(app.events.get_events(self.account, self.room_jid,
            type_events))
        nb += self.get_nb_unread_pm()
        return nb

    def get_nb_unread_pm(self):
        nb = 0
        for nick in app.contacts.get_nick_list(self.account, self.room_jid):
            nb += len(app.events.get_events(self.account, self.room_jid + \
                '/' + nick, ['pm']))
        return nb

    def highlighting_for_message(self, text, tim):
        """
        Returns a 2-Tuple. The first says whether or not to highlight the text,
        the second, what sound to play
        """
        highlight, sound = None, None

        notify = app.config.notify_for_muc(self.room_jid)
        message_sound_enabled = app.config.get_per('soundevents',
                                                   'muc_message_received',
                                                   'enabled')

        # Are any of the defined highlighting words in the text?
        if self.needs_visual_notification(text):
            highlight = True
            if app.config.get_per('soundevents',
                                  'muc_message_highlight',
                                  'enabled'):
                sound = 'highlight'

        # Do we play a sound on every muc message?
        elif notify and message_sound_enabled:
            sound = 'received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim is not None and time.mktime(time.localtime()) - tim > 1:
            sound = None

        return highlight, sound

    def check_and_possibly_add_focus_out_line(self):
        """
        Check and possibly add focus out line for room_jid if it needs it and
        does not already have it as last event. If it goes to add this line
        - remove previous line first
        """
        win = app.interface.msg_win_mgr.get_window(self.room_jid,
            self.account)
        if win and self.room_jid == win.get_active_jid() and\
        win.window.get_property('has-toplevel-focus') and\
        self.parent_win.get_active_control() == self:
            # it's the current room and it's the focused window.
            # we have full focus (we are reading it!)
            return

        self.conv_textview.show_focus_out_line()

    def needs_visual_notification(self, text):
        """
        Check text to see whether any of the words in (muc_highlight_words and
        nick) appear
        """
        special_words = app.config.get('muc_highlight_words').split(';')
        special_words.append(self.nick)
        con = app.connections[self.account]
        special_words.append(con.get_own_jid().getStripped())
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

    def set_subject(self, subject):
        self.subject = subject
        self.draw_banner_text()

    @event_filter(['account', 'room_jid'])
    def _on_subject(self, event):
        if self.subject == event.subject or event.is_fake:
            # Probably a rejoin, we already showed that subject
            return
        self.set_subject(event.subject)
        text = _('%(nick)s has set the subject to %(subject)s') % {
            'nick': event.nickname, 'subject': event.subject}

        if event.user_timestamp:
            date = time.strftime('%d-%m-%Y %H:%M:%S',
                                 time.localtime(event.user_timestamp))
            text = '%s - %s' % (text, date)

        if (app.config.get('show_subject_on_join') or
                self._muc_data.state != MUCJoinedState.JOINED):
            self.add_info_message(text)

        if not event.subject:
            self.subject_button.hide()
        else:
            self.subject_button.show()

    @event_filter(['account', 'room_jid'])
    def _on_config_changed(self, event):
        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
        changes = []
        if StatusCode.SHOWING_UNAVAILABLE in event.status_codes:
            changes.append(_('Group chat now shows unavailable members'))

        if StatusCode.NOT_SHOWING_UNAVAILABLE in event.status_codes:
            changes.append(_('Group chat now does not show unavailable members'))

        if StatusCode.CONFIG_NON_PRIVACY_RELATED in event.status_codes:
            changes.append(_('A setting not related to privacy has been '
                             'changed'))
            app.connections[self.account].get_module('Discovery').disco_muc(
                self.room_jid, self.update_actions, update=True)

        if StatusCode.CONFIG_ROOM_LOGGING in event.status_codes:
            # Can be a presence (see chg_contact_status in groupchat_control.py)
            changes.append(_('Conversations are stored on the server'))

        if StatusCode.CONFIG_NO_ROOM_LOGGING in event.status_codes:
            changes.append(_('Conversations are not stored on the server'))

        if StatusCode.CONFIG_NON_ANONYMOUS in event.status_codes:
            changes.append(_('Group chat is now non-anonymous'))
            self.is_anonymous = False

        if StatusCode.CONFIG_SEMI_ANONYMOUS in event.status_codes:
            changes.append(_('Group chat is now semi-anonymous'))
            self.is_anonymous = True

        if StatusCode.CONFIG_FULL_ANONYMOUS in event.status_codes:
            changes.append(_('Group chat is now fully anonymous'))
            self.is_anonymous = True

        for change in changes:
            self.add_info_message(change)

    def _nec_signed_in(self, obj):
        if obj.conn.name != self.account:
            return
        obj.conn.get_module('MUC').join(self._muc_data)

    def _nec_decrypted_message_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.gc_control == self and obj.resource:
            # We got a pm from this room
            nick = obj.resource
            if obj.session.control:
                # print if a control is open
                frm = ''
                if obj.sent:
                    frm = 'out'
                obj.session.control.add_message(obj.msgtxt, frm,
                    tim=obj.timestamp, xhtml=obj.xhtml, encrypted=obj.encrypted,
                    displaymarking=obj.displaymarking, message_id=obj.message_id,
                    correct_id=obj.correct_id)
            else:
                # otherwise pass it off to the control to be queued
                self.on_private_message(nick, obj.sent, obj.msgtxt, obj.timestamp,
                    obj.xhtml, self.session, msg_log_id=obj.msg_log_id,
                    encrypted=obj.encrypted, displaymarking=obj.displaymarking)

    def _nec_ping(self, obj):
        if self.contact.jid != obj.contact.room_jid:
            return

        nick = obj.contact.get_shown_name()
        if obj.name == 'ping-sent':
            self.add_info_message(_('Ping? (%s)') % nick)
        elif obj.name == 'ping-reply':
            self.add_info_message(
                _('Pong! (%(nick)s %(delay)s s.)') % {'nick': nick,
                'delay': obj.seconds})
        elif obj.name == 'ping-error':
            self.add_info_message(_('Error.'))

    @property
    def is_connected(self) -> bool:
        return app.gc_connected[self.account][self.room_jid]

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        app.gc_connected[self.account][self.room_jid] = value

    def _disable_roster_sort(self):
        self.model.set_sort_column_id(Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID,
                                      Gtk.SortType.ASCENDING)
        self.list_treeview.set_model(None)

    def _enable_roster_sort(self):
        self.model.set_sort_column_id(Column.NICK, Gtk.SortType.ASCENDING)
        self.list_treeview.set_model(self.model)
        self.list_treeview.expand_all()

    def _reset_roster(self):
        self._contact_refs = {}
        self._role_refs = {}
        self.model.clear()

    def got_connected(self):
        # Make autorejoin stop.
        if self.autorejoin:
            GLib.source_remove(self.autorejoin)
        self.autorejoin = None

        if muc_caps_cache.has_mam(self.room_jid):
            # Request MAM
            con = app.connections[self.account]
            con.get_module('MAM').request_archive_on_muc_join(
                self.room_jid)

        self.is_connected = True
        ChatControlBase.got_connected(self)

        # Sort model and assign it to treeview
        self._enable_roster_sort()

        # We don't redraw the whole banner here, because only icon change
        self._update_banner_state_image()
        if self.parent_win:
            self.parent_win.redraw_tab(self)

        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(True)

        self.update_actions()

    def got_disconnected(self):
        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(False)

        self._reset_roster()
        self._disable_roster_sort()

        for contact in app.contacts.get_gc_contact_list(
                self.account, self.room_jid):
            contact.presence = PresenceType.UNAVAILABLE
            ctrl = app.interface.msg_win_mgr.get_control(contact.get_full_jid,
                                                         self.account)
            if ctrl:
                ctrl.got_disconnected()

            app.contacts.remove_gc_contact(self.account, contact)

        self.is_connected = False
        ChatControlBase.got_disconnected(self)

        con = app.connections[self.account]
        con.get_module('Chatstate').remove_delay_timeout(self.contact)

        contact = app.contacts.get_groupchat_contact(self.account,
                                                     self.room_jid)
        if contact is not None:
            app.interface.roster.draw_contact(self.room_jid, self.account)

        # We don't redraw the whole banner here, because only icon change
        self._update_banner_state_image()
        if self.parent_win:
            self.parent_win.redraw_tab(self)

        # Autorejoin stuff goes here.
        # Notice that we don't need to activate autorejoin if connection is lost
        # or in progress.
        if self.autorejoin is None and app.account_is_connected(self.account):
            ar_to = app.config.get('muc_autorejoin_timeout')
            if ar_to:
                self.autorejoin = GLib.timeout_add_seconds(ar_to, self.rejoin)

        self.update_actions()

    def leave(self, reason=None):
        app.connections[self.account].get_module('MUC').leave(self.room_jid,
                                                              reason=reason)
        self.got_disconnected()
        self._close_control()

    def rejoin(self):
        if not self.autorejoin:
            return False
        app.connections[self.account].get_module('MUC').join(self._muc_data)
        return True

    def draw_roster(self):
        self._reset_roster()
        self._disable_roster_sort()

        for nick in app.contacts.get_nick_list(self.account, self.room_jid):
            self.add_contact_to_roster(nick)

        self._enable_roster_sort()
        self.draw_all_roles()
        # Recalculate column width for ellipsizin
        self.list_treeview.columns_autosize()

    def on_send_pm(self, widget=None, model=None, iter_=None, nick=None,
    msg=None):
        """
        Open a chat window and if msg is not None - send private message to a
        contact in a room
        """
        if nick is None:
            nick = model[iter_][Column.NICK]

        ctrl = self._start_private_message(nick)
        if ctrl and msg:
            ctrl.send_message(msg)

    def draw_contact(self, nick):
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return

        gc_contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, nick)

        if app.events.get_events(self.account, self.room_jid + '/' + nick):
            icon_name = get_icon_name('event')
        else:
            icon_name = get_icon_name(gc_contact.show.value)

        name = GLib.markup_escape_text(gc_contact.name)

        # Strike name if blocked
        fjid = self.room_jid + '/' + nick
        if helpers.jid_is_blocked(self.account, fjid):
            name = '<span strikethrough="true">%s</span>' % name

        status = gc_contact.status
        # add status msg, if not empty, under contact name in the treeview
        if status and app.config.get('show_status_msgs_in_roster'):
            status = status.strip()
            if status != '':
                status = helpers.reduce_chars_newlines(status, max_lines=1)
                # escape markup entities and make them small italic and fg color
                name += ('\n<span size="small" style="italic" alpha="70%">'
                         '{}</span>'.format(GLib.markup_escape_text(status)))

        if (not gc_contact.affiliation.is_none and
                app.config.get('show_affiliation_in_groupchat')):
            icon_name += ':%s' % gc_contact.affiliation.value

        self.model[iter_][Column.IMG] = icon_name
        self.model[iter_][Column.TEXT] = name

    def draw_avatar(self, gc_contact):
        if not app.config.get('show_avatars_in_roster'):
            return
        iter_ = self.get_contact_iter(gc_contact.name)
        if not iter_:
            return

        surface = app.interface.get_avatar(
            gc_contact, AvatarSize.ROSTER, self.scale_factor)
        image = Gtk.Image.new_from_surface(surface)
        self.model[iter_][Column.AVATAR_IMG] = image

    def draw_role(self, role):
        role_iter = self.get_role_iter(role)
        if not role_iter:
            return
        role_name = helpers.get_uf_role(role, plural=True)
        if app.config.get('show_contacts_number'):
            nbr_role, nbr_total = app.contacts.get_nb_role_total_gc_contacts(
                self.account, self.room_jid, role)
            role_name += ' (%s/%s)' % (repr(nbr_role), repr(nbr_total))
        self.model[role_iter][Column.TEXT] = role_name

    def draw_all_roles(self):
        for role in (Role.VISITOR, Role.PARTICIPANT, Role.MODERATOR):
            self.draw_role(role)

    @event_filter(['account', 'room_jid'])
    def _on_self_presence(self, event):
        nick = event.properties.muc_nickname
        status_codes = event.properties.muc_status_codes or []

        if not self.is_connected:
            # We just joined the room
            self.add_info_message(_('You (%s) joined the group chat') % nick)
            self.add_contact_to_roster(nick)

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

    @event_filter(['account', 'room_jid'])
    def _on_configuration_finished(self, _event):
        self.add_info_message(_('A new group chat has been created'))

    @event_filter(['account', 'room_jid'])
    def _on_nickname_changed(self, event):
        nick = event.properties.muc_nickname
        new_nick = event.properties.muc_user.nick
        if event.properties.is_muc_self_presence:
            self._nick_completion.change_nick(new_nick)
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)
            self._nick_completion.contact_renamed(nick, new_nick)

        self.add_info_message(message)

        tv = self.conv_textview
        if nick in tv.last_received_message_id:
            tv.last_received_message_id[new_nick] = \
                tv.last_received_message_id[nick]
            del tv.last_received_message_id[nick]

        self.remove_contact(nick)
        self.add_contact_to_roster(new_nick)

    @event_filter(['account', 'room_jid'])
    def _on_status_show_changed(self, event):
        nick = event.properties.muc_nickname
        status = event.properties.status
        status = '' if status is None else ' - %s' % status
        show = helpers.get_uf_show(event.properties.show.value)

        status_default = app.config.get('print_status_muc_default')

        if event.properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)
            self.add_status_message(message)

        elif app.config.get_per('rooms', self.room_jid,
                                'print_status', status_default):
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
            self.add_status_message(message)

        self.draw_contact(nick)

    @event_filter(['account', 'room_jid'])
    def _on_affiliation_changed(self, event):
        affiliation = helpers.get_uf_affiliation(
            event.properties.affiliation)
        nick = event.properties.muc_nickname
        reason = event.properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = event.properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if event.properties.is_muc_self_presence:
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
        self.draw_contact(nick)
        self.update_actions()

    @event_filter(['account', 'room_jid'])
    def _on_role_changed(self, event):
        role = helpers.get_uf_role(event.properties.role)
        nick = event.properties.muc_nickname
        reason = event.properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = event.properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if event.properties.is_muc_self_presence:
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
        self.remove_contact(nick)
        self.add_contact_to_roster(nick)
        self.update_actions()

    @event_filter(['account', 'room_jid'])
    def _on_self_kicked(self, event):
        self.autorejoin = False

        status_codes = event.properties.muc_status_codes or []

        reason = event.properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = event.properties.muc_user.actor
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
            self.autorejoin = True

        self.got_disconnected()

        # Update Actions
        self.update_actions()

    @event_filter(['account', 'room_jid'])
    def _on_user_left(self, event):
        status_codes = event.properties.muc_status_codes or []
        nick = event.properties.muc_nickname

        reason = event.properties.muc_user.reason
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        actor = event.properties.muc_user.actor
        #Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        #Group Chat: We have been removed from the room
        message = _('{nick} has been removed from the group chat{by}{reason}')

        join_default = app.config.get('print_join_left_default')
        print_join_left = app.config.get_per(
            'rooms', self.room_jid, 'print_join_left', join_default)

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
            message = message.format(nick=nick, actor=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(nick=nick, actor=actor, reason=reason)
            self.add_info_message(message)

        elif print_join_left:
            message = _('{nick} has left{reason}').format(nick=nick,
                                                          reason=reason)
            self.add_info_message(message)

        self.remove_contact(nick)
        self.draw_all_roles()

    @event_filter(['account', 'room_jid'])
    def _on_muc_joined(self, _event):
        self.got_connected()
        self._show_page('groupchat')

    @event_filter(['account', 'room_jid'])
    def _on_user_joined(self, event):
        nick = event.properties.muc_nickname
        join_default = app.config.get('print_join_left_default')
        print_join_left = app.config.get_per(
            'rooms', self.room_jid, 'print_join_left', join_default)

        self.add_contact_to_roster(nick)

        if self.is_connected and print_join_left:
            self.add_info_message(_('%s has joined the group chat') % nick)

    @event_filter(['account', 'room_jid'])
    def _on_password_required(self, _event):
        self._show_page('password')

    @event_filter(['account', 'room_jid'])
    def _on_muc_join_failed(self, event):
        self.xml.error_label.set_text(event.properties.error.message)
        self._show_page('error')
        self.autorejoin = False

    @event_filter(['account', 'room_jid'])
    def _on_presence_error(self, event):
        error_type = event.properties.error.type
        error_message = event.properties.error.message

        self.add_info_message(
            'Error %s: %s' % (error_type.value, error_message))

    def add_contact_to_roster(self, nick):
        contact = app.contacts.get_gc_contact(self.account,
                                              self.room_jid,
                                              nick)
        role_name = helpers.get_uf_role(contact.role, plural=True)

        # Create Role
        role_iter = self.get_role_iter(contact.role)
        if not role_iter:
            icon_name = get_icon_name('closed')
            ext_columns = [None] * self.nb_ext_renderers
            row = [icon_name, contact.role.value,
                   'role', role_name, None] + ext_columns
            role_iter = self.model.append(None, row)
            self._role_refs[contact.role] = Gtk.TreeRowReference(
                self.model, self.model.get_path(role_iter))

        # Avatar
        image = None
        if app.config.get('show_avatars_in_roster'):
            surface = app.interface.get_avatar(
                contact, AvatarSize.ROSTER, self.scale_factor)
            image = Gtk.Image.new_from_surface(surface)

        # Add to model
        ext_columns = [None] * self.nb_ext_renderers
        row = [None, nick, 'contact', nick, image] + ext_columns
        iter_ = self.model.append(role_iter, row)
        self._contact_refs[nick] = Gtk.TreeRowReference(
            self.model, self.model.get_path(iter_))

        self.draw_all_roles()
        self.draw_contact(nick)

        if self.list_treeview.get_model():
            self.list_treeview.expand_row(
                (self.model.get_path(role_iter)), False)
        if self.is_continued:
            self.draw_banner_text()

    @event_filter(['account', 'room_jid'])
    def _on_destroyed(self, event):
        destroyed = event.properties.muc_destroyed

        reason = destroyed.reason
        reason = '' if reason is None else ': %s' % reason

        message = _('Group chat has been destroyed')
        self.add_info_message(message)

        alternate = destroyed.alternate
        if alternate is not None:
            join_message = _('You can join this group chat '
                             'instead: xmpp:%s?join') % alternate
            self.add_info_message(join_message)

        self.autorejoin = False
        self.got_disconnected()

        con = app.connections[self.account]
        con.get_module('Bookmarks').remove(self.room_jid)

        if self._wait_for_destruction:
            self._close_control()

    def get_role_iter(self, role: str) -> Optional[Gtk.TreeIter]:
        try:
            ref = self._role_refs[role]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self.model.get_iter(path)


    def remove_contact(self, nick):
        """
        Remove a user from the contacts_list
        """
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return

        parent_iter = self.model.iter_parent(iter_)
        if parent_iter is None:
            # This is not a child, should never happen
            return
        self.model.remove(iter_)
        del self._contact_refs[nick]
        if self.model.iter_n_children(parent_iter) == 0:
            role = self.model[parent_iter][Column.NICK]
            del self._role_refs[Role(role)]
            self.model.remove(parent_iter)

    @event_filter(['account'])
    def _message_sent(self, obj):
        if not obj.message:
            return
        if obj.jid != self.room_jid:
            return
        # we'll save sent message text when we'll receive it in
        # _nec_gc_message_received
        self.last_sent_msg = obj.stanza_id
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
            con = app.connections[self.account]
            chatstate = con.get_module('Chatstate').get_active_chatstate(
                self.contact)

            # Send the message
            app.nec.push_outgoing_event(GcMessageOutgoingEvent(
                None, account=self.account, jid=self.room_jid, message=message,
                xhtml=xhtml, label=label, chatstate=chatstate,
                correct_id=correct_id, automatic_message=False))
            self.msg_textview.get_buffer().set_text('')
            self.msg_textview.grab_focus()

    def get_role(self, nick):
        gc_contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, nick)
        if gc_contact:
            return gc_contact.role
        return Role.VISITOR

    def minimizable(self):
        if self.force_non_minimizable:
            return False
        return app.config.get_per('rooms', self.contact.jid,
                                  'minimize_on_close', True)

    def minimize(self, status='offline'):
        # Minimize it
        win = app.interface.msg_win_mgr.get_window(self.contact.jid,
                self.account)
        ctrl = win.get_control(self.contact.jid, self.account)

        ctrl_page = win.notebook.page_num(ctrl.widget)
        control = win.notebook.get_nth_page(ctrl_page)

        win.notebook.remove_page(ctrl_page)
        control.unparent()
        ctrl.parent_win = None

        # Stop correcting message when we minimize
        if self.correcting:
            self.correcting = False
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'gajim-msg-correcting')
            self.msg_textview.get_buffer().set_text('')

        con = app.connections[self.account]
        con.get_module('Chatstate').set_chatstate(self.contact, Chatstate.INACTIVE)

        app.interface.roster.minimize_groupchat(
            self.account, self.contact.jid, status=self.subject)

        del win._controls[self.account][self.contact.jid]

    def shutdown(self, status='offline'):
        # PluginSystem: calling shutdown of super class (ChatControlBase)
        # to let it remove it's GUI extension points
        super(GroupchatControl, self).shutdown()
        # PluginSystem: removing GUI extension points connected with
        # GrouphatControl instance object
        app.plugin_manager.remove_gui_extension_point('groupchat_control',
            self)

        # Preventing autorejoin from being activated
        self.autorejoin = False

        # Unregister handlers
        for handler in self._event_handlers:
            app.ged.remove_event_handler(*handler)

        nick_list = app.contacts.get_nick_list(self.account, self.room_jid)
        for nick in nick_list:
            # Update pm chat window
            fjid = self.room_jid + '/' + nick
            ctrl = app.interface.msg_win_mgr.get_gc_control(fjid,
                self.account)
            if ctrl:
                contact = app.contacts.get_gc_contact(self.account,
                    self.room_jid, nick)
                contact.show = 'offline'
                contact.status = ''
                ctrl.update_ui()
                ctrl.parent_win.redraw_tab(ctrl)

        # They can already be removed by the destroy function
        if self.room_jid in app.contacts.get_gc_list(self.account):
            app.contacts.remove_room(self.account, self.room_jid)
            del app.gc_connected[self.account][self.room_jid]

        # Save hpaned position
        app.config.set('gc-hpaned-position', self.hpaned.get_position())
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]
        # Remove unread events from systray
        app.events.remove_events(self.account, self.room_jid)

    def safe_shutdown(self):
        if self.minimizable():
            return True
        includes = app.config.get('confirm_close_muc_rooms').split(' ')
        excludes = app.config.get('noconfirm_close_muc_rooms').split(' ')
        # whether to ask for confirmation before closing muc
        if (app.config.get('confirm_close_muc') or self.room_jid in includes)\
        and self.is_connected and self.room_jid not in excludes:
            return False
        return True

    def allow_shutdown(self, method, on_yes, on_no, on_minimize):
        if self.minimizable():
            on_minimize(self)
            return
        if method == self.parent_win.CLOSE_ESC:
            iter_ = self.list_treeview.get_selection().get_selected()[1]
            if iter_:
                self.list_treeview.get_selection().unselect_all()
                on_no(self)
                return
        includes = app.config.get('confirm_close_muc_rooms').split(' ')
        excludes = app.config.get('noconfirm_close_muc_rooms').split(' ')
        # whether to ask for confirmation before closing muc
        if (app.config.get('confirm_close_muc') or self.room_jid in includes)\
        and self.is_connected and self.room_jid \
        not in excludes:

            def on_ok(is_checked):
                if is_checked:
                    # User does not want to be asked again
                    app.config.set('confirm_close_muc', False)
                on_yes(self)

            def on_cancel(is_checked):
                if is_checked:
                    # User does not want to be asked again
                    app.config.set('confirm_close_muc', False)
                on_no(self)

            NewConfirmationCheckDialog(
                _('Leave Group Chat'),
                _('Are you sure you want to leave this group chat?'),
                _('If you close this window, you will leave '
                  '\'%s\'.') % self.name,
                _('_Do not ask me again'),
                [DialogButton.make('Cancel',
                                   callback=on_cancel),
                 DialogButton.make('OK',
                                   text=_('_Leave'),
                                   callback=on_ok)],
                transient_for=self.parent_win.window).show()
            return

        on_yes(self)

    def _close_control(self):
        if self.parent_win is None:
            self.shutdown()
        else:
            self.parent_win.remove_tab(self, None, force=True)

    def set_control_active(self, state):
        self.conv_textview.allow_focus_out_line = True
        self.attention_flag = False
        ChatControlBase.set_control_active(self, state)
        if not state:
            # add the focus-out line to the tab we are leaving
            self.check_and_possibly_add_focus_out_line()
        # Sending active to undo unread state
        self.parent_win.redraw_tab(self, 'active')

    def get_specific_unread(self):
        # returns the number of the number of unread msgs
        # for room_jid & number of unread private msgs with each contact
        # that we have
        nb = 0
        for nick in app.contacts.get_nick_list(self.account, self.room_jid):
            fjid = self.room_jid + '/' + nick
            nb += len(app.events.get_events(self.account, fjid))
            # gc can only have messages as event
        return nb

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        if not selection.get_data():
            return

        # Get contact info
        contact = contacts.Contact(jid=self.room_jid, account=self.account)
        if target_type == self.TARGET_TYPE_URI_LIST:
            # File drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(contact, selection, self)
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

            con = app.connections[self.account]
            con.get_module('MUC').invite(self.room_jid, contact_jid)
            self.add_info_message(_('%(jid)s has been invited to this group chat') %
                                    {'jid': contact_jid})

    def _jid_not_blocked(self, bare_jid: str) -> bool:
        fjid = self.room_jid + '/' + bare_jid
        return not helpers.jid_is_blocked(self.account, fjid)

    def _on_message_textview_key_press_event(self, widget, event):
        res = ChatControlBase._on_message_textview_key_press_event(self, widget,
            event)
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

            gc_refer_to_nick_char = app.config.get('gc_refer_to_nick_char')
            with_refer_to_nick_char = False
            after_nick_len = 1 # the space that is printed after we type [Tab]

            # first part of this if : works fine even if refer_to_nick_char
            if gc_refer_to_nick_char and text.endswith(
            gc_refer_to_nick_char + ' '):
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
                list_nick = app.contacts.get_nick_list(self.account,
                                                         self.room_jid)
                list_nick = list(filter(self._jid_not_blocked, list_nick))

                log.debug("Nicks to be considered for autosuggestions: %s",
                          list_nick)
                self.nick_hits = self._nick_completion.generate_suggestions(
                    nicks=list_nick, beginning=begin)
                log.debug("Nicks filtered for autosuggestions: %s",
                          self.nick_hits)

            if self.nick_hits:
                if len(splitted_text) < 2 or with_refer_to_nick_char:
                    # This is the 1st word of the line or no word or we are cycling
                    # at the beginning, possibly with a space in one nick
                    add = gc_refer_to_nick_char + ' '
                else:
                    add = ' '
                start_iter = end_iter.copy()
                if self.last_key_tabs and with_refer_to_nick_char or (text and \
                                                                      text[-1] == ' '):
                    # have to accommodate for the added space from last
                    # completion
                    # gc_refer_to_nick_char may be more than one char!
                    start_iter.backward_chars(len(begin) + len(add))
                elif self.last_key_tabs and not app.config.get(
                    'shell_like_completion'):
                    # have to accommodate for the added space from last
                    # completion
                    start_iter.backward_chars(len(begin) + \
                                              len(gc_refer_to_nick_char))
                else:
                    start_iter.backward_chars(len(begin))

                con = app.connections[self.account]
                con.get_module('Chatstate').block_chatstates(self.contact, True)

                message_buffer.delete(start_iter, end_iter)
                # get a shell-like completion
                # if there's more than one nick for this completion, complete
                # only the part that all these nicks have in common
                if app.config.get('shell_like_completion') and \
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

                con.get_module('Chatstate').block_chatstates(self.contact, False)

                self.last_key_tabs = True
                return True
            self.last_key_tabs = False

    def on_list_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            selection = widget.get_selection()
            iter_ = selection.get_selected()[1]
            if iter_:
                widget.get_selection().unselect_all()
                return True

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
            elif self._get_current_page() in ('error', 'captcha-error'):
                self._on_page_close_clicked()
            else:
                self._show_page('groupchat')
            return Gdk.EVENT_STOP

        if action == 'change-subject':
            control_action = '%s-%s' % (action, self.control_id)
            self.parent_win.window.lookup_action(control_action).activate()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def on_list_treeview_row_expanded(self, widget, iter_, path):
        """
        When a row is expanded: change the icon of the arrow
        """
        model = widget.get_model()
        model[iter_][Column.IMG] = get_icon_name('opened')

    def on_list_treeview_row_collapsed(self, widget, iter_, path):
        """
        When a row is collapsed: change the icon of the arrow
        """
        model = widget.get_model()
        model[iter_][Column.IMG] = get_icon_name('closed')

    def kick(self, widget, nick):
        """
        Kick a user
        """
        def on_ok(reason):
            con = app.connections[self.account]
            con.get_module('MUC').set_role(self.room_jid, nick, 'none', reason)

        # ask for reason
        InputDialog(_('Kicking %s') % nick,
            _('You may specify a reason below:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def mk_menu(self, event, iter_):
        """
        Make contact's popup menu
        """
        nick = self.model[iter_][Column.NICK]
        c = app.contacts.get_gc_contact(self.account, self.room_jid, nick)
        fjid = self.room_jid + '/' + nick
        jid = c.jid
        target_affiliation = c.affiliation
        target_role = c.role

        # looking for user's affiliation and role
        user_nick = self.nick
        user_affiliation = app.contacts.get_gc_contact(self.account,
            self.room_jid, user_nick).affiliation
        user_role = self.get_role(user_nick)

        # making menu from gtk builder
        xml = get_builder('gc_occupants_menu.ui')

        # these conditions were taken from JEP 0045
        item = xml.get_object('kick_menuitem')
        if not user_role.is_moderator or \
        (user_affiliation.is_admin and target_affiliation.is_owner) or \
        (user_affiliation.is_member and target_affiliation in (Affiliation.ADMIN,
        Affiliation.OWNER)) or (user_affiliation.is_none and not target_affiliation.is_none):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.kick, nick)
        self.handlers[id_] = item

        item = xml.get_object('voice_checkmenuitem')
        item.set_active(not target_role.is_visitor)
        if not user_role.is_moderator or \
        user_affiliation.is_none or \
        (user_affiliation.is_member and not target_affiliation.is_none) or \
        target_affiliation in (Affiliation.ADMIN, Affiliation.OWNER):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_voice_checkmenuitem_activate,
            nick)
        self.handlers[id_] = item

        item = xml.get_object('moderator_checkmenuitem')
        item.set_active(target_role.is_moderator)
        if not user_affiliation in (Affiliation.ADMIN, Affiliation.OWNER) or \
        target_affiliation in (Affiliation.ADMIN, Affiliation.OWNER):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_moderator_checkmenuitem_activate,
            nick)
        self.handlers[id_] = item

        item = xml.get_object('ban_menuitem')
        if not user_affiliation in (Affiliation.ADMIN, Affiliation.OWNER) or \
        (target_affiliation in (Affiliation.ADMIN, Affiliation.OWNER) and\
        not user_affiliation.is_owner):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.ban, jid)
        self.handlers[id_] = item

        item = xml.get_object('member_checkmenuitem')
        item.set_active(not target_affiliation.is_none)
        if not user_affiliation in (Affiliation.ADMIN, Affiliation.OWNER) or \
        (not user_affiliation.is_owner and target_affiliation in (Affiliation.ADMIN, Affiliation.OWNER)):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_member_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('admin_checkmenuitem')
        item.set_active(target_affiliation in (Affiliation.ADMIN, Affiliation.OWNER))
        if not user_affiliation.is_owner:
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_admin_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('owner_checkmenuitem')
        item.set_active(target_affiliation.is_owner)
        if not user_affiliation.is_owner:
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_owner_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('invite_menuitem')
        if jid and c.name != self.nick:
            bookmarked = False
            contact = app.contacts.get_contact(self.account, jid, c.resource)
            if contact and contact.supports(nbxmpp.NS_CONFERENCE):
                bookmarked = True
            gui_menu_builder.build_invite_submenu(item, ((c, self.account),),
                ignore_rooms=[self.room_jid], show_bookmarked=bookmarked)
        else:
            item.set_sensitive(False)

        item = xml.get_object('information_menuitem')
        id_ = item.connect('activate', self.on_info, nick)
        self.handlers[id_] = item

        item = xml.get_object('history_menuitem')
        item.set_action_name('app.browse-history')
        dict_ = {'jid': GLib.Variant('s', fjid),
                 'account': GLib.Variant('s', self.account)}
        variant = GLib.Variant('a{sv}', dict_)
        item.set_action_target_value(variant)

        item = xml.get_object('add_to_roster_menuitem')
        our_jid = app.get_jid_from_account(self.account)
        if not jid or jid == our_jid or not app.connections[self.account].\
        roster_supported:
            item.set_sensitive(False)
        else:
            id_ = item.connect('activate', self.on_add_to_roster, jid)
            self.handlers[id_] = item

        item = xml.get_object('execute_command_menuitem')
        id_ = item.connect('activate', self._on_execute_command_occupant, nick)
        self.handlers[id_] = item

        item = xml.get_object('block_menuitem')
        item2 = xml.get_object('unblock_menuitem')
        if not app.connections[self.account].get_module('PrivacyLists').supported:
            item2.set_no_show_all(True)
            item.set_no_show_all(True)
            item.hide()
            item2.hide()
        elif helpers.jid_is_blocked(self.account, fjid):
            item.set_no_show_all(True)
            item.hide()
            id_ = item2.connect('activate', self.on_unblock, nick)
            self.handlers[id_] = item2
        else:
            id_ = item.connect('activate', self.on_block, nick)
            self.handlers[id_] = item
            item2.set_no_show_all(True)
            item2.hide()

        item = xml.get_object('send_private_message_menuitem')
        id_ = item.connect('activate', self.on_send_pm, self.model, iter_)
        self.handlers[id_] = item

        item = xml.get_object('send_file_menuitem')
        if not c.jid:
            item.set_sensitive(False)
        else:
            item.set_sensitive(True)
            # ToDo: integrate HTTP File Upload
            id_ = item.connect('activate', lambda x: self._on_send_file_jingle(c))
            self.handlers[id_] = item

        # show the popup now!
        menu = xml.get_object('gc_occupants_menu')
        menu.show_all()
        menu.attach_to_widget(app.interface.roster.window, None)
        menu.popup(None, None, None, None, event.button, event.time)

    def _start_private_message(self, nick):
        gc_c = app.contacts.get_gc_contact(self.account, self.room_jid, nick)
        nick_jid = gc_c.get_full_jid()

        ctrl = app.interface.msg_win_mgr.get_control(nick_jid, self.account)
        if not ctrl:
            ctrl = app.interface.new_private_chat(gc_c, self.account)

        if ctrl:
            ctrl.parent_win.set_active_tab(ctrl)

        return ctrl

    def _on_execute_command_occupant(self, widget, nick):
        jid = self.room_jid + '/' + nick
        AdHocCommand(self.account, jid)

    def on_row_activated(self, widget, path):
        """
        When an iter is activated (double click or single click if gnome
        is set this way)
        """
        if path.get_depth() == 1: # It's a group
            if widget.row_expanded(path):
                widget.collapse_row(path)
            else:
                widget.expand_row(path, False)
        else: # We want to send a private message
            nick = self.model[path][Column.NICK]
            self._start_private_message(nick)

    def on_list_treeview_row_activated(self, widget, path, col=0):
        """
        When an iter is double clicked: open the chat window
        """
        if not app.single_click:
            self.on_row_activated(widget, path)

    def on_list_treeview_button_press_event(self, widget, event):
        """
        Popup user's group's or agent menu
        """
        try:
            pos = widget.get_path_at_pos(int(event.x), int(event.y))
            path, x = pos[0], pos[2]
        except TypeError:
            widget.get_selection().unselect_all()
            return
        if event.button == 3: # right click
            widget.get_selection().select_path(path)
            iter_ = self.model.get_iter(path)
            if path.get_depth() == 2:
                self.mk_menu(event, iter_)
            return True

        if event.button == 2: # middle click
            widget.get_selection().select_path(path)
            iter_ = self.model.get_iter(path)
            if path.get_depth() == 2:
                nick = self.model[iter_][Column.NICK]
                self._start_private_message(nick)
            return True

        if event.button == 1: # left click
            if app.single_click and not event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.on_row_activated(widget, path)
                return True

            iter_ = self.model.get_iter(path)
            nick = self.model[iter_][Column.NICK]
            if not nick in app.contacts.get_nick_list(
                    self.account, self.room_jid):
                # it's a group
                if x < 27:
                    if widget.row_expanded(path):
                        widget.collapse_row(path)
                    else:
                        widget.expand_row(path, False)
            elif event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.append_nick_in_msg_textview(self.msg_textview, nick)
                self.msg_textview.grab_focus()
                return True

    def append_nick_in_msg_textview(self, widget, nick):
        self.msg_textview.remove_placeholder()
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
            gc_refer_to_nick_char = app.config.get('gc_refer_to_nick_char')
            add = gc_refer_to_nick_char + ' '
        message_buffer.insert_at_cursor(start + nick + add)

    def grant_voice(self, widget, nick):
        """
        Grant voice privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_role(self.room_jid, nick, 'participant')

    def revoke_voice(self, widget, nick):
        """
        Revoke voice privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_role(self.room_jid, nick, 'visitor')

    def grant_moderator(self, widget, nick):
        """
        Grant moderator privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_role(self.room_jid, nick, 'moderator')

    def revoke_moderator(self, widget, nick):
        """
        Revoke moderator privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_role(self.room_jid, nick, 'participant')

    def ban(self, widget, jid):
        """
        Ban a user
        """
        def on_ok(reason):
            con = app.connections[self.account]
            con.get_module('MUC').set_affiliation(
                self.room_jid,
                {jid: {'affiliation': 'outcast',
                       'reason': reason}})

        # to ban we know the real jid. so jid is not fakejid
        nick = app.get_nick_from_jid(jid)
        # ask for reason
        InputDialog(_('Banning %s') % nick,
            _('You may specify a reason below:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def grant_membership(self, widget, jid):
        """
        Grant membership privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'member'}})

    def revoke_membership(self, widget, jid):
        """
        Revoke membership privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'none'}})

    def grant_admin(self, widget, jid):
        """
        Grant administrative privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'admin'}})

    def revoke_admin(self, widget, jid):
        """
        Revoke administrative privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'member'}})

    def grant_owner(self, widget, jid):
        """
        Grant owner privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'owner'}})

    def revoke_owner(self, widget, jid):
        """
        Revoke owner privilege to a user
        """
        con = app.connections[self.account]
        con.get_module('MUC').set_affiliation(
            self.room_jid,
            {jid: {'affiliation': 'admin'}})

    def on_info(self, widget, nick):
        """
         Call vcard_information_window class to display user's information
        """
        gc_contact = app.contacts.get_gc_contact(self.account, self.room_jid,
            nick)
        contact = gc_contact.as_contact()
        if contact.jid in app.interface.instances[self.account]['infos']:
            app.interface.instances[self.account]['infos'][contact.jid].\
                window.present()
        else:
            app.interface.instances[self.account]['infos'][contact.jid] = \
                vcard.VcardWindow(contact, self.account, gc_contact)

    def on_add_to_roster(self, widget, jid):
        AddNewContactWindow(self.account, jid)

    def on_block(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        con = app.connections[self.account]
        con.get_module('PrivacyLists').block_gc_contact(fjid)
        self.draw_contact(nick)

    def on_unblock(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        con = app.connections[self.account]
        con.get_module('PrivacyLists').unblock_gc_contact(fjid)
        self.draw_contact(nick)

    def on_voice_checkmenuitem_activate(self, widget, nick):
        if widget.get_active():
            self.grant_voice(widget, nick)
        else:
            self.revoke_voice(widget, nick)

    def on_moderator_checkmenuitem_activate(self, widget, nick):
        if widget.get_active():
            self.grant_moderator(widget, nick)
        else:
            self.revoke_moderator(widget, nick)

    def on_member_checkmenuitem_activate(self, widget, jid):
        if widget.get_active():
            self.grant_membership(widget, jid)
        else:
            self.revoke_membership(widget, jid)

    def on_admin_checkmenuitem_activate(self, widget, jid):
        if widget.get_active():
            self.grant_admin(widget, jid)
        else:
            self.revoke_admin(widget, jid)

    def on_owner_checkmenuitem_activate(self, widget, jid):
        if widget.get_active():
            self.grant_owner(widget, jid)
        else:
            self.revoke_owner(widget, jid)

    def _on_page_change(self, stack, _param):
        page_name = stack.get_visible_child_name()
        if page_name == 'groupchat':
            self.xml.progress_spinner.stop()
        elif page_name == 'progress':
            self.xml.progress_spinner.start()
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
        if self._get_current_page() == 'nickname':
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
        app.connections[self.account].get_module('MUC').change_nick(
            self.room_jid, new_nick)
        self._show_page('groupchat')

    def _on_change_subject(self, _action, _param):
        if self._get_current_page() == 'subject':
            return
        self.xml.subject_textview.get_buffer().set_text(self.subject)
        self.xml.subject_textview.grab_focus()
        self._show_page('subject')

    def _on_subject_change_clicked(self, _button):
        buffer_ = self.xml.subject_textview.get_buffer()
        subject = buffer_.get_text(buffer_.get_start_iter(),
                                   buffer_.get_end_iter(),
                                   False)
        con = app.connections[self.account]
        con.get_module('MUC').set_subject(self.room_jid, subject)
        self._show_page('groupchat')

    def _on_password_set_clicked(self, _button):
        password = self.xml.password_entry.get_text()
        self._muc_data.password = password
        app.connections[self.account].get_module('MUC').join(self._muc_data)
        self._show_page('progress')

    def _on_password_changed(self, entry, _param):
        self.xml.password_set_button.set_sensitive(bool(entry.get_text()))

    def _on_password_cancel_clicked(self, _button=None):
        self._close_control()

    @event_filter(['account', 'room_jid'])
    def _on_captcha_challenge(self, event):
        self._remove_captcha_request()

        options = {'no-scrolling': True,
                   'entry-activates-default': True}
        self._captcha_request = DataFormWidget(event.form, options=options)
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

    @event_filter(['account', 'room_jid'])
    def _on_captcha_error(self, event):
        self.xml.captcha_error_label.set_text(event.error_text)
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
        con = app.connections[self.account]
        con.get_module('MUC').send_captcha(self.room_jid, form_node)
        self._remove_captcha_request()
        self._show_page('progress')

    def _on_captcha_cancel_clicked(self, _button=None):
        con = app.connections[self.account]
        con.get_module('MUC').cancel_captcha(self.room_jid)
        self._remove_captcha_request()
        self._close_control()

    def _on_captcha_try_again_clicked(self, _button=None):
        app.connections[self.account].get_module('MUC').join(self._muc_data)
        self._show_page('progress')

    def _on_page_cancel_clicked(self, _button):
        self._show_page('groupchat')

    def _on_page_close_clicked(self, _button=None):
        self._close_control()

    def _on_abort_button_clicked(self, _button):
        self.parent_win.window.lookup_action(
            'disconnect-%s' % self.control_id).activate()


class SubjectPopover(Gtk.Popover):
    def __init__(self):
        Gtk.Popover.__init__(self)
        self.set_name('SubjectPopover')

        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_max_content_height(250)
        scrolledwindow.set_propagate_natural_height(True)
        scrolledwindow.set_propagate_natural_width(True)
        scrolledwindow.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)

        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.label.set_max_width_chars(80)
        self.label.connect('activate-link', self._on_activate_link)

        scrolledwindow.add(self.label)

        box = Gtk.Box()
        box.add(scrolledwindow)
        box.show_all()
        self.add(box)

        self.connect_after('show', self._after_show)

    def set_text(self, text):
        self.label.set_markup(text)

    def _after_show(self, *args):
        # Gtk Bug: If we set selectable True, on show
        # everything inside the Label is selected.
        # So we switch after show to False and again to True
        self.label.set_selectable(False)
        self.label.set_selectable(True)

    @staticmethod
    def _on_activate_link(_label, uri):
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP
