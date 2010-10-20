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
from time import (localtime, time as time_time)
from calendar import timegm
import hmac

from common import nec
from common import helpers
from common import gajim
from common import xmpp
from common import dataforms
from common import exceptions
from common.logger import LOG_DB_PATH

import logging
log = logging.getLogger('gajim.c.connection_handlers_events')

class HelperEvent:
    def get_jid_resource(self):
        if hasattr(self, 'id_') and self.id_ in self.conn.groupchat_jids:
            self.fjid = self.conn.groupchat_jids[self.id_]
            del self.conn.groupchat_jids[self.id_]
        else:
            self.fjid = helpers.get_full_jid_from_iq(self.stanza)
        self.jid, self.resource = gajim.get_room_and_nick_from_fjid(self.fjid)

    def get_id(self):
        self.id_ = self.stanza.getID()

    def get_gc_control(self):
        self.gc_control = gajim.interface.msg_win_mgr.get_gc_control(self.jid,
            self.conn.name)

        # If gc_control is missing - it may be minimized. Try to get it
        # from there. If it's not there - then it's missing anyway and
        # will remain set to None.
        if not self.gc_control:
            minimized = gajim.interface.minimized_controls[self.conn.name]
            self.gc_control = minimized.get(self.jid)

    def _generate_timestamp(self, tag):
        tim = helpers.datetime_tuple(tag)
        self.timestamp = localtime(timegm(tim))

