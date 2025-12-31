# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import locale
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.const import Affiliation

from gajim.common import app
from gajim.common import i18n
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.events import MUCNicknameChanged
from gajim.common.ged import EventHelper
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.util.status import compare_show
from gajim.common.util.user_strings import get_uf_affiliation
from gajim.common.util.user_strings import get_uf_role

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_groupchat_participant_menu
from gajim.gtk.structs import AddChatActionParams
from gajim.gtk.tooltips import GCTooltip
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.misc import scroll_to
from gajim.gtk.widgets import GajimPopover

log = logging.getLogger("gajim.gtk.groupchat_roster")

binds = 0
AffiliationRoleSortOrder = {
    "owner": 0,
    "admin": 1,
    "moderator": 2,
    "participant": 3,
    "visitor": 4,
}


CONTACT_SIGNALS = {
    "user-affiliation-changed",
    "user-joined",
    "user-left",
    "user-nickname-changed",
    "user-role-changed",
    "user-status-show-changed",
}


def get_group_from_contact(contact: types.GroupchatParticipant) -> tuple[str, str]:
    if contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
        return contact.affiliation.value, get_uf_affiliation(
            contact.affiliation, plural=True
        )
    return contact.role.value, get_uf_role(contact.role, plural=True)


class GroupchatRoster(Gtk.Revealer, EventHelper):
    __gtype_name__ = "GroupchatRoster"

    def __init__(self) -> None:
        Gtk.Revealer.__init__(self)
        EventHelper.__init__(self)
        self.set_name("GroupchatRoster")

        self._contact = None
        self._scroll_id = None

        self._ui = get_builder("groupchat_roster.ui")
        self.set_child(self._ui.box)

        self._contact_view = GroupchatContactListView()
        self._contact_view.connect("activate", self._on_contact_item_activated)
        self._contact_view.set_size_request(
            app.settings.get("groupchat_roster_width"), -1
        )
        self._ui.scrolled.set_child(self._contact_view)

        self.set_reveal_child(not app.settings.get("hide_groupchat_occupants_list"))
        self.connect("notify::reveal-child", self._on_reveal)

        self._ui.search_entry.connect("search-changed", self._on_search_changed)
        self._ui.search_entry.connect(
            "stop-search",
            lambda *args: self._ui.search_entry.set_text(""),
        )

        self.bind_property(
            "total-count",
            self._ui.participants_count_label,
            "label",
            GObject.BindingFlags.SYNC_CREATE,
            transform_to=self._transform_count_to_label,
        )

    @GObject.Property(type=int)
    def total_count(self) -> int:
        return self._contact_view.get_count()

    @staticmethod
    def _transform_count_to_label(binding: GObject.Binding, count: int) -> str:
        return i18n.ngettext(
            "%(count)s Participant", "%(count)s Participants", count
        ) % {"count": count}

    def _hide_roster(self, hide_roster: bool, *args: Any) -> None:
        transition = Gtk.RevealerTransitionType.SLIDE_RIGHT
        if not hide_roster:
            transition = Gtk.RevealerTransitionType.SLIDE_LEFT

        self.set_transition_type(transition)
        self.set_reveal_child(not hide_roster)
        self.set_visible(not hide_roster)

    def _on_reveal(self, revealer: Gtk.Revealer, param: Any) -> None:
        if self._contact is None:
            return

        if revealer.get_reveal_child():
            self._load_roster()
        else:
            self._unload_roster()

    def clear(self) -> None:
        if self._contact is None:
            return

        log.info("Clear")
        self._unload_roster()
        app.settings.disconnect_signals(self)
        self._contact.disconnect_signal(self, "state-changed")
        self._contact = None

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self.clear()

        is_groupchat = isinstance(contact, GroupchatContact)
        hide_roster = app.settings.get("hide_groupchat_occupants_list")
        self.set_visible(is_groupchat and not hide_roster)
        if not is_groupchat:
            return

        log.info("Switch to %s (%s)", contact.jid, contact.account)

        contact.connect("state-changed", self._on_muc_state_changed)
        app.settings.connect_signal("hide_groupchat_occupants_list", self._hide_roster)

        self._contact = contact

        if self._contact.is_joined:
            self._load_roster()

    def _load_roster(self) -> None:
        if not self.get_reveal_child():
            return

        log.info("Load Roster")
        assert self._contact is not None
        self._contact.multi_connect(
            {
                "user-joined": self._on_contact_changed,
                "user-left": self._on_contact_changed,
                "user-nickname-changed": self._on_user_nickname_changed,
                "user-affiliation-changed": self._on_contact_changed,
                "user-role-changed": self._on_contact_changed,
                "user-status-show-changed": self._on_contact_changed,
            }
        )

        self._contact_view.unbind_model()
        self._ui.search_entry.set_text("")

        # Convert (copy) participants iterator to list,
        # since it may change during iteration, see #11970
        for participant in list(self._contact.get_participants()):
            self._add_contact(participant)

        self._contact_view.bind_model()
        self.notify("total-count")

        # GTK Bug: ListView does not fully scroll to top when headers are used
        GLib.idle_add(scroll_to, self._ui.scrolled, "top")

    def _unload_roster(self) -> None:
        log.info("Unload Roster")
        self._contact_view.unbind_model()
        self._contact_view.remove_all()
        self.notify("total-count")

        assert self._contact is not None
        self._contact.multi_disconnect(self, CONTACT_SIGNALS)

    def _on_contact_item_activated(
        self,
        _list_view: Gtk.ListView,
        position: int,
    ) -> None:
        item = self._contact_view.get_listitem(position)
        assert item is not None

        participant_contact = item.contact
        if participant_contact.is_self:
            return

        assert self._contact is not None
        disco = self._contact.get_disco()
        assert disco is not None

        muc_prefer_direct_msg = app.settings.get("muc_prefer_direct_msg")
        if (
            disco.muc_is_nonanonymous
            and muc_prefer_direct_msg
            and participant_contact.real_jid is not None
        ):
            dm_params = AddChatActionParams(
                account=self._contact.account,
                jid=participant_contact.real_jid,
                type="chat",
                select=True,
            )
        else:
            dm_params = AddChatActionParams(
                account=self._contact.account,
                jid=participant_contact.jid,
                type="pm",
                select=True,
            )

        app.window.activate_action("win.add-chat", dm_params.to_variant())

    def _on_search_changed(self, widget: Gtk.SearchEntry) -> None:
        self._contact_view.set_search(widget.get_text())
        self._scroll_to_top()

    def _scroll_to_top(self) -> None:
        # Cancel any active source at first so we dont have
        # multiple timeouts running
        if self._scroll_id is not None:
            GLib.source_remove(self._scroll_id)
            self._scroll_id = None

        def _scroll_to() -> None:
            self._scroll_id = None
            self._ui.scrolled.get_vadjustment().set_value(0)

        self._scroll_id = GLib.timeout_add(100, _scroll_to)

    def _add_contact(
        self, contact: types.GroupchatParticipant, notify: bool = False
    ) -> None:
        item = GroupchatContactListItem(contact=contact)
        self._contact_view.add(item)
        if notify:
            self.notify("total-count")

    def _remove_contact(
        self, contact: types.GroupchatParticipant, notify: bool = False
    ) -> None:
        self._contact_view.remove(contact)
        if notify:
            self.notify("total-count")

    def _on_contact_changed(
        self,
        _contact: types.GroupchatContact,
        signal_name: str,
        user_contact: types.GroupchatParticipant,
        *args: Any,
    ) -> None:
        if signal_name == "user-joined":
            self._add_contact(user_contact, notify=True)

        elif signal_name == "user-left":
            self._remove_contact(user_contact, notify=True)

        else:
            self._remove_contact(user_contact)
            self._add_contact(user_contact)

    def _on_user_nickname_changed(
        self,
        _contact: types.GroupchatContact,
        _signal_name: str,
        _event: MUCNicknameChanged,
        old_contact: types.GroupchatParticipant,
        new_contact: types.GroupchatParticipant,
    ) -> None:
        self._remove_contact(old_contact)
        self._add_contact(new_contact)

    def _on_muc_state_changed(
        self, contact: GroupchatContact, _signal_name: str
    ) -> None:
        if contact.is_joined:
            self._load_roster()

        elif contact.is_not_joined:
            self._unload_roster()

    def invalidate_sort(self) -> None:
        self._contact_view.invalidate_sort()


