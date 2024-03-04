# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk


class QuoteWidget(Gtk.Box):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        self.set_vexpand(True)
        self.get_style_context().add_class('conversation-quote')
        quote_bar = Gtk.Box()
        quote_bar.set_size_request(3, -1)
        quote_bar.set_margin_end(6)
        quote_bar.get_style_context().add_class('conversation-quote-bar')
        self.add(quote_bar)
