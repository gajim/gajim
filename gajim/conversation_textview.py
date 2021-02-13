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

import time
import queue
import urllib
import logging

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gdk

from gajim.common import app
from gajim.common import helpers
from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import StyleAttr
from gajim.common.const import Trust
from gajim.common.const import URI_SCHEMES
from gajim.common.helpers import to_user_string
from gajim.common.regex import STH_AT_STH_DOT_STH_REGEX
from gajim.common.regex import BASIC_REGEX
from gajim.common.regex import LINK_REGEX
from gajim.common.regex import EMOT_AND_BASIC_REGEX
from gajim.common.regex import EMOT_AND_LINK_REGEX

from gajim.gui import util
from gajim.gui.util import get_cursor
from gajim.gui.util import format_fingerprint
from gajim.gui.util import text_to_color
from gajim.gui.emoji_data import emoji_pixbufs
from gajim.gui.emoji_data import is_emoji
from gajim.gui.emoji_data import get_emoji_pixbuf
from gajim.gui.htmltextview import HtmlTextView

NOT_SHOWN = 0
ALREADY_RECEIVED = 1
SHOWN = 2

log = logging.getLogger('gajim.conversation_textview')

TRUST_SYMBOL_DATA = {
    Trust.UNTRUSTED: ('dialog-error-symbolic',
                      _('Untrusted'),
                      'error-color'),
    Trust.UNDECIDED: ('security-low-symbolic',
                      _('Trust Not Decided'),
                      'warning-color'),
    Trust.BLIND: ('security-medium-symbolic',
                  _('Unverified'),
                  'encrypted-color'),
    Trust.VERIFIED: ('security-high-symbolic',
                     _('Verified'),
                     'encrypted-color')
}


