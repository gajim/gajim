# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GtkSource

from gajim.common import app
from gajim.common import types
from gajim.common.const import Direction
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.emoji_data_gtk import get_emoji_data
from gajim.gtk.groupchat_nick_completion import GroupChatNickCompletion
from gajim.gtk.menus import escape_mnemonic

EMOJI_NUM_GENDERS = len(['f', 'm', 'n'])
MENUS_MAX_ENTRIES = 2 * EMOJI_NUM_GENDERS

log = logging.getLogger('gajim.gtk.chat_action_processor')


class ChatActionProcessor(Gtk.Popover):
    def __init__(self, message_input: GtkSource.View) -> None:
        Gtk.Popover.__init__(self)
        self._menu = Gio.Menu()
        self.bind_model(self._menu)
        self.set_relative_to(message_input)
        self.set_position(Gtk.PositionType.TOP)
        self.set_modal(False)
        self.set_size_request(250, -1)
        self.connect('closed', self._on_popover_closed)
        self.connect('destroy', self._on_destroy)

        self._account: str | None = None
        self._contact: types.ChatContactT | None = None

        self._message_input = message_input
        self._message_input.connect('key-press-event', self._on_key_press)
        self._message_input.connect('focus-out-event', self._on_focus_out)
        self._message_input.connect('buffer-changed', self._on_changed)


        self._nick_completion = GroupChatNickCompletion()

        self._start_mark: Gtk.TextMark | None = None
        self._current_iter: Gtk.TextIter | None = None

        self._active = False

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self._account = contact.account
        self._contact = contact
        if isinstance(contact, GroupchatContact):
            self._nick_completion.switch_contact(contact)

    def _on_destroy(self, _popover: Gtk.Popover) -> None:
        app.check_finalize(self)

    def _on_key_press(self,
                      source_view: GtkSource.View,
                      event: Gdk.EventKey
                      ) -> bool:
        if isinstance(self._contact, GroupchatContact):
            res = self._nick_completion.process_key_press(source_view, event)
            if res:
                return True

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

    def _on_focus_out(self, *args: Any) -> bool:
        win = self.get_window()
        default_display = Gdk.Display.get_default()
        if default_display is not None:
            pointer = default_display.get_default_seat().get_pointer()
            if win is not None and pointer is not None:
                _win, x_pos, y_pos, _mod = win.get_device_position(pointer)
                rect = self.get_allocation()
                if (x_pos not in range(rect.width) or
                        y_pos not in range(rect.height)):
                    # Only popdown if click is outside of Popover's Rectangle
                    self.popdown()

        return False

    def _on_popover_closed(self, _popover: Gtk.Popover) -> None:
        self._active = False
        self._message_input.grab_focus()

    def _get_text(self) -> str:
        text_buffer = self._message_input.get_buffer()
        start, end = text_buffer.get_bounds()
        return text_buffer.get_text(start, end, True)

    def _replace_text(self, selected_action: str) -> None:
        if not selected_action:
            # selected_action may be an empty string under certain conditions
            return

        assert self._start_mark is not None
        text_buffer = self._message_input.get_buffer()
        start_iter = text_buffer.get_iter_at_mark(self._start_mark)
        assert self._current_iter is not None
        text_buffer.delete(start_iter, self._current_iter)
        text_buffer.insert(start_iter, selected_action)

    def _get_commands(self) -> list[tuple[str, str]]:
        assert self._contact is not None
        return app.commands.get_commands(self._contact.type_string)

    def _on_changed(self, message_input: GtkSource.View) -> None:
        text_buffer = self._message_input.get_buffer()
        insert = text_buffer.get_insert()
        self._current_iter = text_buffer.get_iter_at_mark(insert)
        current_offset = self._current_iter.get_offset()

        if self._start_mark is None:
            start_iter = text_buffer.get_iter_at_offset(current_offset - 1)
        else:
            start_iter = text_buffer.get_iter_at_mark(self._start_mark)

        command_found = self._check_for_command(start_iter)
        emoji_found = self._check_for_emoji(start_iter)

        if not command_found and not emoji_found:
            if self._start_mark is not None:
                text_buffer.delete_mark(self._start_mark)
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

            text_buffer = self._message_input.get_buffer()
            action_text = text_buffer.get_text(start, self._current_iter, False)
            if self._start_mark is None:
                self._start_mark = Gtk.TextMark.new('chat-action-start', True)
                text_buffer.add_mark(self._start_mark, start)
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
        for command, usage in command_list:
            if not command.startswith(action_text[1:]):
                continue
            if num_entries >= MENUS_MAX_ENTRIES:
                continue

            action_data = GLib.Variant('s', f'/{command}')
            menu_item = Gio.MenuItem()
            menu_item.set_label(f'/{command} {usage}')
            menu_item.set_attribute_value('action-data', action_data)
            self._menu.append_item(menu_item)
            num_entries += 1

        if self._menu.get_n_items() > 0:
            self._show_menu(start)
        else:
            self.popdown()

    def _check_for_emoji(self, start_iter: Gtk.TextIter) -> bool:
        if not app.settings.get('enable_emoji_shortcodes'):
            return False

        assert self._current_iter is not None
        search = self._current_iter.backward_search(
            ':',
            Gtk.TextSearchFlags.CASE_INSENSITIVE,
            start_iter)

        if search is not None:
            start, _end = search
            colon_offset = start.get_offset()
            text_buffer = self._message_input.get_buffer()
            before_colon = text_buffer.get_iter_at_offset(colon_offset - 1)
            if before_colon.get_char() not in (' ', '\n'):
                # We want to show the menu only if text begins with a colon,
                # or if a colon follows on a space. This avoids showing the
                # menu within normal sentences containing colons.
                text = self._get_text()
                if not text.startswith(':'):
                    return False

            action_text = text_buffer.get_text(
                start, self._current_iter, False)[1:]
            if self._start_mark is not None:
                text_buffer.delete_mark(self._start_mark)

            self._start_mark = Gtk.TextMark.new('chat-action-start', True)
            text_buffer.add_mark(self._start_mark, start)
            if self._active or len(action_text) > 1:
                # Don't activate until a sufficient # of chars has been typed,
                # which is chosen to be > 1 to not interfere with ASCII smilies
                # consisting of a colon and 1 single other char.
                self._update_emoji_menu(action_text.casefold(), start)
            return True

        return False

    def _update_emoji_menu(self,
                           action_text: str,
                           start: Gtk.TextIter
                           ) -> None:
        self._menu.remove_all()
        emoji_data = get_emoji_data()

        sn_matches: dict[str, str] = {}
        kw_matches: dict[str, str] = {}

        for keyword, entries in emoji_data.items():
            if not keyword.startswith(action_text):
                continue
            for short_name, emoji in entries.items():
                label = f'{emoji} {short_name}'
                if keyword == short_name:
                    # Replace a possible keyword match with the shortname match:
                    sn_matches[emoji] = label
                    if kw_matches.get(emoji) is not None:
                        del kw_matches[emoji]
                else:
                    # Only add a keyword match if no shortname match:
                    if sn_matches.get(emoji) is None:
                        kw_matches[emoji] = f'{label}  [{keyword}]'

        log.debug('Found %d "%s…" emoji by short name, %d more by keyword',
                  len(sn_matches), action_text, len(kw_matches))

        # Put all shortname matches before keyword matches:
        for emoji, label in list(sn_matches.items()) + list(kw_matches.items()):
            action_data = GLib.Variant('s', emoji)
            menu_item = Gio.MenuItem()
            menu_item.set_label(escape_mnemonic(label))
            menu_item.set_attribute_value('action-data', action_data)
            self._menu.append_item(menu_item)
            if self._menu.get_n_items() >= MENUS_MAX_ENTRIES:
                break

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
        assert variant is not None
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
                assert variant is not None
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
