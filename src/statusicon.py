# -*- coding:utf-8 -*-
## src/statusicon.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
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

import sys
from gi.repository import Gtk
from gi.repository import GObject
import os

import dialogs
import config
import tooltips
import gtkgui_helpers
import tooltips

from common import gajim
from common import helpers
from common import pep

class StatusIcon:
    """
    Class for the notification area icon
    """

    def __init__(self):
        self.single_message_handler_id = None
        self.show_roster_handler_id = None
        self.new_chat_handler_id = None
        # click somewhere else does not popdown menu. workaround this.
        self.added_hide_menuitem = False
        self.status = 'offline'
        self.xml = gtkgui_helpers.get_gtk_builder('systray_context_menu.ui')
        self.systray_context_menu = self.xml.get_object('systray_context_menu')
        self.xml.connect_signals(self)
        self.popup_menus = []
        self.status_icon = None
        self.tooltip = tooltips.NotificationAreaTooltip()

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

    def on_event_added(self, event):
        """
        Called when an event is added to the event list
        """
        if event.show_in_systray:
            self.set_img()

    def on_event_removed(self, event_list):
        """
        Called when one or more events are removed from the event list
        """
        self.set_img()

    def show_icon(self):
        if not self.status_icon:
            self.status_icon = Gtk.StatusIcon()
            self.statusicon_size = '16'
            self.status_icon.set_property('has-tooltip', True)
            self.status_icon.connect('activate', self.on_status_icon_left_clicked)
            self.status_icon.connect('popup-menu',
                    self.on_status_icon_right_clicked)
            self.status_icon.connect('query-tooltip',
                    self.on_status_icon_query_tooltip)
            self.status_icon.connect('size-changed',
                    self.on_status_icon_size_changed)

        self.set_img()
        self.subscribe_events()

    def on_status_icon_right_clicked(self, widget, event_button, event_time):
        self.make_menu(event_button, event_time)

    def on_status_icon_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        self.tooltip.populate()
        tooltip.set_custom(self.tooltip.hbox)
        return True

    def hide_icon(self):
        self.status_icon.set_visible(False)
        self.unsubscribe_events()

    def on_status_icon_left_clicked(self, widget):
        self.on_left_click()

    def on_status_icon_size_changed(self, statusicon, size):
        if size > 31:
            self.statusicon_size = '32'
        elif size > 23:
            self.statusicon_size = '24'
        else:
            self.statusicon_size = '16'
        if os.environ.get('KDE_FULL_SESSION') == 'true':
        # detect KDE session. see #5476
            self.statusicon_size = '32'
        if os.environ.get('MATE_DESKTOP_SESSION_ID'):
        # detect MATE session.
            self.statusicon_size = '16'
        self.set_img()

    def set_img(self):
        """
        Apart from image, we also update tooltip text here
        """
        def really_set_img():
            if image.get_storage_type() == Gtk.ImageType.PIXBUF:
                self.status_icon.set_from_pixbuf(image.get_pixbuf())
            # FIXME: oops they forgot to support GIF animation?
            # or they were lazy to get it to work under Windows! WTF!
            elif image.get_storage_type() == Gtk.ImageType.ANIMATION:
                self.status_icon.set_from_pixbuf(
                        image.get_animation().get_static_image())
            #       self.status_icon.set_from_animation(image.get_animation())

        if not gajim.interface.systray_enabled:
            return
        if gajim.config.get('trayicon') == 'always':
            self.status_icon.set_visible(True)
        if gajim.events.get_nb_systray_events():
            self.status_icon.set_visible(True)
#            if gajim.config.get('trayicon_blink'):
#                self.status_icon.set_blinking(True)
#            else:
            image = gtkgui_helpers.load_icon('event')
            really_set_img()
            return
        else:
            if gajim.config.get('trayicon') == 'on_event':
                self.status_icon.set_visible(False)
