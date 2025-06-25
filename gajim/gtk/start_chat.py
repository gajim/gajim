# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Generic
from typing import TypeVar

import locale
import logging

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.client import Client as NBXMPPClient
from nbxmpp.errors import CancelledError
from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.modules.muc.util import MucInfoResult
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.const import PresenceShowExt
from gajim.common.const import RFC5646_LANGUAGE_TAGS
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.util import as_task
from gajim.common.util.jid import validate_jid
from gajim.common.util.muc import get_group_chat_nick
from gajim.common.util.status import compare_show
from gajim.common.util.text import to_one_line
from gajim.common.util.uri import parse_uri
from gajim.common.util.uri import XmppIri

from gajim.gtk.builder import get_builder
from gajim.gtk.chat_filter import ChatFilter
from gajim.gtk.chat_filter import ChatFilters
from gajim.gtk.chat_filter import ChatTypeFilter
from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick import NickChooser
from gajim.gtk.menus import get_start_chat_menu
from gajim.gtk.menus import get_start_chat_row_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.icons import get_icon_theme
from gajim.gtk.util.misc import get_ui_string

# from gajim.gtk.tooltips import ContactTooltip
from gajim.gtk.widgets import AccountBadge
from gajim.gtk.widgets import GajimAppWindow
from gajim.gtk.widgets import GajimPopover
from gajim.gtk.widgets import GroupBadgeBox
from gajim.gtk.widgets import IdleBadge

ContactT = BareContact | GroupchatContact
L = TypeVar("L", bound=type[GObject.Object])
V = TypeVar("V", bound=type[Gtk.Widget])


log = logging.getLogger("gajim.gtk.start_chat")


