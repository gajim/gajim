# Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os

from gi.repository import Gtk
from gi.repository import Gdk

from gajim import dialogs
from gajim import config
from gajim import tooltips
from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import helpers
from gajim.gtk import SingleMessageWindow


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
        app.events.event_added_subscribe(self.on_event_added)
        app.events.event_removed_subscribe(self.on_event_removed)

    def unsubscribe_events(self):
        """
        Unregister listeners to the events class
        """
        app.events.event_added_unsubscribe(self.on_event_added)
        app.events.event_removed_unsubscribe(self.on_event_removed)

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
            self.status_icon.set_property('has-tooltip', True)
            self.status_icon.connect('activate',
                self.on_status_icon_left_clicked)
            self.status_icon.connect('popup-menu',
                self.on_status_icon_right_clicked)
            self.status_icon.connect('query-tooltip',
                self.on_status_icon_query_tooltip)
            self.status_icon.connect('size-changed', self.set_img)

        self.set_img()
        self.subscribe_events()

    def on_status_icon_right_clicked(self, widget, event_button, event_time):
        self.make_menu(event_button, event_time)

    def on_status_icon_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        tooltip.set_custom(self.tooltip.get_tooltip())
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
        self.set_img()

    def set_img(self, *args):
        """
        Apart from image, we also update tooltip text here
        """
        if not app.interface.systray_enabled:
            return
        if app.config.get('trayicon') == 'always':
            self.status_icon.set_visible(True)
        if app.events.get_nb_systray_events():
            self.status_icon.set_visible(True)

            icon_name = gtkgui_helpers.get_iconset_name_for('event')
            self.status_icon.set_from_icon_name(icon_name)
            return
        else:
            if app.config.get('trayicon') == 'on_event':
                self.status_icon.set_visible(False)

        icon_name = gtkgui_helpers.get_iconset_name_for(self.status)
        self.status_icon.set_from_icon_name(icon_name)

    def change_status(self, global_status):
        """
        Set tray image to 'global_status'
        """
        # change image and status, only if it is different
        if global_status is not None and self.status != global_status:
            self.status = global_status
        self.set_img()

    def start_chat(self, widget, account, jid):
        contact = app.contacts.get_first_contact_from_jid(account, jid)
        if app.interface.msg_win_mgr.has_window(jid, account):
            app.interface.msg_win_mgr.get_window(jid, account).set_active_tab(
                    jid, account)
        elif contact:
            app.interface.new_chat(contact, account)
            app.interface.msg_win_mgr.get_window(jid, account).set_active_tab(
                    jid, account)

    def on_single_message_menuitem_activate(self, widget, account):
        SingleMessageWindow(account, action='send')

    def on_new_chat(self, widget, account):
        app.app.activate_action('start-chat')

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
        iconset = app.config.get('iconset')
        path = os.path.join(helpers.get_iconset_path(iconset), '16x16')

        for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
            uf_show = helpers.get_uf_show(show, use_mnemonic=True)
            item = Gtk.MenuItem.new_with_mnemonic(uf_show)
            sub_menu.append(item)
            item.connect('activate', self.on_show_menuitem_activate, show)

        item = Gtk.SeparatorMenuItem.new()
        sub_menu.append(item)

        item = Gtk.MenuItem.new_with_mnemonic(_('_Change Status Message…'))
        sub_menu.append(item)
        item.connect('activate', self.on_change_status_message_activate)

        connected_accounts = app.get_number_of_connected_accounts()
        if connected_accounts < 1:
            item.set_sensitive(False)

        item = Gtk.SeparatorMenuItem.new()
        sub_menu.append(item)

        uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
        item = Gtk.MenuItem.new_with_mnemonic(uf_show)
        sub_menu.append(item)
        item.connect('activate', self.on_show_menuitem_activate, 'offline')

        iskey = connected_accounts > 0 and not (connected_accounts == 1 and
            app.zeroconf_is_connected())
        chat_with_menuitem.set_sensitive(iskey)
        single_message_menuitem.set_sensitive(iskey)
        join_gc_menuitem.set_sensitive(iskey)

        accounts_list = sorted(app.contacts.get_accounts())
        # items that get shown whether an account is zeroconf or not
        if connected_accounts > 1: # 2 or more connections? make submenus
            account_menu_for_chat_with = Gtk.Menu()
            chat_with_menuitem.set_submenu(account_menu_for_chat_with)
            self.popup_menus.append(account_menu_for_chat_with)

            for account in accounts_list:
                account_label = app.get_account_label(account)
                if app.account_is_connected(account):
                    # for chat_with
                    item = Gtk.MenuItem.new_with_label(
                        _('using account %s') % account_label)
                    account_menu_for_chat_with.append(item)
                    item.connect('activate', self.on_new_chat, account)

        elif connected_accounts == 1: # one account
            # one account connected, no need to show 'as jid'
            for account in app.connections:
                if app.connections[account].connected > 1:
                    # for start chat
                    self.new_chat_handler_id = chat_with_menuitem.connect(
                            'activate', self.on_new_chat, account)
                    break # No other connected account

        # menu items that don't apply to zeroconf connections
        if connected_accounts == 1 or (connected_accounts == 2 and \
        app.zeroconf_is_connected()):
            # only one 'real' (non-zeroconf) account is connected, don't need
            # submenus
            for account in app.connections:
                if app.account_is_connected(account) and \
                not app.config.get_per('accounts', account, 'is_zeroconf'):

                    # for single message
                    single_message_menuitem.set_submenu(None)
                    self.single_message_handler_id = single_message_menuitem.\
                            connect('activate',
                            self.on_single_message_menuitem_activate, account)
                    # join gc
                    app.interface.roster.add_bookmarks_list(gc_sub_menu,
                            account)
                    break # No other account connected
        else:
            # 2 or more 'real' accounts are connected, make submenus
            account_menu_for_single_message = Gtk.Menu()
            single_message_menuitem.set_submenu(
                    account_menu_for_single_message)
            self.popup_menus.append(account_menu_for_single_message)

            for account in accounts_list:
                account_label = app.get_account_label(account)
                if app.connections[account].is_zeroconf or \
                not app.account_is_connected(account):
                    continue
                # for single message
                item = Gtk.MenuItem.new_with_label(
                    _('using account %s') % account_label)
                item.connect('activate',
                        self.on_single_message_menuitem_activate, account)
                account_menu_for_single_message.append(item)

                # join gc
                gc_item = Gtk.MenuItem.new_with_label(
                    _('using account %s') % account_label)
                gc_sub_menu.append(gc_item)
                gc_menuitem_menu = Gtk.Menu()
                app.interface.roster.add_bookmarks_list(gc_menuitem_menu,
                        account)
                gc_item.set_submenu(gc_menuitem_menu)
                gc_sub_menu.show_all()

        newitem = Gtk.SeparatorMenuItem.new() # separator
        gc_sub_menu.append(newitem)
        newitem = Gtk.MenuItem.new_with_mnemonic(_('_Manage Bookmarks…'))
        newitem.connect('activate',
            app.interface.roster.on_manage_bookmarks_menuitem_activate)
        newitem.set_sensitive(False)
        gc_sub_menu.append(newitem)
        for account in accounts_list:
            if app.account_supports_private_storage(account):
                newitem.set_sensitive(True)
                break

        sounds_mute_menuitem.set_active(not app.config.get('sounds_on'))

        win = app.interface.roster.window
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
                item = Gtk.MenuItem.new_with_label(
                    _('Hide this menu'))
                self.systray_context_menu.prepend(item)
                self.added_hide_menuitem = True

        self.systray_context_menu.show_all()
        self.systray_context_menu.popup(None, None, None, None, 0, event_time)

    def on_show_all_events_menuitem_activate(self, widget):
        events = app.events.get_systray_events()
        for account in events:
            for jid in events[account]:
                for event in events[account][jid]:
                    app.interface.handle_event(account, jid, event.type_)

    def on_sounds_mute_menuitem_activate(self, widget):
        app.config.set('sounds_on', not widget.get_active())

    def on_show_roster_menuitem_activate(self, widget):
        win = app.interface.roster.window
        win.present()

    def on_hide_roster_menuitem_activate(self, widget):
        win = app.interface.roster.window
        win.hide()

    def on_preferences_menuitem_activate(self, widget):
        from gajim.gtk.preferences import Preferences
        window = app.get_app_window(Preferences)
        if window is None:
            Preferences()
        else:
            window.present()

    def on_quit_menuitem_activate(self, widget):
        app.interface.roster.on_quit_request()

    def on_left_click(self):
        win = app.interface.roster.window
        if len(app.events.get_systray_events()) == 0:
            # No pending events, so toggle visible/hidden for roster window
            if win.get_property('visible') and (win.get_property(
            'has-toplevel-focus') or os.name == 'nt'):
                # visible in ANY virtual desktop?

                # we could be in another VD right now. eg vd2
                # and we want to show it in vd2
                if not gtkgui_helpers.possibly_move_window_in_current_desktop(
                win) and app.config.get('save-roster-position'):
                    x, y = win.get_position()
                    app.config.set('roster_x-position', x)
                    app.config.set('roster_y-position', y)
                win.hide() # else we hide it from VD that was visible in
            else:
                if not win.get_property('visible'):
                    win.show_all()
                    if app.config.get('save-roster-position'):
                        gtkgui_helpers.move_window(win,
                            app.config.get('roster_x-position'),
                            app.config.get('roster_y-position'))
                if not app.config.get('roster_window_skip_taskbar'):
                    win.set_property('skip-taskbar-hint', False)
                win.present_with_time(Gtk.get_current_event_time())
        else:
            self.handle_first_event()

    def handle_first_event(self):
        account, jid, event = app.events.get_first_systray_event()
        if not event:
            return
        win = app.interface.roster.window
        if not win.get_property('visible') and app.config.get(
        'save-roster-position'):
            gtkgui_helpers.move_window(win,
                app.config.get('roster_x-position'),
                app.config.get('roster_y-position'))
        app.interface.handle_event(account, jid, event.type_)

    def on_middle_click(self):
        """
        Middle click raises window to have complete focus (fe. get kbd events)
        but if already raised, it hides it
        """
        win = app.interface.roster.window
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
            app.interface.roster.status_combobox.set_active(index + 2)
            return
        current = app.interface.roster.status_combobox.get_active()
        if index != current:
            app.interface.roster.status_combobox.set_active(index)

    def on_change_status_message_activate(self, widget):
        model = app.interface.roster.status_combobox.get_model()
        active = app.interface.roster.status_combobox.get_active()
        status = model[active][2]
        def on_response(message, pep_dict):
            if message is None: # None if user press Cancel
                return
            accounts = app.connections.keys()
            for acct in accounts:
                if not app.config.get_per('accounts', acct,
                        'sync_with_global_status'):
                    continue
                show = app.SHOW_LIST[app.connections[acct].connected]
                app.interface.roster.send_status(acct, show, message)
                app.interface.roster.send_pep(acct, pep_dict)
        dlg = dialogs.ChangeStatusMessageDialog(on_response, status)
        dlg.dialog.present()
