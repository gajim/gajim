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

from typing import Optional
from typing import Union
from typing import cast

import logging
from enum import IntEnum


from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from nbxmpp.task import Task
from nbxmpp.errors import StanzaError
from nbxmpp.structs import AnnotationNote, SoftwareVersionResult
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import SubscribedPresenceReceived
from gajim.common.events import UnsubscribedPresenceReceived
from gajim.common.helpers import get_uf_affiliation
from gajim.common.helpers import get_uf_role
from gajim.common.helpers import get_uf_show
from gajim.common.i18n import _
from gajim.common.ged import EventHelper
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.modules.contacts import GroupchatParticipant

from .contact_settings import ContactSettings
from .dialogs import ConfirmationDialog
from .dialogs import DialogButton
from .sidebar_switcher import SideBarSwitcher
from .builder import get_builder
from .util import connect_destroy
from .vcard_grid import VCardGrid
from .structs import RemoveHistoryActionParams

log = logging.getLogger('gajim.gui.contact_info')


ContactT = Union[BareContact, GroupchatParticipant]


class Column(IntEnum):
    IN_GROUP = 0
    GROUP_NAME = 1


class ContactInfo(Gtk.ApplicationWindow, EventHelper):
    def __init__(self,
                 account: str,
                 contact: ContactT,
                 page: Optional[str] = None) -> None:

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

        self._tasks: list[Task] = []
        self._devices: dict[str, DeviceGrid] = {}

        self._switcher = SideBarSwitcher()
        self._switcher.set_stack(self._ui.main_stack, rows_visible=False)
        self._ui.main_grid.attach(self._switcher, 0, 0, 1, 1)
        self._ui.main_stack.connect('notify::visible-child-name',
                                    self._on_stack_child_changed)

        self._ui.name_entry.set_text(contact.name)
        if contact.is_in_roster:
            self._ui.edit_name_button.show()

        self._load_avatar()

        self._fill_information_page(self.contact)

        if isinstance(self.contact, BareContact):
            self._fill_settings_page(self.contact)
            self._fill_device_info(self.contact)
            self._fill_groups_page(self.contact)
            self._fill_note_page(self.contact)

        if page is not None:
            self._switcher.set_row(page)

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        # pylint: disable=line-too-long
        connect_destroy(self._ui.tree_selection, 'changed', self._on_group_selection_changed)
        connect_destroy(self._ui.toggle_renderer, 'toggled', self._on_group_toggled)
        connect_destroy(self._ui.text_renderer, 'edited', self._on_group_name_edited)

        self.register_events([
            ('subscribed-presence-received', ged.GUI1, self._on_subscribed_presence_received),
            ('unsubscribed-presence-received', ged.GUI1, self._on_unsubscribed_presence_received),
        ])
        # pylint: enable=line-too-long

        self.add(self._ui.main_grid)
        self.show_all()

    def _on_key_press(self, _widget: ContactInfo, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_stack_child_changed(self,
                                _widget: Gtk.Stack,
                                _pspec: GObject.ParamSpec) -> None:

        name = self._ui.main_stack.get_visible_child_name()
        self._ui.header_revealer.set_reveal_child(name != 'information')

    def _on_destroy(self, _widget: ContactInfo) -> None:
        for task in self._tasks:
            task.cancel()

        if self.contact.is_in_roster:
            self._save_annotation()

        for device_grid in self._devices.values():
            device_grid.destroy()
        self._devices.clear()

        self.unregister_events()
        app.check_finalize(self)

    def _fill_information_page(self, contact: ContactT) -> None:
        self._vcard_grid = VCardGrid(self.account)
        self._ui.vcard_box.add(self._vcard_grid)
        self._client.get_module('VCard4').request_vcard(
            jid=self.contact.jid,
            callback=self._on_vcard_received)

        jid = str(contact.get_address())

        self._ui.contact_name_label.set_text(contact.name)
        self._ui.contact_jid_label.set_text(jid)
        self._ui.contact_jid_label.set_tooltip_text(jid)

        if isinstance(contact, GroupchatParticipant):
            self._ui.role_label.set_text(get_uf_role(contact.role))
            self._ui.affiliation_label.set_text(
                get_uf_affiliation(contact.affiliation))
            self._ui.group_chat_grid.show()

        self._switcher.set_row_visible('information', True)

    def _fill_note_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster:
            return

        note = self._client.get_module('Annotations').get_note(contact.jid)
        if note is not None:
            self._ui.textview_annotation.get_buffer().set_text(note.data)

        if app.account_supports_private_storage(self.account):
            # Hide the Notes page if private storage is not available, because
            # roster notes cannot be stored without.
            # Since there is no disco mechanism for private storage, we rely on
            # Delimiter as a "proxy" for the availability of private storage.
            self._switcher.set_row_visible('notes', True)

    def _fill_settings_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster:
            return

        if contact.subscription in ('from', 'both'):
            self._ui.from_subscription_switch.set_state(True)

        if contact.subscription in ('to', 'both'):
            self._ui.to_subscription_stack.set_visible_child_name('checkmark')

        elif contact.ask == 'subscribe':
            self._ui.to_subscription_stack.set_visible_child_name('request')
            self._ui.request_stack.set_visible_child_name('requested')
        else:
            self._ui.to_subscription_stack.set_visible_child_name('request')
            self._ui.request_stack.set_visible_child_name('cross')

        self._switcher.set_row_visible('settings', True)
        contact_settings = ContactSettings(self.account, contact.jid)
        self._ui.contact_settings_box.add(contact_settings)

        params = RemoveHistoryActionParams(
            account=self.account, jid=self.contact.jid)
        self._ui.remove_history_button.set_action_name('app.remove-history')
        self._ui.remove_history_button.set_action_target_value(
            params.to_variant())

    def _fill_groups_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster:
            return

        model = self._ui.groups_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.set_sort_column_id(Column.GROUP_NAME, Gtk.SortType.ASCENDING)
        groups = self._client.get_module('Roster').get_groups()
        for group in groups:
            is_in_group = group in contact.groups
            model.append([is_in_group, group])

        self._switcher.set_row_visible('groups', True)

    def _fill_device_info(self, contact: BareContact) -> None:
        contacts = list(contact.iter_resources())
        if not contacts:
            return

        for resource_contact in contacts:
            device_grid = DeviceGrid(resource_contact)
            self._devices[resource_contact.resource] = device_grid
            self._ui.devices_box.add(device_grid.widget)
            self._query_device(resource_contact)

        self._ui.devices_stack.set_visible_child_name('devices')
        self._switcher.set_row_visible('devices', True)

    def _query_device(self, contact: ResourceContact) -> None:
        software_module = self._client.get_module('SoftwareVersion')
        task = software_module.request_software_version(
            contact.jid,
            callback=self._set_os_info,
            user_data=contact.resource)
        self._tasks.append(task)

        task = self._client.get_module('EntityTime').request_entity_time(
            contact.jid,
            callback=self._set_entity_time,
            user_data=contact.resource)
        self._tasks.append(task)

    def _on_vcard_received(self, task: Task) -> None:
        try:
            vcard = cast(VCard, task.finish())
        except StanzaError as err:
            log.info('Error loading VCard: %s', err)
            vcard = VCard()

        self._vcard_grid.set_vcard(vcard)

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        surface_1 = self.contact.get_avatar(AvatarSize.VCARD,
                                            scale,
                                            add_show=False)
        surface_2 = self.contact.get_avatar(AvatarSize.VCARD_HEADER,
                                            scale,
                                            add_show=False)
        assert not isinstance(surface_1, GdkPixbuf.Pixbuf)
        assert not isinstance(surface_2, GdkPixbuf.Pixbuf)
        self._ui.avatar_image.set_from_surface(surface_1)
        self._ui.header_image.set_from_surface(surface_2)

    def _set_os_info(self, task: Task) -> None:
        self._tasks.remove(task)

        try:
            result = cast(SoftwareVersionResult, task.finish())
        except Exception as err:
            log.warning('Could not retrieve software version: %s', err)
            result = None

        resource = task.get_user_data()
        device_grid = self._devices[resource]
        device_grid.set_software(result)

    def _set_entity_time(self, task: Task) -> None:
        self._tasks.remove(task)

        try:
            entity_time = cast(str, task.finish())
        except Exception as err:
            log.warning('Could not retrieve entity time: %s', err)
            entity_time = None

        resource = task.get_user_data()

        device_grid = self._devices[resource]
        device_grid.set_entity_time(entity_time)

    def _save_annotation(self) -> None:
        buffer_ = self._ui.textview_annotation.get_buffer()
        new_annotation = buffer_.get_property('text')
        note = self._client.get_module('Annotations').get_note(
            self.contact.jid)
        if note is None or new_annotation != note.data:
            new_note = AnnotationNote(
                jid=self.contact.jid, data=new_annotation)
            self._client.get_module('Annotations').set_note(new_note)

    def _on_edit_name_toggled(self, widget: Gtk.ToggleButton) -> None:
        active = widget.get_active()
        self._ui.name_entry.set_sensitive(active)
        if active:
            self._ui.name_entry.grab_focus()

        name = self._ui.name_entry.get_text()
        self._client.get_module('Roster').set_item(self.contact.jid, name)
        self._ui.contact_name_label.set_text(name)

    def _on_name_entry_activate(self, _widget: Gtk.Entry) -> None:
        self._ui.edit_name_button.set_active(False)

    def _on_from_subscription_switch_toggled(self,
                                             switch: Gtk.Switch,
                                             state: bool) -> int:
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

    def _on_to_subscription_button_clicked(self, _widget: Gtk.Button) -> None:
        # Save auto_auth if switch for disclosing presence is active
        self._client.get_module('Presence').subscribe(
            self.contact.jid,
            auto_auth=self._ui.from_subscription_switch.get_state())
        self._ui.request_stack.set_visible_child_name('requested')

    def _on_subscribed_presence_received(self,
                                         _event: SubscribedPresenceReceived
                                         ) -> None:

        self._ui.to_subscription_stack.set_visible_child_name('checkmark')

    def _on_unsubscribed_presence_received(self,
                                           _event: UnsubscribedPresenceReceived
                                           ) -> None:

        self._ui.to_subscription_stack.set_visible_child_name('request')
        self._ui.request_stack.set_visible_child_name('cross')

    def _on_group_selection_changed(self, _widget: Gtk.TreeSelection) -> None:
        selection = self._ui.groups_treeview.get_selection()
        (_model, iter_) = selection.get_selected()
        self._ui.group_remove_button.set_sensitive(bool(iter_))

    def _on_group_name_edited(self,
                              _renderer: Gtk.CellRendererText,
                              path: str,
                              new_name: str) -> None:
        if new_name == '':
            return

        model = self._ui.groups_treeview.get_model()
        assert model is not None
        assert isinstance(model, Gtk.ListStore)
        selected_iter_ = model.get_iter(path)
        old_name = model[selected_iter_][Column.GROUP_NAME]

        # Check if group already exists
        iter_ = model.get_iter_first()
        while iter_:
            group_name = model.get_value(iter_, Column.GROUP_NAME)
            if group_name == new_name:
                return
            iter_ = model.iter_next(iter_)

        model.set_value(selected_iter_, Column.GROUP_NAME, new_name)
        self._client.get_module('Roster').rename_group(old_name, new_name)

    def _on_group_remove_button_clicked(self, _widget: Gtk.Button) -> int:
        selection = self._ui.groups_treeview.get_selection()
        model, iter_ = selection.get_selected()
        assert iter_ is not None
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

    def _on_group_toggled(self,
                          _renderer: Gtk.CellRendererToggle,
                          path: str) -> None:

        model = self._ui.groups_treeview.get_model()
        assert model is not None
        model[path][Column.IN_GROUP] = not model[path][Column.IN_GROUP]

        groups: set[str] = set()
        iter_ = model.get_iter_first()
        while iter_:
            if model.get_value(iter_, Column.IN_GROUP):
                group_name = model.get_value(iter_, Column.GROUP_NAME)
                groups.add(group_name)
            iter_ = model.iter_next(iter_)

        self._client.get_module('Roster').set_groups(self.contact.jid, groups)

    def _on_group_add_button_clicked(self, _widget: Gtk.Button) -> None:
        default_name = _('New Group')
        model = self._ui.groups_treeview.get_model()
        assert model is not None
        assert isinstance(model, Gtk.ListStore)

        # Check if default_name group already exists
        iter_ = model.get_iter_first()
        while iter_:
            group_name = model.get_value(iter_, Column.GROUP_NAME)
            if group_name == default_name:
                default_name += '_'
            iter_ = model.iter_next(iter_)

        new_iter_ = model.append([False, default_name])
        path = model.get_path(new_iter_)
        column = self._ui.groups_treeview.get_column(Column.GROUP_NAME)
        self._ui.groups_treeview.set_cursor(path, column, True)


class DeviceGrid:
    def __init__(self, contact: ResourceContact) -> None:
        self._contact = contact
        self._ui = get_builder('contact_info.ui', ['devices_grid'])
        self._spinner = Gtk.Spinner()
        self._spinner.start()

        self._ui.resource_label.set_text(_('Device "%s"') % contact.resource)
        self._ui.status_value.set_text(get_uf_show(contact.show.value))

        self._ui.priority_value.set_text(str(self._contact.priority))
        self._ui.priority_value.show()
        self._ui.priority_label.show()

        self._ui.resource_box.add(self._spinner)
        self._ui.devices_grid.show_all()

        self._waiting_for_info = 2

    @property
    def widget(self) -> Gtk.Grid:
        return self._ui.devices_grid

    def set_entity_time(self, entity_time: Optional[str]) -> None:
        if entity_time is not None:
            self._ui.time_value.set_text(entity_time)
            self._ui.time_value.show()
            self._ui.time_label.show()

        self._check_complete()

    def set_software(self, software: Optional[SoftwareVersionResult]) -> None:
        if software is not None:
            software_string = f'{software.name} {software.version}'
            self._ui.software_value.set_text(software_string)
            self._ui.software_value.show()
            self._ui.software_label.show()
            if software.os is not None:
                self._ui.system_value.set_text(software.os)
                self._ui.system_value.show()
                self._ui.system_label.show()

        self._check_complete()

    def _check_complete(self) -> None:
        self._waiting_for_info -= 1
        if not self._waiting_for_info:
            self._spinner.stop()

    def destroy(self) -> None:
        self._spinner.stop()
        del self._spinner
        del self._ui
        del self._contact