class StartChatDialog(GajimAppWindow):
    def __init__(
        self, initial_jid: str | None = None, initial_message: str | None = None
    ) -> None:

        GajimAppWindow.__init__(
            self,
            name="StartChatDialog",
            title=_("Start / Join Chat"),
            default_height=600,
            default_width=550,
            add_window_padding=False,
        )

        self._parameter_form: MuclumbusResult | None = None
        self._keywords: list[str] = []
        self._destroyed = False
        self._search_stopped = False
        self._search_is_changed = False

        self._ui = get_builder("start_chat_dialog.ui")
        self.set_child(self._ui.stack)

        self._nick_chooser = NickChooser()
        self._ui.join_box.prepend(self._nick_chooser)

        self._search_is_valid_jid = False

        self._new_contact_items: dict[str, ContactListItem] = {}
        self._accounts = app.get_enabled_accounts_with_labels()

        self._accounts_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self._ui.account_view.set_model(self._accounts_store)

        self._contact_view = ContactListView()
        self._connect(self._contact_view, "activate", self._on_contact_item_activated)
        self._ui.contact_scrolled.set_child(self._contact_view)

        self._ui.settings_menu.set_menu_model(get_start_chat_menu())

        scale = self.get_scale_factor()
        self._add_accounts()
        self._add_contacts(scale)
        self._add_groupchats(scale)
        self._add_new_contact_items(scale)

        controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        text = self._ui.search_entry.get_delegate()
        assert isinstance(text, Gtk.Text)
        text.add_controller(controller)
        self._connect(controller, "key-pressed", self._on_search_key_pressed)

        self._connect(
            self._ui.infobar_close_button, "clicked", self._on_infobar_close_clicked
        )
        self._connect(self._ui.search_entry, "activate", self._on_search_activate)
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
        self._connect(
            self._ui.search_entry,
            "stop-search",
            lambda *args: self._ui.search_entry.set_text(""),
        )
        self._connect(
            self._ui.stack, "notify::visible-child-name", self._on_page_changed
        )
        self._connect(
            self._ui.global_search_toggle, "toggled", self._on_global_search_toggle
        )
        self._connect(self._ui.error_back_button, "clicked", self._on_back_clicked)
        self._connect(self._ui.join_button, "clicked", self._on_join_clicked)
        self._connect(self._ui.info_back_button, "clicked", self._on_back_clicked)
        self._connect(self._ui.account_view, "row-activated", self._on_select_clicked)
        self._connect(self._ui.account_back_button, "clicked", self._on_back_clicked)
        self._connect(
            self._ui.account_select_button, "clicked", self._on_select_clicked
        )

        self._global_search_view = GlobalSearch()
        self._connect(
            self._global_search_view, "activate", self._on_global_item_activated
        )
        self._connect(
            self._global_search_view,
            "global-search-progress",
            self._on_global_search_progress,
        )
        self._ui.global_scrolled.set_child(self._global_search_view)

        self._muc_info_box = GroupChatInfoScrolled()
        self._ui.info_box.prepend(self._muc_info_box)

        self._ui.infobar.set_reveal_child(app.settings.get("show_help_start_chat"))

        self._chat_filter = ChatFilter()
        self._connect(self._chat_filter, "filter-changed", self._on_chat_filter_changed)
        self._chat_filter.insert_after(self._ui.controls_box, self._ui.search_entry)

        self._connect(
            self.get_default_controller(), "key-pressed", self._on_key_pressed
        )

        self._initial_message: dict[str, str | None] = {}
        if initial_jid is not None:
            self._initial_message[initial_jid] = initial_message
            self._ui.search_entry.set_text(initial_jid)

        self._contact_view.set_loading_finished()

        action = Gio.SimpleAction.new_stateful(
            "sort-by-show",
            None,
            GLib.Variant.new_boolean(app.settings.get("sort_by_show_in_start_chat")),
        )
        self._connect(action, "change-state", self._on_sort_by_show_changed)
        self.window.add_action(action)

        log.debug("Loading dialog finished")
        self.show()

    def _cleanup(self, *args: Any) -> None:
        del self._nick_chooser
        del self._global_search_view
        del self._muc_info_box
        del self._chat_filter
        del self._accounts_store
        self._new_contact_items.clear()
        self._destroyed = True
        app.cancel_tasks(self)

    def remove_row(self, account: str, jid: str) -> None:
        # Used by forget-groupchat action
        self._contact_view.remove(account, jid)

    def _is_global_search_active(self) -> bool:
        return self._ui.list_stack.get_visible_child_name() == "global"

    def _get_active_view(self) -> ContactListView | GlobalSearch:
        if self._ui.list_stack.get_visible_child_name() == "global":
            return self._global_search_view
        return self._contact_view

    def _add_accounts(self) -> None:
        for account in self._accounts:
            self._accounts_store.append([None, *account])

    def _add_contacts(self, scale: int) -> None:
        log.debug("Loading contacts")
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            client = app.get_client(account)
            for jid, _data in client.get_module("Roster").iter():
                contact = client.get_module("Contacts").get_contact(jid)

                if isinstance(contact, GroupchatContact):
                    # Workaround if groupchats are in the roster
                    continue

                item = ContactListItem(
                    account,
                    contact,
                    jid,
                    contact.name,
                    scale,
                    show_account,
                )

                self._contact_view.add(item)

            self_contact = client.get_module("Contacts").get_contact(
                client.get_own_jid().bare
            )
            item = ContactListItem(
                account,
                self_contact,
                self_contact.jid,
                _("Note to myself"),
                scale,
                show_account,
            )
            self._contact_view.add(item)

        log.debug(
            "Loading contacts finished, model count %s", self._contact_view.get_count()
        )

    def _add_groupchats(self, scale: int) -> None:
        log.debug("Loading groupchats")
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            client = app.get_client(account)
            bookmarks = client.get_module("Bookmarks").bookmarks
            for bookmark in bookmarks:
                contact = client.get_module("Contacts").get_contact(
                    bookmark.jid, groupchat=True
                )

                item = ContactListItem(
                    account,
                    contact,
                    bookmark.jid,
                    contact.name,
                    scale,
                    show_account,
                    groupchat=True,
                )
                self._contact_view.add(item)

        log.debug(
            "Loading groupchats finished, model count %s",
            self._contact_view.get_count(),
        )

    def _add_new_contact_items(self, scale: int) -> None:
        for account, _label in self._accounts:
            show_account = len(self._accounts) > 1
            item = ContactListItem(account, None, None, None, scale, show_account)
            self._new_contact_items[account] = item
            self._contact_view.add(item)

    def _on_sort_by_show_changed(
        self, action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        action_state = action.get_state()
        assert action_state is not None
        new_state = not action_state.get_boolean()
        app.settings.set("sort_by_show_in_start_chat", new_state)
        action.set_state(GLib.Variant.new_boolean(new_state))
        self._contact_view.invalidate_sort()

    def _on_page_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        if stack.get_visible_child_name() == "account":
            self._ui.account_view.grab_focus()

    def _on_contact_item_activated(
        self,
        _listbox: Gtk.ListView,
        position: int,
    ) -> None:
        item = self._contact_view.get_listitem(position)
        self._prepare_new_chat(item)

    def _on_global_item_activated(
        self,
        _listview: Gtk.ListView,
        position: int,
    ) -> None:
        self._select_muc()

    def _on_global_search_progress(
        self, _listview: Gtk.ListView, progressing: bool, results_count: int
    ) -> None:
        if progressing:
            self._ui.global_search_placeholder_stack.set_visible(True)
            self._ui.global_search_placeholder_stack.set_visible_child_name(
                "global-search-progress"
            )
            self._ui.global_search_results_label.set_text(
                _("Searching…\n%s results") % results_count
            )
            return

        if results_count == 0:
            self._ui.global_search_placeholder_stack.set_visible(True)
            self._ui.global_search_placeholder_stack.set_visible_child_name(
                "global-search-no-results"
            )
        else:
            self._ui.global_search_placeholder_stack.set_visible(False)

    def _select_muc(self) -> None:
        if len(self._accounts) > 1:
            self._ui.stack.set_visible_child_name("account")
        else:
            self._on_select_clicked()

    def _on_search_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:

        if keyval == Gdk.KEY_Down:
            self._ui.search_entry.emit("next-match")
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Up:
            self._ui.search_entry.emit("previous-match")
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_search_activate(self, search_entry: Gtk.SearchEntry) -> None:
        if self._is_global_search_active() and self._search_is_changed:
            self._search_is_changed = False
            self._global_search_view.remove_all()
            self._start_search()
            return

        view = self._get_active_view()
        pos = view.get_selected()
        if pos == Gtk.INVALID_LIST_POSITION:
            return
        view.emit("activate", pos)

    def _on_search_changed(self, search_entry: Gtk.SearchEntry) -> None:
        self._search_is_changed = True
        self._show_search_entry_error(False)
        self._search_is_valid_jid = False

        if self._is_global_search_active():
            return

        search_text = search_entry.get_text()
        uri = parse_uri(search_text)
        if isinstance(uri, XmppIri):
            search_entry.set_text(str(uri.jid))
            return

        if search_text:
            try:
                validate_jid(search_text)
            except ValueError:
                self._show_search_entry_error(True)
            else:
                self._update_new_contact_items(search_text)
                self._search_is_valid_jid = True

        self._contact_view.set_search(search_text)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:

        if keyval == Gdk.KEY_Escape:
            if self._ui.stack.get_visible_child_name() == "progress":
                # Propagate to GajimAppWindow
                return Gdk.EVENT_PROPAGATE

            if self._ui.stack.get_visible_child_name() == "account":
                self._on_back_clicked()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() in ("error", "info"):
                self._ui.stack.set_visible_child_name("search")
                return Gdk.EVENT_STOP

            self._search_stopped = True
            self._ui.search_entry.grab_focus()
            self._global_search_view.remove_all()
            if self._ui.search_entry.get_text() != "":
                self._ui.search_entry.emit("stop-search")
                return Gdk.EVENT_STOP

            # Propagate to GajimAppWindow
            return Gdk.EVENT_PROPAGATE

        if keyval == Gdk.KEY_Return:
            if self._ui.stack.get_visible_child_name() == "progress":
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == "account":
                self._on_select_clicked()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == "error":
                self._ui.stack.set_visible_child_name("search")
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == "info":
                self._on_join_clicked()
                return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_infobar_close_clicked(
        self,
        _button: Gtk.Button,
    ) -> None:
        self._ui.infobar.set_reveal_child(False)
        app.settings.set("show_help_start_chat", False)

    def _on_chat_filter_changed(self, chat_filter: ChatFilter) -> None:
        self._contact_view.set_chat_filter(chat_filter.get_filters())

    def _prepare_new_chat(self, item: ContactListItem) -> None:
        if item.jid is None:
            return

        if item.is_new:
            try:
                validate_jid(item.jid)
            except ValueError as error:
                self._show_error_page(str(error))
                return

            self._disco_info(item)
            return

        self._start_new_chat(item, groupchat=item.is_groupchat)

    def _start_new_chat(self, item: ContactListItem, *, groupchat: bool) -> None:
        jid = JID.from_string(item.jid)
        if groupchat:
            if not app.account_is_available(item.account):
                self._show_error_page(
                    _("You can not join a group chat unless you are connected.")
                )
                return

            if app.window.chat_exists(item.account, jid):
                app.window.select_chat(item.account, jid)
                self.close()
                return

            self._disco_muc(item.account, jid, request_vcard=item.is_new)

        else:
            initial_message = self._initial_message.get(item.jid)
            app.window.add_chat(
                item.account, jid, "chat", select=True, message=initial_message
            )
            self.close()

    def _disco_info(self, item: ContactListItem) -> None:
        if not app.account_is_available(item.account):
            self._show_error_page(_("You are offline."))
            return

        self._ui.stack.set_visible_child_name("progress")
        client = app.get_client(item.account)
        client.get_module("Discovery").disco_info(
            item.jid, callback=self._disco_info_received, user_data=item, timeout=10
        )

    def _disco_info_received(self, task: Task) -> None:
        item = cast(ContactListItem, task.get_user_data())
        try:
            result = cast(DiscoInfo, task.finish())
        except StanzaError as error:
            contact_conditions = [
                "service-unavailable",  # Prosody
                "subscription-required",  # ejabberd
                "feature-not-implemented",  # transports/bridges
            ]
            if error.condition in contact_conditions:
                # These error conditions are the result of
                # querying contacts without subscription
                self._start_new_chat(item, groupchat=False)
                return

            # Handle other possible errors
            self._show_error_page(to_user_string(error))
            return
        except TimeoutStanzaError:
            # We reached the 10s timeout and we cannot
            # assume which kind contact this is.
            self._show_error_page(_("This address is not reachable."))
            return

        groupchat = False
        if result.is_muc and not result.jid.is_domain:
            # This is mostly a fix for the MUC protocol, there is no
            # way to differentiate between a MUC service and room.
            # Except the MUC XEP defines rooms should have a localpart.
            groupchat = True

        self._start_new_chat(item, groupchat=groupchat)

    def _disco_muc(self, account: str, jid: JID, request_vcard: bool) -> None:
        self._ui.stack.set_visible_child_name("progress")
        client = app.get_client(account)
        client.get_module("Discovery").disco_muc(
            jid,
            request_vcard=request_vcard,
            allow_redirect=True,
            timeout=10,
            callback=self._muc_disco_info_received,
            user_data=account,
        )

    def _muc_disco_info_received(self, task: Task) -> None:
        try:
            result = cast(MucInfoResult, task.finish())
        except (StanzaError, TimeoutStanzaError) as error:
            self._set_error(error)
            return

        account = task.get_user_data()

        if result.info.is_muc:
            self._muc_info_box.set_account(account)
            self._muc_info_box.set_from_disco_info(result.info)
            self._nick_chooser.set_text(get_group_chat_nick(account, result.info.jid))
            self._ui.stack.set_visible_child_name("info")

        else:
            self._set_error_from_code("not-muc-service")

    def _set_error(self, error: StanzaError | TimeoutStanzaError) -> None:
        if isinstance(error, TimeoutStanzaError):
            text = _("This address is not reachable.")
        else:
            text = MUC_DISCO_ERRORS.get(error.condition, to_user_string(error))
            if error.condition == "gone":
                reason = error.get_text(get_rfc5646_lang())
                if reason:
                    text = f"{text}:\n{reason}"
        self._show_error_page(text)

    def _set_error_from_code(self, error_code: str) -> None:
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _show_error_page(self, text: str) -> None:
        self._ui.error_label.set_text(str(text))
        self._ui.stack.set_visible_child_name("error")

    def _on_join_clicked(self, *args: Any) -> None:
        account = self._muc_info_box.get_account()
        jid = self._muc_info_box.get_jid()
        nickname = self._nick_chooser.get_text()
        assert account
        app.window.show_add_join_groupchat(account, str(jid), nickname=nickname)

        self.close()

    def _on_back_clicked(self, *args: Any) -> None:
        self._ui.stack.set_visible_child_name("search")

    def _on_select_clicked(self, *args: Any) -> None:
        model, iter_ = self._ui.account_view.get_selection().get_selected()
        if iter_ is not None:
            account = model[iter_][1]
        elif len(self._accounts) == 1:
            account = self._accounts[0][0]
        else:
            return

        item = self._global_search_view.get_selected_item()
        if item is None:
            return

        if not app.account_is_available(account):
            self._show_error_page(
                _("You can not join a group chat unless you are connected.")
            )
            return

        jid = JID.from_string(item.jid)
        self._disco_muc(account, jid, request_vcard=True)

    def _on_global_search_toggle(self, button: Gtk.ToggleButton) -> None:
        self._ui.search_entry.grab_focus()
        image = cast(Gtk.Image, button.get_child())
        if button.get_active():
            self._chat_filter.reset()
            self._chat_filter.set_sensitive(False)
            image.add_css_class("accent")
            self._ui.list_stack.set_visible_child_name("global")

            self._ui.global_search_placeholder_stack.set_visible_child_name(
                "global-search-hint"
            )
            self._ui.global_search_placeholder_stack.set_visible(True)

            if self._ui.search_entry.get_text():
                self._start_search()
                self._global_search_view.grab_focus()
        else:
            self._chat_filter.set_sensitive(True)
            self._ui.search_entry.set_text("")
            image.remove_css_class("accent")
            self._ui.list_stack.set_visible_child_name("contacts")
            self._global_search_view.remove_all()

    def _show_search_entry_error(self, state: bool):
        self._ui.search_error_box.set_visible(state)

    def _update_new_contact_items(self, search_text: str) -> None:
        for item in self._new_contact_items.values():
            item.props.jid = JID.from_string(search_text)

    def _select_new_match(self, _entry: Gtk.Entry, direction: Direction) -> None:

        if self._is_global_search_active():
            self._global_search_view.select(direction)
        else:
            self._contact_view.select(direction)

    def _start_search(self) -> None:
        self._search_stopped = False
        accounts = app.get_connected_accounts()
        if not accounts:
            return
        client = app.get_client(accounts[0]).connection

        text = self._ui.search_entry.get_text().strip()
        if not text:
            return

        self._global_search_view.start_search()

        if app.settings.get("muclumbus_api_pref") == "http":
            self._start_http_search(client, text)
        else:
            self._start_iq_search(client, text)

    @as_task
    def _start_iq_search(self, client: NBXMPPClient, text: str):
        _task = yield  # noqa: F841

        if self._parameter_form is None:
            result = yield client.get_module("Muclumbus").request_parameters(
                app.settings.get("muclumbus_api_jid")
            )

            self._process_search_result(result, parameters=True)

            self._parameter_form = result
            self._parameter_form.type_ = "submit"

        self._parameter_form.vars["q"].value = text

        result = yield client.get_module("Muclumbus").set_search(
            app.settings.get("muclumbus_api_jid"), self._parameter_form
        )

        self._process_search_result(result)

        while not result.end:
            result = yield client.get_module("Muclumbus").set_search(
                app.settings.get("muclumbus_api_jid"),
                self._parameter_form,
                items_per_page=result.max,
                after=result.last,
            )

            self._process_search_result(result)

        self._global_search_view.end_search()

    @as_task
    def _start_http_search(self, client: NBXMPPClient, text: str):
        _task = yield  # noqa: F841

        self._keywords = text.split(" ")
        result = yield client.get_module("Muclumbus").set_http_search(
            app.settings.get("muclumbus_api_http_uri"), self._keywords
        )

        self._process_search_result(result)

        while not result.end:
            result = yield client.get_module("Muclumbus").set_http_search(
                app.settings.get("muclumbus_api_http_uri"),
                self._keywords,
                after=result.last,
            )

            self._process_search_result(result)

        self._global_search_view.end_search()

    def _process_search_result(
        self, result: MuclumbusResult, parameters: bool = False
    ) -> None:
        if self._search_stopped:
            raise CancelledError

        if is_error(result):
            assert isinstance(result, StanzaError)
            self._ui.global_search_placeholder_stack.set_visible(False)
            self._show_error_page(to_user_string(result))
            raise result

        if parameters:
            return

        for item in result.items:
            self._global_search_view.add(item)


class BaseListView(Generic[L, V], Gtk.ListView, SignalManager):

    _selection_model: Gtk.SingleSelection
    _filter_model: Gtk.FilterListModel

    def __init__(self, list_type: L, view_type: V) -> None:
        Gtk.ListView.__init__(self)
        SignalManager.__init__(self)

        self._model = Gio.ListStore(item_type=list_type)

        factory = Gtk.SignalListItemFactory()
        self._connect(factory, "setup", self._on_factory_setup, view_type)
        self._connect(factory, "bind", self._on_factory_bind)
        self._connect(factory, "unbind", self._on_factory_unbind)
        self.set_factory(factory)

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, view_type: V
    ) -> None:
        list_item.set_child(view_type())

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = list_item.get_child()
        obj = list_item.get_item()
        view_item.bind(obj)

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = list_item.get_child()
        view_item.unbind()

    def add(self, *args, **kwargs) -> None:
        raise NotImplementedError

    def remove_all(self) -> None:
        self._model.remove_all()

    def get_listitem(self, position: int) -> L:
        return self._filter_model.get_item(position)

    def get_selected_item(self) -> L | None:
        return self._selection_model.get_selected_item()

    def get_selected(self) -> int:
        return self._selection_model.get_selected()

    def select(self, direction: Direction) -> None:
        selected_pos = self._selection_model.get_selected()
        if selected_pos == Gtk.INVALID_LIST_POSITION:
            return

        if direction == Direction.NEXT:
            selected_pos += 1
        else:
            selected_pos -= 1

        if not 0 <= selected_pos < self._selection_model.get_n_items():
            return

        self.scroll_to(selected_pos, Gtk.ListScrollFlags.SELECT)


