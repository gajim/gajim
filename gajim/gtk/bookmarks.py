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

from enum import IntEnum

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _

from gajim import gui_menu_builder

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.util import get_builder


class Row(IntEnum):
    ACCOUNT_JID = 0
    ROOM_NAME = 1
    ROOM_JID = 2
    AUTOJOIN = 3
    PASSWORD = 4
    NICK = 5
    LABEL = 6


class ManageBookmarksWindow:
    def __init__(self):
        self.xml = get_builder('manage_bookmarks_window.ui')
        self.window = self.xml.get_object('manage_bookmarks_window')
        self.window.set_transient_for(app.interface.roster.window)

        self.ignore_events = False

        # Account-JID, RoomName, Room-JID, Autojoin, Password, Nick, Name
        self.treestore = Gtk.TreeStore(str, str, str, bool, str, str, str)
        self.treestore.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        # Store bookmarks in treeview.
        for account, account_label in app.get_enabled_accounts_with_labels(
                connected_only=True, private_storage_only=True):
            iter_ = self.treestore.append(None, [
                None, account, None, None,
                None, None, account_label])

            con = app.connections[account]
            bookmarks = con.get_module('Bookmarks').get_sorted_bookmarks()

            for jid, bookmark in bookmarks.items():
                self.treestore.append(iter_, [account,
                                              bookmark['name'],
                                              jid,
                                              bookmark['autojoin'],
                                              bookmark['password'],
                                              bookmark['nick'],
                                              bookmark['name']])

        self.view = self.xml.get_object('bookmarks_treeview')
        self.view.set_model(self.treestore)
        self.view.expand_all()

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Bookmarks', renderer, text=Row.LABEL)
        self.view.append_column(column)

        self.selection = self.view.get_selection()
        self.selection.connect('changed', self.bookmark_selected)

        # Prepare input fields
        self.title_entry = self.xml.get_object('title_entry')
        self.title_entry.connect('changed', self.on_title_entry_changed)
        self.nick_entry = self.xml.get_object('nick_entry')
        self.nick_entry.connect('changed', self.on_nick_entry_changed)
        self.server_entry = self.xml.get_object('server_entry')
        self.server_entry.connect(
            'focus-out-event', self.on_server_entry_focus_out)
        self.room_entry = self.xml.get_object('room_entry')
        self.room_entry_changed_id = self.room_entry.connect(
            'changed', self.on_room_entry_changed)
        self.pass_entry = self.xml.get_object('pass_entry')
        self.pass_entry.connect('changed', self.on_pass_entry_changed)
        self.autojoin_checkbutton = self.xml.get_object('autojoin_checkbutton')
        self.settings_box = self.xml.get_object('settings_box')
        self.remove_bookmark_button = self.xml.get_object(
            'remove_bookmark_button')

        self.xml.connect_signals(self)
        self.window.show_all()
        # select root iter
        first_iter = self.treestore.get_iter_first()
        if first_iter:
            self.selection.select_iter(first_iter)

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_add_bookmark_button_clicked(self, widget):
        """
        Add a new bookmark
        """
        # Get the account that is currently used
        # (the parent of the currently selected item)
        (model, iter_) = self.selection.get_selected()
        if not iter_:  # Nothing selected, do nothing
            return

        parent = model.iter_parent(iter_)

        if parent:
            # We got a bookmark selected, so we add_to the parent
            add_to = parent
        else:
            # No parent, so we got an account -> add to this.
            add_to = iter_

        account = model[add_to][1]
        nick = app.nicks[account]
        label = _('New Group Chat')
        iter_ = self.treestore.append(add_to, [
            account, label, '@', False, '', nick, label])

        self.view.expand_row(model.get_path(add_to), True)
        self.view.set_cursor(model.get_path(iter_))

    def on_remove_bookmark_button_clicked(self, widget):
        """
        Remove selected bookmark
        """
        (model, iter_) = self.selection.get_selected()
        if not iter_:  # Nothing selected
            return

        if not model.iter_parent(iter_):
            # Don't remove account iters
            return

        self.ignore_events = True
        model.remove(iter_)
        self.selection.unselect_all()
        self.clear_fields()
        self.set_sensitive_all(False)
        self.ignore_events = False

    def check_valid_bookmark(self):
        """
        Check if all necessary fields are entered correctly
        """
        (model, iter_) = self.selection.get_selected()

        if not model.iter_parent(iter_):
            # Account data can't be changed
            return

        server = self.server_entry.get_text()
        room = self.room_entry.get_text()

        if server == '' or room == '':
            ErrorDialog(
                _('This bookmark has invalid data'),
                _('Please be sure to fill out server and room fields '
                  'or remove this bookmark.'))
            return False

        return True

    def on_ok_button_clicked(self, widget):
        """
        Parse the treestore data into our new bookmarks array, then send the
        new bookmarks to the server.
        """

        (model, iter_) = self.selection.get_selected()
        if iter_ and model.iter_parent(iter_):
            # bookmark selected, check it
            if not self.check_valid_bookmark():
                return

        for account in self.treestore:
            acct = account[1]
            con = app.connections[acct]
            con.get_module('Bookmarks').bookmarks = {}

            for bm in account.iterchildren():
                # create the bookmark-dict
                bmdict = {
                    'name': bm[Row.ROOM_NAME],
                    'autojoin': bm[Row.AUTOJOIN],
                    'password': bm[Row.PASSWORD],
                    'nick': bm[Row.NICK],
                }

                jid = bm[Row.ROOM_JID]
                con.get_module('Bookmarks').bookmarks[jid] = bmdict

            con.get_module('Bookmarks').store_bookmarks()
            gui_menu_builder.build_bookmark_menu(acct)
        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def bookmark_selected(self, selection):
        """
        Fill in the bookmark's data into the fields.
        """
        (model, iter_) = selection.get_selected()

        if not iter_:
            # After removing the last bookmark for one account
            # this will be None, so we will just:
            return

        if model.iter_parent(iter_):
            # make the fields sensitive
            self.set_sensitive_all(True)
        else:
            # Top-level has no data (it's the account fields)
            # clear fields & make them insensitive
            self.clear_fields()
            self.set_sensitive_all(False)
            return

        # Fill in the data for childs
        self.title_entry.set_text(model[iter_][Row.ROOM_NAME])
        room_jid = model[iter_][Row.ROOM_JID]
        room_jid_s = room_jid.split('@')
        if len(room_jid_s) == 1:
            room = ''
            server = room_jid
        else:
            (room, server) = room_jid_s
        self.room_entry.handler_block(self.room_entry_changed_id)
        self.room_entry.set_text(room)
        self.room_entry.handler_unblock(self.room_entry_changed_id)
        self.server_entry.set_text(server)

        self.autojoin_checkbutton.set_active(model[iter_][Row.AUTOJOIN])
        # sensitive only if auto join is checked

        if model[iter_][Row.PASSWORD] is not None:
            password = model[iter_][Row.PASSWORD]
        else:
            password = None

        if password:
            self.pass_entry.set_text(password)
        else:
            self.pass_entry.set_text('')
        nick = model[iter_][Row.NICK]
        if nick:
            self.nick_entry.set_text(nick)
        else:
            self.nick_entry.set_text('')

    def on_title_entry_changed(self, widget):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if iter_:  # After removing a bookmark, we got nothing selected
            if model.iter_parent(iter_):
                # Don't clear the title field for account nodes
                model[iter_][Row.ROOM_NAME] = self.title_entry.get_text()

    def on_nick_entry_changed(self, widget):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if iter_:
            nick = self.nick_entry.get_text()
            try:
                nick = helpers.parse_resource(nick)
            except helpers.InvalidFormat:
                ErrorDialog(
                    _('Invalid nickname'),
                    _('Character not allowed'),
                    transient_for=self.window)
                self.nick_entry.set_text(model[iter_][Row.NICK])
                return True
            model[iter_][Row.NICK] = nick

    def on_server_entry_focus_out(self, widget, event):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if not iter_:
            return
        server = widget.get_text()
        if not server:
            return
        if '@' in server:
            ErrorDialog(
                _('Invalid server'),
                _('Character not allowed'),
                transient_for=self.window)
            widget.set_text(server.replace('@', ''))

        room = self.room_entry.get_text().strip()
        if not room:
            return
        room_jid = room + '@' + server.strip()
        try:
            room_jid = helpers.parse_jid(room_jid)
        except helpers.InvalidFormat:
            ErrorDialog(
                _('Invalid server'),
                _('Character not allowed'),
                transient_for=self.window)
            self.server_entry.set_text(model[iter_][Row.ROOM_JID].split('@')[1])
            return True
        model[iter_][Row.ROOM_JID] = room_jid

    def on_room_entry_changed(self, widget):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if not iter_:
            return
        room = widget.get_text()
        if not room:
            return
        if '@' in room:
            room, server = room.split('@', 1)
            widget.set_text(room)
            if server:
                self.server_entry.set_text(server)
            self.server_entry.grab_focus()
        server = self.server_entry.get_text().strip()
        if not server:
            return
        room_jid = room.strip() + '@' + server
        try:
            room_jid = helpers.parse_jid(room_jid)
        except helpers.InvalidFormat:
            ErrorDialog(
                _('Invalid room'),
                _('Character not allowed'),
                transient_for=self.window)
            return True
        model[iter_][Row.ROOM_JID] = room_jid

    def on_pass_entry_changed(self, widget):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if iter_:
            model[iter_][Row.PASSWORD] = self.pass_entry.get_text()

    def on_autojoin_checkbutton_toggled(self, widget, *args):
        if self.ignore_events:
            return
        (model, iter_) = self.selection.get_selected()
        if iter_:
            model[iter_][Row.AUTOJOIN] = self.autojoin_checkbutton.get_active()

    def clear_fields(self):
        widgets = [
            self.title_entry, self.nick_entry, self.room_entry,
            self.server_entry, self.pass_entry]
        for field in widgets:
            field.set_text('')
        self.autojoin_checkbutton.set_active(False)

    def set_sensitive_all(self, sensitive):
        widgets = [
            self.title_entry, self.nick_entry, self.room_entry,
            self.server_entry, self.pass_entry, self.settings_box,
            self.remove_bookmark_button]
        for field in widgets:
            field.set_sensitive(sensitive)
