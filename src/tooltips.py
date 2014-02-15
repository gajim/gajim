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
import locale
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
        self.win = Gtk.Window(Gtk.WindowType.POPUP)
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
        self.hide_tooltip()

    def on_size_allocate(self, widget, rect):
        half_width = rect.width / 2 + 1
        if self.preferred_position[1] + rect.height > self.screen.get_height():
             # flip tooltip up
            self.preferred_position[1] -= rect.height + self.widget_height + 8
            if self.preferred_position[1] < 0:
                self.preferred_position[1] = self.screen.get_height() - \
                    rect.height - 2

                if self.preferred_position[0] + rect.width + 7 < \
                self.screen.get_width():
                    self.preferred_position[0] = self.preferred_position[0] + 7
                else:
                    self.preferred_position[0] = self.preferred_position[0] - \
                        rect.width - 7
                self.win.move(self.preferred_position[0],
                    self.preferred_position[1])
                return
        if self.preferred_position[0] < half_width:
            self.preferred_position[0] = 0
        elif self.preferred_position[0] + rect.width > \
        self.screen.get_width() + half_width:
            self.preferred_position[0] = self.screen.get_width() - rect.width
        elif not self.check_last_time:
            self.preferred_position[0] -= half_width
        self.win.move(self.preferred_position[0], self.preferred_position[1])

    def show_tooltip(self, data, widget_height, widget_y_position):
        """
        Show tooltip on widget

        Data contains needed data for tooltip contents.
        widget_height is the height of the widget on which we show the tooltip.
        widget_y_position is vertical position of the widget on the screen.
        """
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

    @staticmethod
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

class StatusTable:
    """
    Contains methods for creating status table. This is used in Roster and
    NotificationArea tooltips
    """

    def __init__(self):
        self.current_row = 1
        self.table = None
        self.text_label = None
        self.spacer_label = '   '

    def create_table(self):
        self.table = Gtk.Grid()
        self.table.insert_row(0)
        self.table.insert_row(0)
        self.table.insert_column(0)
        self.table.set_property('column-spacing', 2)

    def add_text_row(self, text, col_inc = 0):
        self.current_row += 1
        self.text_label = Gtk.Label()
        self.text_label.set_line_wrap(True)
        self.text_label.set_alignment(0, 0)
        self.text_label.set_selectable(False)
        self.text_label.set_markup(text)
        self.table.attach(self.text_label, 1 + col_inc, self.current_row,
            3 - col_inc, 1)

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
        self.table.insert_row(0)
        self.table.insert_row(0)
        self.current_row += 1
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
        image.set_alignment(1, 0.5)
        if indent:
            self.table.attach(spacer, 1, self.current_row, 1, 1)
        self.table.attach(image, 2, self.current_row, 1, 1)
        status_label = Gtk.Label()
        status_label.set_markup(str_status)
        status_label.set_alignment(0, 0)
        status_label.set_line_wrap(True)
        self.table.attach(status_label, 3, self.current_row, 1, 1)
        if show_lock:
            lock_image = Gtk.Image()
            lock_image.set_from_stock(Gtk.STOCK_DIALOG_AUTHENTICATION,
                Gtk.IconSize.MENU)
            self.table.attach(lock_image, 4, self.current_row, 1, 1)

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

