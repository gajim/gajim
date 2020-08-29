# Copyright (C) 2005 Gustavo J. A. M. Carneiro
# Copyright (C) 2006 Santiago Gala
# Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Nikos Kouremenos <kourem AT gmail.com>
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

"""
A Gtk.TextView-based renderer for XHTML-IM, as described in:
  http://xmpp.org/extensions/xep-0071.html

Starting with the version posted by Gustavo Carneiro,
I (Santiago Gala) am trying to make it more compatible
with the markup that docutils generate, and also more
modular.
"""

import re
import logging
import xml.sax
import xml.sax.handler
from io import StringIO

from gi.repository import GObject
from gi.repository import Pango
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common.const import StyleAttr
from gajim.common.helpers import open_uri
from gajim.common.helpers import parse_uri
from gajim.gtk.util import get_cursor

from gajim.gui_menu_builder import get_conv_context_menu

log = logging.getLogger('gajim.htmlview')

whitespace_rx = re.compile('\\s+')
allwhitespace_rx = re.compile('^\\s*$')

# embryo of CSS classes
classes = {
    #'system-message':';display: none',
    'problematic': ';color: red',
}

# styles for elements
_element_styles = {
    'u'             : ';text-decoration: underline',
    'em'            : ';font-style: oblique',
    'cite'          : '; background-color:rgb(170,190,250);'
                      'font-style: oblique',
    'li'            : '; margin-left: 1em; margin-right: 10%',
    'strong'        : ';font-weight: bold',
    'pre'           : '; background-color:rgb(190,190,190);'
                      'font-family: monospace; white-space: pre;'
                      'margin-left: 1em; margin-right: 10%',
    'kbd'           : ';background-color:rgb(210,210,210);'
                      'font-family: monospace',
    'blockquote'    : '; background-color:rgb(170,190,250);'
                      'margin-left: 2em; margin-right: 10%',
    'dt'            : ';font-weight: bold; font-style: oblique',
    'dd'            : ';margin-left: 2em; font-style: oblique'
}
# no difference for the moment
_element_styles['dfn'] = _element_styles['em']
_element_styles['var'] = _element_styles['em']
# deprecated, legacy, presentational
_element_styles['tt'] = _element_styles['kbd']
_element_styles['i'] = _element_styles['em']
_element_styles['b'] = _element_styles['strong']

_supported_style_attrs = [
    'background-color', 'color', 'font-family', 'font-size', 'font-style',
    'font-weight', 'margin-left', 'margin-right', 'text-align',
    'text-decoration', 'white-space', 'display', 'width', 'height'
]

# ==========
#   XEP-0071
# ==========
#
# This Integration Set includes a subset of the modules defined for
# XHTML 1.0 but does not redefine any existing modules, nor
# does it define any new modules. Specifically, it includes the
# following modules only:
#
# - Structure
# - Text
#
#   * Block
#
#     phrasal
#        addr, blockquote, pre
#     Struct
#        div,p
#     Heading
#        h1, h2, h3, h4, h5, h6
#
#   * Inline
#
#     phrasal
#        abbr, acronym, cite, code, dfn, em, kbd, q, samp, strong, var
#     structural
#        br, span
#
# - Hypertext (a)
# - List (ul, ol, dl)
# - Image (img)
# - Style Attribute
#
# Therefore XHTML-IM uses the following content models:
#
#   Block.mix
#             Block-like elements, e.g., paragraphs
#   Flow.mix
#             Any block or inline elements
#   Inline.mix
#             Character-level elements
#   InlineNoAnchor.class
#                       Anchor element
#   InlinePre.mix
#             Pre element
#
# XHTML-IM also uses the following Attribute Groups:
#
# Core.extra.attrib
#       TBD
# I18n.extra.attrib
#       TBD
# Common.extra
#       style
#
#
# ...
# block level:
# Heading    h
#            ( head           = h1 | h2 | h3 | h4 | h5 | h6 )
# Block      ( phrasal        = address | blockquote | pre )
# NOT           ( presentational = hr )
#            ( structural     = div | p )
# other:     section
# Inline     ( phrasal        = abbr | acronym | cite | code | dfn | em |
#                               kbd | q | samp | strong | var )
# NOT        ( presentational =  b  | big | i | small | sub | sup | tt )
#            ( structural     =  br | span )
# Param/Legacy    param, font, basefont, center, s, strike, u, dir, menu,
#                 isindex

BLOCK_HEAD = set(('h1', 'h2', 'h3', 'h4', 'h5', 'h6',))
BLOCK_PHRASAL = set(('address', 'blockquote', 'pre',))
BLOCK_PRES = set(('hr', )) #not in xhtml-im
BLOCK_STRUCT = set(('div', 'p', ))
BLOCK_HACKS = set(('table', 'tr')) # at the very least, they will start line ;)
BLOCK = BLOCK_HEAD | BLOCK_PHRASAL | BLOCK_STRUCT | BLOCK_PRES | BLOCK_HACKS

INLINE_PHRASAL = set(['abbr', 'acronym', 'cite', 'code', 'dfn', 'em',
                      'kbd', 'q', 'samp', 'strong', 'var'])
INLINE_PRES = set(['b', 'i', 'u', 'tt']) #not in xhtml-im
INLINE_STRUCT = set(['br', 'span'])
INLINE = INLINE_PHRASAL | INLINE_PRES | INLINE_STRUCT

LIST_ELEMS = set(['dl', 'ol', 'ul'])

for _name in BLOCK_HEAD:
    _num = int(_name[1])
    _header_size = (_num - 1) // 2
    _weight = (_num - 1) % 2
    _element_styles[_name] = '; font-size: %s; %s' % (
        ('large', 'medium', 'small')[_header_size],
        ('font-weight: bold', 'font-style: oblique')[_weight])

def _parse_css_color(color):
    rgba = Gdk.RGBA()
    success = rgba.parse(color)
    if not success:
        log.warning('Can\'t parse color: %s', color)
    return rgba

def style_iter(style):
    for item in style.split(';'):
        if item.strip():
            yield [x.strip() for x in item.split(':', 1)]


