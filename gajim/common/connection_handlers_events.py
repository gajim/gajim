# -*- coding:utf-8 -*-
## src/common/connection_handlers_events.py
##
## Copyright (C) 2010-2014 Yann Leboulanger <asterix AT lagaule.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

# pylint: disable=no-init
# pylint: disable=attribute-defined-outside-init

from calendar import timegm
import datetime
import hashlib
import binascii
import base64
import hmac
import logging
import sys
import os
from time import time as time_time

import nbxmpp
from nbxmpp.protocol import NS_CHATSTATES
from gajim.common import atom
from gajim.common import nec
from gajim.common import helpers
from gajim.common import app
from gajim.common import i18n
from gajim.common import dataforms
from gajim.common import exceptions
from gajim.common.zeroconf.zeroconf import Constant
from gajim.common.logger import LOG_DB_PATH, KindConstant
from gajim.common.pep import SUPPORTED_PERSONAL_USER_EVENTS
from gajim.common.jingle_transport import JingleTransportSocks5
from gajim.common.file_props import FilesProp
from gajim.common.nec import NetworkEvent

if app.HAVE_PYOPENSSL:
    import OpenSSL.crypto

log = logging.getLogger('gajim.c.connection_handlers_events')

CONDITION_TO_CODE = {
    'realjid-public': 100,
    'affiliation-changed': 101,
    'unavailable-shown': 102,
    'unavailable-not-shown': 103,
    'configuration-changed': 104,
    'self-presence': 110,
    'logging-enabled': 170,
    'logging-disabled': 171,
    'non-anonymous': 172,
    'semi-anonymous': 173,
    'fully-anonymous': 174,
    'room-created': 201,
    'nick-assigned': 210,
    'banned': 301,
    'new-nick': 303,
    'kicked': 307,
    'removed-affiliation': 321,
    'removed-membership': 322,
    'removed-shutdown': 332,
}

class HelperEvent:
    def get_jid_resource(self, check_fake_jid=False):
        if check_fake_jid and hasattr(self, 'id_') and \
                self.id_ in self.conn.groupchat_jids:
            self.fjid = self.conn.groupchat_jids[self.id_]
            del self.conn.groupchat_jids[self.id_]
        else:
            self.fjid = helpers.get_full_jid_from_iq(self.stanza)
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)

    def get_id(self):
        self.id_ = self.stanza.getID()

    def get_gc_control(self):
        self.gc_control = app.interface.msg_win_mgr.get_gc_control(self.jid,
                                                                     self.conn.name)

        # If gc_control is missing - it may be minimized. Try to get it
        # from there. If it's not there - then it's missing anyway and
        # will remain set to None.
        if not self.gc_control:
            minimized = app.interface.minimized_controls[self.conn.name]
            self.gc_control = minimized.get(self.jid)

    def _generate_timestamp(self, tag):
        # Make sure we use only int/float Epoch time
        if not isinstance(tag, str):
            self.timestamp = time_time()
            return
        try:
            tim = helpers.datetime_tuple(tag)
            self.timestamp = timegm(tim)
        except Exception:
            log.error('wrong timestamp, ignoring it: ' + tag)
            self.timestamp = time_time()

    def get_chatstate(self):
        """
        Extract chatstate from a <message/> stanza
        Requires self.stanza and self.msgtxt
        """
        self.chatstate = None

        # chatstates - look for chatstate tags in a message if not delayed
        delayed = self.stanza.getTag('x', namespace=nbxmpp.NS_DELAY) is not None
        if not delayed:
            children = self.stanza.getChildren()
            for child in children:
                if child.getNamespace() == NS_CHATSTATES:
                    self.chatstate = child.getName()
                    break

    def get_oob_data(self, stanza):
        oob_node = stanza.getTag('x', namespace=nbxmpp.NS_X_OOB)
        if oob_node is not None:
            if 'gajim' not in self.additional_data:
                self.additional_data['gajim'] = {}
            oob_url = oob_node.getTagData('url')
            if oob_url is not None:
                self.additional_data['gajim']['oob_url'] = oob_url
            oob_desc = oob_node.getTagData('desc')
            if oob_desc is not None:
                self.additional_data['gajim']['oob_desc'] = oob_desc

    def get_stanza_id(self, stanza, query=False):
        if query:
            # On a MAM query the stanza-id is maybe not set, so
            # get the id of the stanza
            return stanza.getAttr('id')
        stanza_id, by = stanza.getStanzaIDAttrs()
        if by is None:
            # We can not verify who set this stanza-id, ignore it.
            return
        if stanza.getType() == 'groupchat':
            if stanza.getFrom().bareMatch(by):
                # by attribute must match the server
                return stanza_id
        elif self.conn.get_own_jid().bareMatch(by):
            # by attribute must match the server
            return stanza_id
        return

    @staticmethod
    def get_forwarded_message(stanza):
        forwarded = stanza.getTag('forwarded',
                                  namespace=nbxmpp.NS_FORWARD,
                                  protocol=True)
        if forwarded is not None:
            return forwarded.getTag('message', protocol=True)

class HttpAuthReceivedEvent(nec.NetworkIncomingEvent):
    name = 'http-auth-received'
    base_network_events = []

    def generate(self):
        self.opt = app.config.get_per('accounts', self.conn.name, 'http_auth')
        self.iq_id = self.stanza.getTagAttr('confirm', 'id')
        self.method = self.stanza.getTagAttr('confirm', 'method')
        self.url = self.stanza.getTagAttr('confirm', 'url')
        # In case it's a message with a body
        self.msg = self.stanza.getTagData('body')
        return True

class VersionResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'version-result-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource(check_fake_jid=True)
        if self.id_ in self.conn.version_ids:
            self.conn.version_ids.remove(self.id_)

        self.client_info = ''
        self.os_info = ''

        if self.stanza.getType() == 'error':
            return True

        qp = self.stanza.getTag('query')
        if qp.getTag('name'):
            self.client_info += qp.getTag('name').getData()
        if qp.getTag('version'):
            self.client_info += ' ' + qp.getTag('version').getData()
        if qp.getTag('os'):
            self.os_info += qp.getTag('os').getData()

        return True

class TimeResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'time-result-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource(check_fake_jid=True)
        if self.id_ in self.conn.entity_time_ids:
            self.conn.entity_time_ids.remove(self.id_)

        self.time_info = ''

        if self.stanza.getType() == 'error':
            return True

        qp = self.stanza.getTag('time')
        if not qp:
            # wrong answer
            return
        tzo = qp.getTag('tzo').getData()
        if tzo.lower() == 'z':
            tzo = '0:0'
        try:
            tzoh, tzom = tzo.split(':')
        except Exception as e:
            # wrong tzo
            return
        utc_time = qp.getTag('utc').getData()
        ZERO = datetime.timedelta(0)
        class UTC(datetime.tzinfo):
            def utcoffset(self, dt):
                return ZERO
            def tzname(self, dt):
                return "UTC"
            def dst(self, dt):
                return ZERO

        class contact_tz(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(hours=int(tzoh), minutes=int(tzom))
            def tzname(self, dt):
                return "remote timezone"
            def dst(self, dt):
                return ZERO

        if utc_time[-1:] == 'Z':
            # Remove the trailing 'Z'
            utc_time = utc_time[:-1]
        elif utc_time[-6:] == "+00:00":
            # Remove the trailing "+00:00"
            utc_time = utc_time[:-6]
        else:
            log.info("Wrong timezone defintion: %s" % utc_time)
            return
        try:
            t = datetime.datetime.strptime(utc_time, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                t = datetime.datetime.strptime(utc_time,
                                               '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError as e:
                log.info('Wrong time format: %s' % str(e))
                return

        t = t.replace(tzinfo=UTC())
        self.time_info = t.astimezone(contact_tz()).strftime('%c')
        return True

class RosterItemExchangeEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'roster-item-exchange-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        self.exchange_items_list = {}
        items_list = self.stanza.getTag('x').getChildren()
        if not items_list:
            return
        self.action = items_list[0].getAttr('action')
        if self.action is None:
            self.action = 'add'
        for item in self.stanza.getTag('x', namespace=nbxmpp.NS_ROSTERX).\
        getChildren():
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            contact = app.contacts.get_contact(self.conn.name, jid)
            groups = []
            same_groups = True
            for group in item.getTags('group'):
                groups.append(group.getData())
                # check that all suggested groups are in the groups we have for
                # this contact
                if not contact or group not in contact.groups:
                    same_groups = False
            if contact:
                # check that all groups we have for this contact are in the
                # suggested groups
                for group in contact.groups:
                    if group not in groups:
                        same_groups = False
                if contact.sub in ('both', 'to') and same_groups:
                    continue
            self.exchange_items_list[jid] = []
            self.exchange_items_list[jid].append(name)
            self.exchange_items_list[jid].append(groups)
        if self.exchange_items_list:
            return True

class VersionRequestEvent(nec.NetworkIncomingEvent):
    name = 'version-request-received'
    base_network_events = []

class LastRequestEvent(nec.NetworkIncomingEvent):
    name = 'last-request-received'
    base_network_events = []

class TimeRequestEvent(nec.NetworkIncomingEvent):
    name = 'time-request-received'
    base_network_events = []

class TimeRevisedRequestEvent(nec.NetworkIncomingEvent):
    name = 'time-revised-request-received'
    base_network_events = []

class RosterReceivedEvent(nec.NetworkIncomingEvent):
    name = 'roster-received'
    base_network_events = []

    def generate(self):
        if hasattr(self, 'xmpp_roster'):
            self.version = self.xmpp_roster.version
            self.received_from_server = self.xmpp_roster.received_from_server
            self.roster = {}
            raw_roster = self.xmpp_roster.getRaw()
            our_jid = app.get_jid_from_account(self.conn.name)

            for jid in raw_roster:
                try:
                    j = helpers.parse_jid(jid)
                except Exception:
                    print(_('JID %s is not RFC compliant. It will not be added '
                            'to your roster. Use roster management tools such as '
                            'http://jru.jabberstudio.org/ to remove it') % jid,
                          file=sys.stderr)
                else:
                    infos = raw_roster[jid]
                    if jid != our_jid and (not infos['subscription'] or \
                            infos['subscription'] == 'none') and (not infos['ask'] or \
                            infos['ask'] == 'none') and not infos['name'] and \
                            not infos['groups']:
                        # remove this useless item, it won't be shown in roster
                        # anyway
                        self.conn.connection.getRoster().delItem(jid)
                    elif jid != our_jid: # don't add our jid
                        self.roster[j] = raw_roster[jid]
                        self.roster[j]['avatar_sha'] = None
        else:
            # Roster comes from DB
            self.received_from_server = False
            self.version = app.config.get_per('accounts', self.conn.name,
                'roster_version')
            self.roster = app.logger.get_roster(app.get_jid_from_account(
                self.conn.name))
            if not self.roster:
                app.config.set_per(
                    'accounts', self.conn.name, 'roster_version', '')
        return True

class RosterSetReceivedEvent(nec.NetworkIncomingEvent):
    name = 'roster-set-received'
    base_network_events = []

    def generate(self):
        frm = helpers.get_jid_from_iq(self.stanza)
        our_jid = app.get_jid_from_account(self.conn.name)
        if frm and frm != our_jid and frm != app.get_server_from_jid(our_jid):
            return
        self.version = self.stanza.getTagAttr('query', 'ver')
        self.items = {}
        for item in self.stanza.getTag('query').getChildren():
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            sub = item.getAttr('subscription')
            ask = item.getAttr('ask')
            groups = []
            for group in item.getTags('group'):
                groups.append(group.getData())
            self.items[jid] = {'name': name, 'sub': sub, 'ask': ask,
                'groups': groups}
        if len(self.items) > 1:
            reply = nbxmpp.Iq(typ='error', attrs={'id': self.stanza.getID()},
                to=self.stanza.getFrom(), frm=self.stanza.getTo(), xmlns=None)
            self.conn.connection.send(reply)
            return
        if self.conn.connection and self.conn.connected > 1:
            reply = nbxmpp.Iq(typ='result', attrs={'id': self.stanza.getID()},
                to=self.stanza.getFrom(), frm=self.stanza.getTo(), xmlns=None)
            self.conn.connection.send(reply)
        return True

class RosterInfoEvent(nec.NetworkIncomingEvent):
    name = 'roster-info'
    base_network_events = []

    def init(self):
        self.avatar_sha = None

class MucOwnerReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'muc-owner-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        qp = self.stanza.getQueryPayload()
        self.form_node = None
        for q in qp:
            if q.getNamespace() == nbxmpp.NS_DATA:
                self.form_node = q
                self.dataform = dataforms.ExtendForm(node=self.form_node)
                return True

class MucAdminReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'muc-admin-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        items = self.stanza.getTag('query',
            namespace=nbxmpp.NS_MUC_ADMIN).getTags('item')
        self.users_dict = {}
        for item in items:
            if item.has_attr('jid') and item.has_attr('affiliation'):
                try:
                    jid = helpers.parse_jid(item.getAttr('jid'))
                except helpers.InvalidFormat:
                    log.warning('Invalid JID: %s, ignoring it' % \
                        item.getAttr('jid'))
                    continue
                affiliation = item.getAttr('affiliation')
                self.users_dict[jid] = {'affiliation': affiliation}
                if item.has_attr('nick'):
                    self.users_dict[jid]['nick'] = item.getAttr('nick')
                if item.has_attr('role'):
                    self.users_dict[jid]['role'] = item.getAttr('role')
                reason = item.getTagData('reason')
                if reason:
                    self.users_dict[jid]['reason'] = reason
        return True

class PrivateStorageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'private-storage-received'
    base_network_events = []

    def generate(self):
        query = self.stanza.getTag('query')
        self.storage_node = query.getTag('storage')
        if self.storage_node:
            self.namespace = self.storage_node.getNamespace()
            return True


class BookmarksHelper:
    def parse_bookmarks(self):
        self.bookmarks = []
        NS_GAJIM_BM = 'xmpp:gajim.org/bookmarks'
        confs = self.storage_node.getTags('conference')
        for conf in confs:
            autojoin_val = conf.getAttr('autojoin')
            if not autojoin_val:  # not there (it's optional)
                autojoin_val = False
            minimize_val = conf.getTag('minimize', namespace=NS_GAJIM_BM)
            if not minimize_val:  # not there, try old Gajim behaviour
                minimize_val = conf.getAttr('minimize')
                if not minimize_val:  # not there (it's optional)
                    minimize_val = False
            else:
                minimize_val = minimize_val.getData()

            print_status = conf.getTag('print_status', namespace=NS_GAJIM_BM)
            if not print_status:  # not there, try old Gajim behaviour
                print_status = conf.getTagData('print_status')
                if not print_status:  # not there, try old Gajim behaviour
                    print_status = conf.getTagData('show_status')
            else:
                print_status = print_status.getData()

            try:
                jid = helpers.parse_jid(conf.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it'
                            % conf.getAttr('jid'))
                continue

            bm = {'name': conf.getAttr('name'),
                  'jid': jid,
                  'autojoin': autojoin_val,
                  'minimize': minimize_val,
                  'password': conf.getTagData('password'),
                  'nick': conf.getTagData('nick'),
                  'print_status': print_status}

            bm_jids = [b['jid'] for b in self.bookmarks]
            if bm['jid'] not in bm_jids:
                self.bookmarks.append(bm)

class PrivateStorageBookmarksReceivedEvent(nec.NetworkIncomingEvent,
BookmarksHelper):
    name = 'private-storage-bookmarks-received'
    base_network_events = ['private-storage-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.storage_node = self.base_event.storage_node
        if self.base_event.namespace != nbxmpp.NS_BOOKMARKS:
            return
        self.parse_bookmarks()
        return True

class BookmarksReceivedEvent(nec.NetworkIncomingEvent):
    name = 'bookmarks-received'
    base_network_events = ['private-storage-bookmarks-received',
        'pubsub-bookmarks-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.bookmarks = self.base_event.bookmarks
        return True

class PrivateStorageRosternotesReceivedEvent(nec.NetworkIncomingEvent):
    name = 'private-storage-rosternotes-received'
    base_network_events = ['private-storage-received']

    def generate(self):
        self.conn = self.base_event.conn
        if self.base_event.namespace != nbxmpp.NS_ROSTERNOTES:
            return
        notes = self.base_event.storage_node.getTags('note')
        self.annotations = {}
        for note in notes:
            try:
                jid = helpers.parse_jid(note.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it' % note.getAttr('jid'))
                continue
            annotation = note.getData()
            self.annotations[jid] = annotation
        if self.annotations:
            return True

class RosternotesReceivedEvent(nec.NetworkIncomingEvent):
    name = 'rosternotes-received'
    base_network_events = ['private-storage-rosternotes-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.annotations = self.base_event.annotations
        return True

class PubsubReceivedEvent(nec.NetworkIncomingEvent):
    name = 'pubsub-received'
    base_network_events = []

    def generate(self):
        self.jid = self.stanza.getFrom()
        self.pubsub_node = self.stanza.getTag('pubsub')
        if not self.pubsub_node:
            return
        self.items_node = self.pubsub_node.getTag('items')
        if not self.items_node:
            return
        return True

class PubsubBookmarksReceivedEvent(nec.NetworkIncomingEvent, BookmarksHelper):
    name = 'pubsub-bookmarks-received'
    base_network_events = ['pubsub-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.item_node = self.base_event.items_node.getTag('item')
        if not self.item_node:
            return
        children = self.item_node.getChildren()
        if not children:
            return
        self.storage_node = children[0]
        ns = self.storage_node.getNamespace()
        if ns != nbxmpp.NS_BOOKMARKS:
            return
        self.parse_bookmarks()
        return True

class PubsubAvatarReceivedEvent(nec.NetworkIncomingEvent):
    name = 'pubsub-avatar-received'
    base_network_events = ['pubsub-received']

    def __init__(self, name, base_event):
        '''
        Pre-Generated attributes on self:

        :conn:          Connection instance
        :jid:           The from jid
        :pubsub_node:   The 'pubsub' node
        :items_node:    The 'items' node
        '''
        self._set_base_event_vars_as_attributes(base_event)

    def generate(self):
        if self.items_node.getAttr('node') != 'urn:xmpp:avatar:data':
            return
        item = self.items_node.getTag('item')
        if not item:
            log.warning('Received malformed avatar data via pubsub')
            log.debug(self.stanza)
            return
        self.sha = item.getAttr('id')
        data_tag = item.getTag('data', namespace='urn:xmpp:avatar:data')
        if self.sha is None or data_tag is None:
            log.warning('Received malformed avatar data via pubsub')
            log.debug(self.stanza)
            return
        self.data = data_tag.getData()
        if self.data is None:
            log.warning('Received malformed avatar data via pubsub')
            log.debug(self.stanza)
            return
        try:
            self.data = base64.b64decode(self.data.encode('utf-8'))
        except binascii.Error as err:
            log.debug('Received malformed avatar data via pubsub: %s' % err)
            return

        return True

class SearchFormReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'search-form-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.data = None
        self.is_dataform = False
        tag = self.stanza.getTag('query', namespace=nbxmpp.NS_SEARCH)
        if not tag:
            return True
        self.data = tag.getTag('x', namespace=nbxmpp.NS_DATA)
        if self.data:
            self.is_dataform = True
            return True
        self.data = {}
        for i in self.stanza.getQueryPayload():
            self.data[i.getName()] = i.getData()
        return True


class SearchResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'search-result-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.data = None
        self.is_dataform = False
        tag = self.stanza.getTag('query', namespace=nbxmpp.NS_SEARCH)
        if not tag:
            return True
        self.data = tag.getTag('x', namespace=nbxmpp.NS_DATA)
        if self.data:
            self.is_dataform = True
            return True
        self.data = []
        for item in tag.getTags('item'):
            # We also show attributes. jid is there
            f = item.attrs
            for i in item.getPayload():
                f[i.getName()] = i.getData()
            self.data.append(f)
        return True

class IqErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'iq-error-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource(check_fake_jid=True)
        self.errmsg = self.stanza.getErrorMsg()
        self.errcode = self.stanza.getErrorCode()
        return True

class PingReceivedEvent(nec.NetworkIncomingEvent):
    name = 'ping-received'
    base_network_events = []

class StreamReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stream-received'
    base_network_events = []

class StreamConflictReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stream-conflict-received'
    base_network_events = ['stream-received']

    def generate(self):
        if self.base_event.stanza.getTag('conflict'):
            self.conn = self.base_event.conn
            return True

class StreamOtherHostReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stream-other-host-received'
    base_network_events = ['stream-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        other_host = self.stanza.getTag('see-other-host')
        if other_host and self.conn._current_type in ('ssl', 'tls'):
            host = other_host.getData()
            if ':' in host:
                host_l = host.split(':', 1)
                h = host_l[0]
                p = host_l[1]
            else:
                h = host
                p = 5222
            if h.startswith('[') and h.endswith(']'):
                h = h[1:-1]
            self.redirected = {'host': h, 'port': p}
            return True

class PresenceHelperEvent:
    def _generate_show(self):
        self.show = self.stanza.getShow()
        if self.show not in ('chat', 'away', 'xa', 'dnd'):
            self.show = '' # We ignore unknown show
        if not self.ptype and not self.show:
            self.show = 'online'
        elif self.ptype == 'unavailable':
            self.show = 'offline'

    def _generate_ptype(self):
        self.ptype = self.stanza.getType()
        if self.ptype == 'available':
            self.ptype = None
        rfc_types = ('unavailable', 'error', 'subscribe', 'subscribed',
            'unsubscribe', 'unsubscribed')
        if self.ptype and not self.ptype in rfc_types:
            self.ptype = None

class PresenceReceivedEvent(nec.NetworkIncomingEvent, HelperEvent,
PresenceHelperEvent):
    name = 'presence-received'
    base_network_events = ['raw-pres-received']

    def _generate_keyID(self, sig_tag):
        self.keyID = ''
        if sig_tag and self.conn.USE_GPG and self.ptype != 'error':
            # error presences contain our own signature
            # verify
            sig_msg = sig_tag.getData()
            self.keyID = self.conn.gpg.verify(self.status, sig_msg)
            self.keyID = helpers.prepare_and_validate_gpg_keyID(self.conn.name,
                                                                self.jid,
                                                                self.keyID)

    def _generate_prio(self):
        self.prio = self.stanza.getPriority()
        try:
            self.prio = int(self.prio)
        except Exception:
            self.prio = 0

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza

        self.need_add_in_roster = False
        self.need_redraw = False

        self.popup = False # Do we want to open chat window ?

        if not self.conn or self.conn.connected < 2:
            log.debug('account is no more connected')
            return

        self._generate_ptype()
        try:
            self.get_jid_resource()
        except Exception:
            log.warning('Invalid JID: %s, ignoring it' % self.stanza.getFrom())
            return
        jid_list = app.contacts.get_jid_list(self.conn.name)
        self.timestamp = None
        self.get_id()
        self.is_gc = False # is it a GC presence ?
        sig_tag = None
        self.avatar_sha = None
        # XEP-0172 User Nickname
        self.user_nick = self.stanza.getTagData('nick') or ''
        self.contact_nickname = None
        self.transport_auto_auth = False
        # XEP-0203
        delay_tag = self.stanza.getTag('delay', namespace=nbxmpp.NS_DELAY2)
        if delay_tag:
            self._generate_timestamp(self.stanza.getTimestamp2())
        # XEP-0319
        self.idle_time = None
        idle_tag = self.stanza.getTag('idle', namespace=nbxmpp.NS_IDLE)
        if idle_tag:
            time_str = idle_tag.getAttr('since')
            tim = helpers.datetime_tuple(time_str)
            self.idle_time = timegm(tim)
        xtags = self.stanza.getTags('x')
        for x in xtags:
            namespace = x.getNamespace()
            if namespace.startswith(nbxmpp.NS_MUC):
                self.is_gc = True
            elif namespace == nbxmpp.NS_SIGNED:
                sig_tag = x
            elif namespace == nbxmpp.NS_VCARD_UPDATE:
                self.avatar_sha = x.getTagData('photo')
                self.contact_nickname = x.getTagData('nickname')
            elif namespace == nbxmpp.NS_DELAY and not self.timestamp:
                # XEP-0091
                self._generate_timestamp(self.stanza.getTimestamp())
            elif namespace == 'http://delx.cjb.net/protocol/roster-subsync':
                # see http://trac.gajim.org/ticket/326
                agent = app.get_server_from_jid(self.jid)
                if self.conn.connection.getRoster().getItem(agent):
                    # to be sure it's a transport contact
                    self.transport_auto_auth = True

        if not self.is_gc and self.id_ and self.id_.startswith('gajim_muc_') \
        and self.ptype == 'error':
            # Error presences may not include sent stanza, so we don't detect
            # it's a muc presence. So detect it by ID
            h = hmac.new(self.conn.secret_hmac, self.jid.encode('utf-8'),
                         hashlib.md5).hexdigest()[:6]
            if self.id_.split('_')[-1] == h:
                self.is_gc = True
        self.status = self.stanza.getStatus() or ''
        self._generate_show()
        self._generate_prio()
        self._generate_keyID(sig_tag)

        self.errcode = self.stanza.getErrorCode()
        self.errmsg = self.stanza.getErrorMsg()

        if self.is_gc:
            app.nec.push_incoming_event(
                GcPresenceReceivedEvent(
                    None, conn=self.conn, stanza=self.stanza,
                    presence_obj=self))
            return

        if self.ptype == 'subscribe':
            app.nec.push_incoming_event(SubscribePresenceReceivedEvent(None,
                conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'subscribed':
            # BE CAREFUL: no con.updateRosterItem() in a callback
            app.nec.push_incoming_event(SubscribedPresenceReceivedEvent(None,
                conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'unsubscribe':
            log.debug(_('unsubscribe request from %s') % self.jid)
        elif self.ptype == 'unsubscribed':
            app.nec.push_incoming_event(UnsubscribedPresenceReceivedEvent(
                None, conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'error':
            return

        if not self.ptype or self.ptype == 'unavailable':
            our_jid = app.get_jid_from_account(self.conn.name)
            if self.jid == our_jid and self.resource == self.conn.server_resource:
                # We got our own presence
                app.nec.push_incoming_event(OurShowEvent(None, conn=self.conn,
                                                           show=self.show))
            elif self.jid in jid_list or self.jid == our_jid:
                return True

class ZeroconfPresenceReceivedEvent(nec.NetworkIncomingEvent):
    name = 'presence-received'
    base_network_events = []

    def generate(self):
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.resource = 'local'
        self.prio = 0
        self.keyID = None
        self.timestamp = 0
        self.contact_nickname = None
        self.avatar_sha = None
        self.need_add_in_roster = False
        self.need_redraw = False
        if self.show == 'offline':
            self.ptype = 'unavailable'
        else:
            self.ptype = None
        self.is_gc = False
        self.user_nick = ''
        self.transport_auto_auth = False
        self.errcode = None
        self.errmsg = ''
        self.popup = False # Do we want to open chat window ?
        return True

class GcPresenceReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'gc-presence-received'
    base_network_events = []

    def generate(self):
        self.ptype = self.presence_obj.ptype
        self.fjid = self.presence_obj.fjid
        self.jid = self.presence_obj.jid
        self.room_jid = self.presence_obj.jid
        self.nick = self.presence_obj.resource
        self.show = self.presence_obj.show
        self.status = self.presence_obj.status
        self.avatar_sha = self.presence_obj.avatar_sha
        self.errcode = self.presence_obj.errcode
        self.errmsg = self.presence_obj.errmsg
        self.errcon = self.stanza.getError()
        self.get_gc_control()
        self.gc_contact = app.contacts.get_gc_contact(self.conn.name,
            self.room_jid, self.nick)

        if self.ptype == 'error':
            return True

        if self.ptype and self.ptype != 'unavailable':
            return
        if app.config.get('log_contact_status_changes') and \
        app.config.should_log(self.conn.name, self.room_jid):
            if self.gc_contact:
                jid = self.gc_contact.jid
            else:
                jid = self.stanza.getJid()
            st = self.status
            if jid:
                # we know real jid, save it in db
                st += ' (%s)' % jid
            show = app.logger.convert_show_values_to_db_api_values(self.show)
            if show is not None:
                fjid = nbxmpp.JID(self.fjid)
                app.logger.insert_into_logs(self.conn.name,
                                            fjid.getStripped(),
                                            time_time(),
                                            KindConstant.GCSTATUS,
                                            contact_name=fjid.getResource(),
                                            message=st,
                                            show=show)


        # NOTE: if it's a gc presence, don't ask vcard here.
        # We may ask it to real jid in gui part.
        self.status_code = []
        ns_muc_user_x = self.stanza.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if ns_muc_user_x:
            destroy = ns_muc_user_x.getTag('destroy')
        else:
            destroy = None
        if ns_muc_user_x and destroy:
            # Room has been destroyed. see
            # http://www.xmpp.org/extensions/xep-0045.html#destroyroom
            self.reason = _('Room has been destroyed')
            r = destroy.getTagData('reason')
            if r:
                self.reason += ' (%s)' % r
            if destroy.getAttr('jid'):
                try:
                    jid = helpers.parse_jid(destroy.getAttr('jid'))
                    self.reason += '\n' + \
                        _('You can join this room instead: %s') % jid
                except helpers.InvalidFormat:
                    pass
            self.status_code = ['destroyed']
        else:
            self.reason = self.stanza.getReason()
            conditions = self.stanza.getStatusConditions()
            if conditions:
                self.status_code = []
                for condition in conditions:
                    if condition in CONDITION_TO_CODE:
                        self.status_code.append(CONDITION_TO_CODE[condition])
            else:
                self.status_code = self.stanza.getStatusCode()

        self.role = self.stanza.getRole()
        self.affiliation = self.stanza.getAffiliation()
        self.real_jid = self.stanza.getJid()
        self.actor = self.stanza.getActor()
        self.new_nick = self.stanza.getNewNick()
        return True

class SubscribePresenceReceivedEvent(nec.NetworkIncomingEvent):
    name = 'subscribe-presence-received'
    base_network_events = []

    def generate(self):
        self.jid = self.presence_obj.jid
        self.fjid = self.presence_obj.fjid
        self.status = self.presence_obj.status
        self.transport_auto_auth = self.presence_obj.transport_auto_auth
        self.user_nick = self.presence_obj.user_nick
        return True

class SubscribedPresenceReceivedEvent(nec.NetworkIncomingEvent):
    name = 'subscribed-presence-received'
    base_network_events = []

    def generate(self):
        self.jid = self.presence_obj.jid
        self.resource = self.presence_obj.resource
        return True

class UnsubscribedPresenceReceivedEvent(nec.NetworkIncomingEvent):
    name = 'unsubscribed-presence-received'
    base_network_events = []

    def generate(self):
        self.jid = self.presence_obj.jid
        return True

class OurShowEvent(nec.NetworkIncomingEvent):
    name = 'our-show'
    base_network_events = []

class BeforeChangeShowEvent(nec.NetworkIncomingEvent):
    name = 'before-change-show'
    base_network_events = []

class MamMessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'mam-message-received'
    base_network_events = ['raw-mam-message-received']

    def __init__(self, name, base_event):
        '''
        Pre-Generated attributes on self:

        :conn:          Connection instance
        :stanza:        Complete stanza Node
        :forwarded:     Forwarded Node
        :result:        Result Node
        '''
        self._set_base_event_vars_as_attributes(base_event)
        self.additional_data = {}
        self.encrypted = False
        self.groupchat = False
        self.nick = None

    def generate(self):
        archive_jid = self.stanza.getFrom()
        own_jid = self.conn.get_own_jid().getStripped()
        if archive_jid and not archive_jid.bareMatch(own_jid):
            # MAM Message not from our Archive
            return False

        self.msg_ = self.forwarded.getTag('message', protocol=True)

        if self.msg_.getType() == 'groupchat':
            return False

        # use stanza-id as unique-id
        self.unique_id, origin_id = self.get_unique_id()

        # Check for duplicates
        if app.logger.find_stanza_id(own_jid, self.unique_id, origin_id):
            return

        self.msgtxt = self.msg_.getTagData('body')

        frm = self.msg_.getFrom()
        # Some servers dont set the 'to' attribute when
        # we send a message to ourself
        to = self.msg_.getTo()
        if to is None:
            to = own_jid

        if frm.bareMatch(own_jid):
            self.with_ = to
            self.kind = KindConstant.CHAT_MSG_SENT
        else:
            self.with_ = frm
            self.kind = KindConstant.CHAT_MSG_RECV

        delay = self.forwarded.getTagAttr(
            'delay', 'stamp', namespace=nbxmpp.NS_DELAY2)
        if delay is None:
            log.error('Received MAM message without timestamp')
            return

        self.timestamp = helpers.parse_datetime(
            delay, check_utc=True, epoch=True)
        if self.timestamp is None:
            log.error('Received MAM message with invalid timestamp: %s', delay)
            return

        # Save timestamp added by the user
        user_delay = self.msg_.getTagAttr(
            'delay', 'stamp', namespace=nbxmpp.NS_DELAY2)
        if user_delay is not None:
            self.user_timestamp = helpers.parse_datetime(
                user_delay, check_utc=True, epoch=True)
            if self.user_timestamp is None:
                log.warning('Received MAM message with '
                            'invalid user timestamp: %s', user_delay)

        log.debug('Received mam-message: unique id: %s', self.unique_id)
        return True

    def get_unique_id(self):
        stanza_id = self.get_stanza_id(self.result, query=True)
        if self.conn.get_own_jid().bareMatch(self.msg_.getFrom()):
            # message we sent
            origin_id = self.msg_.getOriginID()
            return stanza_id, origin_id

        # A message we received
        return stanza_id, None

class MamGcMessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'mam-gc-message-received'
    base_network_events = ['raw-mam-message-received']

    def __init__(self, name, base_event):
        '''
        Pre-Generated attributes on self:

        :conn:          Connection instance
        :stanza:        Complete stanza Node
        :forwarded:     Forwarded Node
        :result:        Result Node
        '''
        self._set_base_event_vars_as_attributes(base_event)
        self.additional_data = {}
        self.encrypted = False
        self.groupchat = True
        self.kind = KindConstant.GC_MSG

    def generate(self):
        self.msg_ = self.forwarded.getTag('message', protocol=True)

        if self.msg_.getType() != 'groupchat':
            return False

        self.room_jid = self.stanza.getFrom().getStripped()

        self.unique_id = self.get_stanza_id(self.result, query=True)

        # Check for duplicates
        if app.logger.find_stanza_id(self.room_jid, self.unique_id,
                                     groupchat=True):
            return

        self.msgtxt = self.msg_.getTagData('body')
        self.with_ = self.msg_.getFrom().getStripped()
        self.nick = self.msg_.getFrom().getResource()

        # Get the real jid if we have it
        self.real_jid = None
        muc_user = self.msg_.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is not None:
            self.real_jid = muc_user.getTagAttr('item', 'jid')

        delay = self.forwarded.getTagAttr(
            'delay', 'stamp', namespace=nbxmpp.NS_DELAY2)
        if delay is None:
            log.error('Received MAM message without timestamp')
            return

        self.timestamp = helpers.parse_datetime(
            delay, check_utc=True, epoch=True)
        if self.timestamp is None:
            log.error('Received MAM message with invalid timestamp: %s', delay)
            return

        # Save timestamp added by the user
        user_delay = self.msg_.getTagAttr(
            'delay', 'stamp', namespace=nbxmpp.NS_DELAY2)
        if user_delay is not None:
            self.user_timestamp = helpers.parse_datetime(
                user_delay, check_utc=True, epoch=True)
            if self.user_timestamp is None:
                log.warning('Received MAM message with '
                            'invalid user timestamp: %s', user_delay)

        log.debug('Received mam-gc-message: unique id: %s', self.unique_id)
        return True

class MamDecryptedMessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'mam-decrypted-message-received'
    base_network_events = []

    def generate(self):
        if not self.msgtxt:
            # For example Chatstates, Receipts, Chatmarkers
            log.debug('Received MAM message without text')
            return

        self.get_oob_data(self.msg_)

        if self.groupchat:
            return True

        self.is_pm = app.logger.jid_is_room_jid(self.with_.getStripped())
        if self.is_pm is None:
            # Check if this event is triggered after a disco, so we dont
            # run into an endless loop
            if hasattr(self, 'disco'):
                log.error('JID not known even after sucessful disco')
                return
            # we don't know this JID, we need to disco it.
            server = self.with_.getDomain()
            if server not in self.conn.mam_awaiting_disco_result:
                self.conn.mam_awaiting_disco_result[server] = [self]
                self.conn.discoverInfo(server)
            else:
                self.conn.mam_awaiting_disco_result[server].append(self)
            return

        if self.is_pm:
            self.with_ = str(self.with_)
        else:
            self.with_ = self.with_.getStripped()
        return True

class MessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'message-received'
    base_network_events = ['raw-message-received']

    def init(self):
        self.additional_data = {}

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        self.get_id()
        self.forwarded = False
        self.sent = False
        self.encrypted = False
        account = self.conn.name

        if self.stanza.getFrom() == self.conn.get_own_jid(warn=True):
            # Drop messages sent from our own full jid
            # It can happen that when we sent message to our own bare jid
            # that the server routes that message back to us
            log.info('Received message from self: %s, message is dropped',
                     self.stanza.getFrom())
            return

        # check if the message is a roster item exchange (XEP-0144)
        if self.stanza.getTag('x', namespace=nbxmpp.NS_ROSTERX):
            app.nec.push_incoming_event(RosterItemExchangeEvent(None,
                conn=self.conn, stanza=self.stanza))
            return

        # check if the message is a XEP-0070 confirmation request
        if self.stanza.getTag('confirm', namespace=nbxmpp.NS_HTTP_AUTH):
            app.nec.push_incoming_event(HttpAuthReceivedEvent(None,
                conn=self.conn, stanza=self.stanza))
            return

        try:
            self.get_jid_resource()
        except helpers.InvalidFormat:
            log.warning('Invalid JID: %s, ignoring it',
                        self.stanza.getFrom())
            return

        # Check for duplicates
        self.unique_id = self.get_unique_id()
        # Check groupchat messages for duplicates,
        # We do this because of MUC History messages
        if self.stanza.getType() == 'groupchat':
            if app.logger.find_stanza_id(self.stanza.getFrom().getStripped(),
                                         self.unique_id,
                                         groupchat=True):
                return

        address_tag = self.stanza.getTag('addresses',
            namespace=nbxmpp.NS_ADDRESS)
        # Be sure it comes from one of our resource, else ignore address element
        if address_tag and self.jid == app.get_jid_from_account(account):
            address = address_tag.getTag('address', attrs={'type': 'ofrom'})
            if address:
                try:
                    self.fjid = helpers.parse_jid(address.getAttr('jid'))
                except helpers.InvalidFormat:
                    log.warning('Invalid JID: %s, ignoring it',
                                address.getAttr('jid'))
                    return
                self.jid = app.get_jid_without_resource(self.fjid)

        carbon_marker = self.stanza.getTag('sent', namespace=nbxmpp.NS_CARBONS)
        if not carbon_marker:
            carbon_marker = self.stanza.getTag('received',
                namespace=nbxmpp.NS_CARBONS)
        # Be sure it comes from one of our resource, else ignore forward element
        if carbon_marker and self.jid == app.get_jid_from_account(account):
            forward_tag = carbon_marker.getTag('forwarded',
                namespace=nbxmpp.NS_FORWARD)
            if forward_tag:
                msg = forward_tag.getTag('message')
                self.stanza = nbxmpp.Message(node=msg)
                self.get_id()
                if carbon_marker.getName() == 'sent':
                    to = self.stanza.getTo()
                    frm = self.stanza.getFrom()
                    if not frm:
                        frm = app.get_jid_from_account(account)
                    self.stanza.setTo(frm)
                    if not to:
                        to = app.get_jid_from_account(account)
                    self.stanza.setFrom(to)
                    self.sent = True
                elif carbon_marker.getName() == 'received':
                    full_frm = str(self.stanza.getFrom())
                    frm = app.get_jid_without_resource(full_frm)
                    if frm == app.get_jid_from_account(account):
                        # Drop 'received' Carbons from ourself, we already
                        # got the message with the 'sent' Carbon or via the
                        # message itself
                        log.info(
                            'Drop "received"-Carbon from ourself: %s'
                            % full_frm)
                        return
                try:
                    self.get_jid_resource()
                except helpers.InvalidFormat:
                    log.warning('Invalid JID: %s, ignoring it',
                                self.stanza.getFrom())
                    return
                self.forwarded = True

        result = self.stanza.getTag('result', protocol=True)
        if result and result.getNamespace() in (nbxmpp.NS_MAM_1,
                                                nbxmpp.NS_MAM_2):

            if result.getAttr('queryid') not in self.conn.mam_query_ids:
                log.warning('Invalid MAM Message: unknown query id')
                log.debug(self.stanza)
                return

            forwarded = result.getTag('forwarded',
                                      namespace=nbxmpp.NS_FORWARD,
                                      protocol=True)
            if not forwarded:
                log.warning('Invalid MAM Message: no forwarded child')
                return

            app.nec.push_incoming_event(
                NetworkEvent('raw-mam-message-received',
                             conn=self.conn,
                             stanza=self.stanza,
                             forwarded=forwarded,
                             result=result))
            return

        # Mediated invitation?
        muc_user = self.stanza.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user:
            if muc_user.getTag('decline'):
                app.nec.push_incoming_event(
                    GcDeclineReceivedEvent(
                        None, conn=self.conn,
                        room_jid=self.fjid, stanza=muc_user))
                return
            if muc_user.getTag('invite'):
                app.nec.push_incoming_event(
                    GcInvitationReceivedEvent(
                        None, conn=self.conn, jid_from=self.fjid,
                        mediated=True, stanza=muc_user))
                return
        else:
            # Direct invitation?
            direct = self.stanza.getTag(
                'x', namespace=nbxmpp.NS_CONFERENCE)
            if direct:
                app.nec.push_incoming_event(
                    GcInvitationReceivedEvent(
                        None, conn=self.conn, jid_from=self.fjid,
                        mediated=False, stanza=direct))
                return

        self.thread_id = self.stanza.getThread()
        self.mtype = self.stanza.getType()
        if not self.mtype or self.mtype not in ('chat', 'groupchat', 'error'):
            self.mtype = 'normal'

        self.msgtxt = self.stanza.getBody()

        self.get_gc_control()

        if self.gc_control and self.jid == self.fjid:
            if self.mtype == 'error':
                self.msgtxt = _('error while sending %(message)s ( %(error)s )'\
                    ) % {'message': self.msgtxt,
                    'error': self.stanza.getErrorMsg()}
                if self.stanza.getTag('html'):
                    self.stanza.delChild('html')
            # message from a gc without a resource
            self.mtype = 'groupchat'

        self.session = None
        if self.mtype != 'groupchat':
            if app.interface.is_pm_contact(self.fjid, account) and \
            self.mtype == 'error':
                self.session = self.conn.find_session(self.fjid, self.thread_id)
                if not self.session:
                    self.session = self.conn.get_latest_session(self.fjid)
                if not self.session:
                    self.session = self.conn.make_new_session(self.fjid,
                                                              self.thread_id,
                                                              type_='pm')
            else:
                self.session = self.conn.get_or_create_session(self.fjid,
                                                               self.thread_id)

            if self.thread_id and not self.session.received_thread_id:
                self.session.received_thread_id = True

            self.session.last_receive = time_time()

        self._generate_timestamp(self.stanza.getTimestamp())

        return True

    def get_unique_id(self):
        if self.stanza.getType() == 'groupchat':
            # TODO: Disco the MUC check if 'urn:xmpp:mam:2' is announced
            return self.get_stanza_id(self.stanza)

        elif self.stanza.getType() != 'chat':
            return

        # Messages we receive live
        if self.conn.archiving_namespace != nbxmpp.NS_MAM_2:
            # Only mam:2 ensures valid stanza-id
            return

        # Sent Carbon
        sent_carbon = self.stanza.getTag('sent',
                                         namespace=nbxmpp.NS_CARBONS,
                                         protocol=True)
        if sent_carbon is not None:
            message = self.get_forwarded_message(sent_carbon)
            return self.get_stanza_id(message)

        # Received Carbon
        received_carbon = self.stanza.getTag('received',
                                             namespace=nbxmpp.NS_CARBONS,
                                             protocol=True)
        if received_carbon is not None:
            message = self.get_forwarded_message(received_carbon)
            return self.get_stanza_id(message)

        # Normal Message
        return self.get_stanza_id(self.stanza)

class ZeroconfMessageReceivedEvent(MessageReceivedEvent):
    name = 'message-received'
    base_network_events = []

    def get_jid_resource(self):
        self.fjid =self.stanza.getFrom()

        if self.fjid is None:
            for key in self.conn.connection.zeroconf.contacts:
                if self.ip == self.conn.connection.zeroconf.contacts[key][
                        Constant.ADDRESS]:
                    self.fjid = key
                    break

        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)

    def generate(self):
        self.base_event = nec.NetworkIncomingEvent(None, conn=self.conn,
                                                   stanza=self.stanza)
        return super(ZeroconfMessageReceivedEvent, self).generate()

class GcInvitationReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-invitation-received'
    base_network_events = []

    def generate(self):
        account = self.conn.name
        if not self.mediated:
            # direct invitation
            try:
                self.room_jid = helpers.parse_jid(self.stanza.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            self.stanza.getAttr('jid'))
                return
            self.reason = self.stanza.getAttr('reason')
            self.password = self.stanza.getAttr('password')
            self.is_continued = False
            self.is_continued = self.stanza.getAttr('continue') == 'true'
        else:
            self.invite = self.stanza.getTag('invite')
            self.room_jid = self.jid_from
            try:
                self.jid_from = helpers.parse_jid(self.invite.getAttr('from'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            self.invite.getAttr('from'))
                return

            self.reason = self.invite.getTagData('reason')
            self.password = self.stanza.getTagData('password')
            self.is_continued = self.stanza.getTag('continue') is not None

        if self.room_jid in app.gc_connected[account] and \
                app.gc_connected[account][self.room_jid]:
            # We are already in groupchat. Ignore invitation
            return
        jid = app.get_jid_without_resource(self.jid_from)

        ignore = app.config.get_per(
            'accounts', account, 'ignore_unknown_contacts')
        if ignore and not app.contacts.get_contacts(account, jid):
            return

        return True

class GcDeclineReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-decline-received'
    base_network_events = []

    def generate(self):
        account = self.conn.name
        decline = self.stanza.getTag('decline')
        try:
            self.jid_from = helpers.parse_jid(decline.getAttr('from'))
        except helpers.InvalidFormat:
            log.warning('Invalid JID: %s, ignoring it',
                        decline.getAttr('from'))
            return
        jid = app.get_jid_without_resource(self.jid_from)
        ignore = app.config.get_per(
            'accounts', account, 'ignore_unknown_contacts')
        if ignore and not app.contacts.get_contacts(account, jid):
            return
        self.reason = decline.getTagData('reason')

        return True

class DecryptedMessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'decrypted-message-received'
    base_network_events = []

    def generate(self):
        self.stanza = self.msg_obj.stanza
        self.additional_data = self.msg_obj.additional_data
        self.id_ = self.msg_obj.id_
        self.unique_id = self.msg_obj.unique_id
        self.jid = self.msg_obj.jid
        self.fjid = self.msg_obj.fjid
        self.resource = self.msg_obj.resource
        self.mtype = self.msg_obj.mtype
        self.thread_id = self.msg_obj.thread_id
        self.msgtxt = self.msg_obj.msgtxt
        self.gc_control = self.msg_obj.gc_control
        self.session = self.msg_obj.session
        self.timestamp = self.msg_obj.timestamp
        self.encrypted = self.msg_obj.encrypted
        self.forwarded = self.msg_obj.forwarded
        self.sent = self.msg_obj.sent
        self.conn = self.msg_obj.conn
        self.popup = False
        self.msg_log_id = None # id in log database
        self.attention = False # XEP-0224
        self.correct_id = None # XEP-0308
        self.msghash = None

        self.receipt_request_tag = self.stanza.getTag('request',
            namespace=nbxmpp.NS_RECEIPTS)
        self.receipt_received_tag = self.stanza.getTag('received',
            namespace=nbxmpp.NS_RECEIPTS)

        self.subject = self.stanza.getSubject()

        self.displaymarking = None
        self.seclabel = self.stanza.getTag('securitylabel',
            namespace=nbxmpp.NS_SECLABEL)
        if self.seclabel:
            self.displaymarking = self.seclabel.getTag('displaymarking')

        if self.stanza.getTag('attention', namespace=nbxmpp.NS_ATTENTION):
            delayed = self.stanza.getTag('x', namespace=nbxmpp.NS_DELAY) is not\
                None
            if not delayed:
                self.attention = True

        self.form_node = self.stanza.getTag('x', namespace=nbxmpp.NS_DATA)

        if app.config.get('ignore_incoming_xhtml'):
            self.xhtml = None
        else:
            self.xhtml = self.stanza.getXHTML()

        # XEP-0172 User Nickname
        self.user_nick = self.stanza.getTagData('nick') or ''

        self.get_chatstate()

        self.get_oob_data(self.stanza)

        replace = self.stanza.getTag('replace', namespace=nbxmpp.NS_CORRECT)
        if replace:
            self.correct_id = replace.getAttr('id')

        return True

class ChatstateReceivedEvent(nec.NetworkIncomingEvent):
    name = 'chatstate-received'
    base_network_events = []

    def generate(self):
        self.stanza = self.msg_obj.stanza
        self.jid = self.msg_obj.jid
        self.fjid = self.msg_obj.fjid
        self.resource = self.msg_obj.resource
        self.chatstate = self.msg_obj.chatstate
        return True

class GcMessageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-message-received'
    base_network_events = []

    def generate(self):
        self.stanza = self.msg_obj.stanza
        if not hasattr(self.msg_obj, 'additional_data'):
            self.additional_data = {}
        else:
            self.additional_data = self.msg_obj.additional_data
        self.id_ = self.msg_obj.stanza.getID()
        self.unique_id = self.msg_obj.unique_id
        self.fjid = self.msg_obj.fjid
        self.msgtxt = self.msg_obj.msgtxt
        self.jid = self.msg_obj.jid
        self.room_jid = self.msg_obj.jid
        self.nickname = self.msg_obj.resource
        self.timestamp = self.msg_obj.timestamp
        self.xhtml_msgtxt = self.stanza.getXHTML()
        self.encrypted = self.msg_obj.encrypted
        self.correct_id = None # XEP-0308

        if app.config.get('ignore_incoming_xhtml'):
            self.xhtml_msgtxt = None

        if self.msg_obj.resource:
            # message from someone
            self.nick = self.msg_obj.resource
        else:
            # message from server
            self.nick = ''

        self.has_timestamp = bool(self.stanza.timestamp)

        self.subject = self.stanza.getSubject()

        if self.subject is not None:
            app.nec.push_incoming_event(GcSubjectReceivedEvent(None,
                conn=self.conn, msg_event=self))
            return

        conditions = self.stanza.getStatusConditions()
        if conditions:
            self.status_code = []
            for condition in conditions:
                if condition in CONDITION_TO_CODE:
                    self.status_code.append(CONDITION_TO_CODE[condition])
        else:
            self.status_code = self.stanza.getStatusCode()

        if not self.stanza.getTag('body'): # no <body>
            # It could be a config change. See
            # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
            if self.stanza.getTag('x'):
                if self.status_code != []:
                    app.nec.push_incoming_event(GcConfigChangedReceivedEvent(
                        None, conn=self.conn, msg_event=self))
            if self.msg_obj.form_node:
                return True
            return

        self.displaymarking = None
        seclabel = self.stanza.getTag('securitylabel')
        if seclabel and seclabel.getNamespace() == nbxmpp.NS_SECLABEL:
            # Ignore message from room in which we are not
            self.displaymarking = seclabel.getTag('displaymarking')

        self.captcha_form = None
        captcha_tag = self.stanza.getTag('captcha', namespace=nbxmpp.NS_CAPTCHA)
        if captcha_tag:
            self.captcha_form = captcha_tag.getTag('x',
                namespace=nbxmpp.NS_DATA)
            for field in self.captcha_form.getTags('field'):
                for media in field.getTags('media'):
                    for uri in media.getTags('uri'):
                        uri_data = uri.getData()
                        if uri_data.startswith('cid:'):
                            uri_data = uri_data[4:]
                            found = False
                            for data in self.stanza.getTags('data',
                            namespace=nbxmpp.NS_BOB):
                                if data.getAttr('cid') == uri_data:
                                    uri.setData(data.getData())
                                    found = True
                            if not found:
                                self.conn.get_bob_data(uri_data, self.fjid,
                                    self.conn._dispatch_gc_msg_with_captcha,
                                    [self.stanza, self.msg_obj], 0)
                                return

        replace = self.stanza.getTag('replace', namespace=nbxmpp.NS_CORRECT)
        if replace:
            self.correct_id = replace.getAttr('id')

        return True

class GcSubjectReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-subject-received'
    base_network_events = []

    def generate(self):
        self.conn = self.msg_event.conn
        self.stanza = self.msg_event.stanza
        self.room_jid = self.msg_event.room_jid
        self.nickname = self.msg_event.nickname
        self.fjid = self.msg_event.fjid
        self.subject = self.msg_event.subject
        self.msgtxt = self.msg_event.msgtxt
        self.has_timestamp = self.msg_event.has_timestamp
        return True

class GcConfigChangedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-config-changed-received'
    base_network_events = []

    def generate(self):
        self.conn = self.msg_event.conn
        self.stanza = self.msg_event.stanza
        self.room_jid = self.msg_event.room_jid
        self.status_code = self.msg_event.status_code
        return True

class MessageSentEvent(nec.NetworkIncomingEvent):
    name = 'message-sent'
    base_network_events = []

    def generate(self):
        if not self.automatic_message:
            self.conn.sent_message_ids.append(self.stanza_id)
            # only record the last 20000 message ids (should be about 1MB [36 byte per uuid]
            # and about 24 hours if you send out a message every 5 seconds)
            self.conn.sent_message_ids = self.conn.sent_message_ids[-20000:]
        return True

class MessageNotSentEvent(nec.NetworkIncomingEvent):
    name = 'message-not-sent'
    base_network_events = []

class MessageErrorEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'message-error'
    base_network_events = []

    def generate(self):
        self.get_id()
        #only alert for errors of explicitly sent messages (see https://trac.gajim.org/ticket/8222)
        if self.id_ in self.conn.sent_message_ids:
            self.conn.sent_message_ids.remove(self.id_)
            return True
        return False

class AnonymousAuthEvent(nec.NetworkIncomingEvent):
    name = 'anonymous-auth'
    base_network_events = []

class JingleRequestReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-request-received'
    base_network_events = []

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleConnectedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-connected-received'
    base_network_events = []

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleDisconnectedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-disconnected-received'
    base_network_events = []

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleTransferCancelledEvent(nec.NetworkIncomingEvent):
    name = 'jingleFT-cancelled-received'
    base_network_events = []

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleErrorReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-error-received'
    base_network_events = []

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class ArchivingReceivedEvent(nec.NetworkIncomingEvent):
    name = 'archiving-received'
    base_network_events = []

    def generate(self):
        self.type_ = self.stanza.getType()
        if self.type_ not in ('result', 'set', 'error'):
            return
        return True

class ArchivingErrorReceivedEvent(nec.NetworkIncomingEvent):
    name = 'archiving-error-received'
    base_network_events = ['archiving-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        self.type_ = self.base_event.type_

        if self.type_ == 'error':
            self.error_msg = self.stanza.getErrorMsg()
            return True

class ArchivingCountReceived(nec.NetworkIncomingEvent):
    name = 'archiving-count-received'
    base_network_events = []

    def generate(self):
        return True

class ArchivingIntervalFinished(nec.NetworkIncomingEvent):
    name = 'archiving-interval-finished'
    base_network_events = []

    def generate(self):
        return True

class ArchivingQueryID(nec.NetworkIncomingEvent):
    name = 'archiving-query-id'
    base_network_events = []

    def generate(self):
        return True

class Archiving313PreferencesChangedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'archiving-313-preferences-changed-received'
    base_network_events = ['archiving-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        self.type_ = self.base_event.type_
        self.items = []
        self.default = None
        self.id = self.stanza.getID()
        self.answer = None
        prefs = self.stanza.getTag('prefs')

        if self.type_ != 'result' or not prefs:
            return

        self.default = prefs.getAttr('default')

        for item in prefs.getTag('always').getTags('jid'):
            self.items.append((item.getData(), 'Always'))

        for item in prefs.getTag('never').getTags('jid'):
            self.items.append((item.getData(), 'Never'))

        return True

class AccountCreatedEvent(nec.NetworkIncomingEvent):
    name = 'account-created'
    base_network_events = []

class AccountNotCreatedEvent(nec.NetworkIncomingEvent):
    name = 'account-not-created'
    base_network_events = []

class NewAccountConnectedEvent(nec.NetworkIncomingEvent):
    name = 'new-account-connected'
    base_network_events = []

    def generate(self):
        try:
            self.errnum = self.conn.connection.Connection.ssl_errnum
        except AttributeError:
            self.errnum = 0 # we don't have an errnum
        self.ssl_msg = ''
        if self.errnum > 0:
            from gajim.common.connection import ssl_error
            self.ssl_msg = ssl_error.get(self.errnum,
                _('Unknown SSL error: %d') % self.errnum)
        self.ssl_cert = ''
        self.ssl_fingerprint_sha1 = ''
        self.ssl_fingerprint_sha256 = ''
        if self.conn.connection.Connection.ssl_certificate:
            cert = self.conn.connection.Connection.ssl_certificate
            self.ssl_cert = OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_PEM, cert).decode('utf-8')
            self.ssl_fingerprint_sha1 = cert.digest('sha1').decode('utf-8')
            self.ssl_fingerprint_sha256 = cert.digest('sha256').decode('utf-8')
        return True

class NewAccountNotConnectedEvent(nec.NetworkIncomingEvent):
    name = 'new-account-not-connected'
    base_network_events = []

class ConnectionTypeEvent(nec.NetworkIncomingEvent):
    name = 'connection-type'
    base_network_events = []

class VcardPublishedEvent(nec.NetworkIncomingEvent):
    name = 'vcard-published'
    base_network_events = []

class VcardNotPublishedEvent(nec.NetworkIncomingEvent):
    name = 'vcard-not-published'
    base_network_events = []

class StanzaReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stanza-received'
    base_network_events = []
    
    def init(self):
        self.additional_data = {}
        
    def generate(self):
        return True

class StanzaSentEvent(nec.NetworkIncomingEvent):
    name = 'stanza-sent'
    base_network_events = []
    
    def init(self):
        self.additional_data = {}

class AgentRemovedEvent(nec.NetworkIncomingEvent):
    name = 'agent-removed'
    base_network_events = []

    def generate(self):
        self.jid_list = []
        for jid in app.contacts.get_jid_list(self.conn.name):
            if jid.endswith('@' + self.agent):
                self.jid_list.append(jid)
        return True

class BadGPGPassphraseEvent(nec.NetworkIncomingEvent):
    name = 'bad-gpg-passphrase'
    base_network_events = []

    def generate(self):
        self.account = self.conn.name
        self.use_gpg_agent = app.config.get('use_gpg_agent')
        self.keyID = app.config.get_per('accounts', self.conn.name, 'keyid')
        return True

class ConnectionLostEvent(nec.NetworkIncomingEvent):
    name = 'connection-lost'
    base_network_events = []

    def generate(self):
        app.nec.push_incoming_event(OurShowEvent(None, conn=self.conn,
            show='offline'))
        return True

class PingSentEvent(nec.NetworkIncomingEvent):
    name = 'ping-sent'
    base_network_events = []

class PingReplyEvent(nec.NetworkIncomingEvent):
    name = 'ping-reply'
    base_network_events = []

class PingErrorEvent(nec.NetworkIncomingEvent):
    name = 'ping-error'
    base_network_events = []

class CapsPresenceReceivedEvent(nec.NetworkIncomingEvent, HelperEvent,
PresenceHelperEvent):
    name = 'caps-presence-received'
    base_network_events = ['raw-pres-received']

    def _extract_caps_from_presence(self):
        caps_tag = self.stanza.getTag('c', namespace=nbxmpp.NS_CAPS)
        if caps_tag:
            self.hash_method = caps_tag['hash']
            self.node = caps_tag['node']
            self.caps_hash = caps_tag['ver']
        else:
            self.hash_method = self.node = self.caps_hash = None

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        try:
            self.get_jid_resource()
        except Exception:
            return
        self._generate_ptype()
        self._generate_show()
        self._extract_caps_from_presence()
        return True

class CapsDiscoReceivedEvent(nec.NetworkIncomingEvent):
    name = 'caps-disco-received'
    base_network_events = []

class CapsReceivedEvent(nec.NetworkIncomingEvent):
    name = 'caps-received'
    base_network_events = ['caps-presence-received', 'caps-disco-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.fjid = self.base_event.fjid
        self.jid = self.base_event.jid
        self.resource = self.base_event.resource
        self.client_caps = self.base_event.client_caps
        return True

class GPGTrustKeyEvent(nec.NetworkIncomingEvent):
    name = 'gpg-trust-key'
    base_network_events = []

class GPGPasswordRequiredEvent(nec.NetworkIncomingEvent):
    name = 'gpg-password-required'
    base_network_events = []

    def generate(self):
        self.keyid = app.config.get_per('accounts', self.conn.name, 'keyid')
        return True

class PEPReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'pep-received'
    base_network_events = []

    def generate(self):
        if not self.stanza.getTag('event'):
            return
        if self.stanza.getTag('error'):
            log.debug('PEPReceivedEvent received error stanza. Ignoring')
            return

        try:
            self.get_jid_resource()
        except Exception:
            return

        self.event_tag = self.stanza.getTag('event')

        for pep_class in SUPPORTED_PERSONAL_USER_EVENTS:
            pep = pep_class.get_tag_as_PEP(self.fjid, self.conn.name,
                self.event_tag)
            if pep:
                self.pep_type = pep.type_
                return True

        items = self.event_tag.getTag('items')
        if items:
            # for each entry in feed (there shouldn't be more than one, but to
            # be sure...
            for item in items.getTags('item'):
                entry = item.getTag('entry', namespace=nbxmpp.NS_ATOM)
                if entry:
                    app.nec.push_incoming_event(AtomEntryReceived(None,
                        conn=self.conn, node=entry))
        raise nbxmpp.NodeProcessed

class AtomEntryReceived(nec.NetworkIncomingEvent):
    name = 'atom-entry-received'
    base_network_events = []

    def generate(self):
        self.atom_entry = atom.OldEntry(node=self.node)
        return True

class PlainConnectionEvent(nec.NetworkIncomingEvent):
    name = 'plain-connection'
    base_network_events = []

class InsecurePasswordEvent(nec.NetworkIncomingEvent):
    name = 'insecure-password'
    base_network_events = []

class InsecureSSLConnectionEvent(nec.NetworkIncomingEvent):
    name = 'insecure-ssl-connection'
    base_network_events = []

class SSLErrorEvent(nec.NetworkIncomingEvent):
    name = 'ssl-error'
    base_network_events = []

class FingerprintErrorEvent(nec.NetworkIncomingEvent):
    name = 'fingerprint-error'
    base_network_events = []

class UniqueRoomIdSupportedEvent(nec.NetworkIncomingEvent):
    name = 'unique-room-id-supported'
    base_network_events = []

class UniqueRoomIdNotSupportedEvent(nec.NetworkIncomingEvent):
    name = 'unique-room-id-not-supported'
    base_network_events = []

class PrivacyListsReceivedEvent(nec.NetworkIncomingEvent):
    name = 'privacy-lists-received'
    base_network_events = []

class PrivacyListReceivedEvent(nec.NetworkIncomingEvent):
    name = 'privacy-list-received'
    base_network_events = []

class PrivacyListRemovedEvent(nec.NetworkIncomingEvent):
    name = 'privacy-list-removed'
    base_network_events = []

class PrivacyListActiveDefaultEvent(nec.NetworkIncomingEvent):
    name = 'privacy-list-active-default'
    base_network_events = []

class NonAnonymousServerErrorEvent(nec.NetworkIncomingEvent):
    name = 'non-anonymous-server-error'
    base_network_events = []

class VcardReceivedEvent(nec.NetworkIncomingEvent):
    name = 'vcard-received'
    base_network_events = []

    def generate(self):
        return True

class UpdateGCAvatarEvent(nec.NetworkIncomingEvent):
    name = 'update-gc-avatar'
    base_network_events = []

    def generate(self):
        return True

class UpdateRosterAvatarEvent(nec.NetworkIncomingEvent):
    name = 'update-roster-avatar'
    base_network_events = []

    def generate(self):
        return True

class PEPConfigReceivedEvent(nec.NetworkIncomingEvent):
    name = 'pep-config-received'
    base_network_events = []

class MetacontactsReceivedEvent(nec.NetworkIncomingEvent):
    name = 'metacontacts-received'
    base_network_events = []

    def generate(self):
        # Metacontact tags
        # http://www.xmpp.org/extensions/xep-0209.html
        self.meta_list = {}
        query = self.stanza.getTag('query')
        storage = query.getTag('storage')
        metas = storage.getTags('meta')
        for meta in metas:
            try:
                jid = helpers.parse_jid(meta.getAttr('jid'))
            except helpers.InvalidFormat:
                continue
            tag = meta.getAttr('tag')
            data = {'jid': jid}
            order = meta.getAttr('order')
            try:
                order = int(order)
            except Exception:
                order = 0
            if order is not None:
                data['order'] = order
            if tag in self.meta_list:
                self.meta_list[tag].append(data)
            else:
                self.meta_list[tag] = [data]
        return True

class ZeroconfNameConflictEvent(nec.NetworkIncomingEvent):
    name = 'zeroconf-name-conflict'
    base_network_events = []

class PasswordRequiredEvent(nec.NetworkIncomingEvent):
    name = 'password-required'
    base_network_events = []

class Oauth2CredentialsRequiredEvent(nec.NetworkIncomingEvent):
    name = 'oauth2-credentials-required'
    base_network_events = []

class FailedDecryptEvent(nec.NetworkIncomingEvent):
    name = 'failed-decrypt'
    base_network_events = []

    def generate(self):
        self.conn = self.msg_obj.conn
        self.fjid = self.msg_obj.fjid
        self.timestamp = self.msg_obj.timestamp
        self.session = self.msg_obj.session
        return True

class SignedInEvent(nec.NetworkIncomingEvent):
    name = 'signed-in'
    base_network_events = []

class RegisterAgentInfoReceivedEvent(nec.NetworkIncomingEvent):
    name = 'register-agent-info-received'
    base_network_events = []

class AgentItemsReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'agent-items-received'
    base_network_events = []

    def generate(self):
        q = self.stanza.getTag('query')
        self.node = q.getAttr('node')
        if not self.node:
            self.node = ''
        qp = self.stanza.getQueryPayload()
        self.items = []
        if not qp:
            qp = []
        for i in qp:
            # CDATA payload is not processed, only nodes
            if not isinstance(i, nbxmpp.simplexml.Node):
                continue
            attr = {}
            for key in i.getAttrs():
                attr[key] = i.getAttrs()[key]
            if 'jid' not in attr:
                continue
            try:
                attr['jid'] = helpers.parse_jid(attr['jid'])
            except helpers.InvalidFormat:
                # jid is not conform
                continue
            self.items.append(attr)
        self.get_jid_resource()
        hostname = app.config.get_per('accounts', self.conn.name, 'hostname')
        self.get_id()
        if self.id_ in self.conn.disco_items_ids:
            self.conn.disco_items_ids.remove(self.id_)
        if self.fjid == hostname and self.id_[:6] == 'Gajim_':
            for item in self.items:
                self.conn.discoverInfo(item['jid'], id_prefix='Gajim_')
        else:
            return True

class AgentItemsErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'agent-items-error-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.get_id()
        if self.id_ in self.conn.disco_items_ids:
            self.conn.disco_items_ids.remove(self.id_)
        return True

class AgentInfoReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'agent-info-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        if self.id_ in self.conn.disco_info_ids:
            self.conn.disco_info_ids.remove(self.id_)
        if self.id_ is None:
            log.warning('Invalid IQ received without an ID. Ignoring it: %s' % \
                self.stanza)
            return
        # According to XEP-0030:
        # For identity: category, type is mandatory, name is optional.
        # For feature: var is mandatory
        self.identities, self.features, self.data = [], [], []
        q = self.stanza.getTag('query')
        self.node = q.getAttr('node')
        if not self.node:
            self.node = ''
        qc = self.stanza.getQueryChildren()
        if not qc:
            qc = []

        for i in qc:
            if i.getName() == 'identity':
                attr = {}
                for key in i.getAttrs().keys():
                    attr[key] = i.getAttr(key)
                self.identities.append(attr)
            elif i.getName() == 'feature':
                var = i.getAttr('var')
                if var:
                    self.features.append(var)
            elif i.getName() == 'x' and i.getNamespace() == nbxmpp.NS_DATA:
                self.data.append(nbxmpp.DataForm(node=i))

        if not self.identities:
            # ejabberd doesn't send identities when we browse online users
            # see http://www.jabber.ru/bugzilla/show_bug.cgi?id=225
            self.identities = [{'category': 'server', 'type': 'im',
                'name': self.node}]
        self.get_jid_resource()
        return True

class AgentInfoErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'agent-info-error-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.get_id()
        if self.id_ in self.conn.disco_info_ids:
            self.conn.disco_info_ids.remove(self.id_)
        return True

class FileRequestReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'file-request-received'
    base_network_events = []

    def init(self):
        self.jingle_content = None
        self.FT_content = None

    def generate(self):
        self.get_id()
        self.fjid = self.conn._ft_get_from(self.stanza)
        self.jid = app.get_jid_without_resource(self.fjid)
        if self.jingle_content:
            secu = self.jingle_content.getTag('security')
            self.FT_content.use_security = bool(secu)
            if secu:
                fingerprint = secu.getTag('fingerprint')
                if fingerprint:
                    self.FT_content.x509_fingerprint = fingerprint.getData()
            if not self.FT_content.transport:
                self.FT_content.transport = JingleTransportSocks5()
                self.FT_content.transport.set_our_jid(
                    self.FT_content.session.ourjid)
                self.FT_content.transport.set_connection(
                    self.FT_content.session.connection)
            sid = self.stanza.getTag('jingle').getAttr('sid')
            self.file_props = FilesProp.getNewFileProp(self.conn.name, sid)
            self.file_props.transport_sid = self.FT_content.transport.sid
            self.FT_content.file_props = self.file_props
            self.FT_content.transport.set_file_props(self.file_props)
            self.file_props.streamhosts.extend(
                    self.FT_content.transport.remote_candidates)
            for host in self.file_props.streamhosts:
                host['initiator'] = self.FT_content.session.initiator
                host['target'] = self.FT_content.session.responder
            self.file_props.session_type = 'jingle'
            self.file_props.stream_methods = nbxmpp.NS_BYTESTREAM
            desc = self.jingle_content.getTag('description')
            if self.jingle_content.getAttr('creator') == 'initiator':
                file_tag = desc.getTag('file')
                self.file_props.sender = self.fjid
                self.file_props.receiver = self.conn._ft_get_our_jid()
            else:
                file_tag = desc.getTag('file')
                h = file_tag.getTag('hash')
                h = h.getData() if h else None
                n = file_tag.getTag('name')
                n = n.getData() if n else None
                pjid = app.get_jid_without_resource(self.fjid)
                file_info = self.conn.get_file_info(pjid, hash_=h,
                                                name=n,account=self.conn.name)
                self.file_props.file_name = file_info['file-name']
                self.file_props.sender = self.conn._ft_get_our_jid()
                self.file_props.receiver = self.fjid
                self.file_props.type_ = 's'
            for child in file_tag.getChildren():
                name = child.getName()
                val = child.getData()
                if val is None:
                    continue
                if name == 'name':
                    self.file_props.name = val
                if name == 'size':
                    self.file_props.size = int(val)
                if name == 'hash':
                    self.file_props.algo = child.getAttr('algo')
                    self.file_props.hash_ = val
                if name == 'date':
                    self.file_props.date = val
        else:
            si = self.stanza.getTag('si')
            self.file_props = FilesProp.getNewFileProp(self.conn.name,
                si.getAttr('id'))
            self.file_props.transport_sid = self.file_props.sid
            profile = si.getAttr('profile')
            if profile != nbxmpp.NS_FILE:
                self.conn.send_file_rejection(self.file_props, code='400',
                    typ='profile')
                raise nbxmpp.NodeProcessed
            feature_tag = si.getTag('feature', namespace=nbxmpp.NS_FEATURE)
            if not feature_tag:
                return
            form_tag = feature_tag.getTag('x', namespace=nbxmpp.NS_DATA)
            if not form_tag:
                return
            self.dataform = dataforms.ExtendForm(node=form_tag)
            for f in self.dataform.iter_fields():
                if f.var == 'stream-method' and f.type_ == 'list-single':
                    values = [o[1] for o in f.options]
                    self.file_props.stream_methods = ' '.join(values)
                    if nbxmpp.NS_BYTESTREAM in values or \
                    nbxmpp.NS_IBB in values:
                        break
            else:
                self.conn.send_file_rejection(self.file_props, code='400',
                    typ='stream')
                raise nbxmpp.NodeProcessed
            file_tag = si.getTag('file')
            for name, val in file_tag.getAttrs().items():
                if val is None:
                    continue
                if name == 'name':
                    self.file_props.name = val
                if name == 'size':
                    self.file_props.size = int(val)
            mime_type = si.getAttr('mime-type')
            if mime_type is not None:
                self.file_props.mime_type = mime_type
            self.file_props.sender = self.fjid
            self.file_props.receiver = self.conn._ft_get_our_jid()
        self.file_props.request_id = self.id_
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            self.file_props.desc = file_desc_tag.getData()
        self.file_props.transfered_size = []
        return True

class FileRequestErrorEvent(nec.NetworkIncomingEvent):
    name = 'file-request-error'
    base_network_events = []

    def generate(self):
        self.jid = app.get_jid_without_resource(self.jid)
        return True

class FileTransferCompletedEvent(nec.NetworkIncomingEvent):
    name = 'file-transfer-completed'
    base_network_events = []

    def generate(self):
        jid = str(self.file_props.receiver)
        self.jid = app.get_jid_without_resource(jid)
        return True

class GatewayPromptReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'gateway-prompt-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        query = self.stanza.getTag('query')
        if query:
            self.desc = query.getTagData('desc')
            self.prompt = query.getTagData('prompt')
            self.prompt_jid = query.getTagData('jid')
        else:
            self.desc = None
            self.prompt = None
            self.prompt_jid = None
        return True

class NotificationEvent(nec.NetworkIncomingEvent):
    name = 'notification'
    base_network_events = ['decrypted-message-received', 'gc-message-received',
        'presence-received']

    def detect_type(self):
        if self.base_event.name == 'decrypted-message-received':
            self.notif_type = 'msg'
        if self.base_event.name == 'gc-message-received':
            self.notif_type = 'gc-msg'
        if self.base_event.name == 'presence-received':
            self.notif_type = 'pres'

    def get_focused(self):
        self.control_focused = False
        if self.control:
            parent_win = self.control.parent_win
            if parent_win and self.control == parent_win.get_active_control() \
            and parent_win.window.get_property('has-toplevel-focus'):
                self.control_focused = True

    def handle_incoming_msg_event(self, msg_obj):
        # don't alert for carbon copied messages from ourselves
        if msg_obj.sent:
            return
        if not msg_obj.msgtxt:
            return
        self.jid = msg_obj.jid
        if msg_obj.session:
            self.control = msg_obj.session.control
        else:
            self.control = None
        self.get_focused()
        # This event has already been added to event list
        if not self.control and len(app.events.get_events(self.conn.name, \
        self.jid, [msg_obj.mtype])) <= 1:
            self.first_unread = True

        if msg_obj.mtype == 'pm':
            nick = msg_obj.resource
        else:
            nick = app.get_name_from_jid(self.conn.name, self.jid)

        if self.first_unread:
            self.sound_event = 'first_message_received'
        elif self.control_focused:
            self.sound_event = 'next_message_received_focused'
        else:
            self.sound_event = 'next_message_received_unfocused'

        if app.config.get('notification_preview_message'):
            self.popup_text = msg_obj.msgtxt
            if self.popup_text and (self.popup_text.startswith('/me ') or \
            self.popup_text.startswith('/me\n')):
                self.popup_text = '* ' + nick + self.popup_text[3:]
        else:
            # We don't want message preview, do_preview = False
            self.popup_text = ''
        if msg_obj.mtype == 'normal': # single message
            self.popup_msg_type = 'normal'
            self.popup_event_type = _('New Single Message')
            self.popup_image = 'gajim-single_msg_recv'
            self.popup_title = _('New Single Message from %(nickname)s') % \
                {'nickname': nick}
        elif msg_obj.mtype == 'pm':
            self.popup_msg_type = 'pm'
            self.popup_event_type = _('New Private Message')
            self.popup_image = 'gajim-priv_msg_recv'
            self.popup_title = _('New Private Message from group chat %s') % \
                msg_obj.jid
            if self.popup_text:
                self.popup_text = _('%(nickname)s: %(message)s') % \
                    {'nickname': nick, 'message': self.popup_text}
            else:
                self.popup_text = _('Messaged by %(nickname)s') % \
                    {'nickname': nick}
        else: # chat message
            self.popup_msg_type = 'chat'
            self.popup_event_type = _('New Message')
            self.popup_image = 'gajim-chat_msg_recv'
            self.popup_title = _('New Message from %(nickname)s') % \
                {'nickname': nick}


        if app.config.get('notify_on_new_message'):
            if self.first_unread or (app.config.get('autopopup_chat_opened') \
            and not self.control_focused):
                if app.config.get('autopopupaway'):
                    # always show notification
                    self.do_popup = True
                if app.connections[self.conn.name].connected in (2, 3):
                    # we're online or chat
                    self.do_popup = True

        if msg_obj.attention and not app.config.get(
        'ignore_incoming_attention'):
            self.popup_timeout = 0
            self.do_popup = True
        else:
            self.popup_timeout = app.config.get('notification_timeout')

        if msg_obj.attention and not app.config.get(
        'ignore_incoming_attention') and app.config.get_per('soundevents',
        'attention_received', 'enabled'):
            self.sound_event = 'attention_received'
            self.do_sound = True
        elif self.first_unread and helpers.allow_sound_notification(
        self.conn.name, 'first_message_received'):
            self.do_sound = True
        elif not self.first_unread and self.control_focused and \
        helpers.allow_sound_notification(self.conn.name,
        'next_message_received_focused'):
            self.do_sound = True
        elif not self.first_unread and not self.control_focused and \
        helpers.allow_sound_notification(self.conn.name,
        'next_message_received_unfocused'):
            self.do_sound = True

    def handle_incoming_gc_msg_event(self, msg_obj):
        if not msg_obj.msg_obj.gc_control:
            # we got a message from a room we're not in? ignore it
            return
        self.jid = msg_obj.jid
        sound = msg_obj.msg_obj.gc_control.highlighting_for_message(
            msg_obj.msgtxt, msg_obj.timestamp)[1]

        if msg_obj.nickname != msg_obj.msg_obj.gc_control.nick:
            self.do_sound = True
            if sound == 'received':
                self.sound_event = 'muc_message_received'
            elif sound == 'highlight':
                self.sound_event = 'muc_message_highlight'
            else:
                self.do_sound = False
        else:
            self.do_sound = False

        self.do_popup = False

    def get_path_to_generic_or_avatar(self, generic, jid=None, suffix=None):
        """
        Choose between avatar image and default image

        Returns full path to the avatar image if it exists, otherwise returns full
        path to the image.  generic must be with extension and suffix without
        """
        if jid:
            # we want an avatar
            puny_jid = helpers.sanitize_filename(jid)
            path_to_file = os.path.join(app.AVATAR_PATH, puny_jid) + suffix
            path_to_local_file = path_to_file + '_local'
            for extension in ('.png', '.jpeg'):
                path_to_local_file_full = path_to_local_file + extension
                if os.path.exists(path_to_local_file_full):
                    return path_to_local_file_full
            for extension in ('.png', '.jpeg'):
                path_to_file_full = path_to_file + extension
                if os.path.exists(path_to_file_full):
                    return path_to_file_full
        return os.path.abspath(generic)

    def handle_incoming_pres_event(self, pres_obj):
        if app.jid_is_transport(pres_obj.jid):
            return True
        account = pres_obj.conn.name
        self.jid = pres_obj.jid
        resource = pres_obj.resource or ''
        # It isn't an agent
        for c in pres_obj.contact_list:
            if c.resource == resource:
                # we look for other connected resources
                continue
            if c.show not in ('offline', 'error'):
                return True


        # no other resource is connected, let's look in metacontacts
        family = app.contacts.get_metacontacts_family(account, self.jid)
        for info in family:
            acct_ = info['account']
            jid_ = info['jid']
            c_ = app.contacts.get_contact_with_highest_priority(acct_, jid_)
            if not c_:
                continue
            if c_.jid == self.jid:
                continue
            if c_.show not in ('offline', 'error'):
                return True

        if pres_obj.old_show < 2 and pres_obj.new_show > 1:
            event = 'contact_connected'
            show_image = 'online.png'
            suffix = '_notif_size_colored'
            server = app.get_server_from_jid(self.jid)
            account_server = account + '/' + server
            block_transport = False
            if account_server in app.block_signed_in_notifications and \
            app.block_signed_in_notifications[account_server]:
                block_transport = True
            if helpers.allow_showing_notification(account, 'notify_on_signin') \
            and not app.block_signed_in_notifications[account] and \
            not block_transport:
                self.do_popup = True
            if app.config.get_per('soundevents', 'contact_connected',
            'enabled') and not app.block_signed_in_notifications[account] and\
            not block_transport and helpers.allow_sound_notification(account,
            'contact_connected'):
                self.sound_event = event
                self.do_sound = True

        elif pres_obj.old_show > 1 and pres_obj.new_show < 2:
            event = 'contact_disconnected'
            show_image = 'offline.png'
            suffix = '_notif_size_bw'
            if helpers.allow_showing_notification(account, 'notify_on_signout'):
                self.do_popup = True
            if app.config.get_per('soundevents', 'contact_disconnected',
            'enabled') and helpers.allow_sound_notification(account, event):
                self.sound_event = event
                self.do_sound = True
        # Status change (not connected/disconnected or error (<1))
        elif pres_obj.new_show > 1:
            event = 'status_change'
            # FIXME: we don't always 'online.png', but we first need 48x48 for
            # all status
            show_image = 'online.png'
            suffix = '_notif_size_colored'
        else:
            return True

        transport_name = app.get_transport_name_from_jid(self.jid)
        img_path = None
        if transport_name:
            img_path = os.path.join(helpers.get_transport_path(
                transport_name), '48x48', show_image)
        if not img_path or not os.path.isfile(img_path):
            iconset = app.config.get('iconset')
            img_path = os.path.join(helpers.get_iconset_path(iconset),
                '48x48', show_image)
        self.popup_image_path = self.get_path_to_generic_or_avatar(img_path,
            jid=self.jid, suffix=suffix)

        self.popup_timeout = app.config.get('notification_timeout')

        nick = i18n.direction_mark + app.get_name_from_jid(account, self.jid)
        if event == 'status_change':
            self.popup_title = _('%(nick)s Changed Status') % \
                {'nick': nick}
            self.popup_text = _('%(nick)s is now %(status)s') % \
                {'nick': nick, 'status': helpers.get_uf_show(pres_obj.show)}
            if pres_obj.status:
                self.popup_text = self.popup_text + " : " + pres_obj.status
            self.popup_event_type = _('Contact Changed Status')
        elif event == 'contact_connected':
            self.popup_title = _('%(nickname)s Signed In') % {'nickname': nick}
            self.popup_text = ''
            if pres_obj.status:
                self.popup_text = pres_obj.status
            self.popup_event_type = _('Contact Signed In')
        elif event == 'contact_disconnected':
            self.popup_title = _('%(nickname)s Signed Out') % {'nickname': nick}
            self.popup_text = ''
            if pres_obj.status:
                self.popup_text = pres_obj.status
            self.popup_event_type = _('Contact Signed Out')

    def generate(self):
        # what's needed to compute output
        self.conn = self.base_event.conn
        self.jid = ''
        self.control = None
        self.control_focused = False
        self.first_unread = False

        # For output
        self.do_sound = False
        self.sound_file = ''
        self.sound_event = '' # gajim sound played if not sound_file is set
        self.show_popup = False

        self.do_popup = False
        self.popup_title = ''
        self.popup_text = ''
        self.popup_event_type = ''
        self.popup_msg_type = ''
        self.popup_image = ''
        self.popup_image_path = ''
        self.popup_timeout = -1

        self.do_command = False
        self.command = ''

        self.show_in_notification_area = False
        self.show_in_roster = False

        self.detect_type()

        if self.notif_type == 'msg':
            self.handle_incoming_msg_event(self.base_event)
        elif self.notif_type == 'gc-msg':
            self.handle_incoming_gc_msg_event(self.base_event)
        elif self.notif_type == 'pres':
            self.handle_incoming_pres_event(self.base_event)
        return True

class MessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'message-outgoing'
    base_network_events = []

    def init(self):
        self.additional_data = {}
        self.message = None
        self.keyID = None
        self.type_ = 'chat'
        self.kind = None
        self.timestamp = None
        self.subject = ''
        self.chatstate = None
        self.stanza_id = None
        self.resource = None
        self.user_nick = None
        self.xhtml = None
        self.label = None
        self.session = None
        self.forward_from = None
        self.form_node = None
        self.delayed = None
        self.callback = None
        self.callback_args = []
        self.now = False
        self.is_loggable = True
        self.control = None
        self.attention = False
        self.correct_id = None
        self.automatic_message = True
        self.encryption = ''

    def get_full_jid(self):
        if self.resource:
            return self.jid + '/' + self.resource
        if self.session:
            return self.session.get_to()
        return self.jid

    def generate(self):
        if self.type_ == 'chat':
            self.kind = KindConstant.CHAT_MSG_SENT
        else:
            self.kind = KindConstant.SINGLE_MSG_SENT
        return True

class StanzaMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name='stanza-message-outgoing'
    base_network_events = []

    def generate(self):
        return True

class GcStanzaMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name='gc-stanza-message-outgoing'
    base_network_events = []

    def generate(self):
        return True

class GcMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'gc-message-outgoing'
    base_network_events = []

    def init(self):
        self.additional_data = {}
        self.message = ''
        self.chatstate = None
        self.xhtml = None
        self.stanza_id = None
        self.label = None
        self.callback = None
        self.callback_args = []
        self.is_loggable = True
        self.control = None
        self.correct_id = None
        self.automatic_message = True

    def generate(self):
        return True


class ClientCertPassphraseEvent(nec.NetworkIncomingEvent):
    name = 'client-cert-passphrase'
    base_network_events = []

class InformationEvent(nec.NetworkIncomingEvent):
    name = 'information'
    base_network_events = []

    def init(self):
        self.popup = True

class BlockingEvent(nec.NetworkIncomingEvent):
    name = 'blocking'
    base_network_events = []

    def init(self):
        self.blocklist = []
        self.blocked_jids = []
        self.unblocked_jids = []
        self.unblock_all = False

    def generate(self):
        block_list = self.stanza.getTag(
            'blocklist', namespace=nbxmpp.NS_BLOCKING)
        if block_list is not None:
            for item in block_list.getTags('item'):
                self.blocklist.append(item.getAttr('jid'))
            app.log('blocking').info(
                'Blocklist Received: %s', self.blocklist)
            return True

        block_tag = self.stanza.getTag('block', namespace=nbxmpp.NS_BLOCKING)
        if block_tag is not None:
            for item in block_tag.getTags('item'):
                self.blocked_jids.append(item.getAttr('jid'))
            app.log('blocking').info(
                'Blocking Push - blocked JIDs: %s', self.blocked_jids)

        unblock_tag = self.stanza.getTag(
            'unblock', namespace=nbxmpp.NS_BLOCKING)
        if unblock_tag is not None:
            if not unblock_tag.getTags('item'):
                self.unblock_all = True
                app.log('blocking').info('Blocking Push - unblocked all')
                return True
            for item in unblock_tag.getTags('item'):
                self.unblocked_jids.append(item.getAttr('jid'))
            app.log('blocking').info(
                'Blocking Push - unblocked JIDs: %s', self.unblocked_jids)
        return True
