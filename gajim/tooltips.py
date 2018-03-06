# -*- coding: utf-8 -*-
## src/tooltips.py
##
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
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

import os
import time
import logging
from datetime import datetime

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

from gajim import gtkgui_helpers
from gajim.common.const import AvatarSize
from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import Q_

log = logging.getLogger('gajim.tooltips')


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
        self.table.set_property('column-spacing', 2)

    def add_text_row(self, text, col_inc=0):
        self.table.insert_row(self.current_row)
        self.text_label = Gtk.Label()
        self.text_label.set_line_wrap(True)
        self.text_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.text_label.set_max_width_chars(35)
        self.text_label.set_halign(Gtk.Align.START)
        self.text_label.set_valign(Gtk.Align.START)
        self.text_label.set_selectable(False)
        self.text_label.set_markup(text)
        self.table.attach(self.text_label, 1 + col_inc, self.current_row,
            3 - col_inc, 1)
        self.current_row += 1

    def get_status_info(self, resource, priority, show, status):
        str_status = resource + ' (' + str(priority) + ')'
        if status:
            status = status.strip()
            if status != '':
                # reduce to 100 chars, 1 line
                status = helpers.reduce_chars_newlines(status, 100, 1)
                str_status = GLib.markup_escape_text(str_status)
                status = GLib.markup_escape_text(status)
                str_status += ' - <i>' + status + '</i>'
        return str_status

    def add_status_row(self, file_path, show, str_status, show_lock=False,
    indent=True):
        """
        Append a new row with status icon to the table
        """
        self.table.insert_row(self.current_row)
        state_file = show.replace(' ', '_')
        files = []
        files.append(os.path.join(file_path, state_file + '.png'))
        files.append(os.path.join(file_path, state_file + '.gif'))
        image = Gtk.Image()
        image.set_from_pixbuf(None)
        for f in files:
            if os.path.exists(f):
                image.set_from_file(f)
                break
        spacer = Gtk.Label(label=self.spacer_label)
        image.set_halign(Gtk.Align.START)
        image.set_valign(Gtk.Align.CENTER)
        if indent:
            self.table.attach(spacer, 1, self.current_row, 1, 1)
        self.table.attach(image, 2, self.current_row, 1, 1)
        status_label = Gtk.Label()
        status_label.set_markup(str_status)
        status_label.set_halign(Gtk.Align.START)
        status_label.set_valign(Gtk.Align.START)
        status_label.set_line_wrap(True)
        self.table.attach(status_label, 3, self.current_row, 1, 1)
        if show_lock:
            lock_image = Gtk.Image()
            lock_image.set_from_icon_name("dialog-password",
                Gtk.IconSize.MENU)
            self.table.attach(lock_image, 4, self.current_row, 1, 1)
        self.current_row += 1


class NotificationAreaTooltip(StatusTable):
    """
    Tooltip that is shown in the notification area
    """

    def __init__(self):
        StatusTable.__init__(self)

    def fill_table_with_accounts(self, accounts):
        iconset = app.config.get('iconset')
        if not iconset:
            iconset = 'dcraven'
        file_path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
        for acct in accounts:
            message = acct['message']
            message = helpers.reduce_chars_newlines(message, 100, 1)
            message = GLib.markup_escape_text(message)
            if acct['name'] in app.con_types and \
                    app.con_types[acct['name']] in ('tls', 'ssl'):
                show_lock = True
            else:
                show_lock = False
            if message:
                self.add_status_row(file_path, acct['show'],
                    GLib.markup_escape_text(acct['name']) + ' - ' + message,
                    show_lock=show_lock, indent=False)
            else:
                self.add_status_row(file_path, acct['show'],
                    GLib.markup_escape_text(acct['name']), show_lock=show_lock,
                    indent=False)
            for line in acct['event_lines']:
                self.add_text_row('  ' + line, 1)

    def get_tooltip(self):
        self.create_table()

        accounts = helpers.get_notification_icon_tooltip_dict()
        self.fill_table_with_accounts(accounts)
        self.hbox = Gtk.HBox()
        self.table.set_property('column-spacing', 1)

        self.hbox.add(self.table)
        self.hbox.show_all()
        return self.hbox


