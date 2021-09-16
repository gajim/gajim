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

import uuid
import logging

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.i18n import _

from .util import get_icon_name
from .util import get_builder

log = logging.getLogger('gajim.gui.adhoc_muc')


class AdhocMUC(Gtk.ApplicationWindow):
    def __init__(self, account, contact, preselected=None):
        """
        This window is used to transform a one-to-one chat to a MUC. We do 2
        things: first select the server and then make a guests list
        """
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_show_menubar(False)
        self.set_title(_('Adhoc Group Chat'))
        self.set_default_size(500, 400)
        self.set_resizable(True)

        self.account = account
        self.jid = contact.jid
        self._preselected_jids = preselected
        self._client = app.get_client(account)

        self._ui = get_builder('adhoc_muc.ui')
        self.add(self._ui.adhoc_box)

        self._ui.description_label.set_text(
            _('Invite someone to your chat with %s') % contact.name)

        # Setup treeview: name, jid
        self._ui.guests_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self._ui.guests_treeview.get_selection().set_mode(
            Gtk.SelectionMode.MULTIPLE)

        self._add_possible_invitees()
        self._fill_server_list()

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _add_possible_invitees(self):
        for acc in app.settings.get_active_accounts():
            client = app.get_client(acc)
            if client.is_zeroconf:
                continue
            for contact in client.get_module('Roster').iter_contacts():
                jid = str(contact.jid)
                # Add contact if it can be invited
                if self._is_invitable(contact):
                    icon = get_icon_name(contact.show.value)
                    iter_ = self._ui.guests_store.append(
                        [icon, contact.name, jid])
                    # preselect treeview rows
                    if (self._preselected_jids and
                            jid in self._preselected_jids):
                        path = self._ui.guests_store.get_path(iter_)
                        self._ui.guests_treeview.get_selection().select_path(
                            path)

    def _is_invitable(self, contact):
        # All contacts BUT the following can be invited:
        # ourself, gateway contacts, zeroconf contacts
        return (str(contact.jid) != str(self.jid) and
                contact.jid != str(self._client.get_own_jid().bare) and
                str(contact.jid) != app.get_jid_from_account(self.account) and
                contact.show.value != 'error' and
                not contact.is_gateway)

    def _fill_server_list(self):
        servers = []

        # Add own server to combobox
        service_jid = self._client.get_module('MUC').service_jid
        if service_jid is not None:
            servers.append(str(service_jid))

        # Add servers or recently joined groupchats
        recent_groupchats = app.get_recent_groupchats(self.account)
        for groupchat in recent_groupchats:
            if (groupchat.server not in servers and
                    not groupchat.server.startswith('irc')):
                servers.append(groupchat.server)

        # Add a default server (necessary?)
        if not servers:
            servers.append('conference.jabber.org')

        for server in servers:
            self._ui.server_store.append([server])

        self._ui.server_combobox.set_active(0)

    def _on_server_combobox_entry_changed(self, _widget):
        server = self._ui.server_entry.get_text()
        self._ui.invite_button.set_sensitive(server != '')

    def _on_invite_clicked(self, _widget):
        server = self._ui.server_entry.get_text()
        guest_list = []
        guests = self._ui.guests_treeview.get_selection().get_selected_rows()
        for guest in guests[1]:
            iter_ = self._ui.guests_store.get_iter(guest)
            guest_list.append(self._ui.guests_store[iter_][2])
        guest_list.append(self.jid)

        # Build group chat JID
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
        self.destroy()
