# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Dimitur Kirov <dkirov AT gmail.com>
#                    Travis Shirk <travis AT pobox.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#                    Stephan Erb <steve-e AT h3c.de>
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

import logging

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk
from nbxmpp.structs import AnnotationNote
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.errors import is_error

from gajim import gtkgui_helpers
from gajim.common import helpers
from gajim.common import app
from gajim.common import ged
from gajim.common import configpaths
from gajim.common.i18n import Q_
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.nec import EventHelper
from gajim.common.modules.util import as_task

from gajim.gui.util import get_builder


log = logging.getLogger('gajim.vcard')


class VcardWindow(EventHelper):
    """
    Class for contact's information window
    """

    def __init__(self, contact, account, gc_contact=None):
        EventHelper.__init__(self)
        # the contact variable is the jid if vcard is true
        self.xml = get_builder('vcard_information_window.ui')
        self.window = self.xml.get_object('vcard_information_window')
        self.progressbar = self.xml.get_object('progressbar')

        self.contact = contact
        self.account = account
        self.gc_contact = gc_contact
        self.avatar = None

        # Get real jid
        if gc_contact:
            # Don't use real jid if room is (semi-)anonymous
            gc_control = app.interface.msg_win_mgr.get_gc_control(
            gc_contact.room_jid, account)
            if gc_contact.jid and not gc_control.is_anonymous:
                self.real_jid = gc_contact.jid
                self.real_jid_for_vcard = gc_contact.jid
                if gc_contact.resource:
                    self.real_jid += '/' + gc_contact.resource
            else:
                self.real_jid = gc_contact.get_full_jid()
                self.real_jid_for_vcard = self.real_jid
            self.real_resource = gc_contact.name
        else:
            self.real_jid = contact.get_full_jid()
            self.real_resource = contact.resource

        puny_jid = helpers.sanitize_filename(contact.jid)
        local_avatar_basepath = configpaths.get('AVATAR') / (puny_jid +
                                                             '_local')
        for extension in ('.png', '.jpeg'):
            local_avatar_path = local_avatar_basepath.with_suffix(extension)
            if local_avatar_path.is_file():
                image = self.xml.get_object('custom_avatar_image')
                image.set_from_file(local_avatar_path)
                image.show()
                self.xml.get_object('custom_avatar_label').show()
                break
        self.vcard_arrived = False
        self.os_info_arrived = False
        self.entity_time_arrived = False
        self.time = 0
        self.update_intervall = 100  # Milliseconds
        self.update_progressbar_timeout_id = GLib.timeout_add(self.update_intervall,
            self.update_progressbar)

        self.register_events([
            ('time-result-received', ged.GUI1, self.set_entity_time),
        ])

        self.fill_jabber_page()
        con = app.connections[self.account]
        note = con.get_module('Annotations').get_note(self.contact.jid)
        if note is not None:
            buffer_ = self.xml.get_object('textview_annotation').get_buffer()
            buffer_.set_text(note.data)

        for widget_name in ('URL_label',
                            'EMAIL_WORK_USERID_label',
                            'EMAIL_HOME_USERID_label'):
            widget = self.xml.get_object(widget_name)
            widget.hide()

        self.xml.connect_signals(self)
        self.xml.get_object('close_button').grab_focus()
        self.window.show_all()

    def update_progressbar(self):
        self.progressbar.pulse()
        self.time += self.update_intervall
        # Timeout in Milliseconds
        if (self.vcard_arrived and self.os_info_arrived and
                self.entity_time_arrived) or self.time == 10000:
            self.progressbar.hide()
            self.update_progressbar_timeout_id = None
            return False
        return True

    def on_vcard_information_window_destroy(self, widget):
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        del app.interface.instances[self.account]['infos'][self.contact.jid]
        buffer_ = self.xml.get_object('textview_annotation').get_buffer()
        new_annotation = buffer_.get_text(buffer_.get_start_iter(),
                                          buffer_.get_end_iter(),
                                          True)
        con = app.connections[self.account]
        note = con.get_module('Annotations').get_note(self.contact.jid)
        if note is None or new_annotation != note.data:
            new_note = AnnotationNote(jid=self.contact.jid, data=new_annotation)
            con.get_module('Annotations').set_note(new_note)
        self.unregister_events()
        app.cancel_tasks(self)

    def on_vcard_information_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_information_notebook_switch_page(self, widget, page, page_num):
        GLib.idle_add(self.xml.get_object('close_button').grab_focus)

    def set_value(self, entry_name, value):
        try:
            widget = self.xml.get_object(entry_name)
            if entry_name in ('URL_label',
                              'EMAIL_WORK_USERID_label',
                              'EMAIL_HOME_USERID_label'):
                if entry_name == 'URL_label':
                    widget.set_uri(value)
                else:
                    widget.set_uri('mailto:' + value)
                widget.set_label(value)
                self.xml.get_object(entry_name).show()
            else:
                val = widget.get_text()
                if val:
                    value = val + ' / ' + value
                widget.set_text(value)
        except AttributeError:
            pass

    def _set_values(self, vcard, jid):
        for i in vcard.keys():
            if i == 'PHOTO':
                continue
            if i in ('ADR', 'TEL', 'EMAIL'):
                for entry in vcard[i]:
                    add_on = '_HOME'
                    if 'WORK' in entry:
                        add_on = '_WORK'
                    for j in entry.keys():
                        self.set_value(i + add_on + '_' + j + '_label', entry[j])
            if isinstance(vcard[i], dict):
                for j in vcard[i].keys():
                    self.set_value(i + '_' + j + '_label', vcard[i][j])
            else:
                if i == 'DESC':
                    self.xml.get_object('DESC_textview').get_buffer().set_text(
                        vcard[i], len(vcard[i].encode('utf-8')))
                elif i != 'jid': # Do not override jid_label
                    self.set_value(i + '_label', vcard[i])
        self.vcard_arrived = True

    def _load_avatar(self, vcard):
        if not self.xml.get_object('information_notebook').get_n_pages() > 4:
            # TODO: why?
            return

        try:
            avatar, _ = vcard.get_avatar()
        except Exception as error:
            log.warning('Failed to load avatar: %s', error)
            return

        if avatar is None:
            return

        pixbuf = gtkgui_helpers.get_pixbuf_from_data(avatar)
        pixbuf = gtkgui_helpers.scale_pixbuf(pixbuf, AvatarSize.VCARD)

        surface = Gdk.cairo_surface_create_from_pixbuf(
            pixbuf, self.window.get_scale_factor())
        image = self.xml.get_object('PHOTO_image')
        image.set_from_surface(surface)
        image.show()

        self.avatar = pixbuf
        self.xml.get_object('user_avatar_label').show()

    def clear_values(self):
        for l in ('FN', 'NICKNAME', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE',
        'N_PREFIX', 'N_SUFFIX', 'EMAIL_HOME_USERID', 'TEL_HOME_NUMBER', 'BDAY',
        'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE', 'EMAIL_WORK_USERID',
        'TEL_WORK_NUMBER', 'URL'):
            widget = self.xml.get_object(l + '_label')
            if l in ('EMAIL_HOME_USERID', 'EMAIL_WORK_USERID', 'URL'):
                widget.hide()
            else:
                widget.set_text('')
        for pref in ('ADR_HOME', 'ADR_WORK'):
            for l in ('STREET', 'EXTADR', 'LOCALITY', 'PCODE', 'REGION',
            'CTRY'):
                widget = self.xml.get_object(pref + '_' + l + '_label')
                widget.set_text('')
        self.xml.get_object('DESC_textview').get_buffer().set_text('')

    @as_task
    def _request_vcard(self, jid):
        _task = yield

        con = app.connections[self.account]
        vcard = yield con.get_module('VCardTemp').request_vcard(jid=jid)

        if is_error(vcard):
            return

        self.clear_values()
        self._set_values(vcard.data, str(jid))
        self._load_avatar(vcard)

    def set_os_info(self, task):
        error = False
        try:
            result = task.finish()
        except StanzaError:
            error = True

        jid = task.get_user_data()

        if self.xml.get_object('information_notebook').get_n_pages() < 5:
            return

        i = 0
        client = ''
        os_info = ''
        while i in self.os_info:
            if self.os_info[i]['resource'] == JID.from_string(jid).resource:
                if not error:
                    self.os_info[i]['client'] = '%s %s' % (result.name,
                                                           result.version)
                else:
                    self.os_info[i]['client'] = Q_('?Client:Unknown')

                if not error and result.os is not None:
                    self.os_info[i]['os'] = result.os
                else:
                    self.os_info[i]['os'] = Q_('?OS:Unknown')

            if i > 0:
                client += '\n'
                os_info += '\n'
            client += self.os_info[i]['client']
            os_info += self.os_info[i]['os']
            i += 1

        self.xml.get_object('client_name_version_label').set_text(client)
        self.xml.get_object('os_label').set_text(os_info)
        self.os_info_arrived = True

    def set_entity_time(self, obj):
        if obj.conn.name != self.account:
            return
        if self.xml.get_object('information_notebook').get_n_pages() < 5:
            return
        if self.gc_contact:
            if obj.jid != self.contact.jid:
                return
        elif obj.jid.bare != self.contact.jid:
            return
        i = 0
        time_s = ''
        while i in self.time_info:
            if self.time_info[i]['resource'] == obj.jid.resource:
                if obj.time_info:
                    self.time_info[i]['time'] = obj.time_info
                else:
                    self.time_info[i]['time'] = Q_('?Time:Unknown')
            else:
                if not self.time_info[i]['time']:
                    self.time_info[i]['time'] = Q_('?Time:Unknown')
            if i > 0:
                time_s += '\n'
            time_s += self.time_info[i]['time']
            i += 1

        self.xml.get_object('time_label').set_text(time_s)
        self.entity_time_arrived = True

    def fill_status_label(self):
        if self.xml.get_object('information_notebook').get_n_pages() < 5:
            return
        contact_list = app.contacts.get_contacts(self.account, self.contact.jid)
        connected_contact_list = []
        for c in contact_list:
            if c.show not in ('offline', 'error'):
                connected_contact_list.append(c)
        if not connected_contact_list:
            # no connected contact, get the offline one
            connected_contact_list = contact_list
        # stats holds show and status message
        stats = ''
        if connected_contact_list:
            # Start with self.contact, as with resources
            stats = helpers.get_uf_show(self.contact.show)
            if self.contact.status:
                stats += ': ' + self.contact.status
            for c in connected_contact_list:
                if c.resource != self.contact.resource:
                    stats += '\n'
                    stats += helpers.get_uf_show(c.show)
                    if c.status:
                        stats += ': ' + c.status
        else: # Maybe gc_vcard ?
            stats = helpers.get_uf_show(self.contact.show)
            if self.contact.status:
                stats += ': ' + self.contact.status
        status_label = self.xml.get_object('status_label')
        status_label.set_text(stats)
        status_label.set_tooltip_text(stats)

    def fill_jabber_page(self):
        self.xml.get_object('nickname_label').set_markup(
                '<b><span size="x-large">' +
                self.contact.get_shown_name() +
                '</span></b>')
        self.xml.get_object('jid_label').set_text(self.contact.jid)

        subscription_label = self.xml.get_object('subscription_label')
        ask_label = self.xml.get_object('ask_label')
        if self.gc_contact:
            self.xml.get_object('subscription_title_label').set_markup(Q_("?Role in Group Chat:<b>Role:</b>"))
            uf_role = helpers.get_uf_role(self.gc_contact.role)
            subscription_label.set_text(uf_role)

            self.xml.get_object('ask_title_label').set_markup(_("<b>Affiliation:</b>"))
            uf_affiliation = helpers.get_uf_affiliation(self.gc_contact.affiliation)
            ask_label.set_text(uf_affiliation)
        else:
            uf_sub = helpers.get_uf_sub(self.contact.sub)
            subscription_label.set_text(uf_sub)
            if self.contact.sub == 'from':
                tt_text = _("This contact is interested in your presence information, but you are not interested in their presence")
            elif self.contact.sub == 'to':
                tt_text = _("You are interested in the contact's presence information, but it is not mutual")
            elif self.contact.sub == 'both':
                tt_text = _("The contact and you want to exchange presence information")
            else: # None
                tt_text = _("You and the contact have a mutual disinterest in each-others presence information")
            subscription_label.set_tooltip_text(tt_text)

            uf_ask = helpers.get_uf_ask(self.contact.ask)
            ask_label.set_text(uf_ask)
            if self.contact.ask == 'subscribe':
                tt_text = _("You are waiting contact's answer about your subscription request")
            else:
                tt_text = _("There is no pending subscription request.")
            ask_label.set_tooltip_text(tt_text)

        resources = ''
        uf_resources = ''
        if self.contact.resource:
            resources = '%s (%s)' % (self.contact.resource, str(
                self.contact.priority))
            uf_resources = self.contact.resource + _(' resource with priority ')\
                    + str(self.contact.priority)
        if not self.contact.status:
            self.contact.status = ''

        con = app.connections[self.account]

        # do not wait for os_info if contact is not connected or has error
        # additional check for observer is needed, as show is offline for him
        if self.contact.show in ('offline', 'error')\
        and not self.contact.is_observer():
            self.os_info_arrived = True
        else: # Request os info if contact is connected
            if self.gc_contact:
                con.get_module('SoftwareVersion').request_software_version(
                    self.real_jid,
                    callback=self.set_os_info,
                    user_data=self.real_jid)
            else:
                jid = self.contact.get_full_jid()
                con.get_module('SoftwareVersion').request_software_version(
                    jid,
                    callback=self.set_os_info,
                    user_data=jid)

        # do not wait for entity_time if contact is not connected or has error
        # additional check for observer is needed, as show is offline for him
        if self.contact.show in ('offline', 'error')\
        and not self.contact.is_observer():
            self.entity_time_arrived = True
        else: # Request entity time if contact is connected
            if self.gc_contact:
                j, r = app.get_room_and_nick_from_fjid(self.real_jid)
                GLib.idle_add(con.get_module('EntityTime').request_entity_time,
                              j, r)
            else:
                GLib.idle_add(con.get_module('EntityTime').request_entity_time,
                              self.contact.jid, self.contact.resource)

        self.os_info = {0: {'resource': self.real_resource, 'client': '',
                'os': ''}}
        self.time_info = {0: {'resource': self.real_resource, 'time': ''}}
        i = 1
        contact_list = app.contacts.get_contacts(self.account, self.contact.jid)
        if contact_list:
            for c in contact_list:
                if c.resource != self.contact.resource:
                    resources += '\n%s (%s)' % (c.resource,
                            str(c.priority))
                    uf_resources += '\n' + c.resource + \
                            _(' resource with priority ') + str(c.priority)
                    if c.show not in ('offline', 'error'):
                        jid = c.get_full_jid()
                        con.get_module('SoftwareVersion').request_software_version(
                            jid, callback=self.set_os_info, user_data=jid)
                        GLib.idle_add(con.get_module('EntityTime').request_entity_time,
                                      c.jid, c.resource)
                    self.os_info[i] = {'resource': c.resource, 'client': '',
                            'os': ''}
                    self.time_info[i] = {'resource': c.resource, 'time': ''}
                    i += 1

        self.xml.get_object('resource_prio_label').set_text(resources)
        resource_prio_label_eventbox = self.xml.get_object(
                'resource_prio_label_eventbox')
        resource_prio_label_eventbox.set_tooltip_text(uf_resources)

        self.fill_status_label()

        jid = self.contact.jid
        if self.gc_contact:
            jid = self.gc_contact.get_full_jid()

        self._request_vcard(jid)

    def on_close_button_clicked(self, widget):
        self.window.destroy()


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
        self.xml.get_object('nickname_label').set_markup(
                '<b><span size="x-large">' +
                self.contact.get_shown_name() +
                '</span></b>')
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
