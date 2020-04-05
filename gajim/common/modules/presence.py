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
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import PresenceType

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.nec import NetworkEvent
from gajim.common.const import KindConstant
from gajim.common.const import ShowConstant
from gajim.common.modules.base import BaseModule


class Presence(BaseModule):
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

        # keep the jids we auto added (transports contacts) to not send the
        # SUBSCRIBED event to GUI
        self.automatically_added = []

        # list of jid to auto-authorize
        self._jids_for_auto_auth = set()

    def _presence_received(self, _con, stanza, properties):
        if properties.from_muc:
            # MUC occupant presences are already handled in MUC module
            return

        muc = self._con.get_module('MUC').get_manager().get(properties.jid)
        if muc is not None:
            # Presence from the MUC itself, used for MUC avatar
            # handled in VCardAvatars module
            return

        self._log.info('Received from %s', properties.jid)

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
                             conn=self._con,
                             show=properties.show.value))
            return

        jid = properties.jid.getBare()
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
            'conn': self._con,
            'stanza': stanza,
            'prio': properties.priority,
            'need_add_in_roster': False,
            'popup': False,
            'ptype': properties.type.value,
            'jid': properties.jid.getBare(),
            'resource': properties.jid.getResource(),
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

        event_ = NetworkEvent('presence-received', **event_attrs)

        # TODO: Refactor
        self._update_contact(event_, properties)

        app.nec.push_incoming_event(event_)

    def _update_contact(self, event, properties):
        # Note: A similar method also exists in connection_zeroconf
        jid = properties.jid.getBare()
        resource = properties.jid.getResource()

        status_strings = ['offline', 'error', 'online', 'chat', 'away',
                          'xa', 'dnd']

        event.new_show = status_strings.index(event.show)

        # Update contact
        contact_list = app.contacts.get_contacts(self._account, jid)
        if not contact_list:
            self._log.warning('No contact found')
            return

        event.contact_list = contact_list

        contact = app.contacts.get_contact_strict(self._account,
                                                  properties.jid.getBare(),
                                                  properties.jid.getResource())
        if contact is None:
            contact = app.contacts.get_first_contact_from_jid(self._account,
                                                              jid)
            if contact is None:
                self._log.warning('First contact not found')
                return

            if (self._is_resource_known(contact_list) and
                    not app.jid_is_transport(jid)):
                # Another resource of an existing contact connected
                # Add new contact
                event.old_show = 0
                contact = app.contacts.copy_contact(contact)
                contact.resource = resource
                app.contacts.add_contact(self._account, contact)
            else:
                # Convert the inital roster contact to a contact with resource
                contact.resource = resource
                event.old_show = 0
                if contact.show in status_strings:
                    event.old_show = status_strings.index(contact.show)

            event.need_add_in_roster = True

        elif contact.show in status_strings:
            event.old_show = status_strings.index(contact.show)

        # Update contact with presence data
        contact.show = event.show
        contact.status = properties.status
        contact.priority = properties.priority
        contact.idle_time = properties.idle_timestamp

        event.contact = contact

        if not app.jid_is_transport(jid) and len(contact_list) == 1:
            # It's not an agent
            if event.old_show == 0 and event.new_show > 1:
                if not jid in app.newly_added[self._account]:
                    app.newly_added[self._account].append(jid)
                if jid in app.to_be_removed[self._account]:
                    app.to_be_removed[self._account].remove(jid)
            elif event.old_show > 1 and event.new_show == 0 and \
            self._con.state.is_connected:
                if not jid in app.to_be_removed[self._account]:
                    app.to_be_removed[self._account].append(jid)
                if jid in app.newly_added[self._account]:
                    app.newly_added[self._account].remove(jid)

        if app.jid_is_transport(jid):
            return

        if properties.type.is_unavailable:
            # TODO: This causes problems when another
            # resource signs off!
            self._con.get_module('Bytestream').stop_all_active_file_transfers(
                contact)
        self._log_presence(properties)

    @staticmethod
    def _is_resource_known(contact_list):
        if len(contact_list) > 1:
            return True

        if contact_list[0].resource == '':
            return False
        return contact_list[0].show not in ('not in roster', 'offline')

    def _log_presence(self, properties):
        if not app.config.get('log_contact_status_changes'):
            return
        if not app.config.should_log(self._account, properties.jid.getBare()):
            return

        show = ShowConstant[properties.show.name]
        if properties.type.is_unavailable:
            show = ShowConstant.OFFLINE

        app.logger.insert_into_logs(self._account,
                                    properties.jid.getBare(),
                                    time.time(),
                                    KindConstant.STATUS,
                                    message=properties.status,
                                    show=show)

    def _subscribe_received(self, _con, _stanza, properties):
        jid = properties.jid.getBare()
        fjid = str(properties.jid)

        is_transport = app.jid_is_transport(fjid)
        auto_auth = app.config.get_per('accounts', self._account, 'autoauth')

        self._log.info('Received Subscribe: %s, transport: %s, '
                       'auto_auth: %s, user_nick: %s',
                       properties.jid, is_transport,
                       auto_auth, properties.nickname)

        if auto_auth or jid in self._jids_for_auto_auth:
            self.send_presence(fjid, 'subscribed')
            self._jids_for_auto_auth.discard(jid)
            self._log.info('Auto respond with subscribed: %s', jid)
            return

        status = (properties.status or
                  _('I would like to add you to my roster.'))

        app.nec.push_incoming_event(NetworkEvent(
            'subscribe-presence-received',
            conn=self._con,
            jid=jid,
            fjid=fjid,
            status=status,
            user_nick=properties.nickname,
            is_transport=is_transport))

        raise nbxmpp.NodeProcessed

    def _subscribed_received(self, _con, _stanza, properties):
        jid = properties.jid.getBare()
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
            conn=self._con, jid=properties.jid.getBare()))
        raise nbxmpp.NodeProcessed

    def subscribed(self, jid):
        if not app.account_is_available(self._account):
            return
        self._log.info('Subscribed: %s', jid)
        self.send_presence(jid, 'subscribed')

    def unsubscribed(self, jid):
        if not app.account_is_available(self._account):
            return

        self._log.info('Unsubscribed: %s', jid)
        self._jids_for_auto_auth.discard(jid)
        self.send_presence(jid, 'unsubscribed')

    def unsubscribe(self, jid, remove_auth=True):
        if not app.account_is_available(self._account):
            return
        if remove_auth:
            self._con.get_module('Roster').del_item(jid)
            jid_list = app.config.get_per('contacts')
            for j in jid_list:
                if j.startswith(jid):
                    app.config.del_per('contacts', j)
        else:
            self._log.info('Unsubscribe from %s', jid)
            self._jids_for_auto_auth.discard(jid)
            self._con.get_module('Roster').unsubscribe(jid)
            self._con.get_module('Roster').set_item(jid)

    def subscribe(self, jid, msg=None, name='', groups=None, auto_auth=False):
        if not app.account_is_available(self._account):
            return
        if groups is None:
            groups = []

        self._log.info('Request Subscription to %s', jid)

        if auto_auth:
            self.jids_for_auto_auth.add(jid)

        infos = {'jid': jid}
        if name:
            infos['name'] = name
        iq = nbxmpp.Iq('set', nbxmpp.NS_ROSTER)
        query = iq.setQuery()
        item = query.addChild('item', attrs=infos)
        for group in groups:
            item.addChild('group').setData(group)
        self._con.connection.send(iq)

        self.send_presence(jid,
                           'subscribe',
                           status=msg,
                           nick=app.nicks[self._account])

    def get_presence(self, to=None, typ=None, priority=None,
                     show=None, status=None, nick=None, caps=True,
                     idle_time=None):
        if show not in ('chat', 'away', 'xa', 'dnd'):
            # Gajim sometimes passes invalid show values here
            # until this is fixed this is a workaround
            show = None
        presence = nbxmpp.Presence(to, typ, priority, show, status)
        if nick is not None:
            nick_tag = presence.setTag('nick', namespace=nbxmpp.NS_NICK)
            nick_tag.setData(nick)

        if idle_time is not None:
            idle_node = presence.setTag('idle', namespace=nbxmpp.NS_IDLE)
            idle_node.setAttr('since', idle_time)

        if not self._con.avatar_conversion:
            # XEP-0398 not supported by server so
            # we add the avatar sha to our presence
            self._con.get_module('VCardAvatars').add_update_node(presence)

        caps = self._con.get_module('Caps').caps
        if caps is not None and typ != 'unavailable':
            presence.setTag('c',
                            namespace=nbxmpp.NS_CAPS,
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
