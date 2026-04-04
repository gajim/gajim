# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
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
from gajim.common.helpers import multiple_accounts_active
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.datetime import utc_now
from gajim.common.util.muc import get_groupchat_name
from gajim.common.util.user_strings import get_uf_relative_time
from gajim.plugins.manifest import PluginManifest
from gajim.plugins.repository import PluginRepository

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

if typing.TYPE_CHECKING:
    from gajim.gtk.activity_page import ActivityPage


log = logging.getLogger("gajim.gtk.activity_list")

E = TypeVar("E", bound=events.ApplicationEvent | None)

EventT = (
    events.MucInvitation
    | events.MucDecline
    | events.SubscribePresenceReceived
    | events.UnsubscribedPresenceReceived
    | events.GajimUpdateAvailable
    | events.AllowGajimUpdateCheck
    | events.ReactionUpdated
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

        self._model: Gio.ListStore[ActivityListItem[Any]] = Gio.ListStore(
            item_type=ActivityListItem
        )

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
        self._connect(self, "activate", self._on_activity_item_activate)
        self._connect(self, "unselected", self._on_activity_item_unselected)

        self.set_model(self._selection_model)

        self.register_events(
            [
                ("muc-invitation", ged.GUI1, self._on_event),
                ("muc-decline", ged.GUI1, self._on_event),
                ("subscription-request", ged.GUI1, self._on_event),
                ("unsubscribed-presence-received", ged.GUI1, self._on_event),
                ("gajim-update-available", ged.GUI1, self._on_event),
                ("allow-gajim-update-check", ged.GUI1, self._on_event),
                ("reaction-updated", ged.GUI1, self._on_event),
                ("account-disabled", ged.GUI1, self._on_account_disabled),
                ("timezone-changed", ged.GUI2, self._on_timezone_changed),
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
            events.ReactionUpdated: Reaction,
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

    def set_page(self, page: ActivityPage) -> None:
        self._activity_page = page
        self._activity_page.connect("page-removed", self._on_activity_page_removed)

    def _on_activity_page_removed(
        self, page: ActivityPage, item: ActivityListItemT
    ) -> None:
        self._remove(item)

    def select_with_context_id(self, context_id: str) -> None:
        for position, item in enumerate(self._model):
            if item.context_id == context_id:
                self._selection_model.set_selected(position)
                return

    def unselect(self) -> None:
        self._selection_model.unselect_all()

    def _add(self, item: ActivityListItemT, *, prepend: bool = True) -> None:
        if item.unique:
            self._remove_same_items(item)

        if prepend:
            self._model.insert(0, item)
        else:
            self._model.append(item)

        if not item.read:
            self._increase_unread_count()

    def _remove_same_items(self, new_item: ActivityListItemT) -> None:
        for i in reversed(range(len(self._model))):
            old_item = self._model.get_item(i)
            assert old_item is not None

            if (
                isinstance(old_item, type(new_item))
                and old_item.account == new_item.account
            ):
                if not old_item.read:
                    self._decrease_unread_count()
                self._model.remove(i)

    def _remove_by_type(self, item_type: type[ActivityListItemT]) -> None:
        for i in reversed(range(len(self._model))):
            item = self._model.get_item(i)
            assert item is not None

            if isinstance(item, item_type):
                if not item.read:
                    self._decrease_unread_count()
                self._model.remove(i)

    def _remove(self, item: ActivityListItemT) -> None:
        found, position = self._model.find(item)
        if not found:
            return

        self._model.remove(position)
        if not item.read:
            self._decrease_unread_count()

    def _update_time(self) -> bool:
        now = utc_now()
        for item in self._model:
            delta = now - item.timestamp
            if delta > dt.timedelta(days=8):
                # Items older than 8 days show an absolute timestamp
                # so updating makes no sense anymore
                break

            item.update_time()

        return GLib.SOURCE_CONTINUE

    def _on_activity_item_activate(
        self, listview: ActivityListView, position: int
    ) -> None:
        item = listview.get_listitem(position)
        item.activated()
        self._activity_page.process_row_activated(item)

    def _on_activity_item_unselected(self, _listview: ActivityListView) -> None:
        self._activity_page.show_default_page()

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
        if not list_item_cls.can_create(event):  # pyright: ignore
            return

        item = list_item_cls.from_event(event)  # pyright: ignore
        self._add(item)

        if item.should_notify():
            app.ged.raise_event(
                events.Notification(
                    context_id=item.context_id,
                    account=item.account,
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
        self._add(item)

    def _on_plugin_auto_update_finished(
        self, _repository: PluginRepository, _signal_name: str
    ) -> None:
        self._remove_by_type(GajimPluginUpdate)
        item = GajimPluginUpdateFinished.from_event()
        self._add(item)

    def _on_account_disabled(self, event: events.AccountDisabled) -> None:
        count = self._model.get_n_items()
        for pos in range(count - 1, -1, -1):
            item = cast(ActivityListItem[Any], self._model.get_item(pos))
            if item.account == event.account:
                self._model.remove(pos)

    def _on_timezone_changed(self, event: events.TimezoneChanged) -> None:
        self._add(TimezoneChanged.from_event(event))


class ActivityListItem(Generic[E], GObject.Object):
    __gtype_name__ = "ActivityListItem"

    context_id: str = GObject.Property(type=str)  # pyright: ignore
    account: str = GObject.Property(type=str)  # pyright: ignore
    account_visible: bool = GObject.Property(type=bool, default=False)  # pyright: ignore
    activity_type: int = GObject.Property(type=int)  # pyright: ignore
    activity_type_icon: str = GObject.Property(type=str)  # pyright: ignore
    avatar: Gdk.Paintable = GObject.Property(type=Gdk.Paintable)  # pyright: ignore
    timestamp: dt.datetime = GObject.Property(type=object)  # pyright: ignore
    title: str = GObject.Property(type=str)  # pyright: ignore
    subject: str = GObject.Property(type=str)  # pyright: ignore
    read: bool = GObject.Property(type=bool, default=False)  # pyright: ignore
    search_text: str = GObject.Property(type=str)  # pyright: ignore
    event: E = GObject.Property(type=object)  # pyright: ignore
    state = GObject.Property(type=object)
    unique: bool = GObject.Property(type=bool, default=False)  # pyright: ignore

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
        unique: bool = False,
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
            unique=unique,
        )

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def timestamp_string(self) -> str:
        return self._timestamp_string

    def update_time(self) -> None:
        self._timestamp_string = get_uf_relative_time(self.timestamp)
        self.notify("timestamp-string")

    def get_event(self) -> E:
        return self.event

    def activated(self) -> None:
        return

    def should_notify(self) -> bool:
        return False

    @staticmethod
    def can_create(event: E) -> bool:
        return True

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
            unique=True,
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
            unique=True,
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
            unique=True,
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
            unique=True,
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
            account_visible=multiple_accounts_active(),
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Contact Request"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )

    def should_notify(self) -> bool:
        return True


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
            account_visible=multiple_accounts_active(),
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
            account_visible=multiple_accounts_active(),
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Invitation"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )

    def should_notify(self) -> bool:
        return True


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
            account_visible=multiple_accounts_active(),
            activity_type=0,
            activity_type_icon="lucide-users-symbolic",
            avatar=texture,
            title=_("Invitation Declined"),
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )


class TimezoneChanged(ActivityListItem[events.TimezoneChanged]):
    @classmethod
    def from_event(cls, event: events.TimezoneChanged) -> TimezoneChanged:
        scale = app.window.get_scale_factor()
        texture = app.app.avatar_storage.get_gajim_circle_icon(AvatarSize.ROSTER, scale)
        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=multiple_accounts_active(),
            activity_type=0,
            activity_type_icon="lucide-info-symbolic",
            avatar=texture,
            title=_("Timezone Update"),
            timestamp=utc_now(),
            subject=_("Update your timezone?"),
            read=False,
            event=event,
            unique=True,
        )


class Reaction(ActivityListItem[events.ReactionUpdated]):
    @classmethod
    def from_event(cls, event: events.ReactionUpdated) -> Reaction:
        client = app.get_client(event.account)
        scale = app.window.get_scale_factor()
        assert event.message is not None
        if event.message.type in (MessageType.GROUPCHAT, MessageType.PM):
            muc_jid = event.message.remote.jid
            if event.message.type == MessageType.PM:
                muc_jid.new_as_bare()

            groupchat_name = get_groupchat_name(client, muc_jid)

            assert event.occupant is not None
            texture = app.app.avatar_storage.get_occupant_texture(
                event.jid, event.occupant, AvatarSize.ROSTER, scale
            )
            nickname = event.occupant.nickname
            title = _("Reaction from %s (%s)") % (nickname, groupchat_name)

        else:
            contact = client.get_module("Contacts").get_contact(event.jid)
            assert isinstance(contact, BareContact)
            texture = contact.get_avatar(AvatarSize.ROSTER, scale)
            nickname = contact.name
            title = _("Reaction from %s") % nickname

        assert event.message is not None
        assert event.emojis is not None
        emojis = " ".join(event.emojis)

        subject = _(
            "%(contact)s reacted with %(reaction)s to your message '%(message)s'"
        ) % {
            "contact": nickname,
            "reaction": emojis,
            "message": event.message.text or "",
        }
        return cls(
            context_id=event.context_id,
            account=event.account,
            account_visible=multiple_accounts_active(),
            activity_type=0,
            activity_type_icon="lucide-reply-symbolic",
            avatar=texture,
            title=title,
            timestamp=utc_now(),
            subject=subject,
            read=False,
            event=event,
        )

    @staticmethod
    def can_create(event: events.ReactionUpdated) -> bool:
        return (
            event.message is not None
            # Message is in the database
            and event.message.direction == ChatDirection.OUTGOING
            # Message we sent out
            and event.direction == ChatDirection.INCOMING
            # A reaction we received from someone else
        )

    def activated(self) -> None:
        assert self.event.message is not None
        app.window.scroll_to_message(self.event.account, self.event.message)

    def should_notify(self) -> bool:
        assert self.event.message is not None
        if self.event.is_mam_message or app.window.is_chat_active(
            self.account, self.event.jid
        ):
            return False

        if self.event.message.type in (MessageType.GROUPCHAT, MessageType.PM):
            return app.settings.get_app_setting("gc_notify_on_reaction_default")
        return app.settings.get_app_setting("notify_on_reaction_default")


ActivityListItemT = (
    GajimUpdate
    | GajimUpdatePermission
    | GajimPluginUpdate
    | GajimPluginUpdateFinished
    | Subscribe
    | Unsubscribed
    | MucInvitation
    | MucInvitationDeclined
    | TimezoneChanged
    | Reaction
)
