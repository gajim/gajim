# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import locale

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.jid import validate_jid

from gajim.gtk.builder import get_builder
from gajim.gtk.contacts_flowbox import ContactsFlowBox
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import iterate_listbox_children
from gajim.gtk.widgets import AccountBadge


class ContactRow(Gtk.ListBoxRow):
    def __init__(
        self,
        account: str,
        contact: types.BareContact | None,
        jid: str,
        name: str,
        show_account: bool,
    ) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.add_css_class("start-chat-row")
        self.account = account
        self.jid = jid

        self._contact = contact
        self._name = name
        self._show_account = show_account

        self._account_label = app.get_account_label(account)
        self.is_new: bool = jid == ""

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_size_request(260, -1)

        image = self._get_avatar_image(contact)
        image.set_size_request(AvatarSize.ROSTER, AvatarSize.ROSTER)
        grid.attach(image, 0, 0, 1, 1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)

        self._name_label = Gtk.Label(label=self._name)
        self._name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._name_label.set_xalign(0)
        self._name_label.set_width_chars(20)
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.add_css_class("bold16")
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_box.append(self._name_label)

        if show_account:
            account_badge = AccountBadge(account)
            account_badge.set_halign(Gtk.Align.END)
            account_badge.set_valign(Gtk.Align.START)
            account_badge.set_hexpand(True)
            name_box.append(account_badge)
        box.append(name_box)

        self._jid_label = Gtk.Label(label=str(jid))
        self._jid_label.set_tooltip_text(str(jid))
        self._jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._jid_label.set_xalign(0)
        self._jid_label.set_width_chars(22)
        self._jid_label.set_halign(Gtk.Align.START)
        self._jid_label.add_css_class("dim-label")
        box.append(self._jid_label)

        grid.attach(box, 1, 0, 1, 1)

        self.set_child(grid)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def _get_avatar_image(self, contact: types.BareContact | None) -> Gtk.Image:
        if contact is None:
            icon_name = "avatar-default"
            return Gtk.Image.new_from_icon_name(icon_name)

        scale = self.get_scale_factor()
        texture = contact.get_avatar(AvatarSize.ROSTER, scale)
        return Gtk.Image.new_from_paintable(texture)

    def update_jid(self, jid: str) -> None:
        self.jid = jid
        self._jid_label.set_text(jid)

    def get_search_text(self):
        if self._contact is None:
            return str(self.jid)
        return f"{self._name} {self.jid}"


