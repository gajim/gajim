# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Generic
from typing import TypeVar

import datetime as dt
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.datetime import utc_now
from gajim.common.util.muc import get_groupchat_name
from gajim.common.util.user_strings import get_uf_relative_time
from gajim.plugins.manifest import PluginManifest
from gajim.plugins.repository import PluginRepository

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.activity_list")

E = TypeVar("E", bound=events.ApplicationEvent | None)

EventT = (
    events.MucInvitation
    | events.MucDecline
    | events.SubscribePresenceReceived
    | events.UnsubscribedPresenceReceived
    | events.GajimUpdateAvailable
    | events.AllowGajimUpdateCheck
)

EventNotifications = (
    events.MucInvitation,
    events.SubscribePresenceReceived,
)


class ActivityListView(Gtk.ListView, SignalManager, EventHelper):
    __gtype_name__ = "ActivityListView"
    __gsignals__ = {
        "unselected": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    unread_count = GObject.Property(type=int, default=0)

    def __init__(self) -> None:
        Gtk.ListView.__init__(self)
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        self.add_css_class("activity-list-view")

        self._model = Gio.ListStore(item_type=ActivityListItem)

        factory = Gtk.SignalListItemFactory()
        self._connect(factory, "setup", self._on_factory_setup)
        self._connect(factory, "bind", self._on_factory_bind)
        self._connect(factory, "unbind", self._on_factory_unbind)
        self.set_factory(factory)

        # TODO
        # self._chat_filters = ChatFilters()
        self._scroll_id = None
        self._search_string_list: list[str] = []
        self._search_entry: Gtk.SearchEntry | None = None
        self._current_filter_text = ""

        self._timer_id = GLib.timeout_add_seconds(60, self._update_time)

        self._items: dict[str, ActivityListItem[Any]] = {}

        self._custom_filter = Gtk.CustomFilter.new(self._filter_func)

        self._filter_model = Gtk.FilterListModel(
            model=self._model, filter=self._custom_filter
        )

        self._selection_model = Gtk.SingleSelection(
            model=self._filter_model,
            autoselect=False,
            can_unselect=True,
        )
        self._connect(
            self._selection_model, "notify::selected-item", self._on_selection_changed
        )

        self.set_model(self._selection_model)

        self.register_events(
            [
                ("muc-invitation", ged.GUI1, self._on_event),
                ("muc-decline", ged.GUI1, self._on_event),
                ("subscription-request", ged.GUI1, self._on_event),
                ("unsubscribed-presence-received", ged.GUI1, self._on_event),
                ("gajim-update-available", ged.GUI1, self._on_event),
                ("allow-gajim-update-check", ged.GUI1, self._on_event),
                ("account-disabled", ged.GUI1, self._on_account_disabled),
            ]
        )

        app.plugin_repository.connect(
            "plugin-updates-available", self._on_plugin_updates_available
        )
        app.plugin_repository.connect(
            "auto-update-finished", self._on_plugin_auto_update_finished
        )

        self._event_item_map = {
            events.MucInvitation: MucInvitation,
            events.MucDecline: MucInvitationDeclined,
            events.SubscribePresenceReceived: Subscribe,
            events.UnsubscribedPresenceReceived: Unsubscribed,
            events.GajimUpdateAvailable: GajimUpdate,
            events.AllowGajimUpdateCheck: GajimUpdatePermission,
        }

    def do_unroot(self) -> None:
        # The filter func needs to be unset before calling do_unroot (see #12213)
        self._custom_filter.set_filter_func(None)
        Gtk.ListView.do_unroot(self)
        self._disconnect_all()
        app.plugin_repository.disconnect_all_from_obj(self)

        GLib.source_remove(self._timer_id)
        app.check_finalize(self._model)
        app.check_finalize(self._filter_model)
        app.check_finalize(self._selection_model)
        app.check_finalize(self._custom_filter)
        del self._model
        del self._filter_model
        del self._selection_model
        del self._search_entry
        del self._custom_filter
        app.check_finalize(self)

    def select_with_context_id(self, context_id: str) -> None:
        for position, item in enumerate(self._model):
            item = cast(ActivityListItem[Any], item)
            if item.context_id == context_id:
                self._selection_model.set_selected(position)
                return

    def unselect(self) -> None:
        self._selection_model.unselect_all()

    def _add(self, item: ActivityListItemT, *, prepend: bool = True) -> None:
        if prepend:
            self._model.insert(0, item)
        else:
            self._model.append(item)

        if not item.read:
            self._increase_unread_count()

    def _remove(self, position: int, read: bool) -> None:
        if not read:
            self._decrease_unread_count()

        self._model.remove(position)

    def _update_time(self) -> int:
        now = utc_now()
        for item in self._model:
            item = cast(ActivityListItem[Any], item)
            delta = now - item.timestamp
            if delta > dt.timedelta(days=8):
                # Items older than 8 days show an absolute timestamp
                # so updating makes no sense anymore
                break

            item.update_time()

        return GLib.SOURCE_CONTINUE

    def _increase_unread_count(self) -> None:
        self.set_property("unread-count", self.unread_count + 1)

    def _decrease_unread_count(self) -> None:
        self.set_property("unread-count", self.unread_count - 1)

    def _on_selection_changed(
        self, selection_model: Gtk.SingleSelection, *args: Any
    ) -> None:
        item = selection_model.get_selected_item()
        if item is None:
            self.emit("unselected")
            return

        assert isinstance(item, ActivityListItem)
        if not item.read:
            item.read = True
            self._decrease_unread_count()
            if item.context_id:
                app.ged.raise_event(events.NotificationWithdrawn(item.context_id))

        position = selection_model.get_selected()
        self.activate_action("list.activate-item", GLib.Variant("u", position))

    def set_search_entry(self, entry: Gtk.SearchEntry) -> None:
        self._search_entry = entry
        self._connect(entry, "search-changed", self._on_search_changed)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._current_filter_text = entry.get_text().lower()
        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        list_item.set_child(ActivityViewItem())

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = cast(ActivityViewItem, list_item.get_child())
        obj = cast(ActivityListItem[EventT], list_item.get_item())
        view_item.bind(obj)

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = cast(ActivityViewItem, list_item.get_child())
        view_item.unbind()

    def get_listitem(self, position: int) -> ActivityListItemT:
        return cast(ActivityListItemT, self._filter_model.get_item(position))

    def _filter_func(self, item: ActivityListItem[EventT]) -> bool:
        if not self._current_filter_text:
            return True

        return self._current_filter_text in item.search_text

    def _on_event(self, event: EventT) -> None:
        list_item_cls = self._event_item_map[type(event)]
        item = list_item_cls.from_event(event)  # pyright: ignore

        self._add(item)

        if isinstance(event, EventNotifications):
            app.ged.raise_event(
                events.Notification(
                    context_id=event.context_id,
                    account=event.account,
                    jid=None,
                    type=event.name,
                    title=item.title,
                    text=item.subject,
                )
            )

    def _on_plugin_updates_available(
        self,
        _repository: PluginRepository,
        _signal_name: str,
        manifests: list[PluginManifest],
    ) -> None:
        item = GajimPluginUpdate.from_event(
            events.PluginUpdatesAvailable(manifests=manifests)
        )
        self._items["plugin-updates-available"] = item
        self._add(item)

    def _on_plugin_auto_update_finished(
        self, _repository: PluginRepository, _signal_name: str
    ) -> None:
        item = self._items.get("plugin-updates-available")
        if item is not None:
            found, position = self._model.find(item)
            if found:
                self._remove(position, item.read)

        item = GajimPluginUpdateFinished.from_event()
        self._add(item)

    def _on_account_disabled(self, event: events.AccountDisabled) -> None:
        count = self._model.get_n_items()
        for pos in range(count - 1, -1, -1):
            item = cast(ActivityListItem[Any], self._model.get_item(pos))
            if item.account == event.account:
                self._model.remove(pos)


class ActivityListItem(Generic[E], GObject.Object):
    __gtype_name__ = "ActivityListItem"

    context_id = GObject.Property(type=str)
    account = GObject.Property(type=str)
    account_visible = GObject.Property(type=bool, default=False)
    activity_type = GObject.Property(type=int)
    activity_type_icon = GObject.Property(type=str)
    avatar = GObject.Property(type=Gdk.Paintable)
    timestamp = GObject.Property(type=object)
    title = GObject.Property(type=str)
    subject = GObject.Property(type=str)
    read = GObject.Property(type=bool, default=False)
    search_text = GObject.Property(type=str)
    event = GObject.Property(type=object)
    state = GObject.Property(type=object)

    def __init__(
        self,
        context_id: str,
        account: str,
        account_visible: bool,
        activity_type: int,
        activity_type_icon: str,
        avatar: Gdk.Paintable,
        title: str,
        timestamp: dt.datetime,
        subject: str,
        read: bool,
        event: E,
    ) -> None:
        self._timestamp_string = get_uf_relative_time(timestamp)

        super().__init__(
            context_id=context_id,
            account=account,
            account_visible=account_visible,
            activity_type=activity_type,
            activity_type_icon=activity_type_icon,
            avatar=avatar,
            title=title,
            timestamp=timestamp,
            subject=subject,
            read=read,
            search_text=f"{title} {subject}",
            event=event,
            state={},
        )

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def timestamp_string(self) -> str:
        return self._timestamp_string

    def update_time(self) -> None:
        self._timestamp_string = get_uf_relative_time(self.timestamp)
        self.notify("timestamp-string")

    def get_event(self) -> E:
        return self.event

    def __repr__(self) -> str:
        return f"ActivityListItem: {self.account} - {self.activity_type}"


@Gtk.Template(string=get_ui_string("activity_list_row.ui"))
class ActivityViewItem(Gtk.Grid, SignalManager):
    __gtype_name__ = "ActivityViewItem"

    _account_identifier: Gtk.Box = Gtk.Template.Child()
    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _activity_type_image: Gtk.Image = Gtk.Template.Child()
    _activity_title_label: Gtk.Label = Gtk.Template.Child()
    _timestamp_label: Gtk.Label = Gtk.Template.Child()
    _activity_subject_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Grid.__init__(self)
        SignalManager.__init__(self)

        self._account = ""
        self._account_css_class = ""
        self._read = False
        self.__bindings: list[GObject.Binding] = []

    @GObject.Property(type=str)
    def account(self) -> str:  # pyright: ignore
        return self._account

    @account.setter
    def account(self, account: str) -> None:
        self._account = account

        if self._account_css_class:
            self._account_identifier.remove_css_class(self._account_css_class)
            self._account_css_class = ""

        if not account:
            return

        self._account_css_class = app.css_config.get_dynamic_class(account)
        self._account_identifier.add_css_class(self._account_css_class)

    @GObject.Property(type=bool, default=False)
    def read(self) -> bool:  # pyright: ignore
        return self._read

    @read.setter
    def read(self, read: bool) -> None:
        self._read = read
        if self._read:
            self._activity_title_label.remove_css_class("bold")
        else:
            self._activity_title_label.add_css_class("bold")

    def bind(self, obj: ActivityListItem[E]) -> None:
        bind_spec = [
            ("account", self, "account"),
            ("account_visible", self._account_identifier, "visible"),
            ("activity_type_icon", self._activity_type_image, "icon_name"),
            ("avatar", self._avatar_image, "paintable"),
            ("title", self._activity_title_label, "label"),
            ("timestamp_string", self._timestamp_label, "label"),
            ("subject", self._activity_subject_label, "label"),
            ("read", self, "read"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self.__bindings.append(bind)

    def unbind(self) -> None:
        for bind in self.__bindings:
            bind.unbind()
        self.__bindings.clear()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Grid.do_unroot(self)
        app.check_finalize(self)


class GajimUpdate(ActivityListItem[events.GajimUpdateAvailable]):
    @classmethod
    def from_event(cls, event: events.GajimUpdateAvailable) -> GajimUpdate:
        scale = app.window.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)

        return cls(
            context_id=event.context_id,
            account="",
            account_visible=False,
            activity_type=0,
            activity_type_icon="lucide-info-symbolic",
            avatar=texture,
            title=_("Gajim Update"),
            timestamp=utc_now(),
            subject=_("Gajim %s is available") % event.version,
            read=False,
            event=event,
        )


class GajimUpdatePermission(ActivityListItem[events.AllowGajimUpdateCheck]):
    @classmethod
    def from_event(cls, event: events.AllowGajimUpdateCheck) -> GajimUpdatePermission:
        scale = app.window.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)

        return cls(
            context_id=event.context_id,
            account="",
            account_visible=False,
            activity_type=0,
            activity_type_icon="lucide-info-symbolic",
            avatar=texture,
            title=_("Gajim Update Check"),
            timestamp=utc_now(),
            subject=_("Search for Gajim updates periodically?"),
            read=False,
            event=event,
        )


class GajimPluginUpdate(ActivityListItem[events.PluginUpdatesAvailable]):
    @classmethod
    def from_event(cls, event: events.PluginUpdatesAvailable) -> GajimPluginUpdate:
        scale = app.window.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)

        return cls(
            context_id=event.context_id,
            account="",
            account_visible=False,
            activity_type=0,
            activity_type_icon="lucide-info-symbolic",
            avatar=texture,
            title=_("Plugin Update"),
            timestamp=utc_now(),
            subject=_("There are updates for Gajim’s plugins"),
            read=False,
            event=event,
        )


