# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.common.configpaths import get_ui_path
from gajim.common.i18n import _

from gajim.gtk.account_side_bar import AccountSideBar
from gajim.gtk.activity_side_bar import ActivitySideBar
from gajim.gtk.chat_page import ChatPage
from gajim.gtk.workspace_listbox import WorkspaceListBox


@Gtk.Template(filename=get_ui_path("app_side_bar.ui"))
class AppSideBar(Gtk.Box):
    __gtype_name__ = "AppSideBar"

    _activity_side_bar: ActivitySideBar = Gtk.Template.Child()
    _workspace_listbox: WorkspaceListBox = Gtk.Template.Child()
    _toggle_chat_list_button: Gtk.Button = Gtk.Template.Child()
    _toggle_chat_list_icon: Gtk.Image = Gtk.Template.Child()
    _account_side_bar: AccountSideBar = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)

    def set_chat_page(self, chat_page: ChatPage) -> None:
        self._activity_side_bar.set_chat_page(chat_page)
        self._workspace_listbox.set_chat_page(chat_page)

    def select_chat(self) -> None:
        self._activity_side_bar.unselect()
        self._account_side_bar.unselect()

    def show_account_page(self) -> None:
        self._activity_side_bar.unselect()
        self._workspace_listbox.unselect_all()
        self._account_side_bar.select()

    def show_activity_page(self) -> None:
        self._account_side_bar.unselect()
        self._workspace_listbox.unselect_all()
        self._activity_side_bar.select()

    def activate_workspace(self, workspace_id: str) -> None:
        self._activity_side_bar.unselect()
        self._account_side_bar.unselect()
        self._workspace_listbox.activate_workspace(workspace_id)

    def get_active_workspace(self) -> str | None:
        return self._workspace_listbox.get_active_workspace()

    def highlight_dnd_targets(self, highlight: bool) -> None:
        if highlight:
            self._workspace_listbox.add_css_class("dnd-target")
        else:
            self._workspace_listbox.remove_css_class("dnd-target")

    def add_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.add_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.remove_workspace(workspace_id)

    def get_other_workspace(self, workspace_id: str) -> str | None:
        return self._workspace_listbox.get_other_workspace(workspace_id)

    def store_workspace_order(self) -> None:
        self._workspace_listbox.store_workspace_order()

    def update_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.update_avatar(workspace_id)

    def get_first_workspace(self) -> str:
        return self._workspace_listbox.get_first_workspace()

    def activate_workspace_number(self, number: int) -> None:
        self._workspace_listbox.activate_workspace_number(number)

    def set_chat_list_toggle_state(self, chat_list_visible: bool) -> None:
        # chat_list_visible is the current state, which we want to change
        if chat_list_visible:
            self._toggle_chat_list_button.set_tooltip_text(_("Show chat list"))
            self._toggle_chat_list_icon.set_from_icon_name(
                "lucide-chevron-right-symbolic"
            )
        else:
            self._toggle_chat_list_button.set_tooltip_text(_("Hide chat list"))
            self._toggle_chat_list_icon.set_from_icon_name(
                "lucide-chevron-left-symbolic"
            )
