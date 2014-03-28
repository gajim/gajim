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

import os
import time
import locale
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GLib
import gtkgui_helpers
import gui_menu_builder
import message_control
import tooltips
import dialogs
import config
import vcard
import cell_renderer_image
import dataforms_widget
import nbxmpp

from common import gajim
from common import helpers
from common import dataforms
from common import ged
from common import i18n

from chat_control import ChatControl
from chat_control import ChatControlBase
from common.exceptions import GajimGeneralException

from command_system.implementation.hosts import PrivateChatCommands
from command_system.implementation.hosts import GroupChatCommands
from common.connection_handlers_events import GcMessageOutgoingEvent

import logging
log = logging.getLogger('gajim.groupchat_control')

#(status_image, type, nick, shown_nick)
(
C_IMG, # image to show state (online, new message etc)
C_NICK, # contact nickame or ROLE name
C_TYPE, # type of the row ('contact' or 'role')
C_TEXT, # text shown in the cellrenderer
C_AVATAR, # avatar of the contact
) = range(5)

empty_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
empty_pixbuf.fill(0xffffff00)

def set_renderer_color(treeview, renderer, set_background=True):
    """
    Set style for group row, using PRELIGHT system color
    """
    context = treeview.get_style_context()
    if set_background:
        bgcolor = context.get_background_color(Gtk.StateFlags.PRELIGHT)
        renderer.set_property('cell-background-rgba', bgcolor)
    else:
        fgcolor = context.get_color(Gtk.StateFlags.PRELIGHT)
        renderer.set_property('foreground-rgba', fgcolor)

def tree_cell_data_func(column, renderer, model, iter_, tv=None):
    # cell data func is global, because we don't want it to keep
    # reference to GroupchatControl instance (self)
    theme = gajim.config.get('roster_theme')
    # allocate space for avatar only if needed
    parent_iter = model.iter_parent(iter_)
    if isinstance(renderer, Gtk.CellRendererPixbuf):
        avatar_position = gajim.config.get('avatar_position_in_roster')
        if avatar_position == 'right':
            renderer.set_property('xalign', 1) # align pixbuf to the right
        else:
            renderer.set_property('xalign', 0.5)
        if parent_iter and (model[iter_][C_AVATAR] or avatar_position == \
        'left'):
            renderer.set_property('visible', True)
            renderer.set_property('width', gajim.config.get(
                'roster_avatar_width'))
        else:
            renderer.set_property('visible', False)
    if parent_iter:
        bgcolor = gajim.config.get_per('themes', theme, 'contactbgcolor')
        if bgcolor:
            renderer.set_property('cell-background', bgcolor)
        else:
            renderer.set_property('cell-background', None)
        if isinstance(renderer, Gtk.CellRendererText):
            # foreground property is only with CellRendererText
            color = gajim.config.get_per('themes', theme, 'contacttextcolor')
            if color:
                renderer.set_property('foreground', color)
            else:
                renderer.set_property('foreground', None)
            renderer.set_property('font',
                gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
    else: # it is root (eg. group)
        bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
        if bgcolor:
            renderer.set_property('cell-background', bgcolor)
        else:
            set_renderer_color(tv, renderer)
        if isinstance(renderer, Gtk.CellRendererText):
            # foreground property is only with CellRendererText
            color = gajim.config.get_per('themes', theme, 'grouptextcolor')
            if color:
                renderer.set_property('foreground', color)
            else:
                set_renderer_color(tv, renderer, False)
            renderer.set_property('font',
                gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))


