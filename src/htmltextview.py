# -*- coding:utf-8 -*-
## src/htmltextview.py
##
## Copyright (C) 2005 Gustavo J. A. M. Carneiro
## Copyright (C) 2006 Santiago Gala
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Nikos Kouremenos <kourem AT gmail.com>
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

'''
A gtk.TextView-based renderer for XHTML-IM, as described in:
  http://www.jabber.org/jeps/jep-0071.html

Starting with the version posted by Gustavo Carneiro,
I (Santiago Gala) am trying to make it more compatible
with the markup that docutils generate, and also more
modular.

'''

import gobject
import pango
import gtk
import xml.sax, xml.sax.handler
import re
import warnings
from cStringIO import StringIO
import socket
import time
import urllib2
import operator

if __name__ == '__main__':
	from common import i18n
	import common.configpaths
	common.configpaths.gajimpaths.init(None)
from common import gajim

import tooltips


__all__ = ['HtmlTextView']

whitespace_rx = re.compile('\\s+')
allwhitespace_rx = re.compile('^\\s*$')

# pixels = points * display_resolution
display_resolution = 0.3514598*(gtk.gdk.screen_height() /
					float(gtk.gdk.screen_height_mm()))

# embryo of CSS classes
classes = {
	#'system-message':';display: none',
	'problematic':';color: red',
}

# styles for elements
element_styles = {
		'u'			: ';text-decoration: underline',
		'em'		: ';font-style: oblique',
		'cite'		: '; background-color:rgb(170,190,250); font-style: oblique',
		'li'		: '; margin-left: 1em; margin-right: 10%',
		'strong'	: ';font-weight: bold',
		'pre'		: '; background-color:rgb(190,190,190); font-family: monospace; white-space: pre; margin-left: 1em; margin-right: 10%',
		'kbd'		: ';background-color:rgb(210,210,210);font-family: monospace',
		'blockquote': '; background-color:rgb(170,190,250); margin-left: 2em; margin-right: 10%',
		'dt'		: ';font-weight: bold; font-style: oblique',
		'dd'		: ';margin-left: 2em; font-style: oblique'
}
# no difference for the moment
element_styles['dfn'] = element_styles['em']
element_styles['var'] = element_styles['em']
# deprecated, legacy, presentational
element_styles['tt']  = element_styles['kbd']
element_styles['i']   = element_styles['em']
element_styles['b']   = element_styles['strong']

# ==========
#   JEP-0071
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
#     Struc
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
# 			Anchor element
#   InlinePre.mix
#             Pre element
#
# XHTML-IM also uses the following Attribute Groups:
#
# Core.extra.attrib
# 	TBD
# I18n.extra.attrib
# 	TBD
# Common.extra
# 	style
#
#
# ...
# block level:
# Heading    h
#            ( pres           = h1 | h2 | h3 | h4 | h5 | h6 )
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

