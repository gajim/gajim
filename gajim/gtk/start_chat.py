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

from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import JID
from nbxmpp.util import is_error_result
from nbxmpp.const import AnonymityMode

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.const import MUC_DISCO_ERRORS

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_builder
from gajim.gtk.util import ensure_not_destroyed


SERVICE_JID = 'rodrigo.de.mucobedo@dreckshal.de'


class Search(IntEnum):
    CONTACT = 0
    MUC = 1


class StartChatDialog(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('StartChatDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Start New Conversation'))
        self.set_default_size(-1, 400)
        self.ready_to_destroy = False
        self._parameter_form = None
        self._destroyed = False
        self._search_stopped = False

        self._ui = get_builder('start_chat_dialog.ui')
        self.add(self._ui.stack)

        self.new_contact_row_visible = False
        self.new_contact_rows = {}
        self.new_groupchat_rows = {}
        self.accounts = app.connections.keys()
        self.add_contacts()
        self.add_groupchats()

        self._ui.search_entry.connect('search-changed',
                                      self._on_search_changed)
        self._ui.search_entry.connect('next-match',
                                      self._select_new_match, 'next')
        self._ui.search_entry.connect('previous-match',
                                      self._select_new_match, 'prev')
        self._ui.search_entry.connect(
            'stop-search', lambda *args: self._ui.search_entry.set_text(''))

        self._ui.listbox.set_filter_func(self._filter_func, None)
        self._ui.listbox.set_sort_func(self._sort_func, None)
        self._ui.listbox.connect('row-activated', self._on_row_activated)

        self._muc_search_listbox = MUCSearch()
        self._current_listbox = self._ui.listbox

        self._muc_info_box = GroupChatInfoScrolled()
        self._ui.info_box.add(self._muc_info_box)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._destroy)

        self.select_first_row()
        self._ui.connect_signals(self)
        self.show_all()

    def set_search_text(self, text):
        self._ui.search_entry.set_text(text)

    def add_contacts(self):
        show_account = len(self.accounts) > 1
        for account in self.accounts:
            self.new_contact_rows[account] = None
            for jid in app.contacts.get_jid_list(account):
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
                if contact.is_groupchat:
                    continue
                row = ContactRow(account, contact, jid,
                                 contact.get_shown_name(), show_account)
                self._ui.listbox.add(row)

    def add_groupchats(self):
        show_account = len(self.accounts) > 1
        for account in self.accounts:
            self.new_groupchat_rows[account] = None
            con = app.connections[account]
            bookmarks = con.get_module('Bookmarks').bookmarks
            groupchats = {}
            for bookmark in bookmarks:
                groupchats[str(bookmark.jid)] = bookmark.name

            for jid in app.contacts.get_gc_list(account):
                if jid in groupchats:
                    continue
                groupchats[jid] = None

            for jid in groupchats:
                name = groupchats[jid]
                if not name:
                    name = app.get_nick_from_jid(jid)
                row = ContactRow(account, None, jid, name,
                                 show_account, True)
                self._ui.listbox.add(row)

    def _on_row_activated(self, _listbox, row):
        row = row.get_child()
        self._start_new_chat(row)

    def _on_key_press(self, _widget, event):
        is_search = self._ui.stack.get_visible_child_name() == 'search'
        if event.keyval in (Gdk.KEY_Down, Gdk.KEY_Tab):
            if is_search:
                self._ui.search_entry.emit('next-match')
                return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE

        if (event.state == Gdk.ModifierType.SHIFT_MASK and
                event.keyval == Gdk.KEY_ISO_Left_Tab):
            if is_search:
                self._ui.search_entry.emit('previous-match')
                return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE

        if event.keyval == Gdk.KEY_Up:
            if is_search:
                self._ui.search_entry.emit('previous-match')
                return Gdk.EVENT_STOP
            return Gdk.EVENT_PROPAGATE

        if event.keyval == Gdk.KEY_Escape:
            if self._ui.stack.get_visible_child_name() == 'progress':
                self.destroy()
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() in ('error', 'info'):
                self._ui.stack.set_visible_child_name('search')
                return Gdk.EVENT_STOP

            self._search_stopped = True
            self._muc_search_listbox.remove_all()
            if self._ui.search_entry.get_text() != '':
                self._ui.search_entry.emit('stop-search')
            else:
                self.destroy()
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Return:
            if self._ui.stack.get_visible_child_name() == 'progress':
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'error':
                self._ui.stack.set_visible_child_name('search')
                return Gdk.EVENT_STOP

            if self._ui.stack.get_visible_child_name() == 'info':
                self._on_join_clicked()
                return Gdk.EVENT_STOP

            if self._current_listbox_is(Search.MUC):
                self._muc_search_listbox.remove_all()
                self._start_search()
                return Gdk.EVENT_STOP

            row = self._ui.listbox.get_selected_row()
            if row is not None:
                row.emit('activate')
            return Gdk.EVENT_STOP

        if is_search:
            self._ui.search_entry.grab_focus_without_selecting()
        return Gdk.EVENT_PROPAGATE

    def _start_new_chat(self, row):
        if row.new:
            try:
                JID(row.jid)
            except InvalidJid as error:
                self._show_error_page(str(error))
                return

        if row.groupchat:
            if not app.account_is_connected(row.account):
                self._show_error_page(_('You can not join a group chat '
                                        'unless you are connected.'))
                return
            self._disco_muc(row.account, row.jid)
        else:
            app.interface.new_chat_from_jid(row.account, row.jid)

        self.ready_to_destroy = True

    def _disco_muc(self, account, jid):
        self._ui.stack.set_visible_child_name('progress')
        con = app.connections[account]
        con.get_module('Discovery').disco_info(
            jid, callback=self._disco_info_received, user_data=account)

    @ensure_not_destroyed
    def _disco_info_received(self, result, account):
        if is_error_result(result):
            self._set_error(result)

        elif result.is_muc:
            self._muc_info_box.set_account(account)
            self._muc_info_box.set_from_disco_info(result)
            self._ui.stack.set_visible_child_name('info')

        else:
            self._set_error_from_code('not-muc-service')

    def _set_error(self, error):
        text = MUC_DISCO_ERRORS.get(error.type, str(error))
        self._show_error_page(text)

    def _set_error_from_code(self, error_code):
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _show_error_page(self, text):
        self._ui.error_label.set_text(text)
        self._ui.stack.set_visible_child_name('error')

    def _on_join_clicked(self, _button=None):
        row = self._ui.listbox.get_selected_row().get_child()
        app.interface.join_gc_minimal(row.account, row.jid)
        self.ready_to_destroy = True

    def _on_back_clicked(self, _button):
        self._ui.stack.set_visible_child_name('search')

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
        return box == Search.MUC

    def _on_search_changed(self, entry):
        search_text = entry.get_text()
        if search_text.startswith('g:'):
            self._set_listbox(self._muc_search_listbox)
            return

        self._set_listbox(self._ui.listbox)
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
            show_account = len(self.accounts) > 1
            row = ContactRow(account, None, '', None, show_account)
            self.new_contact_rows[account] = row
            group_row = ContactRow(account, None, '', None, show_account, True)
            self.new_groupchat_rows[account] = group_row
            self._ui.listbox.add(row)
            self._ui.listbox.add(group_row)
            row.get_parent().show_all()
        self.new_contact_row_visible = True

    def _remove_new_jid_row(self):
        if not self.new_contact_row_visible:
            return
        for account in self.new_contact_rows:
            self._ui.listbox.remove(
                self.new_contact_rows[account].get_parent())
            self._ui.listbox.remove(
                self.new_groupchat_rows[account].get_parent())
        self.new_contact_row_visible = False

    def _update_new_jid_rows(self, search_text):
        for account in self.new_contact_rows:
            self.new_contact_rows[account].update_jid(search_text)
            self.new_groupchat_rows[account].update_jid(search_text)

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

    def _filter_func(self, row, _user_data):
        search_text = self._ui.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_child().get_search_text().lower()
        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self.select_first_row)
                return None
        GLib.timeout_add(50, self.select_first_row)
        return True

    @staticmethod
    def _sort_func(row1, row2, _user_data):
        name1 = row1.get_child().get_search_text()
        name2 = row2.get_child().get_search_text()
        account1 = row1.get_child().account
        account2 = row2.get_child().account
        is_groupchat1 = row1.get_child().groupchat
        is_groupchat2 = row2.get_child().groupchat
        new1 = row1.get_child().new
        new2 = row2.get_child().new

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        if new1 != new2:
            return 1 if new1 else -1

        if is_groupchat1 != is_groupchat2:
            return 1 if is_groupchat1 else -1

        return locale.strcoll(name1.lower(), name2.lower())

    @staticmethod
    def _get_connection():
        accounts = app.get_connected_accounts()
        if not accounts:
            raise NotConnected
        return app.connections[accounts.pop()].connection

    def _start_search(self):
        self._search_stopped = False
        try:
            con = self._get_connection()
        except NotConnected:
            return

        text = self._ui.search_entry.get_text()
        text = text[2:].strip()
        self._muc_search_listbox.start_search()

        if self._parameter_form is None:
            con.get_module('Muclumbus').request_parameters(
                SERVICE_JID,
                callback=self._parameters_received,
                user_data=(con, text))
        else:
            self._parameter_form.vars['q'].value = text

            con.get_module('Muclumbus').set_search(
                SERVICE_JID,
                self._parameter_form,
                callback=self._on_search_result,
                user_data=con)

    @ensure_not_destroyed
    def _parameters_received(self, result, user_data):
        if is_error_result(result):
            self._on_error(result)
            return

        con, text = user_data
        self._parameter_form = result
        self._parameter_form.type_ = 'submit'
        self._parameter_form.vars['q'].value = text

        con.get_module('Muclumbus').set_search(
            SERVICE_JID,
            self._parameter_form,
            callback=self._on_search_result,
            user_data=con)

    @ensure_not_destroyed
    def _on_search_result(self, result, con):
        if self._search_stopped:
            return

        if is_error_result(result):
            self._on_error(result)
            return

        for item in result.items:
            self._muc_search_listbox.add(ResultRow(item))

        if result.end:
            self._muc_search_listbox.end_search()
            return

        con.get_module('Muclumbus').set_search(
            SERVICE_JID,
            self._parameter_form,
            items_per_page=result.max,
            after=result.last,
            callback=self._on_search_result,
            user_data=con)

    def _on_error(self, result):
        self._muc_search_listbox.show_error(result)

    def _destroy(self, *args):
        self._destroyed = True