class GroupChatInviter(Gtk.Box, SignalManager):
    __gsignals__ = {"listbox-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,))}

    def __init__(self, room_jid: str) -> None:
        Gtk.Box.__init__(self, height_request=250)
        SignalManager.__init__(self)

        self._ui = get_builder("groupchat_inviter.ui")
        self.append(self._ui.invite_box)

        self._invitees_box = ContactsFlowBox()
        self._connect(self._invitees_box, "contact-removed", self._on_invitee_removed)
        self._ui.invitees_scrolled.set_child(self._invitees_box)

        self._ui.contacts_listbox.set_filter_func(self._filter_func, None)
        self._ui.contacts_listbox.set_sort_func(self._sort_func, None)
        self._connect(
            self._ui.contacts_listbox, "row-activated", self._on_contacts_row_activated
        )

        self._room_jid = room_jid

        self._new_contact_rows: dict[str, ContactRow | None] = {}
        self._accounts: list[list[str]] = []

        self._connect(self._ui.search_entry, "search-changed", self._on_search_changed)
        self._connect(
            self._ui.search_entry, "next-match", self._select_new_match, Direction.NEXT
        )
        self._connect(
            self._ui.search_entry,
            "previous-match",
            self._select_new_match,
            Direction.PREV,
        )
        self._connect(self._ui.search_entry, "stop-search", self._on_stop_search)
        self._connect(self._ui.search_entry, "activate", self._on_search_activate)

        controller = Gtk.EventControllerKey()
        self._connect(controller, "key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)

    def _add_accounts(self) -> None:
        for account in self._accounts:
            self._ui.account_store.append([None, *account])

    def _add_contacts(self) -> None:
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            self._new_contact_rows[account] = None
            client = app.get_client(account)
            for contact in client.get_module("Roster").iter_contacts():
                # Exclude group chats
                if contact.is_groupchat:
                    continue
                # Exclude our own jid
                if contact.jid == client.get_own_jid().bare:
                    continue

                row = ContactRow(
                    account, contact, str(contact.jid), contact.name, show_account
                )
                self._ui.contacts_listbox.append(row)

    def _on_contacts_row_activated(self, listbox: Gtk.ListBox, row: ContactRow) -> None:

        self._invitees_box.add_contact(row.account, row.jid, is_new=row.is_new)

        if row.is_new:
            self._remove_new_contact_row()
        else:
            listbox.remove(row)

        self._ui.search_entry.set_text("")
        GLib.timeout_add(50, self._select_first_row)

        invitable = self._invitees_box.has_contacts()
        self.emit("listbox-changed", invitable)

    def _on_invitee_removed(
        self, flowbox: ContactsFlowBox, account: str, jid: str, is_new: bool
    ) -> None:
        if not is_new:
            show_account = len(self._accounts) > 1
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            row = ContactRow(
                account, contact, str(contact.jid), contact.name, show_account
            )
            self._ui.contacts_listbox.append(row)

        self.emit("listbox-changed", flowbox.has_contacts())

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Down:
            self._ui.search_entry.emit("next-match")
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Up:
            self._ui.search_entry.emit("previous-match")
            return Gdk.EVENT_STOP

        if keyval in (
            Gdk.KEY_Return,
            Gdk.KEY_KP_Enter,
            Gdk.KEY_ISO_Enter,
        ):
            row = self._ui.contacts_listbox.get_selected_row()
            if row is not None:
                row.emit("activate")
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    @staticmethod
    def _on_stop_search(entry: Gtk.SearchEntry) -> None:
        entry.set_text("")

    def _on_search_activate(self, _entry: Gtk.SearchEntry) -> None:
        row = self._ui.contacts_listbox.get_selected_row()
        if row is not None and row.get_child_visible():
            row.emit("activate")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        search_text = entry.get_text()
        if "@" in search_text:
            try:
                validate_jid(search_text)
            except Exception:
                self._remove_new_contact_row()
            else:
                self._add_new_contact_row()
                self._update_new_contact_rows(search_text)
        else:
            self._remove_new_contact_row()
        self._ui.contacts_listbox.invalidate_filter()

    def _add_new_contact_row(self) -> None:
        for account, _label in self._accounts:
            row = self._new_contact_rows.get(account)
            if row is not None:
                continue
            show_account = len(self._accounts) > 1
            row = ContactRow(account, None, "", _("New Contact"), show_account)
            self._new_contact_rows[account] = row
            self._ui.contacts_listbox.append(row)

    def _remove_new_contact_row(self) -> None:
        for row in self._new_contact_rows.values():
            if row is not None:
                self._ui.contacts_listbox.remove(row)
        self._new_contact_rows.clear()

    def _update_new_contact_rows(self, search_text: str) -> None:
        for row in self._new_contact_rows.values():
            if row is not None:
                row.update_jid(search_text)

    def _select_new_match(self, _entry: Gtk.SearchEntry, direction: Direction) -> None:
        selected_row = self._ui.contacts_listbox.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()

        if direction == Direction.NEXT:
            index += 1
        else:
            index -= 1

        while True:
            new_selected_row = self._ui.contacts_listbox.get_row_at_index(index)
            if new_selected_row is None:
                return
            if new_selected_row.get_child_visible():
                self._ui.contacts_listbox.select_row(new_selected_row)
                return

            if direction == Direction.NEXT:
                index += 1
            else:
                index -= 1

    def _select_first_row(self) -> None:
        first_row = self._ui.contacts_listbox.get_row_at_y(0)
        self._ui.contacts_listbox.select_row(first_row)

    def _scroll_to_first_row(self) -> None:
        self._ui.scrolledwindow.get_vadjustment().set_value(0)

    def _filter_func(self, row: ContactRow, _user_data: Any | None) -> bool:
        search_text = self._ui.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_search_text().lower()
        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self._select_first_row)
                return False
        GLib.timeout_add(50, self._select_first_row)
        return True

    @staticmethod
    def _sort_func(row1: ContactRow, row2: ContactRow, _user_data: Any | None) -> int:
        name1 = row1.get_search_text()
        name2 = row2.get_search_text()
        account1 = row1.account
        account2 = row2.account

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        return locale.strcoll(name1.lower(), name2.lower())

    def _reset(self) -> None:
        for row in iterate_listbox_children(self._ui.contacts_listbox):
            self._ui.contacts_listbox.remove(row)

        self._invitees_box.clear()

    def load_contacts(self) -> None:
        self._reset()

        self._accounts = app.get_enabled_accounts_with_labels()
        self._new_contact_rows = {}
        self._add_accounts()

        self._add_contacts()

        first_row = self._ui.contacts_listbox.get_row_at_index(0)
        self._ui.contacts_listbox.select_row(first_row)
        self._ui.search_entry.grab_focus()
        self.emit("listbox-changed", False)

    def get_invitees(self) -> list[str]:
        return self._invitees_box.get_contact_jids()
