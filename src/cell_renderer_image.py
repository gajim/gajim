# -*- coding:utf-8 -*-
## src/cell_renderer_image.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

class CellRendererImage(Gtk.CellRendererPixbuf):

    __gproperties__ = {
            'image': (GObject.TYPE_OBJECT, 'Image',
                    'Image', GObject.PARAM_READWRITE),
    }

    def __init__(self, col_index, tv_index):
        super(CellRendererImage, self).__init__()
        self.image = None
        self.col_index = col_index
        self.tv_index = tv_index
        self.iters = {}

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_activate(event, widget, path, bg_area, cell_area, flags):
        """Renderers cannot be activated; always return True."""
        return True

    def do_editing_started(event, widget, path, fb_area, cell_area, flags):
        """Renderers cannot be edited; always return None."""
        return None

    def func(self, model, path, iter_, image_tree):
        image, tree = image_tree
        if model.get_value(iter_, self.tv_index) != image:
            return
        self.redraw = 1
        col = tree.get_column(self.col_index)
        cell_area = tree.get_cell_area(path, col)

        tree.queue_draw_area(cell_area.x, cell_area.y, cell_area.width,
            cell_area.height)

    def animation_timeout(self, tree, image):
        if image.get_storage_type() != Gtk.ImageType.ANIMATION:
            return
        self.redraw = 0
        iter_ = self.iters[image]
        timeval = GLib.TimeVal()
        timeval.tv_sec = GLib.get_monotonic_time() / 1000000
        iter_.advance(timeval)
        model = tree.get_model()
        if model:
            model.foreach(self.func, (image, tree))
        if self.redraw:
            GLib.timeout_add(iter_.get_delay_time(),
                self.animation_timeout, tree, image)
        elif image in self.iters:
            del self.iters[image]

    def do_render(self, ctx, widget, background_area, cell_area, flags):
        if not self.image:
            return

        if self.image.get_storage_type() == Gtk.ImageType.ANIMATION:
            if self.image not in self.iters:
                if not isinstance(widget, Gtk.TreeView):
                    return
                animation = self.image.get_animation()
                timeval = GLib.TimeVal()
                timeval.tv_sec = GLib.get_monotonic_time() / 1000000
                iter_ = animation.get_iter(timeval)
                self.iters[self.image] = iter_
                GLib.timeout_add(iter_.get_delay_time(), self.animation_timeout,
                    widget, self.image)

            pix = self.iters[self.image].get_pixbuf()
        elif self.image.get_storage_type() == Gtk.ImageType.PIXBUF:
            pix = self.image.get_pixbuf()
        else:
            return

        Gdk.cairo_set_source_pixbuf(ctx, pix, cell_area.x, cell_area.y)
        ctx.paint()

    def do_get_size(self, widget, cell_area):
        """
        Return the size we need for this cell.

        Each cell is drawn individually and is only as wide as it needs
        to be, we let the TreeViewColumn take care of making them all
        line up.
        """
        if not self.image:
            return 0, 0, 0, 0
        if self.image.get_storage_type() == Gtk.ImageType.ANIMATION:
            animation = self.image.get_animation()
            timeval = GLib.TimeVal()
            timeval.tv_sec = GLib.get_monotonic_time() / 1000000
            pix = animation.get_iter(timeval).get_pixbuf()
        elif self.image.get_storage_type() == Gtk.ImageType.PIXBUF:
            pix = self.image.get_pixbuf()
        else:
            return 0, 0, 0, 0
        pixbuf_width = pix.get_width()
        pixbuf_height = pix.get_height()
        calc_width = self.get_property('xpad') * 2 + pixbuf_width
        calc_height = self.get_property('ypad') * 2 + pixbuf_height
        x_offset = 0
        y_offset = 0
        if cell_area and pixbuf_width > 0 and pixbuf_height > 0:
            x_offset = self.get_property('xalign') * \
                            (cell_area.width - calc_width - \
                            self.get_property('xpad'))
            y_offset = self.get_property('yalign') * \
                            (cell_area.height - calc_height - \
                            self.get_property('ypad'))
        return x_offset, y_offset, calc_width, calc_height
