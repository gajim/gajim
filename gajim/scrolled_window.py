# -*- coding:utf-8 -*-
# Copyright (C) 2015 Patrick Griffis <tingping@tingping.se>
# Copyright (C) 2014 Christian Hergert <christian@hergert.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GObject, Gtk

class ScrolledWindow(Gtk.ScrolledWindow):
    """
        ScrolledWindow that sets a max size for the child to grow into.
        Taken from the Gnome Builder project:
            https://git.gnome.org/browse/gnome-builder/tree/contrib/egg/egg-scrolled-window.c
    """
    __gtype_name__ = "EggScrolledWindow"

    max_content_height = GObject.Property(type=int, default=-1, nick="Max Content Height",
                                          blurb="The maximum height request that can be made")
    max_content_width = GObject.Property(type=int, default=-1, nick="Max Content Width",
                                         blurb="The maximum width request that can be made")
    min_content_height = GObject.Property(type=int, default=-1, nick="Min Content Height",
                                          blurb="The minimum height request that can be made")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_after("notify::max-content-height", lambda obj, param: self.queue_resize())
        self.connect_after("notify::max-content-width", lambda obj, param: self.queue_resize())

    def set_min_content_height(self, value):
        self.min_content_height = value

    def set_max_content_height(self, value):
        self.max_content_height = value

    def set_max_content_width(self, value):
        self.max_content_width = value

    def get_max_content_height(self):
        return self.max_content_height

    def get_max_content_width(self):
        return self.max_content_width

    def do_get_preferred_height(self):
        min_height, natural_height = Gtk.ScrolledWindow.do_get_preferred_height(self)
        child = self.get_child()

        if natural_height and self.max_content_height > -1 and child:

            style = self.get_style_context()
            border = style.get_border(style.get_state())
            additional = border.top + border.bottom

            child_min_height, child_nat_height = child.get_preferred_height()
            if child_nat_height > natural_height and self.max_content_height > natural_height:
                natural_height = min(self.max_content_height, child_nat_height) + additional
            elif natural_height > child_nat_height:
                if child_nat_height < self.min_content_height:
                    return self.min_content_height, self.min_content_height
                min_height, natural_height = child_min_height + additional, child_nat_height + additional

        return min_height, natural_height

    def do_get_preferred_width(self):
        min_width, natural_width = Gtk.ScrolledWindow.do_get_preferred_width(self)
        child = self.get_child()

        if natural_width and self.max_content_width > -1 and child:

            style = self.get_style_context()
            border = style.get_border(style.get_state())
            additional = border.left + border.right + 1

            child_min_width, child_nat_width = child.get_preferred_width()
            if child_nat_width > natural_width and self.max_content_width > natural_width:
                natural_width = min(self.max_content_width, child_nat_width) + additional

        return min_width, natural_width
