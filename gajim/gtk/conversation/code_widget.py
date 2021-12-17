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
from typing import Tuple
from typing import Optional

import logging

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GtkSource

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from gajim.common.styling import PreBlock

log = logging.getLogger('gajim.gui.conversation.code_widget')


class CodeWidget(Gtk.Box):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.get_style_context().add_class('code-widget')

        self._account = account

        header = Gtk.Box()
        header.set_spacing(6)
        header.get_style_context().add_class('code-widget-header')
        self._lang_label = Gtk.Label()
        header.add(self._lang_label)

        copy_button = Gtk.Button.new_from_icon_name(
            'edit-copy-symbolic', Gtk.IconSize.MENU)
        copy_button.set_tooltip_text(_('Copy code snippet'))
        copy_button.connect('clicked', self._on_copy)
        header.add(copy_button)
        self.add(header)

        self._textview = CodeTextview()
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,
                                  Gtk.PolicyType.NEVER)
        self._scrolled.set_hexpand(True)
        self._scrolled.set_vexpand(True)
        self._scrolled.set_propagate_natural_height(True)
        self._scrolled.set_max_content_height(400)
        self._scrolled.add(self._textview)

        self.add(self._scrolled)

    def _on_copy(self, _button: Gtk.Button) -> None:
        text = self._textview.get_code()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)

    def add_content(self, block: PreBlock):
        code, lang = self._prepare_code(block.text)
        lang_name = self._textview.set_language(lang)
        if lang is None:
            self._lang_label.set_text(_('Code snippet'))
        else:
            self._lang_label.set_text(_('Code snippet (%s)') % lang_name)

        self._textview.print_code(code)

    @staticmethod
    def _prepare_code(text: str) -> Tuple[str, Optional[str]]:
        code_start = text.partition('\n')[0]
        lang = None
        if len(code_start) > 3:
            lang = code_start[3:]

        code = text.partition('\n')[2][:-4]
        return code, lang


class CodeTextview(GtkSource.View):
    def __init__(self) -> None:
        GtkSource.View.__init__(self)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_top_margin(2)
        self.set_bottom_margin(2)
        self.set_monospace(True)

        self._source_manager = GtkSource.LanguageManager.get_default()
        self._style_scheme_manager = GtkSource.StyleSchemeManager.get_default()

        app.ged.register_event_handler('style-changed',
                                       ged.GUI1,
                                       self._on_style_changed)

        style_scheme = self._get_style_scheme()
        if style_scheme is not None:
            self.get_buffer().set_style_scheme(style_scheme)

    def _get_style_scheme(self) -> Optional[GtkSource.StyleScheme]:
        if app.css_config.prefer_dark:
            style_scheme = self._style_scheme_manager.get_scheme(
                'solarized-dark')
        else:
            style_scheme = self._style_scheme_manager.get_scheme(
                'solarized-light')
        return style_scheme

    def _on_style_changed(self, *args: Any) -> None:
        style_scheme = self._get_style_scheme()
        if style_scheme is not None:
            self.get_buffer().set_style_scheme(style_scheme)

    def set_language(self, language_string: Optional[str]) -> str:
        if language_string is None:
            language_string = 'python3'

        lang = self._source_manager.get_language(language_string)
        if lang is None:
            lang = self._source_manager.get_language('python3')

        assert lang is not None

        log.debug('Code snippet lang: %s', lang.get_name())
        self.get_buffer().set_language(lang)
        return lang.get_name()

    def get_code(self) -> str:
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def print_code(self, code: str) -> None:
        self.set_show_line_numbers(True)
        buffer_ = self.get_buffer()
        buffer_.insert(buffer_.get_start_iter(), code)