class GCTooltip(BaseTooltip):
    """
    Tooltip that is shown in the GC treeview
    """

    def __init__(self):
        self.account = None
        self.text_label = Gtk.Label()
        self.text_label.set_line_wrap(True)
        self.text_label.set_alignment(0, 0)
        self.text_label.set_selectable(False)
        self.avatar_image = Gtk.Image()

        BaseTooltip.__init__(self)

    def populate(self, contact):
        if not contact:
            return
        self.create_window()
        vcard_table = Gtk.Grid()
        vcard_table.insert_row(0)
        vcard_table.insert_row(0)
        vcard_table.insert_row(0)
        vcard_table.insert_column(0)
        vcard_table.set_property('column-spacing', 2)
        vcard_current_row = 1
        properties = []

        nick_markup = '<b>' + GLib.markup_escape_text(contact.get_shown_name())\
            + '</b>'
        properties.append((nick_markup, None))

        if contact.status: # status message
            status = contact.status.strip()
            if status != '':
                # escape markup entities
                status = helpers.reduce_chars_newlines(status, 300, 5)
                status = '<i>' + GLib.markup_escape_text(status) + '</i>'
                properties.append((status, None))

        show = helpers.get_uf_show(contact.show)
        show = self.colorize_status(show)
        properties.append((show, None))

        if contact.jid.strip():
            properties.append((_('Jabber ID: '), '\u200E' + "<b>%s</b>" % \
                contact.jid))

        if hasattr(contact, 'resource') and contact.resource.strip():
            properties.append((_('Resource: '), GLib.markup_escape_text(
                contact.resource)))

        if contact.affiliation != 'none':
            uf_affiliation = helpers.get_uf_affiliation(contact.affiliation)
            uf_affiliation = \
                _('%(owner_or_admin_or_member)s of this group chat') % \
                {'owner_or_admin_or_member': uf_affiliation}
            uf_affiliation = self.colorize_affiliation(uf_affiliation)
            properties.append((uf_affiliation, None))

        # Add avatar
        puny_name = helpers.sanitize_filename(contact.name)
        puny_room = helpers.sanitize_filename(contact.room_jid)
        file_ = helpers.get_avatar_path(os.path.join(gajim.AVATAR_PATH,
            puny_room, puny_name))
        if file_:
            self.avatar_image.set_from_file(file_)
            pix = self.avatar_image.get_pixbuf()
            pix = gtkgui_helpers.get_scaled_pixbuf(pix, 'tooltip')
            self.avatar_image.set_from_pixbuf(pix)
        else:
            self.avatar_image.set_from_pixbuf(None)
        while properties:
            property_ = properties.pop(0)
            vcard_current_row += 1
            label = Gtk.Label()
            if not properties:
                label.set_vexpand(True)
            label.set_alignment(0, 0)
            if property_[1]:
                label.set_markup(property_[0])
                vcard_table.attach(label, 1, vcard_current_row, 1, 1)
                label = Gtk.Label()
                if not properties:
                    label.set_vexpand(True)
                label.set_alignment(0, 0)
                label.set_markup(property_[1])
                label.set_line_wrap(True)
                vcard_table.attach(label, 2, vcard_current_row, 1, 1)
            else:
                label.set_markup(property_[0])
                label.set_line_wrap(True)
                vcard_table.attach(label, 1, vcard_current_row, 2, 1)

        self.avatar_image.set_alignment(0, 0)
        vcard_table.attach(self.avatar_image, 3, 2, 1, vcard_current_row - 1)
        gajim.plugin_manager.gui_extension_point('gc_tooltip_populate',
            self, contact, vcard_table)
        self.win.add(vcard_table)

