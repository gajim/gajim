# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.protocol import JID
from nbxmpp.structs import RosterItem

from gajim.common import app
from gajim.common import ged
from gajim.common.events import RosterPush
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.decorators import event_filter

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.menus import get_manage_roster_menu
from gajim.gtk.util import GajimPopover
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.manage_roster")


class ManageRoster(GajimAppWindow, EventHelper):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="ManageRoster",
            title=_("Manage Roster"),
            default_height=600,
            default_width=700,
            add_window_padding=False,
        )
        EventHelper.__init__(self)

        self.account = account
        self._ui = get_builder("manage_roster.ui")
        self.set_child(self._ui.box)

        self._model = Gio.ListStore(item_type=RosterListItem)

        h_factory = Gtk.SignalListItemFactory()
        self._connect(h_factory, "setup", self._on_h_factory_setup)
        self._connect(h_factory, "bind", self._on_h_factory_bind)
        self._connect(h_factory, "unbind", self._on_factory_unbind)
        self._ui.column_view.set_header_factory(h_factory)

        for _jid, item in app.get_client(account).get_module("Roster").iter():
            groups = item.groups or {"No Group"}
            for group in groups:
                self._model.append(RosterListItem(item, group))

        columns = [
            (self._ui.jid_col, RosterViewItemLabel, "jid"),
            (self._ui.name_col, RosterViewItemLabel, "name"),
            (self._ui.subscription_col, RosterViewItemImage, "subscription"),
            (self._ui.ask_col, RosterViewItemImage, "ask"),
        ]

        for col, widget, attr in columns:
            factory = col.get_factory()
            assert factory is not None
            self._connect(factory, "setup", self._on_factory_setup, widget)
            self._connect(factory, "bind", self._on_factory_bind, attr)
            self._connect(factory, "unbind", self._on_factory_unbind)

        expression = Gtk.PropertyExpression.new(
            this_type=RosterListItem,
            expression=None,
            property_name="group",
        )
        section_sorter = Gtk.StringSorter.new(expression=expression)

        expression = Gtk.PropertyExpression.new(
            this_type=RosterListItem,
            expression=None,
            property_name="jid",
        )
        sorter = Gtk.StringSorter.new(expression=expression)

        sort_model = Gtk.SortListModel(
            model=self._model, sorter=sorter, section_sorter=section_sorter
        )

        self._selection_model = Gtk.MultiSelection(model=sort_model)
        self._ui.column_view.set_model(self._selection_model)

        self._popover_menu = GajimPopover(None)
        self._ui.box.append(self._popover_menu)

        gesture_secondary_click = Gtk.GestureClick(
            button=Gdk.BUTTON_SECONDARY, propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        self._connect(gesture_secondary_click, "pressed", self._popup_menu)
        self._ui.box.add_controller(gesture_secondary_click)

        self.register_event("roster-push", ged.GUI2, self._on_roster_push)

        self._add_actions()
        self.show()

    def _cleanup(self, *args: Any) -> None:
        del self._selection_model
        del self._popover_menu
        del self._model
        self.unregister_events()

    def _add_actions(self) -> None:

        actions = [
            ("add-to-group", "s", self._on_add_to_group),
            ("add-to-new-group", None, self._on_add_to_new_group),
            ("move-to-group", "s", self._on_move_to_group),
            ("move-to-new-group", None, self._on_move_to_new_group),
            ("remove-from-group", None, self._remove_from_group),
            ("remove-from-roster", None, self._on_remove_from_roster),
            ("change-name", None, self._on_change_name),
        ]

        for action, variant_type, callback in actions:
            if variant_type is not None:
                variant_type = GLib.VariantType(variant_type)
            act = Gio.SimpleAction.new(action, variant_type)
            act.connect("activate", callback)
            self.window.add_action(act)

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, item_class: Any
    ) -> None:
        list_item.set_child(item_class())

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, attr: str
    ) -> None:
        roster_item = cast(RosterListItem, list_item.get_item())
        roster_view_item = cast(
            RosterViewItemLabel | RosterViewItemImage, list_item.get_child()
        )
        roster_view_item.bind(roster_item, attr)

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        roster_view_item = cast(
            RosterViewItemLabel | RosterViewItemImage, list_item.get_child()
        )
        roster_view_item.unbind()

    @staticmethod
    def _on_h_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        list_item.set_child(HeaderViewItem())

    @staticmethod
    def _on_h_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        roster_item = cast(RosterListItem, list_item.get_item())
        roster_view_item = cast(HeaderViewItem, list_item.get_child())
        roster_view_item.bind(roster_item)

    @staticmethod
    def _on_h_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        roster_view_item: HeaderViewItem = cast(HeaderViewItem, list_item.get_child())
        roster_view_item.unbind()

    @event_filter(["account"])
    def _on_roster_push(self, event: RosterPush) -> None:
        pos = 0
        while item := cast(RosterListItem, self._model.get_item(pos)):
            if item.jid == event.item.jid:
                self._model.remove(pos)
            else:
                pos += 1

        if event.item.subscription == "remove":
            return

        groups = event.item.groups or {"No Group"}
        for group in groups:
            self._model.append(RosterListItem(event.item, group))

    def _on_add_to_group(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        self._add_to_group(param.get_string())

    def _on_add_to_new_group(self, _action: Gio.SimpleAction, param: None) -> None:

        InputDialog(
            _("Choose group name"),
            "",
            "",
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Accept", text=_("OK"), callback=self._add_to_group),
            ],
            transient_for=self.window,
        ).show()

    def _add_to_group(self, group: str) -> None:
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        items = self.get_selected_items()

        for item in items:
            client.get_module("Roster").add_to_group(JID.from_string(item.jid), group)

    def _on_move_to_group(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        self._move_to_group(param.get_string())

    def _on_move_to_new_group(self, _action: Gio.SimpleAction, param: None) -> None:

        InputDialog(
            _("Choose group name"),
            "",
            "",
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Accept", text=_("OK"), callback=self._move_to_group),
            ],
            transient_for=self.window,
        ).show()

    def _move_to_group(self, group: str) -> None:
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        items = self.get_selected_items()

        for item in items:
            client.get_module("Roster").change_group(
                JID.from_string(item.jid), item.group, group
            )

    def _remove_from_group(self, _action: Gio.SimpleAction, param: None) -> None:
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        items = self.get_selected_items()

        for item in items:
            client.get_module("Roster").remove_from_group(
                JID.from_string(item.jid), item.group
            )

    def _on_remove_from_roster(self, _action: Gio.SimpleAction, param: None) -> None:
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        items = self.get_selected_items()

        # TODO Warning Dialog

        for item in items:
            client.get_module("Roster").delete_item(JID.from_string(item.jid))

    def _on_change_name(self, _action: Gio.SimpleAction, param: None) -> None:
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        item = self.get_selected_items()[0]

        def _on_change_name(name: str) -> None:
            client.get_module("Roster").change_name(JID.from_string(item.jid), name)

        InputDialog(
            _("Choose name"),
            "",
            "",
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Accept", text=_("OK"), callback=_on_change_name),
            ],
            input_str=item.name,
            transient_for=self.window,
        ).show()

    def get_selected_items(self) -> list[RosterListItem]:
        bitset = self._selection_model.get_selection()
        valid, iter_, value = Gtk.BitsetIter.init_first(bitset)

        items: list[RosterListItem] = []

        if not valid:
            return items

        items.append(cast(RosterListItem, self._selection_model.get_item(value)))

        while res := iter_.next():
            valid, value = res
            if not valid:
                break

            items.append(cast(RosterListItem, self._selection_model.get_item(value)))

        return items

    def _popup_menu(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> bool:

        items = self.get_selected_items()
        if not items:
            return Gdk.EVENT_STOP

        single_selection = len(items) == 1
        groups = app.get_client(self.account).get_module("Roster").get_groups()
        groups = sorted(groups)

        menu = get_manage_roster_menu(groups, single_selection)
        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x, y)
        self._popover_menu.popup()

        return Gdk.EVENT_STOP