#            self.status_icon.set_blinking(False)

        image = gajim.interface.jabber_state_images[self.statusicon_size][
                                                                self.status]
        really_set_img()

    def change_status(self, global_status):
        """
        Set tray image to 'global_status'
        """
        # change image and status, only if it is different
        if global_status is not None and self.status != global_status:
            self.status = global_status
        self.set_img()

    def start_chat(self, widget, account, jid):
        contact = gajim.contacts.get_first_contact_from_jid(account, jid)
        if gajim.interface.msg_win_mgr.has_window(jid, account):
            gajim.interface.msg_win_mgr.get_window(jid, account).set_active_tab(
                    jid, account)
        elif contact:
            gajim.interface.new_chat(contact, account)
            gajim.interface.msg_win_mgr.get_window(jid, account).set_active_tab(
                    jid, account)

    def on_single_message_menuitem_activate(self, widget, account):
        dialogs.SingleMessageWindow(account, action='send')

    def on_new_chat(self, widget, account):
        dialogs.NewChatDialog(account)

    def make_menu(self, event_button, event_time):
        """
        Create chat with and new message (sub) menus/menuitems
        """
        for m in self.popup_menus:
            m.destroy()

        chat_with_menuitem = self.xml.get_object('chat_with_menuitem')
        single_message_menuitem = self.xml.get_object(
                'single_message_menuitem')
        status_menuitem = self.xml.get_object('status_menu')
        join_gc_menuitem = self.xml.get_object('join_gc_menuitem')
        sounds_mute_menuitem = self.xml.get_object('sounds_mute_menuitem')
        show_roster_menuitem = self.xml.get_object('show_roster_menuitem')

        if self.single_message_handler_id:
            single_message_menuitem.handler_disconnect(
                    self.single_message_handler_id)
            self.single_message_handler_id = None
        if self.new_chat_handler_id:
            chat_with_menuitem.disconnect(self.new_chat_handler_id)
            self.new_chat_handler_id = None

        sub_menu = Gtk.Menu()
        self.popup_menus.append(sub_menu)
        status_menuitem.set_submenu(sub_menu)

        gc_sub_menu = Gtk.Menu() # gc is always a submenu
        join_gc_menuitem.set_submenu(gc_sub_menu)

        # We need our own set of status icons, let's make 'em!
        iconset = gajim.config.get('iconset')
        path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
        state_images = gtkgui_helpers.load_iconset(path)

        if 'muc_active' in state_images:
            join_gc_menuitem.set_image(state_images['muc_active'])

        for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
            uf_show = helpers.get_uf_show(show, use_mnemonic=True)
            item = Gtk.ImageMenuItem.new_with_mnemonic(uf_show)
            item.set_image(state_images[show])
            sub_menu.append(item)
            item.connect('activate', self.on_show_menuitem_activate, show)

        item = Gtk.SeparatorMenuItem.new()
        sub_menu.append(item)

        item = Gtk.ImageMenuItem.new_with_mnemonic(_('_Change Status Message...'))
        gtkgui_helpers.add_image_to_menuitem(item, 'gajim-kbd_input')
        sub_menu.append(item)
        item.connect('activate', self.on_change_status_message_activate)

        connected_accounts = gajim.get_number_of_connected_accounts()
        if connected_accounts < 1:
            item.set_sensitive(False)

        connected_accounts_with_private_storage = 0

        item = Gtk.SeparatorMenuItem.new()
        sub_menu.append(item)

        uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
        item = Gtk.ImageMenuItem.new_with_mnemonic(uf_show)
        item.set_image(state_images['offline'])
        sub_menu.append(item)
        item.connect('activate', self.on_show_menuitem_activate, 'offline')

        iskey = connected_accounts > 0 and not (connected_accounts == 1 and
            gajim.zeroconf_is_connected())
        chat_with_menuitem.set_sensitive(iskey)
        single_message_menuitem.set_sensitive(iskey)
        join_gc_menuitem.set_sensitive(iskey)

        accounts_list = sorted(gajim.contacts.get_accounts())
        # items that get shown whether an account is zeroconf or not
        if connected_accounts > 1: # 2 or more connections? make submenus
            account_menu_for_chat_with = Gtk.Menu()
            chat_with_menuitem.set_submenu(account_menu_for_chat_with)
            self.popup_menus.append(account_menu_for_chat_with)

            for account in accounts_list:
                if gajim.account_is_connected(account):
                    # for chat_with
                    item = Gtk.MenuItem(_('using account %s') % account)
                    account_menu_for_chat_with.append(item)
                    item.connect('activate', self.on_new_chat, account)

        elif connected_accounts == 1: # one account
            # one account connected, no need to show 'as jid'
            for account in gajim.connections:
                if gajim.connections[account].connected > 1:
                    # for start chat
                    self.new_chat_handler_id = chat_with_menuitem.connect(
                            'activate', self.on_new_chat, account)
                    break # No other connected account

        # menu items that don't apply to zeroconf connections
        if connected_accounts == 1 or (connected_accounts == 2 and \
        gajim.zeroconf_is_connected()):
            # only one 'real' (non-zeroconf) account is connected, don't need
            # submenus
            for account in gajim.connections:
                if gajim.account_is_connected(account) and \
                not gajim.config.get_per('accounts', account, 'is_zeroconf'):
                    if gajim.connections[account].private_storage_supported:
                        connected_accounts_with_private_storage += 1

                    # for single message
                    single_message_menuitem.set_submenu(None)
                    self.single_message_handler_id = single_message_menuitem.\
                            connect('activate',
                            self.on_single_message_menuitem_activate, account)
                    # join gc
                    gajim.interface.roster.add_bookmarks_list(gc_sub_menu,
                            account)
                    break # No other account connected
        else:
            # 2 or more 'real' accounts are connected, make submenus
            account_menu_for_single_message = Gtk.Menu()
            single_message_menuitem.set_submenu(
                    account_menu_for_single_message)
            self.popup_menus.append(account_menu_for_single_message)

            for account in accounts_list:
                if gajim.connections[account].is_zeroconf or \
                not gajim.account_is_connected(account):
                    continue
                if gajim.connections[account].private_storage_supported:
                    connected_accounts_with_private_storage += 1
                # for single message
                item = Gtk.MenuItem(_('using account %s') % account)
                item.connect('activate',
                        self.on_single_message_menuitem_activate, account)
                account_menu_for_single_message.append(item)

                # join gc
                gc_item = Gtk.MenuItem(_('using account %s') % account,
                    use_underline=False)
                gc_sub_menu.append(gc_item)
                gc_menuitem_menu = Gtk.Menu()
                gajim.interface.roster.add_bookmarks_list(gc_menuitem_menu,
                        account)
                gc_item.set_submenu(gc_menuitem_menu)
                gc_sub_menu.show_all()

        newitem = Gtk.SeparatorMenuItem.new() # separator
        gc_sub_menu.append(newitem)
        newitem = Gtk.ImageMenuItem.new_with_mnemonic(_('_Manage Bookmarks...'))
        img = Gtk.Image.new_from_stock(Gtk.STOCK_PREFERENCES, Gtk.IconSize.MENU)
        newitem.set_image(img)
        newitem.connect('activate',
                gajim.interface.roster.on_manage_bookmarks_menuitem_activate)
        gc_sub_menu.append(newitem)
        if connected_accounts_with_private_storage == 0:
            newitem.set_sensitive(False)

        sounds_mute_menuitem.set_active(not gajim.config.get('sounds_on'))

        win = gajim.interface.roster.window
        if self.show_roster_handler_id:
            show_roster_menuitem.handler_disconnect(self.show_roster_handler_id)
        if win.get_property('has-toplevel-focus'):
            show_roster_menuitem.get_children()[0].set_label(_('Hide _Roster'))
            self.show_roster_handler_id = show_roster_menuitem.connect(
                'activate', self.on_hide_roster_menuitem_activate)
        else:
            show_roster_menuitem.get_children()[0].set_label(_('Show _Roster'))
            self.show_roster_handler_id = show_roster_menuitem.connect(
                'activate', self.on_show_roster_menuitem_activate)

        if os.name == 'nt':
            if self.added_hide_menuitem is False:
                self.systray_context_menu.prepend(Gtk.SeparatorMenuItem.new())
                item = Gtk.MenuItem(_('Hide this menu'))
                self.systray_context_menu.prepend(item)
                self.added_hide_menuitem = True

        self.systray_context_menu.show_all()
        self.systray_context_menu.popup(None, None, None, None, 0, event_time)

    def on_show_all_events_menuitem_activate(self, widget):
        events = gajim.events.get_systray_events()
        for account in events:
            for jid in events[account]:
                for event in events[account][jid]:
                    gajim.interface.handle_event(account, jid, event.type_)

    def on_sounds_mute_menuitem_activate(self, widget):
        gajim.config.set('sounds_on', not widget.get_active())

    def on_show_roster_menuitem_activate(self, widget):
        win = gajim.interface.roster.window
        win.present()

    def on_hide_roster_menuitem_activate(self, widget):
        win = gajim.interface.roster.window
        win.hide()

    def on_preferences_menuitem_activate(self, widget):
        if 'preferences' in gajim.interface.instances:
            gajim.interface.instances['preferences'].window.present()
        else:
            gajim.interface.instances['preferences'] = config.PreferencesWindow()

    def on_quit_menuitem_activate(self, widget):
        gajim.interface.roster.on_quit_request()

    def on_left_click(self):
        win = gajim.interface.roster.window
        if len(gajim.events.get_systray_events()) == 0:
            # No pending events, so toggle visible/hidden for roster window
            if win.get_property('visible') and (win.get_property(
            'has-toplevel-focus') or os.name == 'nt'):
                # visible in ANY virtual desktop?

                # we could be in another VD right now. eg vd2
                # and we want to show it in vd2
                if not gtkgui_helpers.possibly_move_window_in_current_desktop(
                win) and gajim.config.get('save-roster-position'):
                    x, y = win.get_position()
                    gajim.config.set('roster_x-position', x)
                    gajim.config.set('roster_y-position', y)
                win.hide() # else we hide it from VD that was visible in
            else:
                if not win.get_property('visible'):
                    win.show_all()
                    if gajim.config.get('save-roster-position'):
                        gtkgui_helpers.move_window(win,
                            gajim.config.get('roster_x-position'),
                            gajim.config.get('roster_y-position'))
                if not gajim.config.get('roster_window_skip_taskbar'):
                    win.set_property('skip-taskbar-hint', False)
                win.present_with_time(Gtk.get_current_event_time())
        else:
            self.handle_first_event()

    def handle_first_event(self):
        account, jid, event = gajim.events.get_first_systray_event()
        if not event:
            return
        win = gajim.interface.roster.window
        if not win.get_property('visible') and gajim.config.get(
        'save-roster-position'):
            gtkgui_helpers.move_window(win,
                gajim.config.get('roster_x-position'),
                gajim.config.get('roster_y-position'))
        gajim.interface.handle_event(account, jid, event.type_)

    def on_middle_click(self):
        """
        Middle click raises window to have complete focus (fe. get kbd events)
        but if already raised, it hides it
        """
        win = gajim.interface.roster.window
        if win.is_active(): # is it fully raised? (eg does it receive kbd events?)
            win.hide()
        else:
            win.present()

    def on_clicked(self, widget, event):
        self.on_tray_leave_notify_event(widget, None)
        if event.type_ != Gdk.EventType.BUTTON_PRESS:
            return
        if event.button == 1: # Left click
            self.on_left_click()
        elif event.button == 2: # middle click
            self.on_middle_click()
        elif event.button == 3: # right click
            self.make_menu(event.button, event.time)

    def on_show_menuitem_activate(self, widget, show):
        # we all add some fake (we cannot select those nor have them as show)
        # but this helps to align with roster's status_combobox index positions
        l = ['online', 'chat', 'away', 'xa', 'dnd', 'invisible', 'SEPARATOR',
                'CHANGE_STATUS_MSG_MENUITEM', 'SEPARATOR', 'offline']
        index = l.index(show)
        if not helpers.statuses_unified():
            gajim.interface.roster.status_combobox.set_active(index + 2)
            return
        current = gajim.interface.roster.status_combobox.get_active()
        if index != current:
            gajim.interface.roster.status_combobox.set_active(index)

    def on_change_status_message_activate(self, widget):
        model = gajim.interface.roster.status_combobox.get_model()
        active = gajim.interface.roster.status_combobox.get_active()
        status = model[active][2]
        def on_response(message, pep_dict):
            if message is None: # None if user press Cancel
                return
            accounts = gajim.connections.keys()
            for acct in accounts:
                if not gajim.config.get_per('accounts', acct,
                        'sync_with_global_status'):
                    continue
                show = gajim.SHOW_LIST[gajim.connections[acct].connected]
                gajim.interface.roster.send_status(acct, show, message)
                gajim.interface.roster.send_pep(acct, pep_dict)
        dlg = dialogs.ChangeStatusMessageDialog(on_response, status)
        dlg.dialog.present()
