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

from gajim.common import app
from gajim.common.const import PEPEventType, ACTIVITIES
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import PEPReceivedEvent, PEPEvent, AbstractPEP

log = logging.getLogger('gajim.c.m.user_activity')


class UserActivity(PEPEvent):

    name = 'activity'

    def __init__(self, con):
        PEPEvent.__init__(self, con, con.name)
        self._con = con
        self._account = con.name

        self.handlers = []

        self._stored_publish = None

        self._con.get_module('PEP').register_pep_handler(
            nbxmpp.NS_ACTIVITY,
            self._pep_notify_received,
            self._pep_retract_received)

    def _pep_notify_received(self, jid, item):
        try:
            activity = self._extract_info(item)
        except StanzaMalformed as error:
            log.warning('%s, %s: %s', jid, error, item)
            return

        log.info('Received: %s %s', jid, activity)
        self._push_event(jid, UserActivityPEP(activity))

    def _pep_retract_received(self, jid, id_):
        log.info('Retract: %s %s', jid, id_)
        self._push_event(jid, UserActivityPEP(None))

    def _push_event(self, jid, user_pep):
        self._update_contacts(jid, user_pep)
        app.nec.push_incoming_event(
            PEPReceivedEvent(None, conn=self._con,
                             jid=str(jid),
                             pep_type=self.name))

    def _extract_info(self, item):
        activity_dict = {}
        activity_tag = item.getTag('activity', namespace=nbxmpp.NS_ACTIVITY)
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

    def send_stored_publish(self):
        if self._stored_publish is not None:
            log.info('Send stored publish')
            self.send_activity(*self._stored_publish)
            self._stored_publish = None

    def reset_stored_publish(self):
        log.info('Reset stored publish')
        self._stored_publish = None

    def send_activity(self, activity=None, subactivity=None, message=None):
        if not self._con.pep_supported:
            return

        if self._con.connected == 1:
            # We are connecting, save activity and send it later
            self._stored_publish = (activity, subactivity, message)
            return

        if activity:
            log.info('Send activity: %s %s %s', activity, subactivity, message)
        else:
            log.info('Remove activity')

        item = self._build_activity_node(activity, subactivity, message)

        self._con.get_module('PubSub').send_pb_publish(
            '', nbxmpp.NS_ACTIVITY, item, 'current')

    def _build_activity_node(self, activity, subactivity=None, message=None):
        item = nbxmpp.Node('activity', {'xmlns': nbxmpp.NS_ACTIVITY})
        if activity:
            i = item.addChild(activity)
            if subactivity:
                i.addChild(subactivity)
        if message:
            i = item.addChild('text')
            i.addData(message)
        return item

    def retract_activity(self):
        if not self._con.pep_supported:
            return
        self.send_activity()
        self._con.get_module('PubSub').send_pb_retract(
            '', nbxmpp.NS_ACTIVITY, 'current')


class UserActivityPEP(AbstractPEP):

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
