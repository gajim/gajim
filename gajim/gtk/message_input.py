# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2008-2009 Julien Pivotto <roidelapluie AT gmail.com>
#
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

from nbxmpp.modules.misc import build_xhtml_body

from gajim.common import app
from gajim.common.regex import LINK_REGEX

from .util import scroll_to_end

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports


class MessageInputTextView(Gtk.TextView):
    """
    Class for the message textview (where user writes new messages) for
    chat/groupchat windows
    """
    UNDO_LIMIT = 20

    def __init__(self):
        Gtk.TextView.__init__(self)

        # set properties
        self.set_border_width(3)
        self.set_accepts_tab(True)
        self.set_editable(True)
        self.set_cursor_visible(True)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_left_margin(2)
        self.set_right_margin(2)
        self.set_pixels_above_lines(2)
        self.set_pixels_below_lines(2)
        self.get_style_context().add_class('gajim-conversation-font')

        self.drag_dest_unset()

        # set undo list
        self.undo_list = []
        # needed to know if we undid something
        self.undo_pressed = False

        self._last_text = ''

        self.begin_tags = {}
        self.end_tags = {}
        self.color_tags = []
        self.fonts_tags = []
        self.other_tags = {}

        buffer_ = self.get_buffer()
        self.other_tags['bold'] = buffer_.create_tag('bold')
        self.other_tags['bold'].set_property('weight', Pango.Weight.BOLD)
        self.begin_tags['bold'] = '<strong>'
        self.end_tags['bold'] = '</strong>'
        self.other_tags['italic'] = buffer_.create_tag('italic')
        self.other_tags['italic'].set_property('style', Pango.Style.ITALIC)
        self.begin_tags['italic'] = '<em>'
        self.end_tags['italic'] = '</em>'
        self.other_tags['underline'] = buffer_.create_tag('underline')
        self.other_tags['underline'].set_property('underline',
                                                  Pango.Underline.SINGLE)
        underline = '<span style="text-decoration: underline;">'
        self.begin_tags['underline'] = underline
        self.end_tags['underline'] = '</span>'
        self.other_tags['strike'] = buffer_.create_tag('strike')
        self.other_tags['strike'].set_property('strikethrough', True)
        strike = '<span style="text-decoration: line-through;">'
        self.begin_tags['strike'] = strike
        self.end_tags['strike'] = '</span>'

        self.connect_after('paste-clipboard', self._after_paste_clipboard)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args):
        # We restore the TextView’s drag destination to avoid a GTK warning
        # when closing the control. ChatControlBase.shutdown() calls destroy()
        # on the control’s main box, causing GTK to recursively destroy the
        # child widgets. GTK then tries to set a target list on the TextView,
        # resulting in a warning because the Widget has no drag destination.
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            None,
            Gdk.DragAction.DEFAULT)

    def _on_focus_in(self, _widget, _event):
        self.toggle_speller(True)
        scrolled = self.get_parent()
        scrolled.get_style_context().add_class('message-input-focus')
        return False

    def _on_focus_out(self, _widget, _event):
        self.toggle_speller(False)
        scrolled = self.get_parent()
        scrolled.get_style_context().remove_class('message-input-focus')
        return False

    def insert_text(self, text):
        self.get_buffer().insert_at_cursor(text)

    def insert_newline(self):
        buffer_ = self.get_buffer()
        buffer_.insert_at_cursor('\n')
        mark = buffer_.get_insert()
        iter_ = buffer_.get_iter_at_mark(mark)
        if buffer_.get_end_iter().equal(iter_):
            GLib.idle_add(scroll_to_end, self.get_parent())

    def has_text(self):
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, True)
        return text != ''

    def get_text(self):
        buf = self.get_buffer()
        start, end = buf.get_bounds()
        text = self.get_buffer().get_text(start, end, True)
        return text

    def toggle_speller(self, activate):
        if app.is_installed('GSPELL') and app.settings.get('use_speller'):
            spell_view = Gspell.TextView.get_from_gtk_text_view(self)
            spell_view.set_inline_spell_checking(activate)

    @staticmethod
    def _after_paste_clipboard(textview):
        buffer_ = textview.get_buffer()
        mark = buffer_.get_insert()
        iter_ = buffer_.get_iter_at_mark(mark)
        if iter_.get_offset() == buffer_.get_end_iter().get_offset():
            GLib.idle_add(scroll_to_end, textview.get_parent())

    def make_clickable_urls(self, text):
        _buffer = self.get_buffer()

        start = 0
        end = 0
        index = 0

        new_text = ''
        iterator = LINK_REGEX.finditer(text)
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
        start = self.get_active_iters()[0]
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

    def set_tag(self, tag):
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

    def clear_tags(self):
        _buffer = self.get_buffer()
        start, finish = self.get_active_iters()
        _buffer.remove_all_tags(start, finish)

    def color_set(self, widget, response):
        if response in (-6, -4):
            widget.destroy()
            return

        color = widget.get_property('rgba')
        widget.destroy()
        _buffer = self.get_buffer()
        # Create #aabbcc color string from rgba color
        color_string = '#%02X%02X%02X' % (round(color.red*255),
                                          round(color.green*255),
                                          round(color.blue*255))

        tag_name = 'color' + color_string
        if not tag_name in self.color_tags:
            tag_color = _buffer.create_tag(tag_name)
            tag_color.set_property('foreground', color_string)
            begin = '<span style="color: %s;">' % color_string
            self.begin_tags[tag_name] = begin
            self.end_tags[tag_name] = '</span>'
            self.color_tags.append(tag_name)

        start, finish = self.get_active_iters()

        for tag in self.color_tags:
            _buffer.remove_tag_by_name(tag, start, finish)

        _buffer.apply_tag_by_name(tag_name, start, finish)

    def font_set(self, widget, response, start, finish):
        if response in (-6, -4):
            widget.destroy()
            return

        font = widget.get_font()
        font_desc = widget.get_font_desc()
        family = font_desc.get_family()
        size = font_desc.get_size()
        size = size / Pango.SCALE
        weight = font_desc.get_weight()
        style = font_desc.get_style()

        widget.destroy()

        _buffer = self.get_buffer()

        tag_name = 'font' + font
        if not tag_name in self.fonts_tags:
            tag_font = _buffer.create_tag(tag_name)
            tag_font.set_property('font', family + ' ' + str(size))
            self.begin_tags[tag_name] = \
                    '<span style="font-family: ' + family + '; ' + \
                    'font-size: ' + str(size) + 'px">'
            self.end_tags[tag_name] = '</span>'
            self.fonts_tags.append(tag_name)

        for tag in self.fonts_tags:
            _buffer.remove_tag_by_name(tag, start, finish)

        _buffer.apply_tag_by_name(tag_name, start, finish)

        if weight == Pango.Weight.BOLD:
            _buffer.apply_tag_by_name('bold', start, finish)
        else:
            _buffer.remove_tag_by_name('bold', start, finish)

        if style == Pango.Style.ITALIC:
            _buffer.apply_tag_by_name('italic', start, finish)
        else:
            _buffer.remove_tag_by_name('italic', start, finish)

    def get_xhtml(self):
        _buffer = self.get_buffer()
        old = _buffer.get_start_iter()
        tags = {}
        tags['bold'] = False
        iter_ = _buffer.get_start_iter()
        old = _buffer.get_start_iter()
        text = ''
        modified = False

        def xhtml_special(text):
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('&', '&amp;')
            text = text.replace('\n', '<br />')
            return text

        for tag in iter_.get_toggled_tags(True):
            tag_name = tag.get_property('name')
            if tag_name not in self.begin_tags:
                continue
            text += self.begin_tags[tag_name]
            modified = True
        while (iter_.forward_to_tag_toggle(None) and not iter_.is_end()):
            text += xhtml_special(_buffer.get_text(old, iter_, True))
            old.forward_to_tag_toggle(None)
            new_tags, old_tags, end_tags = [], [], []
            for tag in iter_.get_toggled_tags(True):
                tag_name = tag.get_property('name')
                if tag_name not in self.begin_tags:
                    continue
                new_tags.append(tag_name)
                modified = True

            for tag in iter_.get_tags():
                tag_name = tag.get_property('name')
                if (tag_name not in self.begin_tags or
                        tag_name not in self.end_tags):
                    continue
                if tag_name not in new_tags:
                    old_tags.append(tag_name)

            for tag in iter_.get_toggled_tags(False):
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

        buffer_text = _buffer.get_text(old, _buffer.get_end_iter(), True)
        text += xhtml_special(buffer_text)
        for tag in iter_.get_toggled_tags(False):
            tag_name = tag.get_property('name')
            if tag_name not in self.end_tags:
                continue
            text += self.end_tags[tag_name]

        if modified:
            wrapped_text = '<p>%s</p>' % self.make_clickable_urls(text)
            return build_xhtml_body(wrapped_text)
        return None

    def replace_emojis(self):
        theme = app.settings.get('emoticons_theme')
        if not theme or theme == 'font':
            return

        def replace(anchor):
            if anchor is None:
                return
            image = anchor.get_widgets()[0]
            if hasattr(image, 'codepoint'):
                # found emoji
                self.replace_char_at_iter(iter_, image.codepoint)
                image.destroy()

        iter_ = self.get_buffer().get_start_iter()
        replace(iter_.get_child_anchor())

        while iter_.forward_char():
            replace(iter_.get_child_anchor())

    def replace_char_at_iter(self, iter_, new_char):
        buffer_ = self.get_buffer()
        iter_2 = iter_.copy()
        iter_2.forward_char()
        buffer_.delete(iter_, iter_2)
        buffer_.insert(iter_, new_char)

    def insert_emoji(self, codepoint, pixbuf):
        buffer_ = self.get_buffer()
        if buffer_.get_char_count():
            # buffer contains text
            buffer_.insert_at_cursor(' ')

        insert_mark = buffer_.get_insert()
        insert_iter = buffer_.get_iter_at_mark(insert_mark)

        if pixbuf is None:
            buffer_.insert(insert_iter, codepoint)
        else:
            anchor = buffer_.create_child_anchor(insert_iter)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.codepoint = codepoint
            image.show()
            self.add_child_at_anchor(image, anchor)
        buffer_.insert_at_cursor(' ')

    def clear(self, _widget=None):
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

    def undo(self, _widget=None):
        """
        Undo text in the textview
        """
        _buffer = self.get_buffer()
        if self.undo_list:
            _buffer.set_text(self.undo_list.pop())
        self.undo_pressed = True
