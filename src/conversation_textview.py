##	conversation_textview.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gtk.glade
import pango
import gobject
import time
import tooltips
import dialogs

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class ConversationTextview(gtk.TextView):
	'''Class for the conversation textview (where user reads already said messages)
	for chat/groupchat windows'''
	def __init__(self, account):
		gtk.TextView.__init__(self)

		# set properties
		self.set_border_width(1)
		self.set_accepts_tab(True)
		self.set_editable(False)
		self.set_cursor_visible(False)
		self.set_wrap_mode(gtk.WRAP_WORD)
		self.set_left_margin(2)
		self.set_right_margin(2)

		# connect signals
		self.connect('motion_notify_event', self.on_textview_motion_notify_event)
		self.connect('populate_popup', self.on_textview_populate_popup)
		self.connect('button_press_event', self.on_textview_button_press_event)

		self.account = account
		self.change_cursor = None
		self.last_time_printout = 0

		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.modify_font(font)
		buffer = self.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, False)

		self.tagIn = buffer.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		self.tagIn.set_property('foreground', color)
		self.tagOut = buffer.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		self.tagOut.set_property('foreground', color)
		self.tagStatus = buffer.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		self.tagStatus.set_property('foreground', color)

		tag = buffer.create_tag('marked')
		color = gajim.config.get('markedmsgcolor')
		tag.set_property('foreground', color)
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer.create_tag('time_sometimes')
		tag.set_property('foreground', 'grey')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)

		tag = buffer.create_tag('small')
		tag.set_property('scale', pango.SCALE_SMALL)

		tag = buffer.create_tag('restored_message')
		color = gajim.config.get('restored_messages_color')
		tag.set_property('foreground', color)

		tag = buffer.create_tag('url')
		tag.set_property('foreground', 'blue')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'url')

		tag = buffer.create_tag('mail')
		tag.set_property('foreground', 'blue')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'mail')

		tag = buffer.create_tag('bold')
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = buffer.create_tag('italic')
		tag.set_property('style', pango.STYLE_ITALIC)

		tag = buffer.create_tag('underline')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)

		buffer.create_tag('focus-out-line', justification = gtk.JUSTIFY_CENTER)

		# muc attention states (when we are mentioned in a muc)
		# if the room jid is in the list, the room has mentioned us
		self.muc_attentions = []
		self.line_tooltip = tooltips.BaseTooltip()

	def update_tags(self):
		self.tagIn.set_property('foreground', gajim.config.get('inmsgcolor'))
		self.tagOut.set_property('foreground', gajim.config.get('outmsgcolor'))
		self.tagStatus.set_property('foreground',
			gajim.config.get('statusmsgcolor'))

	def at_the_end(self):
		buffer = self.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = self.get_iter_location(end_iter)
		visible_rect = self.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			return True
		return False

	def scroll_to_end(self):
		parent = self.get_parent()
		buffer = self.get_buffer()
		self.scroll_to_mark(buffer.get_mark('end'), 0, True, 0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		return False # when called in an idle_add, just do it once

	def bring_scroll_to_end(self, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		buffer = self.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = self.get_iter_location(end_iter)
		visible_rect = self.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			gobject.idle_add(self.scroll_to_end_iter)

	def scroll_to_end_iter(self):
		buffer = self.get_buffer()
		end_iter = buffer.get_end_iter()
		self.scroll_to_iter(end_iter, 0, False, 1, 1)
		return False # when called in an idle_add, just do it once

	def show_line_tooltip(self):
		pointer = self.get_pointer()
		x, y = self.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer[0],
			pointer[1])
		tags = self.get_iter_at_location(x, y).get_tags()
		tag_table = self.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag == tag_table.lookup('focus-out-line'):
				over_line = True
				break
		if over_line and not self.line_tooltip.win:
			# check if the current pointer is still over the line
			position = self.window.get_origin()
			win = self.get_toplevel()
			self.line_tooltip.show_tooltip(_('Text below this line is what has '
			'been said since the last time you paid attention to this group chat'),
				(0, 8), (win.get_screen().get_display().get_pointer()[1],
				position[1] + pointer[1]))

	def on_textview_motion_notify_event(self, widget, event):
		'''change the cursor to a hand when we are over a mail or an url'''
		pointer_x, pointer_y, spam = self.window.get_pointer()
		x, y = self.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer_x,
			pointer_y)
		tags = self.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			self.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = None
		tag_table = self.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag in (tag_table.lookup('url'), tag_table.lookup('mail')):
				self.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = tag
			elif tag == tag_table.lookup('focus-out-line'):
				over_line = True

		if self.line_tooltip.timeout != 0:
			# Check if we should hide the line tooltip
			if not over_line:
				self.line_tooltip.hide_tooltip()
		if over_line and not self.line_tooltip.win:
			self.line_tooltip.timeout = gobject.timeout_add(500,
				self.show_line_tooltip)
			self.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
			self.change_cursor = tag

	def clear(self, tv = None):
		'''clear text in the textview'''
		buffer = self.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def visit_url_from_menuitem(self, widget, link):
		'''basically it filters out the widget instance'''
		helpers.launch_browser_mailer('url', link)

	def on_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		and if we have sth selected we show a submenu with actions on the phrase
		(see on_conversation_textview_button_press_event)'''
		item = gtk.SeparatorMenuItem()
		menu.prepend(item)
		item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
		menu.prepend(item)
		item.connect('activate', self.clear)
		if self.selected_phrase:
			s = self.selected_phrase
			if len(s) > 25:
				s = s[:21] + '...'
			item = gtk.MenuItem(_('Actions for "%s"') % s)
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
			item.connect('activate', self.visit_url_from_menuitem, link)
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
				item.connect('activate', self.visit_url_from_menuitem, link)
			else:
				if dict_link.find('%s') == -1:
					#we must have %s in the url if not WIKTIONARY
					item = gtk.MenuItem(_('Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
					item.set_property('sensitive', False)
				else:
					link = dict_link % self.selected_phrase
					item.connect('activate', self.visit_url_from_menuitem, link)
			submenu.append(item)


			search_link = gajim.config.get('search_engine')
			if search_link.find('%s') == -1:
				#we must have %s in the url
				item = gtk.MenuItem(_('Web Search URL is missing an "%s"'))
				item.set_property('sensitive', False)
			else:
				item = gtk.MenuItem(_('Web _Search for it'))
				link =  search_link % self.selected_phrase
				item.connect('activate', self.visit_url_from_menuitem, link)
			submenu.append(item)

		menu.show_all()

	def on_textview_button_press_event(self, widget, event):
		# If we clicked on a taged text do NOT open the standard popup menu
		# if normal text check if we have sth selected

		self.selected_phrase = ''

		if event.button != 3: # if not right click
			return False

		win = self.get_window(gtk.TEXT_WINDOW_TEXT)
		x, y = self.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			int(event.x), int(event.y))
		iter = self.get_iter_at_location(x, y)
		tags = iter.get_tags()


		if tags: # we clicked on sth special (it can be status message too)
			for tag in tags:
				tag_name = tag.get_property('name')
				if 'url' in tag_name or 'mail' in tag_name:
					return True # we block normal context menu

		# we check if sth was selected and if it was we assign
		# selected_phrase variable
		# so on_conversation_textview_populate_popup can use it
		buffer = self.get_buffer()
		return_val = buffer.get_selection_bounds()
		if return_val: # if sth was selected when we right-clicked
			# get the selected text
			start_sel, finish_sel = return_val[0], return_val[1]
			self.selected_phrase = buffer.get_text(start_sel, finish_sel).decode('utf-8')

	def on_open_link_activate(self, widget, kind, text):
		helpers.launch_browser_mailer(kind, text)

	def on_copy_link_activate(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def on_start_chat_activate(self, widget, jid):
		gajim.interface.roster.new_chat_from_jid(self.account, jid)

	def on_join_group_chat_menuitem_activate(self, widget, jid):
		room, server = jid.split('@')
		if gajim.interface.instances[self.account].has_key('join_gc'):
			instance = gajim.interface.instances[self.account]['join_gc']
			instance.xml.get_widget('server_entry').set_text(server)
			instance.xml.get_widget('room_entry').set_text(room)
			gajim.interface.instances[self.account]['join_gc'].window.present()
		else:
			try:
				gajim.interface.instances[self.account]['join_gc'] = \
				dialogs.JoinGroupchatWindow(self.account, server, room)
			except RuntimeError:
				pass

	def on_add_to_roster_activate(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def make_link_menu(self, event, kind, text):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'chat_context_menu', APP)
		menu = xml.get_widget('chat_context_menu')
		childs = menu.get_children()
		if kind == 'url':
			childs[0].connect('activate', self.on_copy_link_activate, text)
			childs[1].connect('activate', self.on_open_link_activate, kind, text)
			childs[2].hide() # copy mail address
			childs[3].hide() # open mail composer
			childs[4].hide() # jid section seperator
			childs[5].hide() # start chat
			childs[6].hide() # join group chat
			childs[7].hide() # add to roster
		else: # It's a mail or a JID
			childs[2].connect('activate', self.on_copy_link_activate, text)
			childs[3].connect('activate', self.on_open_link_activate, kind, text)
			childs[5].connect('activate', self.on_start_chat_activate, text)
			childs[6].connect('activate',
				self.on_join_group_chat_menuitem_activate, text)

			allow_add = False
			if gajim.contacts[self.account].has_key(text):
				c = gajim.contacts[self.account][text][0]
				if _('not in the roster') in c.groups:
					allow_add = True
			else: # he or she's not at all in the account contacts
				allow_add = True

			if allow_add:
				childs[7].connect('activate', self.on_add_to_roster_activate, text)
				childs[7].show() # show add to roster menuitem
			else:
				childs[7].hide() # hide add to roster menuitem

			childs[0].hide() # copy link location
			childs[1].hide() # open link in browser

		menu.popup(None, None, None, event.button, event.time)

	def hyperlink_handler(self, texttag, widget, event, iter, kind):
		if event.type == gtk.gdk.BUTTON_PRESS:
			begin_iter = iter.copy()
			# we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter.copy()
			# we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = self.get_buffer().get_text(begin_iter, end_iter).decode('utf-8')
			if event.button == 3: # right click
				self.make_link_menu(event, kind, word)
			else:
				# we launch the correct application
				helpers.launch_browser_mailer(kind, word)

	def detect_and_print_special_text(self, otext, other_tags):
		'''detects special text (emots & links & formatting)
		prints normal text before any special text it founts,
		then print special text (that happens many times until
		last special text is printed) and then returns the index
		after *last* special text, so we can print it in
		print_conversation_line()'''

		buffer = self.get_buffer()

		start = 0
		end = 0
		index = 0

		# basic: links + mail + formatting is always checked (we like that)
		if gajim.config.get('useemoticons'): # search for emoticons & urls
			iterator = gajim.interface.emot_and_basic_re.finditer(otext)
		else: # search for just urls + mail + formatting
			iterator = gajim.interface.basic_pattern_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start != 0:
				text_before_special_text = otext[index:start]
				end_iter = buffer.get_end_iter()
				# we insert normal text
				buffer.insert_with_tags_by_name(end_iter,
					text_before_special_text, *other_tags)
			index = end # update index

			# now print it
			self.print_special_text(special_text, other_tags)

		return index # the position after *last* special text

	def print_special_text(self, special_text, other_tags):
		'''is called by detect_and_print_special_text and prints
		special text (emots, links, formatting)'''
		tags = []
		use_other_tags = True
		show_ascii_formatting_chars = \
			gajim.config.get('show_ascii_formatting_chars')
		buffer = self.get_buffer()

		possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
		if gajim.config.get('useemoticons') and \
		possible_emot_ascii_caps in gajim.interface.emoticons.keys():
			#it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			end_iter = buffer.get_end_iter()
			anchor = buffer.create_child_anchor(end_iter)
			img = gtk.Image()
			img.set_from_file(gajim.interface.emoticons[emot_ascii])
			img.show()
			#add with possible animation
			self.add_child_at_anchor(img, anchor)
		elif special_text.startswith('mailto:'):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif gajim.interface.sth_at_sth_dot_sth_re.match(special_text):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif special_text.startswith('*'): # it's a bold text
			tags.append('bold')
			if special_text[1] == '/' and special_text[-2] == '/' and len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove */ /*
			elif special_text[1] == '_' and special_text[-2] == '_' and len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove *_ _*
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove * *
		elif special_text.startswith('/'): # it's an italic text
			tags.append('italic')
			if special_text[1] == '*' and special_text[-2] == '*' and len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /* */
			elif special_text[1] == '_' and special_text[-2] == '_' and len(special_text) > 4: # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /_ _/
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove / /
		elif special_text.startswith('_'): # it's an underlined text
			tags.append('underline')
			if special_text[1] == '*' and special_text[-2] == '*' and len(special_text) > 4: # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _* *_
			elif special_text[1] == '/' and special_text[-2] == '/' and len(special_text) > 4: # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _/ /_
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove _ _
		else:
			#it's a url
			tags.append('url')
			use_other_tags = False

		if len(tags) > 0:
			end_iter = buffer.get_end_iter()
			all_tags = tags[:]
			if use_other_tags:
				all_tags += other_tags
			buffer.insert_with_tags_by_name(end_iter, special_text, *all_tags)

	def print_empty_line(self):
		buffer = self.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.insert(end_iter, '\n')

	def print_conversation_line(self, text, jid, kind, name, tim,
			other_tags_for_name = [], other_tags_for_time = [],
			other_tags_for_text = [], subject = None):
		'''prints 'chat' type messages'''
		if kind == 'status' and not gajim.config.get('print_status_in_chats'):
				return
		buffer = self.get_buffer()
		buffer.begin_user_action()
		end_iter = buffer.get_end_iter()
		at_the_end = False
		if self.at_the_end():
			at_the_end = True

		if buffer.get_char_count() > 0:
			buffer.insert(end_iter, '\n')
		if kind == 'incoming_queue':
			kind = 'incoming'
		# print the time stamp
		if not tim:
			# We don't have tim for outgoing messages...
			tim = time.localtime()
		if gajim.config.get('print_time') == 'always':
			before_str = gajim.config.get('before_time')
			after_str = gajim.config.get('after_time')
			msg_day = time.strftime('%j', tim)
			day = time.strftime('%j')
			diff_day = 0
			while day != msg_day:
				diff_day += 1
				before_tim = time.localtime(time.time()-24*3600*diff_day)
				day = time.strftime('%j', before_tim)
			if diff_day == 0:
				day_str = ''
			elif diff_day == 1:
				day_str = _('Yesterday')
			else:
				#the number is >= 2
				# %i is day in year (1-365), %d (1-31) we want %i
				day_str = _('%i days ago') % diff_day
			format = before_str
			if day_str:
				format += day_str + ' '
			format += '%X' + after_str
			tim_format = time.strftime(format, tim)
			buffer.insert_with_tags_by_name(end_iter, tim_format + ' ',
				*other_tags_for_time)
		elif gajim.config.get('print_time') == 'sometimes':
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = time.mktime(tim) - self.last_time_printout
			if seconds_passed > every_foo_seconds:
				self.last_time_printout = time.mktime(tim)
				end_iter = buffer.get_end_iter()
				tim_format = time.strftime('%H:%M', tim)
				buffer.insert_with_tags_by_name(end_iter, tim_format + '\n',
					'time_sometimes')
		other_text_tag = self.detect_other_text_tag(text, kind)
		text_tags = other_tags_for_text[:] # create a new list
		if other_text_tag:
			text_tags.append(other_text_tag)
		else: # not status nor /me
			self.print_name(name, kind, other_tags_for_name)
		self.print_subject(subject)
		self.print_real_text(text, text_tags, name)

		# scroll to the end of the textview
		if at_the_end or kind == 'outgoing':
			# we are at the end or we are sending something
			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.scroll_to_end)

		buffer.end_user_action()

	def detect_other_text_tag(self, text, kind):
		if kind == 'status':
			return kind
		elif text.startswith('/me ') or text.startswith('/me\n'):
			return kind

	def print_name(self, name, kind, other_tags_for_name):
		if name:
			buffer = self.get_buffer()
			end_iter = buffer.get_end_iter()
			name_tags = other_tags_for_name[:] # create a new list
			name_tags.append(kind)
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + name + after_str + ' '
			buffer.insert_with_tags_by_name(end_iter, format, *name_tags)

	def print_subject(self, subject):
		if subject: # if we have subject, show it too!
			subject = _('Subject: %s\n') % subject
			buffer = self.get_buffer()
			end_iter = buffer.get_end_iter()
			buffer.insert(end_iter, subject)
			self.print_empty_line()

	def print_real_text(self, text, text_tags = [], name = None):
		'''this adds normal and special text. call this to add text'''
		buffer = self.get_buffer()
		# /me is replaced by name if name is given
		if name and text.startswith('/me ') or text.startswith('/me\n'):
			text = '* ' + name + text[3:]
		# detect urls formatting and if the user has it on emoticons
		index = self.detect_and_print_special_text(text, text_tags)

		# add the rest of text located in the index and after
		end_iter = buffer.get_end_iter()
		buffer.insert_with_tags_by_name(end_iter, text[index:], *text_tags)