BLOCK_HEAD = set(( 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', ))
BLOCK_PHRASAL = set(( 'address', 'blockquote', 'pre', ))
BLOCK_PRES = set(( 'hr', )) #not in xhtml-im
BLOCK_STRUCT = set(( 'div', 'p', ))
BLOCK_HACKS = set(( 'table', 'tr' )) # at the very least, they will start line ;)
BLOCK = BLOCK_HEAD.union(BLOCK_PHRASAL).union(BLOCK_STRUCT).union(BLOCK_PRES).union(BLOCK_HACKS)

INLINE_PHRASAL = set('abbr, acronym, cite, code, dfn, em, kbd, q, samp, strong, var'.split(', '))
INLINE_PRES = set('b, i, u, tt'.split(', ')) #not in xhtml-im
INLINE_STRUCT = set('br, span'.split(', '))
INLINE = INLINE_PHRASAL.union(INLINE_PRES).union(INLINE_STRUCT)

LIST_ELEMS = set( 'dl, ol, ul'.split(', '))

for name in BLOCK_HEAD:
	num = eval(name[1])
	size = (num-1) // 2
	weigth = (num - 1) % 2
	element_styles[name] = '; font-size: %s; %s' % ( ('large', 'medium', 'small')[size],
													('font-weight: bold', 'font-style: oblique')[weigth],
											  )

def _parse_css_color(color):
	'''_parse_css_color(css_color) -> gtk.gdk.Color'''
	if color.startswith('rgb(') and color.endswith(')'):
		r, g, b = [int(c)*257 for c in color[4:-1].split(',')]
		return gtk.gdk.Color(r, g, b)
	else:
		return gtk.gdk.color_parse(color)

def style_iter(style):
	return ([x.strip() for x in item.split(':', 1)] for item in style.split(';')\
		if len(item.strip()))


class HtmlHandler(xml.sax.handler.ContentHandler):
	"""A handler to display html to a gtk textview.

	It keeps a stack of "style spans" (start/end element pairs)
	and a stack of list counters, for nested lists.
	"""
	def __init__(self, conv_textview, startiter):
		xml.sax.handler.ContentHandler.__init__(self)
		self.textbuf = conv_textview.tv.get_buffer()
		self.textview = conv_textview.tv
		self.iter = startiter
		self.conv_textview = conv_textview
		self.text = ''
		self.starting=True
		self.preserve = False
		self.styles = [] # a gtk.TextTag or None, for each span level
		self.list_counters = [] # stack (top at head) of list
								# counters, or None for unordered list

	def _parse_style_color(self, tag, value):
		color = _parse_css_color(value)
		tag.set_property('foreground-gdk', color)

	def _parse_style_background_color(self, tag, value):
		color = _parse_css_color(value)
		tag.set_property('background-gdk', color)
		tag.set_property('paragraph-background-gdk', color)


	def _get_current_attributes(self):
		attrs = self.textview.get_default_attributes()
		self.iter.backward_char()
		self.iter.get_attributes(attrs)
		self.iter.forward_char()
		return attrs

	def __parse_length_frac_size_allocate(self, textview, allocation,
										  frac, callback, args):
		callback(allocation.width*frac, *args)

	def _parse_length(self, value, font_relative, block_relative, minl, maxl, callback, *args):
		'''Parse/calc length, converting to pixels, calls callback(length, *args)
		when the length is first computed or changes'''
		if value.endswith('%'):
			val = float(value[:-1])
			sign = cmp(val,0)
			# limits: 1% to 500%
			val = sign*max(1,min(abs(val),500))
			frac = val/100
			if font_relative:
				attrs = self._get_current_attributes()
				font_size = attrs.font.get_size() / pango.SCALE
				callback(frac*display_resolution*font_size, *args)
			elif block_relative:
				# CSS says 'Percentage values: refer to width of the closest
				#           block-level ancestor'
				# This is difficult/impossible to implement, so we use
				# textview width instead; a reasonable approximation..
				alloc = self.textview.get_allocation()
				self.__parse_length_frac_size_allocate(self.textview, alloc,
													   frac, callback, args)
				self.textview.connect('size-allocate',
									  self.__parse_length_frac_size_allocate,
									  frac, callback, args)
			else:
				callback(frac, *args)
			return

		def get_val():
			val = float(value[:-2])
			sign = cmp(val,0)
			# validate length
			return sign*max(minl,min(abs(val*display_resolution),maxl))
		if value.endswith('pt'): # points
			callback(get_val()*display_resolution, *args)

		elif value.endswith('em'): # ems, the width of the element's font
			attrs = self._get_current_attributes()
			font_size = attrs.font.get_size() / pango.SCALE
			callback(get_val()*display_resolution*font_size, *args)

		elif value.endswith('ex'): # x-height, ~ the height of the letter 'x'
			# FIXME: figure out how to calculate this correctly
			#        for now 'em' size is used as approximation
			attrs = self._get_current_attributes()
			font_size = attrs.font.get_size() / pango.SCALE
			callback(get_val()*display_resolution*font_size, *args)

		elif value.endswith('px'): # pixels
			callback(get_val(), *args)

		else:
			try:
				# TODO: isn't "no units" interpreted as pixels?
				val = int(value)
				sign = cmp(val,0)
				# validate length
				val = sign*max(minl,min(abs(val),maxl))
				callback(val, *args)
			except Exception:
				warnings.warn('Unable to parse length value "%s"' % value)

	def __parse_font_size_cb(length, tag):
		tag.set_property('size-points', length/display_resolution)
	__parse_font_size_cb = staticmethod(__parse_font_size_cb)

	def _parse_style_display(self, tag, value):
		if value == 'none':
			tag.set_property('invisible','true')
		# FIXME: display: block, inline

	def _parse_style_font_size(self, tag, value):
		try:
			scale = {
				'xx-small': pango.SCALE_XX_SMALL,
				'x-small': pango.SCALE_X_SMALL,
				'small': pango.SCALE_SMALL,
				'medium': pango.SCALE_MEDIUM,
				'large': pango.SCALE_LARGE,
				'x-large': pango.SCALE_X_LARGE,
				'xx-large': pango.SCALE_XX_LARGE,
				} [value]
		except KeyError:
			pass
		else:
			attrs = self._get_current_attributes()
			tag.set_property('scale', scale / attrs.font_scale)
			return
		if value == 'smaller':
			tag.set_property('scale', pango.SCALE_SMALL)
			return
		if value == 'larger':
			tag.set_property('scale', pango.SCALE_LARGE)
			return
		# font relative (5 ~ 4pt, 110 ~ 72pt)
		self._parse_length(value, True, False, 5, 110, self.__parse_font_size_cb, tag)

	def _parse_style_font_style(self, tag, value):
		try:
			style = {
				'normal': pango.STYLE_NORMAL,
				'italic': pango.STYLE_ITALIC,
				'oblique': pango.STYLE_OBLIQUE,
				} [value]
		except KeyError:
			warnings.warn('unknown font-style %s' % value)
		else:
			tag.set_property('style', style)

	def __frac_length_tag_cb(self,length, tag, propname):
		styles = self._get_style_tags()
		if styles:
			length += styles[-1].get_property(propname)
		tag.set_property(propname, length)
	#__frac_length_tag_cb = staticmethod(__frac_length_tag_cb)

	def _parse_style_margin_left(self, tag, value):
		# block relative
		self._parse_length(value, False, True, 1, 1000, self.__frac_length_tag_cb,
						   tag, 'left-margin')

	def _parse_style_margin_right(self, tag, value):
		# block relative
		self._parse_length(value, False, True, 1, 1000, self.__frac_length_tag_cb,
						   tag, 'right-margin')

	def _parse_style_font_weight(self, tag, value):
		# TODO: missing 'bolder' and 'lighter'
		try:
			weight = {
				'100': pango.WEIGHT_ULTRALIGHT,
				'200': pango.WEIGHT_ULTRALIGHT,
				'300': pango.WEIGHT_LIGHT,
				'400': pango.WEIGHT_NORMAL,
				'500': pango.WEIGHT_NORMAL,
				'600': pango.WEIGHT_BOLD,
				'700': pango.WEIGHT_BOLD,
				'800': pango.WEIGHT_ULTRABOLD,
				'900': pango.WEIGHT_HEAVY,
				'normal': pango.WEIGHT_NORMAL,
				'bold': pango.WEIGHT_BOLD,
				} [value]
		except KeyError:
			warnings.warn('unknown font-style %s' % value)
		else:
			tag.set_property('weight', weight)

	def _parse_style_font_family(self, tag, value):
		tag.set_property('family', value)

	def _parse_style_text_align(self, tag, value):
		try:
			align = {
				'left': gtk.JUSTIFY_LEFT,
				'right': gtk.JUSTIFY_RIGHT,
				'center': gtk.JUSTIFY_CENTER,
				'justify': gtk.JUSTIFY_FILL,
				} [value]
		except KeyError:
			warnings.warn('Invalid text-align:%s requested' % value)
		else:
			tag.set_property('justification', align)

	def _parse_style_text_decoration(self, tag, value):
		values = value.split(' ')
		if 'none' in values:
			tag.set_property('underline', pango.UNDERLINE_NONE)
			tag.set_property('strikethrough', False)
		if 'underline' in values:
			tag.set_property('underline', pango.UNDERLINE_SINGLE)
		else:
			tag.set_property('underline', pango.UNDERLINE_NONE)
		if 'line-through' in values:
			tag.set_property('strikethrough', True)
		else:
			tag.set_property('strikethrough', False)
		if 'blink' in values:
			warnings.warn('text-decoration:blink not implemented')
		if 'overline' in values:
			warnings.warn('text-decoration:overline not implemented')

	def _parse_style_white_space(self, tag, value):
		if value == 'pre':
			tag.set_property('wrap_mode', gtk.WRAP_NONE)
		elif value == 'normal':
			tag.set_property('wrap_mode', gtk.WRAP_WORD)
		elif value == 'nowrap':
			tag.set_property('wrap_mode', gtk.WRAP_NONE)

	def __length_tag_cb(self, value, tag, propname):
		try:
			tag.set_property(propname, value)
		except Exception:
			gajim.log.warn( "Error with prop: " + propname + " for tag: " + str(tag))


	def _parse_style_width(self, tag, value):
		if value == 'auto':
			return
		self._parse_length(value, False, False, 1, 1000, self.__length_tag_cb,
						   tag, "width")
	def _parse_style_height(self, tag, value):
		if value == 'auto':
			return
		self._parse_length(value, False, False, 1, 1000, self.__length_tag_cb,
						   tag, "height")


	# build a dictionary mapping styles to methods, for greater speed
	__style_methods = dict()
	for style in ('background-color', 'color', 'font-family', 'font-size',
				  'font-style', 'font-weight', 'margin-left', 'margin-right',
				  'text-align', 'text-decoration', 'white-space', 'display',
				  'width', 'height' ):
		try:
			method = locals()['_parse_style_%s' % style.replace('-', '_')]
		except KeyError:
			warnings.warn('Style attribute "%s" not yet implemented' % style)
		else:
			__style_methods[style] = method
	del style
	# --

	def _get_style_tags(self):
		return [tag for tag in self.styles if tag is not None]

	def _create_url(self, href, title, type_, id_):
		'''Process a url tag.
		'''
		tag = self.textbuf.create_tag(id_)
		if href and href[0] != '#':
			tag.href = href
			tag.type_ = type_ # to be used by the URL handler
			tag.connect('event', self.textview.html_hyperlink_handler, 'url', href)
			tag.set_property('foreground', '#0000ff')
			tag.set_property('underline', pango.UNDERLINE_SINGLE)
			tag.is_anchor = True
		if title:
			tag.title = title
		return tag

	def _process_img(self, attrs):
		'''Process a img tag.
		'''
		mem = ''
		try:
			# Wait maximum 1s for connection
			socket.setdefaulttimeout(1)
			try:
				f = urllib2.urlopen(attrs['src'])
			except Exception, ex:
				gajim.log.debug('Error loading image %s ' % attrs['src']  + str(ex))
				pixbuf = None
				alt = attrs.get('alt', 'Broken image')
			else:
				# Wait 0.1s between each byte
				try:
					f.fp._sock.fp._sock.settimeout(0.5)
				except Exception:
					pass
				# Max image size = 2 MB (to try to prevent DoS)
				deadline = time.time() + 3
				while True:
					if time.time() > deadline:
						gajim.log.debug(str('Timeout loading image %s ' % \
							attrs['src'] + ex))
						mem = ''
						alt = attrs.get('alt', '')
						if alt:
							alt += '\n'
						alt += _('Timeout loading image')
						break
					try:
						temp = f.read(100)
					except socket.timeout, ex:
						gajim.log.debug('Timeout loading image %s ' % attrs['src'] + \
							str(ex))
						alt = attrs.get('alt', '')
						if alt:
							alt += '\n'
						alt += _('Timeout loading image')
						break
					if temp:
						mem += temp
					else:
						break
					if len(mem) > 2*1024*1024:
						alt = attrs.get('alt', '')
						if alt:
							alt += '\n'
						alt += _('Image is too big')
						break
			pixbuf = None
			if mem:
				# Caveat: GdkPixbuf is known not to be safe to load
				# images from network... this program is now potentially
				# hackable ;)
				loader = gtk.gdk.PixbufLoader()
				dims = [0,0]
				def height_cb(length):
					dims[1] = length
				def width_cb(length):
					dims[0] = length
				# process width and height attributes
				w = attrs.get('width')
				h = attrs.get('height')
				# override with width and height styles
				for attr, val in style_iter(attrs.get('style', '')):
					if attr == 'width':
						w = val
					elif attr == 'height':
						h = val
				if w:
					self._parse_length(w, False, False, 1, 1000, width_cb)
				if h:
					self._parse_length(h, False, False, 1, 1000, height_cb)
				def set_size(pixbuf, w, h, dims):
					'''FIXME: floats should be relative to the whole
					textview, and resize with it. This needs new
					pifbufs for every resize, gtk.gdk.Pixbuf.scale_simple
					or similar.
					'''
					if isinstance(dims[0], float):
						dims[0] = int(dims[0]*w)
					elif not dims[0]:
						dims[0] = w
					if isinstance(dims[1], float):
						dims[1] = int(dims[1]*h)
					if not dims[1]:
						dims[1] = h
					loader.set_size(*dims)
				if w or h:
					loader.connect('size-prepared', set_size, dims)
				loader.write(mem)
				loader.close()
				pixbuf = loader.get_pixbuf()
				alt = attrs.get('alt', '')
			if pixbuf is not None:
				tags = self._get_style_tags()
				if tags:
					tmpmark = self.textbuf.create_mark(None, self.iter, True)
				self.textbuf.insert_pixbuf(self.iter, pixbuf)
				self.starting = False
				if tags:
					start = self.textbuf.get_iter_at_mark(tmpmark)
					for tag in tags:
						self.textbuf.apply_tag(tag, start, self.iter)
					self.textbuf.delete_mark(tmpmark)
			else:
				self._insert_text('[IMG: %s]' % alt)
		except Exception, ex:
			gajim.log.error('Error loading image ' + str(ex))
			pixbuf = None
			alt = attrs.get('alt', 'Broken image')
			try:
				loader.close()
			except Exception:
				pass
		return pixbuf

	def _begin_span(self, style, tag=None, id_=None):
		if style is None:
			self.styles.append(tag)
			return None
		if tag is None:
			if id_:
				tag = self.textbuf.create_tag(id_)
			else:
				tag = self.textbuf.create_tag() # we create anonymous tag
		for attr, val in style_iter(style):
			attr = attr.lower()
			val = val
			try:
				method = self.__style_methods[attr]
			except KeyError:
				warnings.warn('Style attribute "%s" requested '
							  'but not yet implemented' % attr)
			else:
				method(self, tag, val)
		self.styles.append(tag)

	def _end_span(self):
		self.styles.pop()

	def _jump_line(self):
		self.textbuf.insert_with_tags_by_name(self.iter, '\n', 'eol')
		self.starting = True

	def _insert_text(self, text):
		if self.starting and text != '\n':
			self.starting = (text[-1] == '\n')
		tags = self._get_style_tags()
		if tags:
			self.textbuf.insert_with_tags(self.iter, text, *tags)
		else:
			self.textbuf.insert(self.iter, text)

	def _starts_line(self):
		return self.starting or self.iter.starts_line()

	def _flush_text(self):
		if not self.text: return
		text, self.text = self.text, ''
		if not self.preserve:
			text = text.replace('\n', ' ')
			self.handle_specials(whitespace_rx.sub(' ', text))
		else:
			self._insert_text(text.strip('\n'))

	def _anchor_event(self, tag, textview, event, iter_, href, type_):
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.textview.emit('url-clicked', href, type_)
			return True
		return False

	def handle_specials(self, text):
		self.iter = self.conv_textview.detect_and_print_special_text(text, 							self._get_style_tags())

	def characters(self, content):
		if self.preserve:
			self.text += content
			return
		if allwhitespace_rx.match(content) is not None and self._starts_line():
			self.text += ' '
			return
		self.text += content
		self.starting = False


	def startElement(self, name, attrs):
		self._flush_text()
		klass = [i for i in attrs.get('class',' ').split(' ') if i]
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
			title = attrs.get('title', attrs.get('rel',href))
			type_ = attrs.get('type', None)
			tag = self._create_url(href, title, type_, id_)
		elif name == 'blockquote':
			cite = attrs.get('cite', None)
			if cite:
				tag = self.textbuf.create_tag(id_)
				tag.title = title
				tag.is_anchor = True
		elif name in LIST_ELEMS:
			style += ';margin-left: 2em'
		elif name == 'img':
			tag = self._process_img(attrs)
		if name in element_styles:
			style += element_styles[name]
		# so that explicit styles override implicit ones,
		# we add the attribute last
		style += ";"+attrs.get('style','')
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
				li_head = unichr(0x2022)
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
			warnings.warn('Unhandled element "%s"' % name)

	def endElement(self, name):
		endPreserving = False
		newLine = False
		if name == 'br':
			newLine = True
		elif name == 'hr':
			#FIXME: plenty of unused attributes (width, height,...) :)
			self._jump_line()
			try:
				self.textbuf.insert_pixbuf(self.iter, self.textview.focus_out_line_pixbuf)
				#self._insert_text(u'\u2550'*40)
				self._jump_line()
			except Exception, e:
				gajim.log.debug(str('Error in hr'+e))
		elif name in LIST_ELEMS:
			self.list_counters.pop()
		elif name == 'li':
			newLine = True
		elif name == 'img':
			pass
		elif name == 'body' or name == 'html':
			pass
		elif name == 'a':
			pass
		elif name in INLINE:
			pass
		elif name in ('dd', 'dt', ):
			pass
		elif name in BLOCK:
			if name == 'pre':
				endPreserving = True
		else:
			warnings.warn("Unhandled element '%s'" % name)
		self._flush_text()
		if endPreserving:
			self.preserve = False
		if newLine:
			self._jump_line()
		self._end_span()
		#if not self._starts_line():
		#    self.text = ' '

class HtmlTextView(gtk.TextView):

	def __init__(self):
		gobject.GObject.__init__(self)
		self.set_wrap_mode(gtk.WRAP_CHAR)
		self.set_editable(False)
		self._changed_cursor = False
		self.connect('destroy', self.__destroy_event)
		self.connect('motion-notify-event', self.__motion_notify_event)
		self.connect('leave-notify-event', self.__leave_event)
		self.connect('enter-notify-event', self.__motion_notify_event)
		self.get_buffer().create_tag('eol', scale = pango.SCALE_XX_SMALL)
		self.tooltip = tooltips.BaseTooltip()
		self.config = gajim.config
		self.interface = gajim.interface
		# end big hack

	def __destroy_event(self, widget):
		if self.tooltip.timeout != 0:
			self.tooltip.hide_tooltip()

	def __leave_event(self, widget, event):
		if self._changed_cursor:
			window = widget.get_window(gtk.TEXT_WINDOW_TEXT)
			window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
			self._changed_cursor = False

	def show_tooltip(self, tag):
		if not self.tooltip.win:
			# check if the current pointer is still over the line
			x, y, _ = self.window.get_pointer()
			x, y = self.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
			tags = self.get_iter_at_location(x, y).get_tags()
			is_over_anchor = False
			for tag_ in tags:
				if getattr(tag_, 'is_anchor', False):
					is_over_anchor = True
					break
			if not is_over_anchor:
				return
			text = getattr(tag, 'title', False)
			if text:
				pointer = self.get_pointer()
				position = self.window.get_origin()
				self.tooltip.show_tooltip(text, 8, position[1] + pointer[1])

	def __motion_notify_event(self, widget, event):
		x, y, _ = widget.window.get_pointer()
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
		tags = widget.get_iter_at_location(x, y).get_tags()
		anchor_tags = [tag for tag in tags if getattr(tag, 'is_anchor', False)]
		if self.tooltip.timeout != 0:
			# Check if we should hide the line tooltip
			if not anchor_tags:
				self.tooltip.hide_tooltip()
		if not self._changed_cursor and anchor_tags:
			window = widget.get_window(gtk.TEXT_WINDOW_TEXT)
			window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
			self._changed_cursor = True
			self.tooltip.timeout = gobject.timeout_add(500, self.show_tooltip, anchor_tags[0])
		elif self._changed_cursor and not anchor_tags:
			window = widget.get_window(gtk.TEXT_WINDOW_TEXT)
			window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
			self._changed_cursor = False
		return False

	def display_html(self, html, conv_textview):
		buffer_ = self.get_buffer()
		eob = buffer_.get_end_iter()
		## this works too if libxml2 is not available
		# parser = xml.sax.make_parser(['drv_libxml2'])
		# parser.setFeature(xml.sax.handler.feature_validation, True)
		parser = xml.sax.make_parser()
		parser.setContentHandler(HtmlHandler(conv_textview, eob))
		parser.parse(StringIO(html))

		# too much space after :)
		#if not eob.starts_line():
		#    buffer_.insert(eob, '\n')



change_cursor = None

if __name__ == '__main__':
	import os

	from conversation_textview import ConversationTextview
	import gajim as gaj

	class log(object):

		def debug(self, text):
			print "debug:", text
		def warn(self, text):
			print "warn;", text
		def error(self,text):
			print "error;", text

	gajim.log=log()

	gaj.Interface()

	htmlview = ConversationTextview(None)

	path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps', 'muc_separator.png')
	# use this for hr
	htmlview.tv.focus_out_line_pixbuf =  gtk.gdk.pixbuf_new_from_file(path_to_file)


	tooltip = tooltips.BaseTooltip()
	def on_textview_motion_notify_event(widget, event):
		'''change the cursor to a hand when we are over a mail or an url'''
		global change_cursor
		pointer_x, pointer_y = htmlview.tv.window.get_pointer()[0:2]
		x, y = htmlview.tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer_x,
								   pointer_y)
		tags = htmlview.tv.get_iter_at_location(x, y).get_tags()
		if change_cursor:
			htmlview.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					 gtk.gdk.Cursor(gtk.gdk.XTERM))
			change_cursor = None
		tag_table = htmlview.tv.get_buffer().get_tag_table()
		for tag in tags:
			try:
				if tag.is_anchor:
					htmlview.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
										gtk.gdk.Cursor(gtk.gdk.HAND2))
					change_cursor = tag
				elif tag == tag_table.lookup('focus-out-line'):
					over_line = True
			except Exception:
				pass

		#if line_tooltip.timeout != 0:
			# Check if we should hide the line tooltip
		#	if not over_line:
		#		line_tooltip.hide_tooltip()
		#if over_line and not line_tooltip.win:
		#	line_tooltip.timeout = gobject.timeout_add(500,
		#		show_line_tooltip)
		#	htmlview.tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
		#		gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
		#	change_cursor = tag

	htmlview.tv.connect('motion_notify_event', on_textview_motion_notify_event)

	def handler(texttag, widget, event, iter_, kind, href):
		if event.type == gtk.gdk.BUTTON_PRESS:
			print href

	htmlview.tv.html_hyperlink_handler = handler

	htmlview.print_real_text(None, xhtml='<div><span style="color: red; text-decoration:underline">Hello</span><br/>\n'
						  '  <img src="http://images.slashdot.org/topics/topicsoftware.gif"/><br/>\n'
						  '  <span style="font-size: 500%; font-family: serif">World</span>\n'
						  '</div>\n')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''<body xmlns='http://www.w3.org/1999/xhtml'><p xmlns='http://www.w3.org/1999/xhtml'>a:b<a href='http://google.com/' xmlns='http://www.w3.org/1999/xhtml'>Google</a></p><br/></body>''')
	htmlview.print_real_text(None, xhtml='''
	 <body xmlns='http://www.w3.org/1999/xhtml'>
	  <p style='font-size:large'>
		<span style='font-style: italic'>O<span style='font-size:larger'>M</span>G</span>,
		I&apos;m <span style='color:green'>green</span>
		with <span style='font-weight: bold'>envy</span>!
	  </p>
	 </body>
		''')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''
	<body xmlns='http://www.w3.org/1999/xhtml'>
		http://test.com/  testing links autolinkifying	
	</body>
		''')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''
	<body xmlns='http://www.w3.org/1999/xhtml'>
	  <p>As Emerson said in his essay <span style='font-style: italic; background-color:cyan'>Self-Reliance</span>:</p>
	  <p style='margin-left: 5px; margin-right: 2%'>
		&quot;A foolish consistency is the hobgoblin of little minds.&quot;
	  </p>
	</body>
		''')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''
	<body xmlns='http://www.w3.org/1999/xhtml'>
	  <p style='text-align:center'>Hey, are you licensed to <a href='http://www.jabber.org/'>Jabber</a>?</p>
	  <p style='text-align:right'><img src='http://www.jabber.org/images/psa-license.jpg'
			  alt='A License to Jabber'
			  width='50%' height='50%'
			  /></p>
	</body>
		''')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''
	<body xmlns='http://www.w3.org/1999/xhtml'>
	  <ul style='background-color:rgb(120,140,100)'>
	   <li> One </li>
	   <li> Two </li>
	   <li> Three </li>
	  </ul><hr /><pre style="background-color:rgb(120,120,120)">def fac(n):
  def faciter(n,acc):
	if n==0: return acc
	return faciter(n-1, acc*n)
  if n&lt;0: raise ValueError('Must be non-negative')
  return faciter(n,1)</pre>
	</body>
		''')
	htmlview.print_real_text(None, xhtml='<hr />')
	htmlview.print_real_text(None, xhtml='''
	<body xmlns='http://www.w3.org/1999/xhtml'>
	 <ol style='background-color:rgb(120,140,100)'>
	   <li> One </li>
	   <li> Two is nested: <ul style='background-color:rgb(200,200,100)'>
			 <li> One </li>
			 <li style='font-size:50%'> Two </li>
			 <li style='font-size:200%'> Three </li>
			 <li style='font-size:9999pt'> Four </li>
			</ul></li>
	   <li> Three </li></ol>
	</body>
		''')
	htmlview.tv.show()
	sw = gtk.ScrolledWindow()
	sw.set_property('hscrollbar-policy', gtk.POLICY_AUTOMATIC)
	sw.set_property('vscrollbar-policy', gtk.POLICY_AUTOMATIC)
	sw.set_property('border-width', 0)
	sw.add(htmlview.tv)
	sw.show()
	frame = gtk.Frame()
	frame.set_shadow_type(gtk.SHADOW_IN)
	frame.show()
	frame.add(sw)
	w = gtk.Window()
	w.add(frame)
	w.set_default_size(400, 300)
	w.show_all()
	w.connect('destroy', lambda w: gtk.main_quit())
	gtk.main()

# vim: se ts=3:
