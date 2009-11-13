# -*- coding:utf-8 -*-
## src/conversation_textview.py
##
## Copyright (C) 2005 Norman Rasmussen <norman AT rasmussen.co.za>
## Copyright (C) 2005-2006 Alex Mauer <hawke AT hawkesnest.net>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
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

from threading import Timer # for smooth scrolling

import gtk
import pango
import gobject
import time
import os
import tooltips
import dialogs
import locale
import Queue

import gtkgui_helpers
from common import gajim
from common import helpers
from common import latex
from common import i18n
from calendar import timegm
from common.fuzzyclock import FuzzyClock

from htmltextview import HtmlTextView
from common.exceptions import GajimGeneralException
from common.exceptions import LatexError

NOT_SHOWN = 0
ALREADY_RECEIVED = 1
SHOWN = 2

def is_selection_modified(mark):
	name = mark.get_name()
	if name and name in ('selection_bound', 'insert'):
		return True
	else:
		return False

def has_focus(widget):
	return widget.flags() & gtk.HAS_FOCUS == gtk.HAS_FOCUS

class TextViewImage(gtk.Image):

	def __init__(self, anchor):
		super(TextViewImage, self).__init__()
		self.anchor = anchor
		self._selected = False
		self._disconnect_funcs = []
		self.connect('parent-set', self.on_parent_set)
		self.connect('expose-event', self.on_expose)

	def _get_selected(self):
		parent = self.get_parent()
		if not parent or not self.anchor: return False
		buffer_ = parent.get_buffer()
		position = buffer_.get_iter_at_child_anchor(self.anchor)
		bounds = buffer_.get_selection_bounds()
		if bounds and position.in_range(*bounds):
			return True
		else:
			return False

	def get_state(self):
		parent = self.get_parent()
		if not parent:
			return gtk.STATE_NORMAL
		if self._selected:
			if has_focus(parent):
				return gtk.STATE_SELECTED
			else:
				return gtk.STATE_ACTIVE
		else:
			return gtk.STATE_NORMAL

	def _update_selected(self):
		selected = self._get_selected()
		if self._selected != selected:
			self._selected = selected
			self.queue_draw()

	def _do_connect(self, widget, signal, callback):
		id_ = widget.connect(signal, callback)
		def disconnect():
			widget.disconnect(id_)
		self._disconnect_funcs.append(disconnect)

	def _disconnect_signals(self):
		for func in self._disconnect_funcs:
			func()
		self._disconnect_funcs = []

	def on_parent_set(self, widget, old_parent):
		parent = self.get_parent()
		if not parent:
			self._disconnect_signals()
			return

		self._do_connect(parent, 'style-set', self.do_queue_draw)
		self._do_connect(parent, 'focus-in-event', self.do_queue_draw)
		self._do_connect(parent, 'focus-out-event', self.do_queue_draw)

		textbuf = parent.get_buffer()
		self._do_connect(textbuf, 'mark-set', self.on_mark_set)
		self._do_connect(textbuf, 'mark-deleted', self.on_mark_deleted)

	def do_queue_draw(self, *args):
		self.queue_draw()
		return False

	def on_mark_set(self, buf, iterat, mark):
		self.on_mark_modified(mark)
		return False

	def on_mark_deleted(self, buf, mark):
		self.on_mark_modified(mark)
		return False

	def on_mark_modified(self, mark):
		if is_selection_modified(mark):
			self._update_selected()

	def on_expose(self, widget, event):
		state = self.get_state()
		if state != gtk.STATE_NORMAL:
			gc = widget.get_style().base_gc[state]
			area = widget.allocation
			widget.window.draw_rectangle(gc, True, area.x, area.y,
				area.width, area.height)
		return False


