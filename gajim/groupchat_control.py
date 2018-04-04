# -*- coding:utf-8 -*-
## src/groupchat_control.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import time
import locale

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import Gio
from gajim import gtkgui_helpers
from gajim import gui_menu_builder
from gajim import message_control
from gajim import tooltips
from gajim import dialogs
from gajim import config
from gajim import vcard
from gajim import dataforms_widget
from gajim import adhoc_commands
from gajim.common.const import AvatarSize
from gajim.common.caps_cache import muc_caps_cache
import nbxmpp

from enum import IntEnum, unique

from gajim.common import events
from gajim.common import app
from gajim.common import helpers
from gajim.common import dataforms
from gajim.common import ged
from gajim.common import i18n
from gajim.common import contacts

from gajim.chat_control import ChatControl
from gajim.chat_control_base import ChatControlBase

from gajim.command_system.implementation.hosts import PrivateChatCommands
from gajim.command_system.implementation.hosts import GroupChatCommands
from gajim.common.connection_handlers_events import GcMessageOutgoingEvent


import logging
log = logging.getLogger('gajim.groupchat_control')

@unique
class Column(IntEnum):
    IMG = 0 # image to show state (online, new message etc)
    NICK = 1 # contact nickame or ROLE name
    TYPE = 2 # type of the row ('contact' or 'role')
    TEXT = 3 # text shown in the cellrenderer
    AVATAR_IMG = 4 # avatar of the contact

empty_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
empty_pixbuf.fill(0xffffff00)


def cell_data_func(column, renderer, model, iter_, user_data):
    # Background color has to be rendered for all cells
    theme = app.config.get('roster_theme')
    has_parent = bool(model.iter_parent(iter_))
    if has_parent:
        bgcolor = app.config.get_per('themes', theme, 'contactbgcolor')
        renderer.set_property('cell-background', bgcolor or None)
    else:
        bgcolor = app.config.get_per('themes', theme, 'groupbgcolor')
        renderer.set_property('cell-background', bgcolor or None)

    if user_data == 'status':
        status_cell_data_func(column, renderer, model, iter_, has_parent)
    elif user_data == 'name':
        text_cell_data_func(column, renderer, model, iter_, has_parent, theme)
    elif user_data == 'avatar':
        avatar_cell_data_func(column, renderer, model, iter_, has_parent)

def status_cell_data_func(column, renderer, model, iter_, has_parent):
    renderer.set_property('width', 26)
    image = model[iter_][Column.IMG]
    surface = image.get_property('surface')
    renderer.set_property('surface', surface)

def avatar_cell_data_func(column, renderer, model, iter_, has_parent):
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

def text_cell_data_func(column, renderer, model, iter_, has_parent, theme):
    # cell data func is global, because we don't want it to keep
    # reference to GroupchatControl instance (self)
    if has_parent:
        color = app.config.get_per('themes', theme, 'contacttextcolor')
        if color:
            renderer.set_property('foreground', color)
        else:
            renderer.set_property('foreground', None)
        renderer.set_property('font',
            gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
    else:
        color = app.config.get_per('themes', theme, 'grouptextcolor')
        renderer.set_property('foreground', color or None)
        renderer.set_property('font',
            gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))


class PrivateChatControl(ChatControl):
    TYPE_ID = message_control.TYPE_PM

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, parent_win, gc_contact, contact, account, session):
        room_jid = gc_contact.room_jid
        self.room_ctrl = app.interface.msg_win_mgr.get_gc_control(room_jid,
            account)
        if room_jid in app.interface.minimized_controls[account]:
            self.room_ctrl = app.interface.minimized_controls[account][room_jid]
        if self.room_ctrl:
            self.room_name = self.room_ctrl.name
        else:
            self.room_name = room_jid
        self.gc_contact = gc_contact
        ChatControl.__init__(self, parent_win, contact, account, session)
        self.TYPE_ID = 'pm'
        app.ged.register_event_handler('update-gc-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.register_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received_pm)
        app.ged.register_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)

    def get_our_nick(self):
        return self.room_ctrl.nick

    def shutdown(self):
        super(PrivateChatControl, self).shutdown()
        app.ged.remove_event_handler('update-gc-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.remove_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received_pm)
        app.ged.remove_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)

    def _nec_caps_received_pm(self, obj):
        if obj.conn.name != self.account or \
        obj.fjid != self.gc_contact.get_full_jid():
            return
        self.update_contact()

    def _nec_gc_presence_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.fjid != self.full_jid:
            return
        if '303' in obj.status_code:
            self.print_conversation(_('%(nick)s is now known as '
                '%(new_nick)s') % {'nick': obj.nick, 'new_nick': obj.new_nick},
                'status')
            gc_c = app.contacts.get_gc_contact(obj.conn.name, obj.room_jid,
                obj.new_nick)
            c = gc_c.as_contact()
            self.gc_contact = gc_c
            self.contact = c
            if self.session:
                # stop e2e
                if self.session.enable_encryption:
                    thread_id = self.session.thread_id
                    self.session.terminate_e2e()
                    obj.conn.delete_session(obj.fjid, thread_id)
                    self.no_autonegotiation = False
            self.draw_banner()
            old_jid = obj.room_jid + '/' + obj.nick
            new_jid = obj.room_jid + '/' + obj.new_nick
            app.interface.msg_win_mgr.change_key(old_jid, new_jid,
                obj.conn.name)
        else:
            self.contact.show = obj.show
            self.contact.status = obj.status
            self.gc_contact.show = obj.show
            self.gc_contact.status = obj.status
            uf_show = helpers.get_uf_show(obj.show)
            self.print_conversation(_('%(nick)s is now %(status)s') % {
                    'nick': obj.nick, 'status': uf_show}, 'status')
            if obj.status:
                self.print_conversation(' (', 'status', simple=True)
                self.print_conversation('%s' % (obj.status), 'status',
                    simple=True)
                self.print_conversation(')', 'status', simple=True)
            self.parent_win.redraw_tab(self)
            self.update_ui()

    def send_message(self, message, xhtml=None, process_commands=True,
    attention=False):
        """
        Call this method to send the message
        """
        message = helpers.remove_invalid_xml_chars(message)
        if not message:
            return

        # We need to make sure that we can still send through the room and that
        # the recipient did not go away
        contact = app.contacts.get_first_contact_from_jid(self.account,
                self.contact.jid)
        if not contact:
            # contact was from pm in MUC
            room, nick = app.get_room_and_nick_from_fjid(self.contact.jid)
            gc_contact = app.contacts.get_gc_contact(self.account, room, nick)
            if not gc_contact:
                dialogs.ErrorDialog(
                    _('Sending private message failed'),
                    #in second %s code replaces with nickname
                    _('You are no longer in group chat "%(room)s" or '
                    '"%(nick)s" has left.') % {'room': '\u200E' + room,
                    'nick': nick}, transient_for=self.parent_win.window)
                return

        ChatControl.send_message(self, message, xhtml=xhtml,
            process_commands=process_commands, attention=attention)

    def update_ui(self):
        if self.contact.show == 'offline':
            self.got_disconnected()
        else:
            self.got_connected()
        ChatControl.update_ui(self)

    def _nec_update_avatar(self, obj):
        if obj.contact != self.gc_contact:
            return
        self.show_avatar()

    def show_avatar(self):
        if not app.config.get('show_avatar_in_chat'):
            return

        scale = self.parent_win.window.get_scale_factor()
        surface = app.interface.get_avatar(
            self.gc_contact.avatar_sha, AvatarSize.CHAT, scale)
        image = self.xml.get_object('avatar_image')
        image.set_from_surface(surface)

    def update_contact(self):
        self.contact = self.gc_contact.as_contact()

    def begin_e2e_negotiation(self):
        self.no_autonegotiation = True

        if not self.session:
            fjid = self.gc_contact.get_full_jid()
            new_sess = app.connections[self.account].make_new_session(fjid,
                type_=self.type_id)
            self.set_session(new_sess)

        self.session.negotiate_e2e(False)

    def got_disconnected(self):
        ChatControl.got_disconnected(self)

