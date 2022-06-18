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

from __future__ import annotations

from typing import cast
from typing import Optional
from typing import TYPE_CHECKING

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import Direction

from .emoji_data_gtk import get_emoji_data
if TYPE_CHECKING:
    from .message_input import MessageInputTextView

MAX_ENTRIES = 5


class ChatActionProcessor(Gtk.Popover):
    def __init__(self, message_input: MessageInputTextView) -> None:
        Gtk.Popover.__init__(self)
        self._menu = Gio.Menu()
        self.bind_model(self._menu)
        self.set_relative_to(message_input)
        self.set_position(Gtk.PositionType.TOP)
        self.set_modal(False)
        self.set_size_request(250, -1)
        self.connect('closed', self._on_popover_closed)
        self.connect('destroy', self._on_destroy)

        self._message_input = message_input
        self._message_input.connect('key-press-event', self._on_key_press)

        self._buf = message_input.get_buffer()
        self._buf.connect('changed', self._on_changed)

        self._start_mark: Optional[Gtk.TextMark] = None
        self._current_iter: Optional[Gtk.TextIter] = None

        self._active = False

    def _on_destroy(self, _popover: Gtk.Popover) -> None:
        app.check_finalize(self)

    def _on_key_press(self,
                      _textview: Gtk.TextView,
                      event: Gdk.EventKey
                      ) -> bool:
        if not self._active:
            return False

        if event.keyval == Gdk.KEY_Up:
            self._move_selection(Direction.PREV)
            return True

        if event.keyval == Gdk.KEY_Down:
            self._move_selection(Direction.NEXT)
            return True

        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            self.popdown()
            return False

        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_Tab):
            selected_action = self._get_selected_action()
            self._replace_text(selected_action)
            self.popdown()
            return True

        return False

    def _on_popover_closed(self, _popover: Gtk.Popover) -> None:
        self._active = False
        self._message_input.grab_focus()

    def _get_text(self) -> str:
        start, end = self._buf.get_bounds()
        return self._buf.get_text(start, end, True)

    def _replace_text(self, selected_action: str) -> None:
        assert self._start_mark is not None
        start_iter = self._buf.get_iter_at_mark(self._start_mark)
        assert self._current_iter is not None
        self._buf.delete(start_iter, self._current_iter)
        self._buf.insert(start_iter, selected_action)

    def _get_commands(self) -> list[str]:
        commands: list[str] = []
        control = app.window.get_control(
            self._message_input.account, self._message_input.contact.jid)
        assert control is not None
        for command in control.list_commands():
            for name in command.names:
                commands.append(name)
        return commands

    def _on_changed(self, _textview: MessageInputTextView) -> None:
        insert = self._buf.get_insert()
        self._current_iter = self._buf.get_iter_at_mark(insert)
        current_offset = self._current_iter.get_offset()

        if self._start_mark is None:
            start_iter = self._buf.get_iter_at_offset(current_offset - 1)
        else:
            start_iter = self._buf.get_iter_at_mark(self._start_mark)

        command_found = self._check_for_command(start_iter)
        emoji_found = self._check_for_emoji(start_iter)

        if not command_found and not emoji_found:
            if self._start_mark is not None:
                self._buf.delete_mark(self._start_mark)
                self._start_mark = None
            self.popdown()

    def _check_for_command(self, start_iter: Gtk.TextIter) -> bool:
        assert self._current_iter is not None
        search = self._current_iter.backward_search(
            '/',
            Gtk.TextSearchFlags.VISIBLE_ONLY,
            start_iter)

        if search is not None:
            start, _end = search
            if start.get_offset() > 0:
                # '/' not at the beginning
                return False

            action_text = self._buf.get_text(start, self._current_iter, False)
            if self._start_mark is None:
                self._start_mark = Gtk.TextMark.new('chat-action-start', True)
                self._buf.add_mark(self._start_mark, start)
            self._update_commands_menu(action_text, start)
            return True

        return False

    def _update_commands_menu(self,
                              action_text: str,
                              start: Gtk.TextIter
                              ) -> None:
        self._menu.remove_all()
        command_list = self._get_commands()
        num_entries = 0
        for command in command_list:
            if not command.startswith(action_text[1:]):
                continue
            if num_entries >= MAX_ENTRIES:
                continue

            action_data = GLib.Variant('s', f'/{command}')
            menu_item = Gio.MenuItem()
            menu_item.set_label(f'/{command}')
            menu_item.set_attribute_value('action-data', action_data)
            self._menu.append_item(menu_item)
            num_entries += 1

        if self._menu.get_n_items() > 0:
            self._show_menu(start)
        else:
            self.popdown()

    def _check_for_emoji(self, start_iter: Gtk.TextIter) -> bool:
        assert self._current_iter is not None
        search = self._current_iter.backward_search(
            ':',
            Gtk.TextSearchFlags.CASE_INSENSITIVE,
            start_iter)

        if search is not None:
            start, _end = search
            colon_offset = start.get_offset()
            before_colon = self._buf.get_iter_at_offset(colon_offset - 1)
            if before_colon.get_char() != ' ':
                # We want to show the menu only if text begins with a colon,
                # or if a colon follows on a space. This avoids showing the
                # menu within normal sentences containing colons.
                text = self._get_text()
                if not text.startswith(':'):
                    return False

            action_text = self._buf.get_text(start, self._current_iter, False)
            if self._start_mark is None:
                self._start_mark = Gtk.TextMark.new('chat-action-start', True)
                self._buf.add_mark(self._start_mark, start)
            self._update_emoji_menu(action_text, start)
            return True

        return False

    def _update_emoji_menu(self,
                           action_text: str,
                           start: Gtk.TextIter
                           ) -> None:
        self._menu.remove_all()
        emoji_data = get_emoji_data()
        menu_entry_count = 0
        for shortcode, codepoint in emoji_data.items():
            if not shortcode.startswith(action_text[1:]):
                continue
            if menu_entry_count >= MAX_ENTRIES:
                continue
            action_data = GLib.Variant('s', codepoint)
            menu_item = Gio.MenuItem()
            menu_item.set_label(f'{codepoint} {shortcode}')
            menu_item.set_attribute_value('action-data', action_data)
            self._menu.append_item(menu_item)
            menu_entry_count += 1

        if self._menu.get_n_items() > 0:
            self._show_menu(start)
        else:
            self.popdown()

    def _show_menu(self, start: Gtk.TextIter) -> None:
        self._active = True
        rectangle = self._message_input.get_iter_location(start)
        self.set_pointing_to(rectangle)
        self.popup()
        menu_items = self._get_menu_items()
        menu_items[0].set_state_flags(
            Gtk.StateFlags.FOCUSED | Gtk.StateFlags.PRELIGHT, False)
        for item in menu_items:
            item.connect(
                'clicked', self._on_item_clicked, menu_items.index(item))

    def _on_item_clicked(self, _button: Gtk.MenuButton, index: int) -> None:
        variant = self._menu.get_item_attribute_value(
            index, 'action-data')
        self._replace_text(variant.get_string())
        self.popdown()

    def _get_menu_items(self) -> list[Gtk.ModelButton]:
        stack = cast(Gtk.Stack, self.get_children()[0])
        menu_section_box = cast(Gtk.Box, stack.get_children()[0])
        box = cast(Gtk.Box, menu_section_box.get_children()[0])
        items = cast(list[Gtk.ModelButton], box.get_children())
        return items

    def _get_selected_action(self) -> str:
        items = self._get_menu_items()
        for item in items:
            if self._item_has_focus(item):
                variant = self._menu.get_item_attribute_value(
                    items.index(item), 'action-data')
                return variant.get_string()
        return ''

    def _move_selection(self, direction: Direction) -> None:
        # The popover cannot have real focus, since we want to continue
        # writing in the message input. Instead, we emulate focus/prelight
        # state for menu items when pressing Up/Down arrows. Reference:
        # https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gtk/
        # gtkemojicompletion.c
        items = self._get_menu_items()
        num_items = len(items)
        if num_items == 1:
            return

        new_item = items[0]  # default item
        for item in items:
            if self._item_has_focus(item):
                item.unset_state_flags(
                    Gtk.StateFlags.FOCUSED | Gtk.StateFlags.PRELIGHT)
            else:
                continue

            if direction is Direction.NEXT:
                if items.index(item) == num_items - 1:
                    # Select first (default)
                    break
                new_item = items[items.index(item) + 1]
                break

            if items.index(item) == 0:
                new_item = items[num_items - 1]
                break
            new_item = items[items.index(item) - 1]
            break

        new_item.set_state_flags(
            Gtk.StateFlags.FOCUSED | Gtk.StateFlags.PRELIGHT, False)

    @staticmethod
    def _item_has_focus(item: Gtk.ModelButton) -> bool:
        flags = item.get_state_flags()
        return 'GTK_STATE_FLAG_FOCUSED' in str(flags)