class HtmlHandler(xml.sax.handler.ContentHandler):
    """
    A handler to display html to a gtk textview

    It keeps a stack of "style spans" (start/end element pairs) and a stack of
    list counters, for nested lists.
    """
    def __init__(self, textview, conv_textview, startiter):
        xml.sax.handler.ContentHandler.__init__(self)
        self.textbuf = textview.get_buffer()
        self.textview = textview
        self.iter = startiter
        self.conv_textview = conv_textview
        self.text = ''
        self.starting = True
        self.preserve = False
        self.styles = [] # a Gtk.TextTag or None, for each span level
        self.list_counters = [] # stack (top at head) of list
                                # counters, or None for unordered list

        # build a dictionary mapping styles to methods
        self.__style_methods = {}
        for style in _supported_style_attrs:
            method_names = '_parse_style_%s' % style.replace('-', '_')
            self.__style_methods[style] = method_names

    def _get_points_from_pixels(self, pixels):
        resolution = self.textview.get_screen().get_resolution()
        # points = pixels * 72 / resolution
        return pixels * 72 / resolution

    @staticmethod
    def _parse_style_color(tag, value):
        color = _parse_css_color(value)
        tag.set_property('foreground-rgba', color)

    @staticmethod
    def _parse_style_background_color(tag, value):
        color = _parse_css_color(value)
        tag.set_property('background-rgba', color)
        tag.set_property('paragraph-background-rgba', color)

    @staticmethod
    def __parse_length_frac_size_allocate(_textview, allocation, frac,
                                          callback, args):
        callback(allocation.width*frac, *args)

    def _parse_length(self, value, font_relative, block_relative, minl, maxl,
                      callback, *args):
        """
        Parse/calc length, converting to pixels, calls callback(length, *args)
        when the length is first computed or changes
        """
        if value.endswith('%'):
            val = float(value[:-1])
            if val > 0:
                sign = 1
            elif val < 0:
                sign = -1
            else:
                sign = 0
            # limits: 1% to 500%
            val = sign*max(1, min(abs(val), 500))
            frac = val/100
            if font_relative:
                callback(frac, '%', *args)
            elif block_relative:
                # CSS says 'Percentage values: refer to width of the closest
                #           block-level ancestor'
                # This is difficult/impossible to implement, so we use
                # textview width instead; a reasonable approximation..
                alloc = self.textview.get_allocation()
                self.__parse_length_frac_size_allocate(
                    self.textview, alloc, frac, callback, args)
                self.textview.connect('size-allocate',
                                      self.__parse_length_frac_size_allocate,
                                      frac, callback, args)
            else:
                callback(frac, *args)
            return

        def get_val(min_val=minl, max_val=maxl):
            try:
                val = float(value[:-2])
            except Exception:
                log.warning('Unable to parse length value "%s"', value)
                return None
            if val > 0:
                sign = 1
            elif val < 0:
                sign = -1
            else:
                sign = 0
            # validate length
            return sign*max(min_val, min(abs(val), max_val))
        if value.endswith('pt'):  # points
            size = get_val(5, 50)
            if size is None:
                return
            callback(size, 'pt', *args)

        elif value.endswith('em'):
            size = get_val(0.3, 4)
            if size is None:
                return
            callback(size, 'em', *args)

        elif value.endswith('px'):  # pixels
            size = get_val(5, 50)
            if size is None:
                return
            callback(size, 'px', *args)

        else:
            try:
                # TODO: isn't "no units" interpreted as pixels?
                val = int(value)
                if val > 0:
                    sign = 1
                elif val < 0:
                    sign = -1
                else:
                    sign = 0
                # validate length
                val = sign*max(5, min(abs(val), 70))
                callback(val, 'px', *args)
            except Exception:
                log.warning('Unable to parse length value "%s"', value)

    def __parse_font_size_cb(self, size, type_, tag):
        if type_ in ('em', '%'):
            tag.set_property('scale', size)
        elif type_ == 'pt':
            tag.set_property('size-points', size)
        elif type_ == 'px':
            tag.set_property('size-points', self._get_points_from_pixels(size))

    @staticmethod
    def _parse_style_display(tag, value):
        if value == 'none':
            tag.set_property('invisible', 'true')
        # FIXME: display: block, inline

    def _parse_style_font_size(self, tag, value):
        try:
            scale = {
                'xx-small': 0.5787037037037,
                'x-small': 0.6444444444444,
                'small': 0.8333333333333,
                'medium': 1.0,
                'large': 1.2,
                'x-large': 1.4399999999999,
                'xx-large': 1.728,
            }[value]
        except KeyError:
            pass
        else:
            tag.set_property('scale', scale)
            return
        if value == 'smaller':
            tag.set_property('scale', 0.8333333333333)
            return
        if value == 'larger':
            tag.set_property('scale', 1.2)
            return
        # font relative (5 ~ 4pt, 110 ~ 72pt)
        self._parse_length(
            value, True, False, 5, 110, self.__parse_font_size_cb, tag)

    @staticmethod
    def _parse_style_font_style(tag, value):
        try:
            style = {
                'normal': Pango.Style.NORMAL,
                'italic': Pango.Style.ITALIC,
                'oblique': Pango.Style.OBLIQUE,
            }[value]
        except KeyError:
            log.warning('unknown font-style %s', value)
        else:
            tag.set_property('style', style)

    def __frac_length_tag_cb(self, length, tag, propname):
        styles = self._get_style_tags()
        if styles:
            length += styles[-1].get_property(propname)
        tag.set_property(propname, length)

    def _parse_style_margin_left(self, tag, value):
        # block relative
        self._parse_length(value, False, True, 1, 1000,
                           self.__frac_length_tag_cb, tag, 'left-margin')

    def _parse_style_margin_right(self, tag, value):
        # block relative
        self._parse_length(value, False, True, 1, 1000,
                           self.__frac_length_tag_cb, tag, 'right-margin')

    @staticmethod
    def _parse_style_font_weight(tag, value):
        # TODO: missing 'bolder' and 'lighter'
        try:
            weight = {
                '100': Pango.Weight.ULTRALIGHT,
                '200': Pango.Weight.ULTRALIGHT,
                '300': Pango.Weight.LIGHT,
                '400': Pango.Weight.NORMAL,
                '500': Pango.Weight.NORMAL,
                '600': Pango.Weight.BOLD,
                '700': Pango.Weight.BOLD,
                '800': Pango.Weight.ULTRABOLD,
                '900': Pango.Weight.HEAVY,
                'normal': Pango.Weight.NORMAL,
                'bold': Pango.Weight.BOLD,
            }[value]
        except KeyError:
            log.warning('unknown font-style %s', value)
        else:
            tag.set_property('weight', weight)

    @staticmethod
    def _parse_style_font_family(tag, value):
        tag.set_property('family', value)

    @staticmethod
    def _parse_style_text_align(tag, value):
        try:
            align = {
                'left': Gtk.Justification.LEFT,
                'right': Gtk.Justification.RIGHT,
                'center': Gtk.Justification.CENTER,
                'justify': Gtk.Justification.FILL,
            }[value]
        except KeyError:
            log.warning('Invalid text-align: %s requested', value)
        else:
            tag.set_property('justification', align)

    @staticmethod
    def _parse_style_text_decoration(tag, value):
        values = value.split(' ')
        if 'none' in values:
            tag.set_property('underline', Pango.Underline.NONE)
            tag.set_property('strikethrough', False)
        if 'underline' in values:
            tag.set_property('underline', Pango.Underline.SINGLE)
        else:
            tag.set_property('underline', Pango.Underline.NONE)
        if 'line-through' in values:
            tag.set_property('strikethrough', True)
        else:
            tag.set_property('strikethrough', False)
        if 'blink' in values:
            log.warning('text-decoration:blink not implemented')
        if 'overline' in values:
            log.warning('text-decoration:overline not implemented')

    @staticmethod
    def _parse_style_white_space(tag, value):
        if value == 'pre':
            tag.set_property('wrap_mode', Gtk.WrapMode.NONE)
        elif value == 'normal':
            tag.set_property('wrap_mode', Gtk.WrapMode.WORD)
        elif value == 'nowrap':
            tag.set_property('wrap_mode', Gtk.WrapMode.NONE)

    @staticmethod
    def __length_tag_cb(value, tag, propname):
        try:
            tag.set_property(propname, value)
        except Exception:
            log.warning('Error with prop: %s for tag: %s', propname, str(tag))

    def _parse_style_width(self, tag, value):
        if value == 'auto':
            return
        self._parse_length(value, False, False, 1, 1000,
                           self.__length_tag_cb, tag, "width")
    def _parse_style_height(self, tag, value):
        if value == 'auto':
            return
        self._parse_length(value, False, False, 1, 1000,
                           self.__length_tag_cb, tag, "height")

    def _get_style_tags(self):
        return [tag for tag in self.styles if tag is not None]

    def _create_url(self, href, title, type_, id_):
        '''Process a url tag.
        '''
        tag = self.textbuf.create_tag(id_)
        if href and href[0] != '#':
            tag.href = href
            tag.type_ = type_ # to be used by the URL handler
            tag.connect('event', self.textview.hyperlink_handler, 'url')
            tag.set_property('foreground',
                             app.css_config.get_value('.gajim-url',
                                                      StyleAttr.COLOR))
            tag.set_property('underline', Pango.Underline.SINGLE)
            tag.is_anchor = True
        if title:
            tag.title = title
        return tag

    def _begin_span(self, style, tag=None, id_=None):
        if style is None:
            self.styles.append(tag)
            return
        if tag is None:
            if id_:
                tag = self.textbuf.create_tag(id_)
            else:
                tag = self.textbuf.create_tag() # we create anonymous tag
        for attr, val in style_iter(style):
            attr = attr.lower()
            try:
                getattr(self, self.__style_methods[attr])(tag, val)
            except KeyError:
                log.warning('Style attribute "%s" requested '
                            'but not yet implemented', attr)
        self.styles.append(tag)

    def _end_span(self):
        self.styles.pop()

    def _jump_line(self):
        self.textbuf.insert_with_tags_by_name(self.iter, '\n', 'eol')
        self.starting = True

    def _insert_text(self, text, working_iter=None):
        if working_iter is None:
            working_iter = self.iter
        if self.starting and text != '\n':
            self.starting = (text[-1] == '\n')
        tags = self._get_style_tags()
        if tags:
            self.textbuf.insert_with_tags(working_iter, text, *tags)
        else:
            self.textbuf.insert(working_iter, text)

    def _starts_line(self):
        return self.starting or self.iter.starts_line()

    def _flush_text(self):
        if not self.text:
            return
        text, self.text = self.text, ''
        if not self.preserve:
            text = text.replace('\n', ' ')
            self.handle_specials(whitespace_rx.sub(' ', text))
        else:
            self._insert_text(text.strip('\n'))

    def _anchor_event(self, _tag, _textview, event, _iter, href, type_):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self.textview.emit('url-clicked', href, type_)
            return True
        return False

    def handle_specials(self, text):
        if self.conv_textview:
            self.iter = self.conv_textview.detect_and_print_special_text(
                text, self._get_style_tags(), iter_=self.iter)
        else:
            self._insert_text(text)

    def characters(self, content):
        if self.preserve:
            self.text += content
            return
        if allwhitespace_rx.match(content) is not None and self._starts_line():
            return
        self.text += content
        self.starting = False

    def startElement(self, name, attrs):
        self._flush_text()
        klass = [i for i in attrs.get('class', ' ').split(' ') if i]
        style = ''
        #Add styles defined for classes
        for k in klass:
            if k  in classes:
                style += classes[k]

        tag = None
        #FIXME: if we want to use id, it needs to be unique across
        # the whole textview, so we need to add something like the
        # message-id to it.
        #id_ = attrs.get('id',None)
        id_ = None
        if name == 'a':
            #TODO: accesskey, charset, hreflang, rel, rev, tabindex, type
            href = attrs.get('href', None)
            if not href:
                href = attrs.get('HREF', None)
            # Gaim sends HREF instead of href
            title = attrs.get('title', attrs.get('rel', href))
            type_ = attrs.get('type', None)
            tag = self._create_url(href, title, type_, id_)
        elif name == 'blockquote':
            cite = attrs.get('cite', None)
            if cite:
                tag = self.textbuf.create_tag(id_)
                tag.title = attrs.get('title', None)
                tag.is_anchor = True
        elif name in LIST_ELEMS:
            style += ';margin-left: 2em'

        if name in _element_styles:
            style += _element_styles[name]
        # so that explicit styles override implicit ones,
        # we add the attribute last
        style += ";"+attrs.get('style', '')
        if style == '':
            style = None
        self._begin_span(style, tag, id_)

        if name == 'br':
            pass # handled in endElement
        elif name == 'hr':
            pass # handled in endElement
        elif name in BLOCK:
            if not self._starts_line():
                self._jump_line()
            if name == 'pre':
                self.preserve = True
        elif name == 'span':
            pass
        elif name in ('dl', 'ul'):
            if not self._starts_line():
                self._jump_line()
            self.list_counters.append(None)
        elif name == 'ol':
            if not self._starts_line():
                self._jump_line()
            self.list_counters.append(0)
        elif name == 'li':
            if self.list_counters[-1] is None:
                li_head = chr(0x2022)
            else:
                self.list_counters[-1] += 1
                li_head = '%i.' % self.list_counters[-1]
            self.text = ' '*len(self.list_counters)*4 + li_head + ' '
            self._flush_text()
            self.starting = True
        elif name == 'dd':
            self._jump_line()
        elif name == 'dt':
            if not self.starting:
                self._jump_line()
        elif name in ('a', 'img', 'body', 'html'):
            pass
        elif name in INLINE:
            pass
        else:
            log.warning('Unhandled element "%s"', name)

    def endElement(self, name):
        end_preserving = False
        newline = False
        if name == 'br':
            newline = True
        elif name == 'hr':
            #FIXME: plenty of unused attributes (width, height,...) :)
            self._jump_line()
            self._insert_text('\u2015'*40)
            self._jump_line()
        elif name in LIST_ELEMS:
            self.list_counters.pop()
        elif name == 'li':
            newline = True
        elif name == 'img':
            pass
        elif name in ('body', 'html'):
            pass
        elif name == 'a':
            pass
        elif name in INLINE:
            pass
        elif name in ('dd', 'dt', ):
            pass
        elif name in BLOCK:
            if name == 'pre':
                end_preserving = True
            elif name in BLOCK_STRUCT:
                newline = True
        else:
            log.warning("Unhandled element '%s'", name)
        self._flush_text()
        if end_preserving:
            self.preserve = False
        if newline:
            self._jump_line()
        self._end_span()


class HtmlTextView(Gtk.TextView):

    _tags = ['url', 'mail', 'xmpp', 'sth_at_sth']

    def __init__(self, account, standalone=False):
        Gtk.TextView.__init__(self)
        self.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.set_editable(False)
        self.set_has_tooltip(True)
        self.connect('copy-clipboard', self._on_copy_clipboard)
        self.get_buffer().eol_tag = self.get_buffer().create_tag('eol')

        self.account = account
        self.plugin_modified = False
        self._cursor_changed = False

        if standalone:
            self.connect('query-tooltip', self._query_tooltip)
            self.create_tags()

    def create_tags(self):
        color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)

        attrs = {'foreground': color,
                 'underline': Pango.Underline.SINGLE}

        for tag in self._tags:
            tag_ = self.get_buffer().create_tag(tag, **attrs)
            tag_.connect('event', self.hyperlink_handler, tag)

    def update_tags(self):
        tag_table = self.get_buffer().get_tag_table()
        color = app.css_config.get_value('.gajim-url', StyleAttr.COLOR)

        for tag in self._tags:
            tag_table.lookup(tag).set_property('foreground', color)

    def _query_tooltip(self, widget, x_pos, y_pos, _keyboard_mode, tooltip):
        window = widget.get_window(Gtk.TextWindowType.TEXT)
        x_pos, y_pos = self.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, x_pos, y_pos)
        iter_ = self.get_iter_at_position(x_pos, y_pos)[1]

        for tag in iter_.get_tags():
            if getattr(tag, 'is_anchor', False):
                text = getattr(tag, 'title', False)
                if text:
                    if len(text) > 50:
                        text = text[:47] + '…'
                    tooltip.set_text(text)
                    window.set_cursor(get_cursor('pointer'))
                    self._cursor_changed = True
                    return True

            tag_name = tag.get_property('name')
            if tag_name in ('url', 'mail', 'xmpp', 'sth_at_sth'):
                window.set_cursor(get_cursor('pointer'))
                self._cursor_changed = True
                return False

        if self._cursor_changed:
            window.set_cursor(get_cursor('text'))
            self._cursor_changed = False
        return False

    def show_context_menu(self, uri):
        menu = get_conv_context_menu(self.account, uri)
        if menu is None:
            log.warning('No handler for URI type: %s', uri)
            return

        def destroy(menu, _pspec):
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu.attach_to_widget(self, None)
        menu.connect('notify::visible', destroy)
        menu.popup_at_pointer()

    def hyperlink_handler(self, texttag, _widget, event, iter_, _kind):
        if event.type != Gdk.EventType.BUTTON_PRESS:
            return Gdk.EVENT_PROPAGATE

        begin_iter = iter_.copy()
        # we get the beginning of the tag
        while not begin_iter.starts_tag(texttag):
            begin_iter.backward_char()
        end_iter = iter_.copy()
        # we get the end of the tag
        while not end_iter.ends_tag(texttag):
            end_iter.forward_char()

        # Detect XHTML-IM link
        word = getattr(texttag, 'href', None)
        if not word:
            word = self.get_buffer().get_text(begin_iter, end_iter, True)

        uri = parse_uri(word)
        if event.button.button == 3: # right click
            self.show_context_menu(uri)
            return Gdk.EVENT_STOP

        self.plugin_modified = False
        app.plugin_manager.extension_point(
            'hyperlink_handler', uri, self, self.get_toplevel())
        if self.plugin_modified:
            return Gdk.EVENT_STOP

        open_uri(uri, account=self.account)
        return Gdk.EVENT_STOP

    def display_html(self, html, textview, conv_textview, iter_=None):
        buffer_ = self.get_buffer()
        if iter_:
            eob = iter_
        else:
            eob = buffer_.get_end_iter()
        parser = xml.sax.make_parser()
        parser.setContentHandler(HtmlHandler(textview, conv_textview, eob))
        parser.parse(StringIO(html))
        # If the xhtml ends with a BLOCK element we have to remove
        # the \n we add after BLOCK elements
        self._delete_last_char(buffer_, eob)

    @staticmethod
    def _delete_last_char(buffer_, iter_):
        start_iter = iter_.copy()
        start_iter.backward_char()
        text = buffer_.get_text(start_iter, iter_, True)
        if text == '\n':
            buffer_.delete(start_iter, iter_)

    @staticmethod
    def _on_copy_clipboard(textview):
        clipboard = textview.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        selected = textview.get_selected_text()
        clipboard.set_text(selected, -1)
        GObject.signal_stop_emission_by_name(textview, 'copy-clipboard')

    def get_selected_text(self):
        bounds = self.get_buffer().get_selection_bounds()
        selection = ''
        if bounds:
            (search_iter, end) = bounds

            while search_iter.compare(end):
                character = search_iter.get_char()
                if character == '\ufffc':
                    anchor = search_iter.get_child_anchor()
                    if anchor:
                        text = anchor.plaintext
                        if text:
                            selection += text
                    else:
                        selection += character
                else:
                    selection += character
                search_iter.forward_char()
        return selection

    def replace_emojis(self, start_mark, end_mark, pixbuf, codepoint):
        buffer_ = self.get_buffer()
        start_iter = buffer_.get_iter_at_mark(start_mark)
        end_iter = buffer_.get_iter_at_mark(end_mark)
        buffer_.delete(start_iter, end_iter)

        anchor = buffer_.create_child_anchor(start_iter)
        anchor.plaintext = codepoint
        emoji = Gtk.Image.new_from_pixbuf(pixbuf)
        emoji.show()
        self.add_child_at_anchor(emoji, anchor)
        buffer_.delete_mark(start_mark)
        buffer_.delete_mark(end_mark)

    def unselect(self):
        buffer_ = self.get_buffer()
        insert_iter = buffer_.get_iter_at_mark(buffer_.get_insert())
        buffer_.select_range(insert_iter, insert_iter)
