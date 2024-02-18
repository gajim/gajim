# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import datetime as dt
import logging
from enum import IntEnum

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.muc import get_groupchat_name
from gajim.common.util.user_strings import get_uf_relative_time
from gajim.plugins.manifest import PluginManifest
from gajim.plugins.repository import PluginRepository

from gajim.gtk import structs
from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import iterate_listbox_children

log = logging.getLogger("gajim.gtk.activity_list")


class ActivityRowType(IntEnum):
    GAJIM_UPDATE = 0
    SUBSCRIPTION = 1
    MUC_INVITATION = 2


class ActivityList(Gtk.ListBox, SignalManager, EventHelper):

    __gsignals__ = {
        "unread-count-changed": (GObject.SignalFlags.RUN_LAST, None, (int,)),
        "row-removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        self._set_placeholder()
        self.set_sort_func(self._sort_func)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_row_state)

        self.register_events(
            [
                (
                    "allow-gajim-update-check",
                    ged.GUI1,
                    self._on_gajim_update_permission_request,
                ),
                ("gajim-update-available", ged.GUI1, self._on_gajim_update_available),
                ("muc-invitation", ged.GUI1, self._on_muc_invitation_received),
                ("muc-decline", ged.GUI1, self._on_muc_invitation_declined),
                ("subscribe-presence-received", ged.GUI1, self._on_subscribe_received),
                (
                    "unsubscribed-presence-received",
                    ged.GUI1,
                    self._on_unsubscribed_received,
                ),
            ]
        )

        app.plugin_repository.connect(
            "plugin-updates-available", self._on_plugin_updates_available
        )
        app.plugin_repository.connect(
            "auto-update-finished", self._on_plugin_auto_update_finished
        )

        self._connect(self, "row-activated", self._on_row_activated)

    def do_unroot(self) -> None:
        GLib.source_remove(self._timer_id)
        app.plugin_repository.disconnect_all_from_obj(self)
        self._disconnect_all()
        Gtk.ListBox.do_unroot(self)

    def remove_activities_for_account(self, account: str) -> None:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            if row.account == account:
                self.remove(row)

    def _set_placeholder(self) -> None:
        label = Gtk.Label(
            label=_("No activities"), halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER
        )
        label.add_css_class("dim-label")
        label.show()
        self.set_placeholder(label)

    def _update_row_state(self) -> bool:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            row.update_row_state()
        return True

    def _on_row_activated(
        self, _activity_list: ActivityList, row: ActivityListRow
    ) -> None:
        row.mark_as_read()
        self._update_unread()

    def _sort_func(self, row1: ActivityListRow, row2: ActivityListRow) -> int:
        # Sort by timestamp
        return -1 if row1.timestamp > row2.timestamp else 1

    def _update_unread(self) -> None:
        rows = cast(list[ActivityListRow], list(iterate_listbox_children(self)))
        self.emit("unread-count-changed", len([row for row in rows if not row.is_read]))

    def _add_activity_row(self, row: ActivityListRow) -> None:
        row.connect("remove-row", self._on_remove_row)
        self.append(row)
        self._update_unread()

    def _on_remove_row(self, row: ActivityListRow) -> None:
        self.remove(row)
        self._update_unread()
        self.emit("row-removed")

    def _remove_rows_of_type(self, row_type: Any) -> None:
        for row in iterate_listbox_children(self):
            if isinstance(row, row_type):
                self.remove(row)

    def _on_gajim_update_permission_request(
        self, _event: events.AllowGajimUpdateCheck
    ) -> None:
        self._remove_rows_of_type(GajimUpdatePermissionRow)
        self._add_activity_row(GajimUpdatePermissionRow())

    def _on_gajim_update_available(self, event: events.GajimUpdateAvailable) -> None:
        self._remove_rows_of_type(GajimUpdateRow)
        self._add_activity_row(GajimUpdateRow(event.version, event.setup_url))

    def _on_plugin_updates_available(
        self,
        _repository: PluginRepository,
        _signal_name: str,
        manifests: list[PluginManifest],
    ) -> None:
        self._remove_rows_of_type(GajimPluginUpdateRow)
        self._add_activity_row(GajimPluginUpdateRow(manifests))

    def _on_plugin_auto_update_finished(
        self, _repository: PluginRepository, _signal_name: str
    ) -> None:
        self._remove_rows_of_type(GajimPluginUpdateFinishedRow)
        self._add_activity_row(GajimPluginUpdateFinishedRow())

    def _on_muc_invitation_received(self, event: events.MucInvitation) -> None:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            if (
                row.type == ActivityRowType.MUC_INVITATION
                and row.account == event.account
                and row.jid == event.muc
            ):
                self.remove(row)

        row = MucInvitationReceivedRow(event)
        self._add_activity_row(row)

        app.ged.raise_event(
            events.Notification(
                account=event.account,
                jid=event.from_.bare,
                type="group-chat-invitation",
                title=row.get_title_text(),
                text=row.get_subject_text(),
            )
        )

    def _on_muc_invitation_declined(self, event: events.MucDecline) -> None:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            if (
                row.type == ActivityRowType.MUC_INVITATION
                and row.account == event.account
                and row.jid == event.from_
            ):
                self.remove(row)

        self._add_activity_row(MucInvitationDeclinedRow(event))

    def _on_subscribe_received(self, event: events.SubscribePresenceReceived) -> None:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            if (
                row.type == ActivityRowType.SUBSCRIPTION
                and row.account == event.account
                and row.jid == JID.from_string(event.jid)
            ):
                self.remove(row)

        row = SubscribeRow(event)
        self._add_activity_row(row)

        app.ged.raise_event(
            events.Notification(
                account=event.account,
                jid=event.jid,
                type="subscription-request",
                title=row.get_title_text(),
                text=row.get_subject_text(),
            )
        )

    def _on_unsubscribed_received(
        self, event: events.UnsubscribedPresenceReceived
    ) -> None:
        for row in iterate_listbox_children(self):
            assert isinstance(row, ActivityListRow)
            if (
                row.type == ActivityRowType.SUBSCRIPTION
                and row.account == event.account
                and row.jid == JID.from_string(event.jid)
            ):
                self.remove(row)

        row = UnsubscribedRow(event)
        self._add_activity_row(row)

        app.ged.raise_event(
            events.Notification(
                account=event.account,
                jid=event.jid,
                type="unsubscribed",
                title=row.get_title_text(),
                text=row.get_subject_text(),
            )
        )


