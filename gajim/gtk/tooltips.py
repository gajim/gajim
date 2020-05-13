# Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
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
import time
import logging
from datetime import datetime

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Pango

from gajim.common import app
from gajim.common import helpers
from gajim.common.helpers import get_connection_status
from gajim.common.const import AvatarSize
from gajim.common.const import PEPEventType
from gajim.common.i18n import Q_
from gajim.common.i18n import _
from gajim.gtkgui_helpers import add_css_class

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import format_mood
from gajim.gtk.util import format_activity
from gajim.gtk.util import format_tune
from gajim.gtk.util import format_location
from gajim.gtk.util import get_css_show_class


log = logging.getLogger('gajim.gtk.tooltips')


class StatusTable:
    """
    Contains methods for creating status table. This is used in Roster and
    NotificationArea tooltips
    """

    def __init__(self):
        self.current_row = 0
        self.table = None
        self.text_label = None
        self.spacer_label = '   '

    def create_table(self):
        self.table = Gtk.Grid()
        self.table.insert_column(0)
        self.table.set_property('column-spacing', 3)

    def add_text_row(self, text, col_inc=0):
        self.table.insert_row(self.current_row)
        self.text_label = Gtk.Label()
        self.text_label.set_line_wrap(True)
        self.text_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.text_label.set_lines(3)
        self.text_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.text_label.set_max_width_chars(30)
        self.text_label.set_halign(Gtk.Align.START)
        self.text_label.set_valign(Gtk.Align.START)
        self.text_label.set_xalign(0)
        self.text_label.set_selectable(False)

        self.text_label.set_text(text)
        self.table.attach(self.text_label, 1 + col_inc,
                          self.current_row,
                          3 - col_inc,
                          1)
        self.current_row += 1

    def add_status_row(self, show, str_status, show_lock=False,
                       indent=True, transport=None):
        """
        Append a new row with status icon to the table
        """
        self.table.insert_row(self.current_row)
        image = Gtk.Image()
        icon_name = get_icon_name(show, transport=transport)
        image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        spacer = Gtk.Label(label=self.spacer_label)
        image.set_halign(Gtk.Align.START)
        image.set_valign(Gtk.Align.CENTER)
        if indent:
            self.table.attach(spacer, 1, self.current_row, 1, 1)
        self.table.attach(image, 2, self.current_row, 1, 1)
        status_label = Gtk.Label()
        status_label.set_text(str_status)
        status_label.set_halign(Gtk.Align.START)
        status_label.set_valign(Gtk.Align.START)
        status_label.set_xalign(0)
        status_label.set_line_wrap(True)
        status_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        status_label.set_lines(3)
        status_label.set_ellipsize(Pango.EllipsizeMode.END)
        status_label.set_max_width_chars(30)
        self.table.attach(status_label, 3, self.current_row, 1, 1)
        if show_lock:
            lock_image = Gtk.Image()
            lock_image.set_from_icon_name('dialog-password', Gtk.IconSize.MENU)
            self.table.attach(lock_image, 4, self.current_row, 1, 1)
        self.current_row += 1

    def fill_table_with_accounts(self, accounts):
        for acct in accounts:
            message = acct['message']
            message = helpers.reduce_chars_newlines(message, 100, 1)
            message = GLib.markup_escape_text(message)
            con_type = app.con_types.get(acct['name'])
            show_lock = con_type in ('tls', 'ssl')

            account_label = GLib.markup_escape_text(acct['account_label'])
            if message:
                status = '%s - %s' % (account_label, message)
            else:
                status = account_label

            self.add_status_row(acct['show'],
                                status,
                                show_lock=show_lock,
                                indent=False)

            for line in acct['event_lines']:
                self.add_text_row('  ' + line, 1)


class NotificationAreaTooltip(StatusTable):
    """
    Tooltip that is shown in the notification area
    """

    def __init__(self):
        StatusTable.__init__(self)

    def get_tooltip(self):
        self.create_table()

        accounts = helpers.get_notification_icon_tooltip_dict()
        self.fill_table_with_accounts(accounts)
        self.table.set_property('column-spacing', 1)

        hbox = Gtk.HBox()
        hbox.add(self.table)
        hbox.show_all()
        return hbox


