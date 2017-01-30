# -*- coding:utf-8 -*-
## src/message_textview.py
##
## Copyright (C) 2003-2017 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2008-2009 Julien Pivotto <roidelapluie AT gmail.com>
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

import gc

import gtk
import gobject
import pango

import gtkgui_helpers
from common import gajim

class MessageTextView(gtk.TextView):
    """
    Class for the message textview (where user writes new messages) for
    chat/groupchat windows
    """
    UNDO_LIMIT = 20
    __gsignals__ = dict(
            mykeypress = (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION,
                            None, # return value
                            (int, gtk.gdk.ModifierType ) # arguments
                    )
            )

    def __init__(self):
        gtk.TextView.__init__(self)

        # set properties
        self.set_border_width(1)
        self.set_accepts_tab(True)
        self.set_editable(True)
        self.set_cursor_visible(True)
        self.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        self.set_left_margin(2)
        self.set_right_margin(2)
        self.set_pixels_above_lines(2)
        self.set_pixels_below_lines(2)

        # set undo list
        self.undo_list = []
        # needed to know if we undid something
        self.undo_pressed = False
        self.lang = None # Lang used for spell checking
        _buffer = self.get_buffer()
        self.begin_tags = {}
        self.end_tags = {}
        self.color_tags = []
        self.fonts_tags = []
        self.other_tags = {}
        self.other_tags['bold'] = _buffer.create_tag('bold')
        self.other_tags['bold'].set_property('weight', pango.WEIGHT_BOLD)
        self.begin_tags['bold'] = '<strong>'
        self.end_tags['bold'] = '</strong>'
        self.other_tags['italic'] = _buffer.create_tag('italic')
        self.other_tags['italic'].set_property('style', pango.STYLE_ITALIC)
        self.begin_tags['italic'] = '<em>'
        self.end_tags['italic'] = '</em>'
        self.other_tags['underline'] = _buffer.create_tag('underline')
        self.other_tags['underline'].set_property('underline', pango.UNDERLINE_SINGLE)
        self.begin_tags['underline'] = '<span style="text-decoration: underline;">'
        self.end_tags['underline'] = '</span>'
        self.other_tags['strike'] = _buffer.create_tag('strike')
        self.other_tags['strike'].set_property('strikethrough', True)
        self.begin_tags['strike'] = '<span style="text-decoration: line-through;">'
        self.end_tags['strike'] = '</span>'

    def make_clickable_urls(self, text):
        _buffer = self.get_buffer()

        start = 0
        end = 0
        index = 0

        new_text = ''
        iterator = gajim.interface.link_pattern_re.finditer(text)
        for match in iterator:
            start, end = match.span()
            url = text[start:end]
            if start != 0:
                text_before_special_text = text[index:start]
            else:
                text_before_special_text = ''
            # we insert normal text
            new_text += text_before_special_text + \
            '<a href="'+ url +'">' + url + '</a>'

            index = end # update index

        if end < len(text):
            new_text += text[end:]

        return new_text # the position after *last* special text

    def get_active_tags(self):
        start, finish = self.get_active_iters()
        active_tags = []
        for tag in start.get_tags():
            active_tags.append(tag.get_property('name'))
        return active_tags

    def get_active_iters(self):
        _buffer = self.get_buffer()
        return_val = _buffer.get_selection_bounds()
        if return_val: # if sth was selected
            start, finish = return_val[0], return_val[1]
        else:
            start, finish = _buffer.get_bounds()
        return (start, finish)

    def set_tag(self, widget, tag):
        _buffer = self.get_buffer()
        start, finish = self.get_active_iters()
        if start.has_tag(self.other_tags[tag]):
            _buffer.remove_tag_by_name(tag, start, finish)
        else:
            if tag == 'underline':
                _buffer.remove_tag_by_name('strike', start, finish)
            elif tag == 'strike':
                _buffer.remove_tag_by_name('underline', start, finish)
            _buffer.apply_tag_by_name(tag, start, finish)

    def clear_tags(self, widget):
        _buffer = self.get_buffer()
        start, finish = self.get_active_iters()
        _buffer.remove_all_tags(start, finish)

    def color_set(self, widget, response, color):
        if response == -6:
            widget.destroy()
            return
        _buffer = self.get_buffer()
        color = color.get_current_color()
        widget.destroy()
        color_string = gtkgui_helpers.make_color_string(color)
        tag_name = 'color' + color_string
        if not tag_name in self.color_tags:
            tagColor = _buffer.create_tag(tag_name)
            tagColor.set_property('foreground', color_string)
            self.begin_tags[tag_name] = '<span style="color: ' + color_string + ';">'
            self.end_tags[tag_name] = '</span>'
            self.color_tags.append(tag_name)

        start, finish = self.get_active_iters()

        for tag in self.color_tags:
            _buffer.remove_tag_by_name(tag, start, finish)

        _buffer.apply_tag_by_name(tag_name, start, finish)

    def font_set(self, widget, response, font):
        if response == -6:
            widget.destroy()
            return

        _buffer = self.get_buffer()

        font = font.get_font_name()
        font_desc = pango.FontDescription(font)
        family = font_desc.get_family()
        size = font_desc.get_size()
        size = size / pango.SCALE
        weight = font_desc.get_weight()
        style = font_desc.get_style()

        widget.destroy()

        tag_name = 'font' + font
        if not tag_name in self.fonts_tags:
            tagFont = _buffer.create_tag(tag_name)
            tagFont.set_property('font', family + ' ' + str(size))
            self.begin_tags[tag_name] = \
                    '<span style="font-family: ' + family + '; ' + \
                    'font-size: ' + str(size) + 'px">'
            self.end_tags[tag_name] = '</span>'
            self.fonts_tags.append(tag_name)

        start, finish = self.get_active_iters()

        for tag in self.fonts_tags:
            _buffer.remove_tag_by_name(tag, start, finish)

        _buffer.apply_tag_by_name(tag_name, start, finish)

        if weight == pango.WEIGHT_BOLD:
            _buffer.apply_tag_by_name('bold', start, finish)
        else:
            _buffer.remove_tag_by_name('bold', start, finish)

        if style == pango.STYLE_ITALIC:
            _buffer.apply_tag_by_name('italic', start, finish)
        else:
            _buffer.remove_tag_by_name('italic', start, finish)

    def get_xhtml(self):
        _buffer = self.get_buffer()
        old = _buffer.get_start_iter()
        tags = {}
        tags['bold'] = False
        iter = _buffer.get_start_iter()
        old = _buffer.get_start_iter()
        text = ''
        modified = False

        def xhtml_special(text):
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('&', '&amp;')
            text = text.replace('\n', '<br />')
            return text

        for tag in iter.get_toggled_tags(True):
            tag_name = tag.get_property('name')
            if tag_name not in self.begin_tags:
                continue
            text += self.begin_tags[tag_name]
            modified = True
        while (iter.forward_to_tag_toggle(None) and not iter.is_end()):
            text += xhtml_special(_buffer.get_text(old, iter))
            old.forward_to_tag_toggle(None)
            new_tags, old_tags, end_tags = [], [], []
            for tag in iter.get_toggled_tags(True):
                tag_name = tag.get_property('name')
                if tag_name not in self.begin_tags:
                    continue
                new_tags.append(tag_name)
                modified = True

            for tag in iter.get_tags():
                tag_name = tag.get_property('name')
                if tag_name not in self.begin_tags or tag_name not in self.end_tags:
                    continue
                if tag_name not in new_tags:
                    old_tags.append(tag_name)

            for tag in iter.get_toggled_tags(False):
                tag_name = tag.get_property('name')
                if tag_name not in self.end_tags:
                    continue
                end_tags.append(tag_name)

            for tag in old_tags:
                text += self.end_tags[tag]
            for tag in end_tags:
                text += self.end_tags[tag]
            for tag in new_tags:
                text += self.begin_tags[tag]
            for tag in old_tags:
                text += self.begin_tags[tag]

        text += xhtml_special(_buffer.get_text(old, _buffer.get_end_iter()))
        for tag in iter.get_toggled_tags(False):
            tag_name = tag.get_property('name')
            if tag_name not in self.end_tags:
                continue
            text += self.end_tags[tag_name]

        if modified:
            return '<p>' + self.make_clickable_urls(text) + '</p>'
        else:
            return None

    def destroy(self):
        gobject.idle_add(gc.collect)

    def clear(self, widget = None):
        """
        Clear text in the textview
        """
        _buffer = self.get_buffer()
        start, end = _buffer.get_bounds()
        _buffer.delete(start, end)

    def save_undo(self, text):
        self.undo_list.append(text)
        if len(self.undo_list) > self.UNDO_LIMIT:
            del self.undo_list[0]
        self.undo_pressed = False

    def undo(self, widget=None):
        """
        Undo text in the textview
        """
        _buffer = self.get_buffer()
        if self.undo_list:
            _buffer.set_text(self.undo_list.pop())
        self.undo_pressed = True

    def get_sensitive(self):
        # get sensitive is not in GTK < 2.18
        try:
            return super(MessageTextView, self).get_sensitive()
        except AttributeError:
            return self.get_property('sensitive')

