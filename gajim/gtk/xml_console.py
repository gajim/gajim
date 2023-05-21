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

from typing import Any
from typing import Optional
from typing import Union

import logging
import time

import nbxmpp
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource

from gajim.common import app
from gajim.common import ged
from gajim.common.const import Direction
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import StanzaReceived
from gajim.common.events import StanzaSent
from gajim.common.i18n import _
from gajim.common.logging_helpers import get_stream_handler

from gajim.gtk.builder import get_builder
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.settings import SettingsDialog
from gajim.gtk.util import at_the_end
from gajim.gtk.util import EventHelper
from gajim.gtk.util import MaxWidthComboBoxText
from gajim.gtk.util import scroll_to_end


class XMLConsoleWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(800, 600)
        self.set_resizable(True)
        self.set_show_menubar(False)
        self.set_name('XMLConsoleWindow')

        self._selected_account = 'AllAccounts'
        self._selected_send_account: Optional[str] = None
        self._filter_dialog: Optional[SettingsDialog] = None
        self._last_stanza: Optional[str] = None
        self._last_search: str = ''

        self._presence = True
        self._message = True
        self._iq = True
        self._stream = True
        self._incoming = True
        self._outgoing = True

        self._ui = get_builder('xml_console.ui')
        self.set_titlebar(self._ui.headerbar)
        self._set_titlebar()
        self.add(self._ui.stack)

        self._ui.paned.set_position(
            self._ui.paned.get_property('max-position'))

        self._combo = MaxWidthComboBoxText()
        self._combo.set_max_size(200)
        self._combo.set_hexpand(False)
        self._combo.set_halign(Gtk.Align.END)
        self._combo.set_no_show_all(True)
        self._combo.set_visible(False)
        self._combo.connect('changed', self._on_value_change)
        available_accounts = self._get_accounts()
        for account, label in available_accounts:
            self._combo.append(account, label)
        if available_accounts:
            self._combo.set_active(0)
        self._ui.actionbox.pack_end(self._combo, False, False, 0)
        self._ui.actionbox.reorder_child(self._combo, 1)

        self._create_tags()

        source_manager = GtkSource.LanguageManager.get_default()
        lang = source_manager.get_language('xml')
        self._ui.protocol_view.get_buffer().set_language(lang)
        self._ui.input_entry.get_buffer().set_language(lang)

        style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        style_scheme = style_scheme_manager.get_scheme('solarized-dark')
        if style_scheme is not None:
            self._ui.protocol_view.get_buffer().set_style_scheme(style_scheme)
            self._ui.input_entry.get_buffer().set_style_scheme(style_scheme)
            self._ui.log_view.get_buffer().set_style_scheme(style_scheme)

        for record in app.logging_records:
            self._add_log_record(record)

        log_handler = get_stream_handler()
        log_handler.set_callback(self._add_log_record)

        self._ui.stack.connect('notify::visible-child-name',
                               self._on_stack_child_changed)

        self.show_all()

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.register_events([
            ('stanza-received', ged.GUI1, self._on_stanza_received),
            ('stanza-sent', ged.GUI1, self._on_stanza_sent),
            ('account-enabled', ged.GUI1, self._on_account_changed),
            ('account-disabled', ged.GUI1, self._on_account_changed)
        ])

    def _on_destroy(self, *args: Any) -> None:
        get_stream_handler().set_callback(None)
        self._ui.popover.destroy()
        app.check_finalize(self)

    def _on_value_change(self, combo: Gtk.ComboBox) -> None:
        self._selected_send_account = combo.get_active_id()

    def _set_titlebar(self) -> None:
        if self._selected_account == 'AllAccounts':
            title = _('All Accounts')
        elif self._selected_account == 'AccountWizard':
            title = _('Account Wizard')
        else:
            title = app.get_jid_from_account(self._selected_account)
        self._ui.headerbar.set_subtitle(title)

    def _on_account_changed(self,
                            event: Union[AccountEnabled, AccountDisabled]
                            ) -> None:
        buf = self._ui.protocol_view.get_buffer()

        if isinstance(event, AccountEnabled):
            buf.create_tag(event.account)
        else:
            start, end = buf.get_bounds()
            buf.remove_tag_by_name(event.account, start, end)

    def _on_stack_child_changed(self,
                                _widget: Gtk.Stack,
                                _pspec: GObject.ParamSpec
                                ) -> None:

        name = self._ui.stack.get_visible_child_name()
        self._ui.search_toggle.set_sensitive(name == 'protocol')

    def _create_tags(self) -> None:
        tags = [
            'incoming',
            'outgoing',
            'presence',
            'message',
            'stream',
            'iq'
        ]

        for account in app.settings.get_active_accounts():
            tags.append(account)

        tags.append('AccountWizard')

        for tag_name in tags:
            self._ui.protocol_view.get_buffer().create_tag(tag_name)

    def _add_log_record(self, record: logging.LogRecord) -> None:
        buf = self._ui.log_view.get_buffer()
        msg = (f'{record.asctime} {record.levelname} {record.name} '
               f'{record.getMessage()}\n')
        end_iter = buf.get_end_iter()
        buf.insert(end_iter, msg)

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            if self._ui.search_revealer.get_child_revealed():
                self._ui.search_revealer.set_reveal_child(False)
                return
            self.destroy()
        if (event.state & Gdk.ModifierType.CONTROL_MASK and
                event.keyval == Gdk.KEY_Return or
                event.keyval == Gdk.KEY_KP_Enter):
            self._on_send()
        if (event.state & Gdk.ModifierType.CONTROL_MASK and
                event.keyval == Gdk.KEY_Up):
            self._on_paste_last()
        if (event.state & Gdk.ModifierType.CONTROL_MASK and
                event.keyval == Gdk.KEY_f):
            self._ui.search_toggle.set_active(
                not self._ui.search_revealer.get_child_revealed())
        if event.keyval == Gdk.KEY_F3:
            self._find(Direction.NEXT)

    def _on_row_activated(self,
                          _listbox: Gtk.ListBox,
                          row: Gtk.ListBoxRow
                          ) -> None:
        child = row.get_child()
        assert isinstance(child, Gtk.Label)
        text = child.get_text()

        input_text = None
        if text == 'Presence':
            input_text = (
                '<presence xmlns="jabber:client">\n'
                '<show></show>\n'
                '<status></status>\n'
                '<priority></priority>\n'
                '</presence>')
        elif text == 'Message':
            input_text = (
                '<message to="" type="" xmlns="jabber:client">\n'
                '<body></body>\n'
                '</message>')
        elif text == 'Iq':
            input_text = (
                '<iq to="" type="" xmlns="jabber:client">\n'
                '<query xmlns=""></query>\n'
                '</iq>')
        elif text == 'Disco Info':
            input_text = (
                '<iq to="" type="get" xmlns="jabber:client">\n'
                '<query xmlns="http://jabber.org/protocol/disco#info">'
                '</query>\n</iq>')

        if input_text is not None:
            buffer_ = self._ui.input_entry.get_buffer()
            buffer_.set_text(input_text)
            self._ui.input_entry.grab_focus()

    def _on_send(self, *args: Any) -> None:
        if not self._selected_send_account:
            return
        if not app.account_is_available(self._selected_send_account):
            # If offline or connecting
            ErrorDialog(
                _('Connection not available'),
                _('Please make sure you are connected with "%s".') %
                self._selected_send_account)
            return
        buffer_ = self._ui.input_entry.get_buffer()
        begin_iter, end_iter = buffer_.get_bounds()
        stanza = buffer_.get_text(begin_iter, end_iter, True)
        if stanza:
            try:
                node = nbxmpp.Node(node=stanza)
            except Exception as error:
                ErrorDialog(_('Invalid Node'), str(error))
                return

            if node.getName() in ('message', 'presence', 'iq'):
                # Parse stanza again if its a message, presence or iq and
                # set jabber:client as toplevel namespace
                # Use type Protocol so nbxmpp counts the stanza for
                # stream management
                node = nbxmpp.Protocol(node=stanza,
                                       attrs={'xmlns': 'jabber:client'})
            client = app.get_client(self._selected_send_account)
            assert isinstance(node, nbxmpp.Protocol)
            client.connection.send_stanza(node)
            self._last_stanza = stanza
            buffer_.set_text('')

    def _on_paste_last(self, *args: Any) -> None:
        buffer_ = self._ui.input_entry.get_buffer()
        if self._last_stanza is not None:
            buffer_.set_text(self._last_stanza)
        self._ui.input_entry.grab_focus()

    def _on_input(self, button: Gtk.ToggleButton) -> None:
        child2 = self._ui.paned.get_child2()
        assert child2 is not None
        if button.get_active():
            child2.show()
            self._ui.send.show()
            self._ui.paste.show()
            self._ui.account_label.show()
            self._combo.show()
            self._ui.menubutton.show()
            self._ui.input_entry.grab_focus()
        else:
            child2.hide()
            self._ui.send.hide()
            self._ui.paste.hide()
            self._ui.account_label.hide()
            self._combo.hide()
            self._ui.menubutton.hide()

    def _on_search_toggled(self, button: Gtk.ToggleButton) -> None:
        self._ui.search_revealer.set_reveal_child(button.get_active())
        self._ui.search_entry.grab_focus()

    def _on_search_activate(self, _entry: Gtk.SearchEntry) -> None:
        self._find(Direction.NEXT)

    def _on_search_clicked(self, button: Gtk.ToolButton) -> None:
        if button is self._ui.search_forward:
            direction = Direction.NEXT
        else:
            direction = Direction.PREV
        self._find(direction)

    def _find(self, direction: Direction) -> None:
        search_str = self._ui.search_entry.get_text()
        textbuffer = self._ui.protocol_view.get_buffer()
        cursor_mark = textbuffer.get_insert()
        current_pos = textbuffer.get_iter_at_mark(cursor_mark)

        if current_pos.get_offset() == textbuffer.get_char_count():
            current_pos = textbuffer.get_start_iter()

        last_pos_mark = textbuffer.get_mark('last_pos')
        if last_pos_mark is not None:
            current_pos = textbuffer.get_iter_at_mark(last_pos_mark)

        if search_str != self._last_search:
            current_pos = textbuffer.get_start_iter()

        if direction == Direction.NEXT:
            match = current_pos.forward_search(
                search_str,
                Gtk.TextSearchFlags.VISIBLE_ONLY |
                Gtk.TextSearchFlags.CASE_INSENSITIVE,
                None)
        else:
            current_pos.backward_cursor_position()
            match = current_pos.backward_search(
                search_str,
                Gtk.TextSearchFlags.VISIBLE_ONLY |
                Gtk.TextSearchFlags.CASE_INSENSITIVE,
                None)

        if match is not None:
            match_start, match_end = match
            textbuffer.select_range(match_start, match_end)
            mark = textbuffer.create_mark('last_pos', match_end, True)
            self._ui.protocol_view.scroll_to_mark(mark, 0, True, 0.5, 0.5)
        self._last_search = search_str

    @staticmethod
    def _get_accounts() -> list[tuple[Optional[str], str]]:
        accounts = app.get_accounts_sorted()
        combo_accounts: list[tuple[Optional[str], str]] = []
        for account in accounts:
            label = app.get_account_label(account)
            combo_accounts.append((account, label))
        combo_accounts.append(('AccountWizard', 'Account Wizard'))
        return combo_accounts

    def _on_filter_options(self, _button: Gtk.Button) -> None:
        if self._filter_dialog is not None:
            self._filter_dialog.present()
            return

        combo_accounts = self._get_accounts()
        combo_accounts.insert(0, ('AllAccounts', _('All Accounts')))

        settings = [
            Setting(SettingKind.COMBO,
                    _('Account'),
                    SettingType.VALUE,
                    self._selected_account,
                    callback=self._set_account,
                    props={'combo_items': combo_accounts}),

            Setting(SettingKind.SWITCH,
                    'Presence',
                    SettingType.VALUE,
                    self._presence,
                    callback=self._on_setting,
                    data='presence'),

            Setting(SettingKind.SWITCH,
                    'Message',
                    SettingType.VALUE,
                    self._message,
                    callback=self._on_setting,
                    data='message'),

            Setting(SettingKind.SWITCH,
                    'IQ', SettingType.VALUE,
                    self._iq,
                    callback=self._on_setting,
                    data='iq'),

            Setting(SettingKind.SWITCH,
                    'Stream Management',
                    SettingType.VALUE,
                    self._stream,
                    callback=self._on_setting,
                    data='stream'),

            Setting(SettingKind.SWITCH,
                    'In',
                    SettingType.VALUE,
                    self._incoming,
                    callback=self._on_setting,
                    data='incoming'),

            Setting(SettingKind.SWITCH,
                    'Out',
                    SettingType.VALUE,
                    self._outgoing,
                    callback=self._on_setting,
                    data='outgoing'),
        ]

        self._filter_dialog = SettingsDialog(
            self,
            _('Filter'),
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            settings,
            self._selected_account or 'AllAccounts')
        self._filter_dialog.connect('destroy', self._on_filter_destroyed)

    def _on_filter_destroyed(self, _widget: Gtk.Widget) -> None:
        self._filter_dialog = None

    def _on_clear(self, _button: Gtk.Button) -> None:
        self._ui.protocol_view.get_buffer().set_text('')

    def _set_account(self, value: str, _data: Any) -> None:
        self._selected_account = value
        self._set_titlebar()

        active_accounts = app.settings.get_active_accounts()
        active_accounts.append('AccountWizard')

        table = self._ui.protocol_view.get_buffer().get_tag_table()

        if value == 'AllAccounts':
            for account in active_accounts:
                tag = table.lookup(account)
                if tag is not None:
                    tag.set_property('invisible', False)
            return

        for account in active_accounts:
            tag = table.lookup(account)
            if tag is not None:
                tag.set_property('invisible', account != value)

    def _on_setting(self, value: bool, data: str) -> None:
        setattr(self, data, value)
        value = not value
        table = self._ui.protocol_view.get_buffer().get_tag_table()
        tag = table.lookup(data)
        if tag is None:
            return

        if data in ('incoming', 'outgoing'):
            if value:
                tag.set_priority(table.get_size() - 1)
            else:
                tag.set_priority(0)

        tag.set_property('invisible', value)

    def _on_stanza_received(self, event: StanzaReceived):
        self._print_stanza(event, 'incoming')

    def _on_stanza_sent(self, event: StanzaSent):
        self._print_stanza(event, 'outgoing')

    def _print_stanza(self,
                      event: Union[StanzaReceived, StanzaSent],
                      kind: str
                      ) -> None:
        if event.account == 'AccountWizard':
            account_label = 'Account Wizard'
        else:
            account_label = app.get_account_label(event.account)

        stanza = event.stanza
        if not isinstance(stanza, str):
            # pylint: disable=unnecessary-dunder-call
            stanza = stanza.__str__(fancy=True)

        if not stanza:
            return

        is_at_the_end = at_the_end(self._ui.scrolled)

        buffer_ = self._ui.protocol_view.get_buffer()
        end_iter = buffer_.get_end_iter()

        type_ = kind
        if stanza.startswith('<presence'):
            type_ = 'presence'
        elif stanza.startswith('<message'):
            type_ = 'message'
        elif stanza.startswith('<iq'):
            type_ = 'iq'
        elif stanza.startswith('<r') or stanza.startswith('<a'):
            type_ = 'stream'

        stanza = '<!-- {kind} {time} ({account}) -->\n{stanza}\n\n'.format(
            kind=kind.capitalize(),
            time=time.strftime('%c'),
            account=account_label,
            stanza=stanza)
        buffer_.insert_with_tags_by_name(
            end_iter, stanza, type_, kind, event.account)

        if is_at_the_end:
            GLib.idle_add(scroll_to_end, self._ui.scrolled)
