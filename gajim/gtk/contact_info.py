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

from enum import IntEnum

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk

from nbxmpp.errors import StanzaError
from nbxmpp.structs import AnnotationNote
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.helpers import get_uf_affiliation
from gajim.common.helpers import get_uf_role
from gajim.common.helpers import get_uf_show
from gajim.common.i18n import _
from gajim.common.nec import EventHelper

from .dialogs import ConfirmationDialog
from .dialogs import DialogButton
from .sidebar_switcher import SideBarSwitcher
from .util import get_builder
from .util import connect_destroy
from .vcard_grid import VCardGrid

log = logging.getLogger('gajim.gui.contact_info')


class Column(IntEnum):
    IN_GROUP = 0
    GROUP_NAME = 1


class ContactInfo(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account, contact, page=None):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(700, 600)
        self.set_name('ContactInfo')
        self.set_title(_('Contact Information'))

        # Set account and jid for window management
        self.account = account
        self.contact = contact
        self._client = app.get_client(account)

        self._ui = get_builder('contact_info.ui')

        side_bar_switcher = SideBarSwitcher()
        side_bar_switcher.set_stack(self._ui.main_stack)
        self._ui.main_grid.attach(side_bar_switcher, 0, 0, 1, 1)
        self._ui.main_stack.connect('notify', self._on_stack_child_changed)

        self._ui.name_entry.set_text(contact.name)

        if contact.is_in_roster:
            self._ui.edit_name_button.show()
            self._fill_groups_page()
            if contact.is_transport:
                side_bar_switcher.hide_row('settings')
                side_bar_switcher.hide_row('devices')
            else:
                self._fill_settings_page()
        else:
            side_bar_switcher.hide_row('settings')
            side_bar_switcher.hide_row('groups')
            side_bar_switcher.hide_row('notes')
            if not contact.is_pm_contact:
                side_bar_switcher.hide_row('devices')

        if page is not None:
            # Jump to specific page if parameter is supplied
            side_bar_switcher.set_row(page)

        self._tasks = []

        # pylint: disable=line-too-long
        self.register_events([
            ('subscribed-presence-received', ged.GUI1, self._on_subscribed_presence_received),
            ('unsubscribed-presence-received', ged.GUI1, self._on_unsubscribed_presence_received),
        ])
        # pylint: enable=line-too-long

        self._load_avatar()

        self._ui.contact_name_label.set_text(contact.name)
        if contact.is_pm_contact:
            self._ui.role_label.set_text(get_uf_role(contact.role))
            self._ui.affiliation_label.set_text(
                get_uf_affiliation(contact.affiliation))
            self._ui.group_chat_grid.show()

        self._vcard_grid = VCardGrid(account)
        self._ui.vcard_box.add(self._vcard_grid)
        self._client.get_module('VCard4').request_vcard(
            jid=contact.jid,
            callback=self._on_vcard_received)

        self._update_timeout_id = None
        if contact.is_in_roster:
            self._devices = {}
            self._received_devices = set()
            self._received_times = set()
            self._devices_grid = DevicesGrid(self._ui.devices_grid)
            self._query_devices()

            self._time = 0
            self._update_timeout_id = GLib.timeout_add(100, self._update_timer)

        if contact.is_in_roster:
            note = self._client.get_module('Annotations').get_note(contact.jid)
            if note is not None:
                self._ui.textview_annotation.get_buffer().set_text(note.data)

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        connect_destroy(self._ui.tree_selection,
                        'changed',
                        self._on_group_selection_changed)
        connect_destroy(self._ui.toggle_renderer,
                        'toggled',
                        self._on_group_toggled)
        connect_destroy(self._ui.text_renderer,
                        'edited',
                        self._on_group_name_edited)

        self.add(self._ui.main_grid)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_stack_child_changed(self, *args):
        if self._ui.main_stack.get_visible_child_name() == 'information':
            self._ui.header_revealer.set_reveal_child(False)
        else:
            self._ui.header_revealer.set_reveal_child(True)

    def _on_destroy(self, _widget):
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        if self.contact.is_in_roster:
            self._save_annotation()

        if self._update_timeout_id is not None:
            GLib.source_remove(self._update_timeout_id)

        self.unregister_events()
        app.check_finalize(self)

    def _save_annotation(self):
        buffer_ = self._ui.textview_annotation.get_buffer()
        new_annotation = buffer_.get_property('text')
        note = self._client.get_module('Annotations').get_note(
            self.contact.jid)
        if note is None or new_annotation != note.data:
            new_note = AnnotationNote(
                jid=self.contact.jid, data=new_annotation)
            self._client.get_module('Annotations').set_note(new_note)

    def _update_timer(self):
        # Timeout for EntityTime in milliseconds, used to stop the spinner
        self._time += 100
        devices_complete = self._received_devices == set(self._devices.keys())
        times_complete = self._received_times == set(self._devices.keys())
        if devices_complete and times_complete or self._time == 10000:
            self._ui.devices_spinner.stop()
            self._update_timeout_id = None
            return False
        return True

    def _on_vcard_received(self, task):
        try:
            vcard = task.finish()
        except StanzaError as err:
            log.info('Error loading VCard: %s', err)
            vcard = VCard()

        self._vcard_grid.set_vcard(vcard)

    def _load_avatar(self):
        scale = self.get_scale_factor()
        surface_1 = self.contact.get_avatar(AvatarSize.VCARD,
                                            scale,
                                            add_show=False)
        surface_2 = self.contact.get_avatar(AvatarSize.VCARD_HEADER,
                                            scale,
                                            add_show=False)
        self._ui.avatar_image.set_from_surface(surface_1)
        self._ui.header_image.set_from_surface(surface_2)

    def _query_devices(self):
        if self.contact.is_pm_contact:
            self._query_device(self.contact)
        else:
            for contact in self.contact.iter_resources():
                self._query_device(contact)

    def _query_device(self, contact):
        self._devices[contact.jid.resource] = {
            'status': contact.show,
            'message': contact.status
        }
        self._rebuild_devices_grid()

        task = self._client.get_module('SoftwareVersion').request_software_version(
            contact.jid, callback=self._set_os_info, user_data=contact)
        self._tasks.append(task)

        task = self._client.get_module('EntityTime').request_entity_time(
            contact.jid, callback=self._set_entity_time, user_data=contact)
        self._tasks.append(task)

    def _set_os_info(self, task):
        self._tasks.remove(task)

        try:
            result = task.finish()
        except Exception as err:
            log.warning('Could not retrieve software version: %s', err)
            return

        contact = task.get_user_data()
        self._devices[contact.jid.resource]['client'] = '%s %s' % (
            result.name, result.version)
        if result.os is not None:
            self._devices[contact.jid.resource]['os'] = result.os
        self._received_devices.add(contact.jid.resource)
        self._rebuild_devices_grid()

    def _set_entity_time(self, task):
        self._tasks.remove(task)

        try:
            entity_time = task.finish()
        except Exception as err:
            log.warning('Could not retrieve entity time: %s', err)
            return

        contact = task.get_user_data()

        self._devices[contact.jid.resource]['time'] = entity_time
        self._received_times.add(contact.jid.resource)
        self._rebuild_devices_grid()

    def _rebuild_devices_grid(self):
        self._ui.devices_stack.set_visible_child_name('devices')
        self._devices_grid.clear()
        for key, client in self._devices.items():
            if not self.contact.is_pm_contact:
                self._devices_grid.add_header(_('Device "%s"') % key)

            if client.get('status'):
                self._devices_grid.add_value(
                    _('Status'), get_uf_show(client['status'].value))
            if client.get('message'):
                self._devices_grid.add_value(
                    _('Status Message'), client['message'])
            if client.get('client'):
                self._devices_grid.add_value(
                    _('Software'), client['client'])
            if client.get('os'):
                self._devices_grid.add_value(
                    _('Operating Sytem'), client['os'])
            if client.get('time'):
                self._devices_grid.add_value(
                    _('Local Time'), client['time'])
        self._ui.devices_grid.show_all()

    def _on_edit_name_toggled(self, widget):
        if widget.get_active():
            self._ui.name_entry.set_sensitive(True)
            self._ui.name_entry.grab_focus()
        else:
            self._ui.name_entry.set_sensitive(False)

        name = GLib.markup_escape_text(self._ui.name_entry.get_text())
        self._client.get_module('Roster').set_item(self.contact.jid, name)
        self._ui.contact_name_label.set_text(name)

    def _on_name_entry_activate(self, _widget, *args):
        self._ui.edit_name_button.set_active(False)

    def _on_from_subscription_switch_toggled(self, switch, state):
        def _stop_sharing():
            self._client.get_module('Presence').unsubscribed(self.contact.jid)
            switch.set_state(state)

        if state:
            self._client.get_module('Presence').subscribed(self.contact.jid)
            switch.set_state(state)
        else:
            ConfirmationDialog(
                _('Online Status'),
                _('Stop sharing online status?'),
                _('The contact will be informed that you stopped sharing your '
                  'status. Please note that this can have other side effects.'),
                [DialogButton.make('Cancel',
                                   callback=lambda: switch.set_active(True)),
                 DialogButton.make('Remove',
                                   text=_('_Stop Sharing'),
                                   callback=_stop_sharing)],
                transient_for=self).show()
        return Gdk.EVENT_STOP

    def _on_to_subscription_button_clicked(self, *args):
        # Save auto_auth if switch for disclosing presence is active
        self._client.get_module('Presence').subscribe(
            self.contact.jid,
            auto_auth=self._ui.from_subscription_switch.get_state())
        self._ui.request_stack.set_visible_child_name('requested')

    def _on_subscribed_presence_received(self, _event):
        self._ui.to_subscription_stack.set_visible_child_name('checkmark')

    def _on_unsubscribed_presence_received(self, _event):
        self._ui.to_subscription_stack.set_visible_child_name('request')
        self._ui.request_stack.set_visible_child_name('cross')

    def _fill_settings_page(self):
        if self.contact.subscription in ('from', 'both'):
            self._ui.from_subscription_switch.set_state(True)
        if self.contact.subscription in ('to', 'both'):
            self._ui.to_subscription_stack.set_visible_child_name('checkmark')
        elif self.contact.ask == 'subscribe':
            self._ui.to_subscription_stack.set_visible_child_name('request')
            self._ui.request_stack.set_visible_child_name('requested')
        else:
            self._ui.to_subscription_stack.set_visible_child_name('request')
            self._ui.request_stack.set_visible_child_name('cross')

    def _fill_groups_page(self):
        model = self._ui.groups_treeview.get_model()
        model.set_sort_column_id(Column.GROUP_NAME, Gtk.SortType.ASCENDING)
        groups = self._client.get_module('Roster').get_groups()
        for group in groups:
            is_in_group = group in self.contact.groups
            model.append([is_in_group, group])

    def _on_group_selection_changed(self, *args):
        selection = self._ui.groups_treeview.get_selection()
        (_model, iter_) = selection.get_selected()
        self._ui.group_remove_button.set_sensitive(bool(iter_))

    def _on_group_name_edited(self, _renderer, path, new_name):
        if new_name == '':
            return

        model = self._ui.groups_treeview.get_model()
        selected_iter_ = model.get_iter(path)
        old_name = model[selected_iter_][Column.GROUP_NAME]

        # Check if group already exists
        iter_ = model.get_iter_first()
        while iter_:
            if model.get_value(iter_, Column.GROUP_NAME) == new_name:
                return
            iter_ = model.iter_next(iter_)

        model.set_value(selected_iter_, Column.GROUP_NAME, new_name)
        self._client.get_module('Roster').rename_group(old_name, new_name)

    def _on_group_remove_button_clicked(self, *args):
        selection = self._ui.groups_treeview.get_selection()
        (model, iter_) = selection.get_selected()
        group = model[iter_][Column.GROUP_NAME]

        def _remove_group():
            self._client.get_module('Roster').remove_group(group)
            del model[iter_]

        ConfirmationDialog(
            _('Remove Group'),
            _('Remove Group'),
            _('Do you really want to remove "%s"?') % group,
            [DialogButton.make('Cancel'),
             DialogButton.make('Remove',
                               callback=_remove_group)],
            transient_for=self).show()
        return Gdk.EVENT_STOP

    def _on_group_toggled(self, _renderer, path):
        model = self._ui.groups_treeview.get_model()
        model[path][Column.IN_GROUP] = not model[path][Column.IN_GROUP]

        groups = set()
        iter_ = model.get_iter_first()
        while iter_:
            if model.get_value(iter_, Column.IN_GROUP):
                groups.add(model.get_value(iter_, Column.GROUP_NAME))
            iter_ = model.iter_next(iter_)

        self._client.get_module('Roster').set_groups(self.contact.jid, groups)

    def _on_group_add_button_clicked(self, *args):
        default_name = _('New Group')
        model = self._ui.groups_treeview.get_model()

        # Check if default_name group already exists
        iter_ = model.get_iter_first()
        while iter_:
            if model.get_value(iter_, Column.GROUP_NAME) == default_name:
                default_name += '_'
            iter_ = model.iter_next(iter_)

        new_iter_ = model.append([False, default_name])
        path = model.get_path(new_iter_)
        column = self._ui.groups_treeview.get_column(Column.GROUP_NAME)
        self._ui.groups_treeview.set_cursor(path, column, True)


class DevicesGrid:
    def __init__(self, grid):
        self._grid = grid
        self._row_num = 0

    def clear(self):
        row = 0
        while self._grid.get_child_at(0, row):
            self._grid.remove_row(row)
        self._row_num = 0

    def add_value(self, name, value):
        self._grid.insert_row(self._row_num)

        label = Gtk.Label(label=name)
        label.get_style_context().add_class('dim-label')
        label.set_valign(Gtk.Align.START)
        label.set_halign(Gtk.Align.END)
        label.set_margin_start(12)
        self._grid.attach(label, 0, self._row_num, 1, 1)

        label = Gtk.Label(label=value)
        label.set_valign(Gtk.Align.START)
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap(True)
        label.set_xalign(0)
        self._grid.attach(label, 1, self._row_num, 1, 1)
        self._row_num += 1

    def add_header(self, text):
        self._grid.insert_row(self._row_num)

        label = Gtk.Label(label=text)
        label.get_style_context().add_class('bold16')
        if self._row_num > 0:
            label.set_margin_top(12)
        label.set_halign(Gtk.Align.START)
        self._grid.attach(label, 0, self._row_num, 2, 1)
        self._row_num += 1
