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

import logging
import time

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.i18n import _
from gajim.common.styling import process

from .conversation.message_widget import MessageWidget
from .util import get_builder

log = logging.getLogger('gajim.gui.search_view')


class SearchView(Gtk.Box):

    __gsignals__ = {
        'hide-search': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            ()),
    }

    def __init__(self):
        Gtk.Box.__init__(self)
        self.set_size_request(300, -1)

        self._account = None
        self._jid = None

        self._ui = get_builder('search_view.ui')
        self._ui.results_listbox.set_header_func(self._header_func)
        self.add(self._ui.search_box)

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.emit('hide-search')

    @staticmethod
    def _header_func(row, before):
        if before is None:
            if row.type == 'counter':
                row.set_header(None)
            else:
                row.set_header(RowHeader(row.account, row.jid, row.time))
        else:
            date1 = time.strftime('%x', time.localtime(row.time))
            date2 = time.strftime('%x', time.localtime(before.time))
            if before.jid != row.jid:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            elif date1 != date2:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            else:
                row.set_header(None)

    def _on_hide_clicked(self, _button):
        self.emit('hide-search')

    def clear(self):
        self._ui.search_entry.set_text('')
        self._clear_results()

    def _clear_results(self):
        for row in self._ui.results_listbox.get_children():
            self._ui.results_listbox.remove(row)

    def _on_search(self, entry):
        self._clear_results()
        text = entry.get_text()
        if text == '':
            return

        accounts = self._get_accounts()
        everywhere = self._ui.search_checkbutton.get_active()
        context = self._account is not None and self._jid is not None

        if not context or everywhere:
            # Global search
            results = app.storage.archive.search_all_logs(text)
            results_count = len(results)
            if results_count:
                self._ui.results_listbox.add(CounterRow(results_count))
            for msg in results:
                result_row = ResultRow(
                    msg,
                    accounts.get(msg.account_id),
                    app.storage.archive.get_jid_from_id(msg.jid_id).jid)
                self._ui.results_listbox.add(result_row)
        else:
            results = app.storage.archive.search_log(
                self._account, self._jid, text)
            results_count = len(results)
            if results_count:
                self._ui.results_listbox.add(CounterRow(results_count))
            for msg in results:
                result_row = ResultRow(msg, self._account, self._jid)
                self._ui.results_listbox.add(result_row)

    @staticmethod
    def _get_accounts():
        accounts = {}
        for account in app.settings.get_accounts():
            account_id = app.storage.archive.get_account_id(account)
            accounts[account_id] = account
        return accounts

    @staticmethod
    def _on_row_activated(_listbox, row):
        if row.type == 'counter':
            return

        control = app.window.get_active_control()
        if control is not None:
            if control.contact.jid == row.jid:
                control.scroll_to_message(row.log_line_id, row.timestamp)
                return

        # Wrong chat or no control opened
        # TODO: type 'pm' is KindConstant.CHAT_MSG_RECV, too
        app.window.add_chat(row.account, row.jid, row.type, select=True)
        control = app.window.get_active_control()
        control.scroll_to_message(row.log_line_id, row.timestamp)

    def set_focus(self):
        self._ui.search_entry.grab_focus()

    def set_context(self, account, jid):
        self._account = account
        self._jid = jid
        self._ui.search_checkbutton.set_active(False)


class RowHeader(Gtk.Box):
    def __init__(self, account, jid, timestamp):
        Gtk.Box.__init__(self)
        self.set_hexpand(True)

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.header_box)

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        self._ui.header_name_label.set_text(contact.name or '')

        local_time = time.localtime(timestamp)
        date = time.strftime('%x', local_time)
        self._ui.header_date_label.set_text(date)

        self.show_all()


class CounterRow(Gtk.ListBoxRow):
    def __init__(self, count):
        Gtk.ListBoxRow.__init__(self)
        self.type = 'counter'
        self.jid = ''
        self.time = 0
        self.get_style_context().add_class('search-view-counter')

        if count == 1:
            counter_text = _('1 result')
        else:
            counter_text = _('%s results') % count
        label = Gtk.Label(label=counter_text)
        self.add(label)
        self.show_all()


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, msg, account, jid):
        Gtk.ListBoxRow.__init__(self)
        self.account = account
        self.jid = jid
        self.time = msg.time
        self._client = app.get_client(account)

        self.contact = self._client.get_module('Contacts').get_contact(jid)

        self.log_line_id = msg.log_line_id
        self.timestamp = msg.time
        self.kind = msg.kind

        self.type = 'contact'
        if msg.kind == KindConstant.GC_MSG:
            self.type = 'groupchat'

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.result_row_grid)

        kind = 'status'
        contact_name = msg.contact_name
        if msg.kind in (
                KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
            kind = 'incoming'
            contact_name = self.contact.name
        elif msg.kind == KindConstant.GC_MSG:
            kind = 'incoming'
        elif msg.kind in (
                KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
            kind = 'outgoing'
            contact_name = app.nicks[account]
        self._ui.row_name_label.set_text(contact_name)

        avatar = self._get_avatar(kind, contact_name)
        self._ui.row_avatar.set_from_surface(avatar)

        local_time = time.localtime(msg.time)
        date = time.strftime('%H:%M', local_time)
        self._ui.row_time_label.set_label(date)

        message_widget = MessageWidget(account)
        self._ui.result_row_grid.attach(message_widget, 1, 1, 2, 1)
        result = process(msg.message)
        message_widget.add_content(result)

        self.show_all()

    def _get_avatar(self, kind, name):
        scale = self.get_scale_factor()
        if self.contact.is_groupchat:
            contact = self.contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self.contact

        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
