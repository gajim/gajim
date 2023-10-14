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

from __future__ import annotations

import logging
import os
from datetime import datetime

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp import JID

from gajim.common import app
from gajim.common import helpers
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.file_props import FileProp
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import BareContact

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.builder import get_builder
from gajim.gtk.util import format_location
from gajim.gtk.util import format_tune

log = logging.getLogger('gajim.gtk.tooltips')


class GCTooltip:
    def __init__(self) -> None:
        self._contact = None

        self._ui = get_builder('groupchat_roster_tooltip.ui')

    def clear_tooltip(self) -> None:
        self._contact = None

    def get_tooltip(self,
                    contact: types.GroupchatParticipant
                    ) -> tuple[bool, Gtk.Grid]:

        if self._contact == contact:
            return True, self._ui.tooltip_grid

        self._populate_grid(contact)
        self._contact = contact
        return False, self._ui.tooltip_grid

    def _hide_grid_children(self) -> None:
        '''
        Hide all Elements of the Tooltip Grid
        '''
        for child in self._ui.tooltip_grid.get_children():
            child.hide()

    def _populate_grid(self, contact: types.GroupchatParticipant) -> None:
        '''
        Populate the Tooltip Grid with data of from the contact
        '''
        self._hide_grid_children()

        self._ui.nick.set_text(contact.name)
        self._ui.nick.show()

        # Status Message
        if contact.status:
            status = contact.status.strip()
            if status != '':
                self._ui.status.set_text(status)
                self._ui.status.show()

        # JID
        if contact.real_jid is not None:
            self._ui.jid.set_text(str(contact.real_jid.bare))
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
        scale = self._ui.tooltip_grid.get_scale_factor()
        surface = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._ui.avatar.set_from_surface(surface)
        self._ui.avatar.show()
        self._ui.fillelement.show()

        app.plugin_manager.extension_point(
            'gc_tooltip_populate', self, contact, self._ui.tooltip_grid)

    def destroy(self) -> None:
        self._ui.tooltip_grid.destroy()


class ContactTooltip:
    def __init__(self) -> None:
        self._contact = None
        self._ui = get_builder('contact_tooltip.ui')

    def clear_tooltip(self) -> None:
        self._contact = None
        for widget in self._ui.resources_box.get_children():
            widget.destroy()
        for widget in self._ui.tooltip_grid.get_children():
            widget.hide()

    def get_tooltip(self,
                    contact: types.BareContact) -> tuple[bool, Gtk.Grid]:
        if self._contact == contact:
            return True, self._ui.tooltip_grid

        self.clear_tooltip()
        self._populate_grid(contact)
        self._contact = contact
        return False, self._ui.tooltip_grid

    def _populate_grid(self, contact: types.BareContact) -> None:
        scale = self._ui.tooltip_grid.get_scale_factor()

        surface = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        assert not isinstance(surface, GdkPixbuf.Pixbuf)
        self._ui.avatar.set_from_surface(surface)
        self._ui.avatar.show()

        self._ui.name.set_markup(GLib.markup_escape_text(contact.name))
        self._ui.name.show()

        self._ui.jid.set_text(str(contact.jid))
        self._ui.jid.show()

        if contact.has_resources():
            for res in contact.iter_resources():
                self._add_resources(res)
        else:
            self._add_resources(contact)

        self._ui.resources_box.show_all()

        if contact.subscription and contact.subscription != 'both':
            # 'both' is the normal subscription value, just omit it
            self._ui.sub.set_text(helpers.get_uf_sub(contact.subscription))
            self._ui.sub.show()
            self._ui.sub_label.show()

        self._append_pep_info(contact)

        app.plugin_manager.extension_point(
            'roster_tooltip_populate', self, contact)

        # This sets the bottom-most widget to expand, in case the avatar
        # takes more space than the labels
        row_count = 1
        last_widget = self._ui.tooltip_grid.get_child_at(1, 1)
        assert last_widget is not None
        while row_count < 6:
            widget = self._ui.tooltip_grid.get_child_at(1, row_count)
            if widget and widget.get_visible():
                last_widget = widget
                row_count += 1
            else:
                break
        last_widget.set_vexpand(True)

    def _add_resources(
        self,
        contact: types.BareContact | types.ResourceContact
    ) -> None:

        resource_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        show_surface = get_show_circle(
            contact.show,
            AvatarSize.SHOW_CIRCLE,
            self._ui.tooltip_grid.get_scale_factor())
        show_image = Gtk.Image(
            surface=show_surface,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER)

        show_string = helpers.get_uf_show(contact.show.value)

        resource_string = ''
        if contact.jid.resource is not None:
            escaped_resource = GLib.markup_escape_text(contact.jid.resource)
            resource_string = f' ({escaped_resource})'

        resource_label = Gtk.Label(
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.START,
            label=f'{show_string}{resource_string}',
            max_width_chars=30,
            xalign=0,
        )

        base_box = Gtk.Box(spacing=6)
        base_box.add(show_image)
        base_box.add(resource_label)
        resource_box.add(base_box)

        if contact.status:
            status_text = GLib.markup_escape_text(contact.status)
            status_label = Gtk.Label(
                ellipsize=Pango.EllipsizeMode.END,
                halign=Gtk.Align.START,
                label=status_text,
                max_width_chars=30,
                xalign=0,
            )
            resource_box.add(status_label)

        if idle_datetime := contact.idle_datetime:
            current = datetime.now()
            if idle_datetime.date() == current.date():
                format_string = app.settings.get('time_format')
                formatted = idle_datetime.strftime(format_string)
            else:
                format_string = app.settings.get('date_time_format')
                formatted = idle_datetime.strftime(format_string)
            idle_text = _('Idle since: %s') % formatted
            idle_label = Gtk.Label(
                halign=Gtk.Align.START,
                label=idle_text,
                xalign=0,
            )
            resource_box.add(idle_label)

        app.plugin_manager.extension_point(
            'roster_tooltip_resource_populate',
            resource_box,
            contact)

        self._ui.resources_box.add(resource_box)

    def _append_pep_info(self, contact: types.BareContact) -> None:
        tune = contact.get_tune()
        if tune is not None:
            tune_str = format_tune(tune)
            self._ui.tune.set_markup(tune_str)
            self._ui.tune.show()
            self._ui.tune_label.show()

        location = contact.get_location()
        if location is not None:
            location_str = format_location(location)
            self._ui.location.set_markup(location_str)
            self._ui.location.show()
            self._ui.location_label.show()

    def destroy(self) -> None:
        self.clear_tooltip()