class GroupchatContactListView(Gtk.ListView):
    def __init__(self) -> None:
        Gtk.ListView.__init__(self)

        self._model = Gio.ListStore(item_type=GroupchatContactListItem)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup, GroupchatContactViewItem)
        factory.connect("bind", self._on_factory_bind)
        factory.connect("unbind", self._on_factory_unbind)
        self.set_factory(factory)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup, GroupchatContactHeaderViewItem)
        factory.connect("bind", self._on_factory_bind)
        self.set_header_factory(factory)

        expression = Gtk.PropertyExpression.new(
            this_type=GroupchatContactListItem,
            expression=None,
            property_name="nick",
        )
        self._string_filter = Gtk.StringFilter(expression=expression)

        section_sorter = Gtk.CustomSorter.new(sort_func=self._section_sort_func)
        self._sorter = Gtk.CustomSorter.new(sort_func=self._sort_func)

        self._sort_model = Gtk.SortListModel(
            model=self._model, sorter=self._sorter, section_sorter=section_sorter
        )
        self._filter_model = Gtk.FilterListModel(
            model=self._sort_model, filter=self._string_filter
        )

        self._selection_model = Gtk.NoSelection(
            model=self._filter_model,
        )
        self.set_model(self._selection_model)

    def invalidate_sort(self) -> None:
        self.unbind_model()
        self.bind_model()

    def bind_model(self) -> None:
        if self._sort_model.get_model() is not None:
            return
        self._sort_model.set_model(self._model)

    def unbind_model(self) -> None:
        self._sort_model.set_model(None)

    def get_count(self) -> int:
        return self._model.get_n_items()

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, view_item: Any
    ) -> None:
        list_item.set_child(view_item())

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = list_item.get_child()
        obj = list_item.get_item()
        if isinstance(view_item, GroupchatContactHeaderViewItem):
            assert isinstance(obj, GroupchatContactListItem)
            view_item.set_data(obj.group, obj.group_label)
        else:
            view_item.bind(obj)  # pyright: ignore

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = list_item.get_child()
        view_item.unbind()  # pyright: ignore

    @staticmethod
    def _section_sort_func(
        obj1: Any,
        obj2: Any,
        _user_data: object | None,
    ) -> int:
        group1_index = AffiliationRoleSortOrder[obj1.group]
        group2_index = AffiliationRoleSortOrder[obj2.group]
        if group1_index == group2_index:
            return 0
        return -1 if group1_index < group2_index else 1

    @staticmethod
    def _sort_func(
        obj1: Any,
        obj2: Any,
        _user_data: object | None,
    ) -> int:
        if obj1.contact.is_self or obj2.contact.is_self:
            return -1 if obj1.contact.is_self else 1

        if app.settings.get("sort_by_show_in_muc"):
            res = compare_show(obj1.contact.show, obj2.contact.show)
            if res != 0:
                return res

        return locale.strcoll(obj1.nick.lower(), obj2.nick.lower())

    def add(self, item: GroupchatContactListItem) -> None:
        self._model.append(item)

    def remove(self, contact: GroupchatParticipant) -> None:
        for item in self._model:
            assert isinstance(item, GroupchatContactListItem)
            if item.contact != contact:
                continue
            success, pos = self._model.find(item)
            if success:
                self._model.remove(pos)
            break

    def remove_all(self) -> None:
        self._model.remove_all()

    def get_listitem(self, position: int) -> GroupchatContactListItem:
        return cast(GroupchatContactListItem, self._filter_model.get_item(position))

    def set_search(self, text: str) -> None:
        self._string_filter.set_search(text)


