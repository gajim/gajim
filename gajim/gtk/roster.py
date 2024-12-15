# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal

import locale
import logging
from collections import defaultdict
from enum import IntEnum

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import PresenceShow
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import PresenceShowExt
from gajim.common.const import StyleAttr
from gajim.common.events import ApplicationEvent
from gajim.common.events import RosterPush
from gajim.common.events import RosterReceived
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.decorators import event_filter

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.menus import get_roster_menu
from gajim.gtk.tooltips import ContactTooltip
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import open_window
from gajim.gtk.util import SignalManager

log = logging.getLogger("gajim.gtk.roster")


DEFAULT_GROUP = _("Contacts")


class Column(IntEnum):
    AVATAR = 0
    TEXT = 1
    IS_CONTACT = 2
    JID_OR_GROUP = 3
    VISIBLE = 4


class Roster(Gtk.ScrolledWindow, EventHelper, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.ScrolledWindow.__init__(self, width_request=200, vexpand=True)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self.add_css_class("roster")

        self._account = account
        self._client = app.get_client(account)
        self._contacts = self._client.get_module("Contacts")

        self._roster_tooltip = ContactTooltip()

        self._ui = get_builder("roster.ui")
        self._ui.roster_treeview.set_model(None)

        box = Gtk.Box()
        box.append(self._ui.roster_treeview)
        self.set_child(box)

        self._popover_menu = GajimPopover(None)
        self._connect(self._popover_menu, "closed", self._on_popover_menu_closed)
        box.append(self._popover_menu)

        gesture_middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        self._connect(gesture_middle_click, "pressed", self._on_row_clicked)
        self._ui.roster_treeview.add_controller(gesture_middle_click)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_row_clicked)
        self._ui.roster_treeview.add_controller(gesture_secondary_click)

        focus_controller = Gtk.EventControllerFocus()
        self._connect(focus_controller, "leave", self._on_focus_out)
        self._ui.roster_treeview.add_controller(focus_controller)

        self._connect(
            self._ui.roster_treeview, "row-activated", self._on_roster_row_activated
        )

        self._contact_refs: dict[JID, list[Gtk.TreeRowReference]] = defaultdict(list)
        self._group_refs: dict[str, Gtk.TreeRowReference] = {}

        self._store = Gtk.TreeStore(Gdk.Texture, str, bool, str, bool)
        self._store.set_sort_func(Column.TEXT, self._tree_compare_iters)

        self._roster = self._ui.roster_treeview
        self._roster.set_has_tooltip(True)
        self._connect(self._roster, "query-tooltip", self._on_query_tooltip)

        # TODO port roster to Gtk.ListView and add back drag and drop
        # entries = [Gtk.TargetEntry.new(
        #     'ROSTER_ITEM',
        #     Gtk.TargetFlags.SAME_APP,
        #     0)]
        # self._roster.enable_model_drag_source(
        #     Gdk.ModifierType.BUTTON1_MASK,
        #     entries,
        #     Gdk.DragAction.MOVE)
        # self._roster.enable_model_drag_dest(entries, Gdk.DragAction.DEFAULT)
        # self._roster.connect('drag-drop', self._on_drag_drop)
        # self._roster.connect('drag-data-received', self._on_drag_data_received)

        self._ui.contact_column.set_cell_data_func(
            self._ui.text_renderer, self._text_cell_data_func
        )

        self.register_events(
            [
                ("roster-received", ged.CORE, self._on_roster_received),
                ("theme-update", ged.GUI2, self._on_theme_update),
                ("roster-push", ged.GUI2, self._on_roster_push),
            ]
        )

        roster_size = self._client.get_module("Roster").get_size()
        self._high_performance = roster_size > 1000

        self._modelfilter = self._store.filter_new()
        if self._high_performance:
            self._modelfilter.set_visible_func(self._visible_func)
        else:
            self._modelfilter.set_visible_column(Column.VISIBLE)
        self._filter_enabled = False
        self._filter_string = ""

        app.settings.connect_signal("showoffline", self._on_setting_changed)
        app.settings.connect_signal("sort_by_show_in_roster", self._on_setting_changed)

        self._connect_actions()
        self._initial_draw()

    def _connect_actions(self) -> None:
        app_actions = [
            (f"{self._account}-contact-info", self._on_contact_info),
            (f"{self._account}-modify-gateway", self._on_modify_gateway),
            (f"{self._account}-execute-command", self._on_execute_command),
            (f"{self._account}-block-contact", self._on_block_contact),
            (f"{self._account}-remove-contact", self._on_remove_contact),
        ]

        for action in app_actions:
            action_name, func = action
            action = app.app.lookup_action(action_name)
            assert action is not None
            self._connect(action, "activate", func)

    def _get_contact(self, jid: str) -> BareContact:
        contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, BareContact)
        return contact

    def _on_theme_update(self, _event: ApplicationEvent) -> None:
        self.redraw()

    # @staticmethod
    # def _on_drag_drop(treeview: Gtk.TreeView,
    #                   drag_context: Any,
    #                   _x_coord: int,
    #                   _y_coord: int,
    #                   timestamp: int) -> bool:

    #     treeview.stop_emission_by_name('drag-drop')
    #     target_list = treeview.drag_dest_get_target_list()
    #     target = treeview.drag_dest_find_target(drag_context, target_list)
    #     treeview.drag_get_data(drag_context, target, timestamp)
    #     return True

    # def _on_drag_data_received(self,
    #                            treeview: Gtk.TreeView,
    #                            _drag_context: Any,
    #                            x_coord: int,
    #                            y_coord: int,
    #                            _selection_data: Any,
    #                            _info: int,
    #                            _timestamp: int) -> None:

    #     treeview.stop_emission_by_name('drag-data-received')
    #     if treeview.get_selection().count_selected_rows() == 0:
    #         # No selections, nothing dragged from treeview
    #         return

    #     drop_info = treeview.get_dest_row_at_pos(x_coord, y_coord)
    #     if not drop_info:
    #         return

    #     path_dest, _ = drop_info

    #     # Source: the row being dragged
    #     rows = treeview.get_selection().get_selected_rows()
    #     assert rows is not None
    #     model, paths = rows
    #     path_source = paths[0]
    #     iter_source = model.get_iter(path_source)
    #     iter_source_parent = model.iter_parent(iter_source)
    #     if iter_source_parent is None:
    #         # Dragged a group
    #         return

    #     source_group = model[iter_source_parent][Column.JID_OR_GROUP]

    #     jid = model[iter_source][Column.JID_OR_GROUP]

    #     # Destination: the row receiving the drop
    #     iter_dest = model.get_iter(path_dest)
    #     iter_dest_parent = model.iter_parent(iter_dest)
    #     if iter_dest_parent is None:
    #         # Dropped on a group
    #         dest_group = model[iter_dest][Column.JID_OR_GROUP]
    #     else:
    #         dest_group = model[iter_dest_parent][Column.JID_OR_GROUP]

    #     if source_group == dest_group:
    #         return

    #     if DEFAULT_GROUP == dest_group:
    #         self._client.get_module('Roster').set_groups(jid, None)
    #         return

    #     self._client.get_module('Roster').change_group(jid,
    #                                                    source_group,
    #                                                    dest_group)

    def _on_query_tooltip(
        self,
        treeview: Gtk.TreeView,
        x_coord: int,
        y_coord: int,
        _keyboard_mode: bool,
        tooltip: Gtk.Tooltip,
    ) -> bool:

        row = treeview.get_path_at_pos(x_coord, y_coord)
        if row is None:
            self._roster_tooltip.clear_tooltip()
            return False

        path = row[0]
        if path is None:
            self._roster_tooltip.clear_tooltip()
            return False

        model = treeview.get_model()
        if model is None:
            self._roster_tooltip.clear_tooltip()
            return False

        iter_ = model.get_iter(path)
        if not model[iter_][Column.IS_CONTACT]:
            # It’s a group
            self._roster_tooltip.clear_tooltip()
            return False

        contact = self._contacts.get_bare_contact(model[iter_][Column.JID_OR_GROUP])
        assert isinstance(contact, BareContact)
        value, widget = self._roster_tooltip.get_tooltip(contact)
        tooltip.set_custom(widget)
        return value

    def _on_setting_changed(self, *args: Any) -> None:
        self._refilter()

    def _on_contact_info(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:

        app.window.contact_info(self._account, param.get_string())

    def _on_modify_gateway(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        open_window(
            "ServiceRegistration",
            account=self._account,
            address=JID.from_string(param.get_string()),
        )

    def _on_execute_command(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:

        app.window.execute_command(self._account, param.get_strv())

    def _on_block_contact(self, _action: Gio.SimpleAction, param: GLib.Variant):

        app.window.block_contact(self._account, param.get_string())

    def _on_remove_contact(self, _action: Gio.SimpleAction, param: GLib.Variant):

        jid = JID.from_string(param.get_string())
        selected_contact = self._contacts.get_contact(jid)
        assert isinstance(selected_contact, BareContact)
        if selected_contact.is_gateway:
            # Check for transport users in roster and warn about removing the
            # transport if there are any
            has_transport_contacts = False
            for contact in self._client.get_module("Roster").iter_contacts():
                if contact.jid.domain == selected_contact.jid.domain:
                    has_transport_contacts = True
                    break

            def _on_remove():
                self._client.get_module("Gateway").unsubscribe(
                    str(selected_contact.jid)
                )

            if has_transport_contacts:
                ConfirmationDialog(
                    _("Remove Transport"),
                    _('Transport "%s" will be ' "removed") % selected_contact.name,
                    _(
                        "You will no longer be able to send and receive "
                        "messages from and to contacts using this transport."
                    ),
                    [
                        DialogButton.make("Cancel"),
                        DialogButton.make("Remove", callback=_on_remove),
                    ],
                    transient_for=app.window,
                ).show()
            else:
                _on_remove()
            return

        app.window.remove_contact(self._account, jid)

    def _on_roster_row_activated(
        self, _treeview: Gtk.TreeView, path: Gtk.TreePath, _column: Gtk.TreeViewColumn
    ) -> None:

        converted_path = self._modelfilter.convert_path_to_child_path(path)
        assert converted_path is not None
        iter_ = self._store.get_iter(converted_path)
        if self._store.iter_parent(iter_) is None:
            # This is a group row
            return

        jid = JID.from_string(self._store[iter_][Column.JID_OR_GROUP])
        app.window.add_chat(self._account, jid, "contact", select=True)

    def _on_row_clicked(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        pos = self._roster.get_path_at_pos(int(x), int(y))
        if pos is None:
            return Gdk.EVENT_PROPAGATE

        path, _, _, _ = pos
        if path is None:
            return Gdk.EVENT_PROPAGATE

        path = self._modelfilter.convert_path_to_child_path(path)
        assert path is not None
        iter_ = self._store.get_iter(path)
        if self._store.iter_parent(iter_) is None:
            # Group row
            return Gdk.EVENT_PROPAGATE

        jid = self._store[iter_][Column.JID_OR_GROUP]

        if gesture_click.get_current_button() == Gdk.BUTTON_SECONDARY:
            self._show_contact_menu(jid, x, y)
            return Gdk.EVENT_STOP

        jid = JID.from_string(jid)
        if gesture_click.get_current_button() == Gdk.BUTTON_MIDDLE:
            app.window.add_chat(self._account, jid, "contact", select=True)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _show_contact_menu(self, jid: str, x: float, y: float) -> None:
        contact = self._contacts.get_bare_contact(jid)
        assert isinstance(contact, BareContact)
        gateway_register = contact.is_gateway and contact.supports(Namespace.REGISTER)

        menu = get_roster_menu(self._account, contact, gateway=gateway_register)
        self._popover_menu.set_menu_model(menu)
        self._popover_menu.set_pointing_to_coord(x, y)
        self._popover_menu.popup()
        self._popover_menu_open = True

    def _on_popover_menu_closed(self, _popover: GajimPopover) -> None:
        self._popover_menu_open = False
        self._roster.get_selection().unselect_all()

    def _on_focus_out(self, _event_controller_focus: Gtk.EventControllerFocus) -> None:
        if not self._popover_menu:
            self._roster.get_selection().unselect_all()

    def set_search_string(self, text: str) -> None:
        self._filter_string = text.lower()
        self._filter_enabled = bool(text)
        self._refilter()

    def _visible_func(
        self, model: Gtk.TreeModelFilter, iter_: Gtk.TreeIter, *_data: Any
    ) -> bool:

        if not self._filter_enabled:
            return True

        if not model[iter_][Column.IS_CONTACT]:
            return True

        return self._filter_string in model[iter_][Column.TEXT].lower()

    def _get_contact_visible(self, contact: BareContact) -> bool:
        if self._filter_enabled:
            return self._filter_string in contact.name.lower()

        if app.settings.get("showoffline"):
            return True

        return contact.show is not PresenceShowExt.OFFLINE

    def _set_model(self) -> None:
        self._roster.set_model(self._modelfilter)

    def _unset_model(self) -> None:
        self._roster.set_model(None)

    def redraw(self) -> None:
        self._unset_model()
        self._set_model()
        self._roster.expand_all()

    def _reset_roster(self) -> None:
        self._unset_model()
        self._enable_sort(False)
        self._clear()
        self._initial_draw()

    def _enable_sort(self, enable: bool) -> None:
        column = Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID
        if enable:
            column = Column.TEXT

        self._store.set_sort_column_id(column, Gtk.SortType.ASCENDING)

    def _initial_draw(self) -> None:
        for contact in self._client.get_module("Roster").iter_contacts():
            self._add_or_update_contact(contact)

        self._enable_sort(True)
        self._set_model()
        self._roster.expand_all()

    def _connect_contact_signals(self, contact: BareContact) -> None:
        contact.connect("presence-update", self._on_contact_update)
        contact.connect("caps-update", self._on_contact_update)
        contact.connect("avatar-update", self._on_contact_update)
        contact.connect("blocking-update", self._on_contact_update)

    def _on_contact_update(self, contact: BareContact, _signal_name: str) -> None:

        self._draw_contact(contact)

    @event_filter(["account"])
    def _on_roster_received(self, _event: RosterReceived) -> None:
        self._reset_roster()

    @event_filter(["account"])
    def _on_roster_push(self, event: RosterPush) -> None:
        contact = self._contacts.get_contact(str(event.item.jid))
        assert isinstance(contact, BareContact)

        if event.item.subscription == "remove":
            self._remove_contact(contact)
        else:
            self._add_or_update_contact(contact)

    def _get_current_groups(self, jid: JID) -> set[str]:
        groups: set[str] = set()
        for ref in self._contact_refs[jid]:
            iter_ = self._get_iter_from_ref(ref)
            group_iter = self._store.iter_parent(iter_)
            assert group_iter is not None
            groups.add(self._store[group_iter][Column.JID_OR_GROUP])
        return groups

    def _add_group(self, group_name: str) -> Gtk.TreeIter:
        group_iter = self._get_group_iter(group_name)
        if group_iter is not None:
            return group_iter

        group_iter = self._store.append(
            None, [None, group_name, False, group_name, True]
        )
        group_path = self._store.get_path(group_iter)
        group_ref = Gtk.TreeRowReference(self._store, group_path)
        self._group_refs[group_name] = group_ref
        return group_iter

    def _add_contact_to_group(self, contact: BareContact, group: str) -> None:

        group_iter = self._add_group(group)
        iter_ = self._store.append(
            group_iter, [None, contact.name, True, str(contact.jid), True]
        )

        ref = Gtk.TreeRowReference(self._store, self._store.get_path(iter_))
        self._contact_refs[contact.jid].append(ref)

    def _add_contact_to_groups(self, contact: BareContact, groups: set[str]) -> None:
        for group in groups:
            self._add_contact_to_group(contact, group)

    def _remove_contact_from_groups(
        self, contact: BareContact, groups: set[str]
    ) -> None:
        if not groups:
            return

        refs = self._contact_refs[contact.jid]
        for ref in refs:
            iter_ = self._get_iter_from_ref(ref)
            group_iter = self._store.iter_parent(iter_)
            assert group_iter is not None
            group = self._store[group_iter][Column.JID_OR_GROUP]
            if group in groups:
                path = ref.get_path()
                assert path is not None
                iter_ = self._store.get_iter(path)
                self._store.remove(iter_)
                self._contact_refs[contact.jid].remove(ref)

        self._check_for_empty_groups()

    def _remove_contact(self, contact: BareContact) -> None:
        contact.disconnect(self)
        refs = self._contact_refs.pop(contact.jid)
        for ref in refs:
            iter_ = self._get_iter_from_ref(ref)
            self._store.remove(iter_)

        self._check_for_empty_groups()

    def _check_for_empty_groups(self) -> None:
        for ref in list(self._group_refs.values()):
            group_iter = self._get_iter_from_ref(ref)
            if self._store.iter_has_child(group_iter):
                continue
            group = self._store[group_iter][Column.JID_OR_GROUP]
            self._store.remove(group_iter)
            del self._group_refs[group]

    def _add_or_update_contact(self, contact: BareContact) -> None:
        self._connect_contact_signals(contact)
        new_groups = set(contact.groups or [DEFAULT_GROUP])
        groups = self._get_current_groups(contact.jid)

        add_to_groups = new_groups - groups
        remove_from_groups = groups - new_groups

        self._add_contact_to_groups(contact, add_to_groups)
        self._remove_contact_from_groups(contact, remove_from_groups)

        self._draw_groups()
        self._draw_contact(contact)

    def _draw_groups(self) -> None:
        for group in self._group_refs:
            self._draw_group(group)

    def _draw_group(self, group_name: str) -> None:
        group_iter = self._get_group_iter(group_name)
        if not group_iter:
            return

        if self._roster.get_model() is not None:
            group_path = self._store.get_path(group_iter)
            self._roster.expand_row(group_path, False)

        total_users = self._get_total_user_count()
        group_users = self._store.iter_n_children(group_iter)
        group_name += f" ({group_users}/{total_users})"

        self._store[group_iter][Column.TEXT] = group_name

    def _refilter(self) -> None:
        if self._high_performance:
            self._modelfilter.refilter()
            self._roster.expand_all()
            return

        for group in self._store:
            group_is_visible = False
            for child in group.iterchildren():
                contact = self._contacts.get_bare_contact(child[Column.JID_OR_GROUP])
                assert isinstance(contact, BareContact)
                is_visible = self._get_contact_visible(contact)
                child[Column.VISIBLE] = is_visible
                if is_visible:
                    group_is_visible = True

            group[Column.VISIBLE] = group_is_visible
        self._roster.expand_all()

    def _draw_contact(self, contact: BareContact) -> None:
        for ref in self._contact_refs[contact.jid]:
            self._draw_contact_row(ref, contact)
        self._roster.expand_all()

    def _draw_contact_row(self, ref: Gtk.TreeRowReference, contact: BareContact):

        iter_ = self._get_iter_from_ref(ref)

        name = GLib.markup_escape_text(contact.name)
        if contact.is_blocked:
            name = f'<span strikethrough="true">{name}</span>'
        self._store[iter_][Column.TEXT] = name

        texture = contact.get_avatar(AvatarSize.ROSTER, 1)
        self._store[iter_][Column.AVATAR] = texture
        self._store[iter_][Column.VISIBLE] = self._get_contact_visible(contact)

    def _get_total_user_count(self) -> int:
        count = 0
        for group_row in self._store:
            count += self._store.iter_n_children(group_row.iter)
        return count

    def _get_iter_from_ref(self, ref: Gtk.TreeRowReference) -> Gtk.TreeIter:
        path = ref.get_path()
        assert path is not None
        return self._store.get_iter(path)

    def _get_group_iter(self, group_name: str) -> Gtk.TreeIter | None:
        try:
            ref = self._group_refs[group_name]
        except KeyError:
            return None

        path = ref.get_path()
        if path is None:
            return None
        return self._store.get_iter(path)

    @staticmethod
    def _text_cell_data_func(
        _column: Gtk.TreeViewColumn,
        renderer: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        _user_data: Literal[None],
    ) -> None:

        has_parent = bool(model.iter_parent(iter_))
        style = "contact" if has_parent else "group"

        bgcolor = app.css_config.get_value(f".gajim-{style}-row", StyleAttr.BACKGROUND)
        renderer.set_property("cell-background", bgcolor)

        color = app.css_config.get_value(f".gajim-{style}-row", StyleAttr.COLOR)
        renderer.set_property("foreground", color)

        desc = app.css_config.get_font(f".gajim-{style}-row")
        renderer.set_property("font-desc", desc)

        if not has_parent:
            renderer.set_property("weight", 600)
            renderer.set_property("ypad", 6)

    def _tree_compare_iters(
        self,
        model: Gtk.TreeModel,
        iter1: Gtk.TreeIter,
        iter2: Gtk.TreeIter,
        _user_data: Literal[None],
    ) -> int:
        """
        Compare two iterators to sort them
        """

        is_contact = model.iter_parent(iter1)
        if is_contact:
            name1 = model[iter1][Column.TEXT]
            name2 = model[iter2][Column.TEXT]

            if not app.settings.get("sort_by_show_in_roster"):
                return locale.strcoll(name1.lower(), name2.lower())

            contact1 = self._contacts.get_bare_contact(
                model[iter1][Column.JID_OR_GROUP]
            )
            assert isinstance(contact1, BareContact)
            contact2 = self._contacts.get_bare_contact(
                model[iter2][Column.JID_OR_GROUP]
            )
            assert isinstance(contact2, BareContact)

            if contact1.show != contact2.show:
                if contact1.show == PresenceShow.DND:
                    return 1
                if contact2.show == PresenceShow.DND:
                    return -1
                return -1 if contact1.show > contact2.show else 1

            return locale.strcoll(name1.lower(), name2.lower())

        # Group
        group1 = model[iter1][Column.JID_OR_GROUP]
        group2 = model[iter2][Column.JID_OR_GROUP]
        return -1 if group1 < group2 else 1

    def _clear(self):
        self._contact_refs.clear()
        self._group_refs.clear()
        self._store.clear()

    @staticmethod
    def _dummy_tree_compare(
        _model: Gtk.TreeModel,
        _iter1: Gtk.TreeIter,
        _iter2: Gtk.TreeIter,
        _user_data: Any,
    ) -> int:
        return 0

    def do_unroot(self) -> None:
        app.settings.disconnect_signals(self)
        self._disconnect_all()
        self.unregister_events()
        self._contact_refs.clear()
        self._group_refs.clear()
        self._unset_model()
        self._enable_sort(False)
        # Set dummy method, otherwise store will not get destroyed
        self._store.set_sort_func(Column.TEXT, self._dummy_tree_compare)
        self._store.clear()
        Gtk.ScrolledWindow.do_unroot(self)
        del self._roster
        del self._store
        del self._roster_tooltip
        del self._contacts
        app.check_finalize(self)
