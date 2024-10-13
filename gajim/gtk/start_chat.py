# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import locale
from enum import IntEnum

from gi.repository import GObject, Gdk, Gio
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp import JID
from nbxmpp.const import AnonymityMode
from nbxmpp.errors import CancelledError
from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.const import URIType
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.util import as_task
from gajim.common.util.jid import validate_jid
from gajim.common.util.muc import get_group_chat_nick
from gajim.common.util.text import get_country_flag_from_code
from gajim.common.util.uri import parse_uri

from gajim.gtk.builder import get_builder
from gajim.gtk.chat_filter import ChatFilter
from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick import NickChooser
from gajim.gtk.menus import get_start_chat_row_menu
from gajim.gtk.tooltips import ContactTooltip
from gajim.gtk.util import AccountBadge
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import get_status_icon_name
from gajim.gtk.util import GroupBadge
from gajim.gtk.util import IdleBadge
from gajim.gtk.util import iterate_listbox_children
from gajim.gtk.util import SignalManager
from gajim.gtk.widgets import GajimAppWindow

ContactT = BareContact | GroupchatContact


class Search(IntEnum):
    CONTACT = 0
    GLOBAL = 1


class StartChatDialog(GajimAppWindow):
    def __init__(self,
                 initial_jid: str | None = None,
                 initial_message: str | None = None
                 ) -> None:

        GajimAppWindow.__init__(
            self,
            name='StartChatDialog',
            title=_('Start / Join Chat'),
            default_height=600,
            add_window_padding=False,
        )

        self.ready_to_destroy = False
        self._parameter_form: MuclumbusResult | None = None
        self._keywords: list[str] = []
        self._destroyed = False
        self._search_stopped = False
        self._redirected = False

        self._ui = get_builder('start_chat_dialog.ui',)
        self.set_child(self._ui.stack)

        self._nick_chooser = NickChooser()
        self._ui.join_box.append(self._nick_chooser)

        self._search_is_valid_jid = False

        self._new_contact_rows: dict[str, ContactRow | None] = {}
        self._accounts = app.get_enabled_accounts_with_labels()

        self._accounts_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self._ui.account_view.set_model(self._accounts_store)

        rows: list[ContactRow] = []
        self._add_accounts()
        self._add_contacts(rows)
        self._add_groupchats(rows)
        self._add_new_contact_rows(rows)

        self._connect(self._ui.infobar_close_button, 'clicked', self._on_infobar_close_clicked)
        self._connect(self._ui.search_entry, 
            'search-changed', self._on_search_changed)
        self._connect(self._ui.search_entry, 
            'next-match', self._select_new_match, Direction.NEXT)
        self._connect(self._ui.search_entry, 
            'previous-match', self._select_new_match, Direction.PREV)
        self._connect(self._ui.search_entry, 
            'stop-search', lambda *args: self._ui.search_entry.set_text(''))
        self._connect(self._ui.stack, 'notify::visible-child-name', self._on_page_changed)
        self._connect(self._ui.filter_bar_toggle ,'toggled', self._on_filter_bar_toggled)
        self._connect(self._ui.global_search_toggle, 'toggled', self._on_global_search_toggle)
        self._connect(self._ui.error_back_button ,'clicked', self._on_back_clicked)
        self._connect(self._ui.join_button, 'clicked', self._on_join_clicked)
        self._connect(self._ui.info_back_button, 'clicked', self._on_back_clicked)
        self._connect(self._ui.account_view, 'row-activated', self._on_select_clicked)
        self._connect(self._ui.account_back_button, 'clicked', self._on_back_clicked)
        self._connect(self._ui.account_select_button, 'clicked', self._on_select_clicked)

        self._ui.listbox.set_placeholder(self._ui.placeholder)
        self._ui.listbox.set_filter_func(self._filter_func, None)
        self._connect(self._ui.listbox, 'row-activated', self._on_row_activated)

        self._global_search_view = GlobalSearch()
        self._connect(self._global_search_view, 'activate', self._on_global_row_activated)
        self._ui.global_scrolled.set_child(self._global_search_view)

        self._muc_info_box = GroupChatInfoScrolled()
        self._ui.info_box.append(self._muc_info_box)

        self._ui.infobar.set_reveal_child(app.settings.get('show_help_start_chat'))

        self._current_filter = 'all'
        self._chat_filter = ChatFilter()
        self._connect(self._chat_filter, 'filter-changed', self._on_chat_filter_changed)
        self._ui.filter_bar_revealer.set_child(self._chat_filter)

        self._connect(self.get_default_controller(), 'key-pressed', self._on_key_pressed)

        if rows:
            self._load_contacts(rows)

        self._initial_message: dict[str, str | None] = {}
        if initial_jid is not None:
            self._initial_message[initial_jid] = initial_message
            self._ui.search_entry.set_text(initial_jid)

        self.select_first_row()

        self.show()

    def _cleanup(self, *args: Any) -> None:
        del self._nick_chooser
        del self._global_search_view
        del self._muc_info_box
        del self._chat_filter
        del self._accounts_store
        self._new_contact_rows.clear()
        self._ui.listbox.set_filter_func(None)
        self._destroyed = True
        app.cancel_tasks(self)

    def remove_row(self, account: str, jid: str) -> None:
        for row in cast(list[ContactRow], list(iterate_listbox_children(self._ui.listbox))):
            if row.account == account and row.jid == jid:
                self._ui.listbox.remove(row)
                return

    def _global_search_active(self) -> bool:
        return self._ui.global_search_toggle.get_active()

    def _add_accounts(self) -> None:
        for account in self._accounts:
            self._accounts_store.append([None, *account])

    def _add_contacts(self, rows: list[ContactRow]):
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            client = app.get_client(account)
            for jid, _data in client.get_module('Roster').iter():
                contact = client.get_module('Contacts').get_contact(jid)
                rows.append(ContactRow(account,
                                       contact,
                                       jid,
                                       contact.name,
                                       show_account))
            self_contact = client.get_module('Contacts').get_contact(
                client.get_own_jid().bare)
            rows.append(ContactRow(account,
                                   self_contact,
                                   self_contact.jid,
                                   _('Note to myself'),
                                   show_account))

    def _add_groupchats(self, rows: list[ContactRow]) -> None:
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            client = app.get_client(account)
            bookmarks = client.get_module('Bookmarks').bookmarks
            for bookmark in bookmarks:
                contact = client.get_module('Contacts').get_contact(
                    bookmark.jid, groupchat=True)
                rows.append(ContactRow(account,
                                       contact,
                                       bookmark.jid,
                                       contact.name,
                                       show_account,
                                       groupchat=True))

    def _add_new_contact_rows(self, rows: list[ContactRow]) -> None:
        for account, _label in self._accounts:
            show_account = len(self._accounts) > 1
            row = ContactRow(account, None, None, None, show_account)
            self._new_contact_rows[account] = row
            rows.append(row)

    def _load_contacts(self, rows: list[ContactRow]) -> None:
        for row in rows:
            self._ui.listbox.append(row)

        self._ui.listbox.set_sort_func(self._sort_func, None)

    def _on_page_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        if stack.get_visible_child_name() == 'account':
            self._ui.account_view.grab_focus()

    def _on_row_activated(self,
                          _listbox: Gtk.ListBox,
                          row: ContactRow
                          ) -> None:
        if self._current_view_is(Search.GLOBAL):
            self._select_muc()
        else:
            self._start_new_chat(row)

    def _on_global_row_activated(
        self,
        _listview: Gtk.ListView,
        position: int
    ) -> None:
        print(position)

    def _select_muc(self) -> None:
        if len(self._accounts) > 1:
            self._ui.stack.set_visible_child_name('account')
        else:
            self._on_select_clicked()

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType
    ) -> bool:
        is_search = self._ui.stack.get_visible_child_name() == 'search'
        if keyval in (Gdk.KEY_Down, Gdk.KEY_Tab):
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_view.select_next()
            else:
                self._ui.search_entry.emit('next-match')
            return Gdk.EVENT_STOP

        if (state == Gdk.ModifierType.SHIFT_MASK and
                keyval == Gdk.KEY_ISO_Left_Tab):
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_view.select_prev()
            else:
                self._ui.search_entry.emit('previous-match')
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Up:
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_view.select_prev()
            else:
                self._ui.search_entry.emit('previous-match')
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Escape:
            if self._ui.stack.get_visible_child_name() == 'progress':
                # Propagate to GajimAppWindow
                return Gdk.EVENT_PROPAGATE

            if self._ui.stack.get_visible_child_name() == 'account':
                self._on_back_clicked()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() in ('error', 'info'):
                self._ui.stack.set_visible_child_name('search')
                return Gdk.EVENT_STOP

            self._search_stopped = True
            self._ui.search_entry.grab_focus()
            self._scroll_to_first_row()
            self._global_search_view.remove_all()
            if self._ui.search_entry.get_text() != '':
                self._ui.search_entry.emit('stop-search')
                return Gdk.EVENT_STOP

            # Propagate to GajimAppWindow
            return Gdk.EVENT_PROPAGATE

        text_widget = self._ui.search_entry.get_delegate()
        assert isinstance(text_widget, Gtk.Text)

        if keyval == Gdk.KEY_Return:
            if self._ui.stack.get_visible_child_name() == 'progress':
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'account':
                self._on_select_clicked()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'error':
                self._ui.stack.set_visible_child_name('search')
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'info':
                self._on_join_clicked()
                return Gdk.EVENT_STOP

            if self._current_view_is(Search.GLOBAL):
                if (text_widget.has_focus() and self._ui.search_entry.get_text()):
                    self._global_search_view.remove_all()
                    self._start_search()

                elif self._global_search_view.get_selected_row() is not None:
                    self._select_muc()
                return Gdk.EVENT_STOP

            row = self._ui.listbox.get_selected_row()
            if row is not None:
                row.emit('activate')
            return Gdk.EVENT_STOP

        if is_search:
            text_widget.grab_focus_without_selecting()

        return Gdk.EVENT_PROPAGATE

    def _on_infobar_close_clicked(
        self,
        _button: Gtk.Button,
    ) -> None:
        self._ui.infobar.set_reveal_child(False)
        app.settings.set('show_help_start_chat', False)

    def _on_filter_bar_toggled(self, toggle_button: Gtk.ToggleButton) -> None:
        active = toggle_button.get_active()
        self._ui.filter_bar_revealer.set_reveal_child(active)

    def _on_chat_filter_changed(self, _filter: ChatFilter, name: str) -> None:
        self._current_filter = name
        self._ui.listbox.invalidate_filter()

    def _start_new_chat(self, row: ContactRow) -> None:
        if row.jid is None:
            return

        if row.is_new:
            try:
                validate_jid(row.jid)
            except ValueError as error:
                self._show_error_page(str(error))
                return

            self._disco_info(row)
            return

        if row.groupchat:
            if not app.account_is_available(row.account):
                self._show_error_page(_('You can not join a group chat '
                                        'unless you are connected.'))
                return

            self.ready_to_destroy = True
            if app.window.chat_exists(row.account, row.jid):
                app.window.select_chat(row.account, row.jid)
                self.close()
                return

            self.ready_to_destroy = False
            self._redirected = False
            self._disco_muc(row.account, row.jid, request_vcard=row.is_new)

        else:
            initial_message = self._initial_message.get(str(row.jid))
            app.window.add_chat(
                row.account,
                row.jid,
                'contact',
                select=True,
                message=initial_message)
            self.ready_to_destroy = True
            self.close()

    def _disco_info(self, row: ContactRow) -> None:
        if not app.account_is_available(row.account):
            self._show_error_page(_('You are offline.'))
            return

        self._ui.stack.set_visible_child_name('progress')
        client = app.get_client(row.account)
        client.get_module('Discovery').disco_info(
            row.jid,
            callback=self._disco_info_received,
            user_data=row,
            timeout=10)

    def _disco_info_received(self, task: Task) -> None:
        row = cast(ContactRow, task.get_user_data())
        try:
            result = cast(DiscoInfo, task.finish())
        except StanzaError as error:
            contact_conditions = [
                'service-unavailable',  # Prosody
                'subscription-required',  # ejabberd
                'feature-not-implemented'  # transports/bridges
            ]
            if error.condition in contact_conditions:
                # These error conditions are the result of
                # querying contacts without subscription
                row.update_chat_type()
                self._start_new_chat(row)
                return

            # Handle other possible errors
            self._show_error_page(error.get_text())
            return
        except TimeoutStanzaError:
            # We reached the 10s timeout and we cannot
            # assume which kind contact this is.
            self._show_error_page(_('This address is not reachable.'))
            return

        if result.is_muc and not result.jid.is_domain:
            # This is mostly a fix for the MUC protocol, there is no
            # way to differentiate between a MUC service and room.
            # Except the MUC XEP defines rooms should have a localpart.
            row.update_chat_type(groupchat=True)
        else:
            row.update_chat_type()
        self._start_new_chat(row)

    def _disco_muc(self, account: str, jid: JID, request_vcard: bool) -> None:
        self._ui.stack.set_visible_child_name('progress')
        client = app.get_client(account)
        client.get_module('Discovery').disco_muc(
            jid,
            request_vcard=request_vcard,
            allow_redirect=True,
            timeout=10,
            callback=self._muc_disco_info_received,
            user_data=account)

    def _muc_disco_info_received(self, task: Task) -> None:
        try:
            result = cast(DiscoInfo, task.finish())
        except (StanzaError, TimeoutStanzaError) as error:
            self._set_error(error)
            return

        account = task.get_user_data()

        if result.info.is_muc:
            self._muc_info_box.set_account(account)
            self._muc_info_box.set_from_disco_info(result.info)
            self._nick_chooser.set_text(get_group_chat_nick(
                account, result.info.jid))
            self._ui.stack.set_visible_child_name('info')

        else:
            self._set_error_from_code('not-muc-service')

    def _set_error(self, error: StanzaError | TimeoutStanzaError) -> None:
        if isinstance(error, TimeoutStanzaError):
            text = _('This address is not reachable.')
        else:
            text = MUC_DISCO_ERRORS.get(error.condition, to_user_string(error))
            if error.condition == 'gone':
                reason = error.get_text(get_rfc5646_lang())
                if reason:
                    text = f'{text}:\n{reason}'
        self._show_error_page(text)

    def _set_error_from_code(self, error_code: str) -> None:
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _show_error_page(self, text: str) -> None:
        self._ui.error_label.set_text(str(text))
        self._ui.stack.set_visible_child_name('error')

    def _on_join_clicked(self, *args: Any) -> None:
        account = self._muc_info_box.get_account()
        jid = self._muc_info_box.get_jid()
        nickname = self._nick_chooser.get_text()
        assert account
        app.window.show_add_join_groupchat(
            account, str(jid), nickname=nickname)

        self.ready_to_destroy = True
        self.close()

    def _on_back_clicked(self, *args: Any) -> None:
        self._ui.stack.set_visible_child_name('search')

    def _on_select_clicked(self, *args: Any) -> None:
        model, iter_ = self._ui.account_view.get_selection().get_selected()
        if iter_ is not None:
            account = model[iter_][1]
        elif len(self._accounts) == 1:
            account = self._accounts[0][0]
        else:
            return

        selected_row = cast(
            MuclumbusViewItem, self._global_search_view.get_selected_row())
        if selected_row is None:
            return

        if not app.account_is_available(account):
            self._show_error_page(_('You can not join a group chat '
                                    'unless you are connected.'))
            return

        self._redirected = False
        self._disco_muc(account, selected_row.jid, request_vcard=True)

    def _current_view_is(self, view: Search) -> bool:
        page_name =  self._ui.list_stack.get_visible_child_name()
        if view == Search.CONTACT:
            return page_name == 'contacts'
        return page_name == 'global'

    def _on_global_search_toggle(self, button: Gtk.ToggleButton) -> None:
        self._ui.search_entry.grab_focus()
        image = cast(Gtk.Image, button.get_child())
        if button.get_active():
            self._ui.filter_bar_toggle.set_active(False)
            self._ui.filter_bar_toggle.set_sensitive(False)
            image.add_css_class('selected-color')
            self._ui.list_stack.set_visible_child_name('global')
            if self._ui.search_entry.get_text():
                self._start_search()
            self._ui.listbox.invalidate_filter()
        else:
            self._ui.filter_bar_toggle.set_sensitive(True)
            self._ui.search_entry.set_text('')
            image.remove_css_class('selected-color')
            self._ui.list_stack.set_visible_child_name('contacts')
            self._global_search_view.remove_all()

    def _on_search_changed(self, search_entry: Gtk.SearchEntry) -> None:
        self._show_search_entry_error(False)
        self._search_is_valid_jid = False

        if self._global_search_active():
            return

        search_text = search_entry.get_text()
        uri = parse_uri(search_text)
        if uri.type == URIType.XMPP:
            search_entry.set_text(uri.data['jid'])
            return

        if search_text:
            try:
                validate_jid(search_text)
            except ValueError:
                self._show_search_entry_error(True)
            else:
                self._update_new_contact_rows(search_text)
                self._search_is_valid_jid = True

        self._ui.listbox.invalidate_filter()

    def _show_search_entry_error(self, state: bool):
        self._ui.search_error_box.set_visible(state)

    def _update_new_contact_rows(self, search_text: str) -> None:
        for row in self._new_contact_rows.values():
            if row is not None:
                row.update_jid(JID.from_string(search_text))

    def _select_new_match(self,
                          _entry: Gtk.Entry,
                          direction: Direction
                          ) -> None:
        selected_row = self._ui.listbox.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()

        if direction == Direction.NEXT:
            index += 1
        else:
            index -= 1

        while True:
            new_selected_row = self._ui.listbox.get_row_at_index(index)
            if new_selected_row is None:
                return
            if new_selected_row.get_child_visible():
                self._ui.listbox.select_row(new_selected_row)
                new_selected_row.grab_focus()
                return
            if direction == Direction.NEXT:
                index += 1
            else:
                index -= 1

    def select_first_row(self) -> None:
        first_row = self._ui.listbox.get_row_at_y(0)
        self._ui.listbox.select_row(first_row)

    def _scroll_to_first_row(self) -> None:
        self._ui.scrolledwindow.get_vadjustment().set_value(0)

    def _filter_func(self, row: ContactRow, _user_data: Any) -> bool:
        if row.contact is None:
            # new contact row
            return self._search_is_valid_jid

        search_text = self._ui.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_search_text().lower()

        if self._current_filter == 'chats' and row.groupchat:
            return False

        if self._current_filter == 'group_chats' and not row.groupchat:
            return False

        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self.select_first_row)
                return False
        GLib.timeout_add(50, self.select_first_row)
        return True

    @staticmethod
    def _sort_func(row1: ContactRow, row2: ContactRow, _user_data: Any) -> int:
        name1 = row1.get_search_text()
        name2 = row2.get_search_text()
        account1 = row1.account
        account2 = row2.account
        is_groupchat1 = row1.groupchat
        is_groupchat2 = row2.groupchat
        new1 = row1.is_new
        new2 = row2.is_new

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        if new1 != new2:
            return 1 if new1 else -1

        if is_groupchat1 != is_groupchat2:
            return 1 if is_groupchat1 else -1

        return locale.strcoll(name1.lower(), name2.lower())

    def _start_search(self) -> None:
        self._search_stopped = False
        accounts = app.get_connected_accounts()
        if not accounts:
            return
        client = app.get_client(accounts[0]).connection

        text = self._ui.search_entry.get_text().strip()
        self._global_search_view.start_search()

        if app.settings.get('muclumbus_api_pref') == 'http':
            self._start_http_search(client, text)
        else:
            self._start_iq_search(client, text)

    @as_task
    def _start_iq_search(self, client, text):
        _task = yield  # noqa: F841

        if self._parameter_form is None:
            result = yield client.get_module('Muclumbus').request_parameters(
                app.settings.get('muclumbus_api_jid'))

            self._process_search_result(result, parameters=True)

            self._parameter_form = result
            self._parameter_form.type_ = 'submit'

        self._parameter_form.vars['q'].value = text

        result = yield client.get_module('Muclumbus').set_search(
            app.settings.get('muclumbus_api_jid'),
            self._parameter_form)

        self._process_search_result(result)

        while not result.end:
            result = yield client.get_module('Muclumbus').set_search(
                app.settings.get('muclumbus_api_jid'),
                self._parameter_form,
                items_per_page=result.max,
                after=result.last)

            self._process_search_result(result)

        self._global_search_view.end_search()

    @as_task
    def _start_http_search(self, client, text):
        _task = yield  # noqa: F841

        self._keywords = text.split(' ')
        result = yield client.get_module('Muclumbus').set_http_search(
            app.settings.get('muclumbus_api_http_uri'),
            self._keywords)

        self._process_search_result(result)

        while not result.end:
            result = yield client.get_module('Muclumbus').set_http_search(
                app.settings.get('muclumbus_api_http_uri'),
                self._keywords,
                after=result.last)

            self._process_search_result(result)

        self._global_search_view.end_search()

    def _process_search_result(self,
                               result: MuclumbusResult,
                               parameters: bool = False
                               ) -> None:
        if self._search_stopped:
            raise CancelledError

        if is_error(result):
            assert isinstance(result, StanzaError)
            self._global_search_view.remove_progress()
            self._show_error_page(to_user_string(result))
            raise result

        if parameters:
            return

        for item in result.items:
            self._global_search_view.add(item)


