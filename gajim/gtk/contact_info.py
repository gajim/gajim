# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import logging
from enum import IntEnum

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import AnnotationNote
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.events import SubscribedPresenceReceived
from gajim.common.events import UnsubscribedPresenceReceived
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.status import get_uf_show
from gajim.common.util.user_strings import get_uf_affiliation
from gajim.common.util.user_strings import get_uf_role

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import CancelDialogResponse
from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import DialogResponse
from gajim.gtk.builder import get_builder
from gajim.gtk.contact_name_widget import ContactNameWidget
from gajim.gtk.contact_settings import ContactSettings
from gajim.gtk.omemo_trust_manager import OMEMOTrustManager
from gajim.gtk.sidebar_switcher import SideBarSwitcher
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.vcard_grid import VCardGrid
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.contact_info")


ContactT = BareContact | GroupchatParticipant


class Column(IntEnum):
    IN_GROUP = 0
    GROUP_NAME = 1


class ContactInfo(GajimAppWindow, EventHelper):
    def __init__(
        self, account: str, contact: ContactT, page: str | None = None
    ) -> None:

        GajimAppWindow.__init__(
            self,
            name="ContactInfo",
            title=_("Contact Information"),
            default_width=700,
            default_height=600,
            add_window_padding=False,
            header_bar=False,
        )

        EventHelper.__init__(self)

        # Set account and jid for window management
        self.account = account
        self.contact = contact
        self._client = app.get_client(account)
        self._client.connect_signal("state-changed", self._on_client_state_changed)

        self._ui = get_builder("contact_info.ui")

        self._tasks: list[Task] = []
        self._devices: dict[str, DeviceInfo] = {}

        self._switcher = SideBarSwitcher()

        toolbar = Adw.ToolbarView(content=self._switcher)
        toolbar.add_top_bar(Adw.HeaderBar())

        self._sidebar_page = Adw.NavigationPage(
            title=self.contact.name, tag="sidebar", child=toolbar
        )

        toolbar = Adw.ToolbarView(content=self._ui.main_stack)
        toolbar.add_top_bar(Adw.HeaderBar())

        content_page = Adw.NavigationPage(title=" ", tag="content", child=toolbar)

        nav = Adw.NavigationSplitView(sidebar=self._sidebar_page, content=content_page)

        self.set_child(nav)

        self._switcher.set_stack(self._ui.main_stack, rows_visible=False)

        self._load_avatar()

        self._contact_name_widget = ContactNameWidget(
            contact=self.contact, edit_mode=True
        )

        self._connect(
            self._contact_name_widget, "name-updated", self._on_contact_name_updated
        )
        self._ui.contact_name_controls_box.append(self._contact_name_widget)

        self._fill_information_page(self.contact)

        if isinstance(self.contact, BareContact):
            self._fill_settings_page(self.contact)
            self._fill_encryption_page(self.contact)
            self._fill_device_info(self.contact)
            self._fill_groups_page(self.contact)
            self._fill_note_page(self.contact)

        if page is not None:
            self._switcher.set_row(page)

        self._connect(
            self._ui.tree_selection, "changed", self._on_group_selection_changed
        )
        self._connect(self._ui.toggle_renderer, "toggled", self._on_group_toggled)
        self._connect(self._ui.text_renderer, "edited", self._on_group_name_edited)

        self._connect(
            self._ui.from_subscription_switch,
            "state-set",
            self._on_from_subscription_switch_toggled,
        )
        self._connect(
            self._ui.to_subscription_button,
            "clicked",
            self._on_to_subscription_button_clicked,
        )
        self._connect(
            self._ui.group_add_button, "clicked", self._on_group_add_button_clicked
        )
        self._connect(
            self._ui.group_remove_button,
            "clicked",
            self._on_group_remove_button_clicked,
        )

        self.register_events(
            [
                (
                    "subscribed-presence-received",
                    ged.GUI1,
                    self._on_subscribed_presence_received,
                ),
                (
                    "unsubscribed-presence-received",
                    ged.GUI1,
                    self._on_unsubscribed_presence_received,
                ),
            ]
        )

    def _cleanup(self) -> None:
        for task in self._tasks:
            task.cancel()

        if self.contact.is_in_roster and self._client.state.is_available:
            self._save_annotation()

        for device_grid in self._devices.values():
            self._ui.devices_page.remove(device_grid)
        self._devices.clear()

        del self._switcher
        del self._contact_name_widget

        self._client.disconnect_all_from_obj(self)
        self._disconnect_all()
        self.unregister_events()
        app.check_finalize(self)

    def _on_client_state_changed(
        self, _client: types.Client, _signal_name: str, state: SimpleClientState
    ) -> None:
        self._ui.subscription_listbox.set_sensitive(state.is_connected)

        if state.is_connected:
            self._ui.groups_page_stack.set_visible_child_name("groups")
            self._ui.notes_page_stack.set_visible_child_name("notes")
        else:
            self._ui.groups_page_stack.set_visible_child_name("offline")
            self._ui.notes_page_stack.set_visible_child_name("offline")

    def _on_contact_name_updated(self, _widget: ContactNameWidget, name: str) -> None:
        self._sidebar_page.set_title(name)

    def _fill_information_page(self, contact: ContactT) -> None:
        self._vcard_grid = VCardGrid(self.account)
        self._ui.vcard_box.append(self._vcard_grid)
        if self._client.state.is_available:
            self._client.get_module("VCard4").request_vcard(
                jid=self.contact.jid, callback=self._on_vcard_received
            )

        jid = str(contact.get_address())

        self._ui.contact_jid_label.set_text(jid)
        self._ui.contact_jid_label.set_tooltip_text(jid)

        if isinstance(contact, GroupchatParticipant):
            self._ui.role_label.set_text(get_uf_role(contact.role))
            self._ui.affiliation_label.set_text(get_uf_affiliation(contact.affiliation))
            self._ui.group_chat_grid.set_visible(True)

        self._switcher.set_row_visible("information", True)

    def _fill_encryption_page(self, contact: ContactT) -> None:
        self._ui.encryption_box.append(
            OMEMOTrustManager(self.contact.account, self.contact)
        )
        self._switcher.set_row_visible("encryption-omemo", True)

    def _fill_note_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster:
            return

        note = self._client.get_module("Annotations").get_note(contact.jid)
        if note is not None:
            self._ui.textview_annotation.get_buffer().set_text(note.data)

        server_disco = self._client.get_module("Discovery").server_info
        if server_disco is not None and server_disco.supports(Namespace.PRIVATE):
            # Hide the Notes page if private storage is not available, because
            # roster notes cannot be stored without.
            # Since there is no disco mechanism for private storage, we rely on
            # Delimiter as a "proxy" for the availability of private storage.
            self._switcher.set_row_visible("notes", True)

    def _fill_settings_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster:
            return

        self._ui.from_subscription_switch.set_state(contact.is_subscribed)

        self._ui.subscription_listbox.set_sensitive(self._client.state.is_available)

        if contact.subscription in ("to", "both"):
            self._ui.to_subscription_stack.set_visible_child_name("checkmark")

        elif contact.ask == "subscribe":
            self._ui.to_subscription_stack.set_visible_child_name("request")
            self._ui.request_stack.set_visible_child_name("requested")
        else:
            self._ui.to_subscription_stack.set_visible_child_name("request")
            self._ui.request_stack.set_visible_child_name("cross")

        self._switcher.set_row_visible("settings", True)
        contact_settings = ContactSettings(self.account, contact.jid)
        self._ui.contact_settings_box.add(contact_settings)

        params = AccountJidParam(account=self.account, jid=self.contact.jid)
        self._ui.remove_history_button.set_action_target_value(params.to_variant())
        self._ui.remove_history_button.set_action_name("app.remove-history")

    def _fill_groups_page(self, contact: BareContact) -> None:
        if not contact.is_in_roster or not self._client.state.is_available:
            return

        model = self._ui.groups_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.set_sort_column_id(Column.GROUP_NAME, Gtk.SortType.ASCENDING)
        groups = self._client.get_module("Roster").get_groups()
        for group in groups:
            is_in_group = group in contact.groups
            model.append([is_in_group, group])

        self._switcher.set_row_visible("groups", True)

    def _fill_device_info(self, contact: BareContact) -> None:
        contacts = list(contact.iter_resources())
        if not contacts:
            return

        for resource_contact in contacts:
            device_grid = DeviceInfo(resource_contact)
            self._devices[resource_contact.resource] = device_grid
            self._ui.devices_page.add(device_grid)
            self._query_device(resource_contact)

        self._ui.devices_stack.set_visible_child_name("devices")
        self._switcher.set_row_visible("devices", True)

    def _query_device(self, contact: ResourceContact) -> None:
        software_module = self._client.get_module("SoftwareVersion")
        task = software_module.request_software_version(
            contact.jid, callback=self._set_os_info, user_data=contact.resource
        )
        self._tasks.append(task)

        task = self._client.get_module("EntityTime").request_entity_time(
            contact.jid, callback=self._set_entity_time, user_data=contact.resource
        )
        self._tasks.append(task)

    def _on_vcard_received(self, task: Task) -> None:
        try:
            vcard = cast(VCard | None, task.finish())
        except StanzaError as err:
            log.info("Error loading VCard: %s", err)
            vcard = None

        if vcard is None:
            vcard = VCard()

        self._vcard_grid.set_vcard(vcard)

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        texture1 = self.contact.get_avatar(AvatarSize.VCARD, scale, add_show=False)

        self._ui.avatar_image.set_pixel_size(AvatarSize.VCARD)
        self._ui.avatar_image.set_from_paintable(texture1)

    def _set_os_info(self, task: Task) -> None:
        self._tasks.remove(task)

        try:
            result = cast(SoftwareVersionResult, task.finish())
        except Exception as err:
            log.warning("Could not retrieve software version: %s", err)
            result = None

        resource = task.get_user_data()
        device_grid = self._devices[resource]
        device_grid.set_software(result)

    def _set_entity_time(self, task: Task) -> None:
        self._tasks.remove(task)

        try:
            entity_time = cast(str, task.finish())
        except Exception as err:
            log.warning("Could not retrieve entity time: %s", err)
            entity_time = None

        resource = task.get_user_data()

        device_grid = self._devices[resource]
        device_grid.set_entity_time(entity_time)

    def _save_annotation(self) -> None:
        buffer_ = self._ui.textview_annotation.get_buffer()
        new_annotation = buffer_.get_property("text")
        note = self._client.get_module("Annotations").get_note(self.contact.jid)
        if note is None or new_annotation != note.data:
            new_note = AnnotationNote(jid=self.contact.jid, data=new_annotation)
            self._client.get_module("Annotations").set_note(new_note)

    def _on_from_subscription_switch_toggled(
        self, switch: Gtk.Switch, state: bool
    ) -> int:
        def _on_response(response_id: str) -> None:
            if response_id == "stop":
                self._client.get_module("Presence").unsubscribed(self.contact.jid)
                switch.set_state(state)
            else:
                switch.set_active(True)

        if state:
            self._client.get_module("Presence").subscribed(self.contact.jid)
            switch.set_state(state)
        else:
            AlertDialog(
                _("Stop Sharing Online Status?"),
                _(
                    "The contact will be informed that you stopped sharing your "
                    "status. Please note that this can have other side effects."
                ),
                responses=[
                    CancelDialogResponse(),
                    DialogResponse(
                        "stop", _("_Stop Sharing"), appearance="destructive"
                    ),
                ],
                callback=_on_response,
                parent=self.window,
            )
        return Gdk.EVENT_STOP

    def _on_to_subscription_button_clicked(self, _widget: Gtk.Button) -> None:
        # Save auto_auth if switch for disclosing presence is active
        self._client.get_module("Presence").subscribe(
            self.contact.jid, auto_auth=self._ui.from_subscription_switch.get_state()
        )
        self._ui.request_stack.set_visible_child_name("requested")

    def _on_subscribed_presence_received(
        self, _event: SubscribedPresenceReceived
    ) -> None:

        self._ui.to_subscription_stack.set_visible_child_name("checkmark")

    def _on_unsubscribed_presence_received(
        self, _event: UnsubscribedPresenceReceived
    ) -> None:

        self._ui.to_subscription_stack.set_visible_child_name("request")
        self._ui.request_stack.set_visible_child_name("cross")

    def _on_group_selection_changed(self, _widget: Gtk.TreeSelection) -> None:
        selection = self._ui.groups_treeview.get_selection()
        (_model, iter_) = selection.get_selected()
        self._ui.group_remove_button.set_sensitive(bool(iter_))

    def _on_group_name_edited(
        self, _renderer: Gtk.CellRendererText, path: str, new_name: str
    ) -> None:
        if new_name == "":
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
        self._client.get_module("Roster").rename_group(old_name, new_name)

    def _on_group_remove_button_clicked(self, _widget: Gtk.Button) -> int:
        selection = self._ui.groups_treeview.get_selection()
        model, iter_ = selection.get_selected()
        assert iter_ is not None
        group = model[iter_][Column.GROUP_NAME]

        def _on_response() -> None:
            self._client.get_module("Roster").remove_group(group)
            del model[iter_]

        ConfirmationAlertDialog(
            _("Remove Group?"),
            _('Do you want to remove "%(group)s"?') % {"group": group},
            confirm_label=_("_Remove"),
            appearance="destructive",
            callback=_on_response,
            parent=self.window,
        )
        return Gdk.EVENT_STOP

    def _on_group_toggled(self, _renderer: Gtk.CellRendererToggle, path: str) -> None:

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

        self._client.get_module("Roster").set_groups(self.contact.jid, groups)

    def _on_group_add_button_clicked(self, _widget: Gtk.Button) -> None:
        default_name = _("New Group")
        model = self._ui.groups_treeview.get_model()
        assert model is not None
        assert isinstance(model, Gtk.ListStore)

        # Check if default_name group already exists
        iter_ = model.get_iter_first()
        while iter_:
            group_name = model.get_value(iter_, Column.GROUP_NAME)
            if group_name == default_name:
                default_name += "_"
            iter_ = model.iter_next(iter_)

        new_iter_ = model.append([False, default_name])
        path = model.get_path(new_iter_)
        column = self._ui.groups_treeview.get_column(Column.GROUP_NAME)
        self._ui.groups_treeview.set_cursor(path, column, True)


