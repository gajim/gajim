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

import nbxmpp
from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.exceptions import GajimGeneralException
from gajim.gtk import ErrorDialog
from gajim.gtk.util import get_builder


class JoinGroupchatWindow(Gtk.ApplicationWindow):
    def __init__(self, account, room_jid, password=None, automatic=None,
                 transient_for=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('JoinGroupchat')
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title(_('Join Group Chat'))
        if transient_for:
            self.set_transient_for(transient_for)

        self.automatic = automatic
        self.password = password
        self.requested_jid = None
        self.room_jid = room_jid
        self.account = account

        if self.room_jid is None:
            self.minimal_mode = False
        else:
            self.minimal_mode = True

        glade_objects = ['main_box', 'account_label', 'account_combo',
                         'server_label', 'server_combo', 'room_entry',
                         'recently_button', 'recently_popover',
                         'recently_treeview', 'search_button', 'password_label',
                         'password_entry', 'nick_entry', 'bookmark_switch',
                         'autojoin_switch']

        self.builder = get_builder('join_groupchat_window.ui')
        for obj in glade_objects:
            setattr(self, obj, self.builder.get_object(obj))

        self.add(self.main_box)

        # Show widgets depending on the mode the window is in
        if not self.minimal_mode:
            self.recently_button.show()
            self.search_button.show()

        accounts = app.get_enabled_accounts_with_labels()
        account_liststore = self.account_combo.get_model()
        for acc in accounts:
            account_liststore.append(acc)

        if not accounts:
            return

        if not self.account:
            self.account = accounts[0][0]

        self.builder.connect_signals(self)
        self.connect('key-press-event', self._on_key_press_event)

        # Hide account combobox if there is only one account
        if len(accounts) == 1:
            self.account_combo.hide()
            self.account_label.hide()

        self.account_combo.set_active_id(self.account)

        if self.minimal_mode:
            if '@' in self.room_jid:
                (room, server) = self.room_jid.split('@')
                self.room_entry.set_text(room)
                if not muc_caps_cache.supports(
                        self.room_jid, 'muc_passwordprotected'):
                    self.password_entry.hide()
                    self.password_label.hide()
                    self.nick_entry.grab_focus()
                else:
                    self.password_entry.grab_focus()
            else:
                server = self.room_jid
                self.room_entry.grab_focus()

            self.server_combo.insert_text(0, server)
            self.server_combo.set_active(0)

        if self.password is not None:
            self.password_entry.set_text(self.password)

        # Set bookmark switch sensitive if server supports bookmarks
        acc = self.account_combo.get_active_id()
        con = app.connections[acc]
        if not con.get_module('Bookmarks').available:
            self.bookmark_switch.set_sensitive(False)
            self.autojoin_switch.set_sensitive(False)

        self.show_all()

    def set_room(self, room_jid):
        room, server = app.get_name_and_server_from_jid(room_jid)
        self.room_entry.set_text(room)
        self.server_combo.get_child().set_text(server)

    def _fill_recent_and_servers(self, account):
        recently_liststore = self.recently_treeview.get_model()
        recently_liststore.clear()
        self.server_combo.remove_all()
        recent = app.get_recent_groupchats(account)
        servers = []
        for groupchat in recent:
            label = '%s@%s' % (groupchat.room, groupchat.server)

            recently_liststore.append([groupchat.server,
                                       groupchat.room,
                                       groupchat.nickname,
                                       label])
            servers.append(groupchat.server)

        self.recently_button.set_sensitive(bool(recent))

        for server in set(servers):
            self.server_combo.append_text(server)

        # Add own Server to ComboBox
        muc_domain = app.get_muc_domain(account)
        if muc_domain is not None:
            self.server_combo.insert_text(0, muc_domain)

    def _on_recent_selected(self, treeview, *args):
        (model, iter_) = treeview.get_selection().get_selected()
        self.server_combo.get_child().set_text(model[iter_][0])
        self.room_entry.set_text(model[iter_][1])
        self.nick_entry.set_text(model[iter_][2])
        self.recently_popover.popdown()

    def _on_account_combo_changed(self, combo):
        account = combo.get_active_id()
        self.account = account
        self.nick_entry.set_text(app.nicks[account])
        self._fill_recent_and_servers(account)

    def _on_jid_detection_changed(self, widget):
        text = widget.get_text()
        if text.startswith('xmpp:'):
            text = text[5:]
        if '@' in text:
            room, server = text.split('@', 1)
            server = server.split('?')[0]
            widget.set_text('')

            if room:
                self.room_entry.set_text(room)

            if server:
                self.server_combo.get_child().set_text(server)
            else:
                self.server_combo.grab_focus()

    def _on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
        if event.keyval == Gdk.KEY_Return:
            self._on_join_clicked()
            return True

    def _on_join_clicked(self, *args):
        account = self.account_combo.get_active_id()
        nickname = self.nick_entry.get_text()

        invisible_show = app.SHOW_LIST.index('invisible')
        if app.connections[account].connected == invisible_show:
            app.interface.raise_dialog('join-while-invisible')
            return

        server = self.server_combo.get_active_text()
        room = self.room_entry.get_text()

        if room == '':
            ErrorDialog(_('Invalid Room'),
                        _('Please choose a room'), transient_for=self)
            return

        self.room_jid = '%s@%s' % (room, server)

        try:
            self.room_jid = helpers.parse_jid(self.room_jid)
        except helpers.InvalidFormat as error:
            ErrorDialog(_('Invalid JID'), str(error), transient_for=self)
            return

        if app.in_groupchat(account, self.room_jid):
            # If we already in the groupchat, join_gc_room will bring
            # it to front
            app.interface.join_gc_room(account, self.room_jid, nickname, '')
            self.destroy()
            return

        if nickname == '':
            ErrorDialog(_('Invalid Nickname'),
                        _('Please choose a nickname'), transient_for=self)
            return

        try:
            helpers.parse_resource(nickname)
        except helpers.InvalidFormat as error:
            ErrorDialog(_('Invalid Nickname'), str(error), transient_for=self)
            return

        if not app.account_is_connected(account):
            ErrorDialog(
                _('You are not connected to the server'),
                _('You can not join a group chat unless you are connected.'),
                transient_for=self)
            return

        password = self.password_entry.get_text()
        self._add_bookmark(account, nickname, password)
        app.add_recent_groupchat(account, self.room_jid, nickname)

        if self.automatic:
            app.automatic_rooms[self.account][self.room_jid] = self.automatic

        app.interface.join_gc_room(account, self.room_jid, nickname, password)
        self.destroy()

    def _on_cancel_clicked(self, *args):
        self.destroy()

    def _on_bookmark_activate(self, switch, param):
        bookmark_state = switch.get_active()
        self.autojoin_switch.set_sensitive(bookmark_state)
        if not bookmark_state:
            self.autojoin_switch.set_active(False)

    def _add_bookmark(self, account, nickname, password):
        con = app.connections[account]

        add_bookmark = self.bookmark_switch.get_active()
        if not add_bookmark:
            return

        autojoin = self.autojoin_switch.get_active()

        # Add as bookmark, with autojoin and not minimized
        name = app.get_nick_from_jid(self.room_jid)
        con.get_module('Bookmarks').add_bookmark(name,
                                                 self.room_jid,
                                                 autojoin,
                                                 True,
                                                 password,
                                                 nickname)

    def _on_search_clicked(self, widget):
        server = self.server_combo.get_active_text().strip()
        con = app.connections[self.account]
        con.get_module('Discovery').disco_info(
            server,
            success_cb=self._disco_info_received,
            error_cb=self._disco_info_error)

    def _disco_info_error(self, from_, error):
        ErrorDialog(_('Wrong server'),
                    _('%s is not a groupchat server') % from_,
                    transient_for=self)

    def _disco_info_received(self, from_, identities, features, data, node):
        if nbxmpp.NS_MUC not in features:
            ErrorDialog(_('Wrong server'),
                        _('%s is not a groupchat server') % from_,
                        transient_for=self)
            return

        jid = str(from_)
        if jid in app.interface.instances[self.account]['disco']:
            app.interface.instances[self.account]['disco'][jid].window.\
                present()
        else:
            try:
                # Object will add itself to the window dict
                from gajim.disco import ServiceDiscoveryWindow
                ServiceDiscoveryWindow(
                    self.account, jid,
                    initial_identities=[{'category': 'conference',
                                         'type': 'text'}])
            except GajimGeneralException:
                pass
