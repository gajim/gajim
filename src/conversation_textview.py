# -*- coding:utf-8 -*-
## src/conversation_textview.py
##
## Copyright (C) 2005 Norman Rasmussen <norman AT rasmussen.co.za>
## Copyright (C) 2005-2006 Alex Mauer <hawke AT hawkesnest.net>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
import time
import os
import tooltips
import dialogs
import locale
import queue
import urllib

import gtkgui_helpers
from common import gajim
from common import helpers
from common import i18n
from calendar import timegm
from common.fuzzyclock import FuzzyClock

from htmltextview import HtmlTextView
from common.exceptions import GajimGeneralException
from encodings.punycode import punycode_encode as puny_encode

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
    return widget.get_state_flags() & Gtk.StateFlags.FOCUSED == \
        Gtk.StateFlags.FOCUSED

class TextViewImage(Gtk.Image):

    def __init__(self, anchor, text):
        super(TextViewImage, self).__init__()
        self.anchor = anchor
        self._selected = False
        self._disconnect_funcs = []
        self.connect('parent-set', self.on_parent_set)
        self.connect('draw', self.on_expose)
        self.set_tooltip_markup(text)
        self.anchor.plaintext = text

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
            return Gtk.StateType.NORMAL
        if self._selected:
            if has_focus(parent):
                return Gtk.StateType.SELECTED
            else:
                return Gtk.StateType.ACTIVE
        else:
            return Gtk.StateType.NORMAL

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
        if state != Gtk.StateType.NORMAL:
            gc = widget.get_style().base_gc[state]
            area = widget.allocation
            widget.get_window(Gtk.TextWindowType.TEXT).draw_rectangle(gc, True,
                area.x, area.y, area.width, area.height)
        return False


class ConversationTextview(GObject.GObject):
    """
    Class for the conversation textview (where user reads already said messages)
    for chat/groupchat windows
    """
    __gsignals__ = dict(
            quote = (GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
                    None, # return value
                    (str, ) # arguments
            )
    )

    MESSAGE_CORRECTED_PIXBUF = gtkgui_helpers.get_icon_pixmap('gtk-spell-check')

    # smooth scroll constants
    MAX_SCROLL_TIME = 0.4 # seconds
    SCROLL_DELAY = 33 # milliseconds

    def __init__(self, account, used_in_history_window = False):
        """
        If used_in_history_window is True, then we do not show Clear menuitem in
        context menu
        """
        GObject.GObject.__init__(self)
        self.used_in_history_window = used_in_history_window

        self.fc = FuzzyClock()


        # no need to inherit TextView, use it as atrribute is safer
        self.tv = HtmlTextView()
        self.tv.hyperlink_handler = self.hyperlink_handler

        # set properties
        self.tv.set_border_width(1)
        self.tv.set_accepts_tab(True)
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.set_left_margin(2)
        self.tv.set_right_margin(2)
        self.handlers = {}
        self.images = []
        self.image_cache = {}
        self.xep0184_marks = {}
        self.xep0184_shown = {}
        self.last_sent_message_marks = [None, None]
        # A pair per occupant. Key is '' in normal chat
        self.last_received_message_marks = {}

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

        id_ = self.tv.connect('draw', self.on_textview_draw)
        self.handlers[id_] = self.tv


        self.account = account
        self.change_cursor = False
        self.last_time_printout = 0

        font = Pango.FontDescription(gajim.config.get('conversation_font'))
        self.tv.override_font(font)
        buffer_ = self.tv.get_buffer()
        end_iter = buffer_.get_end_iter()
        buffer_.create_mark('end', end_iter, False)

        self.tagIn = buffer_.create_tag('incoming')
        color = gajim.config.get('inmsgcolor')
        font = Pango.FontDescription(gajim.config.get('inmsgfont'))
        self.tagIn.set_property('foreground', color)
        self.tagIn.set_property('font-desc', font)

        self.tagOut = buffer_.create_tag('outgoing')
        color = gajim.config.get('outmsgcolor')
        font = Pango.FontDescription(gajim.config.get('outmsgfont'))
        self.tagOut.set_property('foreground', color)
        self.tagOut.set_property('font-desc', font)

        self.tagStatus = buffer_.create_tag('status')
        color = gajim.config.get('statusmsgcolor')
        font = Pango.FontDescription(gajim.config.get('satusmsgfont'))
        self.tagStatus.set_property('foreground', color)
        self.tagStatus.set_property('font-desc', font)

        self.tagInText = buffer_.create_tag('incomingtxt')
        color = gajim.config.get('inmsgtxtcolor')
        font = Pango.FontDescription(gajim.config.get('inmsgtxtfont'))
        if color:
            self.tagInText.set_property('foreground', color)
        self.tagInText.set_property('font-desc', font)

        self.tagOutText = buffer_.create_tag('outgoingtxt')
        color = gajim.config.get('outmsgtxtcolor')
        if color:
            font = Pango.FontDescription(gajim.config.get('outmsgtxtfont'))
        self.tagOutText.set_property('foreground', color)
        self.tagOutText.set_property('font-desc', font)

        colors = gajim.config.get('gc_nicknames_colors')
        colors = colors.split(':')
        for i, color in enumerate(colors):
            tagname = 'gc_nickname_color_' + str(i)
            tag = buffer_.create_tag(tagname)
            tag.set_property('foreground', color)

        self.tagMarked = buffer_.create_tag('marked')
        color = gajim.config.get('markedmsgcolor')
        self.tagMarked.set_property('foreground', color)
        self.tagMarked.set_property('weight', Pango.Weight.BOLD)

        tag = buffer_.create_tag('time_sometimes')
        tag.set_property('foreground', 'darkgrey')
        #Pango.SCALE_SMALL
        tag.set_property('scale', 0.8333333333333)
        tag.set_property('justification', Gtk.Justification.CENTER)

        tag = buffer_.create_tag('small')
        #Pango.SCALE_SMALL
        tag.set_property('scale', 0.8333333333333)

        tag = buffer_.create_tag('restored_message')
        color = gajim.config.get('restored_messages_color')
        tag.set_property('foreground', color)

        self.tv.create_tags()
        
        tag = buffer_.create_tag('bold')
        tag.set_property('weight', Pango.Weight.BOLD)

        tag = buffer_.create_tag('italic')
        tag.set_property('style', Pango.Style.ITALIC)

        tag = buffer_.create_tag('underline')
        tag.set_property('underline', Pango.Underline.SINGLE)

        buffer_.create_tag('focus-out-line', justification = Gtk.Justification.CENTER)
        self.displaymarking_tags = {}

        tag = buffer_.create_tag('xep0184-warning')
        tag.set_property('foreground', '#cc0000')

        tag = buffer_.create_tag('xep0184-received')
        tag.set_property('foreground', '#73d216')

        # One mark at the begining then 2 marks between each lines
        size = gajim.config.get('max_conversation_lines')
        size = 2 * size - 1
        self.marks_queue = queue.Queue(size)

        self.allow_focus_out_line = True
        # holds a mark at the end of --- line
        self.focus_out_end_mark = None

        self.xep0184_warning_tooltip = tooltips.BaseTooltip()

        self.line_tooltip = tooltips.BaseTooltip()
        self.smooth_id = None
        self.just_cleared = False

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
        self.tagMarked.set_property('foreground',
            gajim.config.get('markedmsgcolor'))
        color = gajim.config.get('urlmsgcolor')
        self.tv.tagURL.set_property('foreground', color)
        self.tv.tagMail.set_property('foreground', color)
        self.tv.tagXMPP.set_property('foreground', color)
        self.tv.tagSthAtSth.set_property('foreground', color)

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
        max_val = vadj.get_upper() - vadj.get_page_size() + 1
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
        GLib.idle_add(self.do_smooth_scroll_timeout)
        return

    def do_smooth_scroll_timeout(self):
        if not self.smooth_id:
            # we finished scrolling
            return
        GLib.source_remove(self.smooth_id)
        self.smooth_id = None
        parent = self.tv.get_parent()
        if parent:
            vadj = parent.get_vadjustment()
            self.auto_scrolling = True
            vadj.set_value(vadj.get_upper() - vadj.get_page_size() + 1)
            self.auto_scrolling = False

    def smooth_scroll_to_end(self):
        if None != self.smooth_id: # already scrolling
            return False
        self.smooth_id = GLib.timeout_add(self.SCROLL_DELAY,
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
                GLib.idle_add(self.smooth_scroll_to_end)
            else:
                GLib.idle_add(self.scroll_to_end_iter)

    def scroll_to_end_iter(self):
        buffer_ = self.tv.get_buffer()
        end_iter = buffer_.get_end_iter()
        if not end_iter:
            return False
        self.tv.scroll_to_iter(end_iter, 0, False, 1, 1)
        return False # when called in an idle_add, just do it once

    def stop_scrolling(self):
        if self.smooth_id:
            GLib.source_remove(self.smooth_id)
            self.smooth_id = None
            self.smooth_scroll_timer.cancel()

    def show_corrected_message_warning(self, iter_, text=''):
        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()
        buffer_.insert(iter_, ' ')
        anchor = buffer_.create_child_anchor(iter_)
        img = TextViewImage(anchor, text)
        img.set_from_pixbuf(ConversationTextview.MESSAGE_CORRECTED_PIXBUF)
        img.show()
        self.tv.add_child_at_anchor(img, anchor)
        buffer_.end_user_action()

    def correct_last_sent_message(self, message, xhtml, name, old_txt):
        m1 = self.last_sent_message_marks[0]
        m2 = self.last_sent_message_marks[1]
        buffer_ = self.tv.get_buffer()
        i1 = buffer_.get_iter_at_mark(m1)
        i2 = buffer_.get_iter_at_mark(m2)
        txt = buffer_.get_text(i1, i2, True)
        buffer_.delete(i1, i2)
        tag = 'outgoingtxt'
        if message.startswith('/me'):
            tag = 'outgoing'
        i2 = self.print_conversation_line(message, '', 'outgoing', name, None,
            xhtml=xhtml, iter_=i1)
        tt_txt = _('<b>Message was corrected. Last message was:</b>\n  %s') % \
            GLib.markup_escape_text(old_txt)
        self.show_corrected_message_warning(i2, tt_txt)
        self.last_sent_message_marks[1] = buffer_.create_mark(None, i2,
            left_gravity=True)

    def correct_last_received_message(self, message, xhtml, name, old_txt,
    other_tags_for_name=[], other_tags_for_text=[]):
        if name not in self.last_received_message_marks:
            return
        m1 = self.last_received_message_marks[name][0]
        m2 = self.last_received_message_marks[name][1]
        buffer_ = self.tv.get_buffer()
        i1 = buffer_.get_iter_at_mark(m1)
        i2 = buffer_.get_iter_at_mark(m2)
        txt = buffer_.get_text(i1, i2, True)
        buffer_.delete(i1, i2)
        i2 = self.print_conversation_line(message, '', 'incoming', name, None,
            other_tags_for_name=other_tags_for_name,
            other_tags_for_text=other_tags_for_text, xhtml=xhtml, iter_=i1)
        tt_txt = _('<b>Message was corrected. Last message was:</b>\n  %s') % \
            GLib.markup_escape_text(old_txt)
        self.show_corrected_message_warning(i2, tt_txt)
        self.last_received_message_marks[name][1] = buffer_.create_mark(None, i2,
            left_gravity=True)

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

            end_iter = buffer_.get_iter_at_mark(self.xep0184_marks[id_])
            buffer_.insert_with_tags_by_name(end_iter, ' ✖', 'xep0184-warning')

            self.xep0184_shown[id_] = SHOWN
            return False
        GLib.timeout_add_seconds(3, show_it)

        buffer_.end_user_action()

    def hide_xep0184_warning(self, id_):
        if id_ not in self.xep0184_marks:
            return

        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()

        if self.xep0184_shown[id_] != NOT_SHOWN:
            begin_iter = buffer_.get_iter_at_mark(self.xep0184_marks[id_])

            end_iter = begin_iter.copy()
            # XXX: Is there a nicer way?
            end_iter.forward_char()
            end_iter.forward_char()

            buffer_.delete(begin_iter, end_iter)

        if gajim.config.get('positive_184_ack'):
            begin_iter = buffer_.get_iter_at_mark(self.xep0184_marks[id_])
            buffer_.insert_with_tags_by_name(begin_iter, ' ✓',
                'xep0184-received')

        self.xep0184_shown[id_] = ALREADY_RECEIVED

        buffer_.end_user_action()

        del self.xep0184_marks[id_]
        del self.xep0184_shown[id_]

    def show_focus_out_line(self, scroll=True):
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
                begin_iter_for_previous_line.backward_chars(21)

                # remove focus out line
                buffer_.delete(begin_iter_for_previous_line,
                        end_iter_for_previous_line)
                buffer_.delete_mark(self.focus_out_end_mark)

            # add the new focus out line
            end_iter = buffer_.get_end_iter()
            buffer_.insert(end_iter, '\n' + '―' * 20)

            end_iter = buffer_.get_end_iter()
            before_img_iter = end_iter.copy()
            # one char back (an image also takes one char)
            before_img_iter.backward_chars(20)
            buffer_.apply_tag_by_name('focus-out-line', before_img_iter, end_iter)

            self.allow_focus_out_line = False

            # update the iter we hold to make comparison the next time
            self.focus_out_end_mark = buffer_.create_mark(None,
                    buffer_.get_end_iter(), left_gravity=True)

            buffer_.end_user_action()

            if scroll:
                # scroll to the end (via idle in case the scrollbar has
                # appeared)
                GLib.idle_add(self.scroll_to_end)

    def show_xep0184_warning_tooltip(self):
        w = self.tv.get_window(Gtk.TextWindowType.TEXT)
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        x = pointer[1]
        y = pointer[2]
        tags = self.tv.get_iter_at_location(x, y).get_tags()
        tag_table = self.tv.get_buffer().get_tag_table()
        xep0184_warning = False
        for tag in tags:
            if tag == tag_table.lookup('xep0184-warning'):
                xep0184_warning = True
                break
        if xep0184_warning and not self.xep0184_warning_tooltip.win:
            # check if the current pointer is still over the line
            position = w.get_origin()[1:]
            self.xep0184_warning_tooltip.show_tooltip(_('This icon indicates '
                'that this message has not yet\nbeen received by the remote '
                "end. If this icon stays\nfor a long time, it's likely the "
                'message got lost.'), 8, position[1] + y)

    def show_line_tooltip(self):
        w = self.tv.get_window(Gtk.TextWindowType.TEXT)
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        x = pointer[1]
        y = pointer[2]
        tags = self.tv.get_iter_at_location(x, y).get_tags()
        tag_table = self.tv.get_buffer().get_tag_table()
        over_line = False
        for tag in tags:
            if tag == tag_table.lookup('focus-out-line'):
                over_line = True
                break
        if over_line and not self.line_tooltip.win:
            # check if the current pointer is still over the line
            position = w.get_origin()[1:]
            self.line_tooltip.show_tooltip(_('Text below this line is what has '
                'been said since the\nlast time you paid attention to this '
                'group chat'), 8, position[1] + y)

    def on_textview_draw(self, widget, ctx):
        return
        #TODO
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
        """
        Change the cursor to a hand when we are over a mail or an url
        """
        w = self.tv.get_window(Gtk.TextWindowType.TEXT)
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        x, y = self.tv.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
            pointer[1], pointer[2])
        tags = self.tv.get_iter_at_location(x, y).get_tags()
        if self.change_cursor:
            w.set_cursor(Gdk.Cursor.new(Gdk.CursorType.XTERM))
            self.change_cursor = False
        tag_table = self.tv.get_buffer().get_tag_table()
        over_line = False
        xep0184_warning = False

        for tag in tags:
            if tag in (tag_table.lookup('url'), tag_table.lookup('mail'), \
            tag_table.lookup('xmpp'), tag_table.lookup('sth_at_sth')):
                w.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))
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
            self.line_tooltip.timeout = GLib.timeout_add(500,
                    self.show_line_tooltip)
            w.set_cursor(Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR))
            self.change_cursor = True
        if xep0184_warning and not self.xep0184_warning_tooltip.win:
            self.xep0184_warning_tooltip.timeout = GLib.timeout_add(500,
                    self.show_xep0184_warning_tooltip)
            w.set_cursor(Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR))
            self.change_cursor = True

    def clear(self, tv = None):
        """
        Clear text in the textview
        """
        buffer_ = self.tv.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)
        size = gajim.config.get('max_conversation_lines')
        size = 2 * size - 1
        self.marks_queue = queue.Queue(size)
        self.focus_out_end_mark = None
        self.just_cleared = True

    def visit_url_from_menuitem(self, widget, link):
        """
        Basically it filters out the widget instance
        """
        helpers.launch_browser_mailer('url', link)

    def on_textview_populate_popup(self, textview, menu):
        """
        Override the default context menu and we prepend Clear (only if
        used_in_history_window is False) and if we have sth selected we show a
        submenu with actions on the phrase (see
        on_conversation_textview_button_press_event)
        """
        separator_menuitem_was_added = False
        if not self.used_in_history_window:
            item = Gtk.SeparatorMenuItem.new()
            menu.prepend(item)
            separator_menuitem_was_added = True

            item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_CLEAR, None)
            menu.prepend(item)
            id_ = item.connect('activate', self.clear)
            self.handlers[id_] = item

        if self.selected_phrase:
            if not separator_menuitem_was_added:
                item = Gtk.SeparatorMenuItem.new()
                menu.prepend(item)

            if not self.used_in_history_window:
                item = Gtk.MenuItem.new_with_mnemonic(_('_Quote'))
                id_ = item.connect('activate', self.on_quote)
                self.handlers[id_] = item
                menu.prepend(item)

            _selected_phrase = helpers.reduce_chars_newlines(
                    self.selected_phrase, 25, 2)
            item = Gtk.MenuItem.new_with_mnemonic(
                _('_Actions for "%s"') % _selected_phrase)
            menu.prepend(item)
            submenu = Gtk.Menu()
            item.set_submenu(submenu)
            phrase_for_url = urllib.parse.quote(self.selected_phrase.encode(
                'utf-8'))

            always_use_en = gajim.config.get('always_english_wikipedia')
            if always_use_en:
                link = 'http://en.wikipedia.org/wiki/Special:Search?search=%s'\
                        % phrase_for_url
            else:
                link = 'http://%s.wikipedia.org/wiki/Special:Search?search=%s'\
                        % (gajim.LANG, phrase_for_url)
            item = Gtk.MenuItem.new_with_mnemonic(_('Read _Wikipedia Article'))
            id_ = item.connect('activate', self.visit_url_from_menuitem, link)
            self.handlers[id_] = item
            submenu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('Look it up in _Dictionary'))
            dict_link = gajim.config.get('dictionary_url')
            if dict_link == 'WIKTIONARY':
                # special link (yeah undocumented but default)
                always_use_en = gajim.config.get('always_english_wiktionary')
                if always_use_en:
                    link = 'http://en.wiktionary.org/wiki/Special:Search?search=%s'\
                            % phrase_for_url
                else:
                    link = 'http://%s.wiktionary.org/wiki/Special:Search?search=%s'\
                            % (gajim.LANG, phrase_for_url)
                id_ = item.connect('activate', self.visit_url_from_menuitem, link)
                self.handlers[id_] = item
            else:
                if dict_link.find('%s') == -1:
                    # we must have %s in the url if not WIKTIONARY
                    item = Gtk.MenuItem(_(
                            'Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
                    item.set_property('sensitive', False)
                else:
                    link = dict_link % phrase_for_url
                    id_ = item.connect('activate', self.visit_url_from_menuitem,
                            link)
                    self.handlers[id_] = item
            submenu.append(item)


            search_link = gajim.config.get('search_engine')
            if search_link.find('%s') == -1:
                # we must have %s in the url
                item = Gtk.MenuItem(_('Web Search URL is missing an "%s"'))
                item.set_property('sensitive', False)
            else:
                item = Gtk.MenuItem.new_with_mnemonic(_('Web _Search for it'))
                link =  search_link % phrase_for_url
                id_ = item.connect('activate', self.visit_url_from_menuitem, link)
                self.handlers[id_] = item
            submenu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('Open as _Link'))
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

        x, y = self.tv.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
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
            self.selected_phrase = buffer_.get_text(start_sel, finish_sel, True)
        elif iter_.get_char() and ord(iter_.get_char()) > 31:
            # we clicked on a word, do as if it's selected for context menu
            start_sel = iter_.copy()
            if not start_sel.starts_word():
                start_sel.backward_word_start()
            finish_sel = iter_.copy()
            if not finish_sel.ends_word():
                finish_sel.forward_word_end()
            self.selected_phrase = buffer_.get_text(start_sel, finish_sel, True)

    def on_open_link_activate(self, widget, kind, text):
        helpers.launch_browser_mailer(kind, text)

    def on_copy_link_activate(self, widget, text):
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(text, -1)

    def on_start_chat_activate(self, widget, jid):
        gajim.interface.new_chat_from_jid(self.account, jid)

    def on_join_group_chat_menuitem_activate(self, widget, room_jid):
        if 'join_gc' in gajim.interface.instances[self.account]:
            instance = gajim.interface.instances[self.account]['join_gc']
            instance.xml.get_object('room_jid_entry').set_text(room_jid)
            gajim.interface.instances[self.account]['join_gc'].window.present()
        else:
            try:
                dialogs.JoinGroupchatWindow(account=self.account, room_jid=room_jid)
            except GajimGeneralException:
                pass

    def on_add_to_roster_activate(self, widget, jid):
        dialogs.AddNewContactWindow(self.account, jid)

    def make_link_menu(self, event, kind, text):
        xml = gtkgui_helpers.get_gtk_builder('chat_context_menu.ui')
        menu = xml.get_object('chat_context_menu')
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
            join_group_chat_menuitem = xml.get_object('join_group_chat_menuitem')
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

            if self.account and gajim.connections[self.account].\
            roster_supported:
                id_ = childs[7].connect('activate',
                    self.on_add_to_roster_activate, text)
                self.handlers[id_] = childs[7]
                childs[7].show() # show add to roster menuitem
            else:
                childs[7].hide() # hide add to roster menuitem

            if kind == 'xmpp':
                id_ = childs[0].connect('activate', self.on_copy_link_activate,
                    'xmpp:' + text)
                self.handlers[id_] = childs[0]
                childs[2].hide() # copy mail address
                childs[3].hide() # open mail composer
                childs[4].hide() # jid section separator
            elif kind == 'mail':
                childs[4].hide() # jid section separator
                childs[5].hide() # start chat
                childs[6].hide() # join group chat
                childs[7].hide() # add to roster

            if kind != 'xmpp':
                childs[0].hide() # copy link location
            childs[1].hide() # open link in browser

        menu.attach_to_widget(self.tv, None)
        menu.popup(None, None, None, None, event.button.button, event.time)

    def hyperlink_handler(self, texttag, widget, event, iter_, kind):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            begin_iter = iter_.copy()
            # we get the begining of the tag
            while not begin_iter.begins_tag(texttag):
                begin_iter.backward_char()
            end_iter = iter_.copy()
            # we get the end of the tag
            while not end_iter.ends_tag(texttag):
                end_iter.forward_char()

            # Detect XHTML-IM link
            word = getattr(texttag, 'href', None)
            if word:
                if word.startswith('xmpp'):
                    kind = 'xmpp'
                elif word.startswith('mailto:'):
                    kind = 'mail'
                elif gajim.interface.sth_at_sth_dot_sth_re.match(word):
                    # it's a JID or mail
                    kind = 'sth_at_sth'
            else:
                word = self.tv.get_buffer().get_text(begin_iter, end_iter, True)
            if event.button.button == 3: # right click
                self.make_link_menu(event, kind, word)
                return True
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

    def detect_and_print_special_text(self, otext, other_tags, graphics=True,
    iter_=None):
        """
        Detect special text (emots & links & formatting), print normal text
        before any special text it founds, then print special text (that happens
        many times until last special text is printed) and then return the index
        after *last* special text, so we can print it in
        print_conversation_line()
        """
        if not otext:
            return
        buffer_ = self.tv.get_buffer()
        if other_tags:
            insert_tags_func = buffer_.insert_with_tags_by_name
        else:
            insert_tags_func = buffer_.insert
        # detect_and_print_special_text() is also used by
        # HtmlHandler.handle_specials() and there tags is Gtk.TextTag objects,
        # not strings
        if other_tags and isinstance(other_tags[0], Gtk.TextTag):
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
        if iter_:
            end_iter = iter_
        else:
            end_iter = buffer_.get_end_iter()
        for match in iterator:
            start, end = match.span()
            special_text = otext[start:end]
            if start > index:
                text_before_special_text = otext[index:start]
                if not iter_:
                    end_iter = buffer_.get_end_iter()
                # we insert normal text
                if other_tags:
                    insert_tags_func(end_iter, text_before_special_text, *other_tags)
                else:
                    buffer_.insert(end_iter, text_before_special_text)
            index = end # update index

            # now print it
            self.print_special_text(special_text, other_tags, graphics=graphics,
                iter_=end_iter)
            specials_limit -= 1
            if specials_limit <= 0:
                break

        # add the rest of text located in the index and after
        insert_tags_func(end_iter, otext[index:], *other_tags)

        return end_iter

    def print_special_text(self, special_text, other_tags, graphics=True,
    iter_=None):
        """
        Is called by detect_and_print_special_text and prints special text
        (emots, links, formatting)
        """


        # PluginSystem: adding GUI extension point for ConversationTextview
        self.plugin_modified = False
        gajim.plugin_manager.gui_extension_point('print_special_text', self,
            special_text, other_tags, graphics)
        if self.plugin_modified:
            return

        tags = []
        use_other_tags = True
        text_is_valid_uri = False
        is_xhtml_link = None
        show_ascii_formatting_chars = \
            gajim.config.get('show_ascii_formatting_chars')
        buffer_ = self.tv.get_buffer()

        # Detect XHTML-IM link
        ttt = buffer_.get_tag_table()
        tags_ = [(ttt.lookup(t) if isinstance(t, str) else t) for t in other_tags]
        for t in tags_:
            is_xhtml_link = getattr(t, 'href', None)
            if is_xhtml_link:
                break

        # Check if we accept this as an uri
        schemes = gajim.config.get('uri_schemes').split()
        for scheme in schemes:
            if special_text.startswith(scheme):
                text_is_valid_uri = True

        possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
        if iter_:
            end_iter = iter_
        else:
            end_iter = buffer_.get_end_iter()
        if gajim.config.get('emoticons_theme') and \
        possible_emot_ascii_caps in gajim.interface.emoticons.keys() and graphics:
            # it's an emoticon
            emot_ascii = possible_emot_ascii_caps
            anchor = buffer_.create_child_anchor(end_iter)
            img = TextViewImage(anchor,
                GLib.markup_escape_text(special_text))
            animations = gajim.interface.emoticons_animations
            if not emot_ascii in animations:
                animations[emot_ascii] = GdkPixbuf.PixbufAnimation.new_from_file(
                    gajim.interface.emoticons[emot_ascii])
            img.set_from_animation(animations[emot_ascii])
            img.show()
            self.images.append(img)
            # add with possible animation
            self.tv.add_child_at_anchor(img, anchor)
        elif special_text.startswith('www.') or \
            special_text.startswith('ftp.') or \
            text_is_valid_uri and not is_xhtml_link:
                tags.append('url')
        elif special_text.startswith('mailto:') and not is_xhtml_link:
            tags.append('mail')
        elif special_text.startswith('xmpp:') and not is_xhtml_link:
            tags.append('xmpp')
        elif gajim.interface.sth_at_sth_dot_sth_re.match(special_text) and\
        not is_xhtml_link:
            # it's a JID or mail
            tags.append('sth_at_sth')
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
        else:
            # It's nothing special
            if use_other_tags:
                insert_tags_func = buffer_.insert_with_tags_by_name
                if other_tags and isinstance(other_tags[0], Gtk.TextTag):
                    insert_tags_func = buffer_.insert_with_tags
                if other_tags:
                    insert_tags_func(end_iter, special_text, *other_tags)
                else:
                    buffer_.insert(end_iter, special_text)

        if tags:
            all_tags = tags[:]
            if use_other_tags:
                all_tags += other_tags
            # convert all names to TextTag
            all_tags = [(ttt.lookup(t) if isinstance(t, str) else t) for t in all_tags]
            buffer_.insert_with_tags(end_iter, special_text, *all_tags)
            if 'url' in tags:
                puny_text = puny_encode(special_text).decode('utf-8')
                if not puny_text.endswith('-'):
                    puny_tags = []
                    if use_other_tags:
                        puny_tags += other_tags
                    puny_tags = [(ttt.lookup(t) if isinstance(t, str) else t) for t in puny_tags]
                    buffer_.insert_with_tags(end_iter, " (%s)" % puny_text, *puny_tags)

    def print_empty_line(self):
        buffer_ = self.tv.get_buffer()
        end_iter = buffer_.get_end_iter()
        buffer_.insert_with_tags_by_name(end_iter, '\n', 'eol')
        self.just_cleared = False

    def print_conversation_line(self, text, jid, kind, name, tim,
    other_tags_for_name=[], other_tags_for_time=[], other_tags_for_text=[],
    subject=None, old_kind=None, xhtml=None, simple=False, graphics=True,
    displaymarking=None, iter_=None):
        """
        Print 'chat' type messages
        """
        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()
        if iter_:
            temp_mark = buffer_.create_mark(None, iter_, left_gravity=True)
        if self.marks_queue.full():
            # remove oldest line
            m1 = self.marks_queue.get()
            m2 = self.marks_queue.get()
            i1 = buffer_.get_iter_at_mark(m1)
            i2 = buffer_.get_iter_at_mark(m2)
            buffer_.delete(i1, i2)
            buffer_.delete_mark(m1)
        if iter_:
            end_iter = buffer_.get_iter_at_mark(temp_mark)
            buffer_.delete_mark(temp_mark)
        else:
            end_iter = buffer_.get_end_iter()
        end_offset = end_iter.get_offset()
        at_the_end = self.at_the_end()
        move_selection = False
        if buffer_.get_has_selection() and buffer_.get_selection_bounds()[1].\
        get_offset() == end_offset:
            move_selection = True

        if not iter_:
            # Create one mark and add it to queue once if it's the first line
            # else twice (one for end bound, one for start bound)
            mark = None
            if buffer_.get_char_count() > 0:
                if not simple and not iter_:
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
        if text.startswith('/me '):
            direction_mark = i18n.paragraph_direction_mark(str(text[3:]))
        else:
            direction_mark = i18n.paragraph_direction_mark(text)
        # don't apply direction mark if it's status message
        if kind == 'status':
            direction_mark = i18n.direction_mark
        if current_print_time == 'always' and kind != 'info' and not simple:
            timestamp_str = self.get_time_to_show(tim, direction_mark)
            timestamp = time.strftime(timestamp_str, tim)
            timestamp = direction_mark + timestamp + direction_mark
            if other_tags_for_time:
                buffer_.insert_with_tags_by_name(end_iter, timestamp,
                    *other_tags_for_time)
            else:
                buffer_.insert (end_iter, timestamp)
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
                    tim_format = self.get_time_to_show(tim, direction_mark)
                buffer_.insert_with_tags_by_name(end_iter, tim_format + '\n',
                    'time_sometimes')
        # If there's a displaymarking, print it here.
        if displaymarking:
            self.print_displaymarking(displaymarking, iter_=end_iter)
        # kind = info, we print things as if it was a status: same color, ...
        if kind in ('error', 'info'):
            kind = 'status'
        other_text_tag = self.detect_other_text_tag(text, kind)
        text_tags = other_tags_for_text[:] # create a new list
        mark1 = None
        if other_text_tag:
            # note that color of /me may be overwritten in gc_control
            text_tags.append(other_text_tag)
            if text.startswith('/me') and not iter_:
                mark1 = mark
        else: # not status nor /me
            if gajim.config.get('chat_merge_consecutive_nickname'):
                if kind != old_kind or self.just_cleared:
                    self.print_name(name, kind, other_tags_for_name,
                        direction_mark=direction_mark, iter_=end_iter)
                else:
                    self.print_real_text(gajim.config.get(
                        'chat_merge_consecutive_nickname_indent'),
                        iter_=end_iter)
            else:
                self.print_name(name, kind, other_tags_for_name,
                    direction_mark=direction_mark, iter_=end_iter)
            if kind == 'incoming':
                text_tags.append('incomingtxt')
                if not iter_:
                    mark1 = mark
            elif kind == 'outgoing':
                text_tags.append('outgoingtxt')
                if not iter_:
                    mark1 = mark
        self.print_subject(subject, iter_=end_iter)
        self.print_real_text(text, text_tags, name, xhtml, graphics=graphics,
            iter_=end_iter)
        if not iter_ and mark1:
            mark2 = buffer_.create_mark(None, buffer_.get_end_iter(),
                left_gravity=True)
            if kind == 'incoming':
                if name in self.last_received_message_marks:
                    m = self.last_received_message_marks[name][1]
                    buffer_.delete_mark(m)
                self.last_received_message_marks[name] = [mark1, mark2]
            elif kind == 'outgoing':
                m = self.last_sent_message_marks[1]
                if m:
                    buffer_.delete_mark(m)
                self.last_sent_message_marks = [mark1, mark2]
        # scroll to the end of the textview
        if at_the_end or kind == 'outgoing':
            # we are at the end or we are sending something
            # scroll to the end (via idle in case the scrollbar has appeared)
            if gajim.config.get('use_smooth_scrolling'):
                GLib.idle_add(self.smooth_scroll_to_end)
            else:
                GLib.idle_add(self.scroll_to_end)

        self.just_cleared = False
        buffer_.end_user_action()
        return end_iter

    def get_time_to_show(self, tim, direction_mark=''):
        """
        Get the time, with the day before if needed and return it. It DOESN'T
        format a fuzzy time
        """
        format_ = ''
        # get difference in days since epoch (86400 = 24*3600)
        # number of days since epoch for current time (in GMT) -
        # number of days since epoch for message (in GMT)
        diff_day = int(int(timegm(time.localtime())) / 86400 -\
                int(timegm(tim)) / 86400)
        if diff_day == 0.0:
            day_str = ''
        else:
            #%i is day in year (1-365)
            day_str = i18n.ngettext('Yesterday',
                '%(nb_days)i days ago', diff_day, {'nb_days': diff_day},
                {'nb_days': diff_day})
        if day_str:
            format_ += i18n.direction_mark + day_str + direction_mark + ' '
        timestamp_str = gajim.config.get('time_stamp')
        timestamp_str = helpers.from_one_line(timestamp_str)
        format_ += timestamp_str
        tim_format = time.strftime(format_, tim)
        return tim_format

    def detect_other_text_tag(self, text, kind):
        if kind == 'status':
            return kind
        elif text.startswith('/me ') or text.startswith('/me\n'):
            return kind

    def print_displaymarking(self, displaymarking, iter_=None):
        bgcolor = displaymarking.getAttr('bgcolor') or '#FFF'
        fgcolor = displaymarking.getAttr('fgcolor') or '#000'
        text = displaymarking.getData()
        if text:
            buffer_ = self.tv.get_buffer()
            if iter_:
                end_iter = iter_
            else:
                end_iter = buffer_.get_end_iter()
            tag = self.displaymarking_tags.setdefault(bgcolor + '/' + fgcolor,
                buffer_.create_tag(None, background=bgcolor, foreground=fgcolor))
            buffer_.insert_with_tags(end_iter, '[' + text + ']', tag)
            end_iter = buffer_.get_end_iter()
            buffer_.insert_with_tags(end_iter, ' ')

    def print_name(self, name, kind, other_tags_for_name, direction_mark='',
    iter_=None):
        if name:
            buffer_ = self.tv.get_buffer()
            if iter_:
                end_iter = iter_
            else:
                end_iter = buffer_.get_end_iter()
            name_tags = other_tags_for_name[:] # create a new list
            name_tags.append(kind)
            before_str = gajim.config.get('before_nickname')
            before_str = helpers.from_one_line(before_str)
            after_str = gajim.config.get('after_nickname')
            after_str = helpers.from_one_line(after_str)
            format_ = before_str + name + direction_mark + after_str + ' '
            buffer_.insert_with_tags_by_name(end_iter, format_, *name_tags)

    def print_subject(self, subject, iter_=None):
        if subject: # if we have subject, show it too!
            subject = _('Subject: %s\n') % subject
            buffer_ = self.tv.get_buffer()
            if iter_:
                end_iter = iter_
            else:
                end_iter = buffer_.get_end_iter()
            buffer_.insert(end_iter, subject)
            self.print_empty_line()

    def print_real_text(self, text, text_tags=[], name=None, xhtml=None,
    graphics=True, iter_=None):
        """
        Add normal and special text. call this to add text
        """
        if xhtml:
            try:
                if name and (text.startswith('/me ') or text.startswith('/me\n')):
                    xhtml = xhtml.replace('/me', '<i>* %s</i>' % (name,), 1)
                self.tv.display_html(xhtml, self.tv, self, iter_=iter_)
                return
            except Exception as e:
                gajim.log.debug('Error processing xhtml: ' + str(e))
                gajim.log.debug('with |' + xhtml + '|')

        # /me is replaced by name if name is given
        if name and (text.startswith('/me ') or text.startswith('/me\n')):
            text = '* ' + name + text[3:]
            text_tags.append('italic')
        # detect urls formatting and if the user has it on emoticons
        return self.detect_and_print_special_text(text, text_tags, graphics=graphics,
            iter_=iter_)
