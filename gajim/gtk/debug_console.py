# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import time

import nbxmpp
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import ged
from gajim.common.const import Direction
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import StanzaReceived
from gajim.common.events import StanzaSent
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.logging_helpers import get_log_console_handler

from gajim.gtk.builder import get_builder
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.settings import SettingsDialog
from gajim.gtk.util import at_the_end
from gajim.gtk.util import get_source_view_style_scheme
from gajim.gtk.util import MaxWidthComboBoxText
from gajim.gtk.util import scroll_to_end
from gajim.gtk.widgets import GajimAppWindow

STANZA_PRESETS = {
    "Presence": (
        '<presence xmlns="jabber:client">\n'
        "<show></show>\n"
        "<status></status>\n"
        "<priority></priority>\n"
        "</presence>"
    ),
    "Message": (
        '<message to="" type="" xmlns="jabber:client">\n<body></body>\n</message>'
    ),
    "Iq": (
        '<iq to="" type="" xmlns="jabber:client">\n'
        '<query xmlns=""></query>\n'
        "</iq>"
    ),
    "XEP-0030: Disco Info Query": (
        '<iq to="" type="get" xmlns="jabber:client">\n'
        f'<query xmlns="{Namespace.DISCO_INFO}">'
        "</query>\n</iq>"
    ),
    "XEP-0092: Software Version Query": (
        '<iq to="" type="get" xmlns="jabber:client">\n'
        f'<query xmlns="{Namespace.VERSION}">'
        "</query>\n</iq>"
    ),
}