class ContactListView(BaseListView[type["ContactListItem"], type["ContactViewItem"]]):
    def __init__(self) -> None:
        BaseListView.__init__(self, ContactListItem, ContactViewItem)

        self._chat_filters = ChatFilters()
        self._scroll_id = None
        self._search_string_list: list[str] = []

        self._sorter = Gtk.CustomSorter.new(sort_func=self._sort_func)
        self._sort_model = Gtk.SortListModel(sorter=self._sorter)

        self._custom_filter = Gtk.CustomFilter.new(self._filter_func)

        self._filter_model = Gtk.FilterListModel(
            model=self._sort_model, filter=self._custom_filter
        )
        self._connect(
            self._filter_model, "items-changed", self._on_filter_items_changed
        )

        self._selection_model = Gtk.SingleSelection(model=self._filter_model)

        self.set_model(self._selection_model)

    def do_unroot(self) -> None:
        # The filter func needs to be unset before calling do_unroot (see #12213)
        self._custom_filter.set_filter_func(None)
        self._sorter.set_sort_func(None)
        Gtk.ListView.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self._model)
        app.check_finalize(self._filter_model)
        app.check_finalize(self._sort_model)
        app.check_finalize(self._selection_model)
        app.check_finalize(self._custom_filter)
        del self._model
        del self._filter_model
        del self._sort_model
        del self._selection_model
        del self._custom_filter
        del self._sorter
        app.check_finalize(self)

    def set_loading_finished(self) -> None:
        self._sort_model.set_model(self._model)

    def get_count(self) -> int:
        return self._model.get_n_items()

    def invalidate_sort(self) -> None:
        self._sorter.changed(Gtk.SorterChange.DIFFERENT)

    def _on_filter_items_changed(
        self, filter_model: Gtk.FilterListModel, _pos: int, _removed: int, _added: int
    ) -> None:

        # Cancel any active source at first so we dont have
        # multiple timeouts running

        if self._scroll_id is not None:
            GLib.source_remove(self._scroll_id)
            self._scroll_id = None

        # If the first item is already selected or
        # no items are in the model we dont need to trigger a scroll

        if self._selection_model.get_selected() == 0 or filter_model.get_n_items() == 0:
            return

        def _scroll_to() -> None:
            self._scroll_id = None
            self.scroll_to(0, Gtk.ListScrollFlags.SELECT)

        self._scroll_id = GLib.timeout_add(50, _scroll_to)

    def _filter_func(self, item: ContactListItem) -> bool:
        account = self._chat_filters.account
        if account is not None and account != item.account:
            return False

        if item.is_new:
            return True

        for search_string in self._search_string_list:
            if search_string not in item.search_string:
                return False

        group = self._chat_filters.group
        if group is not None and group not in item.groups:
            return False

        type_ = self._chat_filters.type
        if type_ == ChatTypeFilter.ALL:
            return True

        is_groupchat = item.is_groupchat
        if type_ == ChatTypeFilter.CHAT and not is_groupchat:
            return True

        return type_ == ChatTypeFilter.GROUPCHAT and is_groupchat

    @staticmethod
    def _sort_func(
        obj1: Any,
        obj2: Any,
        _user_data: object | None,
    ) -> int:

        if obj1.is_new != obj2.is_new:
            return 1 if obj1.is_new else -1

        if obj1.is_groupchat != obj2.is_groupchat:
            return 1 if obj1.is_groupchat else -1

        if obj1.is_self != obj2.is_self:
            return 1 if obj1.is_self else -1

        if app.settings.get("sort_by_show_in_start_chat"):
            res = compare_show(obj1.show, obj2.show)
            if res != 0:
                return res

        return locale.strcoll(obj1.name.lower(), obj2.name.lower())

    def add(self, item: ContactViewItem) -> None:
        self._model.append(item)

    def remove(self, account: str, jid: JID) -> None:
        for item in self._model:
            if item.account != account or item.jid != jid:
                continue
            success, pos = self._model.find(item)
            if success:
                self._model.remove(pos)
            break

    def set_search(self, text: str) -> None:
        self._search_string_list = text.lower().split()
        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def set_chat_filter(self, value: ChatFilters) -> None:
        if self._chat_filters == value:
            return
        self._chat_filters = value
        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)