class ContactRow(Gtk.Grid):
    def __init__(self, account, contact, jid, name, show_account,
                 groupchat=False):
        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)
        self.set_size_request(260, -1)
        self.account = account
        self.account_label = app.get_account_label(account)
        self.show_account = show_account
        self.jid = jid
        self.contact = contact
        self.name = name
        self.groupchat = groupchat
        self.new = jid == ''

        if self.groupchat:
            muc_icon = get_icon_name(
                'muc-inactive' if self.new else 'muc-active')
            image = Gtk.Image.new_from_icon_name(muc_icon, Gtk.IconSize.DND)
        else:
            scale = self.get_scale_factor()
            avatar = app.contacts.get_avatar(
                account, jid, AvatarSize.CHAT, scale)
            if avatar is None:
                image = Gtk.Image.new_from_icon_name(
                    'avatar-default', Gtk.IconSize.DND)
            else:
                image = Gtk.Image.new_from_surface(avatar)

        image.set_size_request(AvatarSize.CHAT, AvatarSize.CHAT)
        self.add(image)

        middle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        middle_box.set_hexpand(True)

        if self.name is None:
            if self.groupchat:
                self.name = _('Join Group Chat')
            else:
                self.name = _('Add Contact')

        self.name_label = Gtk.Label(label=self.name)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_xalign(0)
        self.name_label.set_width_chars(25)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.get_style_context().add_class('bold16')

        status = contact.show if contact else 'offline'
        css_class = helpers.get_css_show_color(status)
        if css_class is not None:
            self.name_label.get_style_context().add_class(css_class)
        middle_box.add(self.name_label)

        self.jid_label = Gtk.Label(label=jid)
        self.jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.jid_label.set_xalign(0)
        self.jid_label.set_width_chars(25)
        self.jid_label.set_halign(Gtk.Align.START)
        self.jid_label.get_style_context().add_class('dim-label')
        middle_box.add(self.jid_label)

        self.add(middle_box)

        if show_account:
            account_label = Gtk.Label(label=self.account_label)
            account_label.set_halign(Gtk.Align.START)
            account_label.set_valign(Gtk.Align.START)

            right_box = Gtk.Box()
            right_box.set_vexpand(True)
            right_box.add(account_label)
            self.add(right_box)

        self.show_all()

    def update_jid(self, jid):
        self.jid = jid
        self.jid_label.set_text(jid)

    def get_search_text(self):
        if self.contact is None and not self.groupchat:
            return self.jid
        if self.show_account:
            return '%s %s %s' % (self.name, self.jid, self.account_label)
        return '%s %s' % (self.name, self.jid)