class GCTooltip():
    def __init__(self):
        self.contact = None

        self._ui = get_builder('tooltip_gc_contact.ui')

    def clear_tooltip(self):
        self.contact = None

    def get_tooltip(self, contact):
        if self.contact == contact:
            return True, self._ui.tooltip_grid

        self._populate_grid(contact)
        self.contact = contact
        return False, self._ui.tooltip_grid

    def _hide_grid_childs(self):
        """
        Hide all Elements of the Tooltip Grid
        """
        for child in self._ui.tooltip_grid.get_children():
            child.hide()

    def _populate_grid(self, contact):
        """
        Populate the Tooltip Grid with data of from the contact
        """
        self._hide_grid_childs()

        self._ui.nick.set_text(contact.get_shown_name())
        self._ui.nick.show()

        # Status Message
        if contact.status:
            status = contact.status.strip()
            if status != '':
                self._ui.status.set_text(status)
                self._ui.status.show()

        # Status
        show = helpers.get_uf_show(contact.show.value)
        self._ui.user_show.set_text(show)
        colorize_status(self._ui.user_show, contact.show.value)
        self._ui.user_show.show()

        # JID
        if contact.jid is not None:
            self._ui.jid.set_text(str(contact.jid))
            self._ui.jid.show()

        # Affiliation
        if not contact.affiliation.is_none:
            uf_affiliation = helpers.get_uf_affiliation(contact.affiliation)
            uf_affiliation = \
                _('%(owner_or_admin_or_member)s of this group chat') \
                % {'owner_or_admin_or_member': uf_affiliation}
            self._ui.affiliation.set_text(uf_affiliation)
            self._ui.affiliation.show()

        # Avatar
        if contact.avatar_sha is not None:
            app.log('avatar').debug(
                'Load GCTooltip: %s %s', contact.name, contact.avatar_sha)
        scale = self._ui.tooltip_grid.get_scale_factor()
        surface = app.interface.get_avatar(
            contact, AvatarSize.TOOLTIP, scale)
        self._ui.avatar.set_from_surface(surface)
        self._ui.avatar.show()
        self._ui.fillelement.show()

        app.plugin_manager.gui_extension_point(
            'gc_tooltip_populate', self, contact, self._ui.tooltip_grid)

    def destroy(self):
        self._ui.tooltip_grid.destroy()


class RosterTooltip(StatusTable):
    def __init__(self):
        StatusTable.__init__(self)
        self.create_table()
        self.account = None
        self.row = None
        self.contact_jid = None
        self.prim_contact = None
        self.last_widget = None
        self.num_resources = 0

        self._ui = get_builder('tooltip_roster_contact.ui')

    def clear_tooltip(self):
        """
        Hide all Elements of the Tooltip Grid
        """
        for child in self._ui.tooltip_grid.get_children():
            child.hide()
        status_table = self._ui.tooltip_grid.get_child_at(1, 3)
        if status_table:
            status_table.destroy()
            self.create_table()
        self.row = None

    def get_tooltip(self, row, connected_contacts, account, typ):
        if self.row == row:
            return True, self._ui.tooltip_grid

        self._populate_grid(connected_contacts, account, typ)
        self.row = row
        return False, self._ui.tooltip_grid

    def _populate_grid(self, contacts, account, typ):
        """
        Populate the Tooltip Grid with data of from the contact
        """
        self.current_row = 0
        self.account = account
        if self.last_widget:
            self.last_widget.set_vexpand(False)

        self.clear_tooltip()

        if account == 'all':
            # Tooltip for merged accounts row
            self._show_merged_account_tooltip()
            return

        if typ == 'account':
            jid = app.get_jid_from_account(account)
            contacts = []
            connection = app.connections[account]
            # get our current contact info

            nbr_on, nbr_total = app.\
                contacts.get_nb_online_total_contacts(accounts=[account])
            account_name = app.get_account_label(account)
            if app.account_is_available(account):
                account_name += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))
            contact = app.contacts.create_self_contact(
                jid=jid,
                account=account,
                name=account_name,
                show=get_connection_status(account),
                status=connection.status_message,
                resource=connection.get_own_jid().getResource(),
                priority=connection.priority)

            contacts.append(contact)

        # Username/Account/Groupchat
        self.prim_contact = app.contacts.get_highest_prio_contact_from_contacts(
            contacts)
        if self.prim_contact is None:
            log.error('No contact for Roster tooltip found')
            log.error('contacts: %s, typ: %s, account: %s',
                      contacts, typ, account)
            return
        self.contact_jid = self.prim_contact.jid
        name = GLib.markup_escape_text(self.prim_contact.get_shown_name())

        if app.config.get('mergeaccounts'):
            name = GLib.markup_escape_text(
                self.prim_contact.account.name)

        self._ui.name.set_markup(name)
        self._ui.name.show()

        self.num_resources = 0
        # put contacts in dict, where key is priority
        contacts_dict = {}
        for contact in contacts:
            if contact.resource:
                self.num_resources += 1
                priority = int(contact.priority)
                if priority in contacts_dict:
                    contacts_dict[priority].append(contact)
                else:
                    contacts_dict[priority] = [contact]
        if self.num_resources > 1:
            transport = app.get_transport_name_from_jid(self.prim_contact.jid)
            if transport == 'jabber':
                transport = None
            contact_keys = sorted(contacts_dict.keys())
            contact_keys.reverse()
            for priority in contact_keys:
                for acontact in contacts_dict[priority]:
                    show = self._get_icon_name_for_tooltip(acontact)
                    status = acontact.status
                    resource_line = '%s (%s)' % (acontact.resource,
                                                 str(acontact.priority))
                    self.add_status_row(
                        show, resource_line, transport=transport)
                    if status:
                        self.add_text_row(status, 2)

            self._ui.tooltip_grid.attach(self.table, 1, 3, 2, 1)
            self.table.show_all()

        else:  # only one resource
            if contact.is_groupchat:
                disco_info = app.logger.get_last_disco_info(contact.jid)
                if disco_info is not None:
                    description = disco_info.muc_description
                    if description:
                        self._ui.status.set_text(description)
                        self._ui.status.show()
            elif contact.show and contact.status:
                status = contact.status.strip()
                if status:
                    self._ui.status.set_text(status)
                    self._ui.status.show()

        # PEP Info
        self._append_pep_info(contact)

        # JID
        self._ui.jid.set_text(self.prim_contact.jid)
        self._ui.jid.show()

        # contact has only one resource
        if self.num_resources == 1 and contact.resource:
            res = GLib.markup_escape_text(contact.resource)
            prio = str(contact.priority)
            self._ui.resource.set_text("{} ({})".format(res, prio))
            self._ui.resource.show()
            self._ui.resource_label.show()

        if self.prim_contact.jid not in app.gc_connected[account]:
            if (account and
                    self.prim_contact.sub and
                    self.prim_contact.sub != 'both'):
                # ('both' is the normal sub so we don't show it)
                self._ui.sub.set_text(helpers.get_uf_sub(self.prim_contact.sub))
                self._ui.sub.show()
                self._ui.sub_label.show()

        self._set_idle_time(contact)

        # Avatar
        scale = self._ui.tooltip_grid.get_scale_factor()
        surface = app.contacts.get_avatar(
            account, self.prim_contact.jid, AvatarSize.TOOLTIP, scale)
        self._ui.avatar.set_from_surface(surface)
        self._ui.avatar.show()

        app.plugin_manager.gui_extension_point(
            'roster_tooltip_populate', self, contacts, self._ui.tooltip_grid)

        # Sets the Widget that is at the bottom to expand.
        # This is needed in case the Picture takes more Space than the Labels
        i = 1
        while i < 15:
            if self._ui.tooltip_grid.get_child_at(1, i):
                if self._ui.tooltip_grid.get_child_at(1, i).get_visible():
                    self.last_widget = self._ui.tooltip_grid.get_child_at(1, i)
            i += 1
        self.last_widget.set_vexpand(True)

    def _show_merged_account_tooltip(self):
        accounts = helpers.get_notification_icon_tooltip_dict()
        self.spacer_label = ''
        self.fill_table_with_accounts(accounts)
        self._ui.tooltip_grid.attach(self.table, 1, 3, 2, 1)
        self.table.show_all()

    def _append_pep_info(self, contact):
        """
        Append Tune, Mood, Activity, Location information of the
        specified contact to the given property list.
        """
        if PEPEventType.MOOD in contact.pep:
            mood = format_mood(*contact.pep[PEPEventType.MOOD])
            self._ui.mood.set_markup(mood)
            self._ui.mood.show()
            self._ui.mood_label.show()

        if PEPEventType.ACTIVITY in contact.pep:
            activity = format_activity(*contact.pep[PEPEventType.ACTIVITY])
            self._ui.activity.set_markup(activity)
            self._ui.activity.show()
            self._ui.activity_label.show()

        if PEPEventType.TUNE in contact.pep:
            tune = format_tune(*contact.pep[PEPEventType.TUNE])
            self._ui.tune.set_markup(tune)
            self._ui.tune.show()
            self._ui.tune_label.show()

        if PEPEventType.LOCATION in contact.pep:
            location = format_location(contact.pep[PEPEventType.LOCATION])
            self._ui.location.set_markup(location)
            self._ui.location.show()
            self._ui.location_label.show()

    def _set_idle_time(self, contact):
        if contact.idle_time:
            idle_time = contact.idle_time
            idle_time = time.localtime(contact.idle_time)
            idle_time = datetime(*(idle_time[:6]))
            current = datetime.now()
            if idle_time.date() == current.date():
                formatted = idle_time.strftime('%X')
            else:
                formatted = idle_time.strftime('%c')
            self._ui.idle_since.set_text(formatted)
            self._ui.idle_since.show()
            self._ui.idle_since_label.show()

        if contact.show and self.num_resources < 2:
            show = helpers.get_uf_show(contact.show)
            # Contact is Groupchat
            if (self.account and
                    self.prim_contact.jid in app.gc_connected[self.account]):
                if app.gc_connected[self.account][self.prim_contact.jid]:
                    show = _('Connected')
                else:
                    show = _('Disconnected')

            colorize_status(self._ui.user_show, contact.show)
            self._ui.user_show.set_text(show)
            self._ui.user_show.show()

    @staticmethod
    def _get_icon_name_for_tooltip(contact):
        """
        Helper function used for tooltip contacts/accounts

        Tooltip on account has fake contact with sub == '', in this case we show
        real status of the account
        """
        if contact.ask == 'subscribe':
            return 'requested'
        if contact.sub in ('both', 'to', ''):
            return contact.show
        return 'not in roster'


