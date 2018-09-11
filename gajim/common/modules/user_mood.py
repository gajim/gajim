# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0107: User Mood

import logging

import nbxmpp
from gi.repository import GLib

from gajim.common.const import PEPEventType, MOODS
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.user_mood')


class UserMoodData(AbstractPEPData):

    type_ = PEPEventType.MOOD

    def __init__(self, mood):
        self.data = mood

    def asMarkupText(self):
        mood = self._translate_mood(self.data['mood'])
        markuptext = '<b>%s</b>' % GLib.markup_escape_text(mood)
        if 'text' in self.data:
            text = self.data['text']
            markuptext += ' (%s)' % GLib.markup_escape_text(text)
        return markuptext

    @staticmethod
    def _translate_mood(mood):
        if mood in MOODS:
            return MOODS[mood]
        return mood


class UserMood(AbstractPEPModule):

    name = 'mood'
    namespace = nbxmpp.NS_MOOD
    pep_class = UserMoodData
    store_publish = True
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []

    def _extract_info(self, item):
        mood_dict = {}
        mood_tag = item.getTag('mood', namespace=nbxmpp.NS_MOOD)
        if mood_tag is None:
            raise StanzaMalformed('No mood node')

        for child in mood_tag.getChildren():
            name = child.getName().strip()
            if name == 'text':
                mood_dict['text'] = child.getData()
            else:
                mood_dict['mood'] = name

        return mood_dict or None

    def _build_node(self, data):
        item = nbxmpp.Node('mood', {'xmlns': nbxmpp.NS_MOOD})
        if data is None:
            return
        mood, text = data
        if mood:
            item.addChild(mood)
        if text:
            item.addChild('text', payload=text)
        return item


def get_instance(*args, **kwargs):
    return UserMood(*args, **kwargs), 'UserMood'
