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

from typing import Dict  # pylint: disable=unused-import
from typing import List  # pylint: disable=unused-import
from typing import Tuple  # pylint: disable=unused-import

import uuid
import logging

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.i18n import _

from .util import get_icon_name
from .util import get_builder

log = logging.getLogger('gajim.gui.adhoc_muc')


class AdhocMUC:

    # Keep a reference on windows so garbage collector don't restroy them
    instances = []  # type: List[AdhocMUC]

    def __init__(self, account, jids, preselected=None):
        """
        This window is used to transform a one-to-one chat to a MUC. We do 2
        things: first select the server and then make a guests list
        """

        self.instances.append(self)
        self.account = account
        self.auto_jids = jids
        self.preselected_jids = preselected

        self.xml = get_builder('adhoc_muc.ui')
        self.window = self.xml.get_object('adhoc_muc_window')

        server_list = []
        self.servers = Gtk.ListStore(str)
        self.xml.server_list_comboboxentry.set_model(self.servers)
        cell = Gtk.CellRendererText()
        self.xml.server_list_comboboxentry.pack_start(cell, True)
        self.xml.server_list_comboboxentry.add_attribute(cell, 'text', 0)

        # get the muc server of our server
        self._client = app.get_client(account)
        service_jid = self._client.get_module('MUC').service_jid
        if service_jid is not None:
            server_list.append(str(service_jid))

        # add servers or recently joined groupchats
        recent_groupchats = app.settings.get_account_setting(
            account, 'recent_groupchats').split()
        for group_chat in recent_groupchats:
            server = app.get_server_from_jid(group_chat)
            if server not in server_list and not server.startswith('irc'):
                server_list.append(server)
        # add a default server
        if not server_list:
            server_list.append('conference.jabber.org')

        for serv in server_list:
            self.servers.append([serv])

        self.xml.server_list_comboboxentry.set_active(0)

        # set treeview
        # name, jid

        self.xml.guests_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.xml.guests_treeview.get_selection().set_mode(
            Gtk.SelectionMode.MULTIPLE)

        for acc in app.settings.get_active_accounts():
            client = app.get_client(acc)
            if client.is_zeroconf:
                continue
            for contact in client.get_module('Roster').iter_contacts():
                jid = str(contact.jid)
                if (jid not in self.auto_jids and
                        jid != str(self._client.get_own_jid().bare)):
                    icon = get_icon_name(contact.show.value)
                    iter_ = self.xml.guests_store.append(
                        [icon, contact.name, jid])
                    # preselect treeview rows
                    if self.preselected_jids and jid in self.preselected_jids:
                        path = self.xml.guests_store.get_path(iter_)
                        self.xml.guests_treeview.get_selection().select_path(
                            path)

        # show all
        self.window.show_all()

        self.xml.connect_signals(self)

    def on_chat_to_muc_window_destroy(self, _widget):
        self.instances.remove(self)

    def on_chat_to_muc_window_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_invite_button_clicked(self, _widget):
        row = self.xml.server_list_comboboxentry.get_child().get_displayed_row()
        model = self.xml.server_list_comboboxentry.get_model()
        server = model[row][0].strip()
        if server == '':
            return

        guest_list = []
        guests = self.xml.guests_treeview.get_selection().get_selected_rows()
        for guest in guests[1]:
            iter_ = self.xml.guests_store.get_iter(guest)
            guest_list.append(self.xml.guests_store[iter_][2])
        for guest in self.auto_jids:
            guest_list.append(guest)
        room_jid = f'{uuid.uuid4()}@{server}'
        app.automatic_rooms[self.account][room_jid] = {}
        app.automatic_rooms[self.account][room_jid]['invities'] = guest_list
        app.automatic_rooms[self.account][room_jid]['continue_tag'] = True

        config = {
            # XEP-0045 options
            'muc#roomconfig_roomname': _('Adhoc Group Chat'),
            'muc#roomconfig_publicroom': False,
            'muc#roomconfig_membersonly': True,
            'muc#roomconfig_whois': 'anyone',
            'muc#roomconfig_changesubject': True,
            'muc#roomconfig_persistentroom': False,

            # Ejabberd options
            'public_list': False,
        }

        app.interface.create_groupchat(self.account, room_jid, config)
        app.window.select_chat(self.account, room_jid)
        self.window.destroy()

    def on_cancel_button_clicked(self, _widget):
        self.window.destroy()