class FileTransfersTooltip:
    def __init__(self) -> None:
        self.sid = None
        self.widget = None
        if app.settings.get('use_kib_mib'):
            self.units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self.units = GLib.FormatSizeFlags.DEFAULT

    def clear_tooltip(self) -> None:
        self.sid = None
        self.widget = None

    def get_tooltip(self,
                    file_prop: FileProp,
                    sid: str
                    ) -> tuple[bool, Gtk.Widget]:
        if self.sid == sid:
            assert self.widget is not None
            return True, self.widget

        self.widget = self._create_tooltip(file_prop, sid)
        self.sid = sid
        return False, self.widget

    def _create_tooltip(self, file_prop: FileProp, _sid: str) -> Gtk.Grid:
        ft_grid = Gtk.Grid(row_spacing=6, column_spacing=12)
        ft_grid.insert_column(0)
        current_row = 0
        properties: list[tuple[str, str]] = []
        name = file_prop.name
        if file_prop.type_ == 'r':
            assert file_prop.file_name is not None
            file_name = os.path.split(file_prop.file_name)[1]
        else:
            assert file_prop.name is not None
            file_name = file_prop.name
        properties.append((_('File Name: '),
                           GLib.markup_escape_text(file_name)))

        assert file_prop.tt_account is not None
        client = app.get_client(file_prop.tt_account)
        if file_prop.type_ == 'r':
            type_ = p_('Noun', 'Download')
            actor = _('Sender: ')
            sender = JID.from_string(file_prop.sender)
            contact = client.get_module('Contacts').get_contact(sender.bare)
            assert isinstance(contact, BareContact)
            name = contact.name
        else:
            type_ = p_('Noun', 'Upload')
            actor = _('Recipient: ')
            receiver = JID.from_string(file_prop.receiver)
            contact = client.get_module('Contacts').get_contact(receiver.bare)
            assert isinstance(contact, BareContact)
            name = contact.name
        properties.append((p_('File transfer type', 'Type: '), type_))
        properties.append((actor, GLib.markup_escape_text(name)))

        transferred_len = file_prop.received_len
        if not transferred_len:
            transferred_len = 0
        properties.append((p_('File transfer state', 'Transferred: '),
                           GLib.format_size_full(transferred_len, self.units)))
        status = self._get_current_status(file_prop)
        properties.append((p_('File transfer state', 'Status: '), status))
        file_desc = file_prop.desc or ''
        properties.append((_('Description: '),
                           GLib.markup_escape_text(file_desc)))

        while properties:
            property_ = properties.pop(0)
            label = Gtk.Label(
                halign=Gtk.Align.END,
                label=property_[0],
                use_markup=True,
                valign=Gtk.Align.CENTER,
            )

            ft_grid.attach(label, 0, current_row, 1, 1)
            label = Gtk.Label(
                halign=Gtk.Align.START,
                label=property_[1],
                use_markup=True,
                valign=Gtk.Align.START,
                wrap=True,
            )
            ft_grid.attach(label, 1, current_row, 1, 1)
            current_row += 1

        ft_grid.show_all()
        return ft_grid

    @staticmethod
    def _get_current_status(file_prop: FileProp) -> str:
        if file_prop.stopped:
            return p_('File transfer state', 'Aborted')
        if file_prop.completed:
            return p_('File transfer state', 'Completed')
        if file_prop.paused:
            return p_('File transfer state', 'Paused')
        if file_prop.stalled:
            # stalled is not paused. it is like 'frozen' it stopped alone
            return p_('File transfer state', 'Stalled')

        if file_prop.connected:
            if file_prop.started:
                return p_('File transfer state', 'Transferring')
            return p_('File transfer state', 'Not started')
        return p_('File transfer state', 'Not started')
