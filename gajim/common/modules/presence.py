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

# Presence handler

import time

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import PresenceType

from gajim.common import app
from gajim.common import idle
from gajim.common.i18n import _
from gajim.common.nec import NetworkEvent
from gajim.common.helpers import should_log
from gajim.common.structs import PresenceData
from gajim.common.const import KindConstant
from gajim.common.const import ShowConstant
from gajim.common.modules.base import BaseModule


class Presence(BaseModule):

    _nbxmpp_extends = 'BasePresence'
    _nbxmpp_methods = [
        'subscribed',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._presence_received,
                          priority=50),
            StanzaHandler(name='presence',
                          callback=self._subscribe_received,
                          typ='subscribe',
                          priority=49),
            StanzaHandler(name='presence',
                          callback=self._subscribed_received,
                          typ='subscribed',
                          priority=49),
            StanzaHandler(name='presence',
                          callback=self._unsubscribe_received,
                          typ='unsubscribe',
                          priority=49),
            StanzaHandler(name='presence',
                          callback=self._unsubscribed_received,
                          typ='unsubscribed',
                          priority=49),
        ]

        self._presence_store = {}

        # keep the jids we auto added (transports contacts) to not send the
        # SUBSCRIBED event to GUI
        self.automatically_added = []

        # list of jid to auto-authorize
        self._jids_for_auto_auth = set()

    def _presence_received(self, _con, stanza, properties):
        if properties.from_muc:
            # MUC occupant presences are already handled in MUC module
            return

        muc = self._con.get_module('MUC').get_muc_data(properties.jid)
        if muc is not None:
            # Presence from the MUC itself, used for MUC avatar
            # handled in VCardAvatars module
            return

        self._log.info('Received from %s', properties.jid)

        presence_data = PresenceData.from_presence(properties)
        self._presence_store[properties.jid] = presence_data

        contact = self._con.get_module('Contacts').get_contact(properties.jid)
        contact.update_presence(presence_data)

        if properties.type == PresenceType.ERROR:
            self._log.info('Error: %s %s', properties.jid, properties.error)
            return

        if self._account == 'Local':
            app.nec.push_incoming_event(
                NetworkEvent('raw-pres-received',
                             conn=self._con,
                             stanza=stanza))
            return

        if properties.is_self_presence:
            app.nec.push_incoming_event(
                NetworkEvent('our-show',
                             account=self._account,
                             show=properties.show.value))
            return

        jid = properties.jid.bare
        roster_item = self._con.get_module('Roster').get_item(jid)
        if not properties.is_self_bare and roster_item is None:
            # Handle only presence from roster contacts
            self._log.warning('Unknown presence received')
            self._log.warning(stanza)
            return

        show = properties.show.value
        if properties.type.is_unavailable:
            show = 'offline'

        event_attrs = {
            'account': self._account,
            'conn': self._con,
            'stanza': stanza,
            'prio': properties.priority,
            'need_add_in_roster': False,
            'popup': False,
            'ptype': properties.type.value,
            'jid': properties.jid.bare,
            'resource': properties.jid.resource,
            'id_': properties.id,
            'fjid': str(properties.jid),
            'timestamp': properties.timestamp,
            'avatar_sha': properties.avatar_sha,
            'user_nick': properties.nickname,
            'idle_time': properties.idle_timestamp,
            'show': show,
            'new_show': show,
            'old_show': 0,
            'status': properties.status,
            'contact_list': [],
            'contact': None,
        }

        app.nec.push_incoming_event(
            NetworkEvent('presence-received', **event_attrs))

        self._log_presence(properties)

    def _log_presence(self, properties):
        if not app.settings.get('log_contact_status_changes'):
            return
        if not should_log(self._account, properties.jid.bare):
            return

        show = ShowConstant[properties.show.name]
        if properties.type.is_unavailable:
            show = ShowConstant.OFFLINE

        app.storage.archive.insert_into_logs(self._account,
                                             properties.jid.bare,
                                             time.time(),
                                             KindConstant.STATUS,
                                             message=properties.status,
                                             show=show)

    def _subscribe_received(self, _con, _stanza, properties):
        jid = properties.jid.bare
        fjid = str(properties.jid)

        is_transport = app.jid_is_transport(fjid)
        auto_auth = app.settings.get_account_setting(self._account, 'autoauth')

        self._log.info('Received Subscribe: %s, transport: %s, '
                       'auto_auth: %s, user_nick: %s',
                       properties.jid, is_transport,
                       auto_auth, properties.nickname)

        if auto_auth or jid in self._jids_for_auto_auth:
            self._log.info('Auto respond with subscribed: %s', jid)
            self.subscribed(jid)
            return

        status = (properties.status or
                  _('I would like to add you to my roster.'))

        app.nec.push_incoming_event(NetworkEvent(
            'subscribe-presence-received',
            conn=self._con,
            account=self._account,
            jid=jid,
            fjid=fjid,
            status=status,
            user_nick=properties.nickname,
            is_transport=is_transport))

        raise nbxmpp.NodeProcessed

    def _subscribed_received(self, _con, _stanza, properties):
        jid = properties.jid.bare
        self._log.info('Received Subscribed: %s', properties.jid)
        if jid in self.automatically_added:
            self.automatically_added.remove(jid)
            raise nbxmpp.NodeProcessed

        app.nec.push_incoming_event(NetworkEvent(
            'subscribed-presence-received',
            account=self._account,
            jid=properties.jid))
        raise nbxmpp.NodeProcessed

    def _unsubscribe_received(self, _con, _stanza, properties):
        self._log.info('Received Unsubscribe: %s', properties.jid)
        raise nbxmpp.NodeProcessed

    def _unsubscribed_received(self, _con, _stanza, properties):
        self._log.info('Received Unsubscribed: %s', properties.jid)
        app.nec.push_incoming_event(NetworkEvent(
            'unsubscribed-presence-received',
            conn=self._con,
            account=self._account,
            jid=properties.jid.bare))
        raise nbxmpp.NodeProcessed

    def unsubscribed(self, jid):
        self._log.info('Unsubscribed: %s', jid)
        self._jids_for_auto_auth.discard(jid)
        self._nbxmpp('BasePresence').unsubscribed(jid)

    def unsubscribe(self, jid):
        self._log.info('Unsubscribe from %s', jid)
        self._jids_for_auto_auth.discard(jid)
        self._nbxmpp('BasePresence').unsubscribe(jid)

    def subscribe(self, jid, msg=None, name=None, groups=None, auto_auth=False):
        self._log.info('Request Subscription to %s', jid)

        if auto_auth:
            self._jids_for_auto_auth.add(jid)

        self._con.get_module('Roster').set_item(jid, name, groups=groups)
        self._nbxmpp('BasePresence').subscribe(jid,
                                               status=msg,
                                               nick=app.nicks[self._account])

    def get_presence(self, to=None, typ=None, priority=None,
                     show=None, status=None, nick=None, caps=True,
                     idle_time=False):
        if show not in ('chat', 'away', 'xa', 'dnd'):
            # Gajim sometimes passes invalid show values here
            # until this is fixed this is a workaround
            show = None
        presence = nbxmpp.Presence(to, typ, priority, show, status)
        if nick is not None:
            nick_tag = presence.setTag('nick', namespace=Namespace.NICK)
            nick_tag.setData(nick)

        if (idle_time and
                app.is_installed('IDLE') and
                app.settings.get('autoaway')):
            idle_sec = idle.Monitor.get_idle_sec()
            time_ = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                  time.gmtime(time.time() - idle_sec))

            idle_node = presence.setTag('idle', namespace=Namespace.IDLE)
            idle_node.setAttr('since', time_)

        caps = self._con.get_module('Caps').caps
        if caps is not None and typ != 'unavailable':
            presence.setTag('c',
                            namespace=Namespace.CAPS,
                            attrs=caps._asdict())

        return presence

    def send_presence(self, *args, **kwargs):
        if not app.account_is_connected(self._account):
            return
        presence = self.get_presence(*args, **kwargs)
        app.plugin_manager.extension_point(
            'send-presence', self._account, presence)
        self._log.debug('Send presence:\n%s', presence)
        self._con.connection.send(presence)


def get_instance(*args, **kwargs):
    return Presence(*args, **kwargs), 'Presence'
