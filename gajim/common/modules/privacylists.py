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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0016: Privacy Lists

import logging

import nbxmpp

from gajim.common import app
from gajim.common import helpers
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.connection_handlers_events import InformationEvent


log = logging.getLogger('gajim.c.m.privacylists')


class PrivacyLists:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.default_list = None
        self.active_list = None
        self.blocked_contacts = []
        self.blocked_groups = []
        self.blocked_list = []
        self.blocked_all = False

        self.handlers = [
            ('iq', self._list_push_received, 'set', nbxmpp.NS_PRIVACY)
        ]

        self.supported = False

    def pass_disco(self, from_, identities, features, data, node):
        if nbxmpp.NS_PRIVACY not in features:
            return

        self.supported = True
        log.info('Discovered XEP-0016: Privacy Lists: %s', from_)
        # TODO: Move this GUI code out
        action = app.app.lookup_action('%s-privacylists' % self._account)
        action.set_enabled(True)

    def _list_push_received(self, con, stanza):
        result = stanza.buildReply('result')
        result.delChild(result.getTag('query'))
        self._con.connection.send(result)

        for list_ in stanza.getQueryPayload():
            if list_.getName() == 'list':
                name = list_.getAttr('name')
                log.info('Received Push: %s', name)
                self.get_privacy_list(name)

        raise nbxmpp.NodeProcessed

    def get_privacy_lists(self, callback=None):
        log.info('Request lists')
        iq = nbxmpp.Iq('get', nbxmpp.NS_PRIVACY)
        self._con.connection.SendAndCallForResponse(
            iq, self._privacy_lists_received, {'callback': callback})

    def _privacy_lists_received(self, conn, stanza, callback):
        lists = []
        new_default = None
        result = nbxmpp.isResultNode(stanza)
        if not result:
            log.warning('List not available: %s', stanza.getError())
        else:
            for list_ in stanza.getQueryPayload():
                name = list_.getAttr('name')
                if list_.getName() == 'active':
                    self.active_list = name
                elif list_.getName() == 'default':
                    new_default = name
                else:
                    lists.append(name)

        log.info('Received lists: %s', lists)

        # Download default list if we dont have it
        if self.default_list != new_default:
            self.default_list = new_default
            if new_default is not None:
                log.info('Found new default list: %s', new_default)
                self.get_privacy_list(new_default)

        if callback:
            callback(result)
        else:
            app.nec.push_incoming_event(
                PrivacyListsReceivedEvent(None,
                                          conn=self._con,
                                          active_list=self.active_list,
                                          default_list=self.default_list,
                                          lists=lists))

    def get_privacy_list(self, name):
        log.info('Request list: %s', name)
        list_ = nbxmpp.Node('list', {'name': name})
        iq = nbxmpp.Iq('get', nbxmpp.NS_PRIVACY, payload=[list_])
        self._con.connection.SendAndCallForResponse(
            iq, self._privacy_list_received)

    def _privacy_list_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.warning('List not available: %s', stanza.getError())
            return

        rules = []
        list_ = stanza.getQueryPayload()[0]
        name = list_.getAttr('name')

        for child in list_.getChildren():

            item = child.getAttrs()

            childs = []
            for scnd_child in child.getChildren():
                childs.append(scnd_child.getName())

            item['child'] = childs
            if len(item) not in (3, 5):
                log.warning('Wrong count of attrs: %s', stanza)
                continue
            rules.append(item)

        log.info('Received list: %s', name)

        if name == self.default_list:
            self._default_list_received(rules)

        app.nec.push_incoming_event(PrivacyListReceivedEvent(
            None, conn=self._con, list_name=name, rules=rules))

    def del_privacy_list(self, name):
        log.info('Remove list: %s', name)

        def _del_privacy_list_result(stanza):
            if not nbxmpp.isResultNode(stanza):
                log.warning('List deletion failed: %s', stanza.getError())
                app.nec.push_incoming_event(InformationEvent(
                    None, dialog_name='privacy-list-error', args=name))
            else:
                app.nec.push_incoming_event(PrivacyListRemovedEvent(
                    None, conn=self._con, list_name=name))

        node = nbxmpp.Node('list', {'name': name})
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, payload=[node])
        self._con.connection.SendAndCallForResponse(
            iq, _del_privacy_list_result)

    def set_privacy_list(self, name, rules):
        node = nbxmpp.Node('list', {'name': name})
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, payload=[node])
        for item in rules:
            childs = item.get('child', [])
            for child in childs:
                node.setTag(child)
            item.pop('child', None)
            node.setTag('item', item)
        log.info('Update list: %s %s', name, rules)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_result_handler, {})

    def _default_list_received(self, rules):
        roster = app.interface.roster

        for rule in rules:
            if rule['action'] == 'allow':
                if 'type' not in rule:
                    self.blocked_all = False

                elif rule['type'] == 'jid':
                    if rule['value'] in self.blocked_contacts:
                        self.blocked_contacts.remove(rule['value'])

                elif rule['type'] == 'group':
                    if rule['value'] in self.blocked_groups:
                        self.blocked_groups.remove(rule['value'])

            elif rule['action'] == 'deny':
                if 'type' not in rule:
                    self.blocked_all = True

                elif rule['type'] == 'jid':
                    if rule['value'] not in self.blocked_contacts:
                        self.blocked_contacts.append(rule['value'])

                elif rule['type'] == 'group':
                    if rule['value'] not in self.blocked_groups:
                        self.blocked_groups.append(rule['value'])

            self.blocked_list.append(rule)

            if 'type' in rule:
                if rule['type'] == 'jid':
                    roster.draw_contact(rule['value'], self._account)
                if rule['type'] == 'group':
                    roster.draw_group(rule['value'], self._account)

    def set_active_list(self, name=None):
        log.info('Set active list: %s', name)
        attr = {}
        if name:
            attr['name'] = name
        node = nbxmpp.Node('active', attr)
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, payload=[node])
        self._con.connection.SendAndCallForResponse(
            iq, self._default_result_handler, {})

    def set_default_list(self, name=None):
        log.info('Set default list: %s', name)
        attr = {}
        if name:
            attr['name'] = name
        node = nbxmpp.Node('default', attr)
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, payload=[node])
        self._con.connection.SendAndCallForResponse(
            iq, self._default_result_handler, {})

    def _default_result_handler(self, conn, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Operation failed: %s', stanza.getError())

    def _build_invisible_rule(self):
        node = nbxmpp.Node('list', {'name': 'invisible'})
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, payload=[node])
        if self._account in app.interface.status_sent_to_groups and \
        len(app.interface.status_sent_to_groups[self._account]) > 0:
            for group in app.interface.status_sent_to_groups[self._account]:
                item = node.setTag('item', {'type': 'group',
                                            'value': group,
                                            'action': 'allow',
                                            'order': '1'})
                item.setTag('presence-out')

        if self._account in app.interface.status_sent_to_users and \
        len(app.interface.status_sent_to_users[self._account]) > 0:
            for jid in app.interface.status_sent_to_users[self._account]:
                item = node.setTag('item', {'type': 'jid',
                                            'value': jid,
                                            'action': 'allow',
                                            'order': '2'})
                item.setTag('presence-out')

        item = node.setTag('item', {'action': 'deny', 'order': '3'})
        item.setTag('presence-out')
        return iq

    def set_invisible_rule(self, callback=None, **kwargs):
        log.info('Update invisible list')
        iq = self._build_invisible_rule()
        if callback is None:
            callback = self._default_result_handler
        self._con.connection.SendAndCallForResponse(
            iq, callback, kwargs)

    def _get_max_blocked_list_order(self):
        max_order = 0
        for rule in self.blocked_list:
            order = int(rule['order'])
            if order > max_order:
                max_order = order
        return max_order

    def block_gc_contact(self, jid):
        if jid in self.blocked_contacts:
            return
        log.info('Block GC contact: %s', jid)

        if self.default_list is None:
            self.default_list = 'block'

        max_order = self._get_max_blocked_list_order()
        new_rule = {'order': str(max_order + 1),
                    'type': 'jid',
                    'action': 'deny',
                    'value': jid,
                    'child': ['message', 'iq', 'presence-out']}
        self.blocked_list.append(new_rule)
        self.blocked_contacts.append(jid)
        self.set_privacy_list(self.default_list, self.blocked_list)
        if len(self.blocked_list) == 1:
            self.set_default_list(self.default_list)

    def block_contacts(self, contact_list, message):
        if not self.supported:
            self._con.get_module('Blocking').block(contact_list)
            return

        if self.default_list is None:
            self.default_list = 'block'
        for contact in contact_list:
            log.info('Block contacts: %s', contact.jid)
            contact.show = 'offline'
            self._con.send_custom_status('offline', message, contact.jid)
            max_order = self._get_max_blocked_list_order()
            new_rule = {'order': str(max_order + 1),
                        'type': 'jid',
                        'action': 'deny',
                        'value': contact.jid}
            self.blocked_list.append(new_rule)
            self.blocked_contacts.append(contact.jid)
        self.set_privacy_list(self.default_list, self.blocked_list)
        if len(self.blocked_list) == 1:
            self.set_default_list(self.default_list)

    def unblock_gc_contact(self, jid):
        new_blocked_list = []
        # needed for draw_contact:
        if jid not in self.blocked_contacts:
            return

        self.blocked_contacts.remove(jid)

        log.info('Unblock GC contact: %s', jid)
        for rule in self.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'jid' \
            or rule['value'] != jid:
                new_blocked_list.append(rule)

        if len(new_blocked_list) == 0:
            self.blocked_list = []
            self.blocked_contacts = []
            self.blocked_groups = []
            self.set_default_list(None)
            self.del_privacy_list(self.default_list)
        else:
            self.set_privacy_list(self.default_list, new_blocked_list)

    def unblock_contacts(self, contact_list):
        if not self.supported:
            self._con.get_module('Blocking').unblock(contact_list)
            return

        new_blocked_list = []
        to_unblock = []
        for contact in contact_list:
            log.info('Unblock contacts: %s', contact.jid)
            to_unblock.append(contact.jid)
            if contact.jid in self.blocked_contacts:
                self.blocked_contacts.remove(contact.jid)
        for rule in self.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'jid' \
            or rule['value'] not in to_unblock:
                new_blocked_list.append(rule)

        if len(new_blocked_list) == 0:
            self.blocked_list = []
            self.blocked_contacts = []
            self.blocked_groups = []
            self.set_default_list(None)
            self.del_privacy_list(self.default_list)
        else:
            self.set_privacy_list(self.default_list, new_blocked_list)
        if not app.interface.roster.regroup:
            show = app.SHOW_LIST[self._con.connected]
        else:   # accounts merged
            show = helpers.get_global_show()
        if show == 'invisible':
            return
        for contact in contact_list:
            self._con.send_custom_status(show, self._con.status, contact.jid)
            self._presence_probe(contact.jid)

    def block_group(self, group, contact_list, message):
        if not self.supported:
            return
        if group in self.blocked_groups:
            return
        self.blocked_groups.append(group)

        log.info('Block group: %s', group)

        if self.default_list is None:
            self.default_list = 'block'

        for contact in contact_list:
            self._con.send_custom_status('offline', message, contact.jid)

        max_order = self._get_max_blocked_list_order()
        new_rule = {'order': str(max_order + 1),
                    'type': 'group',
                    'action': 'deny',
                    'value': group}

        self.blocked_list.append(new_rule)
        self.set_privacy_list(self.default_list, self.blocked_list)
        if len(self.blocked_list) == 1:
            self.set_default_list(self.default_list)

    def unblock_group(self, group, contact_list):
        if not self.supported:
            return

        if group not in self.blocked_groups:
            return
        self.blocked_groups.remove(group)

        log.info('Unblock group: %s', group)
        new_blocked_list = []
        for rule in self.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'group' or \
            rule['value'] != group:
                new_blocked_list.append(rule)

        if len(new_blocked_list) == 0:
            self.blocked_list = []
            self.blocked_contacts = []
            self.blocked_groups = []
            self.set_default_list('')
            self.del_privacy_list(self.default_list)
        else:
            self.set_privacy_list(self.default_list, new_blocked_list)
        if not app.interface.roster.regroup:
            show = app.SHOW_LIST[self._con.connected]
        else:   # accounts merged
            show = helpers.get_global_show()
        if show == 'invisible':
            return
        for contact in contact_list:
            self._con.send_custom_status(show, self._con.status, contact.jid)

    def _presence_probe(self, jid):
        log.info('Presence probe: %s', jid)
        # Send a presence Probe to get the current Status
        probe = nbxmpp.Presence(jid, 'probe', frm=self._con.get_own_jid())
        self._con.connection.send(probe)


class PrivacyListsReceivedEvent(NetworkIncomingEvent):
    name = 'privacy-lists-received'


class PrivacyListReceivedEvent(NetworkIncomingEvent):
    name = 'privacy-list-received'


class PrivacyListRemovedEvent(NetworkIncomingEvent):
    name = 'privacy-list-removed'


def get_instance(*args, **kwargs):
    return PrivacyLists(*args, **kwargs), 'PrivacyLists'
