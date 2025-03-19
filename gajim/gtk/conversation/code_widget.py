# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import logging

from gi.repository import Gtk
from gi.repository import GtkSource

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.styling import PreBlock

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.styling import get_source_view_style_scheme

log = logging.getLogger("gajim.gtk.conversation.code_widget")


class CodeWidget(Gtk.Box, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        SignalManager.__init__(self)

        self.add_css_class("code-widget")

        self._account = account

        header = Gtk.Box()
        header.set_spacing(6)
        header.add_css_class("code-widget-header")
        self._lang_label = Gtk.Label()
        header.append(self._lang_label)

        copy_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text(_("Copy code snippet"))
        self._connect(copy_button, "clicked", self._on_copy)
        header.append(copy_button)
        self.append(header)

        self._textview = CodeTextview()
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self._scrolled.set_hexpand(True)
        self._scrolled.set_vexpand(True)
        self._scrolled.set_propagate_natural_width(True)
        self._scrolled.set_propagate_natural_height(True)
        self._scrolled.set_max_content_height(400)
        self._scrolled.set_child(self._textview)

        self.append(self._scrolled)

    def do_unroot(self) -> None:
        self._disconnect_all()

        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_copy(self, _button: Gtk.Button) -> None:
        self.get_clipboard().set(self._textview.get_code())

    def add_content(self, block: PreBlock):
        code, lang = self._prepare_code(block.text)
        if lang is None:
            self._lang_label.set_text(_("Code snippet"))
        else:
            lang_name = self._textview.set_language(lang)
            self._lang_label.set_text(_("Code snippet (%s)") % lang_name)

        self._textview.print_code(code)

    @staticmethod
    def _prepare_code(text: str) -> tuple[str, str | None]:
        text = text.strip()
        code_start = text.partition("\n")[0]
        lang = None
        if len(code_start) > 3:
            lang = code_start[3:]

        code = text.partition("\n")[2][:-4]
        return code, lang


class CodeTextview(GtkSource.View):
    def __init__(self) -> None:
        GtkSource.View.__init__(self)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_top_margin(2)
        self.set_bottom_margin(2)
        self.set_monospace(True)
        self.get_buffer().set_highlight_matching_brackets(False)

        self._source_manager = GtkSource.LanguageManager.get_default()

        app.ged.register_event_handler(
            "style-changed", ged.GUI1, self._on_style_changed
        )

        style_scheme = get_source_view_style_scheme()
        if style_scheme is not None:
            self.get_buffer().set_style_scheme(style_scheme)

    def do_unroot(self) -> None:
        app.ged.remove_event_handler("style-changed", ged.GUI1, self._on_style_changed)

        GtkSource.View.do_unroot(self)
        app.check_finalize(self)

    def _on_style_changed(self, *args: Any) -> None:
        style_scheme = get_source_view_style_scheme()
        if style_scheme is not None:
            self.get_buffer().set_style_scheme(style_scheme)

    def set_language(self, language_string: str) -> str:
        lang = self._source_manager.get_language(language_string)
        if lang is None:
            return _("Unknown language")

        log.debug("Code snippet lang: %s", lang.get_name())
        self.get_buffer().set_language(lang)
        return lang.get_name()

    def get_code(self) -> str:
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def print_code(self, code: str) -> None:
        buffer_ = self.get_buffer()
        buffer_.insert(buffer_.get_start_iter(), code)

        if buffer_.get_line_count() == 1:
            # Add some space at the bottom so that scrollbar
            # does not overlap content, which makes text hard to select
            self.set_pixels_below_lines(10)
