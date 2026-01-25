# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

import emoji
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common.styling import BaseHyperlink
from gajim.common.styling import PlainBlock
from gajim.common.styling import process_uris
from gajim.common.util.text import process_non_spacing_marks
from gajim.common.util.uri import parse_uri

from gajim.gtk.const import MAX_MESSAGE_LENGTH
from gajim.gtk.menus import get_conv_action_context_menu
from gajim.gtk.menus import get_uri_context_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import make_pango_attributes
from gajim.gtk.util.misc import open_uri

log = logging.getLogger("gajim.gtk.conversaion.plain_widget")

URI_TAGS = ["uri", "address", "xmppadr", "mailadr"]
STYLE_TAGS = ["strong", "emphasis", "strike", "pre"]


class PlainWidget(Gtk.Box):
    def __init__(self, account: str, selectable: bool) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        self._text_widget = MessageLabel(self._account, selectable)
        self.append(self._text_widget)

    def set_selectable(self, selectable: bool) -> None:
        self._text_widget.set_selectable(selectable)

    def add_content(self, block: PlainBlock) -> None:
        self._text_widget.print_text_with_styling(block)

    def add_action_phrase(self, text: str, nickname: str) -> None:
        self._text_widget.add_action_phrase(text, nickname)


class MessageLabel(Gtk.Label, SignalManager):
    def __init__(self, account: str, selectable: bool) -> None:
        Gtk.Label.__init__(
            self,
            hexpand=True,
            selectable=selectable,
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        SignalManager.__init__(self)

        self._account = account

        self.add_css_class("gajim-conversation-text")

        self._connect(self, "activate-link", self._on_activate_link)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_secondary_clicked)
        self.add_controller(gesture_secondary_click)

        focus_controller = Gtk.EventControllerFocus()
        self._connect(focus_controller, "enter", self._on_focus_enter)
        self._connect(focus_controller, "leave", self._on_focus_leave)
        self.add_controller(focus_controller)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Label.do_unroot(self)

    def _on_secondary_clicked(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        current_uri = self.get_current_uri()
        selected, start, end = self.get_selection_bounds()

        uri_menu = None
        action_menu = None
        if current_uri:
            uri_menu = get_uri_context_menu(self._account, parse_uri(current_uri))
        elif selected:
            selected_text = self.get_text()[start:end]
            action_menu = get_conv_action_context_menu(self._account, selected_text)

        if uri_menu is None and action_menu is None:
            return

        extra_menu = Gio.Menu()
        if uri_menu is not None:
            extra_menu.append_section(None, uri_menu)
        if action_menu is not None:
            extra_menu.append_section(None, action_menu)

        self.set_extra_menu(extra_menu)
        return

    def _build_link_markup(self, text: str, uris: list[BaseHyperlink]) -> str:
        markup_text = ""
        after = GLib.markup_escape_text(text.strip())
        for uri in uris:
            uri_escaped = GLib.markup_escape_text(uri.text)
            before, _, after = after.partition(uri_escaped)
            markup_text += before
            markup_text += uri.get_markup_string()
        markup_text += after
        return markup_text

    def print_text_with_styling(self, block: PlainBlock) -> None:
        text = self._build_link_markup(block.text, block.uris)
        self.set_markup(process_non_spacing_marks(text))
        if len(self.get_text()) > MAX_MESSAGE_LENGTH:
            # Limit message styling processing
            return

        self.set_attributes(make_pango_attributes(block))

        stripped = text.strip()
        # https://github.com/carpedm20/emoji/issues/300
        # purely_emoji() return True for the empty string
        if stripped and emoji.purely_emoji(stripped):
            emoji_count = emoji.emoji_count(stripped)
            if emoji_count == 1:
                classname = "gajim-single-emoji-msg"
            else:
                classname = "gajim-emoji-msg"
            self.add_css_class(classname)

    def add_action_phrase(self, text: str, nickname: str) -> None:
        text = text.replace("/me", f"* {nickname}", 1)
        uris = process_uris(text)
        text = self._build_link_markup(text, uris)
        self.set_markup(process_non_spacing_marks(f"<i>{text}</i>"))

    def _on_activate_link(self, _label: Gtk.Label, uri: str) -> int:
        puri = parse_uri(uri)
        open_uri(puri)
        return Gdk.EVENT_STOP

    def _on_focus_enter(self, _focus_controller: Gtk.EventControllerFocus) -> None:
        self.remove_css_class("transparent-selection")

    def _on_focus_leave(self, _focus_controller: Gtk.EventControllerFocus) -> None:
        self.add_css_class("transparent-selection")