class GCTooltip():
    # pylint: disable=E1101
    def __init__(self):
        self.contact = None

        self.xml = gtkgui_helpers.get_gtk_builder('tooltip_gc_contact.ui')
        for name in ('nick', 'status', 'jid', 'user_show', 'fillelement',
                     'resource', 'affiliation', 'avatar', 'resource_label',
                     'jid_label', 'tooltip_grid'):
            setattr(self, name, self.xml.get_object(name))

    def clear_tooltip(self):
        self.contact = None

    def get_tooltip(self, contact):
        if self.contact == contact:
            return True, self.tooltip_grid

        self._populate_grid(contact)
        self.contact = contact
        return False, self.tooltip_grid

    def _hide_grid_childs(self):
        """
        Hide all Elements of the Tooltip Grid
        """
        for child in self.tooltip_grid.get_children():
            child.hide()

    def _populate_grid(self, contact):
        """
        Populate the Tooltip Grid with data of from the contact
        """
        self._hide_grid_childs()

        self.nick.set_text(contact.get_shown_name())
        self.nick.show()

        # Status Message
        if contact.status:
            status = contact.status.strip()
            if status != '':
                self.status.set_text(status)
                self.status.show()

        # Status
        show = helpers.get_uf_show(contact.show)
        self.user_show.set_markup(colorize_status(show))
        self.user_show.show()

        # JID
        if contact.jid.strip():
            self.jid.set_text(contact.jid)
            self.jid.show()
            self.jid_label.show()
        # Resource
        if hasattr(contact, 'resource') and contact.resource.strip():
            self.resource.set_text(contact.resource)
            self.resource.show()
            self.resource_label.show()

        # Affiliation
        if contact.affiliation != 'none':
            uf_affiliation = helpers.get_uf_affiliation(contact.affiliation)
            uf_affiliation = \
                _('%(owner_or_admin_or_member)s of this group chat') \
                % {'owner_or_admin_or_member': uf_affiliation}
            uf_affiliation = self.colorize_affiliation(uf_affiliation)
            self.affiliation.set_markup(uf_affiliation)
            self.affiliation.show()

        # Avatar
        if contact.avatar_sha is not None:
            app.log('avatar').debug(
                'Load GCTooltip: %s %s', contact.name, contact.avatar_sha)
            scale = self.tooltip_grid.get_scale_factor()
            surface = app.interface.get_avatar(
                contact.avatar_sha, AvatarSize.TOOLTIP, scale)
            if surface is not None:
                self.avatar.set_from_surface(surface)
                self.avatar.show()
                self.fillelement.show()

        app.plugin_manager.gui_extension_point(
            'gc_tooltip_populate', self, contact, self.tooltip_grid)

    @staticmethod
    def colorize_affiliation(affiliation):
        """
        Color the affiliation of a MUC participant inside the tooltip by
        it's semantics. Color palette is the Tango.
        """
        formatted = "<span foreground='%s'>%s</span>"
        color = None
        if affiliation.startswith(Q_("?Group Chat Contact Affiliation:None")):
            color = app.config.get('tooltip_affiliation_none_color')
        elif affiliation.startswith(_("Member")):
            color = app.config.get('tooltip_affiliation_member_color')
        elif affiliation.startswith(_("Administrator")):
            color = app.config.get('tooltip_affiliation_administrator_color')
        elif affiliation.startswith(_("Owner")):
            color = app.config.get('tooltip_affiliation_owner_color')
        if color:
            affiliation = formatted % (color, affiliation)
        return affiliation