class GroupchatControl(ChatControlBase):
    TYPE_ID = message_control.TYPE_GC

    # Set a command host to bound to. Every command given through a group chat
    # will be processed with this command host.
    COMMAND_HOST = GroupChatCommands

    def __init__(self, parent_win, contact, acct, is_continued=False):
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
        self.nick = contact.name
        self.new_nick = ''
        self.name = ''
        for bm in app.connections[self.account].bookmarks:
            if bm['jid'] == self.room_jid:
                self.name = bm['name']
                break
        if not self.name:
            self.name = self.room_jid.split('@')[0]

        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            app.config.get('hide_groupchat_banner'))

        self._last_selected_contact = None # None or holds jid, account tuple

        # muc attention flag (when we are mentioned in a muc)
        # if True, the room has mentioned us
        self.attention_flag = False

        # sorted list of nicks who mentioned us (last at the end)
        self.attention_list = []
        self.room_creation = int(time.time()) # Use int to reduce mem usage
        self.nick_hits = []
        self.last_key_tabs = False

        self.subject = ''

        # nickname coloring
        self.gc_count_nicknames_colors = -1
        self.gc_custom_colors = {}
        self.number_of_colors = len(app.config.get('gc_nicknames_colors').\
            split(':'))

        self.name_label = self.xml.get_object('banner_name_label')
        self.event_box = self.xml.get_object('banner_eventbox')

        self.list_treeview = self.xml.get_object('list_treeview')
        selection = self.list_treeview.get_selection()
        id_ = selection.connect('changed',
            self.on_list_treeview_selection_changed)
        self.handlers[id_] = selection
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

        #status_image, shown_nick, type, nickname, avatar
        self.columns = [Gtk.Image, str, str, str, Gtk.Image]
        self.model = Gtk.TreeStore(*self.columns)
        self.model.set_sort_func(Column.NICK, self.tree_compare_iters)
        self.model.set_sort_column_id(Column.NICK, Gtk.SortType.ASCENDING)

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
            None, Column.IMG, cell_data_func, 'status'),
            # contact name
            ('name', renderer_text, True,
            'markup', Column.TEXT, cell_data_func, 'name'))

        # avatar img
        avatar_renderer = ('avatar', Gtk.CellRendererPixbuf(),
            False, None, Column.AVATAR_IMG,
            cell_data_func, 'avatar')

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

        self.setup_seclabel(self.xml.get_object('label_selector'))

        self.form_widget = None

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

        # GC Roster tooltip
        self.gc_tooltip = tooltips.GCTooltip()

        self.control_menu = gui_menu_builder.get_groupchat_menu(self.control_id)
        settings_menu = self.xml.get_object('settings_menu')
        settings_menu.set_menu_model(self.control_menu)

        app.ged.register_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)
        app.ged.register_event_handler('gc-message-received', ged.GUI1,
            self._nec_gc_message_received)
        app.ged.register_event_handler('mam-decrypted-message-received',
            ged.GUI1, self._nec_mam_decrypted_message_received)
        app.ged.register_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        app.ged.register_event_handler('update-gc-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.register_event_handler('gc-subject-received', ged.GUI1,
            self._nec_gc_subject_received)
        app.ged.register_event_handler('gc-config-changed-received', ged.GUI1,
            self._nec_gc_config_changed_received)
        app.ged.register_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        app.ged.register_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)
        app.ged.register_event_handler('gc-stanza-message-outgoing', ged.OUT_POSTCORE,
            self._message_sent)
        app.gc_connected[self.account][self.room_jid] = False
        # disable win, we are not connected yet
        ChatControlBase.got_disconnected(self)

        self.update_ui()
        self.widget.show_all()

        if app.config.get('hide_groupchat_occupants_list'):
            # Roster is shown by default, so toggle the roster button to hide it
            self.show_roster()

        # PluginSystem: adding GUI extension point for this GroupchatControl
        # instance object
        app.plugin_manager.gui_extension_point('groupchat_control', self)

    def add_actions(self):
        super().add_actions()
        actions = [
            ('change-subject-', self._on_change_subject),
            ('change-nick-', self._on_change_nick),
            ('disconnect-', self._on_disconnect),
            ('destroy-', self._on_destroy_room),
            ('configure-', self._on_configure_room),
            ('bookmark-', self._on_bookmark_room),
            ('request-voice-', self._on_request_voice),
            ('execute-command-', self._on_execute_command),
            ]

        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(action_name + self.control_id, None)
            act.connect("activate", func)
            self.parent_win.window.add_action(act)

        non_minimized_gc = app.config.get_per(
            'accounts', self.account, 'non_minimized_gc').split()
        value = self.contact.jid not in non_minimized_gc

        act = Gio.SimpleAction.new_stateful(
            'minimize-' + self.control_id, None,
            GLib.Variant.new_boolean(value))
        act.connect('change-state', self._on_minimize)
        self.parent_win.window.add_action(act)

        value = app.config.get_per(
            'rooms', self.contact.jid, 'notify_on_all_messages')

        act = Gio.SimpleAction.new_stateful(
            'notify-on-message-' + self.control_id,
            None, GLib.Variant.new_boolean(value))
        act.connect('change-state', self._on_notify_on_all_messages)
        self.parent_win.window.add_action(act)

    def update_actions(self):
        if self.parent_win is None:
            return
        win = self.parent_win.window
        contact = app.contacts.get_gc_contact(
            self.account, self.room_jid, self.nick)
        online = app.gc_connected[self.account][self.room_jid]

        # Destroy Room
        win.lookup_action('destroy-' + self.control_id).set_enabled(
            online and contact.affiliation == 'owner')

        # Configure Room
        win.lookup_action('configure-' + self.control_id).set_enabled(
            online and contact.affiliation in ('admin', 'owner'))

        # Bookmarks
        con = app.connections[self.account]
        bookmark_support = con.bookmarks_available()
        not_bookmarked = True
        for bm in con.bookmarks:
            if bm['jid'] == self.room_jid:
                not_bookmarked = False
                break
        win.lookup_action('bookmark-' + self.control_id).set_enabled(
            online and bookmark_support and not_bookmarked)

        # Request Voice
        role = self.get_role(self.nick)
        win.lookup_action('request-voice-' + self.control_id).set_enabled(
            online and role == 'visitor')

        # Change Subject
        # Get this from Room Disco
        win.lookup_action('change-subject-' + self.control_id).set_enabled(
            online)

        # Change Nick
        win.lookup_action('change-nick-' + self.control_id).set_enabled(
            online)

        # Execute command
        win.lookup_action('execute-command-' + self.control_id).set_enabled(
            online)

        # Send file (HTTP File Upload)
        httpupload = win.lookup_action(
            'send-file-httpupload-' + self.control_id)
        httpupload.set_enabled(
            online and app.connections[self.account].httpupload)
        win.lookup_action('send-file-' + self.control_id).set_enabled(
            httpupload.get_enabled())

        tooltip_text = None
        if online:
            if httpupload.get_enabled():
                tooltip_text = _('HTTP File Upload')
            else:
                tooltip_text = _('HTTP File Upload not supported '
                                 'by your server')
        self.sendfile_button.set_tooltip_text(tooltip_text)


    def _connect_window_state_change(self, parent_win):
        if self._state_change_handler_id is None:
            id_ = parent_win.window.connect('notify::is-maximized',
                                            self._on_window_state_change)
            self._state_change_handler_id = id_

    # Actions

    def _on_change_subject(self, action, param):
        def on_ok(subject):
            # Note, we don't update self.subject since we don't know whether it
            # will work yet
            app.connections[self.account].send_gc_subject(
                self.room_jid, subject)

        dialogs.InputTextDialog(_('Changing Subject'),
            _('Please specify the new subject:'), input_str=self.subject,
            ok_handler=on_ok, transient_for=self.parent_win.window)

    def _on_change_nick(self, action, param):
        if 'change_nick_dialog' in app.interface.instances:
            app.interface.instances['change_nick_dialog'].dialog.present()
        else:
            title = _('Changing Nickname')
            prompt = _('Please specify the new nickname you want to use:')
            app.interface.instances['change_nick_dialog'] = \
                dialogs.ChangeNickDialog(self.account, self.room_jid, title,
                prompt, change_nick=True, transient_for=self.parent_win.window)

    def _on_disconnect(self, action, param):
        self.force_non_minimizable = True
        self.parent_win.remove_tab(self, self.parent_win.CLOSE_COMMAND)
        self.force_non_minimizable = False

    def _on_destroy_room(self, action, param):
        def on_ok(reason, jid):
            if jid:
                # Test jid
                try:
                    jid = helpers.parse_jid(jid)
                except Exception:
                    dialogs.ErrorDialog(_('Invalid group chat JID'),
                    _('The group chat JID has not allowed characters.'))
                    return
            app.connections[self.account].destroy_gc_room(
                self.room_jid, reason, jid)
            gui_menu_builder.build_bookmark_menu(self.account)
            self.force_non_minimizable = True
            self.parent_win.remove_tab(self, self.parent_win.CLOSE_COMMAND)
            self.force_non_minimizable = False

        # Ask for a reason
        dialogs.DoubleInputDialog(_('Destroying %s') % '\u200E' + \
            self.room_jid, _('You are going to remove this room permanently.'
            '\nYou may specify a reason below:'),
            _('You may also enter an alternate venue:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def _on_configure_room(self, action, param):
        c = app.contacts.get_gc_contact(
            self.account, self.room_jid, self.nick)
        if c.affiliation == 'owner':
            app.connections[self.account].request_gc_config(self.room_jid)
        elif c.affiliation == 'admin':
            if self.room_jid not in app.interface.instances[self.account][
            'gc_config']:
                app.interface.instances[self.account]['gc_config'][
                    self.room_jid] = config.GroupchatConfigWindow(self.account,
                    self.room_jid)

    def _on_bookmark_room(self, action, param):
        """
        Bookmark the room, without autojoin and not minimized
        """
        password = app.gc_passwords.get(self.room_jid, '')
        app.interface.add_gc_bookmark(
            self.account, self.name, self.room_jid,
            '0', '0', password, self.nick)
        self.update_actions()

    def _on_request_voice(self, action, param):
        """
        Request voice in the current room
        """
        app.connections[self.account].request_voice(self.room_jid)

    def _on_minimize(self, action, param):
        """
        When a grouchat is minimized, unparent the tab, put it in roster etc
        """
        action.set_state(param)
        non_minimized_gc = app.config.get_per(
            'accounts', self.account, 'non_minimized_gc').split()

        minimize = param.get_boolean()
        if minimize:
            non_minimized_gc.remove(self.contact.jid)
        else:
            non_minimized_gc.append(self.contact.jid)

        app.config.set_per('accounts', self.account,
                           'non_minimized_gc', ' '.join(non_minimized_gc))

    def _on_notify_on_all_messages(self, action, param):
        action.set_state(param)
        app.config.set_per('rooms', self.contact.jid,
                           'notify_on_all_messages', param.get_boolean())

    def _on_execute_command(self, action, param):
        """
        Execute AdHoc commands on the current room
        """
        adhoc_commands.CommandWindow(self.account, self.room_jid)

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
        self._schedule_activity_timers()
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
        # set renderers propertys
        for renderer in self.renderers_propertys.keys():
            renderer.set_property(self.renderers_propertys[renderer][0],
                self.renderers_propertys[renderer][1])

    def tree_compare_iters(self, model, iter1, iter2, data=None):
        """
        Compare two iters to sort them
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
            cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4,
                'invisible': 5, 'offline': 6, 'error': 7}
            show1 = cshow[gc_contact1.show]
            show2 = cshow[gc_contact2.show]
            if show1 < show2:
                return -1
            elif show1 > show2:
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

    def on_list_treeview_selection_changed(self, selection):
        model, selected_iter = selection.get_selected()
        self.draw_contact(self.nick)
        if self._last_selected_contact is not None:
            self.draw_contact(self._last_selected_contact)
        if selected_iter is None:
            self._last_selected_contact = None
            return
        contact = model[selected_iter]
        nick = contact[Column.NICK]
        self._last_selected_contact = nick
        if contact[Column.TYPE] != 'contact':
            return
        self.draw_contact(nick, selected=True, focus=True)

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
            color = 'state_muc_directed_msg_color'
        elif chatstate == 'active' or (current_tab and has_focus):
            self.attention_flag = False
            # get active color from gtk
            color = 'active'
        elif chatstate == 'newmsg' and (not has_focus or not current_tab) \
        and not self.attention_flag:
            color = 'state_muc_msg_color'

        if self.is_continued:
            # if this is a continued conversation
            label_str = self.get_continued_conversation_name()
        else:
            label_str = self.name

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
        if app.gc_connected[self.account][self.room_jid]:
            tab_image = gtkgui_helpers.get_iconset_name_for('muc-active')
        else:
            tab_image = gtkgui_helpers.get_iconset_name_for('muc-inactive')
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
                'security-high', Gtk.IconSize.MENU)
        else:
            authenticated_string = _('and NOT authenticated')
            self.lock_image.set_from_icon_name(
                'security-low', Gtk.IconSize.MENU)

        tooltip = _('%(type)s encryption is active %(authenticated)s.') % {
            'type': enc_type, 'authenticated': authenticated_string}

        self.authentication_button.set_tooltip_text(tooltip)
        self.widget_set_visible(self.authentication_button, not visible)
        context = self.msg_scrolledwindow.get_style_context()
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
        if self.room_jid in app.gc_connected[self.account] and \
        app.gc_connected[self.account][self.room_jid]:
            icon = gtkgui_helpers.get_iconset_name_for('muc-active')
        else:
            icon = gtkgui_helpers.get_iconset_name_for('muc-inactive')
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
        font_attrs, font_attrs_small = self.get_font_attrs()
        if self.is_continued:
            name = self.get_continued_conversation_name()
        else:
            name = self.room_jid
        text = '<span %s>%s</span>' % (font_attrs, '\u200E' + name)
        self.name_label.set_markup(text)

        if self.subject:
            subject = GLib.markup_escape_text(self.subject)
            subject_text = self.urlfinder.sub(self.make_href, subject)
            subject_text = '<span>%s</span>' % subject_text
            self.subject_button.get_popover().set_text(subject_text)

    def _nec_vcard_published(self, obj):
        if obj.conn.name != self.account:
            return
        show = app.SHOW_LIST[obj.conn.connected]
        status = obj.conn.status
        obj.conn.send_gc_status(self.nick, self.room_jid, show, status)

    def _nec_update_avatar(self, obj):
        if obj.contact.room_jid != self.room_jid:
            return
        app.log('avatar').debug('Draw Groupchat Avatar: %s %s',
                                obj.contact.name, obj.contact.avatar_sha)
        self.draw_avatar(obj.contact)

    def _nec_mam_decrypted_message_received(self, obj):
        if not obj.groupchat:
            return
        if obj.room_jid != self.room_jid:
            return
        self.print_conversation(
            obj.msgtxt, contact=obj.nick,
            tim=obj.timestamp, correct_id=obj.correct_id,
            encrypted=obj.encrypted,
            msg_stanza_id=obj.message_id,
            additional_data=obj.additional_data)

    def _nec_gc_message_received(self, obj):
        if obj.room_jid != self.room_jid or obj.conn.name != self.account:
            return
        if obj.captcha_form:
            if self.form_widget:
                self.form_widget.hide()
                self.form_widget.destroy()
                self.btn_box.destroy()
            dataform = dataforms.ExtendForm(node=obj.captcha_form)
            self.form_widget = dataforms_widget.DataFormWidget(dataform)

            def on_send_dataform_clicked(widget):
                if not self.form_widget:
                    return
                form_node = self.form_widget.data_form.get_purged()
                form_node.type_ = 'submit'
                obj.conn.send_captcha(self.room_jid, form_node)
                self.form_widget.hide()
                self.form_widget.destroy()
                self.btn_box.destroy()
                self.form_widget = None
                del self.btn_box

            self.form_widget.connect('validated', on_send_dataform_clicked)
            self.form_widget.show_all()
            vbox = self.xml.get_object('gc_textviews_vbox')
            vbox.pack_start(self.form_widget, False, True, 0)

            valid_button = Gtk.Button(stock=Gtk.STOCK_OK)
            valid_button.connect('clicked', on_send_dataform_clicked)
            self.btn_box = Gtk.HButtonBox()
            self.btn_box.set_layout(Gtk.ButtonBoxStyle.END)
            self.btn_box.pack_start(valid_button, True, True, 0)
            self.btn_box.show_all()
            vbox.pack_start(self.btn_box, False, False, 0)
            if self.parent_win:
                self.parent_win.redraw_tab(self, 'attention')
            else:
                self.attention_flag = True
        if '100' in obj.status_code:
            # Room is not anonymous
            self.is_anonymous = False
        if not obj.nick:
            # message from server
            self.print_conversation(
                obj.msgtxt, tim=obj.timestamp,
                xhtml=obj.xhtml_msgtxt, displaymarking=obj.displaymarking,
                additional_data=obj.additional_data)
        else:
            # message from someone
            if obj.has_timestamp:
                # don't print xhtml if it's an old message.
                # Like that xhtml messages are grayed too.
                self.print_old_conversation(
                    obj.msgtxt, contact=obj.nick,
                    tim=obj.timestamp, xhtml=None, encrypted=obj.encrypted,
                    displaymarking=obj.displaymarking, msg_stanza_id=obj.id_,
                    additional_data=obj.additional_data)
            else:
                if obj.nick == self.nick:
                    self.last_sent_txt = obj.msgtxt
                self.print_conversation(
                    obj.msgtxt, contact=obj.nick,
                    tim=obj.timestamp, xhtml=obj.xhtml_msgtxt,
                    displaymarking=obj.displaymarking, encrypted=obj.encrypted,
                    correct_id=obj.correct_id, msg_stanza_id=obj.id_,
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
                state_images = \
                    app.interface.roster.get_appropriate_state_images(
                    self.room_jid, icon_name='event')
                image = state_images['event']
                self.model[iter_][Column.IMG] = image
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

    def get_contact_iter(self, nick):
        role_iter = self.model.get_iter_first()
        while role_iter:
            user_iter = self.model.iter_children(role_iter)
            while user_iter:
                if nick == self.model[user_iter][Column.NICK]:
                    return user_iter
                else:
                    user_iter = self.model.iter_next(user_iter)
            role_iter = self.model.iter_next(role_iter)
        return None

    def print_old_conversation(self, text, contact='', tim=None, xhtml = None,
    displaymarking=None, msg_stanza_id=None, encrypted=None, additional_data=None):
        if additional_data is None:
            additional_data = {}

        if contact:
            if contact == self.nick: # it's us
                kind = 'outgoing'
            else:
                kind = 'incoming'
        else:
            kind = 'status'
        if app.config.get('restored_messages_small'):
            small_attr = ['small']
        else:
            small_attr = []

        ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
            small_attr, small_attr + ['restored_message'],
            small_attr + ['restored_message'], count_as_new=False, xhtml=xhtml,
            displaymarking=displaymarking, msg_stanza_id=msg_stanza_id,
            encrypted=encrypted, additional_data=additional_data)

    def print_conversation(self, text, contact='', tim=None, xhtml=None,
    graphics=True, displaymarking=None, correct_id=None, msg_stanza_id=None,
    encrypted=None, additional_data=None):
        """
        Print a line in the conversation

        If contact is set: it's a message from someone or an info message
        (contact = 'info' in such a case).
        If contact is not set: it's a message from the server or help.
        """
        if additional_data is None:
            additional_data = {}
        other_tags_for_name = []
        other_tags_for_text = []
        if contact:
            if contact == self.nick: # it's us
                kind = 'outgoing'
            elif contact == 'info':
                kind = 'info'
                contact = None
            else:
                kind = 'incoming'
                # muc-specific chatstate
                if self.parent_win:
                    self.parent_win.redraw_tab(self, 'newmsg')
        else:
            kind = 'status'

        if kind == 'incoming': # it's a message NOT from us
            # highlighting and sounds
            (highlight, sound) = self.highlighting_for_message(text, tim)
            if contact in self.gc_custom_colors:
                other_tags_for_name.append('gc_nickname_color_' + \
                    str(self.gc_custom_colors[contact]))
            else:
                self.gc_count_nicknames_colors += 1
                if self.gc_count_nicknames_colors == self.number_of_colors:
                    self.gc_count_nicknames_colors = 0
                self.gc_custom_colors[contact] = \
                    self.gc_count_nicknames_colors
                other_tags_for_name.append('gc_nickname_color_' + \
                    str(self.gc_count_nicknames_colors))
            if highlight:
                # muc-specific chatstate
                if self.parent_win:
                    self.parent_win.redraw_tab(self, 'attention')
                else:
                    self.attention_flag = True
                other_tags_for_name.append('bold')
                other_tags_for_text.append('marked')

                if contact in self.attention_list:
                    self.attention_list.remove(contact)
                elif len(self.attention_list) > 6:
                    self.attention_list.pop(0) # remove older
                self.attention_list.append(contact)

            if text.startswith('/me ') or text.startswith('/me\n'):
                other_tags_for_text.append('gc_nickname_color_' + \
                    str(self.gc_custom_colors[contact]))

            self.check_and_possibly_add_focus_out_line()

        ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
            other_tags_for_name, [], other_tags_for_text, xhtml=xhtml,
            graphics=graphics, displaymarking=displaymarking,
            correct_id=correct_id, msg_stanza_id=msg_stanza_id, encrypted=encrypted,
            additional_data=additional_data)

    def get_nb_unread(self):
        type_events = ['printed_marked_gc_msg']
        if app.config.get('notify_on_all_muc_messages') or \
        app.config.get_per('rooms', self.room_jid, 'notify_on_all_messages'):
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
        highlight, sound = (None, None)

        # Are any of the defined highlighting words in the text?
        if self.needs_visual_notification(text):
            highlight = True
            if app.config.get_per('soundevents', 'muc_message_highlight',
            'enabled'):
                sound = 'highlight'

        # Do we play a sound on every muc message?
        elif app.config.get_per('soundevents', 'muc_message_received', \
        'enabled'):
            sound = 'received'

        # Is it a history message? Don't want sound-floods when we join.
        if time.mktime(time.localtime()) - tim > 1:
            sound = None

        return (highlight, sound)

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
            while(found_here > -1):
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

    def _nec_gc_subject_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.room_jid != self.room_jid:
            return
        self.set_subject(obj.subject)
        text = _('%(nick)s has set the subject to %(subject)s') % {
            'nick': obj.nickname, 'subject': obj.subject}
        if obj.has_timestamp:
            self.print_old_conversation(text)
        else:
            self.print_conversation(text)

        if obj.subject == '':
            self.subject_button.hide()
        else:
            self.subject_button.show()

    def _nec_gc_config_changed_received(self, obj):
        # statuscode is a list
        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
        # http://www.xmpp.org/extensions/xep-0045.html#registrar-statuscodes...
        # -init
        if obj.room_jid != self.room_jid or obj.conn.name != self.account:
            return

        changes = []
        if '100' in obj.status_code:
            # Can be a presence (see chg_contact_status in groupchat_control.py)
            changes.append(_('Any occupant is allowed to see your full JID'))
            self.is_anonymous = False
        if '102' in obj.status_code:
            changes.append(_('Room now shows unavailable members'))
        if '103' in obj.status_code:
            changes.append(_('Room now does not show unavailable members'))
        if '104' in obj.status_code:
            changes.append(_('A setting not related to privacy has been '
                'changed'))
        if '170' in obj.status_code:
            # Can be a presence (see chg_contact_status in groupchat_control.py)
            changes.append(_('Room logging is now enabled'))
        if '171' in obj.status_code:
            changes.append(_('Room logging is now disabled'))
        if '172' in obj.status_code:
            changes.append(_('Room is now non-anonymous'))
            self.is_anonymous = False
        if '173' in obj.status_code:
            changes.append(_('Room is now semi-anonymous'))
            self.is_anonymous = True
        if '174' in obj.status_code:
            changes.append(_('Room is now fully anonymous'))
            self.is_anonymous = True

        for change in changes:
            self.print_conversation(change)

    def _nec_signed_in(self, obj):
        if obj.conn.name != self.account:
            return
        password = app.gc_passwords.get(self.room_jid, '')
        obj.conn.join_gc(self.nick, self.room_jid, password, rejoin=True)

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
                obj.session.control.print_conversation(obj.msgtxt, frm,
                    tim=obj.timestamp, xhtml=obj.xhtml, encrypted=obj.encrypted,
                    displaymarking=obj.displaymarking, msg_stanza_id=obj.id_,
                    correct_id=obj.correct_id)
            else:
                # otherwise pass it off to the control to be queued
                self.on_private_message(nick, obj.sent, obj.msgtxt, obj.timestamp,
                    obj.xhtml, self.session, msg_log_id=obj.msg_log_id,
                    encrypted=obj.encrypted, displaymarking=obj.displaymarking)

    def _nec_ping_reply(self, obj):
        if obj.control:
            if obj.control != self:
                return
        else:
            if self.contact != obj.contact:
                return
        self.print_conversation(_('Pong! (%s s.)') % obj.seconds)

    def got_connected(self):
        # Make autorejoin stop.
        if self.autorejoin:
            GLib.source_remove(self.autorejoin)
        self.autorejoin = None

        if muc_caps_cache.has_mam(self.room_jid):
            # Request MAM
            app.connections[self.account].request_archive_on_muc_join(
                self.room_jid)

        app.gc_connected[self.account][self.room_jid] = True
        ChatControlBase.got_connected(self)
        self.list_treeview.set_model(self.model)
        self.list_treeview.expand_all()
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
        self.list_treeview.set_model(None)
        self.model.clear()
        nick_list = app.contacts.get_nick_list(self.account, self.room_jid)
        for nick in nick_list:
            # Update pm chat window
            fjid = self.room_jid + '/' + nick
            gc_contact = app.contacts.get_gc_contact(self.account,
                self.room_jid, nick)

            ctrl = app.interface.msg_win_mgr.get_control(fjid, self.account)
            if ctrl:
                gc_contact.show = 'offline'
                gc_contact.status = ''
                ctrl.update_ui()
                if ctrl.parent_win:
                    ctrl.parent_win.redraw_tab(ctrl)

            app.contacts.remove_gc_contact(self.account, gc_contact)
        app.gc_connected[self.account][self.room_jid] = False
        ChatControlBase.got_disconnected(self)
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

    def rejoin(self):
        if not self.autorejoin:
            return False
        password = app.gc_passwords.get(self.room_jid, '')
        app.connections[self.account].join_gc(self.nick, self.room_jid,
            password, rejoin=True)
        return True

    def draw_roster(self):
        self.model.clear()
        for nick in app.contacts.get_nick_list(self.account, self.room_jid):
            gc_contact = app.contacts.get_gc_contact(self.account,
                self.room_jid, nick)
            self.add_contact_to_roster(nick, gc_contact.show, gc_contact.role,
                gc_contact.affiliation, gc_contact.status, gc_contact.jid)
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

    def draw_contact(self, nick, selected=False, focus=False):
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return
        gc_contact = app.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        theme = Gtk.IconTheme.get_default()
        if len(app.events.get_events(self.account, self.room_jid + '/' + \
        nick)):
            icon_name = gtkgui_helpers.get_iconset_name_for('event')
            surface = theme.load_surface(icon_name, 16, self.scale_factor, None, 0)
        else:
            icon_name = gtkgui_helpers.get_iconset_name_for(gc_contact.show)
            surface = theme.load_surface(icon_name, 16, self.scale_factor, None, 0)

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
                color = gtkgui_helpers.get_fade_color(self.list_treeview,
                        selected, focus)
                colorstring = "#%04x%04x%04x" % (int(color.red * 65535),
                    int(color.green * 65535), int(color.blue * 65535))
                name += ('\n<span size="small" style="italic" foreground="%s">'
                    '%s</span>') % (colorstring, GLib.markup_escape_text(
                    status))

        if (gc_contact.affiliation != 'none' and
                app.config.get('show_affiliation_in_groupchat')):
            gtkgui_helpers.draw_affiliation(surface, gc_contact.affiliation)

        image = Gtk.Image.new_from_surface(surface)
        self.model[iter_][Column.IMG] = image
        self.model[iter_][Column.TEXT] = name

    def draw_avatar(self, gc_contact):
        if not app.config.get('show_avatars_in_roster'):
            return
        iter_ = self.get_contact_iter(gc_contact.name)
        if not iter_:
            return

        surface = app.interface.get_avatar(
            gc_contact.avatar_sha, AvatarSize.ROSTER, self.scale_factor)
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
        for role in ('visitor', 'participant', 'moderator'):
            self.draw_role(role)

    def _nec_gc_presence_received(self, obj):
        if obj.room_jid != self.room_jid or obj.conn.name != self.account:
            return
        if obj.ptype == 'error':
            return

        role = obj.role
        if not role:
            role = 'visitor'

        affiliation = obj.affiliation
        if not affiliation:
            affiliation = 'none'

        newly_created = False
        nick = i18n.direction_mark + obj.nick
        nick_jid = nick + i18n.direction_mark

        # Set to true if role or affiliation have changed
        right_changed = False

        if obj.real_jid:
            # delete ressource
            simple_jid = app.get_jid_without_resource(obj.real_jid)
            nick_jid += ' (%s)' % simple_jid

        # status_code
        # http://www.xmpp.org/extensions/xep-0045.html#registrar-statuscodes-\
        # init
        if obj.status_code and obj.nick == self.nick:
            if '110' in obj.status_code:
                # We just join the room
                if self.room_jid in app.automatic_rooms[self.account] and \
                app.automatic_rooms[self.account][self.room_jid]['invities']:
                    if self.room_jid not in app.interface.instances[
                    self.account]['gc_config']:
                        if obj.affiliation == 'owner':
                            # We need to configure the room if it's a new one.
                            # We cannot know it's a new one. Status 201 is not
                            # sent by all servers.
                            app.connections[self.account].request_gc_config(
                                self.room_jid)
                        elif 'continue_tag' in app.automatic_rooms[
                        self.account][self.room_jid]:
                            # We just need to invite contacts
                            for jid in app.automatic_rooms[self.account][
                            self.room_jid]['invities']:
                                obj.conn.send_invite(self.room_jid, jid)
                                self.print_conversation(_('%(jid)s has been '
                                    'invited in this room') % {'jid': jid},
                                    graphics=False)
            if '100' in obj.status_code:
                # Can be a message (see handle_event_gc_config_change in
                # app.py)
                self.print_conversation(
                    _('Any occupant is allowed to see your full JID'))
                self.is_anonymous = False
            if '170' in obj.status_code:
                # Can be a message (see handle_event_gc_config_change in
                # app.py)
                self.print_conversation(_('Room logging is enabled'))
            if '201' in obj.status_code:
                self.print_conversation(_('A new room has been created'))
            if '210' in obj.status_code:
                self.print_conversation(\
                    _('The server has assigned or modified your roomnick'))

        if obj.show in ('offline', 'error'):
            if obj.status_code:
                if '307' in obj.status_code:
                    if obj.actor is None: # do not print 'kicked by None'
                        s = _('%(nick)s has been kicked: %(reason)s') % {
                            'nick': nick, 'reason': obj.reason}
                    else:
                        s = _('%(nick)s has been kicked by %(who)s: '
                            '%(reason)s') % {'nick': nick, 'who': obj.actor,
                            'reason': obj.reason}
                    self.print_conversation(s, 'info', graphics=False)
                    if obj.nick == self.nick and not app.config.get(
                    'muc_autorejoin_on_kick'):
                        self.autorejoin = False
                elif '301' in obj.status_code:
                    if obj.actor is None: # do not print 'banned by None'
                        s = _('%(nick)s has been banned: %(reason)s') % {
                            'nick': nick, 'reason': obj.reason}
                    else:
                        s = _('%(nick)s has been banned by %(who)s: '
                            '%(reason)s') % {'nick': nick, 'who': obj.actor,
                            'reason': obj.reason}
                    self.print_conversation(s, 'info', graphics=False)
                    if obj.nick == self.nick:
                        self.autorejoin = False
                elif '303' in obj.status_code: # Someone changed his or her nick
                    if obj.new_nick == self.new_nick or obj.nick == self.nick:
                        # We changed our nick
                        self.nick = obj.new_nick
                        self.new_nick = ''
                        s = _('You are now known as %s') % self.nick
                        # Stop all E2E sessions
                        nick_list = app.contacts.get_nick_list(self.account,
                            self.room_jid)
                        for nick_ in nick_list:
                            fjid_ = self.room_jid + '/' + nick_
                            ctrl = app.interface.msg_win_mgr.get_control(
                                fjid_, self.account)
                            if ctrl and ctrl.session and \
                            ctrl.session.enable_encryption:
                                thread_id = ctrl.session.thread_id
                                ctrl.session.terminate_e2e()
                                app.connections[self.account].delete_session(
                                    fjid_, thread_id)
                                ctrl.no_autonegotiation = False
                    else:
                        s = _('%(nick)s is now known as %(new_nick)s') % {
                            'nick': nick, 'new_nick': obj.new_nick}
                    tv = self.conv_textview
                    if obj.nick in tv.last_received_message_id:
                        tv.last_received_message_id[obj.new_nick] = \
                            tv.last_received_message_id[obj.nick]
                        del tv.last_received_message_id[obj.nick]
                    # We add new nick to muc roster here, so we don't see
                    # that "new_nick has joined the room" when he just changed
                    # nick.
                    # add_contact_to_roster will be called a second time
                    # after that, but that doesn't hurt
                    self.add_contact_to_roster(obj.new_nick, obj.show, role,
                        affiliation, obj.status, obj.real_jid)
                    if obj.nick in self.attention_list:
                        self.attention_list.remove(obj.nick)
                    # keep nickname color
                    if obj.nick in self.gc_custom_colors:
                        self.gc_custom_colors[obj.new_nick] = \
                            self.gc_custom_colors[obj.nick]
                    self.print_conversation(s, 'info', graphics=False)
                elif '321' in obj.status_code:
                    s = _('%(nick)s has been removed from the room '
                        '(%(reason)s)') % { 'nick': nick,
                        'reason': _('affiliation changed') }
                    self.print_conversation(s, 'info', graphics=False)
                elif '322' in obj.status_code:
                    s = _('%(nick)s has been removed from the room '
                        '(%(reason)s)') % { 'nick': nick,
                        'reason': _('room configuration changed to '
                        'members-only') }
                    self.print_conversation(s, 'info', graphics=False)
                elif '332' in obj.status_code:
                    s = _('%(nick)s has been removed from the room '
                        '(%(reason)s)') % {'nick': nick,
                        'reason': _('system shutdown') }
                    self.print_conversation(s, 'info', graphics=False)
                # Room has been destroyed.
                elif 'destroyed' in obj.status_code:
                    self.autorejoin = False
                    self.print_conversation(obj.reason, 'info', graphics=False)

            if len(app.events.get_events(self.account, jid=obj.fjid,
            types=['pm'])) == 0:
                self.remove_contact(obj.nick)
                self.draw_all_roles()
            else:
                c = app.contacts.get_gc_contact(self.account, self.room_jid,
                    obj.nick)
                c.show = obj.show
                c.status = obj.status
            if obj.nick == self.nick and (not obj.status_code or \
            '303' not in obj.status_code): # We became offline
                self.got_disconnected()
                contact = app.contacts.\
                    get_contact_with_highest_priority(self.account,
                    self.room_jid)
                if contact:
                    app.interface.roster.draw_contact(self.room_jid,
                        self.account)
                if self.parent_win:
                    self.parent_win.redraw_tab(self)
        else:
            iter_ = self.get_contact_iter(obj.nick)
            if not iter_:
                if '210' in obj.status_code:
                    # Server changed our nick
                    self.nick = obj.nick
                    s = _('You are now known as %s') % nick
                    self.print_conversation(s, 'info', graphics=False)
                iter_ = self.add_contact_to_roster(obj.nick, obj.show, role,
                    affiliation, obj.status, obj.real_jid, obj.avatar_sha)
                newly_created = True
                self.draw_all_roles()
                if obj.status_code and '201' in obj.status_code:
                    # We just created the room
                    app.connections[self.account].request_gc_config(
                        self.room_jid)
            else:
                gc_c = app.contacts.get_gc_contact(self.account,
                    self.room_jid, obj.nick)
                if not gc_c:
                    log.error('%s has an iter, but no gc_contact instance' % \
                        obj.nick)
                    return

                actual_affiliation = gc_c.affiliation
                if affiliation != actual_affiliation:
                    if obj.actor:
                        st = _('** Affiliation of %(nick)s has been set to '
                            '%(affiliation)s by %(actor)s') % {'nick': nick_jid,
                            'affiliation': affiliation, 'actor': obj.actor}
                    else:
                        st = _('** Affiliation of %(nick)s has been set to '
                            '%(affiliation)s') % {'nick': nick_jid,
                            'affiliation': affiliation}
                    if obj.reason:
                        st += ' (%s)' % obj.reason
                    self.print_conversation(st, graphics=False)
                    right_changed = True
                actual_role = self.get_role(obj.nick)
                if role != actual_role:
                    self.remove_contact(obj.nick)
                    self.add_contact_to_roster(obj.nick, obj.show, role,
                        affiliation, obj.status, obj.real_jid)
                    self.draw_role(actual_role)
                    self.draw_role(role)
                    if obj.actor:
                        st = _('** Role of %(nick)s has been set to %(role)s '
                            'by %(actor)s') % {'nick': nick_jid, 'role': role,
                            'actor': obj.actor}
                    else:
                        st = _('** Role of %(nick)s has been set to '
                            '%(role)s') % {'nick': nick_jid, 'role': role}
                    if obj.reason:
                        st += ' (%s)' % obj.reason
                    self.print_conversation(st, graphics=False)
                    right_changed = True
                else:
                    if gc_c.show == obj.show and gc_c.status == obj.status and \
                    gc_c.affiliation == affiliation: # no change
                        return
                    gc_c.show = obj.show
                    gc_c.affiliation = affiliation
                    gc_c.status = obj.status
                    self.draw_contact(obj.nick)
        if (time.time() - self.room_creation) > 30 and obj.nick != self.nick \
        and (not obj.status_code or '303' not in obj.status_code) and not \
        right_changed:
            st = ''
            print_status = None
            for bookmark in app.connections[self.account].bookmarks:
                if bookmark['jid'] == self.room_jid:
                    print_status = bookmark.get('print_status', None)
                    break
            if not print_status:
                print_status = app.config.get('print_status_in_muc')
            if obj.show == 'offline':
                if obj.nick in self.attention_list:
                    self.attention_list.remove(obj.nick)
            if obj.show == 'offline' and print_status in ('all', 'in_and_out') \
            and (not obj.status_code or '307' not in obj.status_code):
                st = _('%s has left') % nick_jid
                if obj.reason:
                    st += ' [%s]' % obj.reason
            else:
                if newly_created and print_status in ('all', 'in_and_out'):
                    st = _('%s has joined the group chat') % nick_jid
                elif print_status == 'all':
                    st = _('%(nick)s is now %(status)s') % {'nick': nick_jid,
                        'status': helpers.get_uf_show(obj.show)}
            if st:
                if obj.status:
                    st += ' (' + obj.status + ')'
                self.print_conversation(st, graphics=False)

        # Update Actions
        if obj.status_code:
            if '110' in obj.status_code:
                self.update_actions()

    def add_contact_to_roster(self, nick, show, role, affiliation, status,
    jid='', avatar_sha=None):
        role_name = helpers.get_uf_role(role, plural=True)

        resource = ''
        if jid:
            jids = jid.split('/', 1)
            j = jids[0]
            if len(jids) > 1:
                resource = jids[1]
        else:
            j = ''

        name = nick

        role_iter = self.get_role_iter(role)
        if not role_iter:
            image = gtkgui_helpers.get_image_from_icon_name('closed', self.scale_factor)
            role_iter = self.model.append(None,
                [image, role, 'role', role_name,  None] + [None] * self.nb_ext_renderers)
            self.draw_all_roles()
        iter_ = self.model.append(role_iter, [None, nick, 'contact', name, None] + \
                [None] * self.nb_ext_renderers)
        if not nick in app.contacts.get_nick_list(self.account,
        self.room_jid):
            gc_contact = app.contacts.create_gc_contact(
                room_jid=self.room_jid, account=self.account,
                name=nick, show=show, status=status, role=role,
                affiliation=affiliation, jid=j, resource=resource,
                avatar_sha=avatar_sha)
            app.contacts.add_gc_contact(self.account, gc_contact)
        else:
            gc_contact = app.contacts.get_gc_contact(self.account, self.room_jid, nick)
        self.draw_contact(nick)
        self.draw_avatar(gc_contact)

        if nick == self.nick: # we became online
            self.got_connected()
        if self.list_treeview.get_model():
            self.list_treeview.expand_row((self.model.get_path(role_iter)), False)
        if self.is_continued:
            self.draw_banner_text()
        return iter_

    def get_role_iter(self, role):
        role_iter = self.model.get_iter_first()
        while role_iter:
            role_name = self.model[role_iter][Column.NICK]
            if role == role_name:
                return role_iter
            role_iter = self.model.iter_next(role_iter)
        return None

    def remove_contact(self, nick):
        """
        Remove a user from the contacts_list
        """
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return
        gc_contact = app.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        if gc_contact:
            app.contacts.remove_gc_contact(self.account, gc_contact)
        parent_iter = self.model.iter_parent(iter_)
        self.model.remove(iter_)
        if self.model.iter_n_children(parent_iter) == 0:
            self.model.remove(parent_iter)

    def _message_sent(self, obj):
        if not obj.message:
            return
        if obj.account != self.account:
            return
        if obj.jid != self.room_jid:
            return
        # we'll save sent message text when we'll receive it in
        # _nec_gc_message_received
        self.last_sent_msg = obj.stanza_id
        if self.correcting:
            self.correcting = False
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'msgcorrectingcolor')

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

            # Set chatstate
            chatstate = None
            if app.config.get('outgoing_chat_state_notifications') != 'disabled':
                chatstate = 'active'
                self.reset_kbd_mouse_timeout_vars()
                self.contact.our_chatstate = chatstate

            # Send the message
            app.nec.push_outgoing_event(GcMessageOutgoingEvent(
                None, account=self.account, jid=self.room_jid, message=message,
                xhtml=xhtml, label=label, chatstate=chatstate,
                correct_id=correct_id, automatic_message=False))
            self.msg_textview.get_buffer().set_text('')
            self.msg_textview.grab_focus()

    def get_role(self, nick):
        gc_contact = app.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        if gc_contact:
            return gc_contact.role
        else:
            return 'visitor'

    def minimizable(self):
        if self.force_non_minimizable:
            return False
        if self.contact.jid not in app.config.get_per('accounts', self.account,
        'non_minimized_gc').split(' '):
            return True
        return False

    def minimize(self, status='offline'):
        # Minimize it
        win = app.interface.msg_win_mgr.get_window(self.contact.jid,
                self.account)
        ctrl = win.get_control(self.contact.jid, self.account)

        ctrl_page = win.notebook.page_num(ctrl.widget)
        control = win.notebook.get_nth_page(ctrl_page)

        win.notebook.remove_page(ctrl_page)
        if self.possible_paused_timeout_id:
            GLib.source_remove(self.possible_paused_timeout_id)
            self.possible_paused_timeout_id = None
        if self.possible_inactive_timeout_id:
            GLib.source_remove(self.possible_inactive_timeout_id)
            self.possible_inactive_timeout_id = None
        control.unparent()
        ctrl.parent_win = None
        self.send_chatstate('inactive', self.contact)

        app.interface.roster.add_groupchat(self.contact.jid, self.account,
            status = self.subject)

        del win._controls[self.account][self.contact.jid]

    def send_chatstate(self, state, contact):
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
        chatstate_setting = app.config.get('outgoing_chat_state_notifications')
        if chatstate_setting == 'disabled':
            return

        elif chatstate_setting == 'composing_only' and state != 'active' and\
                state != 'composing':
            return

        # if the new state we wanna send (state) equals
        # the current state (contact.our_chatstate) then return
        if contact.our_chatstate == state:
            return

        # if wel're inactive prevent composing (XEP violation)
        if contact.our_chatstate == 'inactive' and state == 'composing':
            # go active before
            app.nec.push_outgoing_event(GcMessageOutgoingEvent(None,
                account=self.account, jid=self.contact.jid, chatstate='active',
                control=self))
            contact.our_chatstate = 'active'
            self.reset_kbd_mouse_timeout_vars()

        app.nec.push_outgoing_event(GcMessageOutgoingEvent(None,
            account=self.account, jid=self.contact.jid, chatstate=state,
            control=self))

        contact.our_chatstate = state
        if state == 'active':
            self.reset_kbd_mouse_timeout_vars()

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

        app.ged.remove_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)
        app.ged.remove_event_handler('gc-message-received', ged.GUI1,
            self._nec_gc_message_received)
        app.ged.remove_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        app.ged.remove_event_handler('update-gc-avatar', ged.GUI1,
            self._nec_update_avatar)
        app.ged.remove_event_handler('gc-subject-received', ged.GUI1,
            self._nec_gc_subject_received)
        app.ged.remove_event_handler('gc-config-changed-received', ged.GUI1,
            self._nec_gc_config_changed_received)
        app.ged.remove_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        app.ged.remove_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)
        app.ged.remove_event_handler('gc-stanza-message-outgoing', ged.OUT_POSTCORE,
            self._message_sent)

        if self.room_jid in app.gc_connected[self.account] and \
        app.gc_connected[self.account][self.room_jid]:
            app.connections[self.account].send_gc_status(self.nick,
                self.room_jid, show='offline', status=status)
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
            for sess in app.connections[self.account].get_sessions(fjid):
                if sess.control:
                    sess.control.no_autonegotiation = False
                if sess.enable_encryption:
                    sess.terminate_e2e()
                    app.connections[self.account].delete_session(fjid,
                        sess.thread_id)
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
        # whether to ask for comfirmation before closing muc
        if (app.config.get('confirm_close_muc') or self.room_jid in includes)\
        and app.gc_connected[self.account][self.room_jid] and self.room_jid \
        not in excludes:
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
        # whether to ask for comfirmation before closing muc
        if (app.config.get('confirm_close_muc') or self.room_jid in includes)\
        and app.gc_connected[self.account][self.room_jid] and self.room_jid \
        not in excludes:

            def on_ok(clicked):
                if clicked:
                    # user does not want to be asked again
                    app.config.set('confirm_close_muc', False)
                on_yes(self)

            def on_cancel(clicked):
                if clicked:
                    # user does not want to be asked again
                    app.config.set('confirm_close_muc', False)
                on_no(self)

            pritext = _('Are you sure you want to leave group chat "%s"?')\
                % self.name
            sectext = _('If you close this window, you will be disconnected '
                'from this group chat.')

            dialogs.ConfirmationDialogCheck(pritext, sectext,
                _('_Do not ask me again'), on_response_ok=on_ok,
                on_response_cancel=on_cancel,
                transient_for=self.parent_win.window)
            return

        on_yes(self)

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

    def _on_change_subject_menuitem_activate(self, widget):
        def on_ok(subject):
            # Note, we don't update self.subject since we don't know whether it
            # will work yet
            app.connections[self.account].send_gc_subject(self.room_jid,
                subject)

        dialogs.InputTextDialog(_('Changing Subject'),
            _('Please specify the new subject:'), input_str=self.subject,
            ok_handler=on_ok, transient_for=self.parent_win.window)

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        if not selection.get_data():
            return

        # get contact info
        contact = contacts.Contact(jid=self.room_jid, account=self.account)

        if target_type == self.TARGET_TYPE_URI_LIST:
            # file drag and drop (handled in chat_control_base)
            self.drag_data_file_transfer(contact, selection, self)
        else:
            # Invite contact to groupchat
            treeview = app.interface.roster.tree
            model = treeview.get_model()
            data = selection.get_data()
            path = treeview.get_selection().get_selected_rows()[1][0]
            iter_ = model.get_iter(path)
            type_ = model[iter_][2]
            if type_ != 'contact': # source is not a contact
                return
            contact_jid = data

            app.connections[self.account].send_invite(self.room_jid, contact_jid)
            self.print_conversation(_('%(jid)s has been invited in this room') %
                                    {'jid': contact_jid}, graphics=False)

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
            if len(splitted_text): # if there are any words
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
            if len(self.nick_hits) and self.last_key_tabs and \
               text[:-after_nick_len].endswith(self.nick_hits[0]):
                # we should cycle
                # Previous nick in list may had a space inside, so we check text
                # and not splitted_text and store it into 'begin' var
                self.nick_hits.append(self.nick_hits[0])
                begin = self.nick_hits.pop(0)
            else:
                self.nick_hits = [] # clear the hit list
                list_nick = app.contacts.get_nick_list(self.account,
                                                         self.room_jid)
                list_nick.sort(key=str.lower) # case-insensitive sort
                if begin == '':
                    # empty message, show lasts nicks that highlighted us first
                    for nick in self.attention_list:
                        if nick in list_nick:
                            list_nick.remove(nick)
                        list_nick.insert(0, nick)

                if self.nick in list_nick:
                    list_nick.remove(self.nick) # Skip self
                for nick in list_nick:
                    fjid = self.room_jid + '/' + nick
                    if nick.lower().startswith(begin.lower()) and not \
                       helpers.jid_is_blocked(self.account, fjid):
                        # the word is the begining of a nick
                        self.nick_hits.append(nick)
            if len(self.nick_hits):
                if len(splitted_text) < 2 or with_refer_to_nick_char:
                # This is the 1st word of the line or no word or we are cycling
                # at the beginning, possibly with a space in one nick
                    add = gc_refer_to_nick_char + ' '
                else:
                    add = ' '
                start_iter = end_iter.copy()
                if self.last_key_tabs and with_refer_to_nick_char or (text and \
                                                                      text[-1] == ' '):
                    # have to accomodate for the added space from last
                    # completion
                    # gc_refer_to_nick_char may be more than one char!
                    start_iter.backward_chars(len(begin) + len(add))
                elif self.last_key_tabs and not app.config.get(
                    'shell_like_completion'):
                    # have to accomodate for the added space from last
                    # completion
                    start_iter.backward_chars(len(begin) + \
                                              len(gc_refer_to_nick_char))
                else:
                    start_iter.backward_chars(len(begin))

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

    def on_list_treeview_row_expanded(self, widget, iter_, path):
        """
        When a row is expanded: change the icon of the arrow
        """
        model = widget.get_model()
        image = gtkgui_helpers.get_image_from_icon_name(
            'opened', self.scale_factor)
        model[iter_][Column.IMG] = image

    def on_list_treeview_row_collapsed(self, widget, iter_, path):
        """
        When a row is collapsed: change the icon of the arrow
        """
        model = widget.get_model()
        image = gtkgui_helpers.get_image_from_icon_name(
            'closed', self.scale_factor)
        model[iter_][Column.IMG] = image

    def kick(self, widget, nick):
        """
        Kick a user
        """
        def on_ok(reason):
            app.connections[self.account].gc_set_role(self.room_jid, nick,
                'none', reason)

        # ask for reason
        dialogs.InputDialog(_('Kicking %s') % nick,
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
        xml = gtkgui_helpers.get_gtk_builder('gc_occupants_menu.ui')

        # these conditions were taken from JEP 0045
        item = xml.get_object('kick_menuitem')
        if user_role != 'moderator' or \
        (user_affiliation == 'admin' and target_affiliation == 'owner') or \
        (user_affiliation == 'member' and target_affiliation in ('admin',
        'owner')) or (user_affiliation == 'none' and target_affiliation != \
        'none'):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.kick, nick)
        self.handlers[id_] = item

        item = xml.get_object('voice_checkmenuitem')
        item.set_active(target_role != 'visitor')
        if user_role != 'moderator' or \
        user_affiliation == 'none' or \
        (user_affiliation=='member' and target_affiliation!='none') or \
        target_affiliation in ('admin', 'owner'):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_voice_checkmenuitem_activate,
            nick)
        self.handlers[id_] = item

        item = xml.get_object('moderator_checkmenuitem')
        item.set_active(target_role == 'moderator')
        if not user_affiliation in ('admin', 'owner') or \
        target_affiliation in ('admin', 'owner'):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_moderator_checkmenuitem_activate,
            nick)
        self.handlers[id_] = item

        item = xml.get_object('ban_menuitem')
        if not user_affiliation in ('admin', 'owner') or \
        (target_affiliation in ('admin', 'owner') and\
        user_affiliation != 'owner'):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.ban, jid)
        self.handlers[id_] = item

        item = xml.get_object('member_checkmenuitem')
        item.set_active(target_affiliation != 'none')
        if not user_affiliation in ('admin', 'owner') or \
        (user_affiliation != 'owner' and target_affiliation in ('admin',
        'owner')):
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_member_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('admin_checkmenuitem')
        item.set_active(target_affiliation in ('admin', 'owner'))
        if not user_affiliation == 'owner':
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_admin_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('owner_checkmenuitem')
        item.set_active(target_affiliation == 'owner')
        if not user_affiliation == 'owner':
            item.set_sensitive(False)
        id_ = item.connect('activate', self.on_owner_checkmenuitem_activate,
            jid)
        self.handlers[id_] = item

        item = xml.get_object('invite_menuitem')
        if jid and c.name != self.nick:
            bookmarked = False
            contact = app.contacts.get_contact(self.account, jid, c.resource)
            if contact and contact.supports(nbxmpp.NS_CONFERENCE):
                bookmarked=True
            gui_menu_builder.build_invite_submenu(item, ((c, self.account),),
                ignore_rooms=[self.room_jid], show_bookmarked=bookmarked)
        else:
            item.set_sensitive(False)

        item = xml.get_object('information_menuitem')
        id_ = item.connect('activate', self.on_info, nick)
        self.handlers[id_] = item

        item = xml.get_object('history_menuitem')
        id_ = item.connect('activate', self.on_history, nick)
        self.handlers[id_] = item

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
        if not app.connections[self.account].privacy_rules_supported:
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
        if not c.resource:
            item.set_sensitive(False)
        else:
            item.set_sensitive(False)
            # ToDo: integrate HTTP File Upload
            id_ = item.connect('activate', self._on_send_file_jingle, c)
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
        adhoc_commands.CommandWindow(self.account, jid)

    def on_row_activated(self, widget, path):
        """
        When an iter is activated (dubblick or single click if gnome is set this
        way
        """
        if path.get_depth() == 1: # It's a group
            if (widget.row_expanded(path)):
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

        elif event.button == 2: # middle click
            widget.get_selection().select_path(path)
            iter_ = self.model.get_iter(path)
            if path.get_depth() == 2:
                nick = self.model[iter_][Column.NICK]
                self._start_private_message(nick)
            return True

        elif event.button == 1: # left click
            if app.single_click and not event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.on_row_activated(widget, path)
                return True
            else:
                iter_ = self.model.get_iter(path)
                nick = self.model[iter_][Column.NICK]
                if not nick in app.contacts.get_nick_list(self.account,
                self.room_jid):
                    # it's a group
                    if x < 27:
                        if (widget.row_expanded(path)):
                            widget.collapse_row(path)
                        else:
                            widget.expand_row(path, False)
                elif event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                    self.append_nick_in_msg_textview(self.msg_textview, nick)
                    self.msg_textview.grab_focus()
                    return True

    def append_nick_in_msg_textview(self, widget, nick):
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
        app.connections[self.account].gc_set_role(self.room_jid, nick,
            'participant')

    def revoke_voice(self, widget, nick):
        """
        Revoke voice privilege to a user
        """
        app.connections[self.account].gc_set_role(self.room_jid, nick,
            'visitor')

    def grant_moderator(self, widget, nick):
        """
        Grant moderator privilege to a user
        """
        app.connections[self.account].gc_set_role(self.room_jid, nick,
            'moderator')

    def revoke_moderator(self, widget, nick):
        """
        Revoke moderator privilege to a user
        """
        app.connections[self.account].gc_set_role(self.room_jid, nick,
            'participant')

    def ban(self, widget, jid):
        """
        Ban a user
        """
        def on_ok(reason):
            app.connections[self.account].gc_set_affiliation(self.room_jid,
                jid, 'outcast', reason)

        # to ban we know the real jid. so jid is not fakejid
        nick = app.get_nick_from_jid(jid)
        # ask for reason
        dialogs.InputDialog(_('Banning %s') % nick,
            _('You may specify a reason below:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def grant_membership(self, widget, jid):
        """
        Grant membership privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'member')

    def revoke_membership(self, widget, jid):
        """
        Revoke membership privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'none')

    def grant_admin(self, widget, jid):
        """
        Grant administrative privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'admin')

    def revoke_admin(self, widget, jid):
        """
        Revoke administrative privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'member')

    def grant_owner(self, widget, jid):
        """
        Grant owner privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'owner')

    def revoke_owner(self, widget, jid):
        """
        Revoke owner privilege to a user
        """
        app.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'admin')

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

    def on_history(self, widget, nick):
        jid = app.construct_fjid(self.room_jid, nick)
        self._on_history_menuitem_activate(widget=widget, jid=jid)

    def on_add_to_roster(self, widget, jid):
        dialogs.AddNewContactWindow(self.account, jid)

    def on_block(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        connection = app.connections[self.account]
        default = connection.privacy_default_list
        if fjid in connection.blocked_contacts:
            return
        max_order = connection.get_max_blocked_list_order()
        new_rule = {'order': str(max_order + 1), 'type': 'jid',
            'action': 'deny', 'value' : fjid, 'child': ['message', 'iq',
            'presence-out']}
        connection.blocked_list.append(new_rule)
        connection.blocked_contacts.append(fjid)
        self.draw_contact(nick)
        connection.set_privacy_list(default, connection.blocked_list)
        if len(connection.blocked_list) == 1:
            connection.set_default_list(default)

    def on_unblock(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        connection = app.connections[self.account]
        default = connection.privacy_default_list
        connection.new_blocked_list = []
        # needed for draw_contact:
        if fjid in connection.blocked_contacts:
            connection.blocked_contacts.remove(fjid)
        self.draw_contact(nick)
        for rule in connection.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'jid' \
            or rule['value'] != fjid:
                connection.new_blocked_list.append(rule)

        if len(connection.new_blocked_list) == 0:
            connection.blocked_list = []
            connection.blocked_contacts = []
            connection.blocked_groups = []
            connection.set_default_list('')
            connection.del_privacy_list(default)
            if 'privay_list_block' in app.interface.instances[self.account]:
                del app.interface.instances[self.account]\
                    ['privay_list_block']
        else:
            connection.set_privacy_list(default, connection.new_blocked_list)

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