class GajimPluginUpdateFinished(ActivityListItem[None]):
    @classmethod
    def from_event(cls) -> GajimPluginUpdateFinished:
        scale = app.window.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)

        return cls(
            context_id="",
            account="",
            account_visible=False,
            activity_type=0,
            activity_type_icon="lucide-info-symbolic",
            avatar=texture,
            title=_("Plugins Updated Successfully"),
            timestamp=utc_now(),
            subject=_("Updates will be installed next time Gajim is started"),
            read=False,
            event=None,
        )


class Subscribe(ActivityListItem[events.SubscribePresenceReceived]):
    @classmethod
    def from_event(cls, event: events.SubscribePresenceReceived) -> Subscribe:
        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.jid)

        scale = app.window.get_scale_factor()
        assert not isinstance(contact, ResourceContact)
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)

        nick = event.user_nick
        if not nick:
            assert isinstance(contact, BareContact)
            nick = contact.name

        subject = _("%s wants to add you.") % nick
        if event.status:
            subject = f"{subject} {event.status}"

        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=True,
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Contact Request"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )


class Unsubscribed(ActivityListItem[events.UnsubscribedPresenceReceived]):
    @classmethod
    def from_event(cls, event: events.UnsubscribedPresenceReceived) -> Unsubscribed:
        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.jid)

        scale = app.window.get_scale_factor()
        assert not isinstance(contact, ResourceContact)
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)

        subject = _("%s stopped sharing their status") % contact.name

        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=True,
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Contact Removed"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )


class MucInvitation(ActivityListItem[events.MucInvitation]):
    @classmethod
    def from_event(cls, event: events.MucInvitation) -> MucInvitation:
        client = app.get_client(event.account)
        muc_contact = client.get_module("Contacts").get_contact(event.muc)
        assert isinstance(muc_contact, GroupchatContact)
        if muc_contact.muc_context == "private" and not event.muc.bare_match(
            event.from_
        ):
            contact = client.get_module("Contacts").get_contact(event.from_.bare)
            assert isinstance(contact, BareContact)
            subject = _("%(contact)s invited you to %(chat)s") % {
                "contact": contact.name,
                "chat": event.info.muc_name,
            }

        else:
            subject = _("You have been invited to %s") % event.info.muc_name

        if event.info.jid is not None:
            contact = client.get_module("Contacts").get_contact(event.info.jid)
        else:
            contact = client.get_module("Contacts").get_contact(event.from_.bare)

        scale = app.window.get_scale_factor()
        assert not isinstance(contact, ResourceContact)
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)

        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=True,
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Invitation"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )


class MucInvitationDeclined(ActivityListItem[events.MucDecline]):
    @classmethod
    def from_event(cls, event: events.MucDecline) -> MucInvitationDeclined:
        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.from_.bare)

        scale = app.window.get_scale_factor()
        assert not isinstance(contact, ResourceContact)
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)

        muc_name = get_groupchat_name(client, event.muc)
        subject = _("%(contact)s declined your invitation to %(chat)s") % {
            "contact": contact.name,
            "chat": muc_name,
        }
        if event.reason is not None:
            subject = f"{subject} ({event.reason})"

        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=True,
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Invitation Declined"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )


ActivityListItemT = (
    GajimUpdate
    | GajimUpdatePermission
    | GajimPluginUpdate
    | GajimPluginUpdateFinished
    | Subscribe
    | Unsubscribed
    | MucInvitation
    | MucInvitationDeclined
)
