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

import gi
gi.require_version('GtkSource', '4')
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource


class CodeWidget(Gtk.Box):
    def __init__(self, account):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        self._textview = CodeTextview()
        # self._scrolled = Gtk.ScrolledWindow()
        # self._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,
        #                           Gtk.PolicyType.AUTOMATIC)
        # self._scrolled.set_hexpand(True)
        # self._scrolled.set_vexpand(True)
        # self._scrolled.set_propagate_natural_height(True)
        # self._scrolled.set_max_content_height(400)
        # self._scrolled.add(self._textview)

        self.add(self._textview)

    def add_content(self, block):
        self._textview.print_code(block)


class CodeTextview(GtkSource.View):
    def __init__(self):
        GtkSource.View.__init__(self)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        self._source_manager = GtkSource.LanguageManager.get_default()

    def print_code(self, block):
        buffer_ = self.get_buffer()
        lang = self._source_manager.get_language('python3')
        buffer_.set_language(lang)
        self.set_show_line_numbers(True)
        buffer_.insert(buffer_.get_start_iter(), block.text)
