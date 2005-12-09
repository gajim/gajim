##	cell_renderer_image.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gobject

class CellRendererImage(gtk.GenericCellRenderer):

	__gproperties__ = {
		'image': (gobject.TYPE_OBJECT, 'Image', 
			'Image', gobject.PARAM_READWRITE),
	}

	def __init__(self):
		self.__gobject_init__()
		self.image = None
		self.iters = {}

	def do_set_property(self, pspec, value):
		setattr(self, pspec.name, value)

	def do_get_property(self, pspec):
		return getattr(self, pspec.name)

	def func(self, model, path, iter, (image, tree)):
		if model.get_value(iter, 0) != image:
			return
		self.redraw = 1
		cell_area = tree.get_cell_area(path, tree.get_column(0))
		tree.queue_draw_area(cell_area.x, cell_area.y,
					cell_area.width, cell_area.height)

	def animation_timeout(self, tree, image):
		if image.get_storage_type() != gtk.IMAGE_ANIMATION:
			return
		self.redraw = 0
		iter = self.iters[image]
		iter.advance()
		model = tree.get_model()
		model.foreach(self.func, (image, tree))
		if self.redraw:
			gobject.timeout_add(iter.get_delay_time(),
					self.animation_timeout, tree, image)
		elif image in self.iters:
			del self.iters[image]
				
	def on_render(self, window, widget, background_area, cell_area,
					expose_area, flags):
		if not self.image:
			return
		pix_rect = gtk.gdk.Rectangle()
		pix_rect.x, pix_rect.y, pix_rect.width, pix_rect.height = \
			self.on_get_size(widget, cell_area)

		pix_rect.x += cell_area.x
		pix_rect.y += cell_area.y
		pix_rect.width -= 2 * self.get_property('xpad')
		pix_rect.height -= 2 * self.get_property('ypad')

		draw_rect = cell_area.intersect(pix_rect)
		draw_rect = expose_area.intersect(draw_rect)

		if self.image.get_storage_type() == gtk.IMAGE_ANIMATION:
			if self.image not in self.iters:
				animation = self.image.get_animation()
				iter =  animation.get_iter()
				self.iters[self.image] = iter
				gobject.timeout_add(iter.get_delay_time(),
					self.animation_timeout, widget, self.image)

			pix = self.iters[self.image].get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = self.image.get_pixbuf()
		else:
			return
		window.draw_pixbuf(widget.style.black_gc, pix,
					draw_rect.x - pix_rect.x,
					draw_rect.y - pix_rect.y,
					draw_rect.x, draw_rect.y + 2,
					draw_rect.width, draw_rect.height,
					gtk.gdk.RGB_DITHER_NONE, 0, 0)

	def on_get_size(self, widget, cell_area):
		if not self.image:
			return 0, 0, 0, 0
		if self.image.get_storage_type() == gtk.IMAGE_ANIMATION:
			animation = self.image.get_animation()
			pix = animation.get_iter().get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
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

if gtk.pygtk_version < (2, 8, 0):  
	gobject.type_register(CellRendererImage)