class RosterTooltip(Gtk.Window, StatusTable):
    # pylint: disable=E1101
    def __init__(self, parent):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP, transient_for=parent)
        StatusTable.__init__(self)
        self.create_table()
        self.row = None
        self.contact_jid = None
        self.last_widget = None
        self.num_resources = 0
        self.set_title('tooltip')
        self.set_border_width(3)
        self.set_resizable(False)
        self.set_name('gtk-tooltips')
        self.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)

        self.xml = gtkgui_helpers.get_gtk_builder('tooltip_roster_contact.ui')
        for name in ('name', 'status', 'jid', 'user_show', 'fillelement',
            'resource', 'avatar', 'resource_label', 'pgp', 'pgp_label',
                'jid_label', 'tooltip_grid', 'idle_since', 'idle_since_label',
                'mood', 'tune', 'activity', 'location', 'tune_label',
                'location_label', 'activity_label', 'mood_label', 'sub_label',
                'sub', 'status_label'):
            setattr(self, name, self.xml.get_object(name))

        self.add(self.tooltip_grid)
        self.tooltip_grid.show()

    def clear_tooltip(self):
        """
        Hide all Elements of the Tooltip Grid
        """
        for child in self.tooltip_grid.get_children():
            child.hide()
        status_table = self.tooltip_grid.get_child_at(0, 3)
        if status_table:
            status_table.destroy()
            self.create_table()

    def fill_table_with_accounts(self, accounts):
        iconset = app.config.get('iconset')
        if not iconset:
            iconset = 'dcraven'
        file_path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
        for acct in accounts:
            message = acct['message']
            message = helpers.reduce_chars_newlines(message, 100, 1)
            message = GLib.markup_escape_text(message)
            if acct['name'] in app.con_types and \
                    app.con_types[acct['name']] in ('tls', 'ssl'):
                show_lock = True
            else:
                show_lock = False
            if message:
                self.add_status_row(file_path, acct['show'],
                    GLib.markup_escape_text(acct['name']) + ' - ' + message,
                    show_lock=show_lock, indent=False)
            else:
                self.add_status_row(file_path, acct['show'],
                    GLib.markup_escape_text(acct['name']), show_lock=show_lock,
                    indent=False)
            for line in acct['event_lines']:
                self.add_text_row('  ' + line, 1)

    def populate(self, contacts, account, typ):
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
            accounts = helpers.get_notification_icon_tooltip_dict()
            self.spacer_label = ''
            self.fill_table_with_accounts(accounts)
            self.tooltip_grid.attach(self.table, 0, 3, 2, 1)
            self.table.show_all()
            return

        if typ == 'account':
            jid = app.get_jid_from_account(account)
            contacts = []
            connection = app.connections[account]
            # get our current contact info

            nbr_on, nbr_total = app.\
                contacts.get_nb_online_total_contacts(
                accounts=[account])
            account_name = account
            if app.account_is_connected(account):
                account_name += ' (%s/%s)' % (repr(nbr_on),
                    repr(nbr_total))
            contact = app.contacts.create_self_contact(jid=jid,
                account=account, name=account_name,
                show=connection.get_status(), status=connection.status,
                resource=connection.server_resource,
                priority=connection.priority)
            if app.connections[account].gpg:
                contact.keyID = app.config.get_per('accounts',
                    connection.name, 'keyid')
            contacts.append(contact)
            # if we're online ...
            if connection.connection:
                roster = connection.connection.getRoster()
                # in threadless connection when no roster stanza is sent
                # 'roster' is None
                if roster and roster.getItem(jid):
                    resources = roster.getResources(jid)
                    # ...get the contact info for our other online
                    # resources
                    for resource in resources:
                        # Check if we already have this resource
                        found = False
                        for contact_ in contacts:
                            if contact_.resource == resource:
                                found = True
                                break
                        if found:
                            continue
                        show = roster.getShow(jid + '/' + resource)
                        if not show:
                            show = 'online'
                        contact = app.contacts.create_self_contact(
                            jid=jid, account=account, show=show,
                            status=roster.getStatus(
                            jid + '/' + resource),
                            priority=roster.getPriority(
                            jid + '/' + resource), resource=resource)
                        contacts.append(contact)

        # Username/Account/Groupchat
        self.prim_contact = app.contacts.get_highest_prio_contact_from_contacts(
            contacts)
        if self.prim_contact is None:
            log.error('No contact for Roster tooltip found')
            log.error('contacts: %s, typ: %s, account: %s', contacts, typ, account)
            return
        self.contact_jid = self.prim_contact.jid
        name = GLib.markup_escape_text(self.prim_contact.get_shown_name())
        name_markup = '<b>{}</b>'.format(name)
        if app.config.get('mergeaccounts'):
            color = app.config.get('tooltip_account_name_color')
            account_name = GLib.markup_escape_text(self.prim_contact.account.name)
            name_markup += " <span foreground='{}'>({})</span>".format(
                color, account_name)

        if account and helpers.jid_is_blocked(account, self.prim_contact.jid):
            name_markup += _(' [blocked]')

        try:
            if self.prim_contact.jid in app.interface.minimized_controls[account]:
                name_markup += _(' [minimized]')
        except KeyError:
            pass

        self.name.set_markup(name_markup)
        self.name.show()

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
            self.status_label.show()
            transport = app.get_transport_name_from_jid(self.prim_contact.jid)
            if transport:
                file_path = os.path.join(helpers.get_transport_path(transport),
                    '16x16')
            else:
                iconset = app.config.get('iconset')
                if not iconset:
                    iconset = 'dcraven'
                file_path = os.path.join(helpers.get_iconset_path(iconset),
                    '16x16')

            contact_keys = sorted(contacts_dict.keys())
            contact_keys.reverse()
            for priority in contact_keys:
                for acontact in contacts_dict[priority]:
                    icon_name = self._get_icon_name_for_tooltip(acontact)
                    if acontact.status and len(acontact.status) > 25:
                        status = ''
                        add_text = True
                    else:
                        status = acontact.status
                        add_text = False

                    status_line = self.get_status_info(acontact.resource,
                    acontact.priority, acontact.show, status)
                    self.add_status_row(file_path, icon_name, status_line)
                    if add_text:
                        self.add_text_row(acontact.status, 2)

            self.tooltip_grid.attach(self.table, 0, 3, 2, 1)
            self.table.show_all()

        else:  # only one resource
            if contact.show and contact.status:
                status = contact.status.strip()
                if status:
                    self.status.set_text(status)
                    self.status.show()
                    self.status_label.show()

        # PEP Info
        self._append_pep_info(contact)

        # JID
        self.jid.set_text(self.prim_contact.jid)
        self.jid.show()
        self.jid_label.show()

        # contact has only one ressource
        if self.num_resources == 1 and contact.resource:
            res = GLib.markup_escape_text(contact.resource)
            prio = str(contact.priority)
            self.resource.set_text("{} ({})".format(res, prio))
            self.resource.show()
            self.resource_label.show()

        if self.prim_contact.jid not in app.gc_connected[account]:
            if (account and
                self.prim_contact.sub and
                    self.prim_contact.sub != 'both'):
                # ('both' is the normal sub so we don't show it)
                self.sub.set_text(helpers.get_uf_sub(self.prim_contact.sub))
                self.sub.show()
                self.sub_label.show()

        if self.prim_contact.keyID:
            keyID = None
            if len(self.prim_contact.keyID) == 8:
                keyID = self.prim_contact.keyID
            elif len(self.prim_contact.keyID) == 16:
                keyID = self.prim_contact.keyID[8:]
            if keyID:
                self.pgp.set_text(keyID)
                self.pgp.show()
                self.pgp_label.show()

        self._set_idle_time(contact)

        # Avatar
        scale = self.get_scale_factor()
        surface = app.contacts.get_avatar(
            account, self.prim_contact.jid, AvatarSize.TOOLTIP, scale)
        if surface is None:
            return
        self.avatar.set_from_surface(surface)
        self.avatar.show()

        # Sets the Widget that is at the bottom to expand.
        # This is needed in case the Picture takes more Space then the Labels
        i = 1
        while i < 15:
            if self.tooltip_grid.get_child_at(0, i):
                if self.tooltip_grid.get_child_at(0, i).get_visible():
                    self.last_widget = self.tooltip_grid.get_child_at(0, i)
            i += 1
        self.last_widget.set_vexpand(True)

    def _append_pep_info(self, contact):
        """
        Append Tune, Mood, Activity, Location information of the specified contact
        to the given property list.
        """
        if 'mood' in contact.pep:
            mood = contact.pep['mood'].asMarkupText()
            self.mood.set_markup(mood)
            self.mood.show()
            self.mood_label.show()

        if 'activity' in contact.pep:
            activity = contact.pep['activity'].asMarkupText()
            self.activity.set_markup(activity)
            self.activity.show()
            self.activity_label.show()

        if 'tune' in contact.pep:
            tune = contact.pep['tune'].asMarkupText()
            self.tune.set_markup(tune)
            self.tune.show()
            self.tune_label.show()

        if 'location' in contact.pep:
            location = contact.pep['location'].asMarkupText()
            self.location.set_markup(location)
            self.location.show()
            self.location_label.show()

    def _set_idle_time(self, contact):
        if contact.idle_time:
            idle_color = app.config.get('tooltip_idle_color')
            idle_time = contact.idle_time
            idle_time = time.localtime(contact.idle_time)
            idle_time = datetime(*(idle_time[:6]))
            current = datetime.now()
            if idle_time.date() == current.date():
                formatted = idle_time.strftime("%X")
            else:
                formatted = idle_time.strftime("%c")
            idle_markup = "<span foreground='{}'>{}</span>".format(idle_color,
                formatted)
            self.idle_since.set_markup(idle_markup)
            self.idle_since.show()
            self.idle_since_label.show()

        if contact.show and self.num_resources < 2:
            show = helpers.get_uf_show(contact.show)
            # Contact is Groupchat
            if (self.account and
                    self.prim_contact.jid in app.gc_connected[self.account]):
                if app.gc_connected[self.account][self.prim_contact.jid]:
                    show = _('Connected')
                else:
                    show = _('Disconnected')

            self.user_show.set_markup(colorize_status(show))
            self.user_show.show()

    def _get_icon_name_for_tooltip(self, contact):
        """
        Helper function used for tooltip contacts/acounts

        Tooltip on account has fake contact with sub == '', in this case we show
        real status of the account
        """
        if contact.ask == 'subscribe':
            return 'requested'
        elif contact.sub in ('both', 'to', ''):
            return contact.show
        return 'not in roster'


