# -*- coding:utf-8 -*-
#
# Copyright (C) 2017  Philipp Hörist <philipp AT hoerist.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import logging
import importlib.util as imp
from collections import OrderedDict
from importlib.machinery import SourceFileLoader

from gi.repository import GdkPixbuf, Gtk, GLib

MODIFIER_MAX_CHILDREN_PER_LINE = 6
MAX_CHILDREN_PER_LINE = 10
MIN_HEIGHT = 200

pixbufs = dict()
codepoints = dict()
popover_instance = None

log = logging.getLogger('gajim.emoticons')

class SubPixbuf:

    height = 24
    width = 24
    columns = 20

    def __init__(self, path):
        self.cur_column = 0
        self.src_x = 0
        self.src_y = 0
        self.atlas = GdkPixbuf.Pixbuf.new_from_file(path)

    def get_pixbuf(self):
        self.src_x = self.cur_column * self.width

        subpixbuf = self.atlas.new_subpixbuf(self.src_x, self.src_y, self.width, self.height)

        if self.cur_column == self.columns - 1:
            self.src_y += self.width
            self.cur_column = 0
        else:
            self.cur_column += 1

        return subpixbuf

def load(path):
    module_name = 'emoticons_theme.py'
    theme_path = os.path.join(path, module_name)
    if sys.platform == 'win32' and not os.path.exists(theme_path):
        module_name = 'emoticons_theme.pyc'
        theme_path = os.path.join(path, module_name)

    loader = SourceFileLoader(module_name, theme_path)
    try:
        theme = loader.load_module()
    except FileNotFoundError:
        log.exception('Emoticons theme not found')
        return

    if not theme.use_image:
        # Use Font to display emoticons
        set_popover(theme.emoticons, False)
        return True

    try:
        sub = SubPixbuf(os.path.join(path, 'emoticons.png'))
    except GLib.GError:
        log.exception('Error while creating subpixbuf')
        return False

    def add_emoticon(codepoint_, sub, mod_list=None):
        pix = sub.get_pixbuf()
        for alternate in codepoint_:
            codepoints[alternate.upper()] = pix
            if pix not in pixbufs:
                pixbufs[pix] = alternate.upper()
        if mod_list is not None:
            mod_list.append(pix)
        else:
            pixbuf_list.append(pix)

    popover_dict = OrderedDict()
    try:
        for category in theme.emoticons:
            if not theme.emoticons[category]:
                # Empty category
                continue

            pixbuf_list = []
            for filename, codepoint_ in theme.emoticons[category]:
                if codepoint_ is None:
                    # Category image
                    pixbuf_list.append(sub.get_pixbuf())
                    continue
                if not filename:
                    # We have an emoticon with a modifier
                    mod_list = []
                    for _, mod_codepoint in codepoint_:
                        add_emoticon(mod_codepoint, sub, mod_list)
                    pixbuf_list.append(mod_list)
                else:
                    add_emoticon(codepoint_, sub)

            popover_dict[category] = pixbuf_list

    except Exception:
        log.exception('Error while loading emoticon theme')
        return

    set_popover(popover_dict, True)

    return True

def set_popover(popover_dict, use_image):
    global popover_instance
    popover_instance = EmoticonPopover(popover_dict, use_image)

def get_popover():
    return popover_instance

def get_pixbuf(codepoint_):
    try:
        return codepoints[codepoint_]
    except KeyError:
        return None

def get_codepoint(pixbuf_):
    try:
        return pixbufs[pixbuf_]
    except KeyError:
        return None

def replace_with_codepoint(buffer_):
    if not pixbufs:
        # We use font emoticons
        return
    iter_ = buffer_.get_start_iter()
    pix = iter_.get_pixbuf()

    def replace(pix):
        if pix:
            emote = get_codepoint(pix)
            if not emote:
                return
            iter_2 = iter_.copy()
            iter_2.forward_char()
            buffer_.delete(iter_, iter_2)
            buffer_.insert(iter_, emote)

    replace(pix)
    while iter_.forward_char():
        pix = iter_.get_pixbuf()
        replace(pix)