class PrivateChatControl(ChatControl):
    TYPE_ID = message_control.TYPE_PM

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, parent_win, gc_contact, contact, account, session):
        room_jid = gc_contact.room_jid
        self.room_ctrl = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
            account)
        if room_jid in gajim.interface.minimized_controls[account]:
            self.room_ctrl = gajim.interface.minimized_controls[account][room_jid]
        if self.room_ctrl:
            self.room_name = self.room_ctrl.name
        else:
            self.room_name = room_jid
        self.gc_contact = gc_contact
        ChatControl.__init__(self, parent_win, contact, account, session)
        self.TYPE_ID = 'pm'
        gajim.ged.register_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received_pm)
        gajim.ged.register_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)

    def get_our_nick(self):
        return self.room_ctrl.nick

    def shutdown(self):
        super(PrivateChatControl, self).shutdown()
        gajim.ged.remove_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received_pm)
        gajim.ged.remove_event_handler('gc-presence-received', ged.GUI1,
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
            gc_c = gajim.contacts.get_gc_contact(obj.conn.name, obj.room_jid,
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
            gajim.interface.msg_win_mgr.change_key(old_jid, new_jid,
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
        contact = gajim.contacts.get_first_contact_from_jid(self.account,
                self.contact.jid)
        if not contact:
            # contact was from pm in MUC
            room, nick = gajim.get_room_and_nick_from_fjid(self.contact.jid)
            gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
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

    def update_contact(self):
        self.contact = self.gc_contact.as_contact()

    def begin_e2e_negotiation(self):
        self.no_autonegotiation = True

        if not self.session:
            fjid = self.gc_contact.get_full_jid()
            new_sess = gajim.connections[self.account].make_new_session(fjid,
                type_=self.type_id)
            self.set_session(new_sess)

        self.session.negotiate_e2e(False)

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Set compact view menuitem active state sets active and sensitivity state
        for toggle_gpg_menuitem sets sensitivity for history_menuitem (False for
        tranasports) and file_transfer_menuitem and hide()/show() for
        add_to_roster_menuitem
        """
        menu = gui_menu_builder.get_contact_menu(self.contact, self.account,
            use_multiple_contacts=False, show_start_chat=False,
            show_encryption=True, control=self,
            show_buttonbar_items=not hide_buttonbar_items,
            gc_contact=self.gc_contact,
            is_anonymous=self.room_ctrl.is_anonymous)
        return menu

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
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(False)

        self.actions_button = self.xml.get_object('muc_window_actions_button')
        id_ = self.actions_button.connect('clicked',
            self.on_actions_button_clicked)
        self.handlers[id_] = self.actions_button

        widget = self.xml.get_object('change_nick_button')
        widget.set_sensitive(False)
        id_ = widget.connect('clicked', self._on_change_nick_menuitem_activate)
        self.handlers[id_] = widget

        widget = self.xml.get_object('change_subject_button')
        widget.set_sensitive(False)
        id_ = widget.connect('clicked',
            self._on_change_subject_menuitem_activate)
        self.handlers[id_] = widget

        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(False)

        widget = self.xml.get_object('bookmark_button')
        for bm in gajim.connections[self.account].bookmarks:
            if bm['jid'] == self.contact.jid:
                widget.hide()
                break
        else:
            id_ = widget.connect('clicked',
                self._on_bookmark_room_menuitem_activate)
            self.handlers[id_] = widget

            if gtkgui_helpers.gtk_icon_theme.has_icon('bookmark-new'):
                img = self.xml.get_object('image7')
                img.set_from_icon_name('bookmark-new', Gtk.IconSize.MENU)
            widget.set_sensitive(
                gajim.connections[self.account].private_storage_supported or \
                (gajim.connections[self.account].pubsub_supported and \
                gajim.connections[self.account].pubsub_publish_options_supported))
            widget.show()

        if gtkgui_helpers.gtk_icon_theme.has_icon('document-open-recent'):
            img = self.xml.get_object('history_image')
            img.set_from_icon_name('document-open-recent', Gtk.IconSize.MENU)
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

        id_ = widget.connect('motion_notify_event',
            self.on_list_treeview_motion_notify_event)
        self.handlers[id_] = widget

        id_ = widget.connect('leave_notify_event',
            self.on_list_treeview_leave_notify_event)
        self.handlers[id_] = widget

        self.room_jid = self.contact.jid
        self.nick = contact.name
        self.new_nick = ''
        self.name = ''
        for bm in gajim.connections[self.account].bookmarks:
            if bm['jid'] == self.room_jid:
                self.name = bm['name']
                break
        if not self.name:
            self.name = self.room_jid.split('@')[0]

        compact_view = gajim.config.get('compact_view')
        self.chat_buttons_set_visible(compact_view)
        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            gajim.config.get('hide_groupchat_banner'))
        self.widget_set_visible(self.xml.get_object('list_scrolledwindow'),
            gajim.config.get('hide_groupchat_occupants_list'))

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

        self.tooltip = tooltips.GCTooltip()

        # nickname coloring
        self.gc_count_nicknames_colors = -1
        self.gc_custom_colors = {}
        self.number_of_colors = len(gajim.config.get('gc_nicknames_colors').\
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
        self.resize_from_another_muc = False
        # we want to know when the the widget resizes, because that is
        # an indication that the hpaned has moved...
        self.hpaned = self.xml.get_object('hpaned')
        id_ = self.hpaned.connect('notify', self.on_hpaned_notify)
        self.handlers[id_] = self.hpaned

        # set the position of the current hpaned
        hpaned_position = gajim.config.get('gc-hpaned-position')
        self.hpaned.set_position(hpaned_position)

        #status_image, shown_nick, type, nickname, avatar
        self.columns = [Gtk.Image, str, str, str, GdkPixbuf.Pixbuf]
        self.model = Gtk.TreeStore(*self.columns)
        self.model.set_sort_func(C_NICK, self.tree_compare_iters)
        self.model.set_sort_column_id(C_NICK, Gtk.SortType.ASCENDING)

        # columns
        column = Gtk.TreeViewColumn()
        # list of renderers with attributes / properties in the form:
        # (name, renderer_object, expand?, attribute_name, attribute_value,
        # cell_data_func, func_arg)
        self.renderers_list = []
        # Number of renderers plugins added
        self.nb_ext_renderers = 0
        self.renderers_propertys = {}
        renderer_image = cell_renderer_image.CellRendererImage(0, 0)
        self.renderers_propertys[renderer_image] = ('width', 26)
        renderer_text = Gtk.CellRendererText()
        self.renderers_propertys[renderer_text] = ('ellipsize',
            Pango.EllipsizeMode.END)

        self.renderers_list += (
            # status img
            ('icon', renderer_image, False,
            'image', C_IMG, tree_cell_data_func, self.list_treeview),
            # contact name
            ('name', renderer_text, True,
            'markup', C_TEXT, tree_cell_data_func, self.list_treeview))

        # avatar img
        avater_renderer = ('avatar', Gtk.CellRendererPixbuf(),
            False, 'pixbuf', C_AVATAR,
            tree_cell_data_func, self.list_treeview)

        if gajim.config.get('avatar_position_in_roster') == 'right':
            self.renderers_list.append(avater_renderer)
        else:
            self.renderers_list.insert(0, avater_renderer)

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

        gajim.ged.register_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)
        gajim.ged.register_event_handler('gc-message-received', ged.GUI1,
            self._nec_gc_message_received)
        gajim.ged.register_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        gajim.ged.register_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.register_event_handler('gc-subject-received', ged.GUI1,
            self._nec_gc_subject_received)
        gajim.ged.register_event_handler('gc-config-changed-received', ged.GUI1,
            self._nec_gc_config_changed_received)
        gajim.ged.register_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        gajim.ged.register_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)
        gajim.gc_connected[self.account][self.room_jid] = False
        # disable win, we are not connected yet
        ChatControlBase.got_disconnected(self)

        self.update_ui()
        self.widget.show_all()

        # PluginSystem: adding GUI extension point for this GroupchatControl
        # instance object
        gajim.plugin_manager.gui_extension_point('groupchat_control', self)

    def fill_column(self, col):
        for rend in self.renderers_list:
            col.pack_start(rend[1], rend[2])
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
        type1 = model[iter1][C_TYPE]
        type2 = model[iter2][C_TYPE]
        if not type1 or not type2:
            return 0
        nick1 = model[iter1][C_NICK]
        nick2 = model[iter2][C_NICK]
        if not nick1 or not nick2:
            return 0
        if type1 == 'role':
            return locale.strcoll(nick1, nick2)
        if type1 == 'contact':
            gc_contact1 = gajim.contacts.get_gc_contact(self.account,
                    self.room_jid, nick1)
            if not gc_contact1:
                return 0
        if type2 == 'contact':
            gc_contact2 = gajim.contacts.get_gc_contact(self.account,
                    self.room_jid, nick2)
            if not gc_contact2:
                return 0
        if type1 == 'contact' and type2 == 'contact' and \
        gajim.config.get('sort_by_show_in_muc'):
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

        item = Gtk.MenuItem(_('Insert Nickname'))
        menu.prepend(item)
        submenu = Gtk.Menu()
        item.set_submenu(submenu)

        for nick in sorted(gajim.contacts.get_nick_list(self.account,
        self.room_jid)):
            item = Gtk.MenuItem(nick, use_underline=False)
            submenu.append(item)
            id_ = item.connect('activate', self.append_nick_in_msg_textview,
                nick)
            self.handlers[id_] = item

        menu.show_all()

    def resize_occupant_treeview(self, position):
        self.resize_from_another_muc = True
        self.hpaned.set_position(position)
        def reset_flag():
            self.resize_from_another_muc = False
        # Reset the flag when everything will be redrawn, and in particular when
        # on_treeview_size_allocate will have been called.
        GLib.idle_add(reset_flag)

    def on_hpaned_notify(self, pane, gparamspec):
        """
        The MUC treeview has resized. Move the hpaned in all tabs to match
        """
       # print pane, dir(pane)
        #if gparamspec.name != 'position':
            #return
        if self.resize_from_another_muc:
            # Don't send the event to other MUC
            return

        hpaned_position = self.hpaned.get_position()
        gajim.config.set('gc-hpaned-position', hpaned_position)
        for account in gajim.gc_connected:
            for room_jid in [i for i in gajim.gc_connected[account] if \
            gajim.gc_connected[account][i] and i != self.room_jid]:
                ctrl = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
                    account)
                if not ctrl and room_jid in \
                gajim.interface.minimized_controls[account]:
                    ctrl = gajim.interface.minimized_controls[account][room_jid]
                if ctrl and gajim.config.get('one_message_window') != 'never':
                    ctrl.resize_occupant_treeview(hpaned_position)

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
            nick = contact[C_NICK]
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
        nick = contact[C_NICK]
        self._last_selected_contact = nick
        if contact[C_TYPE] != 'contact':
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
        color_name = None
        color = None
        theme = gajim.config.get('roster_theme')
        context = self.parent_win.notebook.get_style_context()
        if chatstate == 'attention' and (not has_focus or not current_tab):
            self.attention_flag = True
            color_name = gajim.config.get_per('themes', theme,
                'state_muc_directed_msg_color')
        elif chatstate:
            if chatstate == 'active' or (current_tab and has_focus):
                self.attention_flag = False
                # get active color from gtk
                color = context.get_color(Gtk.StateFlags.ACTIVE)
            elif chatstate == 'newmsg' and (not has_focus or not current_tab) \
            and not self.attention_flag:
                color_name = gajim.config.get_per('themes', theme,
                    'state_muc_msg_color')
        if color_name:
            color = Gdk.RGBA()
            ok = Gdk.RGBA.parse(color, color_name)
            if not ok:
                del color
                color = context.get_color(Gtk.StateFlags.ACTIVE)

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
        # Set tab image (always 16x16)
        tab_image = None
        if gajim.gc_connected[self.account][self.room_jid]:
            tab_image = gtkgui_helpers.load_icon('muc_active')
        else:
            tab_image = gtkgui_helpers.load_icon('muc_inactive')
        return tab_image

    def update_ui(self):
        ChatControlBase.update_ui(self)
        for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
            self.draw_contact(nick)

    def _change_style(self, model, path, iter_, option):
        model[iter_][C_NICK] = model[iter_][C_NICK]

    def change_roster_style(self):
        self.model.foreach(self._change_style, None)

    def repaint_themed_widgets(self):
        ChatControlBase.repaint_themed_widgets(self)
        self.change_roster_style()

    def _update_banner_state_image(self):
        banner_status_img = self.xml.get_object('gc_banner_status_image')
        images = gajim.interface.jabber_state_images
        if self.room_jid in gajim.gc_connected[self.account] and \
        gajim.gc_connected[self.account][self.room_jid]:
            image = 'muc_active'
        else:
            image = 'muc_inactive'
        if '32' in images and image in images['32']:
            muc_icon = images['32'][image]
            if muc_icon.get_storage_type() != Gtk.ImageType.EMPTY:
                pix = muc_icon.get_pixbuf()
                banner_status_img.set_from_pixbuf(pix)
                return
        # we need to scale 16x16 to 32x32
        muc_icon = images['16'][image]
        pix = muc_icon.get_pixbuf()
        scaled_pix = pix.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
        banner_status_img.set_from_pixbuf(scaled_pix)

    def get_continued_conversation_name(self):
        """
        Get the name of a continued conversation.  Will return Continued
        Conversation if there isn't any other contact in the room
        """
        nicks = []
        for nick in gajim.contacts.get_nick_list(self.account,
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
        self.banner_status_label.set_ellipsize(Pango.EllipsizeMode.END)
        font_attrs, font_attrs_small = self.get_font_attrs()
        if self.is_continued:
            name = self.get_continued_conversation_name()
        else:
            name = self.room_jid
        text = '<span %s>%s</span>' % (font_attrs, '\u200E' + name)
        self.name_label.set_markup(text)

        if self.subject:
            subject = helpers.reduce_chars_newlines(self.subject, max_lines=2)
            subject = GLib.markup_escape_text(subject)
            subject_text = self.urlfinder.sub(self.make_href, subject)
            subject_text = '<span %s>%s</span>' % (font_attrs_small,
                subject_text)

            # tooltip must always hold ALL the subject
            self.event_box.set_tooltip_text(self.subject)
            self.banner_status_label.set_no_show_all(False)
            self.banner_status_label.show()
        else:
            subject_text = ''
            self.event_box.set_has_tooltip(False)
            self.banner_status_label.hide()
            self.banner_status_label.set_no_show_all(True)

        self.banner_status_label.set_markup(subject_text)

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Set sensitivity state for configure_room
        """
        xml = gtkgui_helpers.get_gtk_builder('gc_control_popup_menu.ui')
        menu = xml.get_object('gc_control_popup_menu')

        bookmark_room_menuitem = xml.get_object('bookmark_room_menuitem')
        change_nick_menuitem = xml.get_object('change_nick_menuitem')
        configure_room_menuitem = xml.get_object('configure_room_menuitem')
        destroy_room_menuitem = xml.get_object('destroy_room_menuitem')
        change_subject_menuitem = xml.get_object('change_subject_menuitem')
        history_menuitem = xml.get_object('history_menuitem')
        minimize_menuitem = xml.get_object('minimize_menuitem')
        request_voice_menuitem = xml.get_object('request_voice_menuitem')
        bookmark_separator = xml.get_object('bookmark_separator')
        separatormenuitem2 = xml.get_object('separatormenuitem2')
        request_voice_separator = xml.get_object('request_voice_separator')

        if gtkgui_helpers.gtk_icon_theme.has_icon('bookmark-new'):
            img = Gtk.Image()
            img.set_from_icon_name('bookmark-new', Gtk.IconSize.MENU)
            bookmark_room_menuitem.set_image(img)
        if gtkgui_helpers.gtk_icon_theme.has_icon('document-open-recent'):
            img = Gtk.Image()
            img.set_from_icon_name('document-open-recent', Gtk.IconSize.MENU)
            history_menuitem.set_image(img)

        if hide_buttonbar_items:
            change_nick_menuitem.hide()
            change_subject_menuitem.hide()
            bookmark_room_menuitem.hide()
            history_menuitem.hide()
            bookmark_separator.hide()
            separatormenuitem2.hide()
        else:
            change_nick_menuitem.show()
            change_subject_menuitem.show()
            bookmark_room_menuitem.show()
            history_menuitem.show()
            bookmark_separator.show()
            separatormenuitem2.show()
            for bm in gajim.connections[self.account].bookmarks:
                if bm['jid'] == self.room_jid:
                    bookmark_room_menuitem.hide()
                    bookmark_separator.hide()
                    break

        ag = Gtk.accel_groups_from_object(self.parent_win.window)[0]
        change_nick_menuitem.add_accelerator('activate', ag, Gdk.KEY_n,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, Gtk.AccelFlags.VISIBLE)
        change_subject_menuitem.add_accelerator('activate', ag,
            Gdk.KEY_t, Gdk.ModifierType.MOD1_MASK, Gtk.AccelFlags.VISIBLE)
        bookmark_room_menuitem.add_accelerator('activate', ag, Gdk.KEY_b,
            Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        history_menuitem.add_accelerator('activate', ag, Gdk.KEY_h,
            Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)

        if self.contact.jid in gajim.config.get_per('accounts', self.account,
        'minimized_gc').split(' '):
            minimize_menuitem.set_active(True)
        conn = gajim.connections[self.account]
        if not conn.private_storage_supported and (not conn.pubsub_supported or \
        not conn.pubsub_publish_options_supported):
            bookmark_room_menuitem.set_sensitive(False)
        if gajim.gc_connected[self.account][self.room_jid]:
            c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
                self.nick)
            if c.affiliation not in ('owner', 'admin'):
                configure_room_menuitem.set_sensitive(False)
            else:
                configure_room_menuitem.set_sensitive(True)
            if c.affiliation != 'owner':
                destroy_room_menuitem.set_sensitive(False)
            else:
                destroy_room_menuitem.set_sensitive(True)
            change_subject_menuitem.set_sensitive(True)
            change_nick_menuitem.set_sensitive(True)
            if c.role == 'visitor':
                request_voice_menuitem.set_sensitive(True)
            else:
                request_voice_menuitem.set_sensitive(False)
        else:
            # We are not connected to this groupchat, disable unusable menuitems
            configure_room_menuitem.set_sensitive(False)
            destroy_room_menuitem.set_sensitive(False)
            change_subject_menuitem.set_sensitive(False)
            change_nick_menuitem.set_sensitive(False)
            request_voice_menuitem.set_sensitive(False)

        # connect the menuitems to their respective functions
        id_ = bookmark_room_menuitem.connect('activate',
            self._on_bookmark_room_menuitem_activate)
        self.handlers[id_] = bookmark_room_menuitem

        id_ = change_nick_menuitem.connect('activate',
            self._on_change_nick_menuitem_activate)
        self.handlers[id_] = change_nick_menuitem

        id_ = configure_room_menuitem.connect('activate',
            self._on_configure_room_menuitem_activate)
        self.handlers[id_] = configure_room_menuitem

        id_ = destroy_room_menuitem.connect('activate',
            self._on_destroy_room_menuitem_activate)
        self.handlers[id_] = destroy_room_menuitem

        id_ = change_subject_menuitem.connect('activate',
            self._on_change_subject_menuitem_activate)
        self.handlers[id_] = change_subject_menuitem

        id_ = history_menuitem.connect('activate',
            self._on_history_menuitem_activate)
        self.handlers[id_] = history_menuitem

        id_ = request_voice_menuitem.connect('activate',
            self._on_request_voice_menuitem_activate)
        self.handlers[id_] = request_voice_menuitem

        id_ = minimize_menuitem.connect('toggled',
            self.on_minimize_menuitem_toggled)
        self.handlers[id_] = minimize_menuitem

        menu.connect('selection-done', self.destroy_menu,
            change_nick_menuitem, change_subject_menuitem,
            bookmark_room_menuitem, history_menuitem)
        return menu

    def destroy_menu(self, menu, change_nick_menuitem, change_subject_menuitem,
    bookmark_room_menuitem, history_menuitem):
        # destroy accelerators
        ag = Gtk.accel_groups_from_object(self.parent_win.window)[0]
        change_nick_menuitem.remove_accelerator(ag, Gdk.KEY_n,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        change_subject_menuitem.remove_accelerator(ag, Gdk.KEY_t,
            Gdk.ModifierType.MOD1_MASK)
        bookmark_room_menuitem.remove_accelerator(ag, Gdk.KEY_b,
            Gdk.ModifierType.CONTROL_MASK)
        history_menuitem.remove_accelerator(ag, Gdk.KEY_h,
            Gdk.ModifierType.CONTROL_MASK)
        # destroy menu
        menu.destroy()

    def _nec_vcard_published(self, obj):
        if obj.conn.name != self.account:
            return
        show = gajim.SHOW_LIST[obj.conn.connected]
        status = obj.conn.status
        obj.conn.send_gc_status(self.nick, self.room_jid, show, status)

    def _nec_vcard_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.room_jid:
            return
        self.draw_avatar(obj.resource)

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
            self.print_conversation(obj.msgtxt, tim=obj.timestamp,
                xhtml=obj.xhtml_msgtxt, displaymarking=obj.displaymarking)
        else:
            # message from someone
            if obj.has_timestamp:
                # don't print xhtml if it's an old message.
                # Like that xhtml messages are grayed too.
                self.print_old_conversation(obj.msgtxt, contact=obj.nick,
                    tim=obj.timestamp, xhtml=None,
                    displaymarking=obj.displaymarking)
            else:
                if obj.nick in self.last_received_txt and obj.correct_id and \
                obj.correct_id == self.last_received_id[obj.nick]:
                    if obj.nick == self.nick:
                        old_txt = self.last_sent_txt
                        self.last_sent_txt = obj.msgtxt
                        self.conv_textview.correct_last_sent_message(obj.msgtxt,
                            obj.xhtml_msgtxt, obj.nick, old_txt)
                    else:
                        old_txt = self.last_received_txt[obj.nick]
                        (highlight, sound) = self.highlighting_for_message(obj.msgtxt, obj.timestamp)
                        other_tags_for_name = []
                        other_tags_for_text = []
                        if obj.nick in self.gc_custom_colors:
                            other_tags_for_name.append('gc_nickname_color_' + \
                                str(self.gc_custom_colors[obj.nick]))
                        else:
                            self.gc_count_nicknames_colors += 1
                            if self.gc_count_nicknames_colors == \
                            self.number_of_colors:
                                self.gc_count_nicknames_colors = 0
                            self.gc_custom_colors[obj.nick] = \
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

                            if obj.nick in self.attention_list:
                                self.attention_list.remove(obj.nick)
                            elif len(self.attention_list) > 6:
                                self.attention_list.pop(0) # remove older
                            self.attention_list.append(obj.nick)

                        if obj.msgtxt.startswith('/me ') or \
                        obj.msgtxt.startswith('/me\n'):
                            other_tags_for_text.append('gc_nickname_color_' + \
                                str(self.gc_custom_colors[obj.nick]))
                        self.conv_textview.correct_last_received_message(
                            obj.msgtxt, obj.xhtml_msgtxt, obj.nick, old_txt,
                            other_tags_for_name=other_tags_for_name,
                            other_tags_for_text=other_tags_for_text)
                    self.last_received_txt[obj.nick] = obj.msgtxt
                    self.last_received_id[obj.nick] = obj.stanza.getID()
                    return
                if obj.nick == self.nick:
                    self.last_sent_txt = obj.msgtxt
                self.print_conversation(obj.msgtxt, contact=obj.nick,
                    tim=obj.timestamp, xhtml=obj.xhtml_msgtxt,
                    displaymarking=obj.displaymarking,
                    correct_id=(obj.stanza.getID(), None))
        obj.needs_highlight = self.needs_visual_notification(obj.msgtxt)

    def on_private_message(self, nick, msg, tim, xhtml, session, msg_id=None,
    encrypted=False, displaymarking=None):
        # Do we have a queue?
        fjid = self.room_jid + '/' + nick
        no_queue = len(gajim.events.get_events(self.account, fjid)) == 0

        event = gajim.events.create_event('pm', (msg, '', 'incoming', tim,
            encrypted, '', msg_id, xhtml, session, None, displaymarking, False))
        gajim.events.add_event(self.account, fjid, event)

        autopopup = gajim.config.get('autopopup')
        autopopupaway = gajim.config.get('autopopupaway')
        iter_ = self.get_contact_iter(nick)
        path = self.model.get_path(iter_)
        if not autopopup or (not autopopupaway and \
        gajim.connections[self.account].connected > 2):
            if no_queue: # We didn't have a queue: we change icons
                state_images = \
                    gajim.interface.roster.get_appropriate_state_images(
                    self.room_jid, icon_name='event')
                image = state_images['event']
                self.model[iter_][C_IMG] = image
            if self.parent_win:
                self.parent_win.show_title()
                self.parent_win.redraw_tab(self)
        else:
            self._start_private_message(nick)
        # Scroll to line
        path_ = path
        path_.up()
        self.list_treeview.expand_row(path_, False)
        self.list_treeview.scroll_to_cell(path)
        self.list_treeview.set_cursor(path)
        contact = gajim.contacts.get_contact_with_highest_priority(
            self.account, self.room_jid)
        if contact:
            gajim.interface.roster.draw_contact(self.room_jid, self.account)

    def get_contact_iter(self, nick):
        role_iter = self.model.get_iter_first()
        while role_iter:
            user_iter = self.model.iter_children(role_iter)
            while user_iter:
                if nick == self.model[user_iter][C_NICK]:
                    return user_iter
                else:
                    user_iter = self.model.iter_next(user_iter)
            role_iter = self.model.iter_next(role_iter)
        return None

    def print_old_conversation(self, text, contact='', tim=None, xhtml = None,
    displaymarking=None):
        if contact:
            if contact == self.nick: # it's us
                kind = 'outgoing'
            else:
                kind = 'incoming'
        else:
            kind = 'status'
        if gajim.config.get('restored_messages_small'):
            small_attr = ['small']
        else:
            small_attr = []
        ChatControlBase.print_conversation_line(self, text, kind, contact, tim,
            small_attr, small_attr + ['restored_message'],
            small_attr + ['restored_message'], count_as_new=False, xhtml=xhtml,
            displaymarking=displaymarking)

    def print_conversation(self, text, contact='', tim=None, xhtml=None,
    graphics=True, displaymarking=None, correct_id=None):
        """
        Print a line in the conversation

        If contact is set: it's a message from someone or an info message
        (contact = 'info' in such a case).
        If contact is not set: it's a message from the server or help.
        """
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
            correct_id=correct_id)

    def get_nb_unread(self):
        type_events = ['printed_marked_gc_msg']
        if gajim.config.get('notify_on_all_muc_messages'):
            type_events.append('printed_gc_msg')
        nb = len(gajim.events.get_events(self.account, self.room_jid,
            type_events))
        nb += self.get_nb_unread_pm()
        return nb

    def get_nb_unread_pm(self):
        nb = 0
        for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
            nb += len(gajim.events.get_events(self.account, self.room_jid + \
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
            if gajim.config.get_per('soundevents', 'muc_message_highlight',
            'enabled'):
                sound = 'highlight'

        # Do we play a sound on every muc message?
        elif gajim.config.get_per('soundevents', 'muc_message_received', \
        'enabled'):
            sound = 'received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim != time.localtime():
            sound = None

        return (highlight, sound)

    def check_and_possibly_add_focus_out_line(self):
        """
        Check and possibly add focus out line for room_jid if it needs it and
        does not already have it as last event. If it goes to add this line
        - remove previous line first
        """
        win = gajim.interface.msg_win_mgr.get_window(self.room_jid,
            self.account)
        if win and self.room_jid == win.get_active_jid() and\
        win.window.get_property('has-toplevel-focus') and\
        self.parent_win.get_active_control() == self:
            # it's the current room and it's the focused window.
            # we have full focus (we are reading it!)
            return

        at_the_end = self.conv_textview.at_the_end()
        self.conv_textview.show_focus_out_line(scroll=at_the_end)

    def needs_visual_notification(self, text):
        """
        Check text to see whether any of the words in (muc_highlight_words and
        nick) appear
        """
        special_words = gajim.config.get('muc_highlight_words').split(';')
        special_words.append(self.nick)
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
            changes.append(_('A non-privacy-related room configuration change '
                'has occurred'))
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
            changes.append(_('Room is now fully-anonymous'))
            self.is_anonymous = True

        for change in changes:
            self.print_conversation(change)

    def _nec_signed_in(self, obj):
        if obj.conn.name != self.account:
            return
        if self.room_jid in gajim.gc_connected[obj.conn.name] and \
        gajim.gc_connected[obj.conn.name][self.room_jid]:
            return
        password = gajim.gc_passwords.get(self.room_jid, '')
        obj.conn.join_gc(self.nick, self.room_jid, password, rejoin=True)

    def _nec_decrypted_message_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.gc_control == self and obj.resource:
            # We got a pm from this room
            nick = obj.resource
            if obj.session.control:
                # print if a control is open
                obj.session.control.print_conversation(obj.msgtxt,
                    tim=obj.timestamp, xhtml=obj.xhtml, encrypted=obj.encrypted,
                    displaymarking=obj.displaymarking)
            else:
                # otherwise pass it off to the control to be queued
                self.on_private_message(nick, obj.msgtxt, obj.timestamp,
                    obj.xhtml, self.session, msg_id=obj.msg_id,
                    encrypted=obj.encrypted, displaymarking=obj.displaymarking)

    def got_connected(self):
        # Make autorejoin stop.
        if self.autorejoin:
            GLib.source_remove(self.autorejoin)
        self.autorejoin = None

        gajim.gc_connected[self.account][self.room_jid] = True
        ChatControlBase.got_connected(self)
        self.list_treeview.set_model(self.model)
        self.list_treeview.expand_all()
        # We don't redraw the whole banner here, because only icon change
        self._update_banner_state_image()
        if self.parent_win:
            self.parent_win.redraw_tab(self)

        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(True)
        emoticons_button = self.xml.get_object('emoticons_button')
        emoticons_button.set_sensitive(True)
        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(True)
        change_nick_button = self.xml.get_object('change_nick_button')
        change_nick_button.set_sensitive(True)
        change_subject_button = self.xml.get_object('change_subject_button')
        change_subject_button.set_sensitive(True)

    def got_disconnected(self):
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(False)
        emoticons_button = self.xml.get_object('emoticons_button')
        emoticons_button.set_sensitive(False)
        formattings_button = self.xml.get_object('formattings_button')
        formattings_button.set_sensitive(False)
        change_nick_button = self.xml.get_object('change_nick_button')
        change_nick_button.set_sensitive(False)
        change_subject_button = self.xml.get_object('change_subject_button')
        change_subject_button.set_sensitive(False)
        self.list_treeview.set_model(None)
        self.model.clear()
        nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
        for nick in nick_list:
            # Update pm chat window
            fjid = self.room_jid + '/' + nick
            gc_contact = gajim.contacts.get_gc_contact(self.account,
                self.room_jid, nick)

            ctrl = gajim.interface.msg_win_mgr.get_control(fjid, self.account)
            if ctrl:
                gc_contact.show = 'offline'
                gc_contact.status = ''
                ctrl.update_ui()
                if ctrl.parent_win:
                    ctrl.parent_win.redraw_tab(ctrl)

            gajim.contacts.remove_gc_contact(self.account, gc_contact)
        gajim.gc_connected[self.account][self.room_jid] = False
        ChatControlBase.got_disconnected(self)
        # Tell connection to note the date we disconnect to avoid duplicate logs
        gajim.connections[self.account].gc_got_disconnected(self.room_jid)
        # We don't redraw the whole banner here, because only icon change
        self._update_banner_state_image()
        if self.parent_win:
            self.parent_win.redraw_tab(self)

        # Autorejoin stuff goes here.
        # Notice that we don't need to activate autorejoin if connection is lost
        # or in progress.
        if self.autorejoin is None and gajim.account_is_connected(self.account):
            ar_to = gajim.config.get('muc_autorejoin_timeout')
            if ar_to:
                self.autorejoin = GLib.timeout_add_seconds(ar_to, self.rejoin)

    def rejoin(self):
        if not self.autorejoin:
            return False
        password = gajim.gc_passwords.get(self.room_jid, '')
        gajim.connections[self.account].join_gc(self.nick, self.room_jid,
            password, rejoin=True)
        return True

    def draw_roster(self):
        self.model.clear()
        for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
            gc_contact = gajim.contacts.get_gc_contact(self.account,
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
            nick = model[iter_][C_NICK]

        ctrl = self._start_private_message(nick)
        if ctrl and msg:
            ctrl.send_message(msg)

    def on_send_file(self, widget, gc_contact):
        """
        Send a file to a contact in the room
        """
        self._on_send_file(gc_contact)

    def draw_contact(self, nick, selected=False, focus=False):
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return
        gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        state_images = gajim.interface.jabber_state_images['16']
        if len(gajim.events.get_events(self.account, self.room_jid + '/' + \
        nick)):
            image = state_images['event']
        else:
            image = state_images[gc_contact.show]

        name = GLib.markup_escape_text(gc_contact.name)

        # Strike name if blocked
        fjid = self.room_jid + '/' + nick
        if helpers.jid_is_blocked(self.account, fjid):
            name = '<span strikethrough="true">%s</span>' % name

        status = gc_contact.status
        # add status msg, if not empty, under contact name in the treeview
        if status and gajim.config.get('show_status_msgs_in_roster'):
            status = status.strip()
            if status != '':
                status = helpers.reduce_chars_newlines(status, max_lines=1)
                # escape markup entities and make them small italic and fg color
                color = gtkgui_helpers.get_fade_color(self.list_treeview,
                        selected, focus)
                colorstring = "#%04x%04x%04x" % (color.red, color.green,
                    color.blue)
                name += ('\n<span size="small" style="italic" foreground="%s">'
                    '%s</span>') % (colorstring, GLib.markup_escape_text(
                    status))

        if image.get_storage_type() == Gtk.ImageType.PIXBUF and \
        gc_contact.affiliation != 'none' and gajim.config.get(
        'show_affiliation_in_groupchat'):
            pixbuf1 = image.get_pixbuf().copy()
            pixbuf2 = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 4, 4)
            if gc_contact.affiliation == 'owner':
                pixbuf2.fill(0xff0000ff) # Red
            elif gc_contact.affiliation == 'admin':
                pixbuf2.fill(0xffb200ff) # Oragne
            elif gc_contact.affiliation == 'member':
                pixbuf2.fill(0x00ff00ff) # Green
            pixbuf2.composite(pixbuf1, 12, 12, pixbuf2.get_property('width'),
                pixbuf2.get_property('height'), 0, 0, 1.0, 1.0,
                GdkPixbuf.InterpType.HYPER, 127)
            image = Gtk.Image.new_from_pixbuf(pixbuf1)
        self.model[iter_][C_IMG] = image
        self.model[iter_][C_TEXT] = name

    def draw_avatar(self, nick):
        if not gajim.config.get('show_avatars_in_roster'):
            return
        iter_ = self.get_contact_iter(nick)
        if not iter_:
            return
        fake_jid = self.room_jid + '/' + nick
        pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(fake_jid)
        if pixbuf in ('ask', None):
            scaled_pixbuf = empty_pixbuf
        else:
            scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
            if not scaled_pixbuf:
                scaled_pixbuf = empty_pixbuf
        self.model[iter_][C_AVATAR] = scaled_pixbuf

    def draw_role(self, role):
        role_iter = self.get_role_iter(role)
        if not role_iter:
            return
        role_name = helpers.get_uf_role(role, plural=True)
        if gajim.config.get('show_contacts_number'):
            nbr_role, nbr_total = gajim.contacts.get_nb_role_total_gc_contacts(
                self.account, self.room_jid, role)
            role_name += ' (%s/%s)' % (repr(nbr_role), repr(nbr_total))
        self.model[role_iter][C_TEXT] = role_name

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
            simple_jid = gajim.get_jid_without_resource(obj.real_jid)
            nick_jid += ' (%s)' % simple_jid

        # status_code
        # http://www.xmpp.org/extensions/xep-0045.html#registrar-statuscodes-\
        # init
        if obj.status_code:
            if '110' in obj.status_code:
                # We just join the room
                if self.room_jid in gajim.automatic_rooms[self.account] and \
                gajim.automatic_rooms[self.account][self.room_jid]['invities']:
                    if self.room_jid not in gajim.interface.instances[
                    self.account]['gc_config']:
                        if obj.role == 'owner':
                            # We need to configure the room if it's a new one.
                            # We cannot know it's a new one. Status 201 is not
                            # sent by all servers.
                            gajim.connections[self.account].request_gc_config(
                                self.room_jid)
                        elif 'continue_tag' not in gajim.automatic_rooms[
                        self.account][self.room_jid]:
                            # We just need to invite contacts
                            for jid in gajim.automatic_rooms[self.account][
                            self.room_jid]['invities']:
                                obj.conn.send_invite(self.room_jid, jid)
                                self.print_conversation(_('%(jid)s has been '
                                    'invited in this room') % {'jid': jid},
                                    graphics=False)
            if '100' in obj.status_code:
                # Can be a message (see handle_event_gc_config_change in
                # gajim.py)
                self.print_conversation(
                    _('Any occupant is allowed to see your full JID'))
                self.is_anonymous = False
            if '170' in obj.status_code:
                # Can be a message (see handle_event_gc_config_change in
                # gajim.py)
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
                    if obj.nick == self.nick and not gajim.config.get(
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
                        nick_list = gajim.contacts.get_nick_list(self.account,
                            self.room_jid)
                        for nick_ in nick_list:
                            fjid_ = self.room_jid + '/' + nick_
                            ctrl = gajim.interface.msg_win_mgr.get_control(
                                fjid_, self.account)
                            if ctrl and ctrl.session and \
                            ctrl.session.enable_encryption:
                                thread_id = ctrl.session.thread_id
                                ctrl.session.terminate_e2e()
                                gajim.connections[self.account].delete_session(
                                    fjid_, thread_id)
                                ctrl.no_autonegotiation = False
                    else:
                        s = _('%(nick)s is now known as %(new_nick)s') % {
                            'nick': nick, 'new_nick': obj.new_nick}
                    tv = self.conv_textview
                    if obj.nick in tv.last_received_message_marks:
                        tv.last_received_message_marks[obj.new_nick] = \
                            tv.last_received_message_marks[obj.nick]
                        del tv.last_received_message_marks[obj.nick]
                    if obj.nick in self.last_received_txt:
                        self.last_received_txt[obj.new_nick] = \
                            self.last_received_txt[obj.nick]
                        del self.last_received_txt[obj.nick]
                        self.last_received_id[obj.new_nick] = \
                            self.last_received_id[obj.nick]
                        del self.last_received_id[obj.nick]
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
                    # rename vcard / avatar
                    puny_jid = helpers.sanitize_filename(self.room_jid)
                    puny_nick = helpers.sanitize_filename(obj.nick)
                    puny_new_nick = helpers.sanitize_filename(obj.new_nick)
                    old_path = os.path.join(gajim.VCARD_PATH, puny_jid,
                        puny_nick)
                    new_path = os.path.join(gajim.VCARD_PATH, puny_jid,
                        puny_new_nick)
                    files = {old_path: new_path}
                    path = os.path.join(gajim.AVATAR_PATH, puny_jid)
                    # possible extensions
                    for ext in ('.png', '.jpeg', '_notif_size_bw.png',
                    '_notif_size_colored.png'):
                        files[os.path.join(path, puny_nick + ext)] = \
                            os.path.join(path, puny_new_nick + ext)
                    for old_file in files:
                        if os.path.exists(old_file) and old_file != \
                        files[old_file]:
                            if os.path.exists(files[old_file]) and \
                            helpers.windowsify(old_file) != helpers.windowsify(
                            files[old_file]):
                                # Windows require this, but os.remove('test')
                                # will also remove 'TEST'
                                os.remove(files[old_file])
                            os.rename(old_file, files[old_file])
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

            if len(gajim.events.get_events(self.account, jid=obj.fjid,
            types=['pm'])) == 0:
                self.remove_contact(obj.nick)
                self.draw_all_roles()
            else:
                c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
                    obj.nick)
                c.show = obj.show
                c.status = obj.status
            if obj.nick == self.nick and (not obj.status_code or \
            '303' not in obj.status_code): # We became offline
                self.got_disconnected()
                contact = gajim.contacts.\
                    get_contact_with_highest_priority(self.account,
                    self.room_jid)
                if contact:
                    gajim.interface.roster.draw_contact(self.room_jid,
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
                    affiliation, obj.status, obj.real_jid)
                newly_created = True
                self.draw_all_roles()
                if obj.status_code and '201' in obj.status_code:
                    # We just created the room
                    gajim.connections[self.account].request_gc_config(
                        self.room_jid)
            else:
                gc_c = gajim.contacts.get_gc_contact(self.account,
                    self.room_jid, obj.nick)
                if not gc_c:
                    log.error('%s has an iter, but no gc_contact instance' % \
                        obj.nick)
                    return
                # Re-get vcard if avatar has changed
                # We do that here because we may request it to the real JID if
                # we knows it. connections.py doesn't know it.
                con = gajim.connections[self.account]
                if gc_c and gc_c.jid:
                    real_jid = gc_c.jid
                else:
                    real_jid = obj.fjid
                if obj.fjid in obj.conn.vcard_shas:
                    if obj.avatar_sha != obj.conn.vcard_shas[obj.fjid]:
                        server = gajim.get_server_from_jid(self.room_jid)
                        if not server.startswith('irc'):
                            obj.conn.request_vcard(real_jid, obj.fjid)
                else:
                    cached_vcard = obj.conn.get_cached_vcard(obj.fjid, True)
                    if cached_vcard and 'PHOTO' in cached_vcard and \
                    'SHA' in cached_vcard['PHOTO']:
                        cached_sha = cached_vcard['PHOTO']['SHA']
                    else:
                        cached_sha = ''
                    if cached_sha != obj.avatar_sha:
                        # avatar has been updated
                        # sha in mem will be updated later
                        server = gajim.get_server_from_jid(self.room_jid)
                        if not server.startswith('irc'):
                            obj.conn.request_vcard(real_jid, obj.fjid)
                    else:
                        # save sha in mem NOW
                        obj.conn.vcard_shas[obj.fjid] = obj.avatar_sha

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
            for bookmark in gajim.connections[self.account].bookmarks:
                if bookmark['jid'] == self.room_jid:
                    print_status = bookmark.get('print_status', None)
                    break
            if not print_status:
                print_status = gajim.config.get('print_status_in_muc')
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

    def add_contact_to_roster(self, nick, show, role, affiliation, status,
    jid=''):
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
            role_iter = self.model.append(None,
                [gajim.interface.jabber_state_images['16']['closed'], role,
                'role', role_name,  None] + [None] * self.nb_ext_renderers)
            self.draw_all_roles()
        iter_ = self.model.append(role_iter, [None, nick, 'contact', name, None] + \
                [None] * self.nb_ext_renderers)
        if not nick in gajim.contacts.get_nick_list(self.account,
        self.room_jid):
            gc_contact = gajim.contacts.create_gc_contact(
                room_jid=self.room_jid, account=self.account,
                name=nick, show=show, status=status, role=role,
                affiliation=affiliation, jid=j, resource=resource)
            gajim.contacts.add_gc_contact(self.account, gc_contact)
        self.draw_contact(nick)
        self.draw_avatar(nick)
        # Do not ask avatar to irc rooms as irc transports reply with messages
        server = gajim.get_server_from_jid(self.room_jid)
        if gajim.config.get('ask_avatars_on_startup') and \
        not server.startswith('irc'):
            fake_jid = self.room_jid + '/' + nick
            pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(fake_jid)
            if pixbuf == 'ask':
                if j and not self.is_anonymous:
                    gajim.connections[self.account].request_vcard(j, fake_jid)
                else:
                    gajim.connections[self.account].request_vcard(fake_jid,
                        fake_jid)
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
            role_name = self.model[role_iter][C_NICK]
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
        gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        if gc_contact:
            gajim.contacts.remove_gc_contact(self.account, gc_contact)
        parent_iter = self.model.iter_parent(iter_)
        self.model.remove(iter_)
        if self.model.iter_n_children(parent_iter) == 0:
            self.model.remove(parent_iter)

    def send_message(self, message, xhtml=None, process_commands=True):
        """
        Call this function to send our message
        """
        if not message:
            return

        if process_commands and self.process_as_command(message):
            return

        message = helpers.remove_invalid_xml_chars(message)

        if not message:
            return

        label = self.get_seclabel()
        if message != '' or message != '\n':
            self.save_message(message, 'sent')

            def _cb(msg, msg_txt):
                # we'll save sent message text when we'll receive it in
                # _nec_gc_message_received
                self.last_sent_msg = msg
                if self.correcting:
                    self.correcting = False
                    self.msg_textview.override_background_color(
                        Gtk.StateType.NORMAL, self.old_message_tv_color)

            if self.correcting and self.last_sent_msg:
                correction_msg = self.last_sent_msg
            else:
                correction_msg = None
            # Send the message
            gajim.nec.push_outgoing_event(GcMessageOutgoingEvent(None,
                account=self.account, jid=self.room_jid, message=message,
                xhtml=xhtml, label=label, callback=_cb,
                callback_args=[_cb] + [message], correction_msg=correction_msg))
            self.msg_textview.get_buffer().set_text('')
            self.msg_textview.grab_focus()

    def get_role(self, nick):
        gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
                nick)
        if gc_contact:
            return gc_contact.role
        else:
            return 'visitor'

    def minimizable(self):
        if self.contact.jid in gajim.config.get_per('accounts', self.account,
        'minimized_gc').split(' '):
            return True
        return False

    def minimize(self, status='offline'):
        # Minimize it
        win = gajim.interface.msg_win_mgr.get_window(self.contact.jid,
                self.account)
        ctrl = win.get_control(self.contact.jid, self.account)

        ctrl_page = win.notebook.page_num(ctrl.widget)
        control = win.notebook.get_nth_page(ctrl_page)

        win.notebook.remove_page(ctrl_page)
        control.unparent()
        ctrl.parent_win = None

        gajim.interface.roster.add_groupchat(self.contact.jid, self.account,
            status = self.subject)

        del win._controls[self.account][self.contact.jid]

    def shutdown(self, status='offline'):
        # PluginSystem: calling shutdown of super class (ChatControlBase)
        # to let it remove it's GUI extension points
        super(GroupchatControl, self).shutdown()
        # PluginSystem: removing GUI extension points connected with
        # GrouphatControl instance object
        gajim.plugin_manager.remove_gui_extension_point('groupchat_control',
            self)

        # Preventing autorejoin from being activated
        self.autorejoin = False

        gajim.ged.remove_event_handler('gc-presence-received', ged.GUI1,
            self._nec_gc_presence_received)
        gajim.ged.remove_event_handler('gc-message-received', ged.GUI1,
            self._nec_gc_message_received)
        gajim.ged.remove_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        gajim.ged.remove_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.remove_event_handler('gc-subject-received', ged.GUI1,
            self._nec_gc_subject_received)
        gajim.ged.remove_event_handler('gc-config-changed-received', ged.GUI1,
            self._nec_gc_config_changed_received)
        gajim.ged.remove_event_handler('signed-in', ged.GUI1,
            self._nec_signed_in)
        gajim.ged.remove_event_handler('decrypted-message-received', ged.GUI2,
            self._nec_decrypted_message_received)

        if self.room_jid in gajim.gc_connected[self.account] and \
        gajim.gc_connected[self.account][self.room_jid]:
            # Tell connection to note the date we disconnect to avoid duplicate
            # logs. We do it only when connected because if connection was lost
            # there may be new messages since disconnection.
            gajim.connections[self.account].gc_got_disconnected(self.room_jid)
            gajim.connections[self.account].send_gc_status(self.nick,
                self.room_jid, show='offline', status=status)
        nick_list = gajim.contacts.get_nick_list(self.account, self.room_jid)
        for nick in nick_list:
            # Update pm chat window
            fjid = self.room_jid + '/' + nick
            ctrl = gajim.interface.msg_win_mgr.get_gc_control(fjid,
                self.account)
            if ctrl:
                contact = gajim.contacts.get_gc_contact(self.account,
                    self.room_jid, nick)
                contact.show = 'offline'
                contact.status = ''
                ctrl.update_ui()
                ctrl.parent_win.redraw_tab(ctrl)
            for sess in gajim.connections[self.account].get_sessions(fjid):
                if sess.control:
                    sess.control.no_autonegotiation = False
                if sess.enable_encryption:
                    sess.terminate_e2e()
                    gajim.connections[self.account].delete_session(fjid,
                        sess.thread_id)
        # They can already be removed by the destroy function
        if self.room_jid in gajim.contacts.get_gc_list(self.account):
            gajim.contacts.remove_room(self.account, self.room_jid)
            del gajim.gc_connected[self.account][self.room_jid]
        # Save hpaned position
        gajim.config.set('gc-hpaned-position', self.hpaned.get_position())
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]
        # Remove unread events from systray
        gajim.events.remove_events(self.account, self.room_jid)

    def safe_shutdown(self):
        if self.minimizable():
            return True
        includes = gajim.config.get('confirm_close_muc_rooms').split(' ')
        excludes = gajim.config.get('noconfirm_close_muc_rooms').split(' ')
        # whether to ask for comfirmation before closing muc
        if (gajim.config.get('confirm_close_muc') or self.room_jid in includes)\
        and gajim.gc_connected[self.account][self.room_jid] and self.room_jid \
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
        includes = gajim.config.get('confirm_close_muc_rooms').split(' ')
        excludes = gajim.config.get('noconfirm_close_muc_rooms').split(' ')
        # whether to ask for comfirmation before closing muc
        if (gajim.config.get('confirm_close_muc') or self.room_jid in includes)\
        and gajim.gc_connected[self.account][self.room_jid] and self.room_jid \
        not in excludes:

            def on_ok(clicked):
                if clicked:
                    # user does not want to be asked again
                    gajim.config.set('confirm_close_muc', False)
                on_yes(self)

            def on_cancel(clicked):
                if clicked:
                    # user does not want to be asked again
                    gajim.config.set('confirm_close_muc', False)
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
        for nick in gajim.contacts.get_nick_list(self.account, self.room_jid):
            fjid = self.room_jid + '/' + nick
            nb += len(gajim.events.get_events(self.account, fjid))
            # gc can only have messages as event
        return nb

    def _on_change_subject_menuitem_activate(self, widget):
        def on_ok(subject):
            # Note, we don't update self.subject since we don't know whether it
            # will work yet
            gajim.connections[self.account].send_gc_subject(self.room_jid,
                subject)

        dialogs.InputTextDialog(_('Changing Subject'),
            _('Please specify the new subject:'), input_str=self.subject,
            ok_handler=on_ok)

    def _on_change_nick_menuitem_activate(self, widget):
        if 'change_nick_dialog' in gajim.interface.instances:
            gajim.interface.instances['change_nick_dialog'].present()
        else:
            title = _('Changing Nickname')
            prompt = _('Please specify the new nickname you want to use:')
            gajim.interface.instances['change_nick_dialog'] = \
                dialogs.ChangeNickDialog(self.account, self.room_jid, title,
                prompt, change_nick=True)

    def _on_configure_room_menuitem_activate(self, widget):
        c = gajim.contacts.get_gc_contact(self.account, self.room_jid,
            self.nick)
        if c.affiliation == 'owner':
            gajim.connections[self.account].request_gc_config(self.room_jid)
        elif c.affiliation == 'admin':
            if self.room_jid not in gajim.interface.instances[self.account][
            'gc_config']:
                gajim.interface.instances[self.account]['gc_config'][
                    self.room_jid] = config.GroupchatConfigWindow(self.account,
                    self.room_jid)

    def _on_destroy_room_menuitem_activate(self, widget):
        def on_ok(reason, jid):
            if jid:
                # Test jid
                try:
                    jid = helpers.parse_jid(jid)
                except Exception:
                    dialogs.ErrorDialog(_('Invalid group chat Jabber ID'),
                    _('The group chat Jabber ID has not allowed characters.'))
                    return
            gajim.connections[self.account].destroy_gc_room(self.room_jid,
                reason, jid)

        # Ask for a reason
        dialogs.DoubleInputDialog(_('Destroying %s') % '\u200E' + \
            self.room_jid, _('You are going to definitively destroy this '
            'room.\nYou may specify a reason below:'),
            _('You may also enter an alternate venue:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def _on_bookmark_room_menuitem_activate(self, widget):
        """
        Bookmark the room, without autojoin and not minimized
        """
        password = gajim.gc_passwords.get(self.room_jid, '')
        gajim.interface.add_gc_bookmark(self.account, self.name, self.room_jid,\
            '0', '0', password, self.nick)

    def _on_request_voice_menuitem_activate(self, widget):
        """
        Request voice in the current room
        """
        gajim.connections[self.account].request_voice(self.room_jid)

    def _on_drag_data_received(self, widget, context, x, y, selection,
    target_type, timestamp):
        # Invite contact to groupchat
        treeview = gajim.interface.roster.tree
        model = treeview.get_model()
        if not selection.data or target_type == 80:
            #  target_type = 80 means a file is dropped
            return
        data = selection.data
        path = treeview.get_selection().get_selected_rows()[1][0]
        iter_ = model.get_iter(path)
        type_ = model[iter_][2]
        if type_ != 'contact': # source is not a contact
            return
        contact_jid = data
        gajim.connections[self.account].send_invite(self.room_jid, contact_jid)
        self.print_conversation(_('%(jid)s has been invited in this room') % {
            'jid': contact_jid}, graphics=False)

    def handle_message_textview_mykey_press(self, widget, event_keyval,
    event_keymod):
        # NOTE: handles mykeypress which is custom signal connected to this
        # CB in new_room(). for this singal see message_textview.py

        if not widget.get_sensitive():
            # Textview is not sensitive, don't handle keypress
            return
        # construct event instance from binding
        event = Gdk.Event(Gdk.EventType.KEY_PRESS) # it's always a key-press here
        event.keyval = event_keyval
        event.state = event_keymod
        event.time = 0 # assign current time

        message_buffer = widget.get_buffer()
        start_iter, end_iter = message_buffer.get_bounds()

        if event.keyval == Gdk.KEY_Tab: # TAB
            cursor_position = message_buffer.get_insert()
            end_iter = message_buffer.get_iter_at_mark(cursor_position)
            text = message_buffer.get_text(start_iter, end_iter, False).decode(
                'utf-8')

            splitted_text = text.split()

            # HACK: Not the best soltution.
            if (text.startswith(self.COMMAND_PREFIX) and not
            text.startswith(self.COMMAND_PREFIX * 2) and \
            len(splitted_text) == 1):
                return super(GroupchatControl, self).\
                    handle_message_textview_mykey_press(widget, event_keyval,
                    event_keymod)

            # nick completion
            # check if tab is pressed with empty message
            if len(splitted_text): # if there are any words
                begin = splitted_text[-1] # last word we typed
            else:
                begin = ''

            gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
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
                list_nick = gajim.contacts.get_nick_list(self.account,
                    self.room_jid)
                list_nick.sort(key=str.lower) # case-insensitive sort
                if begin == '':
                    # empty message, show lasts nicks that highlighted us first
                    for nick in self.attention_list:
                        if nick in list_nick:
                            list_nick.remove(nick)
                        list_nick.insert(0, nick)

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
                elif self.last_key_tabs and not gajim.config.get(
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
                if gajim.config.get('shell_like_completion') and \
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
        image = gajim.interface.jabber_state_images['16']['opened']
        model[iter_][C_IMG] = image

    def on_list_treeview_row_collapsed(self, widget, iter_, path):
        """
        When a row is collapsed: change the icon of the arrow
        """
        model = widget.get_model()
        image = gajim.interface.jabber_state_images['16']['closed']
        model[iter_][C_IMG] = image

    def kick(self, widget, nick):
        """
        Kick a user
        """
        def on_ok(reason):
            gajim.connections[self.account].gc_set_role(self.room_jid, nick,
                'none', reason)

        # ask for reason
        dialogs.InputDialog(_('Kicking %s') % nick,
            _('You may specify a reason below:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def mk_menu(self, event, iter_):
        """
        Make contact's popup menu
        """
        nick = self.model[iter_][C_NICK]
        c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
        fjid = self.room_jid + '/' + nick
        jid = c.jid
        target_affiliation = c.affiliation
        target_role = c.role

        # looking for user's affiliation and role
        user_nick = self.nick
        user_affiliation = gajim.contacts.get_gc_contact(self.account,
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
        muc_icon = gtkgui_helpers.load_icon('muc_active')
        if muc_icon:
            item.set_image(muc_icon)
        if jid and c.name != self.nick:
            bookmarked = False
            contact = gajim.contacts.get_contact(self.account, jid, c.resource)
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
        if gtkgui_helpers.gtk_icon_theme.has_icon('document-open-recent'):
            img = Gtk.Image()
            img.set_from_icon_name('document-open-recent', Gtk.IconSize.MENU)
            item.set_image(img)
        id_ = item.connect('activate', self.on_history, nick)
        self.handlers[id_] = item

        item = xml.get_object('add_to_roster_menuitem')
        our_jid = gajim.get_jid_from_account(self.account)
        if not jid or jid == our_jid or not gajim.connections[self.account].\
        roster_supported:
            item.set_sensitive(False)
        else:
            id_ = item.connect('activate', self.on_add_to_roster, jid)
            self.handlers[id_] = item

        item = xml.get_object('block_menuitem')
        item2 = xml.get_object('unblock_menuitem')
        if helpers.jid_is_blocked(self.account, fjid):
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
        # add a special img for send file menuitem
        pixbuf = gtkgui_helpers.get_icon_pixmap('document-send', quiet=True)
        img = Gtk.Image.new_from_pixbuf(pixbuf)
        item.set_image(img)

        if not c.resource:
            item.set_sensitive(False)
        else:
            id_ = item.connect('activate', self.on_send_file, c)
            self.handlers[id_] = item

        # show the popup now!
        menu = xml.get_object('gc_occupants_menu')
        menu.show_all()
        menu.attach_to_widget(gajim.interface.roster.window, None)
        menu.popup(None, None, None, None, event.button, event.time)

    def _start_private_message(self, nick):
        gc_c = gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
        nick_jid = gc_c.get_full_jid()

        ctrl = gajim.interface.msg_win_mgr.get_control(nick_jid, self.account)
        if not ctrl:
            ctrl = gajim.interface.new_private_chat(gc_c, self.account)

        if ctrl:
            ctrl.parent_win.set_active_tab(ctrl)

        return ctrl

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
            nick = self.model[path][C_NICK]
            self._start_private_message(nick)

    def on_list_treeview_row_activated(self, widget, path, col=0):
        """
        When an iter is double clicked: open the chat window
        """
        if not gajim.single_click:
            self.on_row_activated(widget, path)

    def on_list_treeview_button_press_event(self, widget, event):
        """
        Popup user's group's or agent menu
        """
        # hide tooltip, no matter the button is pressed
        self.tooltip.hide_tooltip()
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
                nick = self.model[iter_][C_NICK]
                self._start_private_message(nick)
            return True

        elif event.button == 1: # left click
            if gajim.single_click and not event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.on_row_activated(widget, path)
                return True
            else:
                iter_ = self.model.get_iter(path)
                nick = self.model[iter_][C_NICK]
                if not nick in gajim.contacts.get_nick_list(self.account,
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
            gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
            add = gc_refer_to_nick_char + ' '
        message_buffer.insert_at_cursor(start + nick + add)

    def on_list_treeview_motion_notify_event(self, widget, event):
        props = widget.get_path_at_pos(int(event.x), int(event.y))
        if self.tooltip.timeout > 0:
            if not props or self.tooltip.id != props[0]:
                self.tooltip.hide_tooltip()
        if props:
            [row, col, x, y] = props
            iter_ = None
            try:
                iter_ = self.model.get_iter(row)
            except Exception:
                self.tooltip.hide_tooltip()
                return
            typ = self.model[iter_][C_TYPE]
            if typ == 'contact':
                account = self.account

                if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
                    self.tooltip.id = row
                    nick = self.model[iter_][C_NICK]
                    self.tooltip.timeout = GLib.timeout_add(500,
                        self.show_tooltip, gajim.contacts.get_gc_contact(
                        account, self.room_jid, nick))

    def on_list_treeview_leave_notify_event(self, widget, event):
        props = widget.get_path_at_pos(int(event.x), int(event.y))
        if self.tooltip.timeout > 0:
            if not props or self.tooltip.id == props[0]:
                self.tooltip.hide_tooltip()

    def show_tooltip(self, contact):
        if not self.list_treeview.get_window():
            # control has been destroyed since tooltip was requested
            return
        w = self.list_treeview.get_window()
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        props = self.list_treeview.get_path_at_pos(pointer[1], pointer[2])
        # check if the current pointer is at the same path
        # as it was before setting the timeout
        if props and self.tooltip.id == props[0]:
            rect = self.list_treeview.get_cell_area(props[0], props[1])
            position = w.get_origin()[1:]
            self.tooltip.show_tooltip(contact, rect.height,
                position[1] + rect.y)
        else:
            self.tooltip.hide_tooltip()

    def grant_voice(self, widget, nick):
        """
        Grant voice privilege to a user
        """
        gajim.connections[self.account].gc_set_role(self.room_jid, nick,
            'participant')

    def revoke_voice(self, widget, nick):
        """
        Revoke voice privilege to a user
        """
        gajim.connections[self.account].gc_set_role(self.room_jid, nick,
            'visitor')

    def grant_moderator(self, widget, nick):
        """
        Grant moderator privilege to a user
        """
        gajim.connections[self.account].gc_set_role(self.room_jid, nick,
            'moderator')

    def revoke_moderator(self, widget, nick):
        """
        Revoke moderator privilege to a user
        """
        gajim.connections[self.account].gc_set_role(self.room_jid, nick,
            'participant')

    def ban(self, widget, jid):
        """
        Ban a user
        """
        def on_ok(reason):
            gajim.connections[self.account].gc_set_affiliation(self.room_jid,
                jid, 'outcast', reason)

        # to ban we know the real jid. so jid is not fakejid
        nick = gajim.get_nick_from_jid(jid)
        # ask for reason
        dialogs.InputDialog(_('Banning %s') % nick,
            _('You may specify a reason below:'), ok_handler=on_ok,
            transient_for=self.parent_win.window)

    def grant_membership(self, widget, jid):
        """
        Grant membership privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'member')

    def revoke_membership(self, widget, jid):
        """
        Revoke membership privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'none')

    def grant_admin(self, widget, jid):
        """
        Grant administrative privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'admin')

    def revoke_admin(self, widget, jid):
        """
        Revoke administrative privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'member')

    def grant_owner(self, widget, jid):
        """
        Grant owner privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'owner')

    def revoke_owner(self, widget, jid):
        """
        Revoke owner privilege to a user
        """
        gajim.connections[self.account].gc_set_affiliation(self.room_jid, jid,
            'admin')

    def on_info(self, widget, nick):
        """
         Call vcard_information_window class to display user's information
        """
        gc_contact = gajim.contacts.get_gc_contact(self.account, self.room_jid,
            nick)
        contact = gc_contact.as_contact()
        if contact.jid in gajim.interface.instances[self.account]['infos']:
            gajim.interface.instances[self.account]['infos'][contact.jid].\
                window.present()
        else:
            gajim.interface.instances[self.account]['infos'][contact.jid] = \
                vcard.VcardWindow(contact, self.account, gc_contact)

    def on_history(self, widget, nick):
        jid = gajim.construct_fjid(self.room_jid, nick)
        self._on_history_menuitem_activate(widget=widget, jid=jid)

    def on_add_to_roster(self, widget, jid):
        dialogs.AddNewContactWindow(self.account, jid)

    def on_block(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        connection = gajim.connections[self.account]
        if fjid in connection.blocked_contacts:
            return
        max_order = connection.get_max_blocked_list_order()
        new_rule = {'order': str(max_order + 1), 'type': 'jid',
            'action': 'deny', 'value' : fjid, 'child': ['message', 'iq',
            'presence-out']}
        connection.blocked_list.append(new_rule)
        connection.blocked_contacts.append(fjid)
        self.draw_contact(nick)
        connection.set_privacy_list('block', connection.blocked_list)
        if len(connection.blocked_list) == 1:
            connection.set_active_list('block')
            connection.set_default_list('block')
        connection.get_privacy_list('block')

    def on_unblock(self, widget, nick):
        fjid = self.room_jid + '/' + nick
        connection = gajim.connections[self.account]
        connection.new_blocked_list = []
        # needed for draw_contact:
        if fjid in connection.blocked_contacts:
            connection.blocked_contacts.remove(fjid)
        self.draw_contact(nick)
        for rule in connection.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'jid' \
            or rule['value'] != fjid:
                connection.new_blocked_list.append(rule)

        connection.set_privacy_list('block', connection.new_blocked_list)
        connection.get_privacy_list('block')
        if len(connection.new_blocked_list) == 0:
            connection.blocked_list = []
            connection.blocked_contacts = []
            connection.blocked_groups = []
            connection.set_default_list('')
            connection.set_active_list('')
            connection.del_privacy_list('block')
            if 'privay_list_block' in gajim.interface.instances[self.account]:
                del gajim.interface.instances[self.account]\
                    ['privay_list_block']

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
