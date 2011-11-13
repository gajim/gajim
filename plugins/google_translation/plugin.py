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
import HTMLParser
import new
from pprint import pformat
from sys import getfilesystemencoding

from common import helpers
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged
from common import nec

class GoogleTranslationPlugin(GajimPlugin):

    @log_calls('GoogleTranslationPlugin')
    def init(self):
        self.description = _('Translates (currently only incoming)'
            'messages using Google Translate.')
        self.config_dialog = None

        self.config_default_values = {
            'from_lang' :
                (u'en', u'Language of text to be translated'),
            'to_lang' :
                (u'fr', u'Language to which translation will be made'),
            'user_agent' :
                (u'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.1.12) '
                'Gecko/20080213 Firefox/2.0.0.11',
                u'User Agent data to be used with urllib2 '
                'when connecting to Google Translate service')}

        self.events_handlers = {'decrypted-message-received': (ged.PREGUI,
            self._nec_decrypted_message_received)}

        self.translated_text_re = re.compile(
            r'google.language.callbacks.id100\(\'22\', '
            '{"translatedText":"(?P<text>[^"]*)"}, 200, null, 200\)')

    @log_calls('GoogleTranslationPlugin')
    def translate_text(self, text, from_lang, to_lang):
        # Converts text so it can be used within URL as query to Google
        # Translate.
        quoted_text = urllib2.quote(text.encode(getfilesystemencoding()))
        # prepare url
        headers = { 'User-Agent' : self.config['user_agent'] }
        translation_url = u'http://www.google.com/uds/Gtranslate?callback='\
            'google.language.callbacks.id100&context=22&q=%(quoted_text)s&'\
            'langpair=%(from_lang)s%%7C%(to_lang)s&key=notsupplied&v=1.0' % \
            locals()
        request = urllib2.Request(translation_url, headers=headers)

        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError, e:
            # print e
            return text

        results = response.read()
        translated_text = self.translated_text_re.search(results).group('text')

        if translated_text:
            try:
                translated_text = unicode(translated_text, 'unicode_escape')
                htmlparser = HTMLParser.HTMLParser()
                translated_text = htmlparser.unescape(translated_text)
            except Exception:
                pass
            return translated_text
        return text

    @log_calls('GoogleTranslationPlugin')
    def _nec_decrypted_message_received(self, obj):
        if not obj.msgtxt:
            return
        from_lang = self.config['from_lang']
        to_lang = self.config['to_lang']
        translated_text = self.translate_text(obj.msgtxt, from_lang, to_lang)
        if translated_text:
            obj.msgtxt = translated_text

    @log_calls('GoogleTranslationPlugin')
    def activate(self):
        pass

    @log_calls('GoogleTranslationPlugin')
    def deactivate(self):
        pass
