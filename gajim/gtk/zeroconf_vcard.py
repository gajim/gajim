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

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import helpers
from gajim.common import app
from gajim.common.i18n import _

from gajim.gui.util import get_builder


class ZeroconfVcardWindow:
    def __init__(self, contact, account, is_fake=False):
        # the contact variable is the jid if vcard is true
        self.xml = get_builder('zeroconf_information_window.ui')
        self.window = self.xml.get_object('zeroconf_information_window')

        self.contact = contact
        self.account = account
        self.is_fake = is_fake

        self.fill_contact_page()
        self.fill_personal_page()

        self.xml.connect_signals(self)
        self.window.show_all()

    def on_zeroconf_information_window_destroy(self, widget):
        del app.interface.instances[self.account]['infos'][self.contact.jid]

    def on_zeroconf_information_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def set_value(self, entry_name, value):
        try:
            if value and entry_name == 'URL_label':
                widget = Gtk.LinkButton(uri=value, label=value)
                widget.set_alignment(0, 0)
                table = self.xml.get_object('personal_info_table')
                table.attach(widget, 1, 3, 2, 1)
            else:
                self.xml.get_object(entry_name).set_text(value)
        except AttributeError:
            pass

    def fill_status_label(self):
        if self.xml.get_object('information_notebook').get_n_pages() < 2:
            return
        contact_list = app.contacts.get_contacts(self.account, self.contact.jid)
        # stats holds show and status message
        stats = ''
        one = True # Are we adding the first line ?
        if contact_list:
            for c in contact_list:
                if not one:
                    stats += '\n'
                stats += helpers.get_uf_show(c.show)
                if c.status:
                    stats += ': ' + c.status
                one = False
        else: # Maybe gc_vcard ?
            stats = helpers.get_uf_show(self.contact.show)
            if self.contact.status:
                stats += ': ' + self.contact.status
        status_label = self.xml.get_object('status_label')
        status_label.set_text(stats)
        status_label.set_tooltip_text(stats)

    def fill_contact_page(self):
        self.xml.get_object('local_jid_label').set_text(self.contact.jid)

        resources = '%s (%s)' % (self.contact.resource, str(
            self.contact.priority))
        uf_resources = self.contact.resource + _(' resource with priority ')\
                + str(self.contact.priority)
        if not self.contact.status:
            self.contact.status = ''

        self.xml.get_object('resource_prio_label').set_text(resources)
        resource_prio_label_eventbox = self.xml.get_object(
                'resource_prio_label_eventbox')
        resource_prio_label_eventbox.set_tooltip_text(uf_resources)

        self.fill_status_label()

    def fill_personal_page(self):
        contact = app.connections[app.ZEROCONF_ACC_NAME].roster.getItem(self.contact.jid)
        for key in ('1st', 'last', 'jid', 'email'):
            if key not in contact['txt_dict']:
                contact['txt_dict'][key] = ''
        self.xml.get_object('first_name_label').set_text(contact['txt_dict']['1st'])
        self.xml.get_object('last_name_label').set_text(contact['txt_dict']['last'])
        self.xml.get_object('jabber_id_label').set_text(contact['txt_dict']['jid'])
        self.xml.get_object('email_label').set_text(contact['txt_dict']['email'])

    def on_close_button_clicked(self, widget):
        self.window.destroy()