class ContactListItem(GObject.Object):
    __gtype_name__ = "ContactListItem"

    account = GObject.Property(type=str)
    account_visible = GObject.Property(type=bool, default=False)
    jid = GObject.Property(type=str)
    name = GObject.Property(type=str)
    groups = GObject.Property(type=object)
    is_groupchat = GObject.Property(type=bool, default=False)
    is_new = GObject.Property(type=bool, default=False)
    is_self = GObject.Property(type=bool, default=False)
    avatar_paintable = GObject.Property(type=Gdk.Paintable)
    idle = GObject.Property(type=object)
    show = GObject.Property(type=object)
    status = GObject.Property(type=str)
    status_visible = GObject.Property(type=bool, default=False)
    search_string = GObject.Property(type=str)
    menu = GObject.Property(type=Gio.Menu)

    def __init__(
        self,
        account: str,
        contact: ContactT | None,
        jid: JID | None,
        name: str | None,
        scale: int,
        account_visible: bool,
        groupchat: bool = False,
    ) -> None:

        name = name or _("Start New Chat")

        idle = None
        status = ""
        groups = []
        show = PresenceShowExt.OFFLINE
        is_self = False
        if contact is not None and not groupchat:
            groups = sorted(contact.groups)
            status = to_one_line(contact.status)
            idle = contact.idle_datetime
            show = contact.show
            is_self = contact.is_self

        menu = get_start_chat_row_menu(account, jid)

        is_new = jid is None

        avatar_paintable = None
        if is_new:
            theme = get_icon_theme()
            avatar_paintable = theme.lookup_icon(
                "feather-user-plus-symbolic",
                None,
                AvatarSize.START_CHAT,
                scale,
                Gtk.TextDirection.NONE,
                0,
            )

        else:
            avatar_paintable = contact.get_avatar(AvatarSize.START_CHAT, scale)

        search_string = "|".join((name, str(jid))).lower()

        super().__init__(
            account=account,
            account_visible=account_visible,
            jid=jid,
            name=name,
            idle=idle,
            is_groupchat=groupchat,
            is_new=jid is None,
            is_self=is_self,
            show=show,
            status=status,
            status_visible=bool(status),
            groups=groups,
            menu=menu,
            avatar_paintable=avatar_paintable,
            search_string=search_string,
        )

    def __repr__(self) -> str:
        return f"ContactListItem: {self.props.account} - {self.props.jid}"