class GroupchatContactListItem(GObject.Object):
    __gtype_name__ = "GroupchatContactListItem"

    contact = GObject.Property(type=object)
    nick = GObject.Property(type=str)
    group = GObject.Property(type=str)
    group_label = GObject.Property(type=str)
    status = GObject.Property(type=str)

    def __init__(self, contact: GroupchatParticipant) -> None:
        nick = contact.name
        if contact.is_self:
            nick = p_("own nickname in group chat", "%s (You)" % nick)

        status = ""
        if app.settings.get("show_status_msgs_in_roster"):
            status = contact.status

        group, group_label = get_group_from_contact(contact)
        super().__init__(
            contact=contact,
            nick=nick,
            group=group,
            group_label=group_label,
            status=status,
        )

    def __repr__(self) -> str:
        return f"GroupchatContactListItem: {self.nick}"


@Gtk.Template(string=get_ui_string("groupchat_contact_view_item.ui"))
class GroupchatContactViewItem(Gtk.Grid, SignalManager):
    __gtype_name__ = "GroupchatContactViewItem"

    _avatar: Gtk.Image = Gtk.Template.Child()
    _nick_label: Gtk.Label = Gtk.Template.Child()
    _status_message_label: Gtk.Label = Gtk.Template.Child()
    _hat_image: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Grid.__init__(self)
        SignalManager.__init__(self)

        self.__bindings: list[GObject.Binding] = []
        self._contact: GroupchatParticipant | None = None

        self._tooltip = GCTooltip()
        self._connect(self, "query-tooltip", self._query_tooltip)

        self._popover_menu = GajimPopover(None)
        self.attach(self._popover_menu, 4, 0, 1, 1)

        self._connect(
            self._status_message_label, "notify::label", self._on_status_change
        )

        gesture_secondary_click = Gtk.GestureClick(
            button=Gdk.BUTTON_SECONDARY, propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        self._connect(gesture_secondary_click, "pressed", self._popup_menu)
        self.add_controller(gesture_secondary_click)

    def bind(self, obj: GroupchatContactListItem) -> None:
        self._contact = obj.contact
        assert self._contact is not None

        bind_spec = [
            ("nick", self._nick_label, "label"),
            ("status", self._status_message_label, "label"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self.__bindings.append(bind)

        self._update_avatar(self._contact)
        self._update_hats(self._contact)

        self._contact.multi_connect(
            {
                "user-avatar-update": self._update_avatar,
                "user-hats-changed": self._update_hats,
            }
        )

    def unbind(self) -> None:
        assert self._contact is not None
        self._contact.disconnect_all_from_obj(self)
        self._contact = None
        for bind in self.__bindings:
            bind.unbind()
        self.__bindings.clear()

    def do_unroot(self) -> None:
        Gtk.Grid.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self._popover_menu)
        app.check_finalize(self._tooltip)
        del self._popover_menu
        del self._tooltip
        app.check_finalize(self)

    def _on_status_change(self, label: Gtk.Label, *args: Any) -> None:
        label.set_visible(bool(label.get_label()))

    def _update_avatar(self, contact: GroupchatParticipant, *args: Any) -> None:
        paintable = contact.get_avatar(AvatarSize.ROSTER, app.window.get_scale_factor())
        self._avatar.set_from_paintable(paintable)

    def _update_hats(self, contact: GroupchatParticipant, *args: Any) -> None:
        self._hat_image.set_visible(bool(contact.hats))

    def _popup_menu(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
        assert self._contact is not None
        participant = self._contact
        if participant.is_self:
            return

        self_contact = participant.room.get_self()
        assert self_contact is not None

        menu = get_groupchat_participant_menu(
            participant.account, self_contact, participant
        )

        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x, y)
        self._popover_menu.popup()

    def _query_tooltip(
        self,
        list_view: GroupchatContactListView,
        x: int,
        y: int,
        _keyboard_mode: bool,
        tooltip: Gtk.Tooltip,
    ) -> bool:
        assert self._contact is not None
        value, widget = self._tooltip.get_tooltip(self._contact)
        tooltip.set_custom(widget)
        return value


@Gtk.Template(string=get_ui_string("groupchat_contact_header_view_item.ui"))
class GroupchatContactHeaderViewItem(Gtk.Box):
    __gtype_name__ = "GroupchatContactHeaderViewItem"

    _group_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.Box.__init__(self)
        self.group = None

    def set_data(self, group: str, group_label: str) -> None:
        self._group_label.set_label(group_label)
        self.group = group

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)
