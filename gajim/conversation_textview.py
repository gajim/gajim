# Copyright (C) 2005 Norman Rasmussen <norman AT rasmussen.co.za>
# Copyright (C) 2005-2006 Alex Mauer <hawke AT hawkesnest.net>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
#                    Stephan Erb <steve-e AT h3c.de>
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
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
import time
import os

import queue
import urllib

from gajim.gtk import AddNewContactWindow
from gajim.gtk import util
from gajim.gtk.util import load_icon
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_cursor
from gajim.gtk.emoji_data import emoji_pixbufs
from gajim.gtk.emoji_data import is_emoji
from gajim.gtk.emoji_data import get_emoji_pixbuf
from gajim.common import app
from gajim.common import helpers
from gajim.common import i18n
from calendar import timegm
from gajim.common.fuzzyclock import FuzzyClock
from gajim.common.const import StyleAttr

from gajim.htmltextview import HtmlTextView

NOT_SHOWN = 0
ALREADY_RECEIVED = 1
SHOWN = 2

import logging
log = logging.getLogger('gajim.conversation_textview')

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
        if isinstance(parent, Gtk.EventBox):
            parent = parent.get_parent()
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

    def __init__(self, account, used_in_history_window = False):
        """
        If used_in_history_window is True, then we do not show Clear menuitem in
        context menu
        """
        GObject.GObject.__init__(self)
        self.used_in_history_window = used_in_history_window
        self.line = 0
        self.message_list = []
        self.corrected_text_list = {}
        self.fc = FuzzyClock()

        # no need to inherit TextView, use it as atrribute is safer
        self.tv = HtmlTextView()
        # we have to override HtmlTextView Event handlers
        # because we don't inherit
        self.tv.hyperlink_handler = self.hyperlink_handler
        self.tv.connect_tooltip(self.query_tooltip)

        # set properties
        self.tv.set_border_width(1)
        self.tv.set_accepts_tab(True)
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.set_left_margin(2)
        self.tv.set_right_margin(2)
        self.handlers = {}
        self.image_cache = {}
        self.xep0184_marks = {}
        # self.last_sent_message_id = msg_stanza_id
        self.last_sent_message_id = None
        # last_received_message_id[name] = (msg_stanza_id, line_start_mark)
        self.last_received_message_id = {}
        self.autoscroll = True
        # connect signals
        id_ = self.tv.connect('populate_popup', self.on_textview_populate_popup)
        self.handlers[id_] = self.tv
        id_ = self.tv.connect('button_press_event',
                self.on_textview_button_press_event)
        self.handlers[id_] = self.tv

        self.account = account
        self.cursor_changed = False
        self.last_time_printout = 0

        style = self.tv.get_style_context()
        style.add_class('gajim-conversation-font')
        buffer_ = self.tv.get_buffer()
        end_iter = buffer_.get_end_iter()
        buffer_.create_mark('end', end_iter, False)

        self.tagIn = buffer_.create_tag('incoming')
        color = app.css_config.get_value(
            '.gajim-incoming-nickname', StyleAttr.COLOR)
        self.tagIn.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-incoming-nickname')
        self.tagIn.set_property('font-desc', desc)

        self.tagOut = buffer_.create_tag('outgoing')
        color = app.css_config.get_value(
            '.gajim-outgoing-nickname', StyleAttr.COLOR)
        self.tagOut.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-outgoing-nickname')
        self.tagOut.set_property('font-desc', desc)

        self.tagStatus = buffer_.create_tag('status')
        color = app.css_config.get_value(
            '.gajim-status-message', StyleAttr.COLOR)
        self.tagStatus.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-status-message')
        self.tagStatus.set_property('font-desc', desc)

        self.tagInText = buffer_.create_tag('incomingtxt')
        color = app.css_config.get_value(
            '.gajim-incoming-message-text', StyleAttr.COLOR)
        if color:
            self.tagInText.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-incoming-message-text')
        self.tagInText.set_property('font-desc', desc)

        self.tagOutText = buffer_.create_tag('outgoingtxt')
        color = app.css_config.get_value(
            '.gajim-outgoing-message-text', StyleAttr.COLOR)
        if color:
            self.tagOutText.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-outgoing-message-text')
        self.tagOutText.set_property('font-desc', desc)

        colors = app.config.get('gc_nicknames_colors')
        colors = colors.split(':')
        for i, color in enumerate(colors):
            tagname = 'gc_nickname_color_' + str(i)
            tag = buffer_.create_tag(tagname)
            tag.set_property('foreground', color)

        self.tagMarked = buffer_.create_tag('marked')
        color = app.css_config.get_value(
            '.gajim-highlight-message', StyleAttr.COLOR)
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
        color = app.css_config.get_value('.gajim-restored-message', StyleAttr.COLOR)
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

        tag = buffer_.create_tag('xep0184-received')
        tag.set_property('foreground', '#73d216')

        # One mark at the begining then 2 marks between each lines
        size = app.config.get('max_conversation_lines')
        size = 2 * size - 1
        self.marks_queue = queue.Queue(size)

        self.allow_focus_out_line = True
        # holds a mark at the end of --- line
        self.focus_out_end_mark = None

        self.just_cleared = False

    def query_tooltip(self, widget, x_pos, y_pos, keyboard_mode, tooltip):
        window = widget.get_window(Gtk.TextWindowType.TEXT)
        x_pos, y_pos = self.tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)
        if Gtk.MINOR_VERSION > 18:
            iter_ = self.tv.get_iter_at_position(x_pos, y_pos)[1]
        else:
            iter_ = self.tv.get_iter_at_position(x_pos, y_pos)[0]
        for tag in iter_.get_tags():
            tag_name = tag.get_property('name')
            if tag_name == 'focus-out-line':
                tooltip.set_text(_(
                    'Text below this line is what has '
                    'been said since the\nlast time you paid attention to this '
                    'group chat'))
                return True
            if getattr(tag, 'is_anchor', False):
                text = getattr(tag, 'title', False)
                if text:
                    if len(text) > 50:
                        text = text[:47] + '…'
                    tooltip.set_text(text)
                    window.set_cursor(get_cursor('HAND2'))
                    self.cursor_changed = True
                    return True
            if tag_name in ('url', 'mail', 'xmpp', 'sth_at_sth'):
                window.set_cursor(get_cursor('HAND2'))
                self.cursor_changed = True
                return False
            try:
                text = self.corrected_text_list[tag_name]
                tooltip.set_markup(text)
                return True
            except KeyError:
                pass
        if self.cursor_changed:
            window.set_cursor(get_cursor('XTERM'))
            self.cursor_changed = False
        return False

    def del_handlers(self):
        for i in self.handlers.keys():
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
        del self.handlers
        self.tv.destroy()

    def update_tags(self):
        self.tagIn.set_property('foreground', app.css_config.get_value('.gajim-incoming-nickname', StyleAttr.COLOR))
        self.tagOut.set_property('foreground', app.css_config.get_value('.gajim-outgoing-nickname', StyleAttr.COLOR))
        self.tagStatus.set_property('foreground',
            app.css_config.get_value('.gajim-status-message', StyleAttr.COLOR))
        self.tagMarked.set_property('foreground',
            app.css_config.get_value('.gajim-highlight-message', StyleAttr.COLOR))
        color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)
        self.tv.tagURL.set_property('foreground', color)
        self.tv.tagMail.set_property('foreground', color)
        self.tv.tagXMPP.set_property('foreground', color)
        self.tv.tagSthAtSth.set_property('foreground', color)

    def scroll_to_end(self, force=False):
        if self.autoscroll or force:
            util.scroll_to_end(self.tv.get_parent())

    def correct_message(self, correct_id, kind, name):
        allowed = True
        if kind == 'incoming':
            try:
                if correct_id in self.last_received_message_id[name]:
                    start_mark = self.last_received_message_id[name][1]
                else:
                    allowed = False
            except KeyError:
                allowed = False
        elif kind == 'outgoing':
            if self.last_sent_message_id[0] == correct_id:
                start_mark = self.last_sent_message_id[1]
            else:
                allowed = False
        else:
            allowed = False

        if not allowed:
            log.debug('Message correction not allowed')
            return None

        end_mark, index = self.get_end_mark(correct_id, start_mark)
        if not index:
            log.debug('Could not find line to correct')
            return None

        buffer_ = self.tv.get_buffer()
        if not end_mark:
            end_iter = self.tv.get_buffer().get_end_iter()
        else:
            end_iter = buffer_.get_iter_at_mark(end_mark)

        start_iter = buffer_.get_iter_at_mark(start_mark)

        old_txt = buffer_.get_text(start_iter, end_iter, True)
        buffer_.delete(start_iter, end_iter)
        buffer_.delete_mark(start_mark)

        return index, end_mark, old_txt

    def add_xep0184_mark(self, id_):
        if id_ in self.xep0184_marks:
            return

        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()

        self.xep0184_marks[id_] = buffer_.create_mark(
            None, buffer_.get_end_iter(), left_gravity=True)

        buffer_.end_user_action()

    def show_xep0184_ack(self, id_):
        if id_ not in self.xep0184_marks:
            return

        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()

        if app.config.get('positive_184_ack'):
            begin_iter = buffer_.get_iter_at_mark(self.xep0184_marks[id_])
            buffer_.insert_with_tags_by_name(begin_iter, ' ✓',
                'xep0184-received')

        buffer_.end_user_action()
        del self.xep0184_marks[id_]

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
            self.scroll_to_end()

    def clear(self, tv = None):
        """
        Clear text in the textview
        """
        buffer_ = self.tv.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)
        size = app.config.get('max_conversation_lines')
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

            item = Gtk.MenuItem.new_with_mnemonic(_('_Clear'))
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

            always_use_en = app.config.get('always_english_wikipedia')
            if always_use_en:
                link = 'http://en.wikipedia.org/wiki/Special:Search?search=%s'\
                        % phrase_for_url
            else:
                link = 'http://%s.wikipedia.org/wiki/Special:Search?search=%s'\
                        % (i18n.LANG, phrase_for_url)
            item = Gtk.MenuItem.new_with_mnemonic(_('Read _Wikipedia Article'))
            id_ = item.connect('activate', self.visit_url_from_menuitem, link)
            self.handlers[id_] = item
            submenu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('Look it up in _Dictionary'))
            dict_link = app.config.get('dictionary_url')
            if dict_link == 'WIKTIONARY':
                # special link (yeah undocumented but default)
                always_use_en = app.config.get('always_english_wiktionary')
                if always_use_en:
                    link = 'http://en.wiktionary.org/wiki/Special:Search?search=%s'\
                            % phrase_for_url
                else:
                    link = 'http://%s.wiktionary.org/wiki/Special:Search?search=%s'\
                            % (i18n.LANG, phrase_for_url)
                id_ = item.connect('activate', self.visit_url_from_menuitem, link)
                self.handlers[id_] = item
            else:
                if dict_link.find('%s') == -1:
                    # we must have %s in the url if not WIKTIONARY
                    item = Gtk.MenuItem.new_with_label(_(
                            'Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
                    item.set_property('sensitive', False)
                else:
                    link = dict_link % phrase_for_url
                    id_ = item.connect('activate', self.visit_url_from_menuitem,
                            link)
                    self.handlers[id_] = item
            submenu.append(item)


            search_link = app.config.get('search_engine')
            if search_link.find('%s') == -1:
                # we must have %s in the url
                item = Gtk.MenuItem.new_with_label(
                    _('Web Search URL is missing an "%s"'))
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
        # If we clicked on a tagged text do NOT open the standard popup menu
        # if normal text check if we have sth selected
        self.selected_phrase = '' # do not move below event button check!

        if event.button != 3: # if not right click
            return False

        x, y = self.tv.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                int(event.x), int(event.y))
        iter_ = self.tv.get_iter_at_location(x, y)
        if isinstance(iter_, tuple):
            iter_ = iter_[1]
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
        app.interface.new_chat_from_jid(self.account, jid)

    def on_join_group_chat_menuitem_activate(self, widget, room_jid):
        # Remove ?join
        room_jid = room_jid.split('?')[0]
        app.interface.join_gc_minimal(self.account, room_jid)

    def on_add_to_roster_activate(self, widget, jid):
        AddNewContactWindow(self.account, jid)

    def make_link_menu(self, event, kind, text):
        xml = get_builder('chat_context_menu.ui')
        menu = xml.get_object('chat_context_menu')
        childs = menu.get_children()
        if kind == 'url':
            id_ = childs[0].connect('activate', self.on_copy_link_activate, text)
            self.handlers[id_] = childs[0]
            id_ = childs[1].connect('activate', self.on_open_link_activate, kind,
                    text)
            self.handlers[id_] = childs[1]
            childs[2].hide() # copy mail/jid address
            childs[3].hide() # open mail composer
            childs[4].hide() # jid section separator
            childs[5].hide() # start chat
            childs[6].hide() # join group chat
            childs[7].hide() # add to roster
        else: # It's a mail or a JID
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

            if self.account and app.connections[self.account].\
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
                childs[0].set_label(_('Copy JID'))
                childs[2].hide() # copy mail/jid address
                childs[3].hide() # open mail composer
                childs[4].hide() # jid section separator
            elif kind == 'mail':
                childs[2].set_label(_('Copy Email Address'))
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
            # we get the beginning of the tag
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
                elif app.interface.sth_at_sth_dot_sth_re.match(word):
                    # it's a JID or mail
                    kind = 'sth_at_sth'
            else:
                word = self.tv.get_buffer().get_text(begin_iter, end_iter, True)
            if event.button.button == 3: # right click
                self.make_link_menu(event, kind, word)
                return True
            else:
                self.plugin_modified = False
                app.plugin_manager.extension_point(
                    'hyperlink_handler', word, kind, self,
                    self.tv.get_toplevel())
                if self.plugin_modified:
                    return

                # we launch the correct application
                if kind == 'xmpp':
                    word = word[5:]
                    if '?' in word:
                        (jid, action) = word.split('?')
                        if action == 'join':
                            app.interface.join_gc_minimal(self.account, jid)
                        else:
                            self.on_start_chat_activate(None, jid)
                    else:
                        self.on_start_chat_activate(None, word)
                # handle geo:-URIs
                elif word[:4] == 'geo:':
                    location = word[4:]
                    lat, _, lon = location.partition(',')
                    if lon == '':
                        return
                    uri = 'https://www.openstreetmap.org/?' \
                          'mlat=%(lat)s&mlon=%(lon)s&zoom=16' % \
                          {'lat': lat, 'lon': lon}
                    helpers.launch_browser_mailer(kind, uri)
                # other URIs
                else:
                    helpers.launch_browser_mailer(kind, word)

    def detect_and_print_special_text(self, otext, other_tags, graphics=True,
    iter_=None, additional_data=None):
        """
        Detect special text (emots & links & formatting), print normal text
        before any special text it founds, then print special text (that happens
        many times until last special text is printed) and then return the index
        after *last* special text, so we can print it in
        print_conversation_line()
        """
        if not otext:
            return
        if additional_data is None:
            additional_data = {}
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

        # add oob text to the end
        try:
            gajim_data = additional_data['gajim']
            oob_url = gajim_data['oob_url']
        except KeyError:
            pass
        else:
            oob_desc = additional_data['gajim'].get('oob_desc', 'URL:')
            if oob_url != otext:
                otext += '\n{} {}'.format(oob_desc, oob_url)

        # basic: links + mail + formatting is always checked (we like that)
        if app.config.get('emoticons_theme') and graphics:
            # search for emoticons & urls
            iterator = app.interface.emot_and_basic_re.finditer(otext)
        else: # search for just urls + mail + formatting
            iterator = app.interface.basic_pattern_re.finditer(otext)
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
                iter_=end_iter, additional_data=additional_data)
            specials_limit -= 1
            if specials_limit <= 0:
                break

        # add the rest of text located in the index and after
        insert_tags_func(end_iter, otext[index:], *other_tags)

        return end_iter

    def print_special_text(self, special_text, other_tags, graphics=True,
    iter_=None, additional_data=None):
        """
        Is called by detect_and_print_special_text and prints special text
        (emots, links, formatting)
        """
        if additional_data is None:
            additional_data = {}

        # PluginSystem: adding GUI extension point for ConversationTextview
        self.plugin_modified = False
        app.plugin_manager.extension_point('print_special_text', self,
            special_text, other_tags, graphics, additional_data, iter_)
        if self.plugin_modified:
            return

        tags = []
        use_other_tags = True
        text_is_valid_uri = False
        is_xhtml_link = None
        show_ascii_formatting_chars = \
            app.config.get('show_ascii_formatting_chars')
        buffer_ = self.tv.get_buffer()

        # Detect XHTML-IM link
        ttt = buffer_.get_tag_table()
        tags_ = [(ttt.lookup(t) if isinstance(t, str) else t) for t in other_tags]
        for t in tags_:
            is_xhtml_link = getattr(t, 'href', None)
            if is_xhtml_link:
                break

        # Check if we accept this as an uri
        schemes = app.config.get('uri_schemes').split()
        for scheme in schemes:
            if special_text.startswith(scheme):
                text_is_valid_uri = True

        if iter_:
            end_iter = iter_
        else:
            end_iter = buffer_.get_end_iter()

        theme = app.config.get('emoticons_theme')
        show_emojis = theme and theme != 'font'
        if show_emojis and graphics and is_emoji(special_text):
            # it's an emoticon
            if emoji_pixbufs.complete:
                # only search for the pixbuf if we are sure
                # that loading is completed
                pixbuf = get_emoji_pixbuf(special_text)
                if pixbuf is None:
                    buffer_.insert(end_iter, special_text)
                else:
                    pixbuf = pixbuf.copy()
                    anchor = buffer_.create_child_anchor(end_iter)
                    anchor.plaintext = special_text
                    img = Gtk.Image.new_from_pixbuf(pixbuf)
                    img.show()
                    self.tv.add_child_at_anchor(img, anchor)
            else:
                # Set marks and save them so we can replace the emojis
                # once the loading is complete
                start_mark = buffer_.create_mark(None, end_iter, True)
                buffer_.insert(end_iter, special_text)
                end_mark = buffer_.create_mark(None, end_iter, True)
                emoji_pixbufs.append_marks(
                    self.tv, start_mark, end_mark, special_text)

        elif special_text.startswith('www.') or \
            special_text.startswith('ftp.') or \
            text_is_valid_uri and not is_xhtml_link:
                tags.append('url')
        elif special_text.startswith('mailto:') and not is_xhtml_link:
            tags.append('mail')
        elif special_text.startswith('xmpp:') and not is_xhtml_link:
            tags.append('xmpp')
        elif app.interface.sth_at_sth_dot_sth_re.match(special_text) and\
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
                puny_text = helpers.puny_encode_url(special_text)
                if puny_text != special_text:
                    puny_tags = []
                    if use_other_tags:
                        puny_tags += other_tags
                    if not puny_text:
                        puny_text = _('Invalid URL')
                    puny_tags = [(ttt.lookup(t) if isinstance(t, str) else t) for t in puny_tags]
                    buffer_.insert_with_tags(end_iter, " (%s)" % puny_text, *puny_tags)

    def print_empty_line(self, iter_=None):
        buffer_ = self.tv.get_buffer()
        if not iter_:
            iter_ = buffer_.get_end_iter()
        buffer_.insert_with_tags_by_name(iter_, '\n', 'eol')
        self.just_cleared = False

    def get_end_mark(self, msg_stanza_id, start_mark):
        for index, msg in enumerate(self.message_list):
            if msg[2] == msg_stanza_id and msg[1] == start_mark:
                try:
                    end_mark = self.message_list[index + 1][1]
                    end_mark_name = end_mark.get_name()
                except IndexError:
                    # We are at the last message
                    end_mark = None
                    end_mark_name = None

                log.debug('start mark: %s, end mark: %s, '
                          'replace message-list index: %s',
                          start_mark.get_name(), end_mark_name, index)

                return end_mark, index
        log.debug('stanza-id not in message list')
        return None, None

    def get_insert_mark(self, timestamp):
        # message_list = [(timestamp, line_start_mark, msg_stanza_id)]
        # We check if this is a new Message
        try:
            if self.message_list[-1][0] <= timestamp:
                return None, None
        except IndexError:
            # We have no Messages in the TextView
            return None, None

        # Not a new Message
        # Search for insertion point
        for index, msg in enumerate(self.message_list):
            if msg[0] > timestamp:
                return msg[1], index

        # Should not happen, but who knows
        return None, None

    def print_conversation_line(self, text, jid, kind, name, tim,
    other_tags_for_name=None, other_tags_for_time=None, other_tags_for_text=None,
    subject=None, old_kind=None, xhtml=None, simple=False, graphics=True,
    displaymarking=None, msg_stanza_id=None, correct_id=None, additional_data=None,
    encrypted=None):
        """
        Print 'chat' type messages
        """
        if additional_data is None:
            additional_data = {}
        buffer_ = self.tv.get_buffer()
        buffer_.begin_user_action()
        insert_mark = None
        insert_mark_name = None

        if kind == 'incoming_queue':
            kind = 'incoming'
        if old_kind == 'incoming_queue':
            old_kind = 'incoming'

        if not tim:
            # For outgoing Messages and Status prints
            tim = time.time()

        corrected = False
        if correct_id:
            try:
                index, insert_mark, old_txt = \
                    self.correct_message(correct_id, kind, name)
                if correct_id in self.corrected_text_list:
                    self.corrected_text_list[msg_stanza_id] = \
                        self.corrected_text_list[correct_id] + '\n{}' \
                        .format(GLib.markup_escape_text(old_txt))
                    del self.corrected_text_list[correct_id]
                else:
                    self.corrected_text_list[msg_stanza_id] = \
                        _('<b>Message corrected. Original message:</b>\n{}') \
                        .format(GLib.markup_escape_text(old_txt))
                corrected = True
            except TypeError:
                log.debug('Message was not corrected !')

        if not corrected:
            # Get insertion point into TextView
            insert_mark, index = self.get_insert_mark(tim)

        if insert_mark:
            insert_mark_name = insert_mark.get_name()

        log.debug(
            'Printed Line: %s, %s, %s, inserted after: %s'
            ', stanza-id: %s, correct-id: %s',
            self.line, text, tim, insert_mark_name,
            msg_stanza_id, correct_id)

        if not insert_mark:  # Texview is empty or Message is new
            iter_ = buffer_.get_end_iter()
            # Insert new Line if Textview is not empty
            if buffer_.get_char_count() > 0 and not corrected:
                buffer_.insert_with_tags_by_name(iter_, '\n', 'eol')
        else:
            iter_ = buffer_.get_iter_at_mark(insert_mark)

        # Create a temporary mark at the start of the line
        # with gravity=Left, so it will not move
        # even if we insert directly at the mark iter
        temp_mark = buffer_.create_mark('temp', iter_, left_gravity=True)

        if text.startswith('/me '):
            direction_mark = i18n.paragraph_direction_mark(str(text[3:]))
        else:
            direction_mark = i18n.paragraph_direction_mark(text)
        # don't apply direction mark if it's status message
        if kind == 'status':
            direction_mark = i18n.direction_mark

        # print the time stamp
        self.print_time(text, kind, tim, simple, direction_mark,
            other_tags_for_time, iter_)

        icon = load_icon('channel-secure-croped-symbolic', self.tv, pixbuf=True)
        if encrypted:
            buffer_.insert_pixbuf(iter_, icon)

        # If there's a displaymarking, print it here.
        if displaymarking:
            self.print_displaymarking(displaymarking, iter_=iter_)

        # kind = info, we print things as if it was a status: same color, ...
        if kind in ('error', 'info'):
            kind = 'status'
        other_text_tag = self.detect_other_text_tag(text, kind)
        text_tags = []
        if other_tags_for_text:
            text_tags = other_tags_for_text[:]  # create a new list
        if other_text_tag:
            text_tags.append(other_text_tag)

        else:  # not status nor /me
            if app.config.get('chat_merge_consecutive_nickname'):
                if kind != old_kind or self.just_cleared:
                    self.print_name(name, kind, other_tags_for_name,
                        direction_mark=direction_mark, iter_=iter_)
                else:
                    self.print_real_text(app.config.get(
                        'chat_merge_consecutive_nickname_indent'),
                        mark=insert_mark, additional_data=additional_data)
            else:
                self.print_name(name, kind, other_tags_for_name,
                    direction_mark=direction_mark, iter_=iter_)
            if kind == 'incoming':
                text_tags.append('incomingtxt')
            elif kind == 'outgoing':
                text_tags.append('outgoingtxt')

        self.print_subject(subject, iter_=iter_)
        
        iter_ = self.print_real_text(text, text_tags, name, xhtml, graphics=graphics,
            mark=insert_mark, additional_data=additional_data)

        if corrected:
            # Show Correction Icon
            buffer_.create_tag(tag_name=msg_stanza_id)
            buffer_.insert(iter_, ' ')
            icon = load_icon('document-edit-symbolic', self.tv, pixbuf=True)
            buffer_.insert_pixbuf(
                iter_, icon)
            tag_start_iter = iter_.copy()
            tag_start_iter.backward_chars(2)
            buffer_.apply_tag_by_name(msg_stanza_id, tag_start_iter, iter_)

        # If we inserted a Line we add a new line at the end
        if insert_mark:
            buffer_.insert_with_tags_by_name(iter_, '\n', 'eol')
        # We delete the temp mark and replace it with a mark
        # that has gravity=right
        temp_iter = buffer_.get_iter_at_mark(temp_mark)
        buffer_.delete_mark(temp_mark)
        new_mark = buffer_.create_mark(
            str(self.line), temp_iter, left_gravity=False)

        if not index:
            # New Message
            self.message_list.append((tim, new_mark, msg_stanza_id))
        elif corrected:
            # Replace the corrected message
            self.message_list[index] = (tim, new_mark, msg_stanza_id)
        else:
            # We insert the message at index
            self.message_list.insert(index, (tim, new_mark, msg_stanza_id))

        if kind == 'incoming':
            self.last_received_message_id[name] = (msg_stanza_id, new_mark)
        elif kind == 'outgoing':
            self.last_sent_message_id = (msg_stanza_id, new_mark)

        if not insert_mark:
            if self.autoscroll or kind == 'outgoing':
                # we are at the end or we are sending something
                self.scroll_to_end(force=True)

        self.just_cleared = False
        buffer_.end_user_action()

        self.line += 1
        return iter_

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
            # strftime Windows bug has problems with Unicode
            # see: http://bugs.python.org/issue8304
            if os.name != 'nt':
                format_ += i18n.direction_mark + day_str + direction_mark + ' '
            else:
                format_ += day_str + ' '
        timestamp_str = app.config.get('time_stamp')
        timestamp_str = helpers.from_one_line(timestamp_str)
        format_ += timestamp_str
        tim_format = time.strftime(format_, tim)
        return tim_format

    def detect_other_text_tag(self, text, kind):
        if kind == 'status':
            return kind
        elif text.startswith('/me ') or text.startswith('/me\n'):
            return kind

    def print_time(self, text, kind, tim, simple, direction_mark, other_tags_for_time, iter_):
        local_tim = time.localtime(tim)
        buffer_ = self.tv.get_buffer()
        current_print_time = app.config.get('print_time')

        if current_print_time == 'always' and kind != 'info' and not simple:
            timestamp_str = self.get_time_to_show(local_tim, direction_mark)
            timestamp = time.strftime(timestamp_str, local_tim)
            timestamp = direction_mark + timestamp + direction_mark
            if other_tags_for_time:
                buffer_.insert_with_tags_by_name(iter_, timestamp,
                    *other_tags_for_time)
            else:
                buffer_.insert(iter_, timestamp)
        elif current_print_time == 'sometimes' and kind != 'info' and not simple:
            every_foo_seconds = 60 * app.config.get(
                'print_ichat_every_foo_minutes')
            seconds_passed = tim - self.last_time_printout
            if seconds_passed > every_foo_seconds:
                self.last_time_printout = tim
                if app.config.get('print_time_fuzzy') > 0:
                    tim_format = self.fc.fuzzy_time(
                        app.config.get('print_time_fuzzy'), local_tim)
                else:
                    tim_format = self.get_time_to_show(local_tim, direction_mark)
                buffer_.insert_with_tags_by_name(iter_, tim_format + '\n',
                    'time_sometimes')

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
            name_tags = []
            buffer_ = self.tv.get_buffer()
            if iter_:
                end_iter = iter_
            else:
                end_iter = buffer_.get_end_iter()

            if other_tags_for_name:
                name_tags = other_tags_for_name[:]  # create a new list
            name_tags.append(kind)
            before_str = app.config.get('before_nickname')
            before_str = helpers.from_one_line(before_str)
            after_str = app.config.get('after_nickname')
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
            self.print_empty_line(end_iter)

    def print_real_text(self, text, text_tags=None, name=None, xhtml=None,
    graphics=True, mark=None, additional_data=None):
        """
        Add normal and special text. call this to add text
        """
        if text_tags is None:
            text_tags = []
        if additional_data is None:
            additional_data = {}
        buffer_ = self.tv.get_buffer()
        if not mark:
            iter_ = buffer_.get_end_iter()
        else:
            iter_ = buffer_.get_iter_at_mark(mark)
        if xhtml:
            try:
                if name and (text.startswith('/me ') or text.startswith('/me\n')):
                    xhtml = xhtml.replace('/me', '<i>* %s</i>' % (name,), 1)
                self.tv.display_html(xhtml, self.tv, self, iter_=iter_)
                return
            except Exception as error:
                log.debug('Error processing xhtml: %s', error)
                log.debug('with |%s|', xhtml)

        # /me is replaced by name if name is given
        if name and (text.startswith('/me ') or text.startswith('/me\n')):
            text = '* ' + name + text[3:]
            text_tags.append('italic')

        # PluginSystem: adding GUI extension point for ConversationTextview
        self.plugin_modified = False
        app.plugin_manager.extension_point('print_real_text', self,
            text, text_tags, graphics, iter_, additional_data)

        if self.plugin_modified:
            if not mark:
                return buffer_.get_end_iter()
            else:
                return buffer_.get_iter_at_mark(mark)

        if not mark:
            iter_ = buffer_.get_end_iter()
        else:
            iter_ = buffer_.get_iter_at_mark(mark)

        # detect urls formatting and if the user has it on emoticons
        return self.detect_and_print_special_text(text, text_tags, graphics=graphics,
            iter_=iter_, additional_data=additional_data)