class RosterTooltip(NotificationAreaTooltip):
    """
    Tooltip that is shown in the roster treeview
    """

    def __init__(self):
        self.account = None
        self.image = Gtk.Image()
        self.image.set_alignment(0, 0)
        # padding is independent of the total length and better than alignment
        self.image.set_padding(1, 2)
        self.avatar_image = Gtk.Image()
        NotificationAreaTooltip.__init__(self)

    def populate(self, contacts):
        self.create_window()

        self.create_table()
        if not contacts or len(contacts) == 0:
            # Tooltip for merged accounts row
            accounts = helpers.get_notification_icon_tooltip_dict()
            self.spacer_label = ''
            self.fill_table_with_accounts(accounts)
            self.win.add(self.table)
            return

        # primary contact
        prim_contact = gajim.contacts.get_highest_prio_contact_from_contacts(
            contacts)

        puny_jid = helpers.sanitize_filename(prim_contact.jid)
        table_size = 3

        file_ = helpers.get_avatar_path(os.path.join(gajim.AVATAR_PATH,
            puny_jid))
        if file_:
            self.avatar_image.set_from_file(file_)
            pix = self.avatar_image.get_pixbuf()
            pix = gtkgui_helpers.get_scaled_pixbuf(pix, 'tooltip')
            self.avatar_image.set_from_pixbuf(pix)
            table_size = 4
        else:
            self.avatar_image.set_from_pixbuf(None)
        vcard_table = Gtk.Grid()
        vcard_table.insert_row(0)
        for i in range(0, table_size):
            vcard_table.insert_column(0)
        vcard_table.set_property('column-spacing', 2)
        vcard_current_row = 1
        properties = []

        name_markup = '<span weight="bold">' + GLib.markup_escape_text(
            prim_contact.get_shown_name()) + '</span>'
        if gajim.config.get('mergeaccounts'):
            name_markup += " <span foreground='%s'>(%s)</span>" % (
                gajim.config.get('tooltip_account_name_color'),
                GLib.markup_escape_text(prim_contact.account.name))

        if self.account and helpers.jid_is_blocked(self.account,
        prim_contact.jid):
            name_markup += _(' [blocked]')
        if self.account and \
        self.account in gajim.interface.minimized_controls and \
        prim_contact.jid in gajim.interface.minimized_controls[self.account]:
            name_markup += _(' [minimized]')
        properties.append((name_markup, None))

        num_resources = 0
        # put contacts in dict, where key is priority
        contacts_dict = {}
        for contact in contacts:
            if contact.resource:
                num_resources += 1
                if contact.priority in contacts_dict:
                    contacts_dict[int(contact.priority)].append(contact)
                else:
                    contacts_dict[int(contact.priority)] = [contact]

        if num_resources > 1:
            properties.append((_('Status: '),       ' '))
            transport = gajim.get_transport_name_from_jid(prim_contact.jid)
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
                    status_line = self.get_status_info(acontact.resource,
                        acontact.priority, acontact.show, acontact.status)

                    icon_name = self._get_icon_name_for_tooltip(acontact)
                    self.add_status_row(file_path, icon_name, status_line,
                        acontact.last_status_time)
            properties.append((self.table,  None))

        else: # only one resource
            if contact.show:
                show = helpers.get_uf_show(contact.show)
                if not self.check_last_time and self.account:
                    if contact.show == 'offline':
                        if not contact.last_status_time:
                            gajim.connections[self.account].\
                                request_last_status_time(contact.jid, '')
                        else:
                            self.check_last_time = contact.last_status_time
                    elif contact.resource:
                        gajim.connections[self.account].\
                            request_last_status_time(
                            contact.jid, contact.resource)
                        if contact.last_activity_time:
                            self.check_last_time = contact.last_activity_time
                else:
                    self.check_last_time = None
                if contact.last_status_time:
                    vcard_current_row += 1
                    if contact.show == 'offline':
                        text = ' - ' + _('Last status: %s')
                    else:
                        text = _(' since %s')

                    if time.strftime('%j', time.localtime()) == \
                        time.strftime('%j', contact.last_status_time):
                        # it's today, show only the locale hour representation
                        local_time = time.strftime('%X',
                            contact.last_status_time)
                    else:
                        # time.strftime returns locale encoded string
                        local_time = time.strftime('%c',
                            contact.last_status_time)

                    text = text % local_time
                    show += text
                if self.account and \
                prim_contact.jid in gajim.gc_connected[self.account]:
                    if gajim.gc_connected[self.account][prim_contact.jid]:
                        show = _('Connected')
                    else:
                        show = _('Disconnected')
                show = self.colorize_status(show)

                if contact.status:
                    status = contact.status.strip()
                    if status:
                        # reduce long status
                        # (no more than 300 chars on line and no more than
                        # 5 lines)
                        # status is wrapped
                        status = helpers.reduce_chars_newlines(status, 300, 5)
                        # escape markup entities.
                        status = GLib.markup_escape_text(status)
                        properties.append(('<i>%s</i>' % status, None))
                properties.append((show, None))

        self._append_pep_info(contact, properties)

        properties.append((_('Jabber ID: '), '\u200E' + "<b>%s</b>" % \
            prim_contact.jid))

        # contact has only one ressource
        if num_resources == 1 and contact.resource:
            properties.append((_('Resource: '), GLib.markup_escape_text(
                contact.resource) + ' (' + str(contact.priority) + ')'))

        if self.account and prim_contact.sub and prim_contact.sub != 'both' and\
        prim_contact.jid not in gajim.gc_connected[self.account]:
            # ('both' is the normal sub so we don't show it)
            properties.append(( _('Subscription: '), GLib.markup_escape_text(
                helpers.get_uf_sub(prim_contact.sub))))

        if prim_contact.keyID:
            keyID = None
            if len(prim_contact.keyID) == 8:
                keyID = prim_contact.keyID
            elif len(prim_contact.keyID) == 16:
                keyID = prim_contact.keyID[8:]
            if keyID:
                properties.append((_('OpenPGP: '), GLib.markup_escape_text(
                    keyID)))

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
                cs = "<span foreground='%s'>" % gajim.config.get(
                    'tooltip_idle_color')
                cs += '%s</span>'
                properties.append((str(), None))
                idle_since = cs % _("Idle since %s")
                properties.append((idle_since % formatted, None))
                idle_for = cs % _("Idle for %s")
                properties.append((idle_for % str(diff), None))

        while properties:
            property_ = properties.pop(0)
            vcard_current_row += 1
            label = Gtk.Label()
            if not properties and table_size == 4:
                label.set_vexpand(True)
            label.set_alignment(0, 0)
            if property_[1]:
                label.set_markup(property_[0])
                vcard_table.attach(label, 1, vcard_current_row, 1, 1)
                label = Gtk.Label()
                if not properties and table_size == 4:
                    label.set_vexpand(True)
                label.set_alignment(0, 0)
                label.set_markup(property_[1])
                label.set_line_wrap(True)
                vcard_table.attach(label, 2, vcard_current_row, 1, 1)
            else:
                if isinstance(property_[0], str):
                    label.set_markup(property_[0])
                    label.set_line_wrap(True)
                else:
                    label = property_[0]
                vcard_table.attach(label, 1, vcard_current_row, 2, 1)
        self.avatar_image.set_alignment(0, 0)
        if table_size == 4:
            vcard_table.attach(self.avatar_image, 3, 2, 1, vcard_current_row - 1)

        gajim.plugin_manager.gui_extension_point('roster_tooltip_populate',
            self, contacts, vcard_table)
        self.win.add(vcard_table)

    def update_last_time(self, last_time):
        if not self.check_last_time or time.strftime('%x %I:%M %p', last_time) !=\
        time.strftime('%x %I:%M %p', self.check_last_time):
            self.win.destroy()
            self.win = None
            self.populate(self.cur_data)
            self.win.show_all()

    def _append_pep_info(self, contact, properties):
        """
        Append Tune, Mood, Activity, Location information of the specified contact
        to the given property list.
        """
        if 'mood' in contact.pep:
            mood = contact.pep['mood'].asMarkupText()
            properties.append((_('Mood: '), "%s" % mood, None))

        if 'activity' in contact.pep:
            activity = contact.pep['activity'].asMarkupText()
            properties.append((_('Activity: '), "%s" % activity, None))

        if 'tune' in contact.pep:
            tune = contact.pep['tune'].asMarkupText()
            properties.append((_('Tune: '), "%s" % tune, None))

        if 'location' in contact.pep:
            location = contact.pep['location'].asMarkupText()
            properties.append((_('Location: '), "%s" % location, None))


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
            type_ = _('Download')
            actor = _('Sender: ')
            sender = file_props.sender.split('/')[0]
            name = gajim.contacts.get_first_contact_from_jid(
                    file_props.tt_account, sender).get_shown_name()
        else:
            type_ = _('Upload')
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
            label.set_alignment(0, 0)
            label.set_markup(property_[0])
            ft_table.attach(label, 1, 2, current_row, current_row + 1,
                    Gtk.AttachOptions.FILL, Gtk.AttachOptions.FILL, 0, 0)
            label = Gtk.Label()
            label.set_alignment(0, 0)
            label.set_line_wrap(True)
            label.set_markup(property_[1])
            ft_table.attach(label, 2, 3, current_row, current_row + 1,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, Gtk.AttachOptions.FILL, 0, 0)

        self.win.add(ft_table)


class ServiceDiscoveryTooltip(BaseTooltip):
    """
    Tooltip that is shown when hovering over a service discovery row
    """
    def populate(self, status):
        self.create_window()
        label = Gtk.Label()
        label.set_line_wrap(True)
        label.set_alignment(0, 0)
        label.set_selectable(False)
        if status == 1:
            label.set_text(
                    _('This service has not yet responded with detailed information'))
        elif status == 2:
            label.set_text(
                    _('This service could not respond with detailed information.\n'
                    'It is most likely legacy or broken'))
        self.win.add(label)
