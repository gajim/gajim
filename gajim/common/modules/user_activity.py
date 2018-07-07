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

# XEP-0108: User Activity

import logging

import nbxmpp
from gi.repository import GLib

from gajim.common.const import PEPEventType, ACTIVITIES
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.user_activity')


class UserActivityData(AbstractPEPData):

    type_ = PEPEventType.ACTIVITY

    def __init__(self, activity):
        self._pep_specific_data = activity

    def asMarkupText(self):
        pep = self._pep_specific_data
        activity = pep['activity']
        subactivity = pep['subactivity'] if 'subactivity' in pep else None
        text = pep['text'] if 'text' in pep else None

        if activity in ACTIVITIES:
            # Translate standard activities
            if subactivity in ACTIVITIES[activity]:
                subactivity = ACTIVITIES[activity][subactivity]
            activity = ACTIVITIES[activity]['category']

        markuptext = '<b>' + GLib.markup_escape_text(activity)
        if subactivity:
            markuptext += ': ' + GLib.markup_escape_text(subactivity)
        markuptext += '</b>'
        if text:
            markuptext += ' (%s)' % GLib.markup_escape_text(text)
        return markuptext


class UserActivity(AbstractPEPModule):

    name = 'activity'
    namespace = nbxmpp.NS_ACTIVITY
    pep_class = UserActivityData
    store_publish = True
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []

    def _extract_info(self, item):
        activity_dict = {}
        activity_tag = item.getTag('activity', namespace=self.namespace)
        if activity_tag is None:
            raise StanzaMalformed('No activity node')

        for child in activity_tag.getChildren():
            name = child.getName().strip()
            data = child.getData().strip()
            if name == 'text':
                activity_dict['text'] = data
            else:
                activity_dict['activity'] = name
                for subactivity in child.getChildren():
                    subactivity_name = subactivity.getName().strip()
                    activity_dict['subactivity'] = subactivity_name

        return activity_dict or None

    def _build_node(self, data):
        item = nbxmpp.Node('activity', {'xmlns': self.namespace})
        if data is None:
            return
        activity, subactivity, message = data
        if activity:
            i = item.addChild(activity)
            if subactivity:
                i.addChild(subactivity)
        if message:
            i = item.addChild('text')
            i.addData(message)
        return item


def get_instance(*args, **kwargs):
    return UserActivity(*args, **kwargs), 'UserActivity'