class ConversationTextview(gobject.GObject):
	'''Class for the conversation textview (where user reads already said
	messages) for chat/groupchat windows'''
	__gsignals__ = dict(
		quote = (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION,
			None, # return value
			(str, ) # arguments
		)
	)

	FOCUS_OUT_LINE_PIXBUF = gtk.gdk.pixbuf_new_from_file(os.path.join(
		gajim.DATA_DIR, 'pixmaps', 'muc_separator.png'))
	XEP0184_WARNING_PIXBUF = gtk.gdk.pixbuf_new_from_file(os.path.join(
		gajim.DATA_DIR, 'pixmaps', 'receipt_missing.png'))

	# smooth scroll constants
	MAX_SCROLL_TIME = 0.4 # seconds
	SCROLL_DELAY = 33 # milliseconds

	def __init__(self, account, used_in_history_window = False):
		'''if used_in_history_window is True, then we do not show
		Clear menuitem in context menu'''
		gobject.GObject.__init__(self)
		self.used_in_history_window = used_in_history_window

		self.fc = FuzzyClock()


		# no need to inherit TextView, use it as atrribute is safer
		self.tv = HtmlTextView()
		self.tv.html_hyperlink_handler = self.html_hyperlink_handler

		# set properties
		self.tv.set_border_width(1)
		self.tv.set_accepts_tab(True)
		self.tv.set_editable(False)
		self.tv.set_cursor_visible(False)
		self.tv.set_wrap_mode(gtk.WRAP_WORD_CHAR)
		self.tv.set_left_margin(2)
		self.tv.set_right_margin(2)
		self.handlers = {}
		self.images = []
		self.image_cache = {}
		self.xep0184_marks = {}
		self.xep0184_shown = {}

		# It's True when we scroll in the code, so we can detect scroll from user
		self.auto_scrolling = False

		# connect signals
		id_ = self.tv.connect('motion_notify_event',
			self.on_textview_motion_notify_event)
		self.handlers[id_] = self.tv
		id_ = self.tv.connect('populate_popup', self.on_textview_populate_popup)
		self.handlers[id_] = self.tv
		id_ = self.tv.connect('button_press_event',
			self.on_textview_button_press_event)
		self.handlers[id_] = self.tv

		id_ = self.tv.connect('expose-event',
			self.on_textview_expose_event)
		self.handlers[id_] = self.tv


		self.account = account
		self.change_cursor = False
		self.last_time_printout = 0

		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.tv.modify_font(font)
		buffer_ = self.tv.get_buffer()
		end_iter = buffer_.get_end_iter()
		buffer_.create_mark('end', end_iter, False)

		self.tagIn = buffer_.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		font = pango.FontDescription(gajim.config.get('inmsgfont'))
		self.tagIn.set_property('foreground', color)
		self.tagIn.set_property('font-desc', font)

		self.tagOut = buffer_.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		font = pango.FontDescription(gajim.config.get('outmsgfont'))
		self.tagOut.set_property('foreground', color)
		self.tagOut.set_property('font-desc', font)

		self.tagStatus = buffer_.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		font = pango.FontDescription(gajim.config.get('satusmsgfont'))
		self.tagStatus.set_property('foreground', color)
		self.tagStatus.set_property('font-desc', font)

		self.tagInText = buffer_.create_tag('incomingtxt')
		color = gajim.config.get('inmsgtxtcolor')
		font = pango.FontDescription(gajim.config.get('inmsgtxtfont'))
		if color:
			self.tagInText.set_property('foreground', color)
		self.tagInText.set_property('font-desc', font)

		self.tagOutText = buffer_.create_tag('outgoingtxt')
		color = gajim.config.get('outmsgtxtcolor')
		if color:
			font = pango.FontDescription(gajim.config.get('outmsgtxtfont'))
		self.tagOutText.set_property('foreground', color)
		self.tagOutText.set_property('font-desc', font)

		colors = gajim.config.get('gc_nicknames_colors')
		colors = colors.split(':')
		for i,color in enumerate(colors):
			tagname = 'gc_nickname_color_' + str(i)
			tag = buffer_.create_tag(tagname)
			tag.set_property('foreground', color)

		tag = buffer_.create_tag('marked')
		color = gajim.config.get('markedmsgcolor')
		tag.set_property('foreground', color)
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer_.create_tag('time_sometimes')
		tag.set_property('foreground', 'darkgrey')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)

		tag = buffer_.create_tag('small')
		tag.set_property('scale', pango.SCALE_SMALL)

		tag = buffer_.create_tag('restored_message')
		color = gajim.config.get('restored_messages_color')
		tag.set_property('foreground', color)

		self.tagURL = buffer_.create_tag('url')
		color = gajim.config.get('urlmsgcolor')
		self.tagURL.set_property('foreground', color)
		self.tagURL.set_property('underline', pango.UNDERLINE_SINGLE)
		id_ = self.tagURL.connect('event', self.hyperlink_handler, 'url')
		self.handlers[id_] = self.tagURL

		self.tagMail = buffer_.create_tag('mail')
		self.tagMail.set_property('foreground', color)
		self.tagMail.set_property('underline', pango.UNDERLINE_SINGLE)
		id_ = self.tagMail.connect('event', self.hyperlink_handler, 'mail')
		self.handlers[id_] = self.tagMail

		self.tagXMPP = buffer_.create_tag('xmpp')
		self.tagXMPP.set_property('foreground', color)
		self.tagXMPP.set_property('underline', pango.UNDERLINE_SINGLE)
		id_ = self.tagXMPP.connect('event', self.hyperlink_handler, 'xmpp')
		self.handlers[id_] = self.tagXMPP

		self.tagSthAtSth = buffer_.create_tag('sth_at_sth')
		self.tagSthAtSth.set_property('foreground', color)
		self.tagSthAtSth.set_property('underline', pango.UNDERLINE_SINGLE)
		id_ = self.tagSthAtSth.connect('event', self.hyperlink_handler,
			'sth_at_sth')
		self.handlers[id_] = self.tagSthAtSth

		tag = buffer_.create_tag('bold')
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer_.create_tag('italic')
		tag.set_property('style', pango.STYLE_ITALIC)

		tag = buffer_.create_tag('underline')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)

		buffer_.create_tag('focus-out-line', justification = gtk.JUSTIFY_CENTER)

		tag = buffer_.create_tag('xep0184-warning')

		# One mark at the begining then 2 marks between each lines
		size = gajim.config.get('max_conversation_lines')
		size = 2 * size - 1
		self.marks_queue = Queue.Queue(size)

		self.allow_focus_out_line = True
		# holds a mark at the end of --- line
		self.focus_out_end_mark = None

		self.xep0184_warning_tooltip = tooltips.BaseTooltip()

		self.line_tooltip = tooltips.BaseTooltip()
		# use it for hr too
		self.tv.focus_out_line_pixbuf = ConversationTextview.FOCUS_OUT_LINE_PIXBUF
		self.smooth_id = None

	def del_handlers(self):
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
		del self.handlers
		self.tv.destroy()
		#FIXME:
		# self.line_tooltip.destroy()

	def update_tags(self):
		self.tagIn.set_property('foreground', gajim.config.get('inmsgcolor'))
		self.tagOut.set_property('foreground', gajim.config.get('outmsgcolor'))
		self.tagStatus.set_property('foreground',
			gajim.config.get('statusmsgcolor'))
		self.tagURL.set_property('foreground', gajim.config.get('urlmsgcolor'))
		self.tagMail.set_property('foreground', gajim.config.get('urlmsgcolor'))

	def at_the_end(self):
		buffer_ = self.tv.get_buffer()
		end_iter = buffer_.get_end_iter()
		end_rect = self.tv.get_iter_location(end_iter)
		visible_rect = self.tv.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			return True
		return False

	# Smooth scrolling inspired by Pidgin code
	def smooth_scroll(self):
		parent = self.tv.get_parent()
		if not parent:
			return False
		vadj = parent.get_vadjustment()
		max_val = vadj.upper - vadj.page_size + 1
		cur_val = vadj.get_value()
		# scroll by 1/3rd of remaining distance
		onethird = cur_val + ((max_val - cur_val) / 3.0)
		self.auto_scrolling = True
		vadj.set_value(onethird)
		self.auto_scrolling = False
		if max_val - onethird < 0.01:
			self.smooth_id = None
			self.smooth_scroll_timer.cancel()
			return False
		return True

	def smooth_scroll_timeout(self):
		gobject.idle_add(self.do_smooth_scroll_timeout)
		return

	def do_smooth_scroll_timeout(self):
		if not self.smooth_id:
			# we finished scrolling
			return
		gobject.source_remove(self.smooth_id)
		self.smooth_id = None
		parent = self.tv.get_parent()
		if parent:
			vadj = parent.get_vadjustment()
			self.auto_scrolling = True
			vadj.set_value(vadj.upper - vadj.page_size + 1)
			self.auto_scrolling = False

	def smooth_scroll_to_end(self):
		if None != self.smooth_id: # already scrolling
			return False
		self.smooth_id = gobject.timeout_add(self.SCROLL_DELAY,
			self.smooth_scroll)
		self.smooth_scroll_timer = Timer(self.MAX_SCROLL_TIME,
			self.smooth_scroll_timeout)
		self.smooth_scroll_timer.start()
		return False

	def scroll_to_end(self):
		parent = self.tv.get_parent()
		buffer_ = self.tv.get_buffer()
		end_mark = buffer_.get_mark('end')
		if not end_mark:
			return False
		self.auto_scrolling = True
		self.tv.scroll_to_mark(end_mark, 0, True, 0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		self.auto_scrolling = False
		return False # when called in an idle_add, just do it once

	def bring_scroll_to_end(self, diff_y = 0,
	use_smooth=gajim.config.get('use_smooth_scrolling')):
		''' scrolls to the end of textview if end is not visible '''
		buffer_ = self.tv.get_buffer()
		end_iter = buffer_.get_end_iter()
		end_rect = self.tv.get_iter_location(end_iter)
		visible_rect = self.tv.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			if use_smooth:
				gobject.idle_add(self.smooth_scroll_to_end)
			else:
				gobject.idle_add(self.scroll_to_end_iter)

	def scroll_to_end_iter(self):
		buffer_ = self.tv.get_buffer()
		end_iter = buffer_.get_end_iter()
		if not end_iter:
			return False
		self.tv.scroll_to_iter(end_iter, 0, False, 1, 1)
		return False # when called in an idle_add, just do it once

	def stop_scrolling(self):
		if self.smooth_id:
			gobject.source_remove(self.smooth_id)
			self.smooth_id = None
			self.smooth_scroll_timer.cancel()

	def show_xep0184_warning(self, id_):
		if id_ in self.xep0184_marks:
			return

		buffer_ = self.tv.get_buffer()
		buffer_.begin_user_action()

		self.xep0184_marks[id_] = buffer_.create_mark(None,
			buffer_.get_end_iter(), left_gravity=True)
		self.xep0184_shown[id_] = NOT_SHOWN

		def show_it():
			if (not id_ in self.xep0184_shown) or \
			self.xep0184_shown[id_] == ALREADY_RECEIVED:
				return False

			end_iter = buffer_.get_iter_at_mark(
				self.xep0184_marks[id_])
			buffer_.insert(end_iter, ' ')
			buffer_.insert_pixbuf(end_iter,
				ConversationTextview.XEP0184_WARNING_PIXBUF)
			before_img_iter = buffer_.get_iter_at_mark(
				self.xep0184_marks[id_])
			before_img_iter.forward_char()
			post_img_iter = before_img_iter.copy()
			post_img_iter.forward_char()
			buffer_.apply_tag_by_name('xep0184-warning', before_img_iter,
				post_img_iter)

			self.xep0184_shown[id_] = SHOWN
			return False
		gobject.timeout_add_seconds(3, show_it)

		buffer_.end_user_action()

	def hide_xep0184_warning(self, id_):
		if id_ not in self.xep0184_marks:
			return

		if self.xep0184_shown[id_] == NOT_SHOWN:
			self.xep0184_shown[id_] = ALREADY_RECEIVED
			return

		buffer_ = self.tv.get_buffer()
		buffer_.begin_user_action()

		begin_iter = buffer_.get_iter_at_mark(self.xep0184_marks[id_])

		end_iter = begin_iter.copy()
		# XXX: Is there a nicer way?
		end_iter.forward_char()
		end_iter.forward_char()

		buffer_.delete(begin_iter, end_iter)
		buffer_.delete_mark(self.xep0184_marks[id_])

		buffer_.end_user_action()

		del self.xep0184_marks[id_]
		del self.xep0184_shown[id_]

	def show_focus_out_line(self):
		if not self.allow_focus_out_line:
			# if room did not receive focus-in from the last time we added
			# --- line then do not readd
			return

		print_focus_out_line = False
		buffer_ = self.tv.get_buffer()

		if self.focus_out_end_mark is None:
			# this happens only first time we focus out on this room
			print_focus_out_line = True

		else:
			focus_out_end_iter = buffer_.get_iter_at_mark(self.focus_out_end_mark)
			focus_out_end_iter_offset = focus_out_end_iter.get_offset()
			if focus_out_end_iter_offset != buffer_.get_end_iter().get_offset():
				# this means after last-focus something was printed
				# (else end_iter's offset is the same as before)
				# only then print ---- line (eg. we avoid printing many following
				# ---- lines)
				print_focus_out_line = True

		if print_focus_out_line and buffer_.get_char_count() > 0:
			buffer_.begin_user_action()

			# remove previous focus out line if such focus out line exists
			if self.focus_out_end_mark is not None:
				end_iter_for_previous_line = buffer_.get_iter_at_mark(
					self.focus_out_end_mark)
				begin_iter_for_previous_line = end_iter_for_previous_line.copy()
				# img_char+1 (the '\n')
				begin_iter_for_previous_line.backward_chars(2)

				# remove focus out line
				buffer_.delete(begin_iter_for_previous_line,
					end_iter_for_previous_line)
				buffer_.delete_mark(self.focus_out_end_mark)

			# add the new focus out line
			end_iter = buffer_.get_end_iter()
			buffer_.insert(end_iter, '\n')
			buffer_.insert_pixbuf(end_iter,
				ConversationTextview.FOCUS_OUT_LINE_PIXBUF)

			end_iter = buffer_.get_end_iter()
			before_img_iter = end_iter.copy()
			# one char back (an image also takes one char)
			before_img_iter.backward_char()
			buffer_.apply_tag_by_name('focus-out-line', before_img_iter, end_iter)

			self.allow_focus_out_line = False

			# update the iter we hold to make comparison the next time
			self.focus_out_end_mark = buffer_.create_mark(None,
				buffer_.get_end_iter(), left_gravity=True)

			buffer_.end_user_action()

			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.scroll_to_end)

	def show_xep0184_warning_tooltip(self):
		pointer = self.tv.get_pointer()
		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			pointer[0], pointer[1])
		tags = self.tv.get_iter_at_location(x, y).get_tags()
		tag_table = self.tv.get_buffer().get_tag_table()
		xep0184_warning = False
		for tag in tags:
			if tag == tag_table.lookup('xep0184-warning'):
				xep0184_warning = True
				break
		if xep0184_warning and not self.xep0184_warning_tooltip.win:
			# check if the current pointer is still over the line
			position = self.tv.window.get_origin()
			self.xep0184_warning_tooltip.show_tooltip(_('This icon indicates that '
				'this message has not yet\nbeen received by the remote end. '
				"If this icon stays\nfor a long time, it's likely the message got "
				'lost.'), 8, position[1] + pointer[1])

	def show_line_tooltip(self):
		pointer = self.tv.get_pointer()
		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			pointer[0], pointer[1])
		tags = self.tv.get_iter_at_location(x, y).get_tags()
		tag_table = self.tv.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag == tag_table.lookup('focus-out-line'):
				over_line = True
				break
		if over_line and not self.line_tooltip.win:
			# check if the current pointer is still over the line
			position = self.tv.window.get_origin()
			self.line_tooltip.show_tooltip(_('Text below this line is what has '
				'been said since the\nlast time you paid attention to this group '
				'chat'), 8, position[1] + pointer[1])

	def on_textview_expose_event(self, widget, event):
		expalloc = event.area
		exp_x0 = expalloc.x
		exp_y0 = expalloc.y
		exp_x1 = exp_x0 + expalloc.width
		exp_y1 = exp_y0 + expalloc.height

		try:
			tryfirst = [self.image_cache[(exp_x0, exp_y0)]]
		except KeyError:
			tryfirst = []

		for image in tryfirst + self.images:
			imgalloc = image.allocation
			img_x0 = imgalloc.x
			img_y0 = imgalloc.y
			img_x1 = img_x0 + imgalloc.width
			img_y1 = img_y0 + imgalloc.height

			if img_x0 <= exp_x0 and img_y0 <= exp_y0 and \
			exp_x1 <= img_x1 and exp_y1 <= img_y1:
				self.image_cache[(img_x0, img_y0)] = image
				widget.propagate_expose(image, event)
				return True
		return False

	def on_textview_motion_notify_event(self, widget, event):
		'''change the cursor to a hand when we are over a mail or an
		url'''
		pointer_x, pointer_y = self.tv.window.get_pointer()[0:2]
		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			pointer_x, pointer_y)
		tags = self.tv.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = False
		tag_table = self.tv.get_buffer().get_tag_table()
		over_line = False
		xep0184_warning = False
		for tag in tags:
			if tag in (tag_table.lookup('url'), tag_table.lookup('mail'), \
			tag_table.lookup('xmpp'), tag_table.lookup('sth_at_sth')):
				self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = True
			elif tag == tag_table.lookup('focus-out-line'):
				over_line = True
			elif tag == tag_table.lookup('xep0184-warning'):
				xep0184_warning = True

		if self.line_tooltip.timeout != 0:
			# Check if we should hide the line tooltip
			if not over_line:
				self.line_tooltip.hide_tooltip()
		if self.xep0184_warning_tooltip.timeout != 0:
			# Check if we should hide the XEP-184 warning tooltip
			if not xep0184_warning:
				self.xep0184_warning_tooltip.hide_tooltip()
		if over_line and not self.line_tooltip.win:
			self.line_tooltip.timeout = gobject.timeout_add(500,
				self.show_line_tooltip)
			self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
			self.change_cursor = True
		if xep0184_warning and not self.xep0184_warning_tooltip.win:
			self.xep0184_warning_tooltip.timeout = gobject.timeout_add(500,
				self.show_xep0184_warning_tooltip)
			self.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
			self.change_cursor = True

	def clear(self, tv = None):
		'''clear text in the textview'''
		buffer_ = self.tv.get_buffer()
		start, end = buffer_.get_bounds()
		buffer_.delete(start, end)
		size = gajim.config.get('max_conversation_lines')
		size = 2 * size - 1
		self.marks_queue = Queue.Queue(size)
		self.focus_out_end_mark = None

	def visit_url_from_menuitem(self, widget, link):
		'''basically it filters out the widget instance'''
		helpers.launch_browser_mailer('url', link)

	def on_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		(only if used_in_history_window is False)
		and if we have sth selected we show a submenu with actions on
		the phrase (see on_conversation_textview_button_press_event)'''

		separator_menuitem_was_added = False
		if not self.used_in_history_window:
			item = gtk.SeparatorMenuItem()
			menu.prepend(item)
			separator_menuitem_was_added = True

			item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
			menu.prepend(item)
			id_ = item.connect('activate', self.clear)
			self.handlers[id_] = item

		if self.selected_phrase:
			if not separator_menuitem_was_added:
				item = gtk.SeparatorMenuItem()
				menu.prepend(item)

			if not self.used_in_history_window:
				item = gtk.MenuItem(_('_Quote'))
				id_ = item.connect('activate', self.on_quote)
				self.handlers[id_] = item
				menu.prepend(item)

			_selected_phrase = helpers.reduce_chars_newlines(
				self.selected_phrase, 25, 2)
			item = gtk.MenuItem(_('_Actions for "%s"') % _selected_phrase)
			menu.prepend(item)
			submenu = gtk.Menu()
			item.set_submenu(submenu)

			always_use_en = gajim.config.get('always_english_wikipedia')
			if always_use_en:
				link = 'http://en.wikipedia.org/wiki/Special:Search?search=%s'\
					% self.selected_phrase
			else:
				link = 'http://%s.wikipedia.org/wiki/Special:Search?search=%s'\
					% (gajim.LANG, self.selected_phrase)
			item = gtk.MenuItem(_('Read _Wikipedia Article'))
			id_ = item.connect('activate', self.visit_url_from_menuitem, link)
			self.handlers[id_] = item
			submenu.append(item)

			item = gtk.MenuItem(_('Look it up in _Dictionary'))
			dict_link = gajim.config.get('dictionary_url')
			if dict_link == 'WIKTIONARY':
				# special link (yeah undocumented but default)
				always_use_en = gajim.config.get('always_english_wiktionary')
				if always_use_en:
					link = 'http://en.wiktionary.org/wiki/Special:Search?search=%s'\
						% self.selected_phrase
				else:
					link = 'http://%s.wiktionary.org/wiki/Special:Search?search=%s'\
						% (gajim.LANG, self.selected_phrase)
				id_ = item.connect('activate', self.visit_url_from_menuitem, link)
				self.handlers[id_] = item
			else:
				if dict_link.find('%s') == -1:
					# we must have %s in the url if not WIKTIONARY
					item = gtk.MenuItem(_(
						'Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
					item.set_property('sensitive', False)
				else:
					link = dict_link % self.selected_phrase
					id_ = item.connect('activate', self.visit_url_from_menuitem,
						link)
					self.handlers[id_] = item
			submenu.append(item)


			search_link = gajim.config.get('search_engine')
			if search_link.find('%s') == -1:
				# we must have %s in the url
				item = gtk.MenuItem(_('Web Search URL is missing an "%s"'))
				item.set_property('sensitive', False)
			else:
				item = gtk.MenuItem(_('Web _Search for it'))
				link =	search_link % self.selected_phrase
				id_ = item.connect('activate', self.visit_url_from_menuitem, link)
				self.handlers[id_] = item
			submenu.append(item)

			item = gtk.MenuItem(_('Open as _Link'))
			id_ = item.connect('activate', self.visit_url_from_menuitem, link)
			self.handlers[id_] = item
			submenu.append(item)

		menu.show_all()

	def on_quote(self, widget):
		self.emit('quote', self.selected_phrase)

	def on_textview_button_press_event(self, widget, event):
		# If we clicked on a taged text do NOT open the standard popup menu
		# if normal text check if we have sth selected
		self.selected_phrase = '' # do not move belove event button check!

		if event.button != 3: # if not right click
			return False

		x, y = self.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			int(event.x), int(event.y))
		iter_ = self.tv.get_iter_at_location(x, y)
		tags = iter_.get_tags()


		if tags: # we clicked on sth special (it can be status message too)
			for tag in tags:
				tag_name = tag.get_property('name')
				if tag_name in ('url', 'mail', 'xmpp', 'sth_at_sth'):
					return True # we block normal context menu

		# we check if sth was selected and if it was we assign
		# selected_phrase variable
		# so on_conversation_textview_populate_popup can use it
		buffer_ = self.tv.get_buffer()
		return_val = buffer_.get_selection_bounds()
		if return_val: # if sth was selected when we right-clicked
			# get the selected text
			start_sel, finish_sel = return_val[0], return_val[1]
			self.selected_phrase = buffer_.get_text(start_sel, finish_sel).decode(
				'utf-8')
		elif ord(iter_.get_char()) > 31:
			# we clicked on a word, do as if it's selected for context menu
			start_sel = iter_.copy()
			if not start_sel.starts_word():
				start_sel.backward_word_start()
			finish_sel = iter_.copy()
			if not finish_sel.ends_word():
				finish_sel.forward_word_end()
			self.selected_phrase = buffer_.get_text(start_sel, finish_sel).decode(
				'utf-8')

	def on_open_link_activate(self, widget, kind, text):
		helpers.launch_browser_mailer(kind, text)

	def on_copy_link_activate(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def on_start_chat_activate(self, widget, jid):
		gajim.interface.new_chat_from_jid(self.account, jid)

	def on_join_group_chat_menuitem_activate(self, widget, room_jid):
		if 'join_gc' in gajim.interface.instances[self.account]:
			instance = gajim.interface.instances[self.account]['join_gc']
			instance.xml.get_widget('room_jid_entry').set_text(room_jid)
			gajim.interface.instances[self.account]['join_gc'].window.present()
		else:
			try:
				dialogs.JoinGroupchatWindow(account=self.account, room_jid=room_jid)
			except GajimGeneralException:
				pass

	def on_add_to_roster_activate(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def make_link_menu(self, event, kind, text):
		xml = gtkgui_helpers.get_glade('chat_context_menu.glade')
		menu = xml.get_widget('chat_context_menu')
		childs = menu.get_children()
		if kind == 'url':
			id_ = childs[0].connect('activate', self.on_copy_link_activate, text)
			self.handlers[id_] = childs[0]
			id_ = childs[1].connect('activate', self.on_open_link_activate, kind,
				text)
			self.handlers[id_] = childs[1]
			childs[2].hide() # copy mail address
			childs[3].hide() # open mail composer
			childs[4].hide() # jid section separator
			childs[5].hide() # start chat
			childs[6].hide() # join group chat
			childs[7].hide() # add to roster
		else: # It's a mail or a JID
			# load muc icon
			join_group_chat_menuitem = xml.get_widget('join_group_chat_menuitem')
			muc_icon = gtkgui_helpers.load_icon('muc_active')
			if muc_icon:
				join_group_chat_menuitem.set_image(muc_icon)

			text = text.lower()
			if text.startswith('xmpp:'):
				text = text[5:]
			id_ = childs[2].connect('activate', self.on_copy_link_activate, text)
			self.handlers[id_] = childs[2]
			id_ = childs[3].connect('activate', self.on_open_link_activate, kind,
				text)
			self.handlers[id_] = childs[3]
			id_ = childs[5].connect('activate', self.on_start_chat_activate, text)
			self.handlers[id_] = childs[5]
			id_ = childs[6].connect('activate',
				self.on_join_group_chat_menuitem_activate, text)
			self.handlers[id_] = childs[6]

			allow_add = False
			if self.account:
				c = gajim.contacts.get_first_contact_from_jid(self.account, text)
				if c and not gajim.contacts.is_pm_from_contact(self.account, c):
					if _('Not in Roster') in c.groups:
						allow_add = True
				else: # he or she's not at all in the account contacts
					allow_add = True

			if allow_add:
				id_ = childs[7].connect('activate', self.on_add_to_roster_activate,
					text)
				self.handlers[id_] = childs[7]
				childs[7].show() # show add to roster menuitem
			else:
				childs[7].hide() # hide add to roster menuitem

			if kind == 'xmpp':
				childs[2].hide() # copy mail address
				childs[3].hide() # open mail composer
				childs[4].hide() # jid section separator
			elif kind == 'mail':
				childs[4].hide() # jid section separator
				childs[5].hide() # start chat
				childs[6].hide() # join group chat
				childs[7].hide() # add to roster

			childs[0].hide() # copy link location
			childs[1].hide() # open link in browser

		menu.popup(None, None, None, event.button, event.time)

	def hyperlink_handler(self, texttag, widget, event, iter_, kind):
		if event.type == gtk.gdk.BUTTON_PRESS:
			begin_iter = iter_.copy()
			# we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter_.copy()
			# we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = self.tv.get_buffer().get_text(begin_iter, end_iter).decode(
				'utf-8')
			if event.button == 3: # right click
				self.make_link_menu(event, kind, word)
			else:
				# we launch the correct application
				if kind == 'xmpp':
					word = word[5:]
					if '?' in word:
						(jid, action) = word.split('?')
						if action == 'join':
							self.on_join_group_chat_menuitem_activate(None, jid)
						else:
							self.on_start_chat_activate(None, jid)
					else:
						self.on_start_chat_activate(None, word)
				else:
					helpers.launch_browser_mailer(kind, word)

	def html_hyperlink_handler(self, texttag, widget, event, iter_, kind, href):
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3: # right click
				self.make_link_menu(event, kind, href)
				return True
			else:
				# we launch the correct application
				helpers.launch_browser_mailer(kind, href)


	def detect_and_print_special_text(self, otext, other_tags, graphics=True):
		'''detects special text (emots & links & formatting)
		prints normal text before any special text it founts,
		then print special text (that happens many times until
		last special text is printed) and then returns the index
		after *last* special text, so we can print it in
		print_conversation_line()'''

		buffer_ = self.tv.get_buffer()
		
		insert_tags_func = buffer_.insert_with_tags_by_name
		# detect_and_print_special_text() is also used by 
		# HtmlHandler.handle_specials() and there tags is gtk.TextTag objects,
		# not strings
		if other_tags and isinstance(other_tags[0], gtk.TextTag):
			insert_tags_func = buffer_.insert_with_tags

		index = 0

		# Too many special elements (emoticons, LaTeX formulas, etc)
		# may cause Gajim to freeze (see #5129).
		# We impose an arbitrary limit of 100 specials per message.
		specials_limit = 100

		# basic: links + mail + formatting is always checked (we like that)
		if gajim.config.get('emoticons_theme') and graphics:
			# search for emoticons & urls
			iterator = gajim.interface.emot_and_basic_re.finditer(otext)
		else: # search for just urls + mail + formatting
			iterator = gajim.interface.basic_pattern_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start > index:
				text_before_special_text = otext[index:start]
				end_iter = buffer_.get_end_iter()
				# we insert normal text
				insert_tags_func(end_iter, text_before_special_text, *other_tags)
			index = end # update index

			# now print it
			self.print_special_text(special_text, other_tags, graphics=graphics)
			specials_limit -= 1
			if specials_limit <= 0:
				break

		# add the rest of text located in the index and after
		end_iter = buffer_.get_end_iter()
		insert_tags_func(end_iter, otext[index:], *other_tags)
		
		return buffer_.get_end_iter()

	def print_special_text(self, special_text, other_tags, graphics=True):
		'''is called by detect_and_print_special_text and prints
		special text (emots, links, formatting)'''
		tags = []
		use_other_tags = True
		text_is_valid_uri = False
		show_ascii_formatting_chars = \
			gajim.config.get('show_ascii_formatting_chars')
		buffer_ = self.tv.get_buffer()

		# Check if we accept this as an uri
		schemes = gajim.config.get('uri_schemes').split()
		for scheme in schemes:
			if special_text.startswith(scheme + ':'):
				text_is_valid_uri = True

		possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
		if gajim.config.get('emoticons_theme') and \
		possible_emot_ascii_caps in gajim.interface.emoticons.keys() and graphics:
			# it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			end_iter = buffer_.get_end_iter()
			anchor = buffer_.create_child_anchor(end_iter)
			img = TextViewImage(anchor)
			animations = gajim.interface.emoticons_animations
			if not emot_ascii in animations:
				animations[emot_ascii] = gtk.gdk.PixbufAnimation(
					gajim.interface.emoticons[emot_ascii])
			img.set_from_animation(animations[emot_ascii])
			img.show()
			self.images.append(img)
			# add with possible animation
			self.tv.add_child_at_anchor(img, anchor)
		elif special_text.startswith('www.') or \
		special_text.startswith('ftp.') or \
		text_is_valid_uri:
			tags.append('url')
			use_other_tags = False
		elif special_text.startswith('mailto:'):
			tags.append('mail')
			use_other_tags = False
		elif special_text.startswith('xmpp:'):
			tags.append('xmpp')
			use_other_tags = False
		elif gajim.interface.sth_at_sth_dot_sth_re.match(special_text):
			# it's a JID or mail
			tags.append('sth_at_sth')
			use_other_tags = False
		elif special_text.startswith('*'): # it's a bold text
			tags.append('bold')
			if special_text[1] == '/' and special_text[-2] == '/' and\
			len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove */ /*
			elif special_text[1] == '_' and special_text[-2] == '_' and \
			len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove *_ _*
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove * *
		elif special_text.startswith('/'): # it's an italic text
			tags.append('italic')
			if special_text[1] == '*' and special_text[-2] == '*' and \
			len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /* */
			elif special_text[1] == '_' and special_text[-2] == '_' and \
			len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /_ _/
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove / /
		elif special_text.startswith('_'): # it's an underlined text
			tags.append('underline')
			if special_text[1] == '*' and special_text[-2] == '*' and \
			len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _* *_
			elif special_text[1] == '/' and special_text[-2] == '/' and \
			len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _/ /_
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove _ _
		elif gajim.HAVE_LATEX and special_text.startswith('$$') and \
		special_text.endswith('$$') and graphics:
			try:
				imagepath = latex.latex_to_image(special_text[2:-2])
			except LatexError, e:
				# print the error after the line has been written
				gobject.idle_add(self.print_conversation_line, str(e), '', 'info',
					'', None)
				imagepath = None
			end_iter = buffer_.get_end_iter()
			if imagepath is not None:
				anchor = buffer_.create_child_anchor(end_iter)
				img = gtk.Image()
				img.set_from_file(imagepath)
				img.show()
				# add
				self.tv.add_child_at_anchor(img, anchor)
				# delete old file
				try:
					os.remove(imagepath)
				except Exception:
					pass
			else:
				buffer_.insert(end_iter, special_text)
			use_other_tags = False
		else:
			# It's nothing special
			if use_other_tags:
				end_iter = buffer_.get_end_iter()
				insert_tags_func = buffer_.insert_with_tags_by_name
				if other_tags and isinstance(other_tags[0], gtk.TextTag):
					insert_tags_func = buffer_.insert_with_tags

				insert_tags_func(end_iter, special_text, *other_tags)

		if tags:
			end_iter = buffer_.get_end_iter()
			all_tags = tags[:]
			if use_other_tags:
				all_tags += other_tags
			buffer_.insert_with_tags_by_name(end_iter, special_text, *all_tags)

	def print_empty_line(self):
		buffer_ = self.tv.get_buffer()
		end_iter = buffer_.get_end_iter()
		buffer_.insert_with_tags_by_name(end_iter, '\n', 'eol')

	def print_conversation_line(self, text, jid, kind, name, tim,
	other_tags_for_name=[], other_tags_for_time=[], other_tags_for_text=[],
	subject=None, old_kind=None, xhtml=None, simple=False, graphics=True):
		'''prints 'chat' type messages'''
		buffer_ = self.tv.get_buffer()
		buffer_.begin_user_action()
		if self.marks_queue.full():
			# remove oldest line
			m1 = self.marks_queue.get()
			m2 = self.marks_queue.get()
			i1 = buffer_.get_iter_at_mark(m1)
			i2 = buffer_.get_iter_at_mark(m2)
			buffer_.delete(i1, i2)
			buffer_.delete_mark(m1)
		end_iter = buffer_.get_end_iter()
		end_offset = end_iter.get_offset()
		at_the_end = self.at_the_end()
		move_selection = False
		if buffer_.get_has_selection() and buffer_.get_selection_bounds()[1].\
		get_offset() == end_offset:
			move_selection = True

		# Create one mark and add it to queue once if it's the first line
		# else twice (one for end bound, one for start bound)
		mark = None
		if buffer_.get_char_count() > 0:
			if not simple:
				buffer_.insert_with_tags_by_name(end_iter, '\n', 'eol')
				if move_selection:
					sel_start, sel_end = buffer_.get_selection_bounds()
					sel_end.backward_char()
					buffer_.select_range(sel_start, sel_end)
			mark = buffer_.create_mark(None, end_iter, left_gravity=True)
			self.marks_queue.put(mark)
		if not mark:
			mark = buffer_.create_mark(None, end_iter, left_gravity=True)
		self.marks_queue.put(mark)
		if kind == 'incoming_queue':
			kind = 'incoming'
		if old_kind == 'incoming_queue':
			old_kind = 'incoming'
		# print the time stamp
		if not tim:
			# We don't have tim for outgoing messages...
			tim = time.localtime()
		current_print_time = gajim.config.get('print_time')
		if current_print_time == 'always' and kind != 'info' and not simple:
			timestamp_str = self.get_time_to_show(tim)
			timestamp = time.strftime(timestamp_str, tim)
			buffer_.insert_with_tags_by_name(end_iter, timestamp,
				*other_tags_for_time)
		elif current_print_time == 'sometimes' and kind != 'info' and not simple:
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = time.mktime(tim) - self.last_time_printout
			if seconds_passed > every_foo_seconds:
				self.last_time_printout = time.mktime(tim)
				end_iter = buffer_.get_end_iter()
				if gajim.config.get('print_time_fuzzy') > 0:
					ft = self.fc.fuzzy_time(gajim.config.get('print_time_fuzzy'), tim)
					tim_format = ft.decode(locale.getpreferredencoding())
				else:
					tim_format = self.get_time_to_show(tim)
				buffer_.insert_with_tags_by_name(end_iter, tim_format + '\n',
					'time_sometimes')
		# kind = info, we print things as if it was a status: same color, ...
		if kind in ('error', 'info'):
			kind = 'status'
		other_text_tag = self.detect_other_text_tag(text, kind)
		text_tags = other_tags_for_text[:] # create a new list
		if other_text_tag:
			# note that color of /me may be overwritten in gc_control
			text_tags.append(other_text_tag)
		else: # not status nor /me
			if gajim.config.get('chat_merge_consecutive_nickname'):
				if kind != old_kind:
					self.print_name(name, kind, other_tags_for_name)
				else:
					self.print_real_text(gajim.config.get(
						'chat_merge_consecutive_nickname_indent'))
			else:
				self.print_name(name, kind, other_tags_for_name)
			if kind == 'incoming':
				text_tags.append('incomingtxt')
			elif kind == 'outgoing':
				text_tags.append('outgoingtxt')
		self.print_subject(subject)
		self.print_real_text(text, text_tags, name, xhtml, graphics=graphics)

		# scroll to the end of the textview
		if at_the_end or kind == 'outgoing':
			# we are at the end or we are sending something
			# scroll to the end (via idle in case the scrollbar has appeared)
			if gajim.config.get('use_smooth_scrolling'):
				gobject.idle_add(self.smooth_scroll_to_end)
			else:
				gobject.idle_add(self.scroll_to_end)

		buffer_.end_user_action()

	def get_time_to_show(self, tim):
		'''Get the time, with the day before if needed and return it.
		It DOESN'T format a fuzzy time'''
		format = ''
		# get difference in days since epoch (86400 = 24*3600)
		# number of days since epoch for current time (in GMT) -
		# number of days since epoch for message (in GMT)
		diff_day = int(timegm(time.localtime())) / 86400 -\
			int(timegm(tim)) / 86400
		if diff_day == 0:
			day_str = ''
		else:
			#%i is day in year (1-365)
			day_str = i18n.ngettext('Yesterday', '%i days ago', diff_day,
				replace_plural=diff_day)
		if day_str:
			format += day_str + ' '
		timestamp_str = gajim.config.get('time_stamp')
		timestamp_str = helpers.from_one_line(timestamp_str)
		format += timestamp_str
		tim_format = time.strftime(format, tim)
		if locale.getpreferredencoding() != 'KOI8-R':
			# if tim_format comes as unicode because of day_str.
			# we convert it to the encoding that we want (and that is utf-8)
			tim_format = helpers.ensure_utf8_string(tim_format)
		return tim_format

	def detect_other_text_tag(self, text, kind):
		if kind == 'status':
			return kind
		elif text.startswith('/me ') or text.startswith('/me\n'):
			return kind

	def print_name(self, name, kind, other_tags_for_name):
		if name:
			buffer_ = self.tv.get_buffer()
			end_iter = buffer_.get_end_iter()
			name_tags = other_tags_for_name[:] # create a new list
			name_tags.append(kind)
			before_str = gajim.config.get('before_nickname')
			before_str = helpers.from_one_line(before_str)
			after_str = gajim.config.get('after_nickname')
			after_str = helpers.from_one_line(after_str)
			format = before_str + name + after_str + ' '
			buffer_.insert_with_tags_by_name(end_iter, format, *name_tags)

	def print_subject(self, subject):
		if subject: # if we have subject, show it too!
			subject = _('Subject: %s\n') % subject
			buffer_ = self.tv.get_buffer()
			end_iter = buffer_.get_end_iter()
			buffer_.insert(end_iter, subject)
			self.print_empty_line()

	def print_real_text(self, text, text_tags=[], name=None, xhtml=None,
	graphics=True):
		'''this adds normal and special text. call this to add text'''
		if xhtml:
			try:
				if name and (text.startswith('/me ') or text.startswith('/me\n')):
					xhtml = xhtml.replace('/me', '<i>* %s</i>' % (name,), 1)
				self.tv.display_html(xhtml.encode('utf-8'), self)
				return
			except Exception, e:
				gajim.log.debug('Error processing xhtml' + str(e))
				gajim.log.debug('with |' + xhtml + '|')

		# /me is replaced by name if name is given
		if name and (text.startswith('/me ') or text.startswith('/me\n')):
			text = '* ' + name + text[3:]
			text_tags.append('italic')
		# detect urls formatting and if the user has it on emoticons
		self.detect_and_print_special_text(text, text_tags, graphics=graphics)

# vim: se ts=3:
