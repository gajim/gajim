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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
import os
import time
from datetime import datetime
from datetime import timedelta

import gtkgui_helpers

from common import gajim
from common import helpers
from common.pep import MOODS, ACTIVITIES
from common.i18n import Q_

class BaseTooltip:
    """
    Base Tooltip class

            Usage:
                    tooltip = BaseTooltip()
                    ....
                    tooltip.show_tooltip(data, widget_height, widget_y_position)
                    ....
                    if tooltip.timeout != 0:
                            tooltip.hide_tooltip()

            * data - the text to be displayed  (extenders override this argument and
                    display more complex contents)
            * widget_height  - the height of the widget on which we want to show tooltip
            * widget_y_position - the vertical position of the widget on the screen

            Tooltip is displayed aligned centered to the mouse poiner and 4px below the widget.
            In case tooltip goes below the visible area it is shown above the widget.
    """

    def __init__(self):
        self.timeout = 0
        self.preferred_position = [0, 0]
        self.win = None
        self.id = None
        self.cur_data = None
        self.check_last_time = None
        self.shown = False
        self.position_computed = False

    def populate(self, data):
        """
        This method must be overriden by all extenders. This is the most simple
        implementation: show data as value of a label
        """
        self.create_window()
        self.win.add(Gtk.Label(label=data))

    def create_window(self):
        """
        Create a popup window each time tooltip is requested
        """
        self.win = Gtk.Window.new(Gtk.WindowType.POPUP)
        self.win.set_title('tooltip')
        self.win.set_border_width(3)
        self.win.set_resizable(False)
        self.win.set_name('gtk-tooltips')
        self.win.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)

        self.win.set_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.win.connect('size-allocate', self.on_size_allocate)
        self.win.connect('motion-notify-event', self.motion_notify_event)
        self.screen = self.win.get_screen()

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

    def motion_notify_event(self, widget, event):
        GLib.idle_add(self.hide_tooltip)

    def on_size_allocate(self, widget, rect):
        if not self.position_computed:
            half_width = rect.width / 2 + 1
            if self.preferred_position[1] + rect.height > \
            self.screen.get_height():
                 # flip tooltip up
                self.preferred_position[1] -= rect.height + self.widget_height \
                    + 8
                if self.preferred_position[1] < 0:
                    self.preferred_position[1] = self.screen.get_height() - \
                        rect.height - 2

                    if self.preferred_position[0] + rect.width + 7 < \
                    self.screen.get_width():
                        self.preferred_position[0] = self.preferred_position[0]\
                            + 7
                    else:
                        self.preferred_position[0] = self.preferred_position[0]\
                            - rect.width - 7
                    self.win.move(self.preferred_position[0],
                        self.preferred_position[1])
                    return
            if self.preferred_position[0] < half_width:
                self.preferred_position[0] = 0
            elif self.preferred_position[0] + rect.width > \
            self.screen.get_width() + half_width:
                self.preferred_position[0] = self.screen.get_width() - \
                    rect.width
            elif not self.check_last_time:
                self.preferred_position[0] -= half_width
            self.position_computed = True
        self.win.move(self.preferred_position[0], self.preferred_position[1])

    def show_tooltip(self, data, widget_height, widget_y_position):
        """
        Show tooltip on widget

        Data contains needed data for tooltip contents.
        widget_height is the height of the widget on which we show the tooltip.
        widget_y_position is vertical position of the widget on the screen.
        """
        if self.shown:
            return
        self.position_computed = False
        self.cur_data = data
        # set tooltip contents
        self.populate(data)

        # get the X position of mouse pointer on the screen
        pointer_x = self.screen.get_display().get_device_manager().\
            get_client_pointer().get_position()[1]

        # get the prefered X position of the tooltip on the screen in case this position is >
        # than the height of the screen, tooltip will be shown above the widget
        preferred_y = widget_y_position + widget_height + 4

        self.preferred_position = [pointer_x, preferred_y]
        self.widget_height = widget_height
        self.win.show_all()
        self.shown = True

    def hide_tooltip(self):
        if self.timeout > 0:
            GLib.source_remove(self.timeout)
            self.timeout = 0
        if self.win:
            self.win.destroy()
            self.win = None
        self.id = None
        self.cur_data = None
        self.check_last_time = None
        self.shown = False

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

    def add_status_row(self, file_path, show, str_status, status_time=None,
    show_lock=False, indent=True):
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
            lock_image.set_from_stock(Gtk.STOCK_DIALOG_AUTHENTICATION,
                Gtk.IconSize.MENU)
            self.table.attach(lock_image, 4, self.current_row, 1, 1)
        self.current_row += 1

class NotificationAreaTooltip(BaseTooltip, StatusTable):
    """
    Tooltip that is shown in the notification area
    """

    def __init__(self):
        BaseTooltip.__init__(self)
        StatusTable.__init__(self)

    def fill_table_with_accounts(self, accounts):
        iconset = gajim.config.get('iconset')
        if not iconset:
            iconset = 'dcraven'
        file_path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
        for acct in accounts:
            message = acct['message']
            message = helpers.reduce_chars_newlines(message, 100, 1)
            message = GLib.markup_escape_text(message)
            if acct['name'] in gajim.con_types and \
                    gajim.con_types[acct['name']] in ('tls', 'ssl'):
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

    def populate(self, data=''):
        self.create_window()
        self.create_table()

        accounts = helpers.get_notification_icon_tooltip_dict()
        self.fill_table_with_accounts(accounts)
        self.hbox = Gtk.HBox()
        self.table.set_property('column-spacing', 1)

        self.hbox.add(self.table)
        self.hbox.show_all()

class GCTooltip(Gtk.Window):
    # pylint: disable=E1101
    def __init__(self, parent):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP, transient_for=parent)
        self.row = None
        self.set_title('tooltip')
        self.set_border_width(3)
        self.set_resizable(False)
        self.set_name('gtk-tooltips')
        self.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)

        self.xml = gtkgui_helpers.get_gtk_builder('tooltip_gc_contact.ui')
        for name in ('nick', 'status', 'jid', 'user_show', 'fillelement',
            'resource', 'affiliation', 'avatar', 'resource_label',
                'jid_label', 'tooltip_grid'):
            setattr(self, name, self.xml.get_object(name))

        self.add(self.tooltip_grid)
        self.tooltip_grid.show()

    def clear_tooltip(self):
        """
        Hide all Elements of the Tooltip Grid
        """
        for child in self.tooltip_grid.get_children():
            child.hide()

    def populate(self, contact):
        """
        Populate the Tooltip Grid with data of from the contact
        """
        self.clear_tooltip()

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
        puny_name = helpers.sanitize_filename(contact.name)
        puny_room = helpers.sanitize_filename(contact.room_jid)
        file_ = helpers.get_avatar_path(os.path.join(gajim.AVATAR_PATH,
            puny_room, puny_name))
        if file_:
            with open(file_, 'rb') as file_data:
                pix = gtkgui_helpers.get_pixbuf_from_data(file_data.read())
            pix = gtkgui_helpers.get_scaled_pixbuf(pix, 'tooltip')
            self.avatar.set_from_pixbuf(pix)
            self.avatar.show()
            self.fillelement.show()

    @staticmethod
    def colorize_affiliation(affiliation):
        """
        Color the affiliation of a MUC participant inside the tooltip by
        it's semantics. Color palette is the Tango.
        """
        formatted = "<span foreground='%s'>%s</span>"
        color = None
        if affiliation.startswith(Q_("?Group Chat Contact Affiliation:None")):
            color = gajim.config.get('tooltip_affiliation_none_color')
        elif affiliation.startswith(_("Member")):
            color = gajim.config.get('tooltip_affiliation_member_color')
        elif affiliation.startswith(_("Administrator")):
            color = gajim.config.get('tooltip_affiliation_administrator_color')
        elif affiliation.startswith(_("Owner")):
            color = gajim.config.get('tooltip_affiliation_owner_color')
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
        self.check_last_time = {}
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
                'jid_label', 'tooltip_grid', 'idle_since', 'idle_for',
                'idle_since_label', 'idle_for_label', 'mood', 'tune',
                'activity', 'location', 'tune_label', 'location_label',
                'activity_label', 'mood_label', 'sub_label', 'sub',
                'status_label'):
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
        iconset = gajim.config.get('iconset')
        if not iconset:
            iconset = 'dcraven'
        file_path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
        for acct in accounts:
            message = acct['message']
            message = helpers.reduce_chars_newlines(message, 100, 1)
            message = GLib.markup_escape_text(message)
            if acct['name'] in gajim.con_types and \
                    gajim.con_types[acct['name']] in ('tls', 'ssl'):
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
            jid = gajim.get_jid_from_account(account)
            contacts = []
            connection = gajim.connections[account]
            # get our current contact info

            nbr_on, nbr_total = gajim.\
                contacts.get_nb_online_total_contacts(
                accounts=[account])
            account_name = account
            if gajim.account_is_connected(account):
                account_name += ' (%s/%s)' % (repr(nbr_on),
                    repr(nbr_total))
            contact = gajim.contacts.create_self_contact(jid=jid,
                account=account, name=account_name,
                show=connection.get_status(), status=connection.status,
                resource=connection.server_resource,
                priority=connection.priority)
            if gajim.connections[account].gpg:
                contact.keyID = gajim.config.get_per('accounts',
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
                        contact = gajim.contacts.create_self_contact(
                            jid=jid, account=account, show=show,
                            status=roster.getStatus(
                            jid + '/' + resource),
                            priority=roster.getPriority(
                            jid + '/' + resource), resource=resource)
                        contacts.append(contact)

        # Username/Account/Groupchat
        self.prim_contact = gajim.contacts.get_highest_prio_contact_from_contacts(
            contacts)
        self.contact_jid = self.prim_contact.jid
        name = GLib.markup_escape_text(self.prim_contact.get_shown_name())
        name_markup = '<b>{}</b>'.format(name)
        if gajim.config.get('mergeaccounts'):
            color = gajim.config.get('tooltip_account_name_color')
            account_name = GLib.markup_escape_text(self.prim_contact.account.name)
            name_markup += " <span foreground='{}'>({})</span>".format(
                color, account_name)

        if account and helpers.jid_is_blocked(account, self.prim_contact.jid):
            name_markup += _(' [blocked]')

        try:
            if self.prim_contact.jid in gajim.interface.minimized_controls[account]:
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
            transport = gajim.get_transport_name_from_jid(self.prim_contact.jid)
            if transport:
                file_path = os.path.join(helpers.get_transport_path(transport),
                    '16x16')
            else:
                iconset = gajim.config.get('iconset')
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
                    self.add_status_row(file_path, icon_name, status_line,
                        acontact.last_status_time)
                    if add_text:
                        self.add_text_row(acontact.status, 2)

            self.tooltip_grid.attach(self.table, 0, 3, 2, 1)
            self.table.show_all()

        else:  # only one resource
            if contact.show:
                request_time = False
                try:
                    last_time = self.check_last_time[contact]
                    if isinstance(last_time, float) and last_time < time.time() - 60:
                        request_time = True
                except KeyError:
                    request_time = True

                if request_time:
                    if contact.show == 'offline':
                        gajim.connections[account].\
                            request_last_status_time(contact.jid, '')
                    elif contact.resource:
                        gajim.connections[account].\
                            request_last_status_time(
                            contact.jid, contact.resource)
                    self.check_last_time[contact] = time.time()

                if contact.status:
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

        if self.prim_contact.jid not in gajim.gc_connected[account]:
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
        puny_jid = helpers.sanitize_filename(self.prim_contact.jid)
        file_ = helpers.get_avatar_path(os.path.join(gajim.AVATAR_PATH,
            puny_jid))
        if file_:
            with open(file_, 'rb') as file_data:
                pix = gtkgui_helpers.get_pixbuf_from_data(file_data.read())
            pix = gtkgui_helpers.get_scaled_pixbuf(pix, 'tooltip')
            self.avatar.set_from_pixbuf(pix)
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
        if contact.last_activity_time:
            last_active = datetime(*contact.last_activity_time[:6])
            current = datetime.now()

            diff = current - last_active
            diff = timedelta(diff.days, diff.seconds)

            if last_active.date() == current.date():
                formatted = last_active.strftime("%X")
            else:
                formatted = last_active.strftime("%c")

            # Do not show the "Idle since" and "Idle for" items if there
            # is no meaningful difference between last activity time and
            # current time.
            if diff.days > 0 or diff.seconds > 0:
                idle_color = gajim.config.get('tooltip_idle_color')
                idle_markup = "<span foreground='{}'>{}</span>".format(idle_color, formatted)
                self.idle_since.set_markup(idle_markup)
                self.idle_since.show()
                self.idle_since_label.show()
                idle_markup = "<span foreground='{}'>{}</span>".format(idle_color, str(diff))
                self.idle_for.set_markup(idle_markup)
                self.idle_for_label.show()
                self.idle_for.show()

        if contact.show and self.num_resources < 2:
            show = helpers.get_uf_show(contact.show)
            if contact.last_status_time:
                if contact.show == 'offline':
                    text = ' - ' + _('Last status: %s')
                else:
                    text = _(' since %s')

                if time.strftime('%j', time.localtime()) == \
                        time.strftime('%j', contact.last_status_time):
                    # it's today, show only the locale hour representation
                    local_time = time.strftime('%X', contact.last_status_time)
                else:
                    # time.strftime returns locale encoded string
                    local_time = time.strftime('%c', contact.last_status_time)

                text = text % local_time
                show += text

            # Contact is Groupchat
            if (self.account and
                    self.prim_contact.jid in gajim.gc_connected[self.account]):
                if gajim.gc_connected[self.account][self.prim_contact.jid]:
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

    def update_last_time(self, contact, error=False):
        if not contact:
            return
        if error:
            self.check_last_time[contact] = 'error'
            return
        if contact.jid == self.contact_jid:
            self._set_idle_time(contact)


class FileTransfersTooltip(BaseTooltip):
    """
    Tooltip that is shown in the notification area
    """

    def __init__(self):
        BaseTooltip.__init__(self)

    def populate(self, file_props):
        ft_table = Gtk.Table(2, 1)
        ft_table.set_property('column-spacing', 2)
        current_row = 1
        self.create_window()
        properties = []
        name = file_props.name
        if file_props.type_ == 'r':
            file_name = os.path.split(file_props.file_name)[1]
        else:
            file_name = file_props.name
        properties.append((_('Name: '), GLib.markup_escape_text(file_name)))
        if file_props.type_ == 'r':
            type_ = _('?Noun:Download')
            actor = _('Sender: ')
            sender = file_props.sender.split('/')[0]
            name = gajim.contacts.get_first_contact_from_jid(
                    file_props.tt_account, sender).get_shown_name()
        else:
            type_ = _('?Noun:Upload')
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
        if file_props.stopped == True:
            status = _('Stopped')
        elif file_props.completed:
            status = _('Completed')
        elif file_props.connected == False:
            if file_props.completed:
                status = _('Completed')
            else:
                if file_props.paused == True:
                    status = _('?transfer status:Paused')
                elif file_props.stalled == True:
                    #stalled is not paused. it is like 'frozen' it stopped alone
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

        self.win.add(ft_table)


def colorize_status(status):
    """
    Colorize the status message inside the tooltip by it's
    semantics. Color palette is the Tango.
    """
    formatted = "<span foreground='%s'>%s</span>"
    color = None
    if status.startswith(Q_("?user status:Available")):
        color = gajim.config.get('tooltip_status_online_color')
    elif status.startswith(_("Free for Chat")):
        color = gajim.config.get('tooltip_status_free_for_chat_color')
    elif status.startswith(_("Away")):
        color = gajim.config.get('tooltip_status_away_color')
    elif status.startswith(_("Busy")):
        color = gajim.config.get('tooltip_status_busy_color')
    elif status.startswith(_("Not Available")):
        color = gajim.config.get('tooltip_status_na_color')
    elif status.startswith(_("Offline")):
        color = gajim.config.get('tooltip_status_offline_color')
    if color:
        status = formatted % (color, status)
    return status