class FileTransfersTooltip():
    def __init__(self):
        self.sid = None
        self.widget = None

    def clear_tooltip(self):
        self.sid = None
        self.widget = None

    def get_tooltip(self, file_props, sid):
        if self.sid == sid:
            return True, self.widget

        self.widget = self._create_tooltip(file_props, sid)
        self.sid = sid
        return False, self.widget

    @staticmethod
    def _create_tooltip(file_props, sid):
        ft_table = Gtk.Table(2, 1)
        ft_table.set_property('column-spacing', 2)
        current_row = 1
        properties = []
        name = file_props.name
        if file_props.type_ == 'r':
            file_name = os.path.split(file_props.file_name)[1]
        else:
            file_name = file_props.name
        properties.append((_('Name: '), GLib.markup_escape_text(file_name)))
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
        properties.append((_('Type: '), type_))
        properties.append((actor, GLib.markup_escape_text(name)))

        transfered_len = file_props.received_len
        if not transfered_len:
            transfered_len = 0
        properties.append((_('Transferred: '), helpers.convert_bytes(transfered_len)))
        status = ''
        if file_props.started:
            status = _('Not started')
        if file_props.stopped:
            status = _('Stopped')
        elif file_props.completed:
            status = _('Completed')
        elif not file_props.connected:
            if file_props.completed:
                status = _('Completed')
            else:
                if file_props.paused:
                    status = Q_('?transfer status:Paused')
                elif file_props.stalled:
                    # stalled is not paused. it is like 'frozen' it stopped alone
                    status = _('Stalled')
                else:
                    status = _('Transferring')
        else:
            status = _('Not started')
        properties.append((_('Status: '), status))
        file_desc = file_props.desc or ''
        properties.append((_('Description: '), GLib.markup_escape_text(
            file_desc)))
        while properties:
            property_ = properties.pop(0)
            current_row += 1
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_markup(property_[0])
            ft_table.attach(label, 1, 2, current_row, current_row + 1,
                    Gtk.AttachOptions.FILL, Gtk.AttachOptions.FILL, 0, 0)
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.START)
            label.set_line_wrap(True)
            label.set_markup(property_[1])
            ft_table.attach(label, 2, 3, current_row, current_row + 1,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, Gtk.AttachOptions.FILL, 0, 0)

        ft_table.show_all()
        return ft_table


def colorize_status(status):
    """
    Colorize the status message inside the tooltip by it's
    semantics. Color palette is the Tango.
    """
    formatted = "<span foreground='%s'>%s</span>"
    color = None
    if status.startswith(Q_("?user status:Available")):
        color = app.config.get('tooltip_status_online_color')
    elif status.startswith(_("Free for Chat")):
        color = app.config.get('tooltip_status_free_for_chat_color')
    elif status.startswith(_("Away")):
        color = app.config.get('tooltip_status_away_color')
    elif status.startswith(_("Busy")):
        color = app.config.get('tooltip_status_busy_color')
    elif status.startswith(_("Not Available")):
        color = app.config.get('tooltip_status_na_color')
    elif status.startswith(_("Offline")):
        color = app.config.get('tooltip_status_offline_color')
    if color:
        status = formatted % (color, status)
    return status
