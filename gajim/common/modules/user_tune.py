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

# XEP-0118: User Tune

import logging

import nbxmpp
from gi.repository import GLib

from gajim.common.const import PEPEventType
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.user_tune')


class UserTuneData(AbstractPEPData):

    type_ = PEPEventType.TUNE

    def __init__(self, tune):
        self._pep_specific_data = tune

    def asMarkupText(self):
        tune = self._pep_specific_data

        artist = tune.get('artist', _('Unknown Artist'))
        artist = GLib.markup_escape_text(artist)

        title = tune.get('title', _('Unknown Title'))
        title = GLib.markup_escape_text(title)

        source = tune.get('source', _('Unknown Source'))
        source = GLib.markup_escape_text(source)

        tune_string = _('<b>"%(title)s"</b> by <i>%(artist)s</i>\n'
                        'from <i>%(source)s</i>') % {'title': title,
                                                     'artist': artist,
                                                     'source': source}
        return tune_string


class UserTune(AbstractPEPModule):

    name = 'tune'
    namespace = nbxmpp.NS_TUNE
    pep_class = UserTuneData
    store_publish = True
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []

    def _extract_info(self, item):
        tune_dict = {}
        tune_tag = item.getTag('tune', namespace=self.namespace)
        if tune_tag is None:
            raise StanzaMalformed('No tune node')

        for child in tune_tag.getChildren():
            name = child.getName().strip()
            data = child.getData().strip()
            if child.getName() in ['artist', 'title', 'source',
                                   'track', 'length']:
                tune_dict[name] = data

        return tune_dict or None

    def _build_node(self, data):
        item = nbxmpp.Node('tune', {'xmlns': nbxmpp.NS_TUNE})
        if data is None:
            return item
        artist, title, source, track, length = data
        if artist:
            item.addChild('artist', payload=artist)
        if title:
            item.addChild('title', payload=title)
        if source:
            item.addChild('source', payload=source)
        if track:
            item.addChild('track', payload=track)
        if length:
            item.addChild('length', payload=length)
        return item