@Gtk.Template(string=get_ui_string("device_info.ui"))
class DeviceInfo(Adw.PreferencesGroup):

    __gtype_name__ = "DeviceInfo"

    _spinner: Adw.Spinner = Gtk.Template.Child()
    _status_row: Adw.ActionRow = Gtk.Template.Child()
    _priority_row: Adw.ActionRow = Gtk.Template.Child()
    _software_row: Adw.ActionRow = Gtk.Template.Child()
    _operating_system_row: Adw.ActionRow = Gtk.Template.Child()
    _local_time_row: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, contact: ResourceContact) -> None:
        Adw.PreferencesGroup.__init__(self)

        self._contact = contact

        self.set_title(_('Device "%s"') % contact.resource)

        self._status_row.set_subtitle(get_uf_show(contact.show.value))

        self._priority_row.set_subtitle(str(self._contact.priority))
        self._priority_row.set_visible(True)

        self._waiting_for_info = 2

    def do_unroot(self) -> None:
        Adw.PreferencesGroup.do_unroot(self)
        del self._contact

    def set_entity_time(self, entity_time: str | None) -> None:
        if entity_time is not None:
            self._local_time_row.set_subtitle(entity_time)
            self._local_time_row.set_visible(True)

        self._check_complete()

    def set_software(self, software: SoftwareVersionResult | None) -> None:
        if software is not None:
            software_string = f"{software.name} {software.version}"
            self._software_row.set_subtitle(software_string)
            self._software_row.set_visible(True)
            if software.os is not None:
                self._operating_system_row.set_subtitle(software.os)
                self._operating_system_row.set_visible(True)

        self._check_complete()

    def _check_complete(self) -> None:
        self._waiting_for_info -= 1
        if not self._waiting_for_info:
            self._spinner.set_visible(False)