@Gtk.Template(string=get_ui_string("contact_view_item.ui"))
class ContactViewItem(Gtk.Grid, SignalManager):
    __gtype_name__ = "ContactViewItem"

    _avatar: Gtk.Label = Gtk.Template.Child()
    _name_label: Gtk.Label = Gtk.Template.Child()
    _address_label: Gtk.Label = Gtk.Template.Child()
    _status_label: Gtk.Label = Gtk.Template.Child()
    _idle_badge: IdleBadge = Gtk.Template.Child()
    _account_badge: AccountBadge = Gtk.Template.Child()
    _group_badge_box: GroupBadgeBox = Gtk.Template.Child()
    _menu: GajimPopover = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Grid.__init__(self)
        SignalManager.__init__(self)

        self.__bindings: list[GObject.Binding] = []

        # TODO: add back tooltip
        # self._tooltip = ContactTooltip()
        # image.set_has_tooltip(True)
        # self._connect(image, 'query-tooltip', self._on_query_tooltip)

        gesture_secondary_click = Gtk.GestureClick(
            button=Gdk.BUTTON_SECONDARY, propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        self._connect(gesture_secondary_click, "pressed", self._popup_menu)
        self.add_controller(gesture_secondary_click)

    def bind(self, obj: GlobalListItem) -> None:
        bind_spec = [
            ("name", self._name_label, "label"),
            ("jid", self._address_label, "label"),
            ("status", self._status_label, "label"),
            ("status_visible", self._status_label, "visible"),
            ("avatar_paintable", self._avatar, "paintable"),
            ("idle", self._idle_badge, "idle"),
            ("account", self._account_badge, "account"),
            ("account_visible", self._account_badge, "visible"),
            ("groups", self._group_badge_box, "groups"),
            ("menu", self._menu, "menu-model"),
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

    # def _on_query_tooltip(self,
    #                       _img: Gtk.Image,
    #                       _x_coord: int,
    #                       _y_coord: int,
    #                       _keyboard_mode: bool,
    #                       tooltip: Gtk.Tooltip) -> bool:
    #     if not isinstance(self.contact, BareContact):
    #         return False
    #     v, widget = self._tooltip.get_tooltip(self.contact)
    #     tooltip.set_custom(widget)
    #     return v

    def _popup_menu(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:

        if self._menu.get_menu_model() is None:
            return Gdk.EVENT_PROPAGATE

        self._menu.set_pointing_to_coord(x, y)
        self._menu.popup()

        return Gdk.EVENT_STOP


class GlobalSearch(
    BaseListView[type["GlobalListItem"], type["GlobalViewItem"]],
    Gtk.ListView,
    SignalManager,
):

    __gsignals__ = {
        "global-search-progress": (GObject.SignalFlags.RUN_FIRST, None, (bool, int)),
    }

    def __init__(self) -> None:
        BaseListView.__init__(self, GlobalListItem, GlobalViewItem)
        SignalManager.__init__(self)

        self._results_count = 0

        self._selection_model = Gtk.SingleSelection(model=self._model)
        self.set_model(self._selection_model)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListView.do_unroot(self)
        del self._model
        app.check_finalize(self)

    def start_search(self) -> None:
        self._results_count = 0
        self.emit("global-search-progress", True, 0)

    def end_search(self) -> None:
        self.emit("global-search-progress", False, self._results_count)

    def add(self, item: MuclumbusItem) -> None:
        self._results_count += 1
        self.emit("global-search-progress", True, self._results_count)
        self._model.append(GlobalListItem(item=item))


class GlobalListItem(GObject.Object):
    __gtype_name__ = "GlobalListItem"

    jid = GObject.Property(type=str)
    name = GObject.Property(type=str)
    nusers = GObject.Property(type=str)
    description = GObject.Property(type=str)
    language_visible = GObject.Property(type=bool, default=False)
    language = GObject.Property(type=str)
    language_code = GObject.Property(type=str)

    def __init__(self, item: MuclumbusItem) -> None:
        jid = JID.from_string(item.jid)
        name = item.name or jid.localpart or str(jid)
        language = RFC5646_LANGUAGE_TAGS.get(item.language, item.language) or None

        super().__init__(
            jid=item.jid,
            name=name,
            nusers=item.nusers,
            description=item.description,
            language_visible=bool(language is not None),
            language=_("Language: %s") % language,
            language_code=item.language.upper()[:2],
        )

    def __repr__(self) -> str:
        return f"GlobalListItem: {self.props.jid} {self.props.name}"


@Gtk.Template(string=get_ui_string("global_view_item.ui"))
class GlobalViewItem(Gtk.Box):
    __gtype_name__ = "GlobalViewItem"

    _name_box: Gtk.Box = Gtk.Template.Child()
    _name_label: Gtk.Label = Gtk.Template.Child()
    _description_label: Gtk.Label = Gtk.Template.Child()
    _language_box: Gtk.Box = Gtk.Template.Child()
    _language_label: Gtk.Label = Gtk.Template.Child()
    _users_count_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        self.__bindings: list[GObject.Binding] = []

    def bind(self, obj: GlobalListItem) -> None:
        bind_spec: list[tuple[str, Gtk.Widget, str]] = [
            ("name", self._name_label, "label"),
            ("description", self._description_label, "label"),
            ("jid", self._name_box, "tooltip_text"),
            ("language_visible", self._language_box, "visible"),
            ("language", self._language_box, "tooltip_text"),
            ("language_code", self._language_label, "label"),
            ("nusers", self._users_count_label, "label"),
        ]

        for source_prop, child_widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, child_widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self.__bindings.append(bind)

    def unbind(self) -> None:
        for bind in self.__bindings:
            bind.unbind()
        self.__bindings.clear()

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)