class FileTransfersTooltip():
    def __init__(self):
        self.sid = None
        self.widget = None
        if app.config.get('use_kib_mib'):
            self.units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self.units = GLib.FormatSizeFlags.DEFAULT

    def clear_tooltip(self):
        self.sid = None
        self.widget = None

    def get_tooltip(self, file_props, sid):
        if self.sid == sid:
            return True, self.widget

        self.widget = self._create_tooltip(file_props, sid)
        self.sid = sid
        return False, self.widget

    def _create_tooltip(self, file_props, _sid):
        ft_grid = Gtk.Grid.new()
        ft_grid.insert_column(0)
        ft_grid.set_row_spacing(6)
        ft_grid.set_column_spacing(12)
        current_row = 0
        properties = []
        name = file_props.name
        if file_props.type_ == 'r':
            file_name = os.path.split(file_props.file_name)[1]
        else:
            file_name = file_props.name
        properties.append((_('File Name: '),
                           GLib.markup_escape_text(file_name)))
        if file_props.type_ == 'r':
            type_ = Q_('?Noun:Download')
            actor = _('Sender: ')
            sender = file_props.sender.split('/')[0]
            name = app.contacts.get_first_contact_from_jid(
                file_props.tt_account, sender).get_shown_name()
        else:
            type_ = Q_('?Noun:Upload')
            actor = _('Recipient: ')
            receiver = file_props.receiver
            if hasattr(receiver, 'name'):
                name = receiver.get_shown_name()
            else:
                name = receiver.split('/')[0]
        properties.append((Q_('?transfer type:Type: '), type_))
        properties.append((actor, GLib.markup_escape_text(name)))

        transfered_len = file_props.received_len
        if not transfered_len:
            transfered_len = 0
        properties.append((Q_('?transfer status:Transferred: '),
                           GLib.format_size_full(transfered_len, self.units)))
        status = self._get_current_status(file_props)
        properties.append((Q_('?transfer status:Status: '), status))
        file_desc = file_props.desc or ''
        properties.append((_('Description: '),
                           GLib.markup_escape_text(file_desc)))

        while properties:
            property_ = properties.pop(0)
            label = Gtk.Label()
            label.set_halign(Gtk.Align.END)
            label.set_valign(Gtk.Align.CENTER)
            label.set_markup(property_[0])
            ft_grid.attach(label, 0, current_row, 1, 1)
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_line_wrap(True)
            label.set_markup(property_[1])
            ft_grid.attach(label, 1, current_row, 1, 1)
            current_row += 1

        ft_grid.show_all()
        return ft_grid

    @staticmethod
    def _get_current_status(file_props):
        if file_props.stopped:
            return Q_('?transfer status:Aborted')
        if file_props.completed:
            return Q_('?transfer status:Completed')
        if file_props.paused:
            return Q_('?transfer status:Paused')
        if file_props.stalled:
            # stalled is not paused. it is like 'frozen' it stopped alone
            return Q_('?transfer status:Stalled')

        if file_props.connected:
            if file_props.started:
                return Q_('?transfer status:Transferring')
            return Q_('?transfer status:Not started')
        return Q_('?transfer status:Not started')


def colorize_status(widget, show):
    """
    Colorize the status message inside the tooltip by it's semantics.
    """
    css_class = get_css_show_class(show)[14:]
    add_css_class(widget, css_class, prefix='gajim-status-')