class ActivityListRow(Gtk.ListBoxRow, SignalManager):

    __gsignals__ = {
        "remove-row": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, account: str | None = None, jid: JID | None = None) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

        self.type: ActivityRowType | None = None
        self.timestamp = dt.datetime.now()
        self.account = account
        self.jid = jid

        self._is_read = False

        self._ui = get_builder("activity_list_row.ui")
        self.set_child(self._ui.activity_list_row)

        self.add_css_class("activitylist-row")

        self._ui.close_button.connect("clicked", self._on_dismiss_clicked)

        self._connect(self, "state-flags-changed", self._on_state_flags_changed)

        self.update_account_identifier()
        self.update_row_state()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)

    def remove(self) -> None:
        self.emit("remove-row")

    def update_row_state(self) -> None:
        self.update_time()

    def update_time(self) -> None:
        self._ui.timestamp_label.set_text(get_uf_relative_time(self.timestamp))

    def set_avatar_from_contact(self, contact: types.ContactT) -> None:
        scale = self.get_scale_factor()
        assert not isinstance(contact, ResourceContact)
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_from_paintable(texture)

    def set_avatar_from_gajim_icon(self) -> None:
        scale = self.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_from_paintable(texture)

    def update_account_identifier(self) -> None:
        if self.account is None:
            return

        account_class = app.css_config.get_dynamic_class(self.account)
        self._ui.account_identifier.add_css_class(account_class)
        show = len(app.settings.get_active_accounts()) > 1
        self._ui.account_identifier.set_visible(show)

    @property
    def is_read(self) -> bool:
        return self._is_read

    def mark_as_read(self) -> None:
        self._is_read = True
        self._ui.activity_title_label.remove_css_class("bold")

    def mark_as_unread(self) -> None:
        self._is_read = False
        self._ui.activity_title_label.add_css_class("bold")

    def _on_state_flags_changed(
        self, _row: ActivityListRow, _flags: Gtk.StateFlags
    ) -> None:
        if (self.get_state_flags() & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def _on_dismiss_clicked(self, _button: Gtk.Button) -> None:
        """Can be overridden."""
        self.emit("remove-row")


class GajimUpdatePermissionRow(ActivityListRow):
    def __init__(self) -> None:
        ActivityListRow.__init__(self)
        self.type = ActivityRowType.GAJIM_UPDATE

        self.set_avatar_from_gajim_icon()
        self._ui.activity_type_indicator.set_from_icon_name("feather-info-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def _on_dismiss_clicked(self, _button: Gtk.Button) -> None:
        app.settings.set("check_for_update", False)
        self.emit("remove-row")

    def get_title_text(self) -> str:
        return _("Gajim Update Check")

    def get_subject_text(self) -> str:
        return _("Search for Gajim updates periodically?")


class GajimUpdateRow(ActivityListRow):
    def __init__(self, new_version: str, new_setup_url: str) -> None:
        ActivityListRow.__init__(self)
        self.type = ActivityRowType.GAJIM_UPDATE

        self._new_version = new_version
        self.new_setup_url = new_setup_url

        self.set_avatar_from_gajim_icon()
        self._ui.activity_type_indicator.set_from_icon_name("feather-info-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_title_text(self) -> str:
        return _("Gajim Update")

    def get_subject_text(self) -> str:
        return _("Gajim %s is available") % self._new_version


class GajimPluginUpdateRow(ActivityListRow):
    def __init__(self, manifests: list[PluginManifest]) -> None:
        ActivityListRow.__init__(self)
        self.type = ActivityRowType.GAJIM_UPDATE

        self.plugin_manifests = manifests

        self.set_avatar_from_gajim_icon()
        self._ui.activity_type_indicator.set_from_icon_name("feather-info-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_title_text(self) -> str:
        return _("Plugin Update")

    def get_subject_text(self) -> str:
        return _("There are updates for Gajim’s plugins")


class GajimPluginUpdateFinishedRow(ActivityListRow):
    def __init__(self) -> None:
        ActivityListRow.__init__(self)
        self.type = ActivityRowType.GAJIM_UPDATE

        self.set_avatar_from_gajim_icon()
        self._ui.activity_type_indicator.set_from_icon_name("feather-info-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_title_text(self) -> str:
        return _("Plugins Updated Successfully")

    def get_subject_text(self) -> str:
        return _("Updates will be installed next time Gajim is started")


class SubscribeRow(ActivityListRow):
    def __init__(self, event: events.SubscribePresenceReceived) -> None:
        ActivityListRow.__init__(self, event.account, JID.from_string(event.jid))
        self.type = ActivityRowType.SUBSCRIPTION

        self._event = event

        self._client = app.get_client(self._event.account)
        self._contact = self._client.get_module("Contacts").get_contact(self._event.jid)
        self.set_avatar_from_contact(self._contact)
        self._ui.activity_type_indicator.set_from_icon_name("feather-user-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

        subscription_accept_action = app.app.lookup_action(
            f"{event.account}-subscription-accept"
        )
        assert subscription_accept_action is not None
        subscription_accept_action.connect("activate", self._on_subscription_accepted)

        subscription_deny_all_action = app.app.lookup_action(
            f"{event.account}-subscription-deny-all"
        )
        assert subscription_deny_all_action is not None
        subscription_deny_all_action.connect("activate", self._on_subscription_deny_all)

        block_contact_action = app.app.lookup_action(f"{event.account}-block-contact")
        assert block_contact_action is not None
        block_contact_action.connect("activate", self._on_contact_blocked)

    @structs.actionmethod
    def _on_subscription_accepted(
        self, _action: Gio.SimpleAction, params: structs.SubscriptionAcceptParam
    ) -> None:
        if self._event.jid == str(params.jid):
            self.emit("remove-row")

    def _on_subscription_deny_all(
        self, _action: Gio.SimpleAction, _param: GLib.Variant
    ) -> None:
        deny_param = structs.AccountJidParam(
            account=self._event.account, jid=JID.from_string(self._event.jid)
        )
        app.app.activate_action(
            f"{self._event.account}-subscription-deny", deny_param.to_variant()
        )
        self.emit("remove-row")

    def _on_contact_blocked(self, _action: str, param: GLib.Variant) -> None:
        if self._event.jid == param.get_string():
            self.emit("remove-row")

    def get_event(self) -> events.SubscribePresenceReceived:
        return self._event

    def get_title_text(self) -> str:
        return _("Contact Request")

    def get_subject_text(self) -> str:
        nick = self._event.user_nick
        if not nick:
            assert isinstance(self._contact, BareContact)
            nick = self._contact.name

        text = _("%s wants to add you.") % nick
        if self._event.status:
            text = f"{text} {self._event.status}"
        return text


class UnsubscribedRow(ActivityListRow):
    def __init__(self, event: events.UnsubscribedPresenceReceived) -> None:
        ActivityListRow.__init__(self, event.account, JID.from_string(event.jid))
        self.type = ActivityRowType.SUBSCRIPTION

        self._event = event

        self._client = app.get_client(self._event.account)
        self._contact = self._client.get_module("Contacts").get_contact(self._event.jid)
        self.set_avatar_from_contact(self._contact)
        self._ui.activity_type_indicator.set_from_icon_name("feather-user-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_event(self) -> events.UnsubscribedPresenceReceived:
        return self._event

    def get_title_text(self) -> str:
        return _("Contact Removed")

    def get_subject_text(self) -> str:
        assert isinstance(self._contact, BareContact)
        return _("%s stopped sharing their status") % self._contact.name


class MucInvitationReceivedRow(ActivityListRow):
    def __init__(self, event: events.MucInvitation) -> None:
        ActivityListRow.__init__(self, event.account, event.muc)
        self.type = ActivityRowType.MUC_INVITATION

        self._event = event

        client = app.get_client(event.account)
        muc_contact = client.get_module("Contacts").get_contact(self._event.muc)
        muc_contact.connect("room-joined", self._on_room_joined)

        if self._event.info.jid is not None:
            contact = client.get_module("Contacts").get_contact(event.info.jid)
        else:
            contact = client.get_module("Contacts").get_contact(event.from_.bare)
        self.set_avatar_from_contact(contact)
        self._ui.activity_type_indicator.set_from_icon_name("feather-users-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_event(self) -> events.MucInvitation:
        return self._event

    def get_title_text(self) -> str:
        return _("Invitation")

    def get_subject_text(self) -> str:
        client = app.get_client(self._event.account)
        muc_contact = client.get_module("Contacts").get_contact(self._event.muc)
        assert isinstance(muc_contact, GroupchatContact)
        if muc_contact.muc_context == "private" and not self._event.muc.bare_match(
            self._event.from_
        ):
            contact = client.get_module("Contacts").get_contact(self._event.from_.bare)
            assert isinstance(contact, BareContact)
            return _("%(contact)s invited you to %(chat)s") % {
                "contact": contact.name,
                "chat": self._event.info.muc_name,
            }

        return _("You have been invited to %s") % self._event.info.muc_name

    def _on_room_joined(self, _contact: GroupchatContact, _signal_name: str) -> None:
        self.emit("remove-row")


class MucInvitationDeclinedRow(ActivityListRow):
    def __init__(self, event: events.MucDecline) -> None:
        ActivityListRow.__init__(self, event.account, event.from_)
        self.type = ActivityRowType.MUC_INVITATION

        self._event = event

        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.from_.bare)
        self.set_avatar_from_contact(contact)
        self._ui.activity_type_indicator.set_from_icon_name("feather-users-symbolic")
        self._ui.activity_title_label.set_text(self.get_title_text())
        self._ui.activity_subject_label.set_text(self.get_subject_text())

    def get_event(self) -> events.MucDecline:
        return self._event

    def get_title_text(self) -> str:
        return _("Invitation Declined")

    def get_subject_text(self) -> str:
        client = app.get_client(self._event.account)

        contact = client.get_module("Contacts").get_contact(self._event.from_.bare)
        assert not isinstance(contact, ResourceContact)

        muc_name = get_groupchat_name(client, self._event.muc)
        text = _("%(contact)s declined your invitation to %(chat)s") % {
            "contact": contact.name,
            "chat": muc_name,
        }
        if self._event.reason is not None:
            text = f"{text} ({self._event.reason})"
        return text
