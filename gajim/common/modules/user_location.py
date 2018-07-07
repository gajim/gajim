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

# XEP-0080: User Location

import logging

import nbxmpp
from gi.repository import GLib

from gajim.common.const import PEPEventType, LOCATION_DATA
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.user_location')


class UserLocationData(AbstractPEPData):

    type_ = PEPEventType.LOCATION

    def __init__(self, location):
        self._pep_specific_data = location

    def asMarkupText(self):
        location = self._pep_specific_data
        location_string = ''

        for entry in location.keys():
            text = location[entry]
            text = GLib.markup_escape_text(text)
            # Translate standard location tag
            tag = LOCATION_DATA.get(entry, entry)
            location_string += '\n<b>%(tag)s</b>: %(text)s' % {
                'tag': tag.capitalize(), 'text': text}

        return location_string.strip()


class UserLocation(AbstractPEPModule):

    name = 'geoloc'
    namespace = nbxmpp.NS_LOCATION
    pep_class = UserLocationData
    store_publish = True
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []

    def _extract_info(self, item):
        location_dict = {}
        location_tag = item.getTag('geoloc', namespace=nbxmpp.NS_LOCATION)
        if location_tag is None:
            raise StanzaMalformed('No geoloc node')

        for child in location_tag.getChildren():
            name = child.getName().strip()
            data = child.getData().strip()
            if child.getName() in LOCATION_DATA:
                location_dict[name] = data

        return location_dict or None

    def _build_node(self, data):
        item = nbxmpp.Node('geoloc', {'xmlns': nbxmpp.NS_LOCATION})
        if data is None:
            return item
        for field in LOCATION_DATA:
            if data.get(field, False):
                item.addChild(field, payload=data[field])
        return item


def get_instance(*args, **kwargs):
    return UserLocation(*args, **kwargs), 'UserLocation'