class MUCSearch(Gtk.ListBox):
    def __init__(self):
        Gtk.ListBox.__init__(self)
        self.set_has_tooltip(True)
        self.set_activate_on_single_click(False)
        self._progress = None

        self._ui = get_builder('start_chat_dialog.ui', ['tooltip'])
        self.connect('query-tooltip', self._query_tooltip)
        self.connect('row-activated', self._on_row_activated)
        self.show_all()

    def remove_all(self):
        def remove(row):
            self.remove(row)
            row.destroy()
        self.foreach(remove)

    def show_error(self, error):
        self.insert(ErrorRow(error), 0)
        self.remove(self._progress)
        self._progress.destroy()

    def start_search(self):
        self._progress = ProgressRow()
        super().add(self._progress)

    def end_search(self):
        self._progress.stop()

    def add(self, row):
        super().add(row)
        self._progress.update()

    def _query_tooltip(self, _widget, _x_pos, y_pos, _keyboard_mode, tooltip):
        row = self.get_row_at_y(y_pos)
        if row is None or not isinstance(row, ResultRow):
            self._clear_tooltip()
            return False

        if row.item.anonymity_mode == AnonymityMode.SEMI:
            self._ui.anonymous_icon.show()
            self._ui.anonymous_label.show()

        self._ui.tooltip_user.set_text(row.item.nusers)
        self._ui.tooltip_jid.set_text(row.item.jid)
        if row.item.description:
            self._ui.tooltip_description.set_text(row.item.description)
            self._ui.tooltip_description.show()
            self._ui.tooltip_description_label.show()

        if row.item.name:
            self._ui.tooltip_name.set_text(row.item.name)
            self._ui.tooltip_name.show()
            self._ui.tooltip_name_label.show()

        tooltip.set_custom(self._ui.tooltip)
        return True

    def _clear_tooltip(self):
        self._ui.anonymous_icon.hide()
        self._ui.anonymous_label.hide()
        self._ui.tooltip_description.hide()
        self._ui.tooltip_description_label.hide()
        self._ui.tooltip_name.hide()
        self._ui.tooltip_name_label.hide()

    @staticmethod
    def _on_row_activated(_listbox, row):
        app.interface.join_gc_minimal(None, row.item.jid)


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, item):
        Gtk.ListBoxRow.__init__(self)
        self.set_activatable(True)
        self.get_style_context().add_class('start-chat-row')
        self.item = item
        self._ui = get_builder('start_chat_dialog.ui', ['search_result_grid'])
        self._ui.jid_label.set_text(item.jid)
        self._ui.name_label.set_text(item.name)
        self._ui.user_label.set_text(item.nusers)
        self.add(self._ui.search_result_grid)
        self.show_all()


class ErrorRow(Gtk.ListBoxRow):
    def __init__(self, error):
        Gtk.ListBoxRow.__init__(self)
        self.set_selectable(False)
        self.set_activatable(False)
        self.get_style_context().add_class('start-chat-row')
        self._error = Gtk.Label(label=str(error))
        self._error.set_line_wrap(True)
        self._error.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._error.set_xalign(0)
        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-error', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('error-color')
        self._error_image.set_valign(Gtk.Align.CENTER)
        box = Gtk.Box()
        box.set_spacing(6)
        box.add(self._error_image)
        box.add(self._error)
        self.add(box)
        self.show_all()


class ProgressRow(Gtk.ListBoxRow):
    def __init__(self):
        Gtk.ListBoxRow.__init__(self)
        self.set_selectable(False)
        self.set_activatable(False)
        self.get_style_context().add_class('start-chat-row')
        self._text = _('%s Group chats found')
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


class NotConnected(Exception):
    pass