class RosterListItem(GObject.Object):
    __gtype_name__ = "RosterListItem"

    jid = GObject.Property(type=str)
    name = GObject.Property(type=str)
    ask = GObject.Property(type=object)
    subscription = GObject.Property(type=object)
    group = GObject.Property(type=str)

    def __init__(self, item: RosterItem, group: str) -> None:

        subscription = self._get_subscription_data(item.subscription)
        ask = self._get_ask_data(item.ask)

        super().__init__(
            jid=str(item.jid),
            name=item.name,
            ask=ask,
            subscription=subscription,
            group=group,
        )

    def _get_subscription_data(self, subscription: str | None) -> tuple[str, str, str]:
        match subscription:
            case "both":
                return ("lucide-arrow-right-left-symbolic", "success-color", "both")
            case "to":
                return ("lucide-arrow-right-symbolic", "warning-color", "to")
            case "from":
                return ("lucide-arrow-left-symbolic", "info-color", "from")
            case "none":
                return ("lucide-x-symbolic", "error-color", "none")
            case _:
                raise ValueError("Invalid value: %s" % subscription)

    def _get_ask_data(
        self, ask: str | None
    ) -> tuple[str | None, str | None, str | None]:
        match ask:
            case None:
                return (None, None, None)
            case "subscribe":
                return ("feather-clock-symbolic", None, "pending")
            case _:
                raise ValueError("Invalid value: %s" % ask)

    def __repr__(self) -> str:
        return f"RosterListItem: {self.props.jid} {self.props.name}"


