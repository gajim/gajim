# -*- coding: utf-8 -*-
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##
'''
Google Translation plugin.

Translates (currently only incoming) messages using Google Translate.

:note: consider this as proof-of-concept
:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 25th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import re
import urllib2
import new
from pprint import pformat

from common import helpers
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged
from common import nec

class GoogleTranslationPlugin(GajimPlugin):
	name = u'Google Translation'
	short_name = u'google_translation'
	version = u'0.1'
	description = u'''Translates (currently only incoming) messages using Google Translate.'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'
	
	@log_calls('GoogleTranslationPlugin')
	def init(self):
		self.config_dialog = None
		#self.gui_extension_points = {}
		self.config_default_values = {'from_lang' : (u'en', _(u'Language of text to be translated')),
									  'to_lang' : (u'fr', _(u'Language to which translation will be made')),
									  'user_agent' : (u'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.1.12) Gecko/20080213 Firefox/2.0.0.11',
													  _(u'User Agent data to be used with urllib2 when connecting to Google Translate service'))}
		
		#self.events_handlers = {}
		
		self.events = [GoogleTranslateMessageReceivedEvent]
		
		self.translated_text_re = \
			re.compile(r'google.language.callbacks.id100\(\'22\',{"translatedText":"(?P<text>[^"]*)"}, 200, null, 200\)')
		
	@log_calls('GoogleTranslationPlugin')
	def translate_text(self, text, from_lang, to_lang):
		text = self.prepare_text_for_url(text)
		headers = { 'User-Agent' : self.config['user_agent'] }
		translation_url = u'http://www.google.com/uds/Gtranslate?callback=google.language.callbacks.id100&context=22&q=%(text)s&langpair=%(from_lang)s%%7C%(to_lang)s&key=notsupplied&v=1.0'%locals()
		
		request = urllib2.Request(translation_url, headers=headers)
		response = urllib2.urlopen(request)
		results = response.read()
		
		translated_text = self.translated_text_re.search(results).group('text')
		
		return translated_text
	
	@log_calls('GoogleTranslationPlugin')
	def prepare_text_for_url(self, text):
		'''
		Converts text so it can be used within URL as query to Google Translate.
		'''
		
		# There should be more replacements for plugin to work in any case:
		char_replacements = { ' ' : '%20',
							  '+' : '%2B'}
		
		for char, replacement in char_replacements.iteritems():
			text = text.replace(char, replacement)
			
		return text
	
	@log_calls('GoogleTranslationPlugin')
	def activate(self):
		pass
		
	@log_calls('GoogleTranslationPlugin')
	def deactivate(self):
		pass
	
class GoogleTranslateMessageReceivedEvent(nec.NetworkIncomingEvent):
	name = 'google-translate-message-received'
	base_network_events = ['raw-message-received']
	
	def generate(self):
		msg_type = self.base_event.xmpp_msg.attrs.get('type', None)
		if msg_type == u'chat':
			msg_text = "".join(self.base_event.xmpp_msg.kids[0].data)
			if msg_text:
				from_lang = self.plugin.config['from_lang']
				to_lang = self.plugin.config['to_lang']
				self.base_event.xmpp_msg.kids[0].setData(
					self.plugin.translate_text(msg_text, from_lang, to_lang))
			
		return False 	# We only want to modify old event, not emit another,
						# so we return False here.
						