# We register depending on keysym and modifier some bindings
# but we also pass those as param so we can construct fake Event
# Here we register bindings for those combinations that there is NO DEFAULT
# action to be done by gtk TextView. In such case we should not add a binding
# as the default action comes first and our bindings is useless. In that case
# we catch and do stuff before default action in normal key_press_event
# and we also return True there to stop the default action from running

# CTRL + SHIFT + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.ISO_Left_Tab,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.ISO_Left_Tab,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Tab,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Tab,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Tab,
        0, 'mykeypress', int, gtk.keysyms.Tab,  gtk.gdk.ModifierType, 0)

# CTRL + UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Up,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Up,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Down,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Down,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + SHIFT + UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Up,
        gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK, 'mykeypress', int,
        gtk.keysyms.Up, gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK |
        gtk.gdk.SHIFT_MASK)

# CTRL + SHIFT + DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Down,
        gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK, 'mykeypress', int,
        gtk.keysyms.Down, gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK |
        gtk.gdk.SHIFT_MASK)

# ENTER
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return,
        0, 'mykeypress', int, gtk.keysyms.Return,
        gtk.gdk.ModifierType, 0)

# Ctrl + Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Return,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter,
        0, 'mykeypress', int, gtk.keysyms.KP_Enter,
        gtk.gdk.ModifierType, 0)

# Ctrl + Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.KP_Enter,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# Ctrl + z
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.z,
        gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.z,
        gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)
