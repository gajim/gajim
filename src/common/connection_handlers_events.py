# -*- coding:utf-8 -*-
## src/common/connection_handlers_events.py
##
## Copyright (C) 2010 Yann Leboulanger <asterix AT lagaule.org>
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

import datetime
import sys

from common import nec
from common import helpers
from common import gajim
from common import xmpp
from common import dataforms

import logging
log = logging.getLogger('gajim.c.connection_handlers_events')

class HelperEvent:
    def get_jid_resource(self):
        if hasattr(self, 'id_') and self.id_ in self.conn.groupchat_jids:
            self.fjid = self.conn.groupchat_jids[self.id_]
            del self.conn.groupchat_jids[self.id_]
        else:
            self.fjid = helpers.get_full_jid_from_iq(self.iq_obj)
        self.jid, self.resource = gajim.get_room_and_nick_from_fjid(self.fjid)

    def get_id(self):
        self.id_ = self.iq_obj.getID()

class HttpAuthReceivedEvent(nec.NetworkIncomingEvent):
    name = 'http-auth-received'
    base_network_events = []

    def generate(self):
        self.opt = gajim.config.get_per('accounts', self.conn.name, 'http_auth')
        self.iq_id = self.iq_obj.getTagAttr('confirm', 'id')
        self.method = self.iq_obj.getTagAttr('confirm', 'method')
        self.url = self.iq_obj.getTagAttr('confirm', 'url')
        # In case it's a message with a body
        self.msg = self.iq_obj.getTagData('body')
        return True

class LastResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'last-result-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        if self.id_ in self.conn.last_ids:
            self.conn.last_ids.remove(self.id_)

        self.status = ''
        self.seconds = -1

        if self.iq_obj.getType() == 'error':
            return True

        qp = self.iq_obj.getTag('query')
        sec = qp.getAttr('seconds')
        self.status = qp.getData()
        try:
            self.seconds = int(sec)
        except Exception:
            return

        return True

class VersionResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'version-result-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        if self.id_ in self.conn.version_ids:
            self.conn.version_ids.remove(self.id_)

        self.client_info = ''
        self.os_info = ''

        if self.iq_obj.getType() == 'error':
            return True

        qp = self.iq_obj.getTag('query')
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
        self.get_jid_resource()
        if self.id_ in self.conn.entity_time_ids:
            self.conn.entity_time_ids.remove(self.id_)

        self.time_info = ''

        if self.iq_obj.getType() == 'error':
            return True

        qp = self.iq_obj.getTag('time')
        if not qp:
            # wrong answer
            return
        tzo = qp.getTag('tzo').getData()
        if tzo.lower() == 'z':
            tzo = '0:0'
        tzoh, tzom = tzo.split(':')
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

        try:
            t = datetime.datetime.strptime(utc_time, '%Y-%m-%dT%H:%M:%SZ')
            t = t.replace(tzinfo=UTC())
            self.time_info = t.astimezone(contact_tz()).strftime('%c')
        except ValueError, e:
            log.info('Wrong time format: %s' % str(e))
            return

        return True

class GMailQueryReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gmail-notify'
    base_network_events = []

    def generate(self):
        if not self.iq_obj.getTag('mailbox'):
            return
        mb = self.iq_obj.getTag('mailbox')
        if not mb.getAttr('url'):
            return
        self.conn.gmail_url = mb.getAttr('url')
        if mb.getNamespace() != xmpp.NS_GMAILNOTIFY:
            return
        self.newmsgs = mb.getAttr('total-matched')
        if not self.newmsgs:
            return
        if self.newmsgs == '0':
            return
        # there are new messages
        self.gmail_messages_list = []
        if mb.getTag('mail-thread-info'):
            gmail_messages = mb.getTags('mail-thread-info')
            for gmessage in gmail_messages:
                unread_senders = []
                for sender in gmessage.getTag('senders').getTags(
                'sender'):
                    if sender.getAttr('unread') != '1':
                        continue
                    if sender.getAttr('name'):
                        unread_senders.append(sender.getAttr('name') + \
                            '< ' + sender.getAttr('address') + '>')
                    else:
                        unread_senders.append(sender.getAttr('address'))

                if not unread_senders:
                    continue
                gmail_subject = gmessage.getTag('subject').getData()
                gmail_snippet = gmessage.getTag('snippet').getData()
                tid = int(gmessage.getAttr('tid'))
                if not self.conn.gmail_last_tid or \
                tid > self.conn.gmail_last_tid:
                    self.conn.gmail_last_tid = tid
                self.gmail_messages_list.append({
                    'From': unread_senders,
                    'Subject': gmail_subject,
                    'Snippet': gmail_snippet,
                    'url': gmessage.getAttr('url'),
                    'participation': gmessage.getAttr('participation'),
                    'messages': gmessage.getAttr('messages'),
                    'date': gmessage.getAttr('date')})
            self.conn.gmail_last_time = int(mb.getAttr('result-time'))

        self.jid = gajim.get_jid_from_account(self.name)
        log.debug(('You have %s new gmail e-mails on %s.') % (self.newmsgs,
            self.jid))
        return True

class RosterItemExchangeEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'roster-item-exchange-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        self.exchange_items_list = {}
        items_list = self.iq_obj.getTag('x').getChildren()
        if not items_list:
            return
        self.action = items_list[0].getAttr('action')
        if self.action is None:
            self.action = 'add'
        for item in self.iq_obj.getTag('x', namespace=xmpp.NS_ROSTERX).\
        getChildren():
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warn('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            contact = gajim.contacts.get_contact(self.conn.name, jid)
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
        self.version = self.xmpp_roster.version
        self.received_from_server = self.xmpp_roster.received_from_server
        self.roster = {}
        raw_roster = self.xmpp_roster.getRaw()
        our_jid = gajim.get_jid_from_account(self.name)

        for jid in raw_roster:
            try:
                j = helpers.parse_jid(jid)
            except Exception:
                print >> sys.stderr, _('JID %s is not RFC compliant. It will not be added to your roster. Use roster management tools such as http://jru.jabberstudio.org/ to remove it') % jid
            else:
                infos = raw_roster[jid]
                if jid != our_jid and (not infos['subscription'] or \
                infos['subscription'] == 'none') and (not infos['ask'] or \
                infos['ask'] == 'none') and not infos['name'] and \
                not infos['groups']:
                    # remove this useless item, it won't be shown in roster anyway
                    self.conn.connection.getRoster().delItem(jid)
                elif jid != our_jid: # don't add our jid
                    self.roster[j] = raw_roster[jid]
        return True

class RosterSetReceivedEvent(nec.NetworkIncomingEvent):
    name = 'roster-set-received'
    base_network_events = []

    def generate(self):
        self.version = self.iq_obj.getTagAttr('query', 'ver')
        self.items = {}
        for item in self.iq_obj.getTag('query').getChildren():
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warn('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
                continue
            name = item.getAttr('name')
            sub = item.getAttr('subscription')
            ask = item.getAttr('ask')
            groups = []
            for group in item.getTags('group'):
                groups.append(group.getData())
            self.items[jid] = {'name': name, 'sub': sub, 'ask': ask,
                'groups': groups}
        if self.conn.connection and self.conn.connected > 1:
            reply = xmpp.Iq(typ='result', attrs={'id': self.iq_obj.getID()},
                to=self.iq_obj.getFrom(), frm=self.iq_obj.getTo(), xmlns=None)
            self.conn.connection.send(reply)
        return True

class RosterInfoEvent(nec.NetworkIncomingEvent):
    name = 'roster-info'
    base_network_events = []

class MucOwnerReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'muc-owner-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        qp = self.iq_obj.getQueryPayload()
        self.form_node = None
        for q in qp:
            if q.getNamespace() == xmpp.NS_DATA:
                self.form_node = q
                self.dataform = dataforms.ExtendForm(node=self.form_node)
                return True

class MucAdminReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'muc-admin-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        items = self.iq_obj.getTag('query',
            namespace=xmpp.NS_MUC_ADMIN).getTags('item')
        self.users_dict = {}
        for item in items:
            if item.has_attr('jid') and item.has_attr('affiliation'):
                try:
                    jid = helpers.parse_jid(item.getAttr('jid'))
                except helpers.InvalidFormat:
                    log.warn('Invalid JID: %s, ignoring it' % \
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
        query = self.iq_obj.getTag('query')
        self.storage_node = query.getTag('storage')
        if self.storage_node:
            self.namespace = self.storage_node.getNamespace()
            return True

class BookmarksHelper:
    def parse_bookmarks(self):
        self.bookmarks = []
        confs = self.base_event.storage_node.getTags('conference')
        for conf in confs:
            autojoin_val = conf.getAttr('autojoin')
            if autojoin_val is None: # not there (it's optional)
                autojoin_val = False
            minimize_val = conf.getAttr('minimize')
            if minimize_val is None: # not there (it's optional)
                minimize_val = False
            print_status = conf.getTagData('print_status')
            if not print_status:
                print_status = conf.getTagData('show_status')
            try:
                jid = helpers.parse_jid(conf.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warn('Invalid JID: %s, ignoring it' % conf.getAttr('jid'))
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
        if self.base_event.namespace != 'storage:bookmarks':
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
        if self.base_event.namespace != 'storage:rosternotes':
            return
        notes = self.base_event.storage_node.getTags('note')
        self.annotations = {}
        for note in notes:
            try:
                jid = helpers.parse_jid(note.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warn('Invalid JID: %s, ignoring it' % note.getAttr('jid'))
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
        self.pubsub_node = self.iq_obj.getTag('pubsub')
        if not self.pubsub_node:
            return
        self.items_node = self.pubsub_node.getTag('items')
        if not self.items_node:
            return
        self.item_node = self.items_node.getTag('item')
        if not self.item_node:
            return
        return True

class PubsubBookmarksReceivedEvent(nec.NetworkIncomingEvent, BookmarksHelper):
    name = 'pubsub-bookmarks-received'
    base_network_events = ['pubsub-received']

    def generate(self):
        self.conn = self.base_event.conn
        storage = self.base_event.item_node.getTag('storage')
        if not storage:
            return
        ns = storage.getNamespace()
        if ns != 'storage:bookmarks':
            return
        self.parse_bookmarks()
        return True

class SearchFormReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'search-form-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.data = None
        self.is_dataform = False
        tag = self.iq_obj.getTag('query', namespace=xmpp.NS_SEARCH)
        if not tag:
            return True
        self.data = tag.getTag('x', namespace=xmpp.NS_DATA)
        if self.data:
            self.is_dataform = True
            return True
        self.data = {}
        for i in self.iq_obj.getQueryPayload():
            self.data[i.getName()] = i.getData()
        return True


class SearchResultReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'search-result-received'
    base_network_events = []

    def generate(self):
        self.get_jid_resource()
        self.data = None
        self.is_dataform = False
        tag = self.iq_obj.getTag('query', namespace=xmpp.NS_SEARCH)
        if not tag:
            return True
        self.data = tag.getTag('x', namespace=xmpp.NS_DATA)
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

class ErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'error-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        self.errmsg = self.iq_obj.getErrorMsg()
        self.errcode = self.iq_obj.getErrorCode()
        return True

class GmailNewMailReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gmail-new-mail-received'
    base_network_events = []

    def generate(self):
        if not self.iq_obj.getTag('new-mail'):
            return
        if self.iq_obj.getTag('new-mail').getNamespace() != xmpp.NS_GMAILNOTIFY:
            return
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
        if self.base_event.iq_obj.getTag('conflict'):
            self.conn = self.base_event.conn
            return True