class ConversationTextview(GObject.GObject):
    """
    Class for the conversation textview (where user reads already said messages)
    for chat/groupchat windows
    """
    __gsignals__ = dict(quote=(
        GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
        None, # return value
        (str, ) # arguments
        ))

    def __init__(self, account, used_in_history_window=False):
        """
        If used_in_history_window is True, then we do not show Clear menuitem in
        context menu
        """
        GObject.GObject.__init__(self)
        self.used_in_history_window = used_in_history_window
        self.line = 0
        self._message_list = []
        self.corrected_text_list = {}

        # no need to inherit TextView, use it as attribute is safer
        self.tv = HtmlTextView(account)
        self.tv.connect('query-tooltip', self._query_tooltip)

        self._buffer = self.tv.get_buffer()
        self.handlers = {}
        self.image_cache = {}
        # self.last_sent_message_id = message_id
        self.last_sent_message_id = None
        # last_received_message_id[name] = (message_id, line_start_mark)
        self.last_received_message_id = {}
        self.autoscroll = True
        # connect signals
        id_ = self.tv.connect('populate_popup', self.on_textview_populate_popup)
        self.handlers[id_] = self.tv
        id_ = self.tv.connect('button_press_event',
                self.on_textview_button_press_event)
        self.handlers[id_] = self.tv

        self.account = account
        self._cursor_changed = False
        self.last_time_printout = 0
        self.encryption_enabled = False

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

        self.tagMarked = buffer_.create_tag('marked')
        color = app.css_config.get_value(
            '.gajim-highlight-message', StyleAttr.COLOR)
        self.tagMarked.set_property('foreground', color)
        self.tagMarked.set_property('weight', Pango.Weight.BOLD)

        textview_icon = buffer_.create_tag('textview-icon')
        textview_icon.set_property('rise', Pango.units_from_double(-2.45))

        # To help plugins easily identify the nickname
        buffer_.create_tag('nickname')

        tag = buffer_.create_tag('time_sometimes')
        tag.set_property('foreground', 'darkgrey')
        #Pango.SCALE_SMALL
        tag.set_property('scale', 0.8333333333333)
        tag.set_property('justification', Gtk.Justification.CENTER)

        tag = buffer_.create_tag('small')
        #Pango.SCALE_SMALL
        tag.set_property('scale', 0.8333333333333)

        self.tv.create_tags()

        tag = buffer_.create_tag('bold')
        tag.set_property('weight', Pango.Weight.BOLD)

        tag = buffer_.create_tag('italic')
        tag.set_property('style', Pango.Style.ITALIC)

        tag = buffer_.create_tag('strikethrough')
        tag.set_property('strikethrough', True)

        buffer_.create_tag('focus-out-line', justification=Gtk.Justification.CENTER)
        self.displaymarking_tags = {}

        # One mark at the beginning then 2 marks between each lines
        size = app.settings.get('max_conversation_lines')
        size = 2 * size - 1
        self.marks_queue = queue.Queue(size)

        self.allow_focus_out_line = True
        # holds a mark at the end of --- line
        self.focus_out_end_mark = None

        self.just_cleared = False

    def _query_tooltip(self, widget, x_pos, y_pos, keyboard_mode, tooltip):
        window = widget.get_window(Gtk.TextWindowType.TEXT)
        x_pos, y_pos = self.tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)

        iter_ = self.tv.get_iter_at_position(x_pos, y_pos)[1]
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
                    window.set_cursor(get_cursor('pointer'))
                    self._cursor_changed = True
                    return True
            if tag_name in ('url', 'mail', 'xmpp', 'sth_at_sth'):
                window.set_cursor(get_cursor('pointer'))
                self._cursor_changed = True
                return False

        if self._cursor_changed:
            window.set_cursor(get_cursor('text'))
            self._cursor_changed = False
        return False

    def del_handlers(self):
        for i in self.handlers:
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
        self.tv.update_tags()

    def scroll_to_end(self, force=False):
        if self.autoscroll or force:
            GLib.idle_add(util.scroll_to_end, self.tv.get_parent())

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

    def show_receipt(self, id_):
        line = self._get_message_line(id_)
        if line is None:
            return
        line.set_receipt()

    def show_displayed(self, id_):
        line = self._get_message_line(id_)
        if line is None:
            return
        line.set_displayed()

    def show_error(self, id_, error):
        line = self._get_message_line(id_)
        if line is None:
            return
        line.set_error(to_user_string(error))

    def show_focus_out_line(self):
        if not self.allow_focus_out_line:
            # if room did not receive focus-in from the last time we added
            # --- line then do not add again
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

    def clear(self, tv=None):
        """
        Clear text in the textview
        """
        buffer_ = self.tv.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)
        size = app.settings.get('max_conversation_lines')
        size = 2 * size - 1
        self.marks_queue = queue.Queue(size)
        self.focus_out_end_mark = None
        self.just_cleared = True

    def visit_url_from_menuitem(self, widget, link):
        """
        Basically it filters out the widget instance
        """
        helpers.open_uri(link)

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

            always_use_en = app.settings.get('always_english_wikipedia')
            if always_use_en:
                link = 'https://en.wikipedia.org/wiki/Special:Search?search=%s'\
                        % phrase_for_url
            else:
                link = 'https://%s.wikipedia.org/wiki/Special:Search?search=%s'\
                        % (i18n.get_short_lang_code(), phrase_for_url)
            item = Gtk.MenuItem.new_with_mnemonic(_('Read _Wikipedia Article'))
            id_ = item.connect('activate', self.visit_url_from_menuitem, link)
            self.handlers[id_] = item
            submenu.append(item)

            item = Gtk.MenuItem.new_with_mnemonic(_('Look it up in _Dictionary'))
            dict_link = app.settings.get('dictionary_url')
            if dict_link == 'WIKTIONARY':
                # special link (yeah undocumented but default)
                always_use_en = app.settings.get('always_english_wiktionary')
                if always_use_en:
                    link = 'https://en.wiktionary.org/wiki/Special:Search?search=%s'\
                            % phrase_for_url
                else:
                    link = 'https://%s.wiktionary.org/wiki/Special:Search?search=%s'\
                            % (i18n.get_short_lang_code(), phrase_for_url)
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


            search_link = app.settings.get('search_engine')
            if search_link.find('%s') == -1:
                # we must have %s in the url
                item = Gtk.MenuItem.new_with_label(
                    _('Web Search URL is missing an "%s"'))
                item.set_property('sensitive', False)
            else:
                item = Gtk.MenuItem.new_with_mnemonic(_('Web _Search for it'))
                link = search_link % phrase_for_url
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
            additional_data = AdditionalDataDict()
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

        oob_url = additional_data.get_value('gajim', 'oob_url')
        if oob_url is not None:
            oob_desc = additional_data.get_value('gajim', 'oob_desc', 'URL:')
            if oob_url != otext:
                otext += '\n{} {}'.format(oob_desc, oob_url)

        # basic: links + mail + formatting is always checked (we like that)
        if app.settings.get('emoticons_theme') and graphics:
            # search for emoticons & urls
            if app.settings.get('ascii_formatting'):
                regex = EMOT_AND_BASIC_REGEX
            else:
                regex = EMOT_AND_LINK_REGEX
        else:
            if app.settings.get('ascii_formatting'):
                # search for just urls + mail + formatting
                regex = BASIC_REGEX
            else: # search for just urls + mail
                regex = LINK_REGEX
        iterator = regex.finditer(otext)
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
            additional_data = AdditionalDataDict()

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
            app.settings.get('show_ascii_formatting_chars')
        buffer_ = self.tv.get_buffer()

        # Detect XHTML-IM link
        ttt = buffer_.get_tag_table()
        tags_ = [(ttt.lookup(t) if isinstance(t, str) else t) for t in other_tags]
        for t in tags_:
            is_xhtml_link = getattr(t, 'href', None)
            if is_xhtml_link:
                break

        # Check if we accept this as an uri
        for scheme in URI_SCHEMES:
            if special_text.startswith(scheme):
                text_is_valid_uri = True

        if iter_:
            end_iter = iter_
        else:
            end_iter = buffer_.get_end_iter()

        theme = app.settings.get('emoticons_theme')
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

        elif (special_text.startswith('www.') or
              special_text.startswith('ftp.') or
              text_is_valid_uri and not is_xhtml_link):
            tags.append('url')
        elif special_text.startswith('mailto:') and not is_xhtml_link:
            tags.append('mail')
        elif special_text.startswith('xmpp:') and not is_xhtml_link:
            tags.append('xmpp')
        elif STH_AT_STH_DOT_STH_REGEX.match(special_text) and \
        not is_xhtml_link:
            # it's a JID or mail
            tags.append('sth_at_sth')
        elif special_text.startswith('*'): # it's a bold text
            tags.append('bold')
            if special_text[1] == '~' and special_text[-2] == '~' and\
            len(special_text) > 4: # it's also strikethrough
                tags.append('strikethrough')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove *~ ~*
            elif special_text[1] == '_' and special_text[-2] == '_' and \
            len(special_text) > 4: # it's also italic
                tags.append('italic')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove *_ _*
            else:
                if not show_ascii_formatting_chars:
                    special_text = special_text[1:-1] # remove * *
        elif special_text.startswith('~'): # it's a strikethrough text
            tags.append('strikethrough')
            if special_text[1] == '*' and special_text[-2] == '*' and \
            len(special_text) > 4: # it's also bold
                tags.append('bold')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove ~* *~
            elif special_text[1] == '_' and special_text[-2] == '_' and \
            len(special_text) > 4: # it's also italic
                tags.append('italic')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove ~_ _~
            else:
                if not show_ascii_formatting_chars:
                    special_text = special_text[1:-1] # remove ~ ~
        elif special_text.startswith('_'): # it's an italic text
            tags.append('italic')
            if special_text[1] == '*' and special_text[-2] == '*' and \
            len(special_text) > 4: # it's also bold
                tags.append('bold')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove _* *_
            elif special_text[1] == '~' and special_text[-2] == '~' and \
            len(special_text) > 4: # it's also strikethrough
                tags.append('strikethrough')
                if not show_ascii_formatting_chars:
                    special_text = special_text[2:-2] # remove _~ ~_
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

    def get_end_mark(self, message_id, start_mark):
        for index, line in enumerate(self._message_list):
            if line.id == message_id and line.start_mark == start_mark:
                try:
                    end_mark = self._message_list[index + 1].start_mark
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
        # message_list = [(timestamp, line_start_mark, message_id)]
        # We check if this is a new Message
        try:
            if self._message_list[-1].timestamp <= timestamp:
                return None, None
        except IndexError:
            # We have no Messages in the TextView
            return None, None

        # Not a new Message
        # Search for insertion point
        for index, line in enumerate(self._message_list):
            if line.timestamp > timestamp:
                return line.start_mark, index

        # Should not happen, but who knows
        return None, None

    def _get_message_line(self, id_):
        for message_line in reversed(self._message_list):
            if message_line.id == id_:
                return message_line

    def print_conversation_line(self, text, kind, name, tim,
    other_tags_for_name=None, other_tags_for_time=None, other_tags_for_text=None,
    subject=None, old_kind=None, graphics=True,
    displaymarking=None, message_id=None, correct_id=None, additional_data=None,
    marker=None, error=None):
        """
        Print 'chat' type messages
        """
        if additional_data is None:
            additional_data = AdditionalDataDict()
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
                    self.corrected_text_list[message_id] = \
                        self.corrected_text_list[correct_id] + '\n{}' \
                        .format(GLib.markup_escape_text(old_txt))
                    del self.corrected_text_list[correct_id]
                else:
                    self.corrected_text_list[message_id] = \
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
            message_id, correct_id)

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

        # print the encryption icon
        if kind in ('incoming', 'outgoing'):
            self.print_encryption_status(iter_, additional_data)

        # print the time stamp
        self.print_time(text, kind, tim, direction_mark,
                        other_tags_for_time, iter_)

        # If there's a displaymarking, print it here.
        if displaymarking:
            self.print_displaymarking(displaymarking, iter_)

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
            if app.settings.get('chat_merge_consecutive_nickname'):
                if kind != old_kind or self.just_cleared:
                    self.print_name(name, kind, other_tags_for_name,
                        direction_mark=direction_mark, iter_=iter_)
                else:
                    self.print_real_text(app.settings.get(
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

        iter_ = self.print_real_text(text, text_tags, name, graphics=graphics,
            mark=insert_mark, additional_data=additional_data)

        message_icons = MessageIcons()
        self._insert_message_icons(iter_, message_icons)

        # If we inserted a Line we add a new line at the end
        if insert_mark:
            buffer_.insert_with_tags_by_name(iter_, '\n', 'eol')
        # We delete the temp mark and replace it with a mark
        # that has gravity=right
        temp_iter = buffer_.get_iter_at_mark(temp_mark)
        buffer_.delete_mark(temp_mark)
        new_mark = buffer_.create_mark(
            str(self.line), temp_iter, left_gravity=False)

        message_line = MessageLine(message_id, tim, message_icons, new_mark)

        if corrected:
            message_line.set_correction(
                self.corrected_text_list[message_id])

        if error is not None:
            message_line.set_error(to_user_string(error))

        if marker is not None:
            if marker == 'received':
                message_line.set_receipt()
            elif marker == 'displayed':
                message_line.set_displayed()

        if index is None:
            # New Message
            self._message_list.append(message_line)
        elif corrected:
            # Replace the corrected message
            self._message_list[index] = message_line
        else:
            # We insert the message at index
            self._message_list.insert(index, message_line)

        if kind == 'incoming':
            self.last_received_message_id[name] = (message_id, new_mark)
        elif kind == 'outgoing':
            self.last_sent_message_id = (message_id, new_mark)

        if not insert_mark:
            if self.autoscroll or kind == 'outgoing':
                # we are at the end or we are sending something
                self.scroll_to_end(force=True)

        self.just_cleared = False
        buffer_.end_user_action()

        self.line += 1

    def get_time_to_show(self, tim):
        """
        Format the time according to config setting 'time_stamp'
        """
        format_ = helpers.from_one_line(app.settings.get('time_stamp'))
        tim_format = time.strftime(format_, tim)
        return tim_format

    def detect_other_text_tag(self, text, kind):
        if kind == 'status':
            return kind
        if text.startswith('/me ') or text.startswith('/me\n'):
            return kind

    def _insert_message_icons(self, iter_, message_icons):
        temp_mark = self._buffer.create_mark(None, iter_, True)
        self._buffer.insert(iter_, ' ')
        anchor = self._buffer.create_child_anchor(iter_)
        anchor.plaintext = ''
        self._buffer.insert(iter_, ' ')

        # Apply mark to vertically center the icon
        start = self._buffer.get_iter_at_mark(temp_mark)
        self._buffer.apply_tag_by_name('textview-icon', start, iter_)
        self.tv.add_child_at_anchor(message_icons, anchor)

    def print_encryption_status(self, iter_, additional_data):
        details = self._get_encryption_details(additional_data)
        if details is None:
            # Message was not encrypted
            if not self.encryption_enabled:
                return
            icon = 'channel-insecure-symbolic'
            color = 'unencrypted-color'
            tooltip = _('Not encrypted')
        else:
            name, fingerprint, trust = details
            tooltip = _('Encrypted (%s)') % (name)
            if trust is None:
                # The encryption plugin did not pass trust information
                icon = 'channel-secure-symbolic'
                color = 'encrypted-color'
            else:
                icon, trust_tooltip, color = TRUST_SYMBOL_DATA[trust]
                tooltip = '%s\n%s' % (tooltip, trust_tooltip)
            if fingerprint is not None:
                fingerprint = format_fingerprint(fingerprint)
                tooltip = '%s\n<tt>%s</tt>' % (tooltip, fingerprint)

        temp_mark = self._buffer.create_mark(None, iter_, True)
        self._buffer.insert(iter_, ' ')
        anchor = self._buffer.create_child_anchor(iter_)
        anchor.plaintext = ''
        self._buffer.insert(iter_, ' ')

        # Apply mark to vertically center the icon
        start = self._buffer.get_iter_at_mark(temp_mark)
        self._buffer.apply_tag_by_name('textview-icon', start, iter_)

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.show()
        image.set_tooltip_markup(tooltip)
        image.get_style_context().add_class(color)
        self.tv.add_child_at_anchor(image, anchor)

    @staticmethod
    def _get_encryption_details(additional_data):
        name = additional_data.get_value('encrypted', 'name')
        if name is None:
            return

        fingerprint = additional_data.get_value('encrypted', 'fingerprint')
        trust = additional_data.get_value('encrypted', 'trust')
        return name, fingerprint, trust

    def print_time(self, text, kind, tim, direction_mark, other_tags_for_time, iter_):
        local_tim = time.localtime(tim)
        buffer_ = self.tv.get_buffer()
        current_print_time = app.settings.get('print_time')

        if current_print_time == 'always':
            timestamp_str = self.get_time_to_show(local_tim)
            timestamp = time.strftime(timestamp_str, local_tim)
            timestamp = direction_mark + timestamp + direction_mark
            if other_tags_for_time:
                buffer_.insert_with_tags_by_name(iter_, timestamp,
                    *other_tags_for_time)
            else:
                buffer_.insert(iter_, timestamp)
        elif current_print_time == 'sometimes':
            every_foo_seconds = 60 * app.settings.get(
                'print_ichat_every_foo_minutes')
            seconds_passed = tim - self.last_time_printout
            if seconds_passed > every_foo_seconds:
                self.last_time_printout = tim
                tim_format = self.get_time_to_show(local_tim)
                buffer_.insert_with_tags_by_name(iter_, tim_format + '\n',
                    'time_sometimes')

    def print_displaymarking(self, displaymarking, iter_):
        bgcolor = displaymarking.bgcolor
        fgcolor = displaymarking.fgcolor
        text = displaymarking.name
        if text:
            buffer_ = self.tv.get_buffer()
            tag = self.displaymarking_tags.setdefault(bgcolor + '/' + fgcolor,
                buffer_.create_tag(None, background=bgcolor, foreground=fgcolor))
            buffer_.insert_with_tags(iter_, '[' + text + ']', tag)
            buffer_.insert_with_tags(iter_, ' ')

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
            name_tags.append('nickname')

            for tag in name_tags:
                if tag.startswith('muc_nickname_color_'):
                    self._add_new_colour_tags(tag, name)

            before_str = app.settings.get('before_nickname')
            before_str = helpers.from_one_line(before_str)
            after_str = app.settings.get('after_nickname')
            after_str = helpers.from_one_line(after_str)
            format_ = before_str + name + direction_mark + after_str + ' '
            buffer_.insert_with_tags_by_name(end_iter, format_, *name_tags)

    def _add_new_colour_tags(self, tag, name):
        if self._buffer.get_tag_table().lookup(tag) is not None:
            return
        rgba = Gdk.RGBA(*text_to_color(name))
        self._buffer.create_tag(tag, foreground_rgba=rgba)

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

    def print_real_text(self, text, text_tags=None, name=None,
    graphics=True, mark=None, additional_data=None):
        """
        Add normal and special text. call this to add text
        """
        if text_tags is None:
            text_tags = []
        if additional_data is None:
            additional_data = AdditionalDataDict()
        buffer_ = self.tv.get_buffer()
        if not mark:
            iter_ = buffer_.get_end_iter()
        else:
            iter_ = buffer_.get_iter_at_mark(mark)

        xhtml = additional_data.get_value('gajim', 'xhtml', False)
        if xhtml and app.settings.get('show_xhtml'):
            try:
                if name and (text.startswith('/me ') or text.startswith('/me\n')):
                    xhtml = xhtml.replace('/me', '<i>* %s</i>' % (name,), 1)
                self.tv.display_html(xhtml, self.tv, self, iter_=iter_)
                return iter_
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
            return buffer_.get_iter_at_mark(mark)

        if not mark:
            iter_ = buffer_.get_end_iter()
        else:
            iter_ = buffer_.get_iter_at_mark(mark)

        # detect urls formatting and if the user has it on emoticons
        return self.detect_and_print_special_text(text, text_tags, graphics=graphics,
            iter_=iter_, additional_data=additional_data)


class MessageLine:
    def __init__(self, id_, timestamp, message_icons, start_mark):
        self.id = id_
        self.timestamp = timestamp
        self.start_mark = start_mark
        self._has_receipt = False
        self._has_displayed = False
        self._message_icons = message_icons

    @property
    def has_receipt(self):
        return self._has_receipt

    @property
    def has_displayed(self):
        return self._has_displayed

    def set_receipt(self):
        self._has_receipt = True
        if self._has_displayed:
            return
        self._message_icons.set_receipt_icon_visible(True)

    def set_displayed(self):
        self._has_displayed = True
        self._message_icons.set_displayed_icon_visible(True)

    def set_correction(self, tooltip):
        self._message_icons.set_correction_icon_visible(True)
        self._message_icons.set_correction_tooltip(tooltip)

    def set_error(self, tooltip):
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)


class MessageIcons(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU)
        self._correction_image.set_no_show_all(True)

        self._marker_image = Gtk.Image.new_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.get_style_context().add_class(
            'receipt-received-color')
        self._marker_image.set_tooltip_text(_('Received'))
        self._marker_image.set_no_show_all(True)

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._correction_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_receipt_icon_visible(self, visible):
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)

    def set_displayed_icon_visible(self, visible):
        self._marker_image.set_visible(visible)
        self._marker_image.set_from_icon_name(
            'feather-check-double-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_tooltip_text(Q_('?Message state:Read'))

    def set_correction_icon_visible(self, visible):
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text):
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible):
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text):
        self._error_image.set_tooltip_markup(text)
