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

import logging
from urllib.parse import quote

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import i18n
from gajim.common.const import StyleAttr
from gajim.common.const import URI_SCHEMES
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import open_uri
from gajim.common.helpers import puny_encode_url
from gajim.common.helpers import reduce_chars_newlines
from gajim.common.i18n import _
from gajim.common.regex import STH_AT_STH_DOT_STH_REGEX
from gajim.common.regex import BASIC_REGEX
from gajim.common.regex import LINK_REGEX
from gajim.common.regex import EMOT_AND_BASIC_REGEX
from gajim.common.regex import EMOT_AND_LINK_REGEX

from .htmltextview import HtmlTextView
from .emoji_data import emoji_pixbufs
from .emoji_data import is_emoji
from .emoji_data import get_emoji_pixbuf
from .util import get_cursor

log = logging.getLogger('gajim.gui.conversation_view')


class ConversationTextview(HtmlTextView):

    __gsignals__ = {
        'quote': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
    }

    def __init__(self, account, history_mode=False):
        HtmlTextView.__init__(self, account)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_margin_start(0)
        self.set_margin_end(0)
        self.set_border_width(0)
        self.set_left_margin(0)
        self.set_right_margin(0)

        self._history_mode = history_mode

        self.handlers = {}

        id_ = self.connect('query-tooltip', self._query_tooltip)
        self.handlers[id_] = self
        id_ = self.connect('button-press-event', self._on_button_press)
        self.handlers[id_] = self
        id_ = self.connect('populate-popup', self._on_populate_popup)
        self.handlers[id_] = self

        # Used for changing the mouse pointer when hovering clickable URIs
        self._cursor_changed = False

        # Keeps text selections for quoting and search actions
        self._selected_text = ''

        self.get_style_context().add_class('gajim-conversation-font')

        buffer_ = self.get_buffer()

        self.tag_in = buffer_.create_tag('incoming')
        color = app.css_config.get_value(
            '.gajim-incoming-nickname', StyleAttr.COLOR)
        self.tag_in.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-incoming-nickname')
        self.tag_in.set_property('font-desc', desc)

        self.tag_out = buffer_.create_tag('outgoing')
        color = app.css_config.get_value(
            '.gajim-outgoing-nickname', StyleAttr.COLOR)
        self.tag_out.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-outgoing-nickname')
        self.tag_out.set_property('font-desc', desc)

        self.tag_status = buffer_.create_tag('status')
        color = app.css_config.get_value(
            '.gajim-status-message', StyleAttr.COLOR)
        self.tag_status.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-status-message')
        self.tag_status.set_property('font-desc', desc)

        tag_in_text = buffer_.create_tag('incomingtxt')
        color = app.css_config.get_value(
            '.gajim-incoming-message-text', StyleAttr.COLOR)
        if color:
            tag_in_text.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-incoming-message-text')
        tag_in_text.set_property('font-desc', desc)

        tag_out_text = buffer_.create_tag('outgoingtxt')
        color = app.css_config.get_value(
            '.gajim-outgoing-message-text', StyleAttr.COLOR)
        if color:
            tag_out_text.set_property('foreground', color)
        desc = app.css_config.get_font('.gajim-outgoing-message-text')
        tag_out_text.set_property('font-desc', desc)

        self.tag_marked = buffer_.create_tag('marked')
        color = app.css_config.get_value(
            '.gajim-highlight-message', StyleAttr.COLOR)
        self.tag_marked.set_property('foreground', color)
        self.tag_marked.set_property('weight', Pango.Weight.BOLD)

        tag = buffer_.create_tag('small')
        tag.set_property('scale', 0.8333333333333)

        tag = buffer_.create_tag('bold')
        tag.set_property('weight', Pango.Weight.BOLD)

        tag = buffer_.create_tag('italic')
        tag.set_property('style', Pango.Style.ITALIC)

        tag = buffer_.create_tag('strikethrough')
        tag.set_property('strikethrough', True)

        self.create_tags()

        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args):
        super()._on_destroy()
        for i in self.handlers:
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
        self.handlers.clear()

    def update_text_tags(self):
        self.tag_in.set_property('foreground', app.css_config.get_value(
            '.gajim-incoming-nickname', StyleAttr.COLOR))
        self.tag_out.set_property('foreground', app.css_config.get_value(
            '.gajim-outgoing-nickname', StyleAttr.COLOR))
        self.tag_status.set_property('foreground', app.css_config.get_value(
            '.gajim-status-message', StyleAttr.COLOR))
        self.tag_marked.set_property('foreground', app.css_config.get_value(
            '.gajim-highlight-message', StyleAttr.COLOR))
        self.update_tags()

    def clear(self):
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)

    def get_text(self):
        buffer_ = self.get_buffer()
        start, end = buffer_.get_bounds()
        return buffer_.get_text(start, end, False)

    def print_text(self, text, other_text_tags=None, kind=None, graphics=True,
                   name=None, additional_data=None):
        if additional_data is None:
            additional_data = AdditionalDataDict()

        # Print XHTML if present
        xhtml = additional_data.get_value('gajim', 'xhtml', False)
        if xhtml and app.settings.get('show_xhtml'):
            try:
                if (name and (text.startswith('/me ') or
                              text.startswith('/me\n'))):
                    xhtml = xhtml.replace('/me', '<i>* %s</i>' % (name,), 1)
                self.display_html(
                    xhtml, self, self)
                return
            except Exception as err:
                log.debug('Error processing xhtml: %s', err)
                log.debug('with |%s|', xhtml)

        text_tags = []
        if other_text_tags:
            text_tags = other_text_tags[:]  # create a new list

        if (kind == 'status' or
                text.startswith('/me') or text.startswith('/me\n')):
            text_tags.append(kind)

        if name and (text.startswith('/me ') or text.startswith('/me\n')):
            text = '* ' + name + text[3:]
            text_tags.append('italic')

        if kind in ('incoming', 'incoming_queue'):
            text_tags.append('incomingtxt')
        elif kind == 'outgoing':
            text_tags.append('outgoingtxt')

        self.parse_formatting(
            text, text_tags, graphics=graphics, additional_data=additional_data)

    def parse_formatting(self, text, text_tags, graphics=True,
                         additional_data=None):
        '''
        Parses message formatting (Emojis, URIs, Styles).
        A regex is used for text matching. Each text fragment gets
        passed to apply_formatting(), where respective TextTags are added.
        Unformatted text (no match) will be passed through unaltered.
        '''
        if not text:
            return

        if text_tags is None:
            text_tags = []

        buffer_ = self.get_buffer()

        if text_tags:
            insert_tags_func = buffer_.insert_with_tags_by_name
        else:
            insert_tags_func = buffer_.insert

        # TODO: Adapt HtmlHandler.handle_specials()
        # detect_and_print_special_text() is used by
        # HtmlHandler.handle_specials() and uses Gtk.TextTag objects,
        # not strings
        if text_tags and isinstance(text_tags[0], Gtk.TextTag):
            insert_tags_func = buffer_.insert_with_tags

        # TODO: Plugin system GUI extension point
        # self.plugin_modified = False
        # app.plugin_manager.extension_point('print_real_text', self,
        #    text, text_tags, graphics, additional_data)
        # if self.plugin_modified:
        #    return

        # Add XEP-0066 Out of Band text to the end
        oob_url = additional_data.get_value('gajim', 'oob_url')
        if oob_url is not None:
            oob_desc = additional_data.get_value('gajim', 'oob_desc', 'URL:')
            if oob_url != text:
                text += f'\n{oob_desc} {oob_url}'

        if app.settings.get('emoticons_theme') and graphics:
            # Match for Emojis & URIs
            if app.settings.get('ascii_formatting'):
                regex = EMOT_AND_BASIC_REGEX
            else:
                regex = EMOT_AND_LINK_REGEX
        else:
            if app.settings.get('ascii_formatting'):
                # Match for URIs + mail + formatting
                regex = BASIC_REGEX
            else:
                # Match only for URIs + formatting
                regex = LINK_REGEX

        iterator = regex.finditer(text)
        end_iter = buffer_.get_end_iter()
        # TODO: Evaluate limit
        # Too many fragments (emoticons, LaTeX formulas, etc)
        # may cause Gajim to freeze (see #5129).
        # We impose an arbitrary limit of 100 fragments per message.
        fragment_limit = 100
        index = 0
        for match in iterator:
            start, end = match.span()
            fragment = text[start:end]
            if start > index:
                text_before_fragment = text[index:start]
                end_iter = buffer_.get_end_iter()
                if text_tags:
                    insert_tags_func(
                        end_iter, text_before_fragment, *text_tags)
                else:
                    buffer_.insert(end_iter, text_before_fragment)
            index = end

            self.apply_formatting(fragment,
                                  text_tags,
                                  graphics=graphics,
                                  additional_data=additional_data)
            fragment_limit += 1
            if fragment_limit <= 0:
                break

        # Add remaining text after last match
        insert_tags_func(buffer_.get_end_iter(), text[index:], *text_tags)

    def apply_formatting(self, fragment, text_tags, graphics=True,
                         additional_data=None):
        # TODO: Plugin system GUI extension point
        # self.plugin_modified = False
        # app.plugin_manager.extension_point('print_special_text', self,
        #    fragment, text_tags, graphics, additional_data)
        # if self.plugin_modified:
        #     return

        tags = []
        buffer_ = self.get_buffer()
        ttt = buffer_.get_tag_table()

        # Detect XHTML-IM link
        is_xhtml_uri = False
        tags_ = [
            (ttt.lookup(t) if isinstance(t, str) else t) for t in text_tags]
        for tag in tags_:
            is_xhtml_uri = getattr(tag, 'href', False)
            if is_xhtml_uri:
                break

        # Check if we accept this as an uri
        is_valid_uri = fragment.startswith(tuple(URI_SCHEMES))

        end_iter = buffer_.get_end_iter()

        theme = app.settings.get('emoticons_theme')
        show_emojis = theme and theme != 'font'

        # XEP-0393 Message Styling
        # * = bold
        # _ = italic
        # ~ = strikethrough
        show_formatting_chars = app.settings.get(
            'show_ascii_formatting_chars')

        if show_emojis and graphics and is_emoji(fragment):
            # it's an emoticon
            if emoji_pixbufs.complete:
                # only search for the pixbuf if we are sure
                # that loading is completed
                pixbuf = get_emoji_pixbuf(fragment)
                if pixbuf is None:
                    buffer_.insert(end_iter, fragment)
                else:
                    pixbuf = pixbuf.copy()
                    anchor = buffer_.create_child_anchor(end_iter)
                    anchor.plaintext = fragment
                    img = Gtk.Image.new_from_pixbuf(pixbuf)
                    img.show()
                    self.add_child_at_anchor(img, anchor)
            else:
                # Set marks and save them so we can replace emojis
                # once the loading is complete
                start_mark = buffer_.create_mark(None, end_iter, True)
                buffer_.insert(end_iter, fragment)
                end_mark = buffer_.create_mark(None, end_iter, True)
                emoji_pixbufs.append_marks(
                    self, start_mark, end_mark, fragment)
        elif (fragment.startswith('www.') or
                fragment.startswith('ftp.') or
                is_valid_uri and not is_xhtml_uri):
            tags.append('url')
        elif fragment.startswith('mailto:') and not is_xhtml_uri:
            tags.append('mail')
        elif fragment.startswith('xmpp:') and not is_xhtml_uri:
            tags.append('xmpp')
        elif STH_AT_STH_DOT_STH_REGEX.match(fragment) and not is_xhtml_uri:
            # JID or E-Mail
            tags.append('sth_at_sth')
        elif fragment.startswith('*'):
            tags.append('bold')
            if (fragment[1] == '~' and fragment[-2] == '~' and
                    len(fragment) > 4):
                tags.append('strikethrough')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            elif (fragment[1] == '_' and fragment[-2] == '_' and
                    len(fragment) > 4):
                tags.append('italic')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            else:
                if not show_formatting_chars:
                    fragment = fragment[1:-1]
        elif fragment.startswith('~'):
            tags.append('strikethrough')
            if (fragment[1] == '*' and fragment[-2] == '*' and
                    len(fragment) > 4):
                tags.append('bold')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            elif (fragment[1] == '_' and fragment[-2] == '_' and
                    len(fragment) > 4):
                tags.append('italic')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            else:
                if not show_formatting_chars:
                    fragment = fragment[1:-1]
        elif fragment.startswith('_'):
            tags.append('italic')
            if (fragment[1] == '*' and fragment[-2] == '*' and
                    len(fragment) > 4):
                tags.append('bold')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            elif (fragment[1] == '~' and fragment[-2] == '~' and
                    len(fragment) > 4):
                tags.append('strikethrough')
                if not show_formatting_chars:
                    fragment = fragment[2:-2]
            else:
                if not show_formatting_chars:
                    fragment = fragment[1:-1]
        else:
            insert_tags_func = buffer_.insert_with_tags_by_name
            if text_tags and isinstance(text_tags[0], Gtk.TextTag):
                insert_tags_func = buffer_.insert_with_tags
            if text_tags:
                insert_tags_func(end_iter, fragment, *text_tags)
            else:
                buffer_.insert(end_iter, fragment)

        if tags:
            all_tags = tags[:]
            all_tags += text_tags
            # convert all names to TextTag
            all_tags = [
                (ttt.lookup(t) if isinstance(t, str) else t) for t in all_tags]
            buffer_.insert_with_tags(end_iter, fragment, *all_tags)
            if 'url' in tags:
                puny_text = puny_encode_url(fragment)
                if puny_text != fragment:
                    puny_tags = []
                    if not puny_text:
                        puny_text = _('Invalid URL')
                    puny_tags = [(ttt.lookup(t) if isinstance(
                        t, str) else t) for t in puny_tags]
                    puny_tags += text_tags
                    buffer_.insert_with_tags(
                        end_iter, " (%s)" % puny_text, *puny_tags)

    def _query_tooltip(self, widget, x_pos, y_pos, _keyboard_mode, tooltip):
        window = widget.get_window(Gtk.TextWindowType.TEXT)
        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)

        iter_ = self.get_iter_at_position(x_pos, y_pos)[1]
        for tag in iter_.get_tags():
            tag_name = tag.get_property('name')
            if getattr(tag, 'is_anchor', False):
                text = getattr(tag, 'title', False)
                if text:
                    if len(text) > 50:
                        text = reduce_chars_newlines(text, 47, 1)
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

    def _on_button_press(self, _widget, event):
        '''
        We don’t open the standard context menu when receiving
        a click on tagged text.
        If it’s untagged text, check if something is selected
        '''
        self._selected_text = ''

        if event.button != 3:
            # If it’s not a right click
            return False

        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT,
            int(event.x),
            int(event.y))
        iter_ = self.get_iter_at_location(x_pos, y_pos)
        if isinstance(iter_, tuple):
            iter_ = iter_[1]
        tags = iter_.get_tags()

        if tags:
            # A tagged text fragment has been clicked
            for tag in tags:
                tag_name = tag.get_property('name')
                if tag_name in ('url', 'mail', 'xmpp', 'sth_at_sth'):
                    # Block regular context menu
                    return True

        # Check if there is a selection and make it available for
        # _on_populate_popup
        buffer_ = self.get_buffer()
        return_val = buffer_.get_selection_bounds()
        if return_val:
            # Something has been selected, get the text
            start_sel, finish_sel = return_val[0], return_val[1]
            self._selected_text = buffer_.get_text(
                start_sel, finish_sel, True)
        elif iter_.get_char() and ord(iter_.get_char()) > 31:
            # Clicked on a word, take whole word for selection
            start_sel = iter_.copy()
            if not start_sel.starts_word():
                start_sel.backward_word_start()
            finish_sel = iter_.copy()
            if not finish_sel.ends_word():
                finish_sel.forward_word_end()
            self._selected_text = buffer_.get_text(
                start_sel, finish_sel, True)
        return False

    def _on_populate_popup(self, _textview, menu):
        '''
        Overrides the default context menu.
        If text is selected, a submenu with actions on the selection is added.
        (see _on_button_press)
        '''
        if not self._selected_text:
            menu.show_all()
            return

        if not self._history_mode:
            item = Gtk.MenuItem.new_with_mnemonic(_('_Quote'))
            id_ = item.connect('activate', self._on_quote)
            self.handlers[id_] = item
            menu.prepend(item)

        selected_text_short = reduce_chars_newlines(
            self._selected_text, 25, 2)
        item = Gtk.MenuItem.new_with_mnemonic(
            _('_Actions for "%s"') % selected_text_short)
        menu.prepend(item)
        submenu = Gtk.Menu()
        item.set_submenu(submenu)
        uri_text = quote(self._selected_text.encode('utf-8'))

        if app.settings.get('always_english_wikipedia'):
            uri = (f'https://en.wikipedia.org/wiki/'
                   f'Special:Search?search={uri_text}')
        else:
            uri = (f'https://{i18n.get_short_lang_code()}.wikipedia.org/'
                   f'wiki/Special:Search?search={uri_text}')
        item = Gtk.MenuItem.new_with_mnemonic(_('Read _Wikipedia Article'))
        id_ = item.connect('activate', self._visit_uri, uri)
        self.handlers[id_] = item
        submenu.append(item)

        item = Gtk.MenuItem.new_with_mnemonic(
            _('Look it up in _Dictionary'))
        dict_link = app.settings.get('dictionary_url')
        if dict_link == 'WIKTIONARY':
            # Default is wikitionary.org
            if app.settings.get('always_english_wiktionary'):
                uri = (f'https://en.wiktionary.org/wiki/'
                       f'Special:Search?search={uri_text}')
            else:
                uri = (f'https://{i18n.get_short_lang_code()}.wiktionary.org/'
                       f'wiki/Special:Search?search={uri_text}')
            id_ = item.connect('activate', self._visit_uri, uri)
            self.handlers[id_] = item
        else:
            if dict_link.find('%s') == -1:
                # There has to be a '%s' in the url if it’s not WIKTIONARY
                item = Gtk.MenuItem.new_with_label(
                    _('Dictionary URL is missing a "%s"'))
                item.set_sensitive(False)
            else:
                uri = dict_link % uri_text
                id_ = item.connect('activate', self._visit_uri, uri)
                self.handlers[id_] = item
        submenu.append(item)

        search_link = app.settings.get('search_engine')
        if search_link.find('%s') == -1:
            # There has to be a '%s' in the url
            item = Gtk.MenuItem.new_with_label(
                _('Web Search URL is missing a "%s"'))
            item.set_sensitive(False)
        else:
            item = Gtk.MenuItem.new_with_mnemonic(_('Web _Search for it'))
            uri = search_link % uri_text
            id_ = item.connect('activate', self._visit_uri, uri)
            self.handlers[id_] = item
        submenu.append(item)

        item = Gtk.MenuItem.new_with_mnemonic(_('Open as _Link'))
        id_ = item.connect('activate', self._visit_uri, uri)
        self.handlers[id_] = item
        submenu.append(item)

        menu.show_all()

    def _on_quote(self, _widget):
        self.emit('quote', self._selected_text)

    @staticmethod
    def _visit_uri(_widget, uri):
        open_uri(uri)