class RosterViewItemLabel(Gtk.Label):
    __gtype_name__ = "RosterViewItemLabel"

    def __init__(self) -> None:
        Gtk.Label.__init__(
            self,
            ellipsize=Pango.EllipsizeMode.END,
            width_chars=20,
            xalign=0,
        )

        self.__bindings: list[GObject.Binding] = []

    def bind(self, obj: RosterListItem, attr: str) -> None:
        bind_spec = [
            (attr, self, "label"),
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
        Gtk.Label.do_unroot(self)
        app.check_finalize(self)


class RosterViewItemImage(Gtk.Image):
    __gtype_name__ = "RosterViewItemImage"

    def __init__(self) -> None:
        Gtk.Image.__init__(
            self,
            pixel_size=16,
        )

        self._icon_data = ("", "", "")
        self.__bindings: list[GObject.Binding] = []

    @GObject.Property(type=object)
    def icon_data(self) -> tuple[str | None, str | None, str | None]:  # pyright: ignore
        return self._icon_data

    @icon_data.setter
    def icon_data(self, value: tuple[str | None, str | None, str | None]) -> None:
        self._icon_data = value
        icon_name, css_class, tooltip = value

        self.set_from_icon_name(icon_name)
        self.set_tooltip_text(tooltip)

        self.remove_css_class("success-color")
        self.remove_css_class("warning-color")
        self.remove_css_class("error-color")
        self.remove_css_class("info-color")
        if css_class is not None:
            self.add_css_class(css_class)

    def bind(self, obj: RosterListItem, attr: str) -> None:
        bind_spec = [
            (attr, self, "icon-data"),
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
        Gtk.Image.do_unroot(self)
        app.check_finalize(self)


class HeaderViewItem(Gtk.Label):
    __gtype_name__ = "HeaderViewItem"

    def __init__(self) -> None:
        Gtk.Label.__init__(
            self,
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.START,
            xalign=0,
        )

        self.__bindings: list[GObject.Binding] = []

    def bind(self, obj: RosterListItem) -> None:
        bind_spec = [
            ("group", self, "label"),
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
        Gtk.Label.do_unroot(self)
        app.check_finalize(self)