class DebugConsoleWindow(GajimAppWindow, EventHelper):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="DebugConsoleWindow",
            default_width=800,
            default_height=600,
            add_window_padding=False,
        )

        EventHelper.__init__(self)

        self._selected_account = "AllAccounts"
        self._selected_send_account: str | None = None
        self._filter_dialog: SettingsDialog | None = None
        self._sent_stanzas = SentSzanzas()
        self._last_selected_ts = 0

        self._presence = True
        self._message = True
        self._iq = True
        self._stream = True
        self._incoming = True
        self._outgoing = True

        self._ui = get_builder("debug_console.ui")
        self.window.set_titlebar(self._ui.headerbar)
        self._set_title()

        self.set_child(self._ui.stack)

        self._ui.paned.set_position(self._ui.paned.get_property("max-position"))

        self._combo = MaxWidthComboBoxText()
        self._combo.set_max_width_chars(15)
        self._combo.set_hexpand(False)
        self._combo.set_halign(Gtk.Align.END)
        self._combo.set_visible(False)
        self._combo.set_visible(False)
        self._connect(self._combo, "changed", self._on_value_change)
        available_accounts = self._get_accounts()
        for account, label in available_accounts:
            self._combo.append(account, label)
        if available_accounts:
            self._combo.set_active(0)
        self._ui.actionbox.append(self._combo)
        self._ui.actionbox.reorder_child_after(self._combo, self._ui.account_label)

        self._create_tags()
        self._add_stanza_presets()

        self._connect(
            self._ui.filter_options_button, "clicked", self._on_filter_options
        )
        self._connect(self._ui.clear_button, "clicked", self._on_clear)
        self._connect(self._ui.paste, "clicked", self._on_paste_previous)
        self._connect(
            self._ui.stanza_presets_listbox, "row-activated", self._on_row_activated
        )
        self._connect(self._ui.search_entry, "activate", self._on_search_activate)
        self._connect(self._ui.search_forward, "clicked", self._on_search_clicked)
        self._connect(self._ui.search_backward, "clicked", self._on_search_clicked)
        self._connect(
            self._ui.jump_to_end_button, "clicked", self._on_jump_to_end_clicked
        )
        self._connect(self._ui.send, "clicked", self._on_send)
        self._connect(self._ui.edit_toggle, "toggled", self._on_input)
        self._connect(self._ui.search_toggle, "toggled", self._on_search_toggled)

        source_manager = GtkSource.LanguageManager.get_default()
        lang = source_manager.get_language("xml")
        self._ui.protocol_view.get_buffer().set_language(lang)
        self._ui.input_entry.get_buffer().set_language(lang)

        style_scheme = get_source_view_style_scheme()
        if style_scheme is not None:
            self._ui.protocol_view.get_buffer().set_style_scheme(style_scheme)
            self._ui.input_entry.get_buffer().set_style_scheme(style_scheme)
            self._ui.log_view.get_buffer().set_style_scheme(style_scheme)

        self._search_settings = GtkSource.SearchSettings(wrap_around=True)
        self._search_context = GtkSource.SearchContext.new(
            self._ui.protocol_view.get_buffer(), self._search_settings
        )

        for record in app.logging_records:
            self._add_log_record(record)

        log_handler = get_log_console_handler()
        log_handler.set_callback(self._add_log_record)

        self._connect(
            self._ui.stack, "notify::visible-child-name", self._on_stack_child_changed
        )

        vadjustment = self._ui.scrolled.get_vadjustment()
        self._connect(vadjustment, "notify::upper", self._on_adj_upper_changed)
        self._connect(vadjustment, "notify::value", self._on_adj_value_changed)

        controller = self.get_default_controller()
        self._connect(controller, "key-pressed", self._on_key_pressed)

        self.register_events(
            [
                ("stanza-received", ged.GUI1, self._on_stanza_received),
                ("stanza-sent", ged.GUI1, self._on_stanza_sent),
                ("account-enabled", ged.GUI1, self._on_account_changed),
                ("account-disabled", ged.GUI1, self._on_account_changed),
            ]
        )

    def _cleanup(self) -> None:
        self.unregister_events()
        get_log_console_handler().set_callback(None)

    def _on_adj_upper_changed(
        self, adj: Gtk.Adjustment, _pspec: GObject.ParamSpec
    ) -> None:
        if adj.get_upper() == adj.get_page_size():
            self._ui.jump_to_end_button.set_visible(False)

    def _on_adj_value_changed(
        self, adj: Gtk.Adjustment, _pspec: GObject.ParamSpec
    ) -> None:
        bottom = adj.get_upper() - adj.get_page_size()
        autoscroll = bottom - adj.get_value() < 1
        self._ui.jump_to_end_button.set_visible(not autoscroll)

    def _on_jump_to_end_clicked(self, _button: Gtk.Button) -> None:
        vadjustment = self._ui.scrolled.get_vadjustment()
        vadjustment.set_value(vadjustment.get_upper())

    def _on_value_change(self, combo: Gtk.ComboBox) -> None:
        self._selected_send_account = combo.get_active_id()

    def _set_title(self) -> None:
        if self._selected_account == "AllAccounts":
            title = _("All Accounts")
        elif self._selected_account == "AccountWizard":
            title = _("Account Wizard")
        else:
            title = app.get_jid_from_account(self._selected_account)
        self.window.set_title(title)

    def _on_account_changed(self, event: AccountEnabled | AccountDisabled) -> None:
        buf = self._ui.protocol_view.get_buffer()

        if isinstance(event, AccountEnabled):
            buf.create_tag(event.account)
        else:
            start, end = buf.get_bounds()
            buf.remove_tag_by_name(event.account, start, end)

    def _on_stack_child_changed(
        self, _widget: Gtk.Stack, _pspec: GObject.ParamSpec
    ) -> None:

        name = self._ui.stack.get_visible_child_name()
        self._ui.search_toggle.set_sensitive(name == "protocol")

    def _create_tags(self) -> None:
        tags = ["incoming", "outgoing", "presence", "message", "stream", "iq"]

        accounts = app.settings.get_active_accounts()
        tags.extend(accounts)

        tags.append("AccountWizard")

        for tag_name in tags:
            self._ui.protocol_view.get_buffer().create_tag(tag_name)

    def _add_stanza_presets(self) -> None:
        for stanza_type in STANZA_PRESETS:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=stanza_type, halign=Gtk.Align.START)
            row.set_child(label)
            self._ui.stanza_presets_listbox.append(row)

        self._ui.stanza_presets_listbox.show()

    def _add_log_record(self, message: str) -> None:
        buf = self._ui.log_view.get_buffer()
        end_iter = buf.get_end_iter()
        buf.insert(end_iter, message)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self._ui.search_toggle.get_active():
                self._ui.search_toggle.set_active(False)
                return Gdk.EVENT_STOP

            self.close()

        if (
            state & Gdk.ModifierType.CONTROL_MASK
            and keyval == Gdk.KEY_Return
            or keyval == Gdk.KEY_KP_Enter
        ):
            self._on_send()
            return Gdk.EVENT_STOP

        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_Up:
            self._on_paste_previous()
            return Gdk.EVENT_STOP

        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_Down:
            self._on_paste_next()
            return Gdk.EVENT_STOP

        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_f:
            self._ui.search_toggle.set_active(True)
            self._ui.search_entry.grab_focus()
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_F3:
            self._find(Direction.NEXT)
            return Gdk.EVENT_STOP

        if state & Gdk.ModifierType.SHIFT_MASK and keyval == Gdk.KEY_F3:
            self._find(Direction.PREV)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        child = row.get_child()
        assert isinstance(child, Gtk.Label)
        text = child.get_text()

        stanza_string = STANZA_PRESETS.get(text)

        if stanza_string is not None:
            buffer_ = self._ui.input_entry.get_buffer()
            buffer_.set_text(stanza_string)
            self._ui.input_entry.grab_focus()

    def _on_send(self, *args: Any) -> None:
        if not self._selected_send_account:
            return
        if not app.account_is_available(self._selected_send_account):
            # If offline or connecting
            ErrorDialog(
                _("Connection not available"),
                _('Please make sure you are connected with "%s".')
                % self._selected_send_account,
            )
            return
        buffer_ = self._ui.input_entry.get_buffer()
        begin_iter, end_iter = buffer_.get_bounds()
        stanza = buffer_.get_text(begin_iter, end_iter, True)
        if stanza:
            try:
                node = nbxmpp.Node(node=stanza)
            except Exception as error:
                ErrorDialog(_("Invalid Node"), str(error))
                return

            if node.getName() in ("message", "presence", "iq"):
                # Parse stanza again if its a message, presence or iq and
                # set jabber:client as toplevel namespace
                # Use type Protocol so nbxmpp counts the stanza for
                # stream management
                try:
                    node = nbxmpp.Protocol(
                        node=stanza, attrs={"xmlns": "jabber:client"}
                    )
                except Exception as error:
                    ErrorDialog(_("Invalid Stanza"), str(error))
                    return

            client = app.get_client(self._selected_send_account)
            assert isinstance(node, nbxmpp.Protocol)
            client.connection.send_stanza(node)
            self._sent_stanzas.add(stanza)
            buffer_.set_text("")

    def _on_paste_previous(self, *args: Any) -> None:
        buffer_ = self._ui.input_entry.get_buffer()
        buffer_.set_text(self._sent_stanzas.get_previous())
        self._ui.input_entry.grab_focus()

    def _on_paste_next(self, *args: Any) -> None:
        buffer_ = self._ui.input_entry.get_buffer()
        buffer_.set_text(self._sent_stanzas.get_next())
        self._ui.input_entry.grab_focus()

    def _on_input(self, button: Gtk.ToggleButton) -> None:
        child2 = self._ui.paned.get_end_child()
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

    def _on_search_clicked(self, button: Any) -> None:
        if button is self._ui.search_forward:
            direction = Direction.NEXT
        else:
            direction = Direction.PREV
        self._find(direction)

    def _find(self, direction: Direction) -> None:
        self._search_settings.set_search_text(self._ui.search_entry.get_text())
        textbuffer = self._ui.protocol_view.get_buffer()

        last_pos_mark = textbuffer.get_mark("last_pos")
        if last_pos_mark is not None:
            current_pos = textbuffer.get_iter_at_mark(last_pos_mark)
        else:
            current_pos = textbuffer.get_start_iter()

        if direction == Direction.NEXT:
            self._search_context.forward_async(
                current_pos, None, self._on_search_finished, direction
            )
        else:
            self._search_context.backward_async(
                current_pos, None, self._on_search_finished, direction
            )

    def _on_search_finished(
        self,
        _context: GtkSource.SearchContext,
        result: Gio.AsyncResult,
        direction: Direction,
    ) -> None:

        if direction == Direction.NEXT:
            match = self._search_context.forward_finish(result)
        else:
            match = self._search_context.backward_finish(result)

        match_found, match_start, match_end, _has_wrapped_around = match

        if not match_found:
            self._ui.search_results_label.set_text(_("No results"))
            return

        occurrences_count = self._search_context.get_occurrences_count()
        if occurrences_count == -1:
            # Text scan may not be complete yet
            occurrences_count = "?"

        occurrence_positon = self._search_context.get_occurrence_position(
            match_start, match_end
        )
        if occurrence_positon == -1:
            occurrence_positon = 1
        self._ui.search_results_label.set_text(
            _("%s of %s") % (occurrence_positon, occurrences_count)
        )

        textbuffer = self._ui.protocol_view.get_buffer()

        if direction == Direction.NEXT:
            mark = textbuffer.create_mark("last_pos", match_end, True)
        else:
            mark = textbuffer.create_mark("last_pos", match_start, True)
        self._ui.protocol_view.scroll_to_mark(mark, 0, True, 0.5, 0.5)

    @staticmethod
    def _get_accounts() -> list[tuple[str | None, str]]:
        accounts = app.get_accounts_sorted()
        combo_accounts: list[tuple[str | None, str]] = []
        for account in accounts:
            label = app.get_account_label(account)
            combo_accounts.append((account, label))
        combo_accounts.append(("AccountWizard", _("Account Wizard")))
        return combo_accounts

    def _on_filter_options(self, _button: Gtk.Button) -> None:
        if self._filter_dialog is not None:
            self._filter_dialog.present()
            return

        combo_accounts = self._get_accounts()
        combo_accounts.insert(0, ("AllAccounts", _("All Accounts")))

        settings = [
            Setting(
                SettingKind.COMBO,
                _("Account"),
                SettingType.VALUE,
                self._selected_account,
                callback=self._set_account,
                props={"combo_items": combo_accounts},
            ),
            Setting(
                SettingKind.SWITCH,
                "Presence",
                SettingType.VALUE,
                self._presence,
                callback=self._on_setting,
                data="presence",
            ),
            Setting(
                SettingKind.SWITCH,
                "Message",
                SettingType.VALUE,
                self._message,
                callback=self._on_setting,
                data="message",
            ),
            Setting(
                SettingKind.SWITCH,
                "IQ",
                SettingType.VALUE,
                self._iq,
                callback=self._on_setting,
                data="iq",
            ),
            Setting(
                SettingKind.SWITCH,
                "Stream Management",
                SettingType.VALUE,
                self._stream,
                callback=self._on_setting,
                data="stream",
            ),
            Setting(
                SettingKind.SWITCH,
                "In",
                SettingType.VALUE,
                self._incoming,
                callback=self._on_setting,
                data="incoming",
            ),
            Setting(
                SettingKind.SWITCH,
                "Out",
                SettingType.VALUE,
                self._outgoing,
                callback=self._on_setting,
                data="outgoing",
            ),
        ]

        self._filter_dialog = SettingsDialog(
            self.window,
            _("Filter"),
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            settings,
            self._selected_account or "AllAccounts",
        )
        self._connect(
            self._filter_dialog.window, "close-request", self._on_filter_destroyed
        )

    def _on_filter_destroyed(self, _widget: Gtk.Widget) -> None:
        self._filter_dialog = None

    def _on_clear(self, _button: Gtk.Button) -> None:
        self._ui.protocol_view.get_buffer().set_text("")

    def _apply_filters(self) -> None:
        table = self._ui.protocol_view.get_buffer().get_tag_table()

        active_accounts = app.settings.get_active_accounts()
        active_accounts.append("AccountWizard")
        for account in active_accounts:
            tag = table.lookup(account)
            if tag is None:
                continue

            if self._selected_account == "AllAccounts":
                visible = True
            else:
                visible = account == self._selected_account

            if visible:
                tag.set_priority(0)
            else:
                tag.set_priority(table.get_size() - 1)

            tag.set_property("invisible", not visible)

        for data in ["presence", "message", "iq", "stream", "incoming", "outgoing"]:
            visible = getattr(self, f"_{data}")

            tag = table.lookup(data)
            if tag is None:
                continue

            if data in ("incoming", "outgoing"):
                if visible:
                    tag.set_priority(0)
                else:
                    tag.set_priority(table.get_size() - 1)

            tag.set_property("invisible", not visible)

    def _set_account(self, value: str, _data: Any) -> None:
        self._selected_account = value
        self._set_title()
        self._apply_filters()

    def _on_setting(self, value: bool, data: str) -> None:
        setattr(self, f"_{data}", value)
        self._apply_filters()

    def _on_stanza_received(self, event: StanzaReceived):
        self._print_stanza(event, "incoming")

    def _on_stanza_sent(self, event: StanzaSent):
        self._print_stanza(event, "outgoing")

    def _print_stanza(self, event: StanzaReceived | StanzaSent, kind: str) -> None:
        if event.account == "AccountWizard":
            account_label = _("Account Wizard")
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
        if stanza.startswith("<presence"):
            type_ = "presence"
        elif stanza.startswith("<message"):
            type_ = "message"
        elif stanza.startswith("<iq"):
            type_ = "iq"
        elif stanza.startswith(("<r", "<a")):
            type_ = "stream"

        text = "<!-- {kind} {time} ({account}) -->\n{stanza}\n\n".format(
            kind=kind.capitalize(),
            time=time.strftime("%c"),
            account=account_label,
            stanza=stanza,
        )
        buffer_.insert_with_tags_by_name(end_iter, text, type_, kind, event.account)

        if is_at_the_end:
            GLib.idle_add(scroll_to_end, self._ui.scrolled)


class SentSzanzas:
    def __init__(self) -> None:
        self._sent_stanzas: dict[float, str] = {}
        self._last_selected_ts = 0

    def add(self, stanza: str) -> None:
        self._sent_stanzas[time.time()] = stanza
        self._last_selected_ts = 0

    def get_previous(self) -> str:
        return self._get(Direction.PREV)

    def get_next(self) -> str:
        return self._get(Direction.NEXT)

    def _get(self, direction: Direction) -> str:
        if not self._sent_stanzas:
            return ""

        if direction == Direction.PREV:
            for timestamp, stanza in reversed(self._sent_stanzas.items()):
                if timestamp >= self._last_selected_ts:
                    continue
                self._last_selected_ts = timestamp
                return stanza
        else:
            for timestamp, stanza in self._sent_stanzas.items():
                if timestamp <= self._last_selected_ts:
                    continue
                self._last_selected_ts = timestamp
                return stanza

        self._last_selected_ts = list(self._sent_stanzas.keys())[-1]
        return self._sent_stanzas[self._last_selected_ts]