class EmoticonPopover(Gtk.Popover):
    def __init__(self, emoji_dict, use_image):
        super().__init__()
        self.set_name('EmoticonPopover')
        self.text_widget = None
        self.use_image = use_image

        notebook = Gtk.Notebook()
        self.add(notebook)
        self.handler_id = self.connect('key_press_event', self.on_key_press)

        for category in emoji_dict:
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_min_content_height(MIN_HEIGHT)

            flowbox = Gtk.FlowBox()
            flowbox.set_max_children_per_line(MAX_CHILDREN_PER_LINE)
            flowbox.connect('child_activated', self.on_emoticon_press)

            scrolled_window.add(flowbox)

            # Use first entry as a label for the notebook page
            if self.use_image:
                cat_image = Gtk.Image()
                cat_image.set_from_pixbuf(emoji_dict[category][0])
                notebook.append_page(scrolled_window, cat_image)
            else:
                notebook.append_page(scrolled_window, Gtk.Label(label=emoji_dict[category][0]))

            # Populate the category with emojis
            for pix in emoji_dict[category][1:]:
                if isinstance(pix, list):
                    widget = self.add_emoticon_modifier(pix)
                else:
                    if self.use_image:
                        widget = Gtk.Image()
                        widget.set_from_pixbuf(pix)
                    else:
                        widget = Gtk.Label(pix)
                flowbox.add(widget)

        notebook.show_all()

    def add_emoticon_modifier(self, pixbuf_list):
        button = Gtk.MenuButton()
        button.set_relief(Gtk.ReliefStyle.NONE)

        if self.use_image:
            # We use the first item of the list as image for the button
            button.get_child().set_from_pixbuf(pixbuf_list[0])
        else:
            button.remove(button.get_child())
            label = Gtk.Label(pixbuf_list[0])
            button.add(label)

        button.connect('button-press-event', self.on_modifier_press)

        popover = Gtk.Popover()
        popover.set_name('EmoticonPopover')
        popover.connect('key_press_event', self.on_key_press)

        flowbox = Gtk.FlowBox()
        flowbox.set_size_request(200, -1)
        flowbox.set_max_children_per_line(MODIFIER_MAX_CHILDREN_PER_LINE)
        flowbox.connect('child_activated', self.on_emoticon_press)

        popover.add(flowbox)

        for pix in pixbuf_list[1:]:
            if self.use_image:
                widget = Gtk.Image()
                widget.set_from_pixbuf(pix)
            else:
                widget = Gtk.Label(pix)
            flowbox.add(widget)

        flowbox.show_all()
        button.set_popover(popover)
        return button

    def set_callbacks(self, widget):
        self.text_widget = widget
        # Because the handlers getting disconnected when on_destroy() is called
        # we connect them again
        if self.handler_id:
            self.disconnect(self.handler_id)
        self.handler_id = self.connect('key_press_event', self.on_key_press)

    def on_key_press(self, widget, event):
        self.text_widget.grab_focus()

    def on_modifier_press(self, button, event):
        if event.button == 3:
            button.get_popover().show()
            button.get_popover().get_child().unselect_all()
        if event.button == 1:
            button.get_parent().emit('activate')
            if self.use_image:
                self.append_emoticon(button.get_child().get_pixbuf())
            else:
                self.append_emoticon(button.get_child().get_text())
            return True

    def on_emoticon_press(self, flowbox, child):
        GLib.timeout_add(100, flowbox.unselect_all)
        
        if isinstance(child.get_child(), Gtk.MenuButton):
            return

        if self.use_image:
            self.append_emoticon(child.get_child().get_pixbuf())
        else:
            self.append_emoticon(child.get_child().get_text())

    def append_emoticon(self, pix):
        buffer_ = self.text_widget.get_buffer()
        if buffer_.get_char_count():
            buffer_.insert_at_cursor(' ')
            insert_mark = buffer_.get_insert()
            insert_iter = buffer_.get_iter_at_mark(insert_mark)
            if self.use_image:
                buffer_.insert_pixbuf(insert_iter, pix)
            else:
                buffer_.insert(insert_iter, pix)
            buffer_.insert_at_cursor(' ')
        else: # we are the beginning of buffer
            insert_mark = buffer_.get_insert()
            insert_iter = buffer_.get_iter_at_mark(insert_mark)
            if self.use_image:
                buffer_.insert_pixbuf(insert_iter, pix)
            else:
                buffer_.insert(insert_iter, pix)
            buffer_.insert_at_cursor(' ')

    def do_destroy(self):
        # Remove the references we hold to other objects
        self.text_widget = None
        # Even though we dont destroy the Popover, handlers are getting
        # still disconnected, which makes the handler_id invalid
        # FIXME: find out how we can prevent handlers getting disconnected
        self.handler_id = None
        # Never destroy, creating a new EmoticonPopover is expensive
        return True


