# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import locale
from enum import IntEnum

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Pango

from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.errors import CancelledError

from gajim.common import app
from gajim.common.helpers import validate_jid
from gajim.common.helpers import to_user_string
from gajim.common.helpers import get_group_chat_nick
from gajim.common.i18n import _
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.const import AvatarSize
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.modules.util import as_task

from .chat_filter import ChatFilter
from .groupchat_info import GroupChatInfoScrolled
from .groupchat_nick import NickChooser
from .util import get_builder
from .util import get_icon_name
from .util import AccountBadge


class Search(IntEnum):
    CONTACT = 0
    GLOBAL = 1


class StartChatDialog(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('StartChatDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Start / Join Chat'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(-1, 600)
        self.ready_to_destroy = False
        self._parameter_form = None
        self._keywords = []
        self._destroyed = False
        self._search_stopped = False
        self._redirected = False
        self._source_id = None

        self._ui = get_builder('start_chat_dialog.ui')
        self.add(self._ui.stack)

        self._nick_chooser = NickChooser()
        self._ui.join_box.pack_start(self._nick_chooser, True, False, 0)

        # Helper for the case where we don't receive a disco info
        self._new_chat_row = None

        self.new_contact_row_visible = False
        self.new_contact_rows = {}
        self._accounts = app.get_enabled_accounts_with_labels()

        rows = []
        self._add_accounts()
        self._add_contacts(rows)
        self._add_groupchats(rows)

        self._ui.search_entry.connect('search-changed',
                                      self._on_search_changed)
        self._ui.search_entry.connect('next-match',
                                      self._select_new_match, 'next')
        self._ui.search_entry.connect('previous-match',
                                      self._select_new_match, 'prev')
        self._ui.search_entry.connect(
            'stop-search', lambda *args: self._ui.search_entry.set_text(''))

        self._ui.listbox.set_placeholder(self._ui.placeholder)
        self._ui.listbox.set_filter_func(self._filter_func, None)
        self._ui.listbox.connect('row-activated', self._on_row_activated)

        self._global_search_listbox = GlobalSearch()
        self._global_search_listbox.connect('row-activated',
                                            self._on_row_activated)
        self._current_listbox = self._ui.listbox

        self._muc_info_box = GroupChatInfoScrolled()
        self._ui.info_box.add(self._muc_info_box)

        self._ui.infobar.set_revealed(app.settings.get('show_help_start_chat'))

        self._current_filter = 'all'
        self._chat_filter = ChatFilter()
        self._chat_filter.connect(
            'filter-changed', self._on_chat_filter_changed)
        self._ui.filter_bar_revealer.add(self._chat_filter)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._destroy)

        self.select_first_row()
        self._ui.connect_signals(self)
        self.show_all()

        if rows:
            self._load_contacts(rows)

    def set_search_text(self, text):
        self._ui.search_entry.set_text(text)

    def _global_search_active(self):
        return self._ui.global_search_toggle.get_active()

    def _add_accounts(self):
        for account in self._accounts:
            self._ui.account_store.append([None, *account])

    def _add_contacts(self, rows):
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            self.new_contact_rows[account] = None
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

    def _add_groupchats(self, rows):
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

    def _load_contacts(self, rows):
        generator = self._incremental_add(rows)
        self._source_id = GLib.idle_add(lambda: next(generator, False),
                                        priority=GLib.PRIORITY_LOW)

    def _incremental_add(self, rows):
        for row in rows:
            self._ui.listbox.add(row)
            yield True

        self._ui.listbox.set_sort_func(self._sort_func, None)
        self._source_id = None

    def _on_page_changed(self, stack, _param):
        if stack.get_visible_child_name() == 'account':
            self._ui.account_view.grab_focus()

    def _on_row_activated(self, _listbox, row):
        if self._current_listbox_is(Search.GLOBAL):
            self._select_muc()
        else:
            self._start_new_chat(row)

    def _select_muc(self):
        if len(self._accounts) > 1:
            self._ui.stack.set_visible_child_name('account')
        else:
            self._on_select_clicked()

    def _on_key_press(self, _widget, event):
        is_search = self._ui.stack.get_visible_child_name() == 'search'
        if event.keyval in (Gdk.KEY_Down, Gdk.KEY_Tab):
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_listbox.select_next()
            else:
                self._ui.search_entry.emit('next-match')
            return Gdk.EVENT_STOP

        if (event.state == Gdk.ModifierType.SHIFT_MASK and
                event.keyval == Gdk.KEY_ISO_Left_Tab):
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_listbox.select_prev()
            else:
                self._ui.search_entry.emit('previous-match')
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Up:
            if not is_search:
                return Gdk.EVENT_PROPAGATE

            if self._global_search_active():
                self._global_search_listbox.select_prev()
            else:
                self._ui.search_entry.emit('previous-match')
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Escape:
            if self._ui.stack.get_visible_child_name() == 'progress':
                self.destroy()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'account':
                self._on_back_clicked()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() in ('error', 'info'):
                self._ui.stack.set_visible_child_name('search')
                return Gdk.EVENT_STOP

            self._search_stopped = True
            self._ui.search_entry.grab_focus()
            self._scroll_to_first_row()
            self._global_search_listbox.remove_all()
            if self._ui.search_entry.get_text() != '':
                self._ui.search_entry.emit('stop-search')
            else:
                self.destroy()
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Return:
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

            if self._current_listbox_is(Search.GLOBAL):
                if self._ui.search_entry.is_focus():
                    self._global_search_listbox.remove_all()
                    self._start_search()

                elif self._global_search_listbox.get_selected_row() is not None:
                    self._select_muc()
                return Gdk.EVENT_STOP

            row = self._ui.listbox.get_selected_row()
            if row is not None:
                row.emit('activate')
            return Gdk.EVENT_STOP

        if is_search:
            self._ui.search_entry.grab_focus_without_selecting()
        return Gdk.EVENT_PROPAGATE

    def _on_infobar_response(self, _widget, response):
        if response == Gtk.ResponseType.CLOSE:
            self._ui.infobar.set_revealed(False)
            app.settings.set('show_help_start_chat', False)

    def _on_filter_bar_toggled(self, toggle_button):
        active = toggle_button.get_active()
        self._ui.filter_bar_revealer.set_reveal_child(active)

    def _on_chat_filter_changed(self, _filter, name):
        self._current_filter = name
        self._ui.listbox.invalidate_filter()

    def _start_new_chat(self, row):
        if row.new:
            try:
                validate_jid(row.jid)
            except ValueError as error:
                self._show_error_page(error)
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
                self.destroy()
                return

            self.ready_to_destroy = False
            self._redirected = False
            self._disco_muc(row.account, row.jid, request_vcard=row.new)

        else:
            app.window.add_chat(row.account, row.jid, 'contact', select=True)
            self.ready_to_destroy = True
            self.destroy()

    def _disco_info(self, row):
        if not app.account_is_available(row.account):
           # Account is disconnected: offer to open 1:1 chat anyway
           self._new_chat_row = row
           self._ui.stack.set_visible_child_name('no-disco')
           return

        self._ui.stack.set_visible_child_name('progress')
        client = app.get_client(row.account)
        client.get_module('Discovery').disco_info(
            row.jid,
            callback=self._disco_info_received,
            user_data=row,
            timeout=10)

    def _disco_info_received(self, task):
        row = task.get_user_data()
        try:
            result = task.finish()
        except StanzaError as error:
            contact_conditions = [
                'service-unavailable',  # Prosody
                'subscription-required'  # ejabberd
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
            # We reached the 10s timeout, but we should
            # offer to open a chat anyway
            self._new_chat_row = row
            self._ui.stack.set_visible_child_name('no-disco')
            return

        if result.is_muc:
            row.update_chat_type(groupchat=True)
        else:
            row.update_chat_type()
        self._start_new_chat(row)

    def _on_no_disco_continue(self, _button):
        self._new_chat_row.update_chat_type()
        self._start_new_chat(self._new_chat_row)

    def _disco_muc(self, account, jid, request_vcard):
        self._ui.stack.set_visible_child_name('progress')
        client = app.get_client(account)
        client.get_module('Discovery').disco_muc(
            jid,
            request_vcard=request_vcard,
            allow_redirect=True,
            callback=self._muc_disco_info_received,
            user_data=account)

    def _muc_disco_info_received(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
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

    def _set_error(self, error):
        text = MUC_DISCO_ERRORS.get(error.condition, to_user_string(error))
        if error.condition == 'gone':
            reason = error.get_text(get_rfc5646_lang())
            if reason:
                text = '%s:\n%s' % (text, reason)
        self._show_error_page(text)

    def _set_error_from_code(self, error_code):
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _show_error_page(self, text):
        self._ui.error_label.set_text(str(text))
        self._ui.stack.set_visible_child_name('error')

    def _on_join_clicked(self, _button=None):
        account = self._muc_info_box.get_account()
        jid = self._muc_info_box.get_jid()
        nickname = self._nick_chooser.get_text()

        app.interface.show_add_join_groupchat(account, jid, nickname=nickname)

        self.ready_to_destroy = True
        self.destroy()

    def _on_back_clicked(self, _button=None):
        self._ui.stack.set_visible_child_name('search')

    def _on_select_clicked(self, *args):
        model, iter_ = self._ui.account_view.get_selection().get_selected()
        if iter_ is not None:
            account = model[iter_][1]
        elif len(self._accounts) == 1:
            account = self._accounts[0][0]
        else:
            return

        selected_row = self._global_search_listbox.get_selected_row()
        if selected_row is None:
            return

        if not app.account_is_available(account):
            self._show_error_page(_('You can not join a group chat '
                                    'unless you are connected.'))
            return

        self._redirected = False
        self._disco_muc(account, selected_row.jid, request_vcard=True)

    def _set_listbox(self, listbox):
        if self._current_listbox == listbox:
            return
        viewport = self._ui.scrolledwindow.get_child()
        viewport.remove(viewport.get_child())
        self._ui.scrolledwindow.remove(viewport)
        self._ui.scrolledwindow.add(listbox)
        self._current_listbox = listbox

    def _current_listbox_is(self, box):
        if self._current_listbox == self._ui.listbox:
            return box == Search.CONTACT
        return box == Search.GLOBAL

    def _on_global_search_toggle(self, button):
        self._ui.search_entry.grab_focus()
        image_style_context = button.get_children()[0].get_style_context()
        if button.get_active():
            self._ui.filter_bar_toggle.set_active(False)
            self._ui.filter_bar_toggle.set_sensitive(False)
            image_style_context.add_class('selected-color')
            self._set_listbox(self._global_search_listbox)
            if self._ui.search_entry.get_text():
                self._start_search()
            self._remove_new_jid_row()
            self._ui.listbox.invalidate_filter()
        else:
            self._ui.filter_bar_toggle.set_sensitive(True)
            self._ui.search_entry.set_text('')
            image_style_context.remove_class('selected-color')
            self._set_listbox(self._ui.listbox)
            self._global_search_listbox.remove_all()

    def _on_search_changed(self, entry):
        if self._global_search_active():
            return

        search_text = entry.get_text()
        if '@' in search_text:
            self._add_new_jid_row()
            self._update_new_jid_rows(search_text)
        else:
            self._remove_new_jid_row()
        self._ui.listbox.invalidate_filter()

    def _add_new_jid_row(self):
        if self.new_contact_row_visible:
            return
        for account in self.new_contact_rows:
            show_account = len(self._accounts) > 1
            row = ContactRow(account, None, '', None, show_account)
            self.new_contact_rows[account] = row
            self._ui.listbox.add(row)
            row.get_parent().show_all()
        self.new_contact_row_visible = True

    def _remove_new_jid_row(self):
        if not self.new_contact_row_visible:
            return

        for account in self.new_contact_rows:
            self._ui.listbox.remove(
                self.new_contact_rows[account])
        self.new_contact_row_visible = False

    def _update_new_jid_rows(self, search_text):
        for account in self.new_contact_rows:
            self.new_contact_rows[account].update_jid(search_text)

    def _select_new_match(self, _entry, direction):
        selected_row = self._ui.listbox.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()

        if direction == 'next':
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
            if direction == 'next':
                index += 1
            else:
                index -= 1

    def select_first_row(self):
        first_row = self._ui.listbox.get_row_at_y(0)
        self._ui.listbox.select_row(first_row)

    def _scroll_to_first_row(self):
        self._ui.scrolledwindow.get_vadjustment().set_value(0)

    def _filter_func(self, row, _user_data):
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
                return None
        GLib.timeout_add(50, self.select_first_row)
        return True

    @staticmethod
    def _sort_func(row1, row2, _user_data):
        name1 = row1.get_search_text()
        name2 = row2.get_search_text()
        account1 = row1.account
        account2 = row2.account
        is_groupchat1 = row1.groupchat
        is_groupchat2 = row2.groupchat
        new1 = row1.new
        new2 = row2.new

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        if new1 != new2:
            return 1 if new1 else -1

        if is_groupchat1 != is_groupchat2:
            return 1 if is_groupchat1 else -1

        return locale.strcoll(name1.lower(), name2.lower())

    def _start_search(self):
        self._search_stopped = False
        accounts = app.get_connected_accounts()
        if not accounts:
            return
        con = app.connections[accounts[0]].connection

        text = self._ui.search_entry.get_text().strip()
        self._global_search_listbox.start_search()

        if app.settings.get('muclumbus_api_pref') == 'http':
            self._start_http_search(con, text)
        else:
            self._start_iq_search(con, text)

    @as_task
    def _start_iq_search(self, con, text):
        _task = yield

        if self._parameter_form is None:
            result = yield con.get_module('Muclumbus').request_parameters(
                app.settings.get('muclumbus_api_jid'))

            self._process_search_result(result, parameters=True)

            self._parameter_form = result
            self._parameter_form.type_ = 'submit'

        self._parameter_form.vars['q'].value = text

        result = yield con.get_module('Muclumbus').set_search(
            app.settings.get('muclumbus_api_jid'),
            self._parameter_form)

        self._process_search_result(result)

        while not result.end:
            result = yield con.get_module('Muclumbus').set_search(
                app.settings.get('muclumbus_api_jid'),
                self._parameter_form,
                items_per_page=result.max,
                after=result.last)

            self._process_search_result(result)

        self._global_search_listbox.end_search()

    @as_task
    def _start_http_search(self, con, text):
        _task = yield

        self._keywords = text.split(' ')
        result = yield con.get_module('Muclumbus').set_http_search(
            app.settings.get('muclumbus_api_http_uri'),
            self._keywords)

        self._process_search_result(result)

        while not result.end:
            result = yield con.get_module('Muclumbus').set_http_search(
                app.settings.get('muclumbus_api_http_uri'),
                self._keywords,
                after=result.last)

            self._process_search_result(result)

        self._global_search_listbox.end_search()

    def _process_search_result(self, result, parameters=False):
        if self._search_stopped:
            raise CancelledError()

        if is_error(result):
            self._global_search_listbox.remove_progress()
            self._show_error_page(to_user_string(result))
            raise result

        if parameters:
            return

        for item in result.items:
            self._global_search_listbox.add(ResultRow(item))

    def _destroy(self, *args):
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
        self._destroyed = True
        app.cancel_tasks(self)


class ContactRow(Gtk.ListBoxRow):
    def __init__(self, account, contact, jid, name, show_account,
                 groupchat=False):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('start-chat-row')
        self.account = account
        self.account_label = app.get_account_label(account)
        self.show_account = show_account
        self.jid = jid
        self.contact = contact
        self.name = name
        self.groupchat = groupchat
        self.new = jid == ''

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_size_request(260, -1)

        image = self._get_avatar_image(contact)
        image.set_size_request(AvatarSize.CHAT, AvatarSize.CHAT)
        grid.add(image)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)

        if self.name is None:
            self.name = _('Start New Chat')

        self.name_label = Gtk.Label(label=self.name)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_xalign(0)
        self.name_label.set_width_chars(20)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.get_style_context().add_class('bold16')
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_box.add(self.name_label)
        if show_account:
            account_badge = AccountBadge(account)
            account_badge.set_halign(Gtk.Align.END)
            account_badge.set_valign(Gtk.Align.START)
            account_badge.set_hexpand(True)
            name_box.add(account_badge)
        box.add(name_box)

        self.jid_label = Gtk.Label(label=str(jid))
        self.jid_label.set_tooltip_text(str(jid))
        self.jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.jid_label.set_xalign(0)
        self.jid_label.set_width_chars(22)
        self.jid_label.set_halign(Gtk.Align.START)
        self.jid_label.get_style_context().add_class('dim-label')
        box.add(self.jid_label)

        grid.add(box)

        self.add(grid)
        self.show_all()

    def _get_avatar_image(self, contact):
        if self.new:
            icon_name = 'avatar-default'
            if self.groupchat:
                icon_name = get_icon_name('muc-inactive')
            return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)

        scale = self.get_scale_factor()
        surface = contact.get_avatar(AvatarSize.CHAT, scale)
        return Gtk.Image.new_from_surface(surface)

    def update_jid(self, jid):
        self.jid = jid
        self.jid_label.set_text(jid)

    def update_chat_type(self, groupchat=False):
        self.new = False
        self.groupchat = groupchat

    def get_search_text(self):
        if self.contact is None and not self.groupchat:
            return str(self.jid)
        if self.show_account:
            return '%s %s %s' % (self.name, self.jid, self.account_label)
        return '%s %s' % (self.name, self.jid)


class GlobalSearch(Gtk.ListBox):
    def __init__(self):
        Gtk.ListBox.__init__(self)
        self.set_has_tooltip(True)
        self.set_activate_on_single_click(False)
        self._progress = None
        self._add_placeholder()
        self.show_all()

    def _add_placeholder(self):
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.set_valign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name('system-search-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('dim-label')
        label = Gtk.Label(label=_('Search for group chats globally\n'
                                  '(press Return to start search)'))
        label.get_style_context().add_class('dim-label')
        label.set_justify(Gtk.Justification.CENTER)
        label.set_max_width_chars(35)
        placeholder.add(icon)
        placeholder.add(label)
        placeholder.show_all()
        self.set_placeholder(placeholder)

    def remove_all(self):
        def remove(row):
            self.remove(row)
            row.destroy()
        self.foreach(remove)

    def remove_progress(self):
        self.remove(self._progress)
        self._progress.destroy()

    def start_search(self):
        self._progress = ProgressRow()
        super().add(self._progress)

    def end_search(self):
        self._progress.stop()

    def add(self, row):
        super().add(row)
        if self.get_selected_row() is None:
            row = self.get_row_at_index(1)
            if row is not None:
                self.select_row(row)
                row.grab_focus()
        self._progress.update()

    def _select(self, direction):
        selected_row = self.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()
        if direction == 'next':
            index += 1
        else:
            index -= 1

        new_selected_row = self.get_row_at_index(index)
        if new_selected_row is None:
            return

        self.select_row(new_selected_row)
        new_selected_row.grab_focus()

    def select_next(self):
        self._select('next')

    def select_prev(self):
        self._select('prev')


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, item):
        Gtk.ListBoxRow.__init__(self)
        self.set_activatable(True)
        self.get_style_context().add_class('start-chat-row')
        self.new = False
        self.jid = item.jid
        self.groupchat = True

        name_label = Gtk.Label(label=item.name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(40)
        name_label.get_style_context().add_class('bold16')
        jid_label = Gtk.Label(label=item.jid)
        jid_label.set_halign(Gtk.Align.START)
        jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        jid_label.set_max_width_chars(40)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(name_label)
        box.add(jid_label)

        self.add(box)
        self.show_all()


class ProgressRow(Gtk.ListBoxRow):
    def __init__(self):
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
            'emblem-ok-symbolic', Gtk.IconSize.MENU)
        self._finished_image.get_style_context().add_class('success-color')
        self._finished_image.set_no_show_all(True)

        box = Gtk.Box()
        box.set_spacing(6)
        box.add(self._finished_image)
        box.add(self._spinner)
        box.add(self._count_label)
        self.add(box)
        self.show_all()

    def update(self):
        self._count += 1
        self._count_label.set_text(self._text % self._count)

    def stop(self):
        self._spinner.stop()
        self._spinner.hide()
        self._finished_image.show()