class ContactRow(Gtk.ListBoxRow, SignalManager):
    def __init__(self,
                 account: str,
                 contact: ContactT | None,
                 jid: JID | None,
                 name: str | None,
                 show_account: bool,
                 groupchat: bool = False
                 ) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

        self.add_css_class('start-chat-row')

        self.account = account
        self.account_label = app.get_account_label(account)
        self.show_account = show_account
        self.jid = jid
        self.contact = contact
        self.name = name
        self.groupchat = groupchat
        self.is_new = bool(jid is None)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_size_request(260, -1)

        image = self._get_avatar_image(contact)
        image.set_size_request(AvatarSize.CHAT, AvatarSize.CHAT)
        grid.attach(image, 0, 0, 1, 1)

        self._tooltip = ContactTooltip()
        image.set_has_tooltip(True)
        self._connect(image, 'query-tooltip', self._on_query_tooltip)

        if self.name is None:
            self.name = _('Start New Chat')

        meta_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)

        self.name_label = Gtk.Label(label=self.name)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_xalign(0)
        self.name_label.set_width_chars(20)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.get_style_context().add_class('bold14')
        meta_box.append(self.name_label)

        if contact and not contact.is_groupchat:
            if idle := contact.idle_datetime:
                idle_badge = IdleBadge(idle)
                meta_box.append(idle_badge)

        if contact and not contact.is_groupchat and (status := contact.status):
            self.status_label = Gtk.Label(
                label=status,
                ellipsize=Pango.EllipsizeMode.END,
                xalign=0,
                width_chars=22,
                halign=Gtk.Align.START,
            )
            self.status_label.get_style_context().add_class('dim-label')
            self.status_label.get_style_context().add_class('small-label')
            meta_box.append(self.status_label)

        grid.attach(meta_box, 1, 0, 1, 3)

        badge_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        if show_account:
            account_badge = AccountBadge(account)
            account_badge.set_halign(Gtk.Align.END)
            account_badge.set_valign(Gtk.Align.START)
            account_badge.set_hexpand(True)
            badge_box.append(account_badge)

        if contact and not contact.is_groupchat and not contact.is_pm_contact:
            groups = contact.groups
            for group in groups:
                group_badge = GroupBadge(group)
                badge_box.append(group_badge)

        grid.attach(badge_box, 2, 0, 1, 3)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, 'pressed', self._popup_menu)
        self.add_controller(gesture_secondary_click)

        self._menu_popover = GajimPopover(None)
        grid.attach(self._menu_popover, 0, 1, 1, 1)

        self._grid = grid
        self.set_child(grid)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        self._disconnect_all()
        del self._menu_popover
        del self._grid
        app.check_finalize(self)

    def _on_query_tooltip(self,
                          _img: Gtk.Image,
                          _x_coord: int,
                          _y_coord: int,
                          _keyboard_mode: bool,
                          tooltip: Gtk.Tooltip) -> bool:
        if not isinstance(self.contact, BareContact):
            return False
        v, widget = self._tooltip.get_tooltip(self.contact)
        tooltip.set_custom(widget)
        return v

    def _popup_menu(
        self,
        _gesture_click : Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        if not self.groupchat:
            return Gdk.EVENT_PROPAGATE

        menu = get_start_chat_row_menu(self.account, self.jid)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()

        return Gdk.EVENT_PROPAGATE

    def _get_avatar_image(self, contact: ContactT) -> Gtk.Image:
        if self.is_new:
            icon_name = 'avatar-default'
            if self.groupchat:
                icon_name = get_status_icon_name('muc-inactive')
            return Gtk.Image.new_from_icon_name(icon_name)

        scale = self.get_scale_factor()
        texture = contact.get_avatar(AvatarSize.CHAT, scale)
        return Gtk.Image.new_from_paintable(texture)

    def update_jid(self, jid: JID) -> None:
        self.jid = jid
        self._grid.set_tooltip_text(str(jid))

    def update_chat_type(self, groupchat: bool = False) -> None:
        self.is_new = False
        self.groupchat = groupchat

    def get_search_text(self) -> str:
        if self.contact is None and not self.groupchat:
            return str(self.jid)

        return f'{self.name} {self.jid}'


class GlobalSearch(Gtk.ListView, SignalManager):
    def __init__(self) -> None:
        Gtk.ListView.__init__(
            self,
            has_tooltip=True,
            single_click_activate=True,
        )
        SignalManager.__init__(self)

        self.model = Gio.ListStore(item_type=MuclumbusListItem)

        factory = Gtk.SignalListItemFactory()
        self._connect(factory, 'setup', self._on_factory_setup)
        self._connect(factory, 'bind', self._on_factory_bind)
        self._connect(factory, 'unbind', self._on_factory_unbind)

        self.set_model(Gtk.NoSelection(model=self.model))
        self.set_factory(factory)

    def do_unroot(self) -> None:
        Gtk.ListView.do_unroot(self)
        self._disconnect_all()
        del self.model
        app.check_finalize(self)

    def remove_all(self) -> None:
        self.model.remove_all()

    def _on_factory_setup(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        list_item.set_child(MuclumbusViewItem())

    def _on_factory_bind(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        row = list_item.get_child()
        obj = list_item.get_item()
        row.bind_gobject(obj)

    def _on_factory_unbind(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        row = list_item.get_child()
        row.unbind_gobject()

    # def _add_placeholder(self) -> None:
    # TODO GTK4
    #     placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    #     placeholder.set_halign(Gtk.Align.CENTER)
    #     placeholder.set_valign(Gtk.Align.CENTER)
    #     icon = Gtk.Image.new_from_icon_name('system-search-symbolic')
    #     icon.get_style_context().add_class('dim-label')
    #     label = Gtk.Label(label=_('Search for group chats globally\n'
    #                               '(press Return to start search)'))
    #     label.get_style_context().add_class('dim-label')
    #     label.set_justify(Gtk.Justification.CENTER)
    #     label.set_max_width_chars(35)
    #     placeholder.append(icon)
    #     placeholder.append(label)
    #     self.set_placeholder(placeholder)

    def remove_progress(self) -> None:
        # assert self._progress
        # self.remove(self._progress)
        pass

    def start_search(self) -> None:
        # self._progress = ProgressRow()
        # self.append(self._progress)
        pass

    def end_search(self) -> None:
        # assert self._progress
        # self._progress.stop()
        pass

    def add(self, item: MuclumbusItem) -> None:
        self.model.append(MuclumbusListItem(item=item))

    def _select(self, direction: Direction) -> None:
        selected_row = self.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()
        if direction == Direction.NEXT:
            index += 1
        else:
            index -= 1

        new_selected_row = self.get_row_at_index(index)
        if new_selected_row is None:
            return

        self.select_row(new_selected_row)
        new_selected_row.grab_focus()

    def select_next(self) -> None:
        self._select(Direction.NEXT)

    def select_prev(self) -> None:
        self._select(Direction.PREV)


class MuclumbusListItem(GObject.Object):
    __gtype_name__ = "MuclumbusListItem"

    def __init__(self, item: MuclumbusItem) -> None:
        super().__init__()

        self._item = item
        jid = JID.from_string(self._item.jid)
        self._name = self._item.name or jid.localpart or str(jid)

        language_code = item.language.upper()
        if len(language_code) < 2:
            language_code = ''

        if len(language_code) > 2:
            # Fix if no ISO code has been provided
            language_code = language_code[:2]

        if language_code == 'EN':
            # Fix for most used languages/countries
            language_code = 'GB'

        self._language_code = get_country_flag_from_code(language_code)

    @GObject.Property(type=str)
    def jid(self) -> str:
        return self._item.jid

    @GObject.Property(type=str)
    def name(self) -> str:
        return self._name

    @GObject.Property(type=str)
    def nusers(self) -> str:
        return self._item.nusers

    @GObject.Property(type=str)
    def description(self) -> str:
        return self._item.description

    @GObject.Property(type=str)
    def language(self) -> str:
        return self._item.language

    @GObject.Property(type=str)
    def language_code(self) -> str:
        return self._language_code

    @GObject.Property(type=str)
    def is_open(self) -> bool:
        return self._item.is_open

    @GObject.Property(type=str)
    def anonymity_mode(self) -> AnonymityMode:
        return self._item.anonymity_mode

    def __repr__(self) -> str:
        return f"MuclumbusListItem: {self._item}"


class MuclumbusViewItem(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(
            self,
            spacing=12,
            css_classes=['start-chat-row']
        )

        self.__bindings: list[GObject.Binding] = []

        self._name_label = Gtk.Label(
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=40,
            css_classes=['bold16']
        )

        self._description_label = Gtk.Label(
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=40,
            css_classes=['dim-label']
        )

        self._name_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
        )
        self._name_box.append(self._name_label)
        self._name_box.append(self._description_label)

        self.append(self._name_box)

        self._language_label = Gtk.Label()
        self.append(self._language_label)

        users_box = Gtk.Box(
            spacing=6,
            tooltip_text=_('Participants Count'),
            css_classes=['dim-label'],
        )

        users_icon = Gtk.Image.new_from_icon_name('system-users-symbolic')
        users_box.append(users_icon)

        self._users_count_label = Gtk.Label()
        users_box.append(self._users_count_label)

        self.append(users_box)

    def bind_gobject(self, obj: MuclumbusListItem) -> None:
        bind = obj.bind_property('name', self._name_label, "label", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)
        bind = obj.bind_property('description', self._description_label, "label", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)
        bind = obj.bind_property('jid', self._name_box, "tooltip_text", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)
        bind = obj.bind_property('language_code', self._language_label, "label", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)
        bind = obj.bind_property('language', self._language_label, "tooltip_text", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)
        bind = obj.bind_property('nusers', self._users_count_label, "label", GObject.BindingFlags.SYNC_CREATE)
        self.__bindings.append(bind)

    def unbind_gobject(self) -> None:
        for bind in self.__bindings:
            bind.unbind()
        self.__bindings.clear()

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)


class ProgressRow(Gtk.ListBoxRow):
    def __init__(self) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.set_selectable(False)
        self.set_activatable(False)
        self.get_style_context().add_class('start-chat-row')
        self._text = _('%s group chats found')
        self._count = 0
        self._spinner = Gtk.Spinner()
        self._spinner.start()
        self._count_label = Gtk.Label(label=self._text % 0)
        self._count_label.get_style_context().add_class('bold')
        self._finished_image = Gtk.Image.new_from_icon_name(
            'emblem-ok-symbolic')
        self._finished_image.get_style_context().add_class('success-color')
        self._finished_image.set_visible(False)

        box = Gtk.Box()
        box.set_spacing(6)
        box.append(self._finished_image)
        box.append(self._spinner)
        box.append(self._count_label)
        self.set_child(box)

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def update(self) -> None:
        self._count += 1
        self._count_label.set_text(self._text % self._count)

    def stop(self) -> None:
        self._spinner.stop()
        self._spinner.hide()
        self._finished_image.show()