class HttpAuthReceivedEvent(nec.NetworkIncomingEvent):
    name = 'http-auth-received'
    base_network_events = []

    def generate(self):
        self.opt = gajim.config.get_per('accounts', self.conn.name, 'http_auth')
        self.iq_id = self.stanza.getTagAttr('confirm', 'id')
        self.method = self.stanza.getTagAttr('confirm', 'method')
        self.url = self.stanza.getTagAttr('confirm', 'url')
        # In case it's a message with a body
        self.msg = self.stanza.getTagData('body')
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

        if self.stanza.getType() == 'error':
            return True

        qp = self.stanza.getTag('query')
        if not qp:
            return
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
        self.get_jid_resource()
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
        except ValueError, e:
            try:
                t = datetime.datetime.strptime(utc_time,
                    '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError, e:
                log.info('Wrong time format: %s' % str(e))
                return

        t = t.replace(tzinfo=UTC())
        self.time_info = t.astimezone(contact_tz()).strftime('%c')
        return True

class GMailQueryReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gmail-notify'
    base_network_events = []

    def generate(self):
        if not self.stanza.getTag('mailbox'):
            return
        mb = self.stanza.getTag('mailbox')
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
        items_list = self.stanza.getTag('x').getChildren()
        if not items_list:
            return
        self.action = items_list[0].getAttr('action')
        if self.action is None:
            self.action = 'add'
        for item in self.stanza.getTag('x', namespace=xmpp.NS_ROSTERX).\
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
        if hasattr(self, 'xmpp_roster'):
            self.version = self.xmpp_roster.version
            self.received_from_server = self.xmpp_roster.received_from_server
            self.roster = {}
            raw_roster = self.xmpp_roster.getRaw()
            our_jid = gajim.get_jid_from_account(self.conn.name)

            for jid in raw_roster:
                try:
                    j = helpers.parse_jid(jid)
                except Exception:
                    print >> sys.stderr, _('JID %s is not RFC compliant. It '
                        'will not be added to your roster. Use roster '
                        'management tools such as '
                        'http://jru.jabberstudio.org/ to remove it') % jid
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
        else:
            # Roster comes from DB
            self.received_from_server = False
            self.version = gajim.config.get_per('accounts', self.conn.name,
                'roster_version')
            self.roster = gajim.logger.get_roster(gajim.get_jid_from_account(
                self.conn.name))
        return True

class RosterSetReceivedEvent(nec.NetworkIncomingEvent):
    name = 'roster-set-received'
    base_network_events = []

    def generate(self):
        self.version = self.stanza.getTagAttr('query', 'ver')
        self.items = {}
        for item in self.stanza.getTag('query').getChildren():
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
            reply = xmpp.Iq(typ='result', attrs={'id': self.stanza.getID()},
                to=self.stanza.getFrom(), frm=self.stanza.getTo(), xmlns=None)
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
        qp = self.stanza.getQueryPayload()
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
        items = self.stanza.getTag('query',
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
        query = self.stanza.getTag('query')
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
        self.pubsub_node = self.stanza.getTag('pubsub')
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
        tag = self.stanza.getTag('query', namespace=xmpp.NS_SEARCH)
        if not tag:
            return True
        self.data = tag.getTag('x', namespace=xmpp.NS_DATA)
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
        tag = self.stanza.getTag('query', namespace=xmpp.NS_SEARCH)
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

class IqErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'iq-error-received'
    base_network_events = []

    def generate(self):
        self.get_id()
        self.get_jid_resource()
        self.errmsg = self.stanza.getErrorMsg()
        self.errcode = self.stanza.getErrorCode()
        return True

class GmailNewMailReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gmail-new-mail-received'
    base_network_events = []

    def generate(self):
        if not self.stanza.getTag('new-mail'):
            return
        if self.stanza.getTag('new-mail').getNamespace() != xmpp.NS_GMAILNOTIFY:
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
        if self.base_event.stanza.getTag('conflict'):
            self.conn = self.base_event.conn
            return True

class PresenceReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
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
                self.jid, self.keyID)

    def _generate_show(self):
        self.show = self.stanza.getShow()
        if self.show not in ('chat', 'away', 'xa', 'dnd'):
            self.show = '' # We ignore unknown show
        if not self.ptype and not self.show:
            self.show = 'online'
        elif self.ptype == 'unavailable':
            self.show = 'offline'

    def _generate_prio(self):
        self.prio = self.stanza.getPriority()
        try:
            self.prio = int(self.prio)
        except Exception:
            self.prio = 0

    def _generate_ptype(self):
        self.ptype = self.stanza.getType()
        if self.ptype == 'available':
            self.ptype = None
        rfc_types = ('unavailable', 'error', 'subscribe', 'subscribed',
            'unsubscribe', 'unsubscribed')
        if self.ptype and not self.ptype in rfc_types:
            self.ptype = None

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza

        self.need_add_in_roster = False
        self.need_redraw = False

        if not self.conn or self.conn.connected < 2:
            log.debug('account is no more connected')
            return

        self._generate_ptype()
        try:
            self.get_jid_resource()
        except Exception:
            return
        jid_list = gajim.contacts.get_jid_list(self.conn.name)
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
        delay_tag = self.stanza.getTag('delay', namespace=xmpp.NS_DELAY2)
        if delay_tag:
            self._generate_timestamp(self.stanza.getTimestamp2())
        xtags = self.stanza.getTags('x')
        for x in xtags:
            namespace = x.getNamespace()
            if namespace.startswith(xmpp.NS_MUC):
                self.is_gc = True
            elif namespace == xmpp.NS_SIGNED:
                sig_tag = x
            elif namespace == xmpp.NS_VCARD_UPDATE:
                self.avatar_sha = x.getTagData('photo')
                self.contact_nickname = x.getTagData('nickname')
            elif namespace == xmpp.NS_DELAY and not self.timestamp:
                # XEP-0091
                self._generate_timestamp(self.stanza.getTimestamp())
            elif namespace == 'http://delx.cjb.net/protocol/roster-subsync':
                # see http://trac.gajim.org/ticket/326
                agent = gajim.get_server_from_jid(self.jid)
                if self.conn.connection.getRoster().getItem(agent):
                    # to be sure it's a transport contact
                    self.transport_auto_auth = True

        if not self.is_gc and self.id_ and self.id_.startswith('gajim_muc_') \
        and self.ptype == 'error':
            # Error presences may not include sent stanza, so we don't detect
            # it's a muc presence. So detect it by ID
            h = hmac.new(self.conn.secret_hmac, self.jid).hexdigest()[:6]
            if self.id_.split('_')[-1] == h:
                self.is_gc = True
        self.status = self.stanza.getStatus() or ''
        self._generate_show()
        self._generate_prio()
        self._generate_keyID(sig_tag)

        self.errcode = self.stanza.getErrorCode()
        self.errmsg = self.stanza.getErrorMsg()

        if self.is_gc:
            gajim.nec.push_incoming_event(GcPresenceReceivedEvent(None,
                conn=self.conn, stanza=self.stanza, presence_obj=self))
            return

        if self.ptype == 'subscribe':
            gajim.nec.push_incoming_event(SubscribePresenceReceivedEvent(None,
                conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'subscribed':
            # BE CAREFUL: no con.updateRosterItem() in a callback
            gajim.nec.push_incoming_event(SubscribedPresenceReceivedEvent(None,
                conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'unsubscribe':
            log.debug(_('unsubscribe request from %s') % self.jid)
        elif self.ptype == 'unsubscribed':
            gajim.nec.push_incoming_event(UnsubscribedPresenceReceivedEvent(
                None, conn=self.conn, stanza=self.stanza, presence_obj=self))
        elif self.ptype == 'error':
            if self.errcode != '409': # conflict # See #5120
                self.show = 'error'
                self.status = self.errmsg
                return True

        if not self.ptype or self.ptype == 'unavailable':
            our_jid = gajim.get_jid_from_account(self.conn.name)
            if self.jid == our_jid and self.resource == \
            self.conn.server_resource:
                # We got our own presence
                self.conn.dispatch('STATUS', self.show)
            elif self.jid in jid_list or self.jid == our_jid:
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
        self.gc_contact = gajim.contacts.get_gc_contact(self.conn.name,
            self.room_jid, self.nick)

        if self.ptype == 'error':
            return True

        if self.ptype and self.ptype != 'unavailable':
            return
        if gajim.config.get('log_contact_status_changes') and \
        gajim.config.should_log(self.conn.name, self.room_jid):
            if self.gc_contact:
                jid = self.gc_contact.jid
            else:
                jid = self.stanza.getJid()
            st = self.status
            if jid:
                # we know real jid, save it in db
                st += ' (%s)' % jid
            try:
                gajim.logger.write('gcstatus', self.fjid, st,
                    self.show)
            except exceptions.PysqliteOperationalError, e:
                self.conn.dispatch('DB_ERROR', (_('Disk Write Error'),
                    str(e)))
            except exceptions.DatabaseMalformed:
                pritext = _('Database Error')
                sectext = _('The database file (%s) cannot be read. '
                    'Try to repair it (see '
                    'http://trac.gajim.org/wiki/DatabaseBackup) or '
                    'remove it (all history will be lost).') % \
                    LOG_DB_PATH
                self.conn.dispatch('DB_ERROR', (pritext, sectext))
        if self.avatar_sha == '':
            # contact has no avatar
            puny_nick = helpers.sanitize_filename(self.nick)
            gajim.interface.remove_avatar_files(self.room_jid, puny_nick)
        # NOTE: if it's a gc presence, don't ask vcard here.
        # We may ask it to real jid in gui part.
        self.status_code = []
        ns_muc_user_x = self.stanza.getTag('x', namespace=xmpp.NS_MUC_USER)
        destroy = ns_muc_user_x.getTag('destroy')
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
                except common.helpers.InvalidFormat:
                    pass
            self.status_code = ['destroyed']
        else:
            self.reason = self.stanza.getReason()
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

class MessageReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'message-received'
    base_network_events = ['raw-message-received']

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza
        self.get_id()

        account = self.conn.name

        # check if the message is a roster item exchange (XEP-0144)
        if self.stanza.getTag('x', namespace=xmpp.NS_ROSTERX):
            gajim.nec.push_incoming_event(RosterItemExchangeEvent(None,
                conn=self.conn, stanza=self.stanza))
            return

        # check if the message is a XEP-0070 confirmation request
        if self.stanza.getTag('confirm', namespace=xmpp.NS_HTTP_AUTH):
            gajim.nec.push_incoming_event(HttpAuthReceivedEvent(None,
                conn=self.conn, stanza=self.stanza))
            return

        try:
            self.get_jid_resource()
        except helpers.InvalidFormat:
            self.conn.dispatch('ERROR', (_('Invalid Jabber ID'),
                _('A message from a non-valid JID arrived, it has been '
                'ignored.')))
            return

        address_tag = self.stanza.getTag('addresses', namespace=xmpp.NS_ADDRESS)
        # Be sure it comes from one of our resource, else ignore address element
        if address_tag and self.jid == gajim.get_jid_from_account(account):
            address = address_tag.getTag('address', attrs={'type': 'ofrom'})
            if address:
                try:
                    self.fjid = helpers.parse_jid(address.getAttr('jid'))
                except helpers.InvalidFormat:
                    log.warn('Invalid JID: %s, ignoring it' % address.getAttr(
                        'jid'))
                    return
                self.jid = gajim.get_jid_without_resource(self.fjid)

        self.enc_tag = self.stanza.getTag('x', namespace=xmpp.NS_ENCRYPTED)

        self.invite_tag = None
        if not self.enc_tag:
            self.invite_tag = self.stanza.getTag('x',
                namespace=xmpp.NS_MUC_USER)
            if self.invite_tag and not self.invite_tag.getTag('invite'):
                self.invite_tag = None

        self.thread_id = self.stanza.getThread()
        self.mtype = self.stanza.getType()
        if not self.mtype or self.mtype not in ('chat', 'groupchat', 'error'):
            self.mtype = 'normal'

        self.msgtxt = self.stanza.getBody()

        self.get_gc_control()

        if self.gc_control and self.jid == self.fjid:
            # message from a gc without a resource
            self.mtype = 'groupchat'

        self.session = None
        if self.mtype != 'groupchat':
            self.session = self.conn.get_or_create_session(self.fjid,
                self.thread_id)

            if self.thread_id and not self.session.received_thread_id:
                self.session.received_thread_id = True

            self.session.last_receive = time_time()

        # check if the message is a XEP-0020 feature negotiation request
        if self.stanza.getTag('feature', namespace=xmpp.NS_FEATURE):
            if gajim.HAVE_PYCRYPTO:
                feature = self.stanza.getTag(name='feature',
                    namespace=xmpp.NS_FEATURE)
                form = xmpp.DataForm(node=feature.getTag('x'))

                if form['FORM_TYPE'] == 'urn:xmpp:ssn':
                    self.session.handle_negotiation(form)
                else:
                    reply = self.stanza.buildReply()
                    reply.setType('error')
                    reply.addChild(feature)
                    err = xmpp.ErrorNode('service-unavailable', typ='cancel')
                    reply.addChild(node=err)
                    self.conn.connection.send(reply)
            return

        if self.stanza.getTag('init', namespace=xmpp.NS_ESESSION_INIT):
            init = self.stanza.getTag(name='init',
                namespace=xmpp.NS_ESESSION_INIT)
            form = xmpp.DataForm(node=init.getTag('x'))

            self.session.handle_negotiation(form)

            return

        self._generate_timestamp(self.stanza.getTimestamp())

        self.encrypted = False
        xep_200_encrypted = self.stanza.getTag('c',
            namespace=xmpp.NS_STANZA_CRYPTO)
        if xep_200_encrypted:
            self.encrypted = 'xep200'

        return True

class GcInvitationReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-invitation-received'
    base_network_events = []

    def generate(self):
        self.room_jid = self.msg_obj.fjid

        item = self.msg_obj.invite_tag.getTag('invite')
        try:
            self.jid_from = helpers.parse_jid(item.getAttr('from'))
        except helpers.InvalidFormat:
            log.warn('Invalid JID: %s, ignoring it' % item.getAttr('from'))
            return
        self.reason = item.getTagData('reason')
        self.password = self.msg_obj.invite_tag.getTagData('password')

        self.is_continued = False
        if item.getTag('continue'):
            self.is_continued = True

        return True

class DecryptedMessageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'decrypted-message-received'
    base_network_events = []

    def generate(self):
        self.stanza = self.msg_obj.stanza
        self.id_ = self.msg_obj.id_
        self.jid = self.msg_obj.jid
        self.fjid = self.msg_obj.fjid
        self.resource = self.msg_obj.resource
        self.mtype = self.msg_obj.mtype
        self.invite_tag = self.msg_obj.invite_tag
        self.thread_id = self.msg_obj.thread_id
        self.msgtxt = self.msg_obj.msgtxt
        self.gc_control = self.msg_obj.gc_control
        self.session = self.msg_obj.session
        self.timestamp = self.msg_obj.timestamp
        self.encrypted = self.msg_obj.encrypted

        self.receipt_request_tag = self.stanza.getTag('request',
            namespace=xmpp.NS_RECEIPTS)
        self.receipt_received_tag = self.stanza.getTag('received',
            namespace=xmpp.NS_RECEIPTS)
        return True

class GcMessageReceivedEvent(nec.NetworkIncomingEvent):
    name = 'gc-message-received'
    base_network_events = []

    def generate(self):
        self.stanza = self.msg_obj.stanza
        self.fjid = self.msg_obj.fjid
        self.msgtxt = self.msg_obj.msgtxt
        self.jid = self.msg_obj.jid
        self.room_jid = self.msg_obj.jid
        self.timestamp = self.msg_obj.timestamp
        self.xhtml_msgtxt = self.stanza.getXHTML()

        if gajim.config.get('ignore_incoming_xhtml'):
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
            self.conn.dispatch('GC_SUBJECT', (self.fjid, self.subject,
                self.msgtxt, self.has_timestamp))
            return

        self.status_code = self.stanza.getStatusCode()

        if not self.stanza.getTag('body'): # no <body>
            # It could be a config change. See
            # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
            if self.stanza.getTag('x'):
                if self.status_code != []:
                    self.conn.dispatch('GC_CONFIG_CHANGE', (self.jid,
                        self.status_code))
            return

        self.displaymarking = None
        seclabel = self.stanza.getTag('securitylabel')
        if seclabel and seclabel.getNamespace() == xmpp.NS_SECLABEL:
            # Ignore message from room in which we are not
            self.displaymarking = seclabel.getTag('displaymarking')

        if self.jid not in self.conn.last_history_time:
            return

        self.captcha_form = None
        captcha_tag = self.stanza.getTag('captcha', namespace=xmpp.NS_CAPTCHA)
        if captcha_tag:
            self.captcha_form = captcha_tag.getTag('x', namespace=xmpp.NS_DATA)
            for field in self.captcha_form.getTags('field'):
                for media in field.getTags('media'):
                    for uri in media.getTags('uri'):
                        uri_data = uri.getData()
                        if uri_data.startswith('cid:'):
                            uri_data = uri_data[4:]
                            found = False
                            for data in self.stanza.getTags('data',
                            namespace=xmpp.NS_BOB):
                                if data.getAttr('cid') == uri_data:
                                    uri.setData(data.getData())
                                    found = True
                            if not found:
                                self.conn.get_bob_data(uri_data, frm,
                                    self.conn._dispatch_gc_msg_with_captcha,
                                    [self.stanza, self.msg_obj], 0)
                                return

        return True